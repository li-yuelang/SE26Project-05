"""Requery saved phase windows without changing original evidence."""
import argparse
import asyncio
import csv
import hashlib
import json
import math
from pathlib import Path
import re

import httpx


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    directory = args.run / "requery-v2"
    directory.mkdir(exist_ok=False)
    rows = []
    async with httpx.AsyncClient(base_url="http://127.0.0.1:19090", timeout=20) as client:
        for step in json.loads((args.run / "steps.json").read_text()):
            original = json.loads((args.run / f"prometheus-step-{step['step']}.json").read_text())
            row = {"step": step["step"], "target_rps": step["target_rps"]}
            raw = {}
            for name, item in original.items():
                # Aggregate numerator labels before division by the aggregated request count.
                query = re.sub(
                    r'increase\((process_cpu_seconds_total\{[^}]*\}|papermate_db_pool_hold_seconds_(?:sum|count))\[\d+s\]\)',
                    lambda m: 'sum(' + m.group(0) + ')', item['query'])
                result = (await client.get('/api/v1/query', params={
                    'query': query, 'time': step['end_unix'] - 1})).json()
                assert result['status'] == 'success', name
                series = result['data']['result']
                assert len(series) <= 1, name
                value = float(series[0]['value'][1]) if series else None
                row[name] = value if value is not None and math.isfinite(value) else None
                raw[name] = {'query': query, 'response': result}
            (directory / f"prometheus-step-{step['step']}.json").write_text(json.dumps(raw, indent=2))
            rows.append(row)
    (directory / 'server.json').write_text(json.dumps(rows, indent=2))
    with (directory / 'server.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    (directory / 'SHA256.json').write_text(json.dumps({
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir() if p.is_file()
    }, indent=2))
    print(json.dumps(rows, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
