from __future__ import annotations

import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"

INCLUDE_FILES = [
    "__init__.py",
    "config.json",
    "config.schema.json",
    "manifest.json",
    "README.md",
    "LICENSE",
]


def version() -> str:
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    return str(manifest.get("human_version", "dev"))


def build() -> Path:
    DIST.mkdir(exist_ok=True)
    output = DIST / f"Balanced_Audio_Controller-v{version()}.ankiaddon"

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in INCLUDE_FILES:
            path = ROOT / relative
            if path.is_file():
                archive.write(path, relative)

        web = ROOT / "web"
        for path in sorted(web.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                archive.write(path, path.relative_to(ROOT).as_posix())

    with zipfile.ZipFile(output, "r") as archive:
        bad_file = archive.testzip()
        if bad_file:
            raise RuntimeError(f"Arquivo corrompido dentro do pacote: {bad_file}")

    print(output)
    return output


if __name__ == "__main__":
    build()
