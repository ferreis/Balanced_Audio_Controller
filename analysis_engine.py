from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Callable

IMAGEIO_FFMPEG_VERSION = "0.6.0"
DOWNLOAD_TIMEOUT_SECONDS = 45
MAX_DOWNLOAD_BYTES = 128 * 1024 * 1024

# Pinned imageio-ffmpeg 0.6.0 platform wheels from PyPI.
# URLs and SHA-256 values are intentionally fixed so an unexpected upstream
# replacement cannot be executed silently.
FFMPEG_WHEELS: dict[str, dict[str, Any]] = {
    "windows-x86_64": {
        "url": "https://files.pythonhosted.org/packages/2c/c6/fa760e12a2483469e2bf5058c5faff664acf66cadb4df2ad6205b016a73d/imageio_ffmpeg-0.6.0-py3-none-win_amd64.whl",
        "sha256": "02fa47c83703c37df6bfe4896aab339013f62bf02c5ebf2dce6da56af04ffc0a",
        "size": 31246824,
    },
    "linux-x86_64": {
        "url": "https://files.pythonhosted.org/packages/a0/2d/43c8522a2038e9d0e7dbdf3a61195ecc31ca576fb1527a528c877e87d973/imageio_ffmpeg-0.6.0-py3-none-manylinux2014_x86_64.whl",
        "sha256": "c7e46fcec401dd990405049d2e2f475e2b397779df2519b544b8aab515195282",
        "size": 29498237,
    },
    "linux-aarch64": {
        "url": "https://files.pythonhosted.org/packages/33/e7/1925bfbc563c39c1d2e82501d8372734a5c725e53ac3b31b4c2d081e895b/imageio_ffmpeg-0.6.0-py3-none-manylinux2014_aarch64.whl",
        "sha256": "1d47bebd83d2c5fc770720d211855f208af8a596c82d17730aa51e815cdee6dc",
        "size": 25632706,
    },
    "macos-arm64": {
        "url": "https://files.pythonhosted.org/packages/40/5c/f3d8a657d362cc93b81aab8feda487317da5b5d31c0e1fdfd5e986e55d17/imageio_ffmpeg-0.6.0-py3-none-macosx_11_0_arm64.whl",
        "sha256": "b1ae3173414b5fc5f538a726c4e48ea97edc0d2cdc11f103afee655c463fa742",
        "size": 21113891,
    },
    "macos-x86_64": {
        "url": "https://files.pythonhosted.org/packages/da/58/87ef68ac83f4c7690961bce288fd8e382bc5f1513860fc7f90a9c1c1c6bf/imageio_ffmpeg-0.6.0-py3-none-macosx_10_9_intel.macosx_10_9_x86_64.whl",
        "sha256": "9d2baaf867088508d4a3458e61eeb30e945c4ad8016025545f66c4b5aaef0a61",
        "size": 24932969,
    },
}


def platform_key() -> str | None:
    machine = platform.machine().lower().replace("amd64", "x86_64")
    if machine in {"arm64", "aarch64"}:
        machine = "aarch64" if sys.platform.startswith("linux") else "arm64"

    if sys.platform.startswith("win") and machine == "x86_64":
        return "windows-x86_64"
    if sys.platform.startswith("linux") and machine in {"x86_64", "aarch64"}:
        return f"linux-{machine}"
    if sys.platform == "darwin" and machine in {"x86_64", "arm64"}:
        return f"macos-{machine}"
    return None


def _managed_root(addon_root: Path) -> Path:
    return addon_root / "user_files" / "tools" / "ffmpeg" / IMAGEIO_FFMPEG_VERSION


def managed_ffmpeg_path(addon_root: Path) -> Path:
    name = "ffmpeg.exe" if sys.platform.startswith("win") else "ffmpeg"
    return _managed_root(addon_root) / (platform_key() or "unsupported") / name


def _creation_flags() -> int:
    if sys.platform.startswith("win"):
        return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return 0


def is_executable_usable(path: str | Path) -> bool:
    try:
        candidate = str(path)
        result = subprocess.run(
            [candidate, "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
            shell=False,
            creationflags=_creation_flags(),
        )
        return result.returncode == 0
    except (OSError, ValueError, subprocess.SubprocessError):
        return False


def find_ffmpeg(addon_root: Path) -> tuple[str | None, str | None]:
    managed = managed_ffmpeg_path(addon_root)
    if managed.is_file() and is_executable_usable(managed):
        return str(managed), "managed"

    system = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if system and is_executable_usable(system):
        return system, "system"

    # Anki distributions sometimes place helper executables near Python/Anki.
    runtime = Path(sys.executable).resolve().parent
    candidates = [
        runtime / "ffmpeg",
        runtime / "ffmpeg.exe",
        runtime / "bin" / "ffmpeg",
        runtime / "bin" / "ffmpeg.exe",
    ]
    for candidate in candidates:
        if candidate.is_file() and is_executable_usable(candidate):
            return str(candidate), "runtime"
    return None, None


def ffmpeg_status(addon_root: Path) -> dict[str, Any]:
    executable, source = find_ffmpeg(addon_root)
    key = platform_key()
    spec = FFMPEG_WHEELS.get(key or "")
    return {
        "available": bool(executable),
        "source": source,
        "managed": source == "managed",
        "installer_available": bool(spec),
        "installer_name": f"imageio-ffmpeg {IMAGEIO_FFMPEG_VERSION}" if spec else None,
        "platform": key,
    }


def resolve_backend(configured: Any, ffmpeg_available: bool) -> str:
    value = str(configured or "auto").strip().lower()
    if value == "ffmpeg":
        return "ffmpeg"
    if value == "webaudio":
        return "webaudio"
    return "ffmpeg" if ffmpeg_available else "webaudio"


def _download_wheel(spec: dict[str, Any], destination: Path, progress: Callable[[int, int], None] | None) -> None:
    url = str(spec["url"])
    if not url.startswith("https://files.pythonhosted.org/"):
        raise RuntimeError("untrusted download host")

    expected_size = int(spec["size"])
    if expected_size <= 0 or expected_size > MAX_DOWNLOAD_BYTES:
        raise RuntimeError("invalid pinned download size")

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Balanced-Audio-Controller/0.10 imageio-ffmpeg-installer",
            "Accept": "application/octet-stream",
        },
        method="GET",
    )
    digest = hashlib.sha256()
    received = 0

    with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:  # noqa: S310 - URL is pinned above.
        final_url = response.geturl()
        if not final_url.startswith("https://files.pythonhosted.org/"):
            raise RuntimeError("download redirected to an untrusted host")

        declared = response.headers.get("Content-Length")
        if declared:
            declared_size = int(declared)
            if declared_size != expected_size:
                raise RuntimeError("download size does not match pinned metadata")

        with destination.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                received += len(chunk)
                if received > MAX_DOWNLOAD_BYTES or received > expected_size + 1024:
                    raise RuntimeError("download exceeded expected size")
                digest.update(chunk)
                handle.write(chunk)
                if progress:
                    progress(received, expected_size)
            handle.flush()
            os.fsync(handle.fileno())

    if received != expected_size:
        raise RuntimeError("download was incomplete")
    if digest.hexdigest().lower() != str(spec["sha256"]).lower():
        raise RuntimeError("download SHA-256 mismatch")


def _extract_binary(wheel_path: Path, destination: Path) -> None:
    with zipfile.ZipFile(wheel_path, "r") as archive:
        candidates: list[zipfile.ZipInfo] = []
        for member in archive.infolist():
            normalized = member.filename.replace("\\", "/")
            if member.is_dir() or not normalized.startswith("imageio_ffmpeg/binaries/"):
                continue
            basename = normalized.rsplit("/", 1)[-1].lower()
            if basename.startswith("ffmpeg-") or basename == "ffmpeg.exe" or basename == "ffmpeg":
                candidates.append(member)

        if len(candidates) != 1:
            raise RuntimeError("wheel did not contain exactly one expected FFmpeg binary")

        member = candidates[0]
        if member.file_size <= 0 or member.file_size > MAX_DOWNLOAD_BYTES:
            raise RuntimeError("invalid FFmpeg binary size")

        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        try:
            with archive.open(member, "r") as source, temporary.open("wb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
                output.flush()
                os.fsync(output.fileno())
            if not sys.platform.startswith("win"):
                temporary.chmod(0o755)
            if not is_executable_usable(temporary):
                raise RuntimeError("downloaded FFmpeg executable failed validation")
            temporary.replace(destination)
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except Exception:
                pass


def install_managed_ffmpeg(addon_root: Path, progress: Callable[[int, int], None] | None = None) -> Path:
    key = platform_key()
    spec = FFMPEG_WHEELS.get(key or "")
    if not spec:
        raise RuntimeError("automatic FFmpeg installation is unsupported on this platform")

    existing = managed_ffmpeg_path(addon_root)
    if existing.is_file() and is_executable_usable(existing):
        return existing

    root = existing.parent
    root.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="ffmpeg-", suffix=".whl.part", dir=root)
    os.close(fd)
    wheel_path = Path(temp_name)

    try:
        _download_wheel(spec, wheel_path, progress)
        _extract_binary(wheel_path, existing)
        metadata = {
            "provider": "imageio-ffmpeg",
            "provider_version": IMAGEIO_FFMPEG_VERSION,
            "platform": key,
            "url": spec["url"],
            "sha256": spec["sha256"],
        }
        (root / "source.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return existing
    finally:
        try:
            wheel_path.unlink(missing_ok=True)
        except Exception:
            pass


def parse_loudnorm_json(stderr: str) -> dict[str, float] | None:
    # Locate the last loudnorm JSON block without trusting arbitrary process
    # output as a command or expression. loudnorm emits a flat JSON object.
    marker = stderr.rfind('"input_i"')
    if marker < 0:
        return None
    start = stderr.rfind("{", 0, marker)
    end = stderr.find("}", marker)
    if start < 0 or end < 0:
        return None
    try:
        raw = json.loads(stderr[start : end + 1])
        values = {
            "input_i": float(raw["input_i"]),
            "input_tp": float(raw["input_tp"]),
            "input_lra": float(raw.get("input_lra", 0.0)),
            "input_thresh": float(raw.get("input_thresh", 0.0)),
        }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return values if all(math.isfinite(v) for v in values.values()) else None


def measure_with_ffmpeg(
    ffmpeg: str,
    path: Path,
    target: float,
    dual_mono: bool,
    true_peak_limit: float,
    lra_target: float,
) -> dict[str, float] | None:
    filter_spec = (
        f"loudnorm=I={target:.1f}:TP={true_peak_limit:.1f}:LRA={lra_target:.0f}:"
        f"dual_mono={'true' if dual_mono else 'false'}:print_format=json"
    )
    command = [
        ffmpeg,
        "-hide_banner",
        "-nostdin",
        "-nostats",
        "-i",
        str(path),
        "-af",
        filter_spec,
        "-f",
        "null",
        "-",
    ]
    completed = subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
        shell=False,
        creationflags=_creation_flags(),
    )
    return parse_loudnorm_json(completed.stderr)
