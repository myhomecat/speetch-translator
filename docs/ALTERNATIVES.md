# 동시통역 대안 기술 비교

현재 구현된 Gemini Live API는 턴제(Turn-based) 방식입니다. 진정한 동시통역을 위한 대안 기술들을 비교합니다.

## 목차
1. [현재 구현 방식의 한계](#현재-구현-방식의-한계)
2. [대안 1: OpenAI Realtime API](#대안-1-openai-realtime-api)
3. [대안 2: Meta SeamlessStreaming](#대안-2-meta-seamlessstreaming)
4. [대안 3: STT → 번역 → TTS 파이프라인](#대안-3-stt--번역--tts-파이프라인)
5. [대안 4: StreamSpeech](#대안-4-streamspeech)
6. [비용 비교](#비용-비교)
7. [권장 사항](#권장-사항)

---

## 현재 구현 방식의 한계

### Gemini Live API (현재)
- **방식**: 턴제 (Turn-based)
- **동작**: 사용자 발화 완료 → 번역 → 응답
- **지연시간**: 발화 완료 후 1-3초
- **장점**: 설정 간단, 무료 티어 제공
- **단점**: 실시간 동시통역 불가, 세션 초기화 필요

---

## 대안 1: OpenAI Realtime API

### 개요
OpenAI의 실시간 음성 API로, WebSocket/WebRTC를 통한 저지연 Speech-to-Speech 지원.

### 특징
| 항목 | 내용 |
|------|------|
| **지연시간** | 200-300ms (거의 실시간) |
| **연결 방식** | WebSocket, WebRTC, SIP |
| **세션 제한** | 최대 60분 |
| **동시 세션** | 무제한 (2025.02.03~) |
| **감정 보존** | 음성의 감정, 톤, 속도 유지 |

### 장점
- 진정한 Speech-to-Speech (중간 텍스트 변환 없음)
- 자연스러운 바지인(Barge-in) 처리
- 감정/억양 보존 우수

### 단점
- **유료** (무료 티어 없음)
- 가격: 약 $0.06/분 (입력) + $0.24/분 (출력)
- 한국어 지원 제한적

### 코드 예시
```python
import websockets
import json

async def openai_realtime():
    url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "OpenAI-Beta": "realtime=v1"
    }

    async with websockets.connect(url, extra_headers=headers) as ws:
        # 세션 설정
        await ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "instructions": "Translate Korean to Japanese in real-time",
                "input_audio_transcription": {"model": "whisper-1"}
            }
        }))

        # 오디오 스트리밍...
```

### 참고 자료
- [OpenAI Realtime API 문서](https://platform.openai.com/docs/guides/realtime)
- [번역 예제 Cookbook](https://cookbook.openai.com/examples/voice_solutions/one_way_translation_using_realtime_api)

---

## 대안 2: Meta SeamlessStreaming

### 개요
Meta의 오픈소스 동시통역 모델. 약 2초 지연시간으로 100개 언어 지원.

### 특징
| 항목 | 내용 |
|------|------|
| **지연시간** | ~2초 |
| **지원 언어** | 100개 (입력), 36개 (음성 출력) |
| **모델 크기** | 2.3B (large), 1.2B (medium) |
| **라이선스** | CC BY-NC 4.0 (비상업적) |
| **한국어** | ✅ 지원 |
| **일본어** | ✅ 지원 |

### 장점
- **무료** (오픈소스)
- 진정한 동시통역 (Simultaneous Translation)
- 감정/억양 보존 (SeamlessExpressive)
- 로컬 실행 가능

### 단점
- **GPU 필요** (최소 16GB VRAM 권장)
- 서버 구축 필요
- 비상업적 라이선스

### 설치 및 실행
```bash
# 설치
pip install fairseq2 seamless_communication

# Python 코드
from seamless_communication.streaming import StreamingS2STAgent

agent = StreamingS2STAgent(
    source_lang="kor",
    target_lang="jpn",
    device="cuda"
)

# 실시간 스트리밍
async for audio_chunk in audio_stream:
    translated = await agent.process(audio_chunk)
    yield translated
```

### 하드웨어 요구사항
| 모델 | VRAM | 처리 속도 |
|------|------|----------|
| Medium (1.2B) | 8GB | ~2x 실시간 |
| Large (2.3B) | 16GB | ~1.5x 실시간 |

### 참고 자료
- [GitHub 저장소](https://github.com/facebookresearch/seamless_communication)
- [Hugging Face 모델](https://huggingface.co/facebook/seamless-m4t-v2-large)
- [Meta AI 블로그](https://ai.meta.com/research/seamless-communication/)

---

## 대안 3: STT → 번역 → TTS 파이프라인

### 개요
전통적인 캐스케이드 방식. 각 단계를 별도 서비스로 구성.

### 아키텍처
```
[마이크] → [Streaming STT] → [Translation API] → [Streaming TTS] → [스피커]
           (실시간 텍스트)     (텍스트 번역)      (실시간 음성)
```

### 서비스 조합 예시

#### 옵션 A: Google Cloud (유료)
| 단계 | 서비스 | 가격 |
|------|--------|------|
| STT | Cloud Speech-to-Text | $0.016/분 |
| 번역 | Cloud Translation | $20/백만 문자 |
| TTS | Cloud Text-to-Speech | $4/백만 문자 |

#### 옵션 B: Deepgram + DeepL (유료)
| 단계 | 서비스 | 가격 |
|------|--------|------|
| STT | Deepgram Nova-3 | $0.0077/분 (실시간) |
| 번역 | DeepL API | $5.49/백만 문자 |
| TTS | ElevenLabs | $0.30/1000 문자 |

#### 옵션 C: 오픈소스 (무료, GPU 필요)
| 단계 | 서비스 | 요구사항 |
|------|--------|----------|
| STT | Whisper / Faster-Whisper | 4GB VRAM |
| 번역 | NLLB / MarianMT | 2GB VRAM |
| TTS | Coqui TTS / VITS | 4GB VRAM |

### 장점
- 각 단계 최적화 가능
- 서비스 교체 용이
- 중간 텍스트 활용 가능 (자막)

### 단점
- **지연시간 누적** (각 단계 100-500ms)
- 감정/억양 손실
- 복잡한 구현

### 코드 예시 (파이프라인)
```python
import asyncio
from deepgram import DeepgramClient
from google.cloud import translate_v2
from elevenlabs import stream as tts_stream

async def cascade_pipeline(audio_stream):
    # 1. Streaming STT
    deepgram = DeepgramClient(DEEPGRAM_API_KEY)

    async for transcript in deepgram.listen.live(audio_stream):
        if transcript.is_final:
            # 2. Translation
            translated = translate_client.translate(
                transcript.text,
                source_language="ko",
                target_language="ja"
            )

            # 3. Streaming TTS
            audio = tts_stream(translated["translatedText"])
            yield audio
```

---

## 대안 4: StreamSpeech

### 개요
"All in One" 오픈소스 모델. 동시 ASR, 번역, TTS를 단일 모델로 처리.

### 특징
| 항목 | 내용 |
|------|------|
| **방식** | End-to-End Simultaneous S2ST |
| **지연시간** | 조절 가능 (품질 vs 속도 트레이드오프) |
| **라이선스** | MIT (상업적 사용 가능) |

### 지원 기능
- Simultaneous ASR (동시 음성인식)
- Simultaneous S2TT (동시 음성-텍스트 번역)
- Simultaneous S2ST (동시 음성-음성 번역)
- Real-time TTS

### 참고 자료
- [GitHub 저장소](https://github.com/ictnlp/StreamSpeech)

---

## 비용 비교

### 월 100시간 사용 기준

| 솔루션 | 월 비용 | 지연시간 | GPU 필요 |
|--------|---------|----------|----------|
| **Gemini Live (현재)** | 무료* | 1-3초 (턴제) | ❌ |
| **OpenAI Realtime** | ~$1,800 | 200-300ms | ❌ |
| **Google Cloud 파이프라인** | ~$150 | 500-1000ms | ❌ |
| **Deepgram 파이프라인** | ~$80 | 300-700ms | ❌ |
| **SeamlessStreaming** | 전기료만 | ~2초 | ✅ (16GB) |
| **StreamSpeech** | 전기료만 | 조절가능 | ✅ (8GB) |

*Gemini 무료 티어 제한 있음

### GPU 서버 비용 참고
| 서비스 | GPU | 월 비용 |
|--------|-----|---------|
| Lambda Labs | A10 (24GB) | ~$350/월 |
| Vast.ai | RTX 3090 | ~$200/월 |
| RunPod | RTX 4090 | ~$400/월 |
| 자체 구축 | RTX 4080 | 전기료 ~$30/월 |

---

## 권장 사항

### 사용 사례별 추천

#### 1. 개인/학습 목적 (무료)
**추천: 현재 Gemini Live API 유지**
- 턴제지만 무료
- 설정 간단
- 품질 우수

#### 2. 프로토타입/데모 (저비용)
**추천: Deepgram + DeepL 파이프라인**
- $200 무료 크레딧 (Deepgram)
- 비교적 낮은 지연시간
- 빠른 구현

#### 3. 프로덕션 (품질 중시)
**추천: OpenAI Realtime API**
- 가장 낮은 지연시간
- 감정/억양 보존
- 안정적인 서비스

#### 4. 프로덕션 (비용 중시)
**추천: SeamlessStreaming + GPU 서버**
- 초기 비용 후 저렴한 운영비
- 2초 지연으로 실용적
- 100개 언어 지원

### 이 프로젝트 적용 방안

현재 아키텍처를 유지하면서 백엔드의 `gemini_session.py`를 교체 가능한 구조로 리팩토링:

```python
# backend/app/core/translation_provider.py
from abc import ABC, abstractmethod

class TranslationProvider(ABC):
    @abstractmethod
    async def connect(self): pass

    @abstractmethod
    async def send_audio(self, audio: bytes): pass

    @abstractmethod
    async def disconnect(self): pass

class GeminiProvider(TranslationProvider):
    # 현재 구현
    pass

class OpenAIRealtimeProvider(TranslationProvider):
    # OpenAI Realtime API 구현
    pass

class SeamlessProvider(TranslationProvider):
    # SeamlessStreaming 구현
    pass
```

---

## 결론

| 요소 | Gemini (현재) | OpenAI | Seamless | 파이프라인 |
|------|--------------|--------|----------|-----------|
| **동시통역** | ❌ 턴제 | ✅ | ✅ | △ 지연있음 |
| **비용** | 무료 | 고가 | GPU비용 | 중간 |
| **구현 난이도** | 쉬움 | 중간 | 어려움 | 중간 |
| **한/일 지원** | ✅ | △ | ✅ | ✅ |
| **감정 보존** | ✅ | ✅ | ✅ | ❌ |

**최종 권장**:
- 현재 상태로 사용하되, 추후 **SeamlessStreaming**으로 마이그레이션 고려
- GPU 서버 확보 시 동시통역 구현 가능
- OpenAI는 비용 대비 효과 검토 필요

---

## 참고 링크

### 공식 문서
- [OpenAI Realtime API](https://platform.openai.com/docs/guides/realtime)
- [Meta Seamless Communication](https://ai.meta.com/research/seamless-communication/)
- [Google Cloud Speech-to-Text](https://cloud.google.com/speech-to-text)
- [Deepgram API](https://deepgram.com/pricing)

### GitHub 저장소
- [seamless_communication](https://github.com/facebookresearch/seamless_communication)
- [StreamSpeech](https://github.com/ictnlp/StreamSpeech)
- [RealtimeSTT](https://github.com/KoljaB/RealtimeSTT)
- [RealtimeTTS](https://github.com/KoljaB/RealtimeTTS)

### 비교 자료
- [Real-Time vs Turn-Based Architecture](https://softcery.com/lab/ai-voice-agents-real-time-vs-turn-based-tts-stt-architecture)
- [Speech-to-Speech APIs 비교](https://getstream.io/blog/speech-apis/)

---

*Last Updated: 2026-01-07*
