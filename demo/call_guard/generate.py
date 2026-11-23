"""Regenerate the synthetic Call Guard demo clips from manifest.json (dev-time only, needs network once).

Voice: Piper `en_US-libritts_r-medium` (LibriTTS-R, CC BY 4.0). Every clip is synthetic TTS read
from the `script` field; no real call audio or real person's voice is used.

    uvx --from piper-tts python demo/call_guard/generate.py --voice-dir /var/tmp/piper-voices
"""
import argparse
import json
import subprocess
import sys
import urllib.request
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
VOICE = "en_US-libritts_r-medium"
BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/libritts_r/medium/"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice-dir", required=True, help="where to cache the Piper voice (not committed)")
    ap.add_argument("--out-dir", default=str(HERE))
    a = ap.parse_args()
    vdir = Path(a.voice_dir)
    vdir.mkdir(parents=True, exist_ok=True)
    for name in (f"{VOICE}.onnx", f"{VOICE}.onnx.json"):
        if not (vdir / name).is_file():
            urllib.request.urlretrieve(BASE + name, vdir / name)
    rows = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
    for row in rows:
        out = Path(a.out_dir) / row["file"]
        tmp = out.with_suffix(".22k.wav")
        subprocess.run([sys.executable, "-m", "piper", "-m", str(vdir / f"{VOICE}.onnx"),
                        "--speaker", str(row["speaker"]), "-f", str(tmp)],
                       input=row["script"].encode(), check=True)
        # Store as 16 kHz mono 16-bit PCM (what the ASR consumes; keeps the repo small).
        sys.path.insert(0, str(HERE.parents[1] / "candidates" / "BEST"))
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
