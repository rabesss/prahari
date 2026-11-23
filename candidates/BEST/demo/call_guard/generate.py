"""Regenerate the synthetic Call Guard demo clips from manifest.json (dev-time only, needs network once).

Voice: Piper `en_US-libritts_r-medium` (LibriTTS-R, CC BY 4.0). Every clip is synthetic TTS read
from the `script` field; no real call audio or real person's voice is used.

    uvx --from piper-tts --with numpy python candidates/BEST/demo/call_guard/generate.py --voice-dir /var/tmp/piper-voices
"""
import argparse
import hashlib
import json
import subprocess
import sys
import urllib.request
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
VOICE = "en_US-libritts_r-medium"
BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/libritts_r/medium/"
SHA256 = {  # observed 2026-11-23; the .onnx digest equals Hugging Face's LFS etag
    f"{VOICE}.onnx": "10bb85e071d616fcf4071f369f1799d0491492ab3c5d552ec19fb548fac13195",
    f"{VOICE}.onnx.json": "b471dc60d2d8335e819c393d196d6fbf792817f40051257b269878505bc9afb3",
}


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice-dir", required=True, help="where to cache the Piper voice (not committed)")
    ap.add_argument("--out-dir", default=str(HERE))
    a = ap.parse_args()
    vdir = Path(a.voice_dir)
    vdir.mkdir(parents=True, exist_ok=True)
    for name, digest in SHA256.items():
        if not (vdir / name).is_file():
            urllib.request.urlretrieve(BASE + name, vdir / name)
        if _sha256(vdir / name) != digest:
            sys.exit(f"SHA-256 mismatch for {vdir / name}; refusing an unverified voice")
    rows = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
    for row in rows:
        out = Path(a.out_dir) / row["file"]
        tmp = out.with_suffix(".22k.wav")
        subprocess.run([sys.executable, "-m", "piper", "-m", str(vdir / f"{VOICE}.onnx"),
                        "--speaker", str(row["speaker"]), "-f", str(tmp)],
                       input=row["script"].encode(), check=True)
        # Store as 16 kHz mono 16-bit PCM (what the ASR consumes; keeps the repo small).
        sys.path.insert(0, str(HERE.parents[1]))
        import numpy as np
        from triage.asr import _read_wav_pcm, resample_to_16k
        x, sr = _read_wav_pcm(tmp)
        y = (np.clip(resample_to_16k(x, sr), -1, 1) * 32767).astype("<i2")
        with wave.open(str(out), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(y.tobytes())
        tmp.unlink()
        print(out, round(len(y) / 16000, 2), "s")


if __name__ == "__main__":
    main()
