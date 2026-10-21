import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--build-no", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-url", default="")
    args = parser.parse_args()

    info = {
        "version": args.version,
        "build_no": args.build_no,
        "commit": args.commit,
        "run_id": args.run_id,
        "run_url": args.run_url,
    }

    root = Path(__file__).resolve().parents[1]
    target = root / "backend" / "app" / "build_info.json"
    target.write_text(
        json.dumps(info, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(target)
    print(json.dumps(info, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()