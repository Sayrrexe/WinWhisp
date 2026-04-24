"""Мини-проверка ASR: качает tiny-модель и транскрибирует 2 секунды синуса."""
import numpy as np
from transcrb.asr.engine import ensure_model
from faster_whisper import WhisperModel


def main():
    model_path = ensure_model("tiny")
    print(f"model at: {model_path}")
    m = WhisperModel(str(model_path), device="cuda", compute_type="float16")
    print("model loaded on CUDA fp16")
    t = np.linspace(0, 2, 32000, dtype=np.float32)
    sig = 0.1 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
    segs, info = m.transcribe(sig, beam_size=1, language="en")
    print(f"language detected: {info.language} prob={info.language_probability:.2f}")
    for s in segs:
        print(f"  [{s.start:.2f}-{s.end:.2f}] {s.text}")
    print("ASR round-trip OK")


if __name__ == "__main__":
    main()
