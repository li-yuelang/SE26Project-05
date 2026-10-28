"""Write an immutable pre-load prediction from a saved steady baseline."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = json.loads((args.baseline / 'server.json').read_text())
    row = data[-1]
    meta = json.loads((args.baseline / 'meta.json').read_text())
    hold = row['hold_ms_per_req']
    cpu = row['cpu_ms_per_req']
    assert hold and cpu, 'Missing steady baseline measurements'
    pool_limit = meta['pool_capacity'] * 1000 / hold
    cpu_limit = 1000 / cpu
    reference = min(pool_limit, cpu_limit)
    prediction = {
        'written_utc': datetime.now(timezone.utc).isoformat(),
        'baseline': str(args.baseline), 'baseline_server_sha256': hashlib.sha256(
            (args.baseline / 'server.json').read_bytes()).hexdigest(),
        'source_row': row, 'pool_capacity': meta['pool_capacity'],
        'hold_ms_per_request': hold, 'cpu_ms_per_request': cpu,
        'pool_limit_rps': pool_limit, 'api_cpu_limit_rps': cpu_limit,
        'predicted_first_resource': 'connection pool' if pool_limit < cpu_limit else 'API CPU',
        'planned_rates': sorted(set(round(reference * factor) for factor in [.4, .7, 1, 1.3, 1.7, 2.1])),
        'expected_signs': ['throughput flattens', 'p99 rises', 'pool checked-out reaches capacity if pool bound',
                           'acquisition duration and inflight grow if pool bound',
                           'API CPU approaches one core if CPU bound'],
        'experimental_slo': 'success fraction >=99% and client p99 <=200ms',
        'conditions': ['one uvicorn worker', '1000 synthetic papers, fixed discovery page',
                       'pool overflow disabled', 'API on SMT siblings 2,3; generator/DB on 0,1',
                       'low-load per-request CPU and hold can change under load',
                       'no artificial delays; acquisition includes connection creation/pre-ping'],
    }
    with args.output.open('x') as handle:
        json.dump(prediction, handle, indent=2)
        handle.write('\n')
    print(json.dumps(prediction, indent=2))


if __name__ == '__main__':
    main()
