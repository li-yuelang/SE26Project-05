"""Verify a release checksum, embedded metadata, and local Git ancestry."""
import argparse
import hashlib
import io
import json
import re
import subprocess
import tarfile
import zipfile
from pathlib import Path
from urllib.parse import urlparse


def verify(package: Path, repo: Path, ref: str) -> None:
    checksum = package.with_name(package.name + ".sha256")
    parts = checksum.read_text(encoding="utf-8").strip().split()
    if len(parts) != 2 or parts[1].lstrip("*") != package.name:
        raise ValueError("Checksum filename does not match package")
    actual = hashlib.sha256(package.read_bytes()).hexdigest()
    if parts[0].lower() != actual:
        raise ValueError("SHA-256 mismatch")
    print("SHA256:", actual, "OK")

    with tarfile.open(package, "r:gz") as archive:
        members = archive.getmembers()
        metadata = [m for m in members if m.name.count("/") == 1
                    and m.name.endswith("/BUILD_INFO.json")]
        if len(metadata) != 1:
            raise ValueError("Expected one root BUILD_INFO.json")
        base = metadata[0].name.rsplit("/", 1)[0]
        info = json.load(archive.extractfile(metadata[0]))
        frontend = json.load(archive.extractfile(base + "/frontend/build_info.json"))
        wheels = [m for m in members if m.name.startswith(base + "/backend/")
                  and m.name.endswith(".whl")]
        if len(wheels) != 1:
            raise ValueError("Expected one backend wheel")
        with zipfile.ZipFile(io.BytesIO(archive.extractfile(wheels[0]).read())) as wheel:
            backend = json.loads(wheel.read("app/build_info.json"))
        if info != frontend or info != backend:
            raise ValueError("Frontend/backend/package metadata differ")

    required = {"version", "build_no", "commit", "run_id", "run_url"}
    if not required <= info.keys() or not all(isinstance(info[k], str) for k in required):
        raise ValueError("Invalid BUILD_INFO schema")
    for key in sorted(required):
        print(f"{key}: {info[key]}")
    if not re.fullmatch(r"[0-9a-f]{40}", info["commit"]):
        raise ValueError("Expected a full Git commit SHA")

    if info["run_id"] == "local":
        print("LOCAL BUILD: no hosted run; dirty source may differ from this commit")
    else:
        run = urlparse(info["run_url"])
        match = re.fullmatch(r"/([^/]+)/([^/]+)/actions/runs/([0-9]+)", run.path)
        if (run.scheme != "https" or run.netloc != "github.com" or not match
                or match[3] != info["run_id"] or not info["build_no"].isdigit()):
            raise ValueError("Invalid Actions run URL or build identifiers")
        remote = subprocess.check_output(
            ["git", "-C", str(repo), "remote", "get-url", "origin"], text=True
        ).strip().removesuffix(".git")
        if remote not in (f"https://github.com/{match[1]}/{match[2]}",
                          f"git@github.com:{match[1]}/{match[2]}"):
            raise ValueError("Actions repository differs from local origin")
        print("Actions:", info["run_url"])

    subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor",
                    info["commit"], ref], check=True)
    title = subprocess.check_output(
        ["git", "-C", str(repo), "show", "-s", "--format=%s", info["commit"]],
        text=True, encoding="utf-8",
    ).strip()
    print(f"Git: commit is an ancestor of {ref}")
    print("Commit title:", title)
    pr = re.search(r"\(#([0-9]+)\)$", title)
    if pr and info["run_id"] != "local":
        print("PR:", f"https://github.com/{match[1]}/{match[2]}/pull/{pr[1]}")
    else:
        print("PR: inspect GitHub commit history / associated pull requests")
    print("Integrity checked against the supplied checksum; retain its original value independently.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--ref", default="origin/main")
    args = parser.parse_args()
    try:
        verify(args.package, args.repo, args.ref)
    except (ValueError, OSError, KeyError, tarfile.TarError, zipfile.BadZipFile,
            subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Trace failed: {exc}\n")


if __name__ == "__main__":
    main()
