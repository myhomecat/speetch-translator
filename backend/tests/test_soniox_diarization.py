"""Soniox diarization 토큰 처리 유닛테스트

실제 Soniox 연결 없이 _process_response에 diarization 형식의 토큰을 넣어
화자 전환 시 버퍼 분리와 speaker 전달을 검증한다.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.soniox_session import SonioxSession
from app.models.room import TranslationMode


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def make_session(collected):
    async def on_transcript(text, is_final, translated, speaker=None):
        collected.append((text, is_final, translated, speaker))

    return SonioxSession(
        user_id="u1",
        translation_mode=TranslationMode.AUTO,
        on_transcript=on_transcript,
    )


def test_speaker_change_flushes_previous_buffer():
    collected = []
    session = make_session(collected)

    async def scenario():
        # 화자 1 발화
        await session._process_response({
            "tokens": [
                {"text": "안녕하세요", "is_final": True,
                 "translation_status": "original", "language": "ko", "speaker": 1},
            ]
        })
        # 화자 2로 전환 → 화자 1 버퍼가 final로 플러시되어야 함
        await session._process_response({
            "tokens": [
                {"text": "こんにちは", "is_final": True,
                 "translation_status": "original", "language": "ja", "speaker": 2},
            ]
        })
        await session._process_response({"segment_end": True})

    run(scenario())

    finals = [c for c in collected if c[1] is True]
    assert len(finals) == 2, f"final 2건이어야 함: {finals}"
    assert finals[0][0] == "안녕하세요" and finals[0][3] == 1, finals[0]
    assert finals[1][0] == "こんにちは" and finals[1][3] == 2, finals[1]
    print("PASS: 화자 전환 시 버퍼 분리 + speaker 전달")


def test_same_speaker_accumulates():
    collected = []
    session = make_session(collected)

    async def scenario():
        for text in ["오늘 ", "미팅에 ", "참석해주셔서"]:
            await session._process_response({
                "tokens": [
                    {"text": text, "is_final": True,
                     "translation_status": "original", "language": "ko", "speaker": 1},
                ]
            })
        await session._process_response({"segment_end": True})

    run(scenario())

    finals = [c for c in collected if c[1] is True]
    assert len(finals) == 1, f"동일 화자는 한 문장으로 누적되어야 함: {finals}"
    assert finals[0][0] == "오늘 미팅에 참석해주셔서"
    assert finals[0][3] == 1
    print("PASS: 동일 화자 누적")


def test_translation_tokens_carry_speaker():
    collected = []
    session = make_session(collected)

    async def scenario():
        await session._process_response({
            "tokens": [
                {"text": "감사합니다", "is_final": True,
                 "translation_status": "original", "language": "ko", "speaker": 1},
                {"text": "ありがとうございます", "is_final": True,
                 "translation_status": "translation", "language": "ja"},
            ]
        })
        await session._process_response({"segment_end": True})

    run(scenario())

    finals = [c for c in collected if c[1] is True]
    assert len(finals) == 1
    text, _, translated, speaker = finals[0]
    assert text == "감사합니다" and translated == "ありがとうございます"
    assert speaker == 1, "번역 토큰에도 현재 화자가 붙어야 함"
    print("PASS: 번역 토큰 speaker 전달")


def test_diarization_config_flag():
    session = make_session([])
    # 기본값은 OFF (실 키 검증 전 prod 동작 보존)
    config = session._get_config()
    assert "enable_speaker_diarization" not in config
    # env로 켜면 Soniox 설정에 포함되어야 함
    session._settings.enable_speaker_diarization = True
    config = session._get_config()
    assert config.get("enable_speaker_diarization") is True
    print("PASS: enable_speaker_diarization 기본 OFF / env ON 시 포함")


if __name__ == "__main__":
    asyncio.set_event_loop(asyncio.new_event_loop())
    test_speaker_change_flushes_previous_buffer()
    test_same_speaker_accumulates()
    test_translation_tokens_carry_speaker()
    test_diarization_config_flag()
    print("\n모든 diarization 유닛테스트 통과")
