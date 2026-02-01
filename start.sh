#!/bin/bash

# Speech Translator 서버 시작 스크립트

PROJECT_DIR="/home/pgchae/바탕화면/speetch-translator"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

echo "=== Speech Translator 서버 시작 ==="

# 기존 프로세스 종료
echo "[1/4] 기존 프로세스 정리..."
pkill -f "uvicorn app.main:app" 2>/dev/null
pkill -f "libretranslate" 2>/dev/null
pkill -f "next dev" 2>/dev/null
sleep 2

# Backend 시작
echo "[2/4] Backend 시작 (port 8000)..."
cd "$BACKEND_DIR"
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1 &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID"

# LibreTranslate 시작
echo "[3/4] LibreTranslate 시작 (port 5000)..."
libretranslate --load-only ko,ja,en --port 5000 > /tmp/libretranslate.log 2>&1 &
LIBRE_PID=$!
echo "  LibreTranslate PID: $LIBRE_PID"

# Frontend 시작
echo "[4/4] Frontend 시작 (port 3000)..."
cd "$FRONTEND_DIR"
npm run dev > /tmp/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "  Frontend PID: $FRONTEND_PID"

# 서버 준비 대기
echo ""
echo "서버 시작 대기 중..."
sleep 10

# 상태 확인
echo ""
echo "=== 서버 상태 ==="
curl -s http://localhost:8000/health > /dev/null && echo "✅ Backend:       http://localhost:8000" || echo "❌ Backend: 시작 실패"
curl -s http://localhost:3000 > /dev/null && echo "✅ Frontend:      http://localhost:3000" || echo "❌ Frontend: 시작 실패"
curl -s http://localhost:5000/languages > /dev/null && echo "✅ LibreTranslate: http://localhost:5000" || echo "⏳ LibreTranslate: 모델 로딩 중..."

echo ""
echo "=== 로그 확인 ==="
echo "Backend:       tail -f /tmp/backend.log"
echo "Frontend:      tail -f /tmp/frontend.log"
echo "LibreTranslate: tail -f /tmp/libretranslate.log"
echo ""
echo "종료: ./stop.sh"
