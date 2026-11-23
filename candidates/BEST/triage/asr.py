"""On-device offline Whisper speech-to-text through ExecuTorch (XNNPACK + KleidiAI INT8).

Uses Arm's Apache-2.0 INT8 Whisper Tiny ExecuTorch export (`Arm/whisper-tiny-int8-xnnpack-executorch`,
117 MB `.pte`, 8da8w XNNPACK). Log-mel spectrograms are computed in pure NumPy (80 Slaney mel bins,
16 kHz, 30 s windows) rather than loading `whisper_preprocessor.pte`, which reduces peak RSS on
aarch64 from ~4.17 GB to ~0.60 GB while keeping identical Whisper features.

Model weights are never committed to the repository and never downloaded during inference. Run
`bin/callguard --setup-model` (or `download_model()`) once with network access, then run offline.
"""
from __future__ import annotations

import hashlib
import json
import os
import resource
import shutil
import subprocess
import time
import urllib.request
import wave
from pathlib import Path

import numpy as np

CAND = Path(__file__).resolve().parents[1]
REPO = CAND.parents[1]

MODEL_REPO = "Arm/whisper-tiny-int8-xnnpack-executorch"
MODEL_FILENAME = "whisper_tiny_vivo_executorch_optimized.pte"
TOKENIZER_FILENAME = "tokenizer.json"
MODEL_ID = "whisper-tiny-int8-xnnpack"

# Observed SHA-256 checksums of Arm/whisper-tiny-int8-xnnpack-executorch (Apache-2.0, 2026-11-23).
PINNED_SHA256 = {
    MODEL_FILENAME: "5d7595871c44fccd1262fbfec08bd31682fbe912eee967c6bad9104d1f4e42d2",
    TOKENIZER_FILENAME: "27fc476bfe7f17299480be2273fc0608e4d5a99aba2ab5dec5374b4482d1a566",
}

SAMPLE_RATE = 16000
CHUNK_SECONDS = 30
CHUNK_SAMPLES = SAMPLE_RATE * CHUNK_SECONDS
N_FFT = 400
HOP_LENGTH = 160
N_MELS = 80
N_FRAMES = 3000
MAX_CHUNKS = 4  # Up to 2 minutes of audio per file.

DECODER_START_TOKEN_ID = 50258   # <|startoftranscript|>
EOS_TOKEN_ID = 50257             # <|endoftext|>
TRANSCRIBE_TOKEN_ID = 50359      # <|transcribe|>
NOTIMESTAMPS_TOKEN_ID = 50363    # <|notimestamps|>
LANG_TOKEN_IDS = {
    "en": 50259,  # <|en|>
    "hi": 50276,  # <|hi|>
}

MAX_GENERATION_TOKENS = 140
MAX_SECONDS_PER_CHUNK = 90.0
REPETITION_GUARD_REPEATS = 3
REPETITION_GUARD_MIN_PATTERN_LEN = 2
REPETITION_GUARD_MAX_PATTERN_LEN = 16

# Non-speech / timestamp suppression tokens from Arm's Whisper Tiny ExecuTorch reference.
SUPPRESS_TOKENS = (
    1, 2, 7, 8, 9, 10, 14, 25, 26, 27, 28, 29, 31, 58, 59, 60, 61, 62, 63,
    90, 91, 92, 93, 357, 366, 438, 532, 685, 705, 796, 930, 1058, 1220, 1267,
    1279, 1303, 1343, 1377, 1391, 1635, 1782, 1875, 2162, 2361, 2488, 3467,
    4008, 4211, 4600, 4808, 5299, 5855, 6329, 7203, 9609, 9959, 10563, 10786,
    11420, 11709, 11907, 13163, 13697, 13700, 14808, 15306, 16410, 16791,
    17992, 19203, 19510, 20724, 22305, 22935, 27007, 30109, 30420, 33409,
    34949, 40283, 40493, 40549, 47282, 49146, 50359, 50360, 50361,
)
BEGIN_SUPPRESS_TOKENS = (220, 50257)


class AsrError(Exception):
    """Base error for offline Call Guard ASR."""


class AudioDecodeError(AsrError):
    """Raised when an audio file cannot be decoded offline."""


class ModelMissingError(AsrError):
    """Raised when the Whisper ExecuTorch `.pte` or tokenizer is not installed locally."""


_MEL_FB: np.ndarray | None = None
_HANN_WIN: np.ndarray | None = None


def mel_filters_slaney(sr: int = SAMPLE_RATE, n_fft: int = N_FFT, n_mels: int = N_MELS) -> np.ndarray:
    """Slaney-scale mel filterbank matching Whisper / librosa, shape (n_mels, n_fft // 2 + 1)."""
    f_sp = 200.0 / 3.0
    min_log_hz = 1000.0
    min_log_mel = min_log_hz / f_sp
    logstep = np.log(6.4) / 27.0

    def hz_to_mel(freq):
        f = np.asarray(freq, dtype=np.float64)
        return np.where(f >= min_log_hz, min_log_mel + np.log(np.maximum(f, 1e-10) / min_log_hz) / logstep, f / f_sp)

    def mel_to_hz(mel):
        m = np.asarray(mel, dtype=np.float64)
        return np.where(m >= min_log_mel, min_log_hz * np.exp(logstep * (m - min_log_mel)), f_sp * m)

    all_freqs = np.linspace(0.0, sr / 2.0, n_fft // 2 + 1)
    m_pts = np.linspace(hz_to_mel(0.0), hz_to_mel(sr / 2.0), n_mels + 2)
    f_pts = mel_to_hz(m_pts)
    f_diff = np.diff(f_pts)
    slopes = f_pts[np.newaxis, :] - all_freqs[:, np.newaxis]
    down = -slopes[:, :-2] / f_diff[:-1]
    up = slopes[:, 2:] / f_diff[1:]
    fb = np.maximum(0.0, np.minimum(down, up))
    enorm = 2.0 / (f_pts[2:n_mels + 2] - f_pts[:n_mels])
    fb *= enorm[np.newaxis, :]
    return fb.T.astype(np.float32)


def log_mel_spectrogram(waveform_16k: np.ndarray) -> np.ndarray:
    """Compute a Whisper log-mel spectrogram of shape (1, 80, 3000) float32 in pure NumPy."""
    global _MEL_FB, _HANN_WIN
    if _MEL_FB is None:
        _MEL_FB = mel_filters_slaney()
    if _HANN_WIN is None:
        _HANN_WIN = np.hanning(N_FFT + 1)[:-1].astype(np.float32)

    w = np.asarray(waveform_16k, dtype=np.float32).reshape(-1)
    if len(w) > CHUNK_SAMPLES:
        w = w[:CHUNK_SAMPLES]
    elif len(w) < CHUNK_SAMPLES:
        w = np.pad(w, (0, CHUNK_SAMPLES - len(w)))

    pad = N_FFT // 2
    padded = np.pad(w, (pad, pad), mode="reflect")
    frames = np.lib.stride_tricks.sliding_window_view(padded, N_FFT)[::HOP_LENGTH][:N_FRAMES]
    spec = np.fft.rfft(frames * _HANN_WIN, axis=1)
    mags = (spec.real ** 2 + spec.imag ** 2).T.astype(np.float32)
    mel = _MEL_FB @ mags
    log_spec = np.log10(np.maximum(mel, 1e-10))
    log_spec = np.maximum(log_spec, log_spec.max() - 8.0)
    log_spec = (log_spec + 4.0) / 4.0
    return np.ascontiguousarray(log_spec[np.newaxis, :, :], dtype=np.float32)


def resample_to_16k(waveform: np.ndarray, sample_rate: int) -> np.ndarray:
    """Linear resample mono float32 audio to 16 kHz."""
    w = np.asarray(waveform, dtype=np.float32).reshape(-1)
    if sample_rate <= 0:
        raise AudioDecodeError(f"invalid sample rate: {sample_rate}")
    if sample_rate == SAMPLE_RATE or len(w) == 0:
        return np.ascontiguousarray(w, dtype=np.float32)
    target_len = max(1, int(round(len(w) * SAMPLE_RATE / sample_rate)))
    out = np.interp(
        np.linspace(0.0, len(w) - 1, target_len),
        np.arange(len(w)),
        w,
    )
    return np.ascontiguousarray(out, dtype=np.float32)


def _read_wav_pcm(path: Path) -> tuple[np.ndarray, int]:
    try:
        with wave.open(str(path), "rb") as wf:
            sr = wf.getframerate()
            ch = wf.getnchannels()
            sw = wf.getsampwidth()
            raw = wf.readframes(wf.getnframes())
    except wave.Error as exc:
        raise AudioDecodeError(f"not a readable PCM WAV file ({path.name}): {exc}") from exc

    if sw == 1:
        x = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif sw == 2:
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sw == 4:
        x = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        raise AudioDecodeError(f"unsupported WAV sample width ({sw * 8}-bit) in {path.name}")

    if ch > 1:
        usable = (len(x) // ch) * ch
        x = x[:usable].reshape(-1, ch).mean(axis=1)
    return x.astype(np.float32), int(sr)


def _decode_with_ffmpeg(path: Path) -> tuple[np.ndarray, int]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise AudioDecodeError(
            f"cannot decode '{path.suffix or path.name}' without ffmpeg on PATH; "
            "install ffmpeg or convert the voice note to 16 kHz PCM WAV first."
        )
    cmd = [
        ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
        "-i", str(path), "-f", "s16le", "-acodec", "pcm_s16le",
        "-ac", "1", "-ar", str(SAMPLE_RATE), "pipe:1",
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    if proc.returncode != 0 or not proc.stdout:
        err = proc.stderr.decode("utf-8", "replace").strip()[:200]
        raise AudioDecodeError(f"ffmpeg failed to decode {path.name}: {err or 'empty output'}")
    x = np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    return x, SAMPLE_RATE


def load_audio_16k(audio_path: str | Path) -> tuple[np.ndarray, float]:
    """Load an audio file (WAV natively; WhatsApp .ogg/.opus/.m4a/.mp3/.flac via local ffmpeg).

    Returns (mono_float32_16k, duration_seconds).
    """
    path = Path(audio_path)
    if not path.is_file():
        raise AudioDecodeError(f"audio file not found: {path}")
    if path.suffix.lower() == ".wav":
        try:
            wav, sr = _read_wav_pcm(path)
        except AudioDecodeError:
            if shutil.which("ffmpeg"):
                wav, sr = _decode_with_ffmpeg(path)
            else:
                raise
    else:
        wav, sr = _decode_with_ffmpeg(path)
    wav16 = resample_to_16k(wav, sr)
    return wav16, round(len(wav16) / SAMPLE_RATE, 3)


def split_chunks(waveform_16k: np.ndarray, max_chunks: int = MAX_CHUNKS) -> list[np.ndarray]:
    """Split audio into sequential 30-second windows, capped at `max_chunks`."""
    w = np.asarray(waveform_16k, dtype=np.float32).reshape(-1)
    if len(w) == 0:
        return [np.zeros(CHUNK_SAMPLES, dtype=np.float32)]
    chunks = []
    for start in range(0, min(len(w), CHUNK_SAMPLES * max_chunks), CHUNK_SAMPLES):
        chunk = w[start:start + CHUNK_SAMPLES]
        if len(chunk) > 0:
            chunks.append(chunk)
    return chunks or [np.zeros(CHUNK_SAMPLES, dtype=np.float32)]


def _gpt2_bytes_to_unicode() -> dict[int, str]:
    bs = list(range(ord("!"), ord("~") + 1)) + list(range(ord("¡"), ord("¬") + 1)) + list(range(ord("®"), ord("ÿ") + 1))
    cs = list(bs)
    n = 0
    for b in range(256):
        if b not in bs:
            bs.append(b)
            cs.append(256 + n)
            n += 1
    return dict(zip(bs, [chr(c) for c in cs]))


class PureWhisperTokenizer:
    """Zero-dependency Whisper token-ID decoder reading HuggingFace `tokenizer.json`.

    Used automatically as a fallback on platforms without the `tokenizers` wheel (e.g. Chaquopy).
    """

    def __init__(self, tokenizer_json: str | Path):
        data = json.loads(Path(tokenizer_json).read_text(encoding="utf-8"))
        vocab = data.get("model", {}).get("vocab") or {}
        self.id_to_token: dict[int, str] = {int(v): k for k, v in vocab.items()}
        self.special_ids: set[int] = set()
        for entry in data.get("added_tokens") or []:
            tid = int(entry["id"])
            self.id_to_token[tid] = entry["content"]
            if entry.get("special"):
                self.special_ids.add(tid)
        self._u2b = {v: k for k, v in _gpt2_bytes_to_unicode().items()}

    def decode(self, token_ids: list[int], skip_special_tokens: bool = True) -> str:
        pieces = []
        for tid in token_ids:
            if skip_special_tokens and (tid in self.special_ids or tid >= EOS_TOKEN_ID):
                continue
            tok = self.id_to_token.get(int(tid))
            if tok is not None:
                pieces.append(tok)
        joined = "".join(pieces)
        raw = bytearray()
        for ch in joined:
            if ch in self._u2b:
                raw.append(self._u2b[ch])
            else:
                raw.extend(ch.encode("utf-8"))
        return raw.decode("utf-8", errors="replace").strip()


def load_tokenizer(tokenizer_path: str | Path):
    """Load `tokenizer.json` with `tokenizers` when installed, else PureWhisperTokenizer."""
    try:
        from tokenizers import Tokenizer
        return Tokenizer.from_file(str(tokenizer_path))
    except ImportError:
        return PureWhisperTokenizer(tokenizer_path)


def find_repeated_suffix_pattern(
    token_ids: list[int],
    *,
    repeats: int = REPETITION_GUARD_REPEATS,
    min_pattern_len: int = REPETITION_GUARD_MIN_PATTERN_LEN,
    max_pattern_len: int = REPETITION_GUARD_MAX_PATTERN_LEN,
) -> int | None:
    """Detect degenerate Whisper decoder loops (pattern repeated >= `repeats` times at end)."""
    total = len(token_ids)
    upper = min(max_pattern_len, total // repeats)
    for pattern_len in range(min_pattern_len, upper + 1):
        pattern = token_ids[-pattern_len:]
        if all(
            token_ids[-pattern_len * (idx + 1):-pattern_len * idx or None] == pattern
            for idx in range(repeats)
        ):
            return pattern_len
    return None


def resolve_whisper_dir(explicit_dir: str | Path | None = None) -> tuple[Path, Path]:
    """Locate `(model_pte, tokenizer_json)` without accessing the network."""
    candidates: list[Path] = []
    if explicit_dir:
        candidates.append(Path(explicit_dir))
    env_dir = os.environ.get("PRAHARI_WHISPER_DIR")
    if env_dir:
        candidates.append(Path(env_dir))
    reg_path = Path(os.environ.get("HC_MODEL_REGISTRY", REPO / "models" / "registry.json"))
    if reg_path.is_file():
        try:
            reg = json.loads(reg_path.read_text(encoding="utf-8"))
            entry = reg.get(MODEL_ID) or reg.get("whisper-tiny-int8")
            if isinstance(entry, dict) and entry.get("pte") and entry.get("tokenizer"):
                p_pte, p_tok = Path(entry["pte"]), Path(entry["tokenizer"])
                if p_pte.is_file() and p_tok.is_file():
                    return p_pte, p_tok
        except (ValueError, OSError):
            pass
    candidates.extend([
        REPO / ".venv" / "models" / "whisper-tiny",
        CAND / ".venv" / "models" / "whisper-tiny",
        Path("/var/tmp/arm-bharat-ai-soc-models/whisper-tiny"),
    ])
    for d in candidates:
        pte = d / MODEL_FILENAME
        tok = d / TOKENIZER_FILENAME
        if pte.is_file() and tok.is_file():
            return pte, tok
    searched = ", ".join(str(c) for c in candidates)
    raise ModelMissingError(
        f"Whisper ExecuTorch model files ({MODEL_FILENAME}, {TOKENIZER_FILENAME}) not found. "
        f"Run `candidates/BEST/bin/callguard --setup-model` (needs network once) or set "
        f"PRAHARI_WHISPER_DIR. Searched: {searched}"
    )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def download_model(dest_dir: str | Path | None = None, verify: bool = True) -> dict:
    """Explicit setup helper: download Arm Whisper Tiny INT8 .pte + tokenizer.json and verify SHA-256."""
    target = Path(dest_dir) if dest_dir else (REPO / ".venv" / "models" / "whisper-tiny")
    target.mkdir(parents=True, exist_ok=True)
    base_url = f"https://huggingface.co/{MODEL_REPO}/resolve/main"
    files = {}
    for name, expected_sha in PINNED_SHA256.items():
        dst = target / name
        if not dst.is_file() or (verify and sha256_file(dst) != expected_sha):
            tmp = target / (name + ".part")
            urllib.request.urlretrieve(f"{base_url}/{name}", tmp)
            digest = sha256_file(tmp)
            if verify and digest != expected_sha:
                tmp.unlink(missing_ok=True)
                raise AsrError(
                    f"SHA-256 mismatch for {name}: got {digest}, expected {expected_sha}. "
                    "Upstream file may have changed; refusing unverified model."
                )
            tmp.replace(dst)
        files[name] = {"path": str(dst), "bytes": dst.stat().st_size, "sha256": sha256_file(dst)}
    return {"model_dir": str(target), "repo": MODEL_REPO, "licence": "Apache-2.0", "files": files}


class WhisperExecuTorchASR:
    """Offline Whisper Tiny INT8 speech-to-text runner via ExecuTorch (XNNPACK)."""

    def __init__(self, model_dir: str | Path | None = None):
        self.pte_path, self.tokenizer_path = resolve_whisper_dir(model_dir)
        import torch
        try:
            # Import the LLM custom-ops library before the first program load. Measured on
            # Neoverse-N1: without it Whisper decode is ~1.8x slower, and a Llama runner loaded
            # later in the same process drops from ~82 to ~18 prefill tokens/s.
            from executorch.extension.llm.custom_ops import custom_ops  # noqa: F401
        except ImportError:
            pass
        import executorch.kernels.quantized  # noqa: F401
        from executorch.runtime import Runtime

        self._torch = torch
        t0 = time.perf_counter()
        self.tokenizer = load_tokenizer(self.tokenizer_path)
        rt = Runtime.get()
        self.program = rt.load_program(str(self.pte_path))
        self.encoder = self.program.load_method("encoder")
        self.decoder = self.program.load_method("text_decoder")
        self.load_ms = round((time.perf_counter() - t0) * 1000, 1)

    def _decode_chunk(self, wav_chunk: np.ndarray, language: str = "en") -> dict:
        torch = self._torch
        t0 = time.perf_counter()
        feats_np = log_mel_spectrogram(wav_chunk)
        feats = torch.from_numpy(feats_np).contiguous()
        t1 = time.perf_counter()

        enc_out = self.encoder.execute([feats])[0]
        if isinstance(enc_out, (list, tuple)):
            enc_out = enc_out[0]
        hidden = torch.as_tensor(enc_out).float().contiguous()
        t2 = time.perf_counter()

        # Step 0: feed <|startoftranscript|> at KV cache position 0.
        logits0 = self.decoder.execute([
            torch.tensor([[DECODER_START_TOKEN_ID]], dtype=torch.long),
            hidden,
            torch.tensor([0], dtype=torch.long),
        ])[0]
        if isinstance(logits0, (list, tuple)):
            logits0 = logits0[0]
        logits0 = torch.as_tensor(logits0).float().flatten()

        if language == "auto":
            en_score = float(logits0[LANG_TOKEN_IDS["en"]].item())
            hi_score = float(logits0[LANG_TOKEN_IDS["hi"]].item())
            det_lang = "hi" if hi_score > en_score else "en"
        elif language in LANG_TOKEN_IDS:
            det_lang = language
        else:
            det_lang = "en"

        prefix = [LANG_TOKEN_IDS[det_lang], TRANSCRIBE_TOKEN_ID, NOTIMESTAMPS_TOKEN_ID]
        tokens = [DECODER_START_TOKEN_ID, prefix[0]]
        free_tokens: list[int] = []
        stop_reason = "max_tokens"
        decode_start = time.perf_counter()

        suppress_idx = list(SUPPRESS_TOKENS)
        begin_suppress_idx = list(BEGIN_SUPPRESS_TOKENS)

        for step in range(1, MAX_GENERATION_TOKENS + len(prefix)):
            out = self.decoder.execute([
                torch.tensor([[tokens[-1]]], dtype=torch.long),
                hidden,
                torch.tensor([step], dtype=torch.long),
            ])[0]
            if isinstance(out, (list, tuple)):
                out = out[0]
            logits = torch.as_tensor(out).float().flatten()

            if step < len(prefix):
                nxt = prefix[step]
            else:
                scores = logits.clone()
                vocab = scores.shape[0]
                valid_sup = [i for i in suppress_idx if 0 <= i < vocab and i != EOS_TOKEN_ID]
                if valid_sup:
                    scores[valid_sup] = float("-inf")
                if not free_tokens:
                    valid_beg = [i for i in begin_suppress_idx if 0 <= i < vocab]
                    if valid_beg:
                        scores[valid_beg] = float("-inf")
                nxt = int(scores.argmax().item())
                if nxt == EOS_TOKEN_ID:
                    stop_reason = "eos"
                    tokens.append(nxt)
                    break
                free_tokens.append(nxt)
                rep_len = find_repeated_suffix_pattern(free_tokens)
                if rep_len is not None:
                    trim = rep_len * REPETITION_GUARD_REPEATS
                    del free_tokens[-trim:]
                    if trim > 1:
                        del tokens[-(trim - 1):]
                    stop_reason = "repetition_guard"
                    break
                if time.perf_counter() - decode_start >= MAX_SECONDS_PER_CHUNK:
                    stop_reason = "timeout"
                    break
            tokens.append(nxt)

        t3 = time.perf_counter()
        text = self.tokenizer.decode(tokens, skip_special_tokens=True).strip()
        return {
            "text": text,
            "language": det_lang,
            "generated_tokens": len(free_tokens),
            "stop_reason": stop_reason,
            "mel_ms": (t1 - t0) * 1000,
            "encode_ms": (t2 - t1) * 1000,
            "decode_ms": (t3 - t2) * 1000,
        }

    def transcribe_waveform(self, waveform_16k: np.ndarray, language: str = "en") -> dict:
        """Transcribe a 16 kHz mono float32 waveform (auto-chunked in 30 s windows)."""
        duration_s = round(len(waveform_16k) / SAMPLE_RATE, 3)
        chunks = split_chunks(waveform_16k)
        parts, langs, reasons = [], [], []
        mel_ms = enc_ms = dec_ms = 0.0
        gen_tokens = 0
        for chunk in chunks:
            res = self._decode_chunk(chunk, language=language)
            if res["text"]:
                parts.append(res["text"])
            langs.append(res["language"])
            reasons.append(res["stop_reason"])
            mel_ms += res["mel_ms"]
            enc_ms += res["encode_ms"]
            dec_ms += res["decode_ms"]
            gen_tokens += res["generated_tokens"]

        total_ms = mel_ms + enc_ms + dec_ms
        rtfx = round(duration_s / (total_ms / 1000.0), 2) if total_ms > 0 and duration_s > 0 else None
        rss_mb = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 1)
        return {
            "text": " ".join(parts).strip(),
            "language": langs[0] if langs else language,
            "audio_seconds": duration_s,
            "chunks": len(chunks),
            "generated_tokens": gen_tokens,
            "stop_reason": reasons[-1] if reasons else "empty",
            "backend": "executorch",
            "model": MODEL_ID,
            "load_ms": self.load_ms,
            "mel_ms": round(mel_ms, 1),
            "encode_ms": round(enc_ms, 1),
            "decode_ms": round(dec_ms, 1),
            "total_ms": round(total_ms, 1),
            "rtfx": rtfx,
            "peak_rss_mb": rss_mb,
        }

    def transcribe_file(self, audio_path: str | Path, language: str = "en") -> dict:
        wav, _ = load_audio_16k(audio_path)
        return self.transcribe_waveform(wav, language=language)
