# 실시간 자막 + 번역 기능

## 변경 배경

### 기존 문제점
기존 Gemini Live API는 **턴제(Turn-based)** 방식으로 동작합니다:
1. 사용자가 말을 완전히 끝냄
2. Gemini가 전체 발화를 분석
3. 번역된 음성과 텍스트 반환

이로 인해 **1-3초의 지연**이 발생하고, 사용자는 말하는 동안 아무런 피드백을 받지 못했습니다.

### 요구사항
- 말하는 **중간에도** 텍스트가 실시간으로 표시되어야 함
- 문장이 완료되면 **즉시 번역**이 표시되어야 함
- 2명이 **동시에 말해도** 각각의 자막이 표시되어야 함

---

## 구현 방법

### 아키텍처

```
[마이크 입력]
     │
     ├──→ [Gemini Live API] ──→ 번역된 음성 + 최종 자막 (1-3초 후)
     │
     └──→ [AssemblyAI Realtime] ──→ 실시간 텍스트 (100ms 단위)
                │
                ├── interim (말하는 중) ──→ 원본 텍스트만 표시
                │
                └── final (문장 완료) ──→ Gemini Text API ──→ 번역 표시
```

### 왜 이 방식인가?

| 방식 | 장점 | 단점 |
|------|------|------|
| interim마다 번역 | 완전한 실시간 | API 호출 폭발, 비용 급증, 순서 꼬임 |
| **final만 번역** | 비용 절약, 안정적 | 문장 완료까지 번역 없음 |
| 디바운싱 (300ms) | 절충안 | 구현 복잡 |

**final만 번역** 방식을 선택한 이유:
1. API 호출 수 최소화 (비용 절약)
2. 응답 순서 문제 없음
3. 구현 단순
4. 실제 체감 지연은 크지 않음 (문장 완료 후 ~500ms)

---

## 구현 상세

### Backend 변경

#### 1. 텍스트 번역기 추가
`backend/app/core/text_translator.py`

```python
class TextTranslator:
    """Gemini Text API를 사용한 빠른 텍스트 번역"""

    async def translate(self, text: str) -> tuple[str, str, str]:
        # Gemini 2.0 Flash 모델 사용 (빠른 응답)
        # 언어 자동 감지 + 번역
        return (translated_text, source_lang, target_lang)
```

#### 2. 메시지 타입 확장
`backend/app/models/messages.py`

```python
class RealtimeTranscriptMessage(BaseMessage):
    text: str
    is_final: bool
    translated_text: Optional[str] = None  # final일 때만
    source_language: Optional[str] = None
    target_language: Optional[str] = None
```

#### 3. WebSocket 핸들러 수정
`backend/app/api/websocket.py`

```python
async def on_realtime_transcript(text: str, is_final: bool):
    translated_text = None

    # final일 때만 번역 수행
    if is_final and text.strip():
        translated_text, source_lang, target_lang = await text_translator.translate(text)

    await broadcast(RealtimeTranscriptMessage(...))
```

### Frontend 변경

#### 1. 타입 확장
`frontend/src/types/index.ts`

```typescript
interface RealtimeTranscript {
  text: string;
  translatedText: string | null;
  sourceLanguage: string | null;
  targetLanguage: string | null;
  isFinal: boolean;
}
```

#### 2. UI 표시
`frontend/src/components/SubtitleDisplay.tsx`

- **말하는 중**: 점선 테두리, 원본 텍스트만, 커서 애니메이션
- **문장 완료**: 실선 테두리, 원본 + 번역, 3초 후 자동 제거

---

## 결과

### 타임라인 비교

#### Before (Gemini Live만)
```
0s      1s      2s      3s      4s
│       │       │       │       │
└── 말하기 ──┘   └── 대기 ──┘
                              └── 자막 표시
```

#### After (AssemblyAI + Gemini Text)
```
0s      1s      2s      3s      4s
│       │       │       │       │
└── 말하기 ──┘
    │
    └── 실시간 자막 (말하는 중)
            │
            └── 번역 표시 (~500ms 후)
```

### 지연 시간

| 단계 | 지연 |
|------|------|
| 음성 → 텍스트 (interim) | ~100ms |
| 음성 → 텍스트 (final) | ~500ms |
| 텍스트 → 번역 | ~300-500ms |
| **총 지연 (final + 번역)** | **~800ms-1s** |

### 비용 영향

| 항목 | 추가 비용 |
|------|----------|
| AssemblyAI | 무료 100시간/월 내 |
| Gemini Text API | 무료 티어 내 (분당 15회 제한) |

---

## 사용 방법

### 환경 변수 설정

```bash
# backend/.env
GEMINI_API_KEY=your_gemini_key      # 필수
ASSEMBLYAI_API_KEY=your_aai_key     # 선택 (없으면 실시간 자막 비활성화)
```

### API 키 발급

1. **Gemini API**: https://aistudio.google.com/
2. **AssemblyAI**: https://www.assemblyai.com/ (매월 100시간 무료)

---

## 제한사항

1. **AssemblyAI 무료 한도**: 월 100시간 (3명 동시 사용 시 33시간)
2. **Gemini Text API 한도**: 분당 15회 (무료 티어)
3. **언어 지원**: 한국어, 일본어만 (확장 가능)

---

## 향후 개선 가능

1. **디바운싱 적용**: interim에서도 300ms 간격으로 번역
2. **캐싱**: 동일 텍스트 번역 결과 캐싱
3. **로컬 번역**: MarianMT 등 오프라인 모델 사용
4. **스트리밍 번역**: Claude/GPT 스트리밍 응답 활용

---

*Created: 2026-01-07*
