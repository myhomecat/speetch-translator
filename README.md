# Speech Translator (실시간 음성 번역기)

실시간 한국어-일본어 음성 번역 웹 애플리케이션입니다. Soniox API를 사용하여 실시간 STT + 번역 자막을 제공하고, 원본 음성을 상대방에게 전달합니다.

**배포 URL**: https://www.pgchae.my

**GitHub**: https://github.com/myhomecat/speetch-translator

## 주요 기능

- **실시간 음성 전달**: 원본 음성을 상대방에게 그대로 전달
- **실시간 자막 (STT + 번역)**: Soniox API로 실시간 텍스트 인식 및 번역
- **다중 사용자 지원**: 최대 3명까지 동시 접속 가능한 채팅방
- **자막 표시**: 원본 텍스트와 번역된 텍스트 실시간 표시
- **번역 모드 선택**: 자동 감지 / 한→일 / 일→한 모드 선택
- **오디오 파일 업로드**: 마이크 없이 오디오 파일로 테스트 가능
- **HTTPS 지원**: Let's Encrypt SSL 인증서 적용

## 기술 스택

### Backend
- **Python 3.12+**
- **FastAPI**: 비동기 웹 프레임워크
- **WebSocket**: 실시간 양방향 통신
- **Soniox API**: 실시간 STT + 번역
- **Google Gemini API**: `google-genai` SDK (S2ST 모드용, 현재 미사용)
- **Pydantic**: 데이터 검증

### Frontend
- **Next.js 16**: React 프레임워크
- **React 19**: UI 라이브러리
- **TypeScript**: 타입 안전성
- **Tailwind CSS 4**: 스타일링
- **AudioWorklet API**: 오디오 캡처 및 처리

### Infrastructure
- **Nginx**: 리버스 프록시
- **Let's Encrypt**: SSL 인증서
- **도메인**: pgchae.my (가비아)

## 프로젝트 구조

```
speetch-translator/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── websocket.py      # WebSocket 엔드포인트
│   │   │   └── rooms.py          # 방 관리 REST API
│   │   ├── core/
│   │   │   ├── gemini_session.py # Gemini Live API 세션 관리
│   │   │   ├── room_manager.py   # 방 상태 관리
│   │   │   └── connection_manager.py # WebSocket 연결 관리
│   │   ├── models/
│   │   │   ├── room.py           # 방/사용자 모델
│   │   │   └── messages.py       # WebSocket 메시지 모델
│   │   ├── config.py             # 설정
│   │   └── main.py               # FastAPI 앱 엔트리포인트
│   ├── .env                      # 환경 변수
│   └── requirements.txt
│
└── frontend/
    ├── src/
    │   ├── app/
    │   │   ├── page.tsx          # 홈페이지 (방 생성/참가)
    │   │   └── room/[roomId]/page.tsx  # 채팅방 페이지
    │   ├── components/
    │   │   ├── TranslatorRoom.tsx    # 메인 번역 채팅방 컴포넌트
    │   │   ├── AudioControls.tsx     # 녹음 버튼
    │   │   ├── AudioFileUpload.tsx   # 오디오 파일 업로드
    │   │   ├── LanguageSelector.tsx  # 번역 모드 선택
    │   │   ├── SubtitleDisplay.tsx   # 자막 표시
    │   │   └── UserList.tsx          # 접속자 목록
    │   ├── hooks/
    │   │   ├── useWebSocket.ts       # WebSocket 연결 관리
    │   │   ├── useAudioCapture.ts    # 마이크 오디오 캡처
    │   │   └── useAudioPlayback.ts   # 번역된 오디오 재생
    │   ├── lib/
    │   │   └── constants.ts          # 상수 정의
    │   └── types/
    │       └── index.ts              # TypeScript 타입 정의
    ├── .env.local                    # 환경 변수
    └── package.json
```

## 설치 및 실행

### 사전 요구사항

- Python 3.12+
- Node.js 18+
- Google Gemini API 키 ([Google AI Studio](https://aistudio.google.com/)에서 발급)

### Backend 설정

```bash
cd backend

# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install fastapi uvicorn websockets google-genai pydantic python-dotenv

# 환경 변수 설정
cp .env.example .env
# .env 파일에서 GEMINI_API_KEY 설정

# 서버 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend 설정

```bash
cd frontend

# 의존성 설치
npm install

# 환경 변수 설정
# .env.local 파일 생성
echo "NEXT_PUBLIC_WS_URL=ws://localhost:8000" > .env.local
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" >> .env.local

# 개발 서버 실행
npm run dev
```

### 외부 접속 설정 (포트포워딩 시)

```bash
# backend/.env
GEMINI_API_KEY=your_api_key
ALLOWED_ORIGINS=http://localhost:3000,http://YOUR_EXTERNAL_IP:FRONTEND_PORT

# frontend/.env.local
NEXT_PUBLIC_WS_URL=ws://YOUR_EXTERNAL_IP:BACKEND_PORT
NEXT_PUBLIC_API_URL=http://YOUR_EXTERNAL_IP:BACKEND_PORT
```

## 환경 변수

### Backend (.env)

| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `GEMINI_API_KEY` | Google Gemini API 키 | (필수) |
| `ASSEMBLYAI_API_KEY` | AssemblyAI API 키 (실시간 자막용) | (선택) |
| `ALLOWED_ORIGINS` | CORS 허용 도메인 | `http://localhost:3000` |
| `MAX_USERS_PER_ROOM` | 방당 최대 사용자 수 | `3` |

> **참고**: `ASSEMBLYAI_API_KEY`가 설정되지 않으면 실시간 자막 기능이 비활성화되고, Gemini 번역만 동작합니다.

### Frontend (.env.local)

| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `NEXT_PUBLIC_WS_URL` | WebSocket 서버 URL | `ws://localhost:8000` |
| `NEXT_PUBLIC_API_URL` | REST API 서버 URL | `http://localhost:8000` |

## API 문서

### WebSocket 엔드포인트

**URL**: `ws://{host}/ws/{room_id}`

#### 클라이언트 → 서버 메시지

1. **join** (연결 후 첫 메시지)
```json
{
  "type": "join",
  "user_name": "사용자 이름",
  "translation_mode": "auto" | "ko_to_ja" | "ja_to_ko"
}
```

2. **mode_change** (번역 모드 변경)
```json
{
  "type": "mode_change",
  "translation_mode": "auto" | "ko_to_ja" | "ja_to_ko"
}
```

3. **reset_session** (Gemini 세션 초기화)
```json
{
  "type": "reset_session"
}
```

4. **오디오 데이터** (바이너리)
- PCM 포맷: 16kHz, 16-bit, mono
- WebSocket binary frame으로 전송

#### 서버 → 클라이언트 메시지

1. **room_info** (입장 성공)
```json
{
  "type": "room_info",
  "room_id": "abc123",
  "user_id": "user-uuid",
  "users": [{"id": "...", "name": "...", "translation_mode": "..."}]
}
```

2. **user_joined** (다른 사용자 입장)
```json
{
  "type": "user_joined",
  "user": {"id": "...", "name": "...", "translation_mode": "..."}
}
```

3. **user_left** (사용자 퇴장)
```json
{
  "type": "user_left",
  "user_id": "...",
  "user_name": "..."
}
```

4. **transcript** (번역 텍스트)
```json
{
  "type": "transcript",
  "user_id": "...",
  "user_name": "...",
  "original_text": "원본 텍스트",
  "original_language": "ko",
  "translated_text": "翻訳テキスト",
  "translated_language": "ja"
}
```

5. **error** (에러)
```json
{
  "type": "error",
  "message": "에러 메시지",
  "code": "ROOM_FULL"
}
```

6. **번역된 오디오** (바이너리)
- PCM 포맷: Gemini가 생성한 음성
- WebSocket binary frame으로 수신

### REST API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `/rooms` | 새 방 생성 |
| `GET` | `/rooms/{room_id}` | 방 정보 조회 |

## 오디오 처리 파이프라인

### 음성 번역 (Gemini Live API)
```
[마이크] → [AudioWorklet (48kHz→16kHz 다운샘플링)] → [WebSocket] → [Backend]
    ↓
[Gemini Live API] ← [PCM 16kHz mono]
    ↓
[번역된 음성 + 텍스트]
    ↓
[WebSocket] → [Frontend] → [AudioContext 재생]
```

### 실시간 자막 (AssemblyAI + Gemini Text)
```
[마이크] → [WebSocket] → [AssemblyAI Realtime STT]
                              │
                              ├── interim (말하는 중) → 원본 텍스트만 표시
                              │
                              └── final (문장 완료) → [Gemini Text API] → 번역 표시
```

> **자세한 내용**: [실시간 자막 구현 문서](docs/REALTIME_SUBTITLE.md)를 참조하세요.

## Gemini Live API 설정

현재 사용 중인 모델: `gemini-2.5-flash-native-audio-preview-12-2025`

### Voice Activity Detection (VAD) 설정

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

## 알려진 제한사항

1. **턴제 방식**: Gemini Live API는 턴제(Turn-based)로 동작하여 진정한 동시통역이 아님
   - 실시간 자막으로 보완 (AssemblyAI + Gemini Text API)
2. **HTTPS 요구사항**: 외부 네트워크에서 마이크 사용 시 HTTPS 필요 (localhost 제외)
3. **브라우저 지원**: Chrome 권장 (AudioWorklet API 지원)
4. **API 제한**:
   - Gemini: 무료 티어 사용 시 요청 제한 있음
   - AssemblyAI: 월 100시간 무료 (3명 동시 사용 시 ~33시간)

> **동시통역이 필요한 경우**: [대안 기술 비교 문서](docs/ALTERNATIVES.md)를 참조하세요.
> **실시간 자막 구현 상세**: [실시간 자막 문서](docs/REALTIME_SUBTITLE.md)를 참조하세요.

## 트러블슈팅

### 마이크가 작동하지 않는 경우
- HTTPS 환경인지 확인 (HTTP에서는 getUserMedia 사용 불가)
- 브라우저에서 마이크 권한 허용 확인
- Chrome 사용 권장

### WebSocket 연결이 끊기는 경우
- 네트워크 상태 확인
- Backend 서버 실행 중인지 확인
- CORS 설정 확인 (ALLOWED_ORIGINS)

### 번역이 되지 않는 경우
- Gemini API 키 확인
- Backend 로그에서 에러 메시지 확인
- 오디오 파일 업로드로 테스트

## 라이선스

MIT License
