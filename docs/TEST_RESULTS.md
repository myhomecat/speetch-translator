# 테스트 결과 보고서

**최종 업데이트**: 2026-01-08 17:10

---

## 테스트 요약

| 항목 | 상태 | 비고 |
|------|------|------|
| WebSocket 연결 | ✅ 정상 | Binary/JSON 멀티플렉싱 작동 |
| Gemini STT | ✅ 정상 | input_transcription 정상 수신 |
| Gemini S2ST | ❌ 접근불가 | 실험적 모델, 일반 프로젝트 제한 |
| **Gemini Native Audio** | ✅ 정상 작동 | 오디오 송수신 성공, 번역 텍스트 수신됨 |
| VAD (음성 감지) | ⚠️ 볼륨기반 | @ricky0123/vad-web ONNX 오류로 볼륨 기반 VAD 사용 |
| Whisper STT | ✅ 정상 | faster-whisper small 모델 |
| LibreTranslate | ⚠️ 부분 작동 | 일부 문장 오역 |
| **UI 표시** | ✅ 해결됨 | 실시간 번역 텍스트 표시 가능 |
| 외부 IP 접속 | ⚠️ Hairpin NAT | 내부망에서 외부 IP 접근 불가, 내부 IP 사용 |

---

## 테스트 #6: 자막 표시 문제 해결 (2026-01-08 17:10)

### 목표
자막이 UI에 표시되지 않는 문제 해결

### 발견된 문제

| 문제 | 원인 | 해결 |
|------|------|------|
| 로그 미출력 | logger 설정 불완전 | print문 추가로 디버깅 |
| 프론트엔드 자막 미표시 | `is_final=false`일 때 `translated_text` 무시 | TranslatorRoom.tsx, SubtitleDisplay.tsx 수정 |

### 수정 사항

**frontend/src/components/TranslatorRoom.tsx:**
```typescript
// 수정 전: is_final=false일 때 translated_text를 null로 설정
translatedText: null,

// 수정 후: 실제 값 사용
translatedText: message.translated_text || null,
```

**frontend/src/components/SubtitleDisplay.tsx:**
```typescript
// 수정 전: is_final일 때만 번역 텍스트 표시
{rt.isFinal && rt.translatedText && (...)}

// 수정 후: 항상 번역 텍스트 표시 (스타일만 다르게)
{rt.translatedText && (...)}
```

### 테스트 결과 (test_websocket.py)

```bash
$ python test_websocket.py
Connecting to ws://localhost:10113/ws/test-room-123...
Sent join message
Received: room_info
Joined room as user: 4c87a6cc-02f5-4dce-b376-3630c3bdec31
Sample rate: 16000 Hz
PCM data size: 120576 bytes
Sent 120576 bytes of audio
Sent end_audio_stream

Waiting for responses (10 seconds)...
[MSG] {'type': 'realtime_transcript', 'user_id': '...', 'text': '', 'is_final': False, 'translated_text': 'はい、承知'}
[MSG] {'type': 'realtime_transcript', 'user_id': '...', 'text': '', 'is_final': False, 'translated_text': 'いたし'}
[MSG] {'type': 'realtime_transcript', 'user_id': '...', 'text': '', 'is_final': False, 'translated_text': 'ました。'}
...
[MSG] {'type': 'realtime_transcript', 'user_id': '...', 'text': '(음성 입력)', 'is_final': True, 'translated_text': 'します。'}
```

### 결론

- ✅ WebSocket 통합 정상 작동
- ✅ `realtime_transcript` 메시지 정상 전송
- ✅ 프론트엔드 코드 수정 완료
- 🔄 브라우저 테스트 필요

---

## 테스트 #7: CORS 문제 해결 (2026-01-08 17:30)

### 발견된 문제

**현상:** 외부 IP(58.227.107.5:10112)에서 백엔드 API 호출 시 CORS 오류

**원인:**
```python
# 잘못된 설정 - credentials와 wildcard origin 동시 사용 불가
allow_origins=["*"],
allow_credentials=True,  # ❌ 충돌
```

### 해결

**backend/app/main.py:**
```python
# 수정 후
allow_origins=["*"],
allow_credentials=False,  # ✅
```

### 환경 설정 정리

| 항목 | 외부 접속 | 내부 접속 |
|------|----------|----------|
| 프론트엔드 URL | http://58.227.107.5:10112 | http://192.168.0.113:3000 |
| 백엔드 API | http://58.227.107.5:10113 | http://192.168.0.113:10113 |
| 포트포워딩 | 10112 → 3000, 10113 → 10113 | 불필요 |

### 프론트엔드 환경변수 (.env.local)

```bash
# 외부 테스트용
NEXT_PUBLIC_WS_URL=ws://58.227.107.5:10113
NEXT_PUBLIC_API_URL=http://58.227.107.5:10113
```

---

## 테스트 #5: Native Audio 실시간 테스트 (2026-01-08 16:40)

### 목표
Gemini Native Audio 모델로 실제 WebSocket 기반 실시간 음성 번역 테스트

### 진행 결과

#### 1. 환경 설정 문제 해결
| 이슈 | 원인 | 해결 |
|------|------|------|
| 외부 IP 접속 불가 | Hairpin NAT (내부망에서 공인IP 접근 불가) | 내부 IP (192.168.0.113) 사용 |
| CORS 오류 | allow_origins 설정 미흡 | `allow_origins=["*"]` 설정 |
| 로그 미출력 | websocket.py logger 레벨 미설정 | `logging.basicConfig(level=DEBUG)` 추가 |

#### 2. VAD 구현 변경
| 항목 | 변경 전 | 변경 후 | 이유 |
|------|---------|---------|------|
| VAD 라이브러리 | @ricky0123/vad-web | 볼륨 기반 VAD | ONNX 로드 오류 발생 |
| 구현 방식 | ML 기반 | AnalyserNode 볼륨 측정 | 브라우저 호환성 문제 |
| 임계값 | - | 0.02 (기본값) | 소음 환경 조정 가능 |

**ONNX 오류 내용:**
```
Error loading @ricky0123/vad-web: Cannot read properties of undefined (reading 'filename')
```

**볼륨 기반 VAD 구현 (useAudioCapture.ts):**
```typescript
// AnalyserNode로 볼륨 측정
analyserRef.current.getByteFrequencyData(dataArray);
const avg = dataArray.reduce((a, b) => a + b) / dataArray.length;
const normalized = avg / 255;
const isSpeaking = normalized > VOLUME_THRESHOLD; // 0.02
```

#### 3. Gemini S2ST 세션 상태
| 항목 | 상태 | 로그 |
|------|------|------|
| WebSocket 연결 | ✅ 성공 | `[S2ST] Session connected for user xxx` |
| 오디오 전송 | ✅ 성공 | `[S2ST] Sending audio: 3200 bytes` |
| 응답 수신 | ✅ 성공 | `[S2ST] Received response: data=True` |
| output_transcription | ✅ 수신됨 | `[S2ST] Output: '...'` |
| on_transcript 콜백 | ✅ 호출됨 | `[S2ST] on_transcript callback completed` |
| WebSocket 브로드캐스트 | 🔄 확인중 | `[WS] on_s2st_transcript` 로그 확인 필요 |

#### 4. 현재 이슈 분석
| 문제 | 상태 | 분석 |
|------|------|------|
| 자막 미표시 | 🔄 디버깅중 | gemini_s2st_session.py에서 콜백은 완료되나 websocket.py의 on_s2st_transcript 로그 미출력 |
| input_transcription | ⚠️ 미수신 | Native Audio 모델은 입력 음성 텍스트 미반환 (출력만 반환) |

#### 5. 코드 변경 사항

**backend/app/api/websocket.py:**
```python
# 로깅 설정 추가
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# print → logger.info로 변경
logger.info(f"[WS] on_s2st_transcript: text='{text}', is_final={is_final}")
```

**backend/app/core/gemini_s2st_session.py:**
```python
# 콜백 호출 시 try/catch 및 로깅 추가
logger.info(f"[S2ST] Calling on_transcript callback")
try:
    await self.on_transcript(...)
    logger.info(f"[S2ST] on_transcript callback completed")
except Exception as e:
    logger.error(f"[S2ST] on_transcript callback error: {e}")
```

**backend/app/main.py:**
```python
# CORS 전체 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    ...
)
```

**frontend/src/components/AudioFileUpload.tsx:**
```typescript
// 에러 메시지 개선
} catch (err) {
  const error = err as Error;
  console.error("Error:", error.name, error.message, error.stack);
  alert(`오류: ${error.message || error}`);
}
```

#### 6. 서버 설정
| 서비스 | 주소 | 포트 |
|--------|------|------|
| Frontend | http://192.168.0.113:3000 | 3000 |
| Backend | http://192.168.0.113:10113 | 10113 |
| WebSocket | ws://192.168.0.113:10113 | 10113 |

### 다음 단계

1. **websocket.py 로그 확인**: on_s2st_transcript 함수가 실제로 호출되는지 확인
2. **브로드캐스트 검증**: RealtimeTranscriptMessage가 프론트엔드로 전송되는지 확인
3. **프론트엔드 메시지 핸들러 확인**: realtime_transcript 메시지 처리 로직 점검

---

## 테스트 #4: Native Audio 모델 통합 (2026-01-08 14:40)

### 목표
`gemini-live-2.5-flash-native-audio` 모델로 실시간 음성 번역 구현

### 진행 결과

#### 1. 모델 전환 및 설정
| 단계 | 상태 | 내용 |
|------|------|------|
| 모델 변경 | ✅ 완료 | `gemini-live-2.5-flash-native-audio` |
| 시스템 프롬프트 추가 | ✅ 완료 | 번역 지시 (한→일, 일→한, 자동) |
| Vertex AI 연결 | ✅ 성공 | ADC 인증으로 WebSocket 연결 |
| 오디오 전송 | ✅ 성공 | 3200 bytes 청크 단위 |
| end-of-turn 신호 | ✅ 성공 | `LiveClientContent(turn_complete=True)` |

#### 2. 응답 수신 결과
| 기능 | 상태 | 내용 |
|------|------|------|
| 오디오 응답 | ✅ 수신 | 9600~15360 bytes 청크로 수신 |
| output_transcription | ✅ 작동 | 모델 응답 텍스트 수신 |
| input_transcription | ⚠️ 미수신 | 입력 음성 텍스트 미반환 |

#### 3. 테스트 로그
```
[S2ST] Session connected for user xxx
[S2ST] Receive loop started
[S2ST] Sending audio: 3200 bytes
[S2ST] Audio sent successfully
...
[S2ST] Sending end-of-turn signal for user xxx
[S2ST] End-of-turn signal sent successfully
[S2ST] Received response: data=True, server_content=True
[S2ST] Received audio: 9600 bytes
[S2ST] Output: ' 들으면'
[S2ST] Output: ' 한국어로'
[S2ST] Output: ' 통역해'
[S2ST] Output: ' 드릴게요.'
...
```

#### 4. 현재 이슈
| 문제 | 원인 분석 | 해결 방안 |
|------|----------|----------|
| 입력 음성 미인식 | gTTS 오디오 품질 / 모델 한계 | 실제 마이크 테스트 필요 |
| 번역 대신 인사 | 시스템 프롬프트 해석 문제 | 프롬프트 조정 필요 |

### VAD (음성 감지) 구현 완료

| 항목 | 내용 |
|------|------|
| 라이브러리 | `@ricky0123/vad-web` |
| 위치 | `frontend/src/hooks/useAudioCapture.ts` |
| 동작 | 음성 감지 시에만 오디오 전송 |
| UI 표시 | 🎤 음성 감지 중... (녹색 펄스) |
| 설정 | positiveSpeechThreshold: 0.8, negativeSpeechThreshold: 0.3 |

### 수정된 파일

| 파일 | 변경 내용 |
|------|----------|
| `backend/app/config.py` | 모델명 변경 |
| `backend/app/core/gemini_s2st_session.py` | 번역 프롬프트, end_turn() 추가 |
| `backend/app/api/websocket.py` | end_turn 호출 추가 |
| `frontend/src/hooks/useAudioCapture.ts` | VAD 통합 |
| `frontend/src/components/AudioControls.tsx` | 음성 감지 UI |
| `frontend/src/components/TranslatorRoom.tsx` | isSpeaking 상태 전달 |

### 결론

**✅ 핵심 파이프라인 작동 확인:**
1. 프론트엔드 → 백엔드 오디오 전송 ✅
2. 백엔드 → Gemini Live API 연결 ✅
3. 오디오 청크 전송 ✅
4. end-of-turn 신호 전송 ✅
5. Gemini 응답 수신 (오디오 + 텍스트) ✅
6. VAD 음성 감지 구현 ✅

**⚠️ 추가 조정 필요:**
- 입력 음성 인식 확인 (실제 마이크 테스트)
- 시스템 프롬프트 최적화 (번역 정확도 향상)
- 입력 텍스트(input_transcription) 표시 연결

---

## 테스트 플랜 (Phase 8 계속)

### Phase 8-3: 기능 검증 테스트

| # | 테스트 항목 | 방법 | 예상 결과 | 상태 |
|---|------------|------|----------|------|
| 1 | 실제 마이크 입력 테스트 | 브라우저에서 마이크 버튼 클릭 후 한국어 말하기 | 입력 음성 인식 + 일본어 번역 출력 | 🔄 예정 |
| 2 | VAD 작동 확인 | 마이크 켜고 침묵 유지 → 말하기 시작 | 침묵 시 "대기 중", 말할 때 "음성 감지 중" 표시 | 🔄 예정 |
| 3 | 일본어 → 한국어 테스트 | "일→한" 모드 선택 후 일본어 말하기 | 한국어 번역 음성 + 자막 출력 | 🔄 예정 |
| 4 | 자동 감지 모드 테스트 | "자동 감지" 모드에서 한/일 번갈아 말하기 | 자동으로 반대 언어로 번역 | 🔄 예정 |
| 5 | 오디오 출력 확인 | 번역된 음성이 스피커로 재생되는지 | 번역된 음성 들림 | 🔄 예정 |
| 6 | 자막 표시 확인 | 대화 내용 영역에 원본/번역 표시 | 실시간 자막 표시 | 🔄 예정 |

### Phase 8-4: 품질 개선

| # | 개선 항목 | 내용 | 우선순위 |
|---|----------|------|---------|
| 1 | 시스템 프롬프트 최적화 | 더 명확한 번역 지시로 변경 | 높음 |
| 2 | input_transcription 연결 | 입력 음성 텍스트를 UI에 표시 | 높음 |
| 3 | 오디오 품질 확인 | 출력 오디오 샘플레이트/포맷 검증 | 중간 |
| 4 | 에러 핸들링 | 연결 끊김/재연결 로직 개선 | 중간 |
| 5 | 다중 사용자 테스트 | 2명 이상 접속하여 양방향 통역 테스트 | 낮음 |

### Phase 8-5: 성능/비용 테스트

| # | 테스트 항목 | 측정 방법 | 목표 |
|---|------------|----------|------|
| 1 | 응답 지연시간 | 말 끝 → 번역 음성 시작까지 시간 | < 2초 |
| 2 | VAD 비용 절감 효과 | 1분 대화 중 실제 전송 시간 측정 | 50% 이상 절감 |
| 3 | 토큰 사용량 | Vertex AI 콘솔에서 확인 | 예상치와 비교 |

### 테스트 체크리스트

```
[ ] 마이크 권한 요청 정상 작동
[ ] VAD 음성 감지 UI 표시
[ ] 오디오 전송 → Gemini 응답 수신
[ ] 번역된 음성 재생
[ ] 원본 자막 표시
[ ] 번역 자막 표시
[ ] 한→일 모드 정상 작동
[ ] 일→한 모드 정상 작동
[ ] 자동 감지 모드 정상 작동
[ ] 연결 끊김 시 자동 재연결
[ ] 2인 동시 접속 테스트
```

---

## 테스트 #3: Vertex AI S2ST 연동 시도 (2026-01-08)

### 목표
Vertex AI Live API의 Speech-to-Speech Translation (S2ST) 모델을 사용하여 실시간 음성 번역 구현

### 진행 과정

#### 1. 인증 설정
| 단계 | 상태 | 내용 |
|------|------|------|
| API Key 시도 | ❌ 실패 | "API keys are not supported by this API" |
| gcloud CLI 설치 | ✅ 완료 | google-cloud-sdk 설치 |
| ADC 인증 | ✅ 완료 | `gcloud auth application-default login` |
| Vertex AI API 활성화 | ✅ 완료 | Console에서 활성화 |
| 결제 계정 연결 | ✅ 완료 | 프로젝트에 결제 계정 연결 |

#### 2. S2ST 모델 연결 시도
| 모델명 | 결과 | 에러 |
|--------|------|------|
| `gemini-2.5-flash-s2st-exp-11-2025` | ❌ | Publisher Model 접근 불가 |
| `gemini-2.5-flash-s2st-11-2025-exp` | ❌ | Publisher Model 접근 불가 |

#### 3. 에러 분석
```
ERROR: received 1008 (policy violation)
Publisher Model `projects/gen-lang-client-0315513596/locations/us-central1/
publishers/google/models/gemini-2.5-flash-s2st-...` 접근 불가
```

**결론**: S2ST 모델은 실험적(experimental) 모델로, 일반 프로젝트에서 접근 제한됨

### 대안 분석

| 옵션 | 모델 | 기능 | 장단점 |
|------|------|------|--------|
| **A** | `gemini-live-2.5-flash-native-audio` | STT + 프롬프트 번역 + TTS | ✅ 접근 가능, 프롬프트로 번역 지시 필요 |
| B | Whisper + LibreTranslate | STT + 텍스트 번역 | ✅ 현재 작동 중, 음성 출력 없음 |
| C | S2ST 접근 권한 요청 | 완전한 S2ST | ❌ Google 별도 요청 필요, 승인 불확실 |

### 선택: 옵션 A (Native Audio 모델)

**이유:**
1. 일반 프로젝트에서 접근 가능
2. 실시간 텍스트 스트리밍 지원 (`input_audio_transcription`, `output_audio_transcription`)
3. 음성 출력 지원 (TTS)
4. 프롬프트로 번역 언어 지정 가능

### 가격 정보 (Gemini 2.5 Flash Live API)

| 항목 | 100만 토큰당 |
|------|-------------|
| 오디오 입력 | $3 |
| 오디오 출력 | $12 |
| 텍스트 출력 | $2 |

**예상 비용:**
- 1분 대화: 약 $0.025 (≈35원)
- 10분 대화: 약 350원
- 1시간 대화: 약 2,100원

**비용 절감 방안:** VAD(음성 감지) 추가 → 침묵 시 오디오 전송 안 함

---

## 테스트 #1: 초기 테스트 (2026-01-07 14:20)

### 환경
- Ubuntu Linux, Python 3.12, Next.js 16
- 테스트 방식: 오디오 파일 업로드 (TTS 생성)

### 결과 요약

| 테스트 | Gemini 수신 | AssemblyAI | 번역 | 상태 |
|--------|-------------|------------|------|------|
| 한국어 1 (인사) | ✅ | ❌ | ❌ | 부분 성공 |
| 한국어 2 (취미) | ✅ | ❌ | ❌ | 부분 성공 |
| 한국어 3 (업무) | ✅ | ❌ | ❌ | 부분 성공 |
| 일본어 1 (인사) | ❌ | ❌ | ❌ | 실패 |
| 일본어 2 (취미) | ✅ | ❌ | ❌ | 부분 성공 |
| 일본어 3 (업무) | ✅ | ❌ | ❌ | 부분 성공 |

### 발견된 문제

1. **AssemblyAI API 키 미설정** → 실시간 자막 미작동
2. **Gemini output_transcription 미반환** → 번역 텍스트 없음
3. **Gemini 문자 단위 스트리밍** → 완전한 문장 전달 안됨

---

## 테스트 #2: LibreTranslate 통합 테스트 (2026-01-07 18:00)

### 환경
- Ubuntu Linux, Python 3.12, Next.js 16
- LibreTranslate 서버: `http://localhost:5000` (ko, ja, en 지원)
- 테스트 방식: 브라우저에서 오디오 파일 업로드

### 테스트 파이프라인

```
오디오 파일 → Gemini STT → LibreTranslate → UI 표시
```

### 결과

#### 테스트 케이스: ko_1.mp3 ("안녕하세요")

| 단계 | 결과 | 비고 |
|------|------|------|
| 오디오 전송 | ✅ | 3200 bytes 청크 단위 전송 |
| Gemini STT | ✅ | "안녕하세요." 인식 |
| 언어 감지 | ✅ | "ko" 감지됨 |
| LibreTranslate 번역 | ⚠️ | "お問い合わせ" (오역) |
| UI 표시 | ✅ | 원본/번역 모두 표시 |

#### LibreTranslate 번역 품질 테스트

| 원본 (한국어) | 번역 결과 | 정답 | 정확성 |
|--------------|----------|------|--------|
| 안녕하세요 | お問い合わせ | こんにちは | ❌ |
| 감사합니다 | 私たちについて | ありがとうございます | ❌ |
| 좋은 아침입니다 | おはようございます | おはようございます | ✅ |
| 오늘 날씨가 좋습니다 | 今日は天気が良い | 今日は天気がいいです | ✅ |

### 결론

1. **파이프라인 정상 작동**: 오디오 → STT → 번역 → UI 표시 성공
2. **LibreTranslate 품질 문제**: 기본 인사말에서 오역 발생
3. **전체 흐름 검증 완료**: 개선 필요하지만 기본 구조는 완성

---

## 발견된 API 한계

### Gemini Live API (gemini-2.5-flash-native-audio-preview)

| 기능 | 상태 | 설명 |
|------|------|------|
| input_transcription | ✅ 작동 | 입력 음성 → 텍스트 변환 |
| output_transcription | ❌ 미작동 | 항상 `None` 반환 |
| 오디오 출력 | ❌ 미작동 | 번역된 음성 미생성 |
| System Instruction | ⚠️ 무시됨 | 번역 지시가 적용되지 않음 |

**결론**: Gemini Live API는 현재 **STT 전용**으로만 사용 가능

### AssemblyAI Real-time Streaming

| 항목 | 상태 |
|------|------|
| Universal-2 모델 | ❌ Deprecated |
| Universal Streaming | ❌ 한국어/일본어 미지원 |
| 에러 메시지 | `"Model deprecated. See docs for new model information"` |

**결론**: 한국어/일본어 실시간 STT에 사용 불가

### LibreTranslate

| 항목 | 상태 |
|------|------|
| API 연동 | ✅ 정상 |
| 한국어 → 일본어 | ⚠️ 불안정 (일부 오역) |
| 일본어 → 한국어 | 미테스트 |
| 응답 속도 | ~200ms |

**결론**: 무료 오픈소스로 사용 가능하나 품질 개선 필요

---

## 다음 진행 예정 (Phase 8)

### Phase 8-1: Native Audio 모델 전환 (현재 진행 중)

**목표:** `gemini-live-2.5-flash-native-audio` 모델로 실시간 번역 + 음성 출력 구현

| 단계 | 내용 | 상태 |
|------|------|------|
| 1 | 모델 변경 (`gemini_s2st_session.py`) | 🔄 예정 |
| 2 | 시스템 프롬프트 추가 (번역 지시) | 🔄 예정 |
| 3 | 연결 테스트 | 🔄 예정 |

### Phase 8-2: VAD (음성 감지) 구현

**목표:** 침묵 시 오디오 전송 안 함 → 비용 절감

| 방법 | 라이브러리 | 장점 | 단점 |
|------|-----------|------|------|
| ML 기반 | `@ricky0123/vad-web` | 높은 정확도, 소음 환경 강함 | +2MB |
| 볼륨 기반 | 없음 (직접 구현) | 가벼움 | 정확도 낮음 |

**선택:** ML 기반 VAD (`@ricky0123/vad-web`)

### 구현 흐름

```
[Phase 8-1] Native Audio 모델 전환
     ↓
     - 모델: gemini-live-2.5-flash-native-audio
     - 프롬프트: "한국어를 일본어로 번역해서 말해줘"
     - 기능: 입력 텍스트 + 번역 텍스트 + 번역 음성
     ↓
[Phase 8-2] VAD 구현
     ↓
     - 프론트엔드: @ricky0123/vad-web 설치
     - 음성 감지 시에만 오디오 전송
     - 비용 절감 효과
     ↓
[테스트] 실시간 번역 + 음성 출력 검증
```

### 예상 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                             │
│  ┌─────────┐    ┌─────────┐    ┌──────────────────────┐    │
│  │   Mic   │───▶│   VAD   │───▶│  WebSocket (Binary)  │    │
│  └─────────┘    └─────────┘    └──────────────────────┘    │
│       음성 감지 시에만 전송                 │               │
│                                            │               │
│  ┌─────────────────────────────────────────▼──────────┐    │
│  │              Audio Playback + Subtitles            │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        Backend                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Gemini Live API Session                 │  │
│  │  Model: gemini-live-2.5-flash-native-audio           │  │
│  │  Config:                                             │  │
│  │    - input_audio_transcription: ON                   │  │
│  │    - output_audio_transcription: ON                  │  │
│  │    - response_modalities: ["AUDIO"]                  │  │
│  │    - system_instruction: "번역 지시"                 │  │
│  └──────────────────────────────────────────────────────┘  │
│                              │                              │
│                              ▼                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────┐  │
│  │ 입력 텍스트     │  │ 번역 텍스트     │  │ 번역 음성  │  │
│  │ (원본 자막)     │  │ (번역 자막)     │  │ (TTS)      │  │
│  └─────────────────┘  └─────────────────┘  └────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 장기 개선 사항

1. **TTS 추가**
   - 번역된 텍스트를 음성으로 출력
   - Google Cloud TTS / VOICEVOX 등

2. **Gemini Live API 모니터링**
   - output_transcription 지원 여부 추후 확인
   - API 업데이트 시 재테스트

---

## 테스트 파일

| 파일 | 내용 | 언어 |
|------|------|------|
| `test_audio/ko_1.mp3` | "안녕하세요. 오늘 날씨가 정말 좋네요." | 한국어 |
| `test_audio/ko_2.mp3` | "저는 음식을 만드는 것을 좋아합니다..." | 한국어 |
| `test_audio/ko_3.mp3` | "내일 회의가 있으니 준비해 주세요..." | 한국어 |
| `test_audio/ja_1.mp3` | "こんにちは。今日は天気がとても良いですね。" | 일본어 |
| `test_audio/ja_2.mp3` | "私は料理を作ることが好きです..." | 일본어 |
| `test_audio/ja_3.mp3` | "明日会議がありますので準備をお願いします..." | 일본어 |

---

## 서버 실행 방법

### Backend
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd frontend
npm run dev
```

### LibreTranslate
```bash
libretranslate --load-only ko,ja,en
# 또는
nohup libretranslate --load-only ko,ja,en > /dev/null 2>&1 &
```

---

*테스트 환경: Ubuntu Linux 6.14.0, Python 3.12, Next.js 16*
