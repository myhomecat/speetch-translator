FROM python:3.12-slim
WORKDIR /app

# 의존성 먼저 (캐시 활용)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 앱 소스
COPY app ./app
RUN mkdir -p /app/chat-log

EXPOSE 8000
ENV CHAT_LOG_DIR=/app/chat-log
# Soniox 모드 — Whisper 모델 로드 안 함 (1GB에서도 가벼움)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
