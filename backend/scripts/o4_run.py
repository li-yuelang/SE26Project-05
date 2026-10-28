"""Linux-only open-loop O4 runner. One iteration is one authenticated GET.

Run from backend, with DATABASE_URL and O4_TEST_PASSWORD supplied privately.
No credentials, response bodies or query parameters are written to evidence.
"""

import argparse
import asyncio
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import subprocess
import time

import httpx
from prometheus_client.parser import text_string_to_metric_families

SELECTOR = 'job="papermate-o4",method="GET",route="/api/papers/discover"'


def percentile(values, p):
    return sorted(values)[max(0, math.ceil(p * len(values)) - 1)] if values else None


def samples(text):
    return {(s.name, tuple(sorted(s.labels.items()))): s.value
            for family in text_string_to_metric_families(text) for s in family.samples}


def json_write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def collectors(directory, api_pid):
    processes = []
    for name, command in {
        "vmstat": ["vmstat", "-t", "-w", "1"],
        "mpstat": ["mpstat", "-P", "ALL", "1"],
        "iostat": ["iostat", "-d", "-x", "-t", "vda", "1"],
        "pidstat": ["pidstat", "-h", "-u", "-r", "-w", "-p", str(api_pid), "1"],
    }.items():
        handle = (directory / f"{name}.log").open("w")
        env = os.environ.copy()
        env.update(LC_ALL="C", S_TIME_FORMAT="ISO")
        processes.append((subprocess.Popen(command, stdout=handle, stderr=handle, env=env), handle))
    return processes


async def run(args, directory):
    password = os.environ.get("O4_TEST_PASSWORD")
    if not password:
        raise ValueError("Set private O4_TEST_PASSWORD in the environment")
    api_pid = int(subprocess.check_output(
        ["systemctl", "show", "-p", "MainPID", "--value", "papermate-o4-api"], text=True))
    if not api_pid:
        raise RuntimeError("O4 API is not running")
    metadata = {
        "kind": args.kind, "name": args.name, "target": "/api/papers/discover",
        "page": 1, "page_size": 20, "rates": args.rates, "step_seconds": args.step,
        "arrival": "poisson", "seed": args.seed, "timeout_seconds": args.timeout,
        "max_inflight": args.max_inflight, "auth": "Bearer token in memory, login outside stages",
        "generator_affinity": sorted(os.sched_getaffinity(0)),
        "api_affinity": sorted(os.sched_getaffinity(api_pid)), "api_pid": api_pid,
        "hostname": os.uname().nodename, "kernel": os.uname().release,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "client_latency": "planned arrival to complete response body, successful requests only",
        "steady_client_window": "planned arrivals from stage start+5s to stage end-1s",
        "server_window": "Prometheus window [start+5s,end-1s], may differ by scrape and completion boundaries",
        "duration_scope": "server ends at final ASGI response body, pool hold ends at checkin",
        "abort_on": "generator warning or fewer than half scheduled arrivals successfully completed",
    }
    manifest = Path("../SOURCE_MANIFEST.json")
    if manifest.exists():
        metadata["source_manifest"] = json.loads(manifest.read_text())
    async with httpx.AsyncClient(base_url=args.api, timeout=args.timeout,
                                limits=httpx.Limits(max_connections=args.max_inflight + 8,
                                                    max_keepalive_connections=args.max_inflight + 8)) as client:
        response = await client.post("/api/auth/login", json={
            "email": "o4_bench@example.com", "password": password})
        response.raise_for_status()
        token = response.json()["data"]["access_token"]
        headers = {"Authorization": "Bearer " + token}
        for _ in range(10):
            warm = await client.get("/api/papers/discover?page=1&page_size=20", headers=headers)
            warm.raise_for_status()
        metadata["paper_count"] = warm.json()["data"]["total"]
        initial = (await client.get("/metrics")).text
        initial_samples = samples(initial)
        metadata["pool_capacity"] = initial_samples["papermate_db_pool_capacity", ()]
        (directory / "metrics-start.txt").write_text(initial)
        json_write(directory / "meta.json", metadata)
        processes = collectors(directory, api_pid)
        rng = random.Random(args.seed)
        results = []
        requests_log = (directory / "requests.jsonl").open("w")
        try:
            for number, rate in enumerate(args.rates):
                start = time.monotonic()
                start_wall = time.time()
                cpu_start = time.process_time()
                records = []
                tasks = set()
                next_arrival = 0.0
                scheduled = 0

                async def one_request(planned):
                    actual = time.monotonic()
                    code = 0
                    error = ""
                    try:
                        response = await client.get("/api/papers/discover?page=1&page_size=20", headers=headers)
                        code = response.status_code
                    except httpx.TimeoutException:
                        error = "timeout"
                    except httpx.HTTPError:
                        error = "transport"
                    records.append({"step": number, "planned_offset_s": planned - start,
                                    "lag_ms": 1000 * (actual - planned),
                                    "latency_ms": 1000 * (time.monotonic() - planned),
                                    "code": code, "error": error})

                if rate > 0:
                    while True:
                        next_arrival += rng.expovariate(rate)
                        if next_arrival >= args.step:
                            break
                        planned = start + next_arrival
                        await asyncio.sleep(max(0, planned - time.monotonic()))
                        scheduled += 1
                        if len(tasks) >= args.max_inflight:
                            records.append({"step": number, "planned_offset_s": next_arrival,
                                            "lag_ms": 1000 * max(0, time.monotonic() - planned),
                                            "latency_ms": None, "code": 0, "error": "dropped"})
                        else:
                            task = asyncio.create_task(one_request(planned))
                            tasks.add(task)
                            task.add_done_callback(tasks.discard)
                await asyncio.sleep(max(0, start + args.step - time.monotonic()))
                cpu_at_end = time.process_time()
                end_wall = start_wall + args.step
                pending_at_end = len(tasks)
                if tasks:
                    await asyncio.gather(*tasks)
                sent = [r for r in records if r["error"] != "dropped"]
                ok = [r for r in sent if 200 <= r["code"] < 300]
                steady = [r for r in records if 5 <= r["planned_offset_s"] < args.step - 1]
                steady_ok = [r for r in steady if 200 <= r["code"] < 300]
                generator_cpu = 100 * (cpu_at_end - cpu_start) / args.step
                lag = percentile([r["lag_ms"] for r in sent], .99)
                warnings = []
                if scheduled > len(sent):
                    warnings.append("dropped arrivals")
                if lag is not None and lag > 10:
                    warnings.append("generator lag p99 >10ms")
                if generator_cpu > 80:
                    warnings.append("generator CPU >80% of one logical CPU")
                row = {
                    "step": number, "target_rps": rate, "start_unix": start_wall, "end_unix": end_wall,
                    "scheduled": scheduled, "sent": len(sent), "ok": len(ok),
                    "ok_rps": len(ok) / args.step,
                    "error_rate": (scheduled - len(ok)) / scheduled if scheduled else None,
                    "mean_ms": sum(r["latency_ms"] for r in ok) / len(ok) if ok else None,
                    "p99_ms": percentile([r["latency_ms"] for r in ok], .99),
                    "steady_ok_rps": len(steady_ok) / (args.step - 6),
                    "steady_mean_ms": sum(r["latency_ms"] for r in steady_ok) / len(steady_ok) if steady_ok else None,
                    "steady_p99_ms": percentile([r["latency_ms"] for r in steady_ok], .99),
                    "lag_p99_ms": lag, "gen_cpu_pct": generator_cpu,
                    "pending_at_end": pending_at_end, "warn": "; ".join(warnings),
                }
                for record in sorted(records, key=lambda r: r["planned_offset_s"]):
                    requests_log.write(json.dumps(record) + "\n")
                requests_log.flush()
                results.append(row)
                print(json.dumps(row), flush=True)
                with (directory / "steps.csv").open("w", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=results[0].keys())
                    writer.writeheader()
                    writer.writerows(results)
                json_write(directory / "steps.json", results)
                (directory / f"metrics-step-{number}.txt").write_text((await client.get("/metrics")).text)
                if warnings or (scheduled and len(ok) < scheduled / 2):
                    print("STOP: generator warning or fewer than half arrivals succeeded", flush=True)
                    break
                await asyncio.sleep(2)
        finally:
            requests_log.close()
            for process, handle in processes:
                process.terminate()
                process.wait(timeout=5)
                handle.close()
            (directory / "metrics-end.txt").write_text((await client.get("/metrics")).text)
    # Wait for the last relevant scrape, then query exactly the saved stage windows.
    await asyncio.sleep(2)
    server_results = []
    async with httpx.AsyncClient(base_url=args.prom, timeout=20) as prom:
        for row in results:
            window = args.step - 6
            selector = SELECTOR
            requests = f'sum(increase(papermate_http_requests_total{{{selector}}}[{window}s]))'
            hold_sum = f'sum(increase(papermate_db_pool_hold_seconds_sum[{window}s]))'
            hold_count = f'sum(increase(papermate_db_pool_hold_seconds_count[{window}s]))'
            expressions = {
                "server_rps": f'{requests}/{window}',
                "server_error_rate": f'(sum(increase(papermate_http_requests_total{{{selector},code=~"5.."}}[{window}s])) or vector(0)) / {requests}',
                "server_mean_ms": f'1000*sum(increase(papermate_http_request_duration_seconds_sum{{{selector}}}[{window}s]))/{requests}',
                "server_p99_ms": f'1000*histogram_quantile(0.99,sum by(le)(rate(papermate_http_request_duration_seconds_bucket{{{selector}}}[{window}s])))',
                "cpu_ms_per_req": f'1000*sum(increase(process_cpu_seconds_total{{job="papermate-o4"}}[{window}s]))/{requests}',
                "pool_in_use_avg": f'avg_over_time(papermate_db_pool_checked_out[{window}s])',
                "pool_acquiring_avg": f'avg_over_time(papermate_db_pool_acquiring[{window}s])',
                "hold_ms_per_req": f'1000*{hold_sum}/{requests}',
                "hold_mean_ms": f'1000*{hold_sum}/{hold_count}',
                "checkouts_per_req": f'{hold_count}/{requests}',
                "acquire_p99_ms": f'1000*histogram_quantile(0.99,sum by(le)(rate(papermate_db_pool_acquire_seconds_bucket{{outcome="success"}}[{window}s])))',
                "pool_timeouts": f'increase(papermate_db_pool_timeouts_total[{window}s])',
                "api_cpu_cores": f'rate(process_cpu_seconds_total{{job="papermate-o4"}}[{window}s])',
            }
            values = {"step": row["step"], "target_rps": row["target_rps"]}
            raw = {}
            for name, expression in expressions.items():
                response = await prom.get("/api/v1/query", params={"query": expression, "time": row["end_unix"] - 1})
                response.raise_for_status()
                result = response.json()
                if result.get("status") != "success":
                    raise RuntimeError(f"Prometheus query failed: {name}")
                raw[name] = {"query": expression, "response": result}
                series = result["data"]["result"]
                if len(series) > 1:
                    raise RuntimeError(f"Expected one series for {name}")
                value = float(series[0]["value"][1]) if series else None
                values[name] = value if value is not None and math.isfinite(value) else None
            json_write(directory / f"prometheus-step-{row['step']}.json", raw)
            server_results.append(values)
        json_write(directory / "server.json", server_results)
        with (directory / "server.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=server_results[0].keys())
            writer.writeheader()
            writer.writerows(server_results)
    manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in directory.iterdir() if p.is_file()}
    json_write(directory / "SHA256.json", manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--rates", required=True)
    parser.add_argument("--step", type=int, default=30)
    parser.add_argument("--kind", choices=["baseline", "formal", "smoke"], required=True)
    parser.add_argument("--max-inflight", type=int, default=512)
    parser.add_argument("--timeout", type=float, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--api", default="http://127.0.0.1:18080")
    parser.add_argument("--prom", default="http://127.0.0.1:19090")
    args = parser.parse_args()
    args.rates = [float(r) for r in args.rates.split(",")]
    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.name) or args.name in {".", ".."}:
        parser.error("Invalid run name")
    if args.step < 15 or not args.rates or any(not math.isfinite(r) or r < 0 for r in args.rates):
        parser.error("Stage must be >=15 seconds and rates must be finite and non-negative")
    if args.max_inflight < 1 or args.timeout <= 0:
        parser.error("Invalid inflight or timeout limit")
    directory = Path("../runs/o4") / args.name
    directory.mkdir(parents=True, exist_ok=False)
    asyncio.run(run(args, directory))


if __name__ == "__main__":
    main()
