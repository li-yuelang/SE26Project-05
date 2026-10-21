import hashlib
import json
import re
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    info_path = root / "backend/app/build_info.json"
    info = json.loads(info_path.read_text(encoding="utf-8"))

    version = info["version"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", version):
        raise SystemExit("Invalid package version")

    frontend = root / "frontend/dist"
    if not (frontend / "index.html").is_file():
        raise SystemExit("Build frontend first")

    wheels = list((root / "backend/dist").glob("*.whl"))
    if len(wheels) != 1:
        raise SystemExit("Expected exactly one wheel in backend/dist")

    wheel = wheels[0]
    with zipfile.ZipFile(wheel) as archive:
        wheel_info = json.loads(archive.read("app/build_info.json"))
    if wheel_info != info:
        raise SystemExit("Wheel metadata is stale; rebuild backend")

    output = root / "dist"
    output.mkdir(exist_ok=True)
    name = f"papermate_{version}"
    package = output / f"{name}.tar.gz"

    with tempfile.TemporaryDirectory(prefix="papermate-package-") as temporary:
        stage = Path(temporary) / name
        backend = stage / "backend"
        backend.mkdir(parents=True)

        shutil.copytree(frontend, stage / "frontend")
        shutil.copy2(wheel, backend / wheel.name)
        shutil.copy2(root / "backend/dist/requirements.txt",
             backend / "requirements.txt")
        for filename in ("pyproject.toml", "uv.lock", "alembic.ini"):
            shutil.copy2(root / "backend" / filename, backend / filename)

        shutil.copytree(
            root / "backend/alembic",
            backend / "alembic",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        shutil.copy2(root / "frontend/package-lock.json",
                     stage / "frontend-package-lock.json")
        shutil.copy2(info_path, stage / "BUILD_INFO.json")
        shutil.copy2(root / "scripts/RELEASE_README.md", stage / "README.md")
        shutil.copy2(root / "scripts/trace.py", stage / "trace.py")
        shutil.copy2(info_path, stage / "frontend/build_info.json")

        with tarfile.open(package, "w:gz") as archive:
            for path in sorted(stage.rglob("*")):
                if path.is_file():
                    archive.add(
                        path,
                        arcname=path.relative_to(stage.parent).as_posix(),
                        recursive=False,
                    )

    digest = hashlib.sha256(package.read_bytes()).hexdigest()
    checksum = package.with_name(package.name + ".sha256")
    checksum.write_text(
        f"{digest}  {package.name}\n",
        encoding="utf-8",
    )
    print(f"Package: {package}")
    print(f"SHA256:  {digest}")
    print(f"Checksum: {checksum}")


if __name__ == "__main__":
    main()