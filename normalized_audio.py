from __future__ import annotations

import hashlib
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

FIELD_BASE_NAME = "BAC Áudio Normalizado"
GENERATED_PREFIX = "bac_norm_"
TEMPLATE_START = "<!-- BAC:NORMALIZED:AUDIO:START -->"
TEMPLATE_END = "<!-- BAC:NORMALIZED:AUDIO:END -->"
MAX_OUTPUT_BYTES = 128 * 1024 * 1024
_SOUND_RE = re.compile(r"\[sound:([^\]\r\n]+)\]", flags=re.IGNORECASE)
_MANAGED_VALUE_RE = re.compile(
    r"^(?:\s*\[sound:bac_norm_[^\]\r\n]+\]\s*)*$",
    flags=re.IGNORECASE,
)


def extract_sound_filenames(fields: Iterable[str]) -> set[str]:
    result: set[str] = set()
    for value in fields:
        for match in _SOUND_RE.finditer(str(value or "")):
            filename = match.group(1).strip()
            if filename:
                result.add(filename)
    return result


def is_managed_field_value(value: str | None) -> bool:
    return bool(_MANAGED_VALUE_RE.fullmatch(str(value or "")))


def field_value_for_files(filenames: Iterable[str]) -> str:
    safe: list[str] = []
    for filename in filenames:
        value = str(filename or "").strip()
        if not value or "\x00" in value or "]" in value or "\r" in value or "\n" in value:
            continue
        safe.append(f"[sound:{value}]")
    return " ".join(dict.fromkeys(safe))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def normalized_media_stem(
    source_filename: str,
    source_digest: str,
    target: float,
    dual_mono: bool,
) -> str:
    basename = Path(str(source_filename).replace("\\", "/")).name
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(basename).stem).strip("._-")
    stem = (stem or "audio")[:48]
    identity = f"{source_digest}\0{basename}\0{float(target):.3f}\0{int(bool(dual_mono))}"
    short = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return f"{GENERATED_PREFIX}{short}_{stem}"


def _validated_field_name(field_name: str) -> str:
    value = str(field_name or "").strip()
    if not value or any(token in value for token in ("{{", "}}", "\r", "\n")):
        raise ValueError("invalid normalized audio field name")
    return value


def template_block(field_name: str) -> str:
    field = _validated_field_name(field_name)
    return (
        f"{TEMPLATE_START}\n"
        f"{{{{#{field}}}}}<div class=\"bac-normalized-audio\">{{{{{field}}}}}</div>{{{{/{field}}}}}\n"
        f"{TEMPLATE_END}"
    )


def upsert_template_block(html: str, field_name: str) -> str:
    source = str(html or "")
    block = template_block(field_name)
    start = source.find(TEMPLATE_START)
    end = source.find(TEMPLATE_END, start + len(TEMPLATE_START)) if start >= 0 else -1
    if start >= 0 and end >= 0:
        end += len(TEMPLATE_END)
        return source[:start].rstrip() + "\n\n" + block + source[end:]
    return source.rstrip() + "\n\n" + block


def remove_template_block(html: str) -> str:
    source = str(html or "")
    start = source.find(TEMPLATE_START)
    end = source.find(TEMPLATE_END, start + len(TEMPLATE_START)) if start >= 0 else -1
    if start < 0 or end < 0:
        return source
    end += len(TEMPLATE_END)
    return (source[:start].rstrip() + source[end:]).strip()


def _creation_flags() -> int:
    if sys.platform.startswith("win"):
        return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return 0


def _loudnorm_filter(
    measurement: dict[str, Any],
    target: float,
    dual_mono: bool,
    true_peak_limit: float,
    lra_target: float,
) -> str:
    required = {
        "input_i": float(measurement["input_i"]),
        "input_tp": float(measurement["input_tp"]),
        "input_lra": float(measurement.get("input_lra", 0.0)),
        "input_thresh": float(measurement.get("input_thresh", -70.0)),
        "target_offset": float(measurement.get("target_offset", 0.0)),
    }
    if not all(math.isfinite(value) for value in required.values()):
        raise ValueError("invalid loudness measurement")
    return (
        f"loudnorm=I={float(target):.1f}:TP={float(true_peak_limit):.1f}:LRA={float(lra_target):.0f}:"
        f"measured_I={required['input_i']:.3f}:measured_TP={required['input_tp']:.3f}:"
        f"measured_LRA={required['input_lra']:.3f}:measured_thresh={required['input_thresh']:.3f}:"
        f"offset={required['target_offset']:.3f}:linear=true:dual_mono={'true' if dual_mono else 'false'}"
    )


def _run_render(command: list[str], destination: Path) -> bool:
    completed = subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
        shell=False,
        creationflags=_creation_flags(),
    )
    return (
        completed.returncode == 0
        and destination.is_file()
        and 0 < destination.stat().st_size <= MAX_OUTPUT_BYTES
    )


def render_normalized_audio(
    ffmpeg: str,
    source: Path,
    destination_m4a: Path,
    measurement: dict[str, Any],
    target: float,
    dual_mono: bool,
    true_peak_limit: float,
    lra_target: float,
) -> Path:
    if not source.is_file():
        raise FileNotFoundError(source)
    destination_m4a.parent.mkdir(parents=True, exist_ok=True)
    filter_spec = _loudnorm_filter(
        measurement,
        target,
        dual_mono,
        true_peak_limit,
        lra_target,
    )

    base = [
        ffmpeg,
        "-hide_banner",
        "-nostdin",
        "-nostats",
        "-y",
        "-i",
        str(source),
        "-map",
        "0:a:0",
        "-vn",
        "-map_metadata",
        "-1",
        "-af",
        filter_spec,
    ]
    aac_command = base + ["-c:a", "aac", "-b:a", "128k", str(destination_m4a)]
    if _run_render(aac_command, destination_m4a):
        return destination_m4a

    try:
        destination_m4a.unlink(missing_ok=True)
    except Exception:
        pass

    # PCM/WAV is the compatibility fallback if the local FFmpeg build lacks AAC.
    destination_wav = destination_m4a.with_suffix(".wav")
    wav_command = base + ["-c:a", "pcm_s16le", str(destination_wav)]
    if _run_render(wav_command, destination_wav):
        return destination_wav

    try:
        destination_wav.unlink(missing_ok=True)
    except Exception:
        pass
    raise RuntimeError("FFmpeg could not create a normalized audio copy")
