# Real-Time Korean-Japanese Speech Translator

실시간 한국어-일본어 동시번역기 구현 계획서

## 프로젝트 개요

| 항목 | 내용 |
|------|------|
| **목적** | 실시간 음성 동시번역 채팅방 |
| **번역 언어** | 한국어 ↔ 일본어 |
| **최대 인원** | 3명 |
| **접속 방식** | URL 공유 |

## 기술 스택

| Component | Technology |
|-----------|------------|
| **Backend** | Python + FastAPI |
| **Frontend** | Next.js (TypeScript + Tailwind) |
| **Translation API** | Gemini 2.5 Flash Native Audio |
| **Real-time** | WebSocket |
| **Model** | `gemini-2.5-flash-native-audio-preview-12-2025` |

## 주요 기능

### 1. 음성 번역 (Speech-to-Speech)
- 사용자 음성 → Gemini Live API → 번역된 음성
- 화자의 억양/감정 보존
- 실시간 저지연 처리

### 2. 자막 표시 (STT)
- 입력 음성 텍스트 (원본 언어)
- 출력 음성 텍스트 (번역 언어)
- 라인 형태로 실시간 표시

### 3. 번역 모드
- **auto**: 자동 언어 감지 후 번역
- **ko_to_ja**: 한국어 → 일본어 고정
- **ja_to_ko**: 일본어 → 한국어 고정

### 4. 채팅방
- URL 공유로 입장 (`/room/{roomId}`)
- 최대 3명 동시 접속
- 다른 참가자에게 번역된 음성 전송

## 오디오 사양

| Direction | Sample Rate | Format |
|-----------|-------------|--------|
| Client → Server | 16kHz | 16-bit PCM, mono |
| Server → Client | 24kHz | 16-bit PCM, mono |

## 아키텍처

```
[User A Browser]                    [FastAPI Server]                    [User B Browser]
     │                                     │                                   │
     │ ── Audio (PCM 16kHz) ──────────────>│                                   │
     │                                     │── Audio to Gemini Live API ──────>│
     │                                     │<─ Translated Audio (24kHz) ───────│
     │                                     │<─ Transcription ──────────────────│
     │                                     │                                   │
     │<───────── Translated Audio ─────────│── Broadcast to Others ───────────>│
     │<───────── STT Transcripts ──────────│                                   │
```

## 프로젝트 구조

```
speetch-translator/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI entry point
│   │   ├── config.py                  # Environment config
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── websocket.py           # WebSocket handlers
│   │   │   └── rooms.py               # Room REST API
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── room_manager.py        # Room state management
│   │   │   ├── connection_manager.py  # WebSocket connections
│   │   │   └── gemini_session.py      # Gemini Live API wrapper
│   │   └── models/
│   │       ├── __init__.py
│   │       ├── messages.py            # Message types
│   │       └── room.py                # Room/User models
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx               # Home (room creation)
│   │   │   └── room/[roomId]/page.tsx # Room page
│   │   ├── components/
│   │   │   ├── TranslatorRoom.tsx     # Main translator UI
│   │   │   ├── AudioControls.tsx      # Start/Stop buttons
│   │   │   ├── SubtitleDisplay.tsx    # STT text display
│   │   │   └── LanguageSelector.tsx   # Mode selection
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts        # WebSocket hook
│   │   │   ├── useAudioCapture.ts     # Microphone capture
│   │   │   └── useAudioPlayback.ts    # Audio playback
│   │   ├── lib/
│   │   │   └── constants.ts           # Config constants
│   │   └── types/
│   │       └── index.ts               # TypeScript types
│   ├── public/worklet/
│   │   └── pcm-processor.js           # AudioWorklet processor
│   └── package.json
│
├── docker-compose.yml
├── PLAN.md                            # This file
└── README.md
```

## 구현 상태

### Phase 1: Backend 기본 구조 ✅
1. ✅ `backend/app/config.py` - 환경 변수 설정
2. ✅ `backend/app/models/room.py` - Room, User 모델
3. ✅ `backend/app/core/room_manager.py` - 방 관리 (max 3명)
4. ✅ `backend/app/core/connection_manager.py` - WebSocket 연결 관리
5. ✅ `backend/app/main.py` - FastAPI 앱 + CORS

### Phase 2: Gemini 연동 ✅
6. ✅ `backend/app/core/gemini_session.py` - Gemini Live API 래퍼
   - System instruction으로 번역 지시
   - 오디오 스트리밍 + 트랜스크립션
   - 자동 재연결 로직
   - VAD 연속 청취 모드 설정
7. ✅ `backend/app/api/websocket.py` - WebSocket 엔드포인트
8. ✅ `backend/app/api/rooms.py` - 방 생성 REST API

### Phase 3: Frontend 기본 구조 ✅
9. ✅ Next.js 프로젝트 생성 (TypeScript + Tailwind)
10. ✅ `frontend/src/types/index.ts` - 타입 정의
11. ✅ `frontend/src/lib/constants.ts` - 상수 정의
12. ✅ AudioWorklet 인라인 구현 (useAudioCapture.ts 내부)

### Phase 4: Frontend 오디오 & WebSocket ✅
13. ✅ `frontend/src/hooks/useAudioCapture.ts` - 마이크 캡처 + 다운샘플링
14. ✅ `frontend/src/hooks/useAudioPlayback.ts` - 오디오 재생
15. ✅ `frontend/src/hooks/useWebSocket.ts` - Binary/JSON 멀티플렉싱

### Phase 5: Frontend UI ✅
16. ✅ `frontend/src/components/AudioControls.tsx` - 녹음 제어
17. ✅ `frontend/src/components/LanguageSelector.tsx` - 모드 선택
18. ✅ `frontend/src/components/SubtitleDisplay.tsx` - 자막 표시
19. ✅ `frontend/src/components/TranslatorRoom.tsx` - 메인 컴포넌트
20. ✅ `frontend/src/components/AudioFileUpload.tsx` - 오디오 파일 테스트
21. ✅ `frontend/src/components/UserList.tsx` - 접속자 목록

### Phase 6: 통합 및 테스트 ✅
22. ✅ `frontend/src/app/page.tsx` - 홈 페이지
23. ✅ `frontend/src/app/room/[roomId]/page.tsx` - 방 페이지
24. ✅ End-to-end 테스트 완료
25. ⬜ Docker 설정 (선택)

## 환경 변수

### Backend (.env)
```bash
GEMINI_API_KEY=your_gemini_api_key_here
ALLOWED_ORIGINS=http://localhost:3000
MAX_USERS_PER_ROOM=3
```

### Frontend (.env.local)
```bash
NEXT_PUBLIC_WS_URL=ws://localhost:8000
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Dependencies

### Backend (requirements.txt)
```
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
websockets>=12.0
google-genai>=0.4.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
python-dotenv>=1.0.0
```

### Frontend (npm)
```
next
react
react-dom
typescript
@types/react
tailwindcss
uuid
```

## 핵심 코드 패턴

### 1. Gemini Session 설정
```python
config = {
    "response_modalities": ["AUDIO"],
    "system_instruction": """
        You are a real-time speech translator.
        When you hear Korean, translate and speak in Japanese.
        When you hear Japanese, translate and speak in Korean.
        Preserve the speaker's tone and emotion.
    """,
    "input_audio_transcription": {},   # Enable STT
    "output_audio_transcription": {},
}
```

### 2. WebSocket Binary/JSON 처리
```python
# Backend
if "bytes" in message:
    # Binary audio data
    await gemini_session.send_audio(message["bytes"])
elif "text" in message:
    # JSON control message
    data = json.loads(message["text"])
```

```typescript
// Frontend
ws.onmessage = (event) => {
  if (event.data instanceof ArrayBuffer) {
    playAudio(event.data);  // Binary
  } else {
    handleMessage(JSON.parse(event.data));  // JSON
  }
};
```

### 3. AudioWorklet 다운샘플링
```javascript
// 48kHz → 16kHz
downsample(buffer, fromRate, toRate) {
    const ratio = fromRate / toRate;
    const newLength = Math.round(buffer.length / ratio);
    const result = new Float32Array(newLength);
    // ... averaging samples
    return result;
}
```

## 주의 사항

| 이슈 | 해결 방안 |
|------|----------|
| 브라우저 48kHz vs API 16kHz | AudioWorklet에서 클라이언트 측 다운샘플링 |
| Gemini 세션 제한 (15분) | 재연결 로직 구현 ✅ |
| 오디오 재생 끊김 | currentTime 기반 스케줄링 |
| 방 정리 | 비활성 방 타임아웃 + 연결 해제 시 정리 |
| HTTPS 필요 (getUserMedia) | 프로덕션에서 HTTPS 사용, localhost는 예외 |
| React StrictMode 중복 연결 | isConnectingRef로 중복 방지 ✅ |
| 녹음 간 세션 초기화 | reset_session 메시지로 해결 ✅ |

## 추가 구현 사항

### VAD (Voice Activity Detection) 설정
연속 청취 모드를 위한 VAD 파라미터 최적화:
```python
realtime_input_config=types.RealtimeInputConfig(
    automatic_activity_detection=types.AutomaticActivityDetection(
        disabled=False,
        start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_LOW,
        end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_LOW,
        silence_duration_ms=2000,  # 2초 침묵 허용
        prefix_padding_ms=500,     # 500ms 이상 말해야 인식
    )
)
```

### 오디오 파일 업로드 테스트
HTTP 환경에서 마이크 사용이 불가능한 경우를 위한 대체 테스트 방법:
- WAV/MP3/OGG 파일 업로드
- 자동으로 16kHz PCM으로 변환
- 청크 단위로 WebSocket 전송

### 실시간 자막 + 번역 (2026-01-07 추가)

#### 변경 배경
- 기존 Gemini Live API는 턴제 방식으로 1-3초 지연 발생
- 말하는 중간에 피드백이 없어 사용자 경험 저하

#### 해결 방법 (초기 설계)
```
[마이크] → [AssemblyAI Realtime] → interim (말하는 중): 원본만 표시
                                 → final (완료): Gemini Text API로 번역
```

#### 구현 파일
| 파일 | 역할 |
|------|------|
| `backend/app/core/assemblyai_session.py` | AssemblyAI 실시간 STT 세션 |
| `backend/app/core/text_translator.py` | ~~Gemini Text API 번역~~ → **LibreTranslate** |
| `frontend/src/components/SubtitleDisplay.tsx` | 실시간 자막 UI |

> 상세 문서: [docs/REALTIME_SUBTITLE.md](docs/REALTIME_SUBTITLE.md)

---

### 아키텍처 변경 (2026-01-07 저녁)

#### 발견된 문제점

1. **Gemini Live API 한계**
   - `output_transcription`이 항상 `None`으로 반환됨
   - System Instruction에 번역 지시를 해도 번역된 음성/텍스트를 생성하지 않음
   - `input_transcription`만 정상 작동 (STT 기능만 사용 가능)

2. **AssemblyAI Real-time Streaming 지원 언어 제한**
   - Universal-2 모델이 deprecated됨
   - 새로운 Universal Streaming은 **한국어/일본어 미지원**
   - 에러: `"Model deprecated. See docs for new model information"`

#### 해결 방법: LibreTranslate 통합

기존 Gemini Live API의 번역 기능 대신 **LibreTranslate**(오픈소스 번역 서버)를 사용:

```
[현재 파이프라인]
┌─────────────────────────────────────────────────────────────────┐
│  [마이크] → [Gemini Live API] → input_transcription (STT)       │
│                                        ↓                        │
│                              [LibreTranslate] (번역)            │
│                                        ↓                        │
│                              [UI 표시: 원본 + 번역]             │
└─────────────────────────────────────────────────────────────────┘
```

#### LibreTranslate 설정

```bash
# 설치 (pip)
pip install libretranslate

# 실행 (한국어, 일본어, 영어 지원)
libretranslate --load-only ko,ja,en
```

서버 주소: `http://localhost:5000`

#### 코드 변경 사항

| 파일 | 변경 내용 |
|------|----------|
| `backend/app/core/text_translator.py` | LibreTranslate API 호출로 변경 |
| `backend/app/api/websocket.py` | 문장 완성 감지 후 LibreTranslate 번역 호출 |
| `backend/app/core/gemini_session.py` | input_transcription 텍스트 로깅 추가 |

#### 번역 로직

```python
# websocket.py - on_transcript 콜백
input_text_buffer = []

if original_text:
    input_text_buffer.append(original_text)
    full_text = "".join(input_text_buffer)

    # 문장 종결 부호 감지 시 번역
    if any(char in original_text for char in [".", "。", "!", "?", "？", "！"]):
        trans_text, src_lang, tgt_lang = await text_translator.translate(full_text)
        # broadcast 번역 결과
        input_text_buffer = []  # 버퍼 초기화
```

---

### 알려진 이슈 및 향후 방향

#### 현재 이슈

| 이슈 | 상태 | 설명 |
|------|------|------|
| LibreTranslate 번역 품질 | ⚠️ 불안정 | 일부 기본 표현 오역 (예: "안녕하세요" → "お問い合わせ") |
| AssemblyAI 미작동 | ❌ 비활성화 | 한국어/일본어 실시간 스트리밍 미지원 |
| Gemini 번역 미작동 | ❌ 한계 | output_transcription 미반환 |

#### LibreTranslate 번역 품질 테스트

| 원본 (한국어) | LibreTranslate 번역 | 정확성 |
|--------------|---------------------|--------|
| 안녕하세요 | お問い合わせ | ❌ (정답: こんにちは) |
| 감사합니다 | 私たちについて | ❌ (정답: ありがとうございます) |
| 좋은 아침입니다 | おはようございます | ✅ |
| 오늘 날씨가 좋습니다 | 今日は天気が良い | ✅ |

#### Phase 7 진행 상황

##### Phase 7-2: Faster-Whisper 실시간 STT ✅ 완료 (2026-01-07)

**Vosk → Faster-Whisper 전환:**
- Vosk 한국어 모델 WER 28% → 정확도 부족
- Faster-Whisper WER ~5% → 높은 정확도

**구현 내용:**
- `backend/app/core/whisper_session.py` 생성
- VAD + 버퍼링으로 실시간 스트리밍 구현
- 서버 시작 시 모델 프리로드 (small 모델, ~500MB)
- **Local Agreement 알고리즘 적용** (아래 참조)

**테스트 결과 비교:**
```
Vosk:    "안녕하세요 오늘 날씨 가 정말 좋네요" ❌ (띄어쓰기 오류)
Whisper: "안녕하세요 오늘 날씨가 정말 좋네요" ✅ (정확)
```

**Local Agreement 알고리즘:**

참고: https://velog.io/@jayginwoolee/Whisper-streaming

배치 모델(Whisper)을 실시간 스트리밍에 활용하기 위한 알고리즘:

```
[Buffer 1] → "안녕하세요 오늘"
[Buffer 2] → "안녕하세요 오늘 날씨가" → "안녕하세요 오늘" 확정
[Buffer 3] → "안녕하세요 오늘 날씨가 정말" → "날씨가" 확정
...
```

- **n=2 설정**: 연속 2개 버퍼에서 동일한 토큰이 생성되어야 확정
- **Partial/Final**: 미확정 토큰은 partial로, 확정 토큰은 final로 전송
- **문맥 유지**: 이전 확정 텍스트(최대 200단어)를 프롬프트로 사용
- **문장 종결 감지**: `.` `?` `!` `。` `？` `！` 등의 종결 부호 감지 시 강제 확정
- **침묵 감지**: 1초 이상 침묵 시 강제 확정

**Faster-Whisper 장점:**
- OpenAI Whisper 기반 높은 정확도
- CTranslate2로 최적화되어 빠른 추론
- 한국어/일본어 자동 감지 지원
- CPU에서도 실시간 처리 가능

**STT 솔루션 비교:**

| 솔루션 | 실시간 스트리밍 | 서버 통합 | 정확도 | 메모리 |
|--------|----------------|-----------|--------|--------|
| Vosk | ✅ 네이티브 | ✅ 쉬움 | 중간 (WER 28%) | 낮음 (~50MB) |
| **Faster-Whisper** | ✅ Local Agreement | ✅ 구현됨 | 높음 (WER ~5%) | 중간 (~500MB) |
| Azure Speech | ✅ 네이티브 | ✅ SDK | 높음 | N/A (클라우드) |
| Buzz | ❌ GUI 앱 | ❌ 불가 | 높음 | - |

> **현재 사용 중: Faster-Whisper + Local Agreement**

**Azure Speech 대안 (로컬 솔루션 문제 시):**
- 무료 티어: 월 5시간 음성 인식
- 한국어/일본어 실시간 스트리밍 지원
- 높은 인식 정확도

##### 2. 번역 품질 개선: Google Cloud Translation 우선

| 항목 | 내용 |
|------|------|
| **1순위** | Google Cloud Translation API (무료 티어: 월 50만 자) |
| **대안** | LibreTranslate 개선 모델 탐색 |

**Google Cloud Translation 우선 이유:**
- LibreTranslate ko↔ja 품질이 매우 낮음 (기본 인사말도 오역)
- 커뮤니티에 고품질 ko↔ja 모델이 거의 없음
- Google Cloud는 품질이 보장되고 무료 티어가 넉넉함 (월 50만 자)
- `text_translator.py` 수정만으로 빠르게 전환 가능

**LibreTranslate 모델 탐색 (선택):**
- Argos Translate 기반 ko-ja 모델 품질 확인
- 개선 모델 발견 시 적용 검토

##### 🔴 발견된 성능 문제 (2026-01-07)

**Whisper CPU 처리 병목**:
```
측정 결과: 버퍼 7.34초 → 처리시간 10.40초 (실시간보다 느림!)
```

| 컴포넌트 | 처리 시간 | 병목 |
|---------|----------|------|
| **Whisper STT (CPU)** | 10.40초/7초 오디오 | 🔴 99% |
| LibreTranslate | ~0.1초 | ✅ |
| Gemini (클라우드) | 네트워크만 | ✅ |

##### Phase 7-3: Gemini S2ST API 전환 ⏳ 최우선 (권장)

**방향 전환 이유**:
- 원래 계획: 분산 Whisper GPU 서버 (Phase 7-3-B)
- **변경된 계획**: Gemini S2ST API 전환
- **이유**: Gemini S2ST가 **더 간단한 해결책**
  - 별도 Windows 서버 구축 불필요
  - STT + 번역 + TTS를 **한 API로** 해결
  - 인프라 관리 부담 없음

**목표**: Whisper + LibreTranslate를 Gemini S2ST로 완전 대체

**모델**: `gemini-2.5-flash-s2st-exp-11-2025` (음성-음성 번역 전용)

> 참고: [Vertex AI S2ST 문서](https://cloud.google.com/vertex-ai/generative-ai/docs/live-api/speech-to-speech-translation)

**아키텍처 변경**:
```
[현재]
마이크 → Whisper(CPU 병목) → LibreTranslate(품질↓) → UI

[Gemini S2ST]
마이크 → Gemini S2ST API → 원본텍스트 + 번역텍스트 + 번역음성(TTS)
         (클라우드)         (한 번에 모든 출력!)
```

**Gemini S2ST 출력**:
| 출력 | 설명 |
|------|------|
| 원본 텍스트 | 음성 인식 (STT) |
| 번역 텍스트 | 목표 언어 번역 |
| 번역 음성 | 화자 음성 보존 TTS |

**현재 vs Gemini S2ST 비교**:

| 항목 | 현재 | Gemini S2ST |
|------|------|-------------|
| STT | Whisper CPU (10초/7초) | ✅ 클라우드 실시간 |
| 번역 | LibreTranslate (오역) | ✅ Google 번역 |
| TTS | ❌ 없음 | ✅ 화자 음성 보존 |
| 스트리밍 | ⚠️ 버퍼링 | ✅ 네이티브 |
| 한국어/일본어 | ✅ | ✅ |

**가격 (Gemini 2.5 Flash Live API)**:

| 항목 | 가격 |
|------|------|
| 입력 오디오 | $3 / 1M 토큰 (25토큰/초) |
| 출력 오디오 | $12 / 1M 토큰 (12토큰/초) |
| **1분당** | **~$0.013 (약 18원)** |
| **1시간당** | **~$0.79 (약 1,100원)** |

> 참고: [Vertex AI Pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing)

**실험용 vs 유료**:

| 버전 | 모델 | 비용 | 안정성 |
|------|------|------|--------|
| 실험용 | `gemini-2.5-flash-s2st-exp-11-2025` | 무료 | ⚠️ 변경 가능 |
| 유료 | `gemini-2.5-flash` Live API | 위 가격표 | ✅ 안정 |

**필요 조건**:
- Google Cloud 프로젝트 생성
- Vertex AI API 활성화
- 서비스 계정 키 생성 (JSON)
- 결제 계정 연결 (실험용도 필요)

**구현 계획**:
1. `gemini_s2st_session.py` 생성
2. `websocket.py`에 모드 전환 플래그 추가
3. 기존 Whisper 코드 유지 (롤백 가능)
4. `.env`에 `USE_GEMINI_S2ST=true/false` 추가

**⚠️ 롤백 계획 (Gemini S2ST 실패 시)**:

현재 Whisper + LibreTranslate 코드는 **삭제하지 않고 유지**:
```python
# .env
USE_GEMINI_S2ST=true  # false로 변경 시 기존 방식으로 롤백

# websocket.py
if settings.use_gemini_s2st:
    # Gemini S2ST 사용
else:
    # 기존 Whisper + LibreTranslate 사용 (현재 코드)
```

**롤백이 필요한 상황**:
| 상황 | 대응 |
|------|------|
| Google Cloud 인증 실패 | `.env`에서 `USE_GEMINI_S2ST=false` |
| API 비용 과다 | 위와 동일 |
| 지연 시간 높음 | 위와 동일 |
| 실험용 모델 중단 | 위와 동일 또는 Phase 7-3-B 진행 |

---

##### Phase 7-3-B: 분산 Whisper GPU 서버 (2차 대안)

**사용 시점**: Gemini S2ST 실패 + 기존 Whisper(CPU) 성능도 부족할 때

**기존 방식(Whisper CPU)과의 차이**:
- 기존: Linux 서버 CPU에서 Whisper 실행 (느림)
- 대안: Windows GPU 서버에서 Whisper 실행 (빠름)

```
[Linux 서버]                         [Windows PC (GTX 1660 Ti)]
192.168.x.10                        192.168.x.20:8001
     │                                     │
[마이크] → [WebSocket] ──오디오 HTTP──→ [Whisper API 서버]
     │                                     │
     │         ←────텍스트 결과────←        │ (GPU: 0.6초/10초)
     │
     └→ [LibreTranslate] → 번역
```

**예상 성능 (GTX 1660 Ti 6GB)**:

| 모델 | CPU (현재) | GPU (예상) | 개선 |
|------|-----------|------------|------|
| small | ~10초 | **0.6초** | **17배** |

**필요 조건**:
- Windows: Python 3.10+, CUDA 11.x+, faster-whisper
- 내부 네트워크 IP 확인
- Windows 방화벽 포트 허용

##### Phase 7-4: UI 버그 수정 ⏳

**채팅 히스토리 미추가 문제**:
- 증상: 인식된 텍스트가 UI에 보이다가 사라짐
- 원인: `is_final: true` 메시지가 제대로 전송 안 됨
- 해결: Whisper `final` 전송 조건 확인 및 수정

##### Phase 7-5: 원본 음성 전달 기능 ⏳

**목표**: 마이크 입력 음성을 상대방에게도 들리게 하기

```python
# websocket.py에 추가
await connection_manager.broadcast_bytes(
    room_id=room_id,
    data=audio_bytes,
    exclude_user_id=user_id
)
```

**고려사항**: 네트워크 대역폭, 에코 방지

##### 구현 우선순위

```
[Phase 7-2] Faster-Whisper 실시간 STT ✅ 완료
     ↓
[Phase 7-3] Gemini S2ST API 전환 ⏳ 최우선 (권장 - 모든 문제 해결)
     │
     └─ [Phase 7-3-B] 분산 Whisper GPU 서버 (대안)
     ↓
[Phase 7-4] UI 버그 수정 (채팅 히스토리) ⏳
     ↓
[Phase 7-5] 원본 음성 전달 기능 ⏳
     ↓
[Phase 7-1] Google Cloud Translation API ⏳ (S2ST 전환 시 불필요)
```

**참고**: Gemini S2ST로 전환하면 Phase 7-1 (Google Cloud Translation)은 불필요해짐

#### 장기 개선 방향

1. **음성 합성 (TTS) 추가**
   - 번역된 텍스트를 음성으로 출력
   - Google Cloud TTS / VOICEVOX (일본어) 등

2. **Gemini Live API 모니터링**
   - output_transcription 지원 여부 추후 확인
   - API 업데이트 시 재테스트

## 참고 자료

### Gemini API
- [Live API Documentation](https://ai.google.dev/gemini-api/docs/live)
- [Live API WebSocket Reference](https://ai.google.dev/api/live)
- [Gemini 2.5 Native Audio Blog](https://blog.google/technology/google-deepmind/gemini-2-5-native-audio/)

### Web Audio
- [AudioWorklet Guide](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API/Using_AudioWorklet)
- [Web Audio API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API)

### FastAPI
- [WebSocket Documentation](https://fastapi.tiangolo.com/advanced/websockets/)

---

## Phase 8: Native Audio 실시간 테스트 (현재 진행 중)

### 현재 상태 (2026-01-08 16:40)

**완료된 작업:**
- ✅ Gemini Native Audio 모델 연결 성공 (`gemini-live-2.5-flash-native-audio`)
- ✅ 오디오 전송 및 응답 수신 확인
- ✅ output_transcription 텍스트 수신됨
- ✅ CORS 문제 해결 (allow_origins=["*"])
- ✅ 로깅 설정 개선 (websocket.py logger 레벨 설정)
- ✅ VAD 볼륨 기반 구현 (ONNX 오류로 @ricky0123/vad-web 대체)

**현재 이슈:**
| 이슈 | 상태 | 설명 |
|------|------|------|
| 자막 미표시 | 🔄 디버깅중 | on_transcript 콜백 완료 로그는 있으나 websocket.py의 on_s2st_transcript 로그 미출력 |
| Hairpin NAT | ⚠️ 우회 | 내부망에서 외부 IP 접근 불가, 내부 IP 사용 중 |
| input_transcription | ⚠️ 미지원 | Native Audio 모델은 입력 텍스트 미반환 |

### 다음 세션에서 해야 할 작업

#### 1. 자막 표시 문제 해결 (최우선)

**문제 분석:**
```
gemini_s2st_session.py: "[S2ST] on_transcript callback completed" ✅ 출력됨
websocket.py: "[WS] on_s2st_transcript: ..." ❌ 미출력
```

**확인해야 할 사항:**
1. websocket.py의 on_s2st_transcript 함수가 실제로 호출되는지 확인
2. 콜백 함수가 올바르게 전달되었는지 확인 (gemini_s2st_session_manager.create_session)
3. broadcast_json이 실행되는지 확인

**디버깅 방법:**
```bash
# 백엔드 로그 실시간 확인
tail -f /tmp/backend.log | grep -E "(WS\]|S2ST\])"
```

**테스트 방법:**
1. http://192.168.0.113:3000 접속
2. 방 생성 후 입장
3. 오디오 파일 업로드 또는 마이크 테스트
4. 백엔드 로그에서 `[WS] on_s2st_transcript` 확인

#### 2. 프론트엔드 메시지 핸들러 확인

**확인할 파일:** `frontend/src/hooks/useWebSocket.ts`

```typescript
// realtime_transcript 메시지 처리 확인
case "realtime_transcript":
  // 이 부분이 실행되는지 console.log 추가
  break;
```

#### 3. 오디오 파일 업로드 오류 해결

**현재 오류:** 오디오 파일 업로드 시 "오디오 파일 처리 중 오류가 발생했습니다" 발생

**확인할 파일:** `frontend/src/components/AudioFileUpload.tsx`
- 에러 로깅 개선됨 (error.name, error.message, error.stack 출력)
- 브라우저 콘솔에서 상세 오류 확인 필요

### 서버 실행 방법

```bash
# Backend (터미널 1)
cd /home/pgchae/바탕화면/speetch-translator/backend
source venv/bin/activate
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 10113 --log-level debug > /tmp/backend.log 2>&1 &

# Frontend (터미널 2)
cd /home/pgchae/바탕화면/speetch-translator/frontend
npm run dev

# 로그 확인
tail -f /tmp/backend.log
```

### 환경 설정

**frontend/.env.local:**
```
NEXT_PUBLIC_WS_URL=ws://192.168.0.113:10113
NEXT_PUBLIC_API_URL=http://192.168.0.113:10113
```

**backend/.env:**
```
USE_GEMINI_S2ST=true
GEMINI_S2ST_MODEL=gemini-live-2.5-flash-native-audio
```

### 주요 파일 위치

| 파일 | 역할 |
|------|------|
| `backend/app/api/websocket.py` | WebSocket 핸들러, on_s2st_transcript 콜백 정의 |
| `backend/app/core/gemini_s2st_session.py` | Gemini S2ST 세션 관리, on_transcript 호출 |
| `frontend/src/hooks/useWebSocket.ts` | 프론트엔드 WebSocket 메시지 처리 |
| `frontend/src/hooks/useAudioCapture.ts` | 마이크 캡처 + 볼륨 VAD |
| `frontend/src/components/SubtitleDisplay.tsx` | 자막 UI 표시 |

### 롤백 계획

Gemini S2ST 문제 시 Whisper + LibreTranslate로 롤백:
```bash
# backend/.env에서 변경
USE_GEMINI_S2ST=false
```

---

## Phase 9: 기술 분석 및 방향 재검토 (2026-01-23)

### 현재 상황 분석

#### Gemini API 한계점 발견

| 문제 | 상세 |
|------|------|
| **동시통역 미지원** | Gemini Live API는 턴 기반(turn-based) 방식만 지원 |
| **지연 시간** | 말이 끝나야 번역 시작 → 1~3초 지연 |
| **input_transcription 미지원** | Native Audio 모델은 입력 텍스트 미반환 |

#### Google의 동시통역 현황

| 플랫폼 | 동시통역 | 상태 |
|--------|---------|------|
| Google Translate 앱 | ✅ 지원 | 베타 (Android US/Mexico/India) |
| Gemini API (개발자용) | ❌ 미지원 | **2026년 추가 예정** |

> Google 공식: "Based on feedback, Google will continue to iterate on this experience and **bring it to more Google products including the Gemini API in 2026**."

#### 동시통역이 어려운 이유

1. **어순 차이**: 한국어/일본어는 동사가 문장 끝에 위치 → 끝까지 들어야 의미 확정
2. **문맥 의존**: 문장 완성 전까지 번역 불가
3. **처리 단계**: 음성인식(0.3초) + 번역(0.5초) + 음성합성(0.5초) ≈ 2초

**참고**: 전문 동시통역사도 2~4초 뒤처져서 통역함

---

### 대안 기술 검토

#### 1. Meta SeamlessStreaming

| 항목 | 내용 |
|------|------|
| **지연 시간** | ~2초 (전문 통역사 수준) |
| **동시 텍스트 출력** | ✅ 지원 (96개 언어) |
| **동시 음성 출력** | ✅ 지원 (36개 언어) |
| **한국어/일본어** | ✅ 지원 |
| **비용** | 무료 (로컬 실행) |
| **VRAM 요구** | ~6-8GB |

**문제점**: GTX 1660 Ti (6GB)로는 VRAM 부족

#### 2. Whisper GPU + Gemini Text API 조합

```
[음성 입력] → [Whisper GPU 실시간 STT] → [Gemini Text API 번역] → [텍스트 출력]
                   (0.6초)                    (0.3초)
```

| 항목 | 내용 |
|------|------|
| **실시간 텍스트** | ✅ 가능 |
| **번역 품질** | ✅ 높음 (Gemini) |
| **GTX 1660 Ti** | ✅ 가능 (Whisper small ~2-3GB) |
| **음성 출력** | ❌ 별도 TTS 필요 |

---

### GPU 성능 분석 (GTX 1660 Ti 6GB)

| 모델 | VRAM | 가능 여부 | 예상 속도 |
|------|------|----------|----------|
| Whisper small | ~2-3GB | ✅ 가능 | 0.6초/10초 오디오 |
| Whisper medium | ~5GB | ⚠️ 빠듯함 | - |
| SeamlessM4T Medium | ~4-5GB | ⚠️ 빠듯함 | 느림 |
| SeamlessM4T Large | ~8-10GB | ❌ 불가 | - |
| SeamlessStreaming | ~6-8GB | ❌ 불가 | - |

---

## Phase 10: Whisper GPU + Gemini Text API ❌ 보류

### 보류 사유 (2026-01-23 토론 결과)

| 문제점 | 상세 |
|--------|------|
| **지연 더 길어짐** | Local Agreement로 5~7초 지연 (현재 1~3초보다 느림) |
| **음성 출력 상실** | TTS 별도 구현 필요 → 복잡성 증가 |
| **복잡성 2배** | 서버 2개 관리, 장애 포인트 4개 |
| **실질적 개선 없음** | 노력 대비 이점 불분명 |

### 아키텍트 진단

> **현재 문제는 아키텍처가 아닌 구현 버그입니다.**
>
> Gemini S2ST의 자막 표시 버그(콜백 전달 이슈)만 수정하면 1~3초 지연으로 동작합니다.

### 기존 계획 (참고용)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  [마이크] → [WebSocket] → [Linux 서버]                                   │
│                               │                                         │
│                               ▼                                         │
│                    ┌─────────────────────┐                              │
│                    │ Windows PC          │                              │
│                    │ GTX 1660 Ti         │                              │
│                    │ Whisper GPU 서버     │                              │
│                    │ (192.168.x.20:8001) │                              │
│                    └─────────────────────┘                              │
│                               │                                         │
│                               ▼ (텍스트)                                 │
│                    ┌─────────────────────┐                              │
│                    │ Gemini Text API     │ → 번역 텍스트                 │
│                    └─────────────────────┘                              │
│                               │                                         │
│                               ▼                                         │
│                    [실시간 자막 표시]                                     │
│                    - 원본: "안녕하세요"                                   │
│                    - 번역: "こんにちは"                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 구현 계획

| 단계 | 작업 | 예상 시간 |
|------|------|----------|
| 1 | Windows PC에 Whisper GPU 서버 구축 | - |
| 2 | HTTP API 엔드포인트 생성 (`/transcribe`) | - |
| 3 | Linux 서버에서 Whisper API 호출 연동 | - |
| 4 | Gemini Text API 번역 연동 | - |
| 5 | 프론트엔드 실시간 자막 UI 개선 | - |
| 6 | 통합 테스트 | - |

### 예상 성능

| 구간 | 지연 |
|------|------|
| 음성 → Whisper STT | ~0.6초 |
| 텍스트 → Gemini 번역 | ~0.3초 |
| **총 지연** | **~1초** |

### 환경 설정

**Windows PC (Whisper 서버):**
```bash
# Python 환경
pip install faster-whisper flask

# 서버 실행
python whisper_server.py --port 8001 --model small --device cuda
```

**Linux 서버 (.env):**
```bash
USE_WHISPER_GPU=true
WHISPER_GPU_URL=http://192.168.x.20:8001
GEMINI_TEXT_API_KEY=your_key_here
```

### 롤백 계획

문제 발생 시 현재 Gemini S2ST로 롤백:
```bash
# backend/.env
USE_WHISPER_GPU=false
USE_GEMINI_S2ST=true
```

---

## Phase 11: Google 동시통역 API 전환 ⏸️ 대기 중

### 프로젝트 상태: 🔴 보류

> **2026년 Google Gemini API 동시통역 기능 출시까지 개발 보류**

### Google 공식 발표

| 항목 | 내용 |
|------|------|
| **발표일** | 2025년 12월 12일 |
| **현재 상태** | Google Translate 앱 베타 (Android US/Mexico/India) |
| **API 출시** | **2026년 (구체적 날짜 미정)** |

> "Based on feedback, Google will continue to iterate on this experience and **bring it to more Google products including the Gemini API in 2026**."

### 예상 타임라인

| 시점 | 가능성 | 근거 |
|------|--------|------|
| 2026년 상반기 | 낮음 | 아직 앱 베타 단계 |
| **2026년 5월 (Google I/O)** | **중간** | 발표 가능성 높음 |
| 2026년 하반기 | 높음 | 앱 안정화 후 API 공개 패턴 |

### 전환 계획 (API 출시 시)

```
[현재] Gemini S2ST (턴 기반, 1~3초 지연)
    ↓
[API 출시 후] Google 동시통역 API (실시간 음성+텍스트)
```

### 전환 시 이점

| 항목 | 현재 (턴 기반) | Google 동시통역 API |
|------|---------------|---------------------|
| 지연 시간 | 1~3초 | ~2초 (동시) |
| 실시간 텍스트 | ❌ 턴 끝나야 | ✅ 말하는 중 표시 |
| 실시간 음성 | ❌ 턴 끝나야 | ✅ 말하는 중 출력 |
| 복잡성 | 낮음 | 낮음 (클라우드) |

### 모니터링 체크리스트

**정기 확인 (월 1회):**
- [ ] [Gemini API Release Notes](https://ai.google.dev/gemini-api/docs/changelog)
- [ ] [Google AI Blog](https://blog.google/technology/ai/)
- [ ] [Vertex AI Release Notes](https://cloud.google.com/vertex-ai/generative-ai/docs/release-notes)

**키워드 모니터링:**
- "simultaneous translation"
- "continuous listening"
- "live speech translation API"
- "streaming translation"

**이벤트 확인:**
- [ ] Google I/O 2026 (예상: 5월)
- [ ] Google Cloud Next 2026

---

## 프로젝트 현황 요약 (2026-01-23)

### 상태: 🔴 개발 보류

| 단계 | 상태 | 비고 |
|------|------|------|
| Phase 1-6 | ✅ 완료 | 기본 구조 |
| Phase 7 | ✅ 완료 | Whisper + LibreTranslate |
| Phase 8 | ⚠️ 버그 있음 | Gemini S2ST (자막 미표시) |
| Phase 9 | ✅ 완료 | 기술 분석 |
| Phase 10 | ❌ 보류 | Whisper GPU (비효율적) |
| **Phase 11** | **⏸️ 대기** | **Google API 출시 대기** |

### 현재 사용 가능한 기능

| 기능 | 상태 | 지연 |
|------|------|------|
| 음성 → 번역된 음성 | ✅ 동작 | 1~3초 (턴 기반) |
| 음성 → 번역된 텍스트 | ⚠️ 버그 | 콜백 전달 이슈 |
| 실시간 동시통역 | ❌ 미지원 | API 한계 |

### 재개 조건

1. **Google Gemini API 동시통역 기능 출시**
2. 또는 다른 동시통역 API 등장 (Microsoft, AWS 등)

### 다음 액션

- 월 1회 Google API 릴리스 노트 확인
- Google I/O 2026 주시
- API 출시 시 즉시 테스트 및 전환

---

## 참고 링크

### Google 동시통역 관련
- [Google Translate Gemini Live Translation](https://9to5google.com/2025/12/12/google-translate-gemini-headphones/)
- [Gemini 2.5 Native Audio Updates](https://blog.google/products/gemini/gemini-audio-model-updates/)
- [Gemini API Release Notes](https://ai.google.dev/gemini-api/docs/changelog)

### Meta SeamlessStreaming (참고)
- [SeamlessM4T - Hugging Face](https://huggingface.co/facebook/seamless-m4t-v2-large)
- [Seamless GitHub](https://github.com/facebookresearch/seamless_communication)
- [SeamlessStreaming - Hugging Face](https://huggingface.co/facebook/seamless-streaming)

---

*Last Updated: 2026-01-23*
*Status: 🔴 개발 보류 - Google API 동시통역 기능 출시 대기*
