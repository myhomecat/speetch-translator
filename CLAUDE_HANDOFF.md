# Claude 세션 핸드오프 문서

**마지막 업데이트**: 2026-01-19 23:45

---

## 프로젝트 개요

실시간 한국어-일본어 음성 번역 채팅방

**현재 아키텍처** (Gemini Native Audio 사용):
```
[사용자 음성] → [Gemini Live API] → [번역 음성 + 번역 텍스트]
     ↓              (실시간)              ↓
[마이크 캡처]                      [자막 UI 표시]
```

## 현재 상태 요약 (2026-01-19)

| 구성요소 | 상태 | 비고 |
|---------|------|------|
| WebSocket 통신 | ✅ 완료 | Binary/JSON 멀티플렉싱, keepalive ping/pong |
| Gemini Native Audio | ✅ 정상 작동 | 실시간 번역 동작 확인 |
| VAD (음성 감지) | ✅ 작동 | 볼륨 기반 AnalyserNode 사용 |
| 자막 UI 표시 | ✅ 완료 | 실시간 + 영구 저장 모두 동작 |
| 오디오 파일 업로드 | ✅ 작동 | WAV/MP3/OGG 지원 (m4a 미지원) |

## 해결된 이슈 (2026-01-19)

### 1. 오디오 파일 업로드 버튼 문제 ✅
- **문제**: 숨겨진 `<input type="file">` 클릭이 안 됨
- **해결**: label-wrapped transparent input 방식으로 변경
- **파일**: `frontend/src/components/AudioFileUpload.tsx`

### 2. WebSocket 연결 끊김 문제 ✅
- **문제**: Gemini 처리 중 keepalive ping timeout
- **해결**:
  - 20초 간격 keepalive ping/pong 메커니즘 추가
  - callback refs로 재연결 루프 방지
  - React StrictMode 비활성화
- **파일**:
  - `frontend/src/hooks/useWebSocket.ts`
  - `backend/app/api/websocket.py`
  - `frontend/next.config.ts`

### 3. 번역 내용 미저장 문제 ✅
- **문제**: 번역이 표시되었다가 사라지고 채팅 기록에 안 남음
- **원인**: `realtime_transcript`만 전송, `transcript`(영구 저장용) 미전송
- **해결**: `is_final=true`일 때 `TranscriptMessage`도 함께 전송
- **파일**: `backend/app/api/websocket.py`

### 4. m4a 파일 오류 ✅
- **문제**: 브라우저에서 m4a 파일 디코딩 실패
- **해결**: 사용자 친화적 오류 메시지 추가
- **파일**: `frontend/src/components/AudioFileUpload.tsx`

## Gemini Live API 동작 원리

```
사용자: "안녕하세요" [잠시 멈춤]
        ↓
Gemini: "こんにちは" (번역 출력)
        ↓
사용자: "오늘 날씨 좋네요" [잠시 멈춤]
        ↓
Gemini: "今日は天気がいいですね" (번역 출력)
```

- **Turn 기반**: 사용자가 말하고 멈추면 번역 응답
- **짧은 문장 단위 번역**: 이것이 정상 동작 (실시간 통역 목적)
- **input_transcription**: 원본 텍스트 (turn_complete 시점에만 제공)
- **output_transcription**: 번역된 텍스트 (실시간 제공)

## 서버 실행 방법

```bash
# Backend
cd /home/pgchae/바탕화면/speetch-translator/backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 10113 > /tmp/backend.log 2>&1 &

# Frontend
cd /home/pgchae/바탕화면/speetch-translator/frontend
npm run dev

# 로그 확인
tail -f /tmp/backend.log
```

## 환경 변수

### Backend (.env)
```
USE_GEMINI_S2ST=true
GEMINI_S2ST_MODEL=gemini-live-2.5-flash-native-audio
ALLOWED_ORIGINS=*
```

### Frontend (.env.local)
```
NEXT_PUBLIC_WS_URL=ws://192.168.0.113:10113
NEXT_PUBLIC_API_URL=http://192.168.0.113:10113
```

## 수정된 파일 목록

| 파일 | 수정 내용 |
|------|----------|
| `frontend/src/components/AudioFileUpload.tsx` | label-wrapped input, m4a 오류 메시지 |
| `frontend/src/hooks/useWebSocket.ts` | keepalive ping, callback refs |
| `frontend/src/components/TranslatorRoom.tsx` | useEffect 의존성 수정, 타임아웃 10초 |
| `frontend/next.config.ts` | reactStrictMode: false |
| `backend/app/api/websocket.py` | ping/pong 핸들러, TranscriptMessage 전송 |

## 주요 파일 위치

| 파일 | 역할 |
|------|------|
| `backend/app/api/websocket.py` | WebSocket 핸들러, 콜백 처리 |
| `backend/app/core/gemini_s2st_session.py` | Gemini S2ST 세션 관리 |
| `frontend/src/hooks/useWebSocket.ts` | 프론트엔드 WebSocket 처리 |
| `frontend/src/hooks/useAudioCapture.ts` | 마이크 캡처 + 볼륨 VAD |
| `frontend/src/components/SubtitleDisplay.tsx` | 자막 UI |
| `frontend/src/components/TranslatorRoom.tsx` | 메인 채팅방 컴포넌트 |

## 테스트 방법

1. http://192.168.0.113:3000 접속
2. 이름 입력 후 방 생성
3. 마이크 버튼 클릭하여 말하기
4. 말을 멈추면 번역이 표시됨
5. 번역이 채팅 기록에 영구 저장되는지 확인

## 참고 사항

- **파일 업로드**: 긴 오디오 파일은 침묵 구간에서 Turn이 끊겨 짧은 조각만 인식됨 (Gemini Live API 특성)
- **내부망 접속**: Hairpin NAT 문제로 내부 IP(192.168.0.113) 사용 권장

---

*Last Updated: 2026-01-19 23:45*
