"""Wrap the course Go loadgen; preserve original CSV and sample server metrics."""
import argparse
import asyncio
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

import httpx

from o4_run import collectors, json_write, samples


async def query_server(directory, rows):
    results = []
    async with httpx.AsyncClient(base_url='http://127.0.0.1:19090', timeout=20) as prom:
        for row in rows:
            window = int(float(row['end_unix']) - float(row['start_unix'])) - 6
            selector = 'job="papermate-o4",method="GET",route="/api/papers/discover"'
            requests = f'sum(increase(papermate_http_requests_total{{{selector}}}[{window}s]))'
            hold_sum = f'sum(increase(papermate_db_pool_hold_seconds_sum[{window}s]))'
            hold_count = f'sum(increase(papermate_db_pool_hold_seconds_count[{window}s]))'
            expressions = {
                'server_rps': f'{requests}/{window}',
                'server_error_rate': f'(sum(increase(papermate_http_requests_total{{{selector},code=~"5.."}}[{window}s])) or vector(0))/{requests}',
                'server_mean_ms': f'1000*sum(increase(papermate_http_request_duration_seconds_sum{{{selector}}}[{window}s]))/{requests}',
                'server_p99_ms': f'1000*histogram_quantile(0.99,sum by(le)(rate(papermate_http_request_duration_seconds_bucket{{{selector}}}[{window}s])))',
                'cpu_ms_per_req': f'1000*sum(increase(process_cpu_seconds_total{{job="papermate-o4"}}[{window}s]))/{requests}',
                'pool_in_use_avg': f'avg_over_time(papermate_db_pool_checked_out[{window}s])',
                'pool_acquiring_avg': f'avg_over_time(papermate_db_pool_acquiring[{window}s])',
                'hold_ms_per_req': f'1000*{hold_sum}/{requests}',
                'hold_mean_ms': f'1000*{hold_sum}/{hold_count}',
                'checkouts_per_req': f'{hold_count}/{requests}',
                'acquire_p99_ms': f'1000*histogram_quantile(0.99,sum by(le)(rate(papermate_db_pool_acquire_seconds_bucket{{outcome="success"}}[{window}s])))',
                'pool_timeouts': f'increase(papermate_db_pool_timeouts_total[{window}s])',
                'api_cpu_cores': f'rate(process_cpu_seconds_total{{job="papermate-o4"}}[{window}s])',
            }
            values = {'step': row['step'], 'target_rps': float(row['target_rps'])}
            raw = {}
            for name, expression in expressions.items():
                response = await prom.get('/api/v1/query', params={
                    'query': expression, 'time': float(row['end_unix']) - 1})
                response.raise_for_status()
                result = response.json()
                assert result.get('status') == 'success', name
                raw[name] = {'query': expression, 'response': result}
                series = result['data']['result']
                assert len(series) <= 1, name
                value = float(series[0]['value'][1]) if series else None
                values[name] = value if value is not None and -float('inf') < value < float('inf') else None
            json_write(directory / f"prometheus-step-{row['step']}.json", raw)
            results.append(values)
    json_write(directory / 'server.json', results)
    with (directory / 'server.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True)
    parser.add_argument('--rates', required=True)
    parser.add_argument('--step', type=int, default=30)
    parser.add_argument('--kind', choices=['baseline', 'formal'], required=True)
    args = parser.parse_args()
    if not args.name.replace('-', '').replace('_', '').isalnum() or args.step < 15:
        parser.error('Invalid run name or stage duration')
    directory = Path('../runs/o4') / args.name
    directory.mkdir(parents=True, exist_ok=False)
    pid = int(subprocess.check_output(['systemctl', 'show', '-p', 'MainPID', '--value',
                                       'papermate-o4-api'], text=True))
    with httpx.Client(base_url='http://127.0.0.1:18080', timeout=10) as client:
        response = client.post('/api/auth/login', json={
            'email': 'o4_bench@example.com', 'password': os.environ['O4_TEST_PASSWORD']})
        response.raise_for_status()
        token = response.json()['data']['access_token']
        headers = {'Authorization': 'Bearer ' + token}
        for _ in range(10):
            response = client.get('/api/papers/discover?page=1&page_size=20', headers=headers)
            response.raise_for_status()
        initial = client.get('/metrics').text
        metrics = samples(initial)
        (directory / 'metrics-start.txt').write_text(initial)
        binary = Path('../bin/o4-loadgen')
        (directory / 'loadgen-source.go').write_bytes(Path('../tools/o4-loadgen/main.go').read_bytes())
        command = [str(binary), '-url', 'http://127.0.0.1:18080/api/papers/discover?page=1&page_size=20',
                   '-rates', args.rates, '-step', f'{args.step}s', '-timeout', '2s', '-slo', '200ms',
                   '-max-inflight', '2000', '-seed', '42', '-stop-below', '0.5',
                   '-out', str(directory / 'steps.csv')]
        meta = {'kind': args.kind, 'name': args.name,
                'started_utc': datetime.now(timezone.utc).isoformat(), 'tool': 'course Go loadgen + env auth',
                'source_manifest': json.loads(Path('../SOURCE_MANIFEST.json').read_text()),
                'loadgen_source_sha256': hashlib.sha256(Path('../tools/o4-loadgen/main.go').read_bytes()).hexdigest(),
                'loadgen_binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                'command': command, 'auth': 'O4_BEARER_TOKEN environment, never saved',
                'generator_affinity': sorted(os.sched_getaffinity(0)),
                'api_affinity': sorted(os.sched_getaffinity(pid)), 'api_pid': pid,
                'pool_capacity': metrics['papermate_db_pool_capacity', ()],
                'pool_size': int(os.environ['DB_POOL_SIZE']),
                'pool_max_overflow': int(os.environ['DB_MAX_OVERFLOW']),
                'pool_timeout_s': float(os.environ['DB_POOL_TIMEOUT']),
                'paper_count': response.json()['data']['total'], 'page_size': 20,
                'server_window': 'first 5s and last 1s excluded; client is full-stage',
                'generator_source': 'copy of /root/lab2/cmd/loadgen/main.go; auth only modification',
                'slo': 'client success and <=200ms; experimental choice, not course requirement'}
        json_write(directory / 'meta.json', meta)
        processes = collectors(directory, pid)
        env = os.environ.copy()
        env['O4_BEARER_TOKEN'] = token
        try:
            with (directory / 'loadgen.log').open('w') as log:
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                           text=True, env=env)
                for line in process.stdout:
                    print(line, end='', flush=True)
                    log.write(line)
                    log.flush()
                if process.wait() != 0:
                    raise RuntimeError('loadgen failed; see original output')
        finally:
            for process, handle in processes:
                process.terminate()
                process.wait(timeout=5)
                handle.close()
            (directory / 'metrics-end.txt').write_text(client.get('/metrics').text)
    rows = [row for row in csv.DictReader((directory / 'steps.csv').open()) if row['step'] != 'all']
    json_write(directory / 'steps.json', rows)
    time.sleep(2)
    asyncio.run(query_server(directory, rows))
    json_write(directory / 'SHA256.json', {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                          for p in directory.iterdir() if p.is_file()})


if __name__ == '__main__':
    main()
