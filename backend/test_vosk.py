#!/usr/bin/env python3
"""Test Vosk STT with audio files"""

import wave
import subprocess
import json
from pathlib import Path
from vosk import Model, KaldiRecognizer

MODELS_DIR = Path(__file__).parent / "models"
TEST_AUDIO_DIR = Path(__file__).parent.parent / "test_audio"

def convert_mp3_to_wav(mp3_path: Path, wav_path: Path):
    """Convert MP3 to 16kHz mono WAV using ffmpeg"""
    cmd = [
        "ffmpeg", "-y", "-i", str(mp3_path),
        "-ar", "16000",  # 16kHz sample rate
        "-ac", "1",      # mono
        "-f", "wav",
        str(wav_path)
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    print(f"Converted {mp3_path.name} to WAV")

def test_vosk_stt(audio_file: Path, lang: str):
    """Test Vosk STT on a single audio file"""
    model_path = MODELS_DIR / f"vosk-model-small-{lang}-0.22"

    if not model_path.exists():
        print(f"Model not found: {model_path}")
        return None

    # Convert to WAV if needed
    if audio_file.suffix.lower() == ".mp3":
        wav_file = audio_file.with_suffix(".wav")
        convert_mp3_to_wav(audio_file, wav_file)
        audio_file = wav_file

    print(f"\nTesting: {audio_file.name} with {lang} model")
    print("-" * 50)

    # Load model
    model = Model(str(model_path))

    # Open audio file
    wf = wave.open(str(audio_file), "rb")

    if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getcomptype() != "NONE":
        print(f"Audio file must be WAV mono PCM. Got: channels={wf.getnchannels()}, width={wf.getsampwidth()}")
        return None

    sample_rate = wf.getframerate()
    print(f"Sample rate: {sample_rate}")

    rec = KaldiRecognizer(model, sample_rate)
    rec.SetWords(True)

    results = []

    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            if result.get("text"):
                print(f"[Final] {result['text']}")
                results.append(result["text"])
        else:
            partial = json.loads(rec.PartialResult())
            if partial.get("partial"):
                print(f"[Partial] {partial['partial']}", end="\r")

    # Get final result
    final = json.loads(rec.FinalResult())
    if final.get("text"):
        print(f"[Final] {final['text']}")
        results.append(final["text"])

    wf.close()

    full_text = " ".join(results)
    print(f"\n=== Full result: {full_text}")
    return full_text


def main():
    print("=== Vosk STT Test ===\n")

    # Test Korean files
    print("\n### Korean Tests ###")
    for i in range(1, 4):
        ko_file = TEST_AUDIO_DIR / f"ko_{i}.mp3"
        if ko_file.exists():
            test_vosk_stt(ko_file, "ko")

    # Test Japanese files
    print("\n### Japanese Tests ###")
    for i in range(1, 4):
        ja_file = TEST_AUDIO_DIR / f"ja_{i}.mp3"
        if ja_file.exists():
            test_vosk_stt(ja_file, "ja")


if __name__ == "__main__":
    main()
