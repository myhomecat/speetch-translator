#!/bin/bash

# Speech Translator 서버 시작 스크립트
# 업데이트: 2026-02-01 (Soniox + HTTPS 배포)

PROJECT_DIR="/home/pgchae/바탕화면/speetch-translator"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

BACKEND_PORT=10113
FRONTEND_PORT=3000

echo "=== Speech Translator 서버 시작 ==="
echo "배포 URL: https://www.pgchae.my"
echo ""

# 기존 프로세스 종료
echo "[1/3] 기존 프로세스 정리..."
pkill -f "uvicorn app.main:app" 2>/dev/null
fuser -k $FRONTEND_PORT/tcp 2>/dev/null
sleep 2

# Backend 시작
echo "[2/3] Backend 시작 (port $BACKEND_PORT)..."
cd "$BACKEND_DIR"
source venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port $BACKEND_PORT > /tmp/backend.log 2>&1 &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID"

# Frontend 시작 (프로덕션 모드)
echo "[3/3] Frontend 시작 (port $FRONTEND_PORT)..."
cd "$FRONTEND_DIR"
nohup npm start > /tmp/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "  Frontend PID: $FRONTEND_PID"

# 서버 준비 대기
echo ""
echo "서버 시작 대기 중..."
sleep 5

# 상태 확인
echo ""
echo "=== 서버 상태 ==="
curl -s http://localhost:$BACKEND_PORT/health > /dev/null 2>&1 && echo "✅ Backend:  http://localhost:$BACKEND_PORT" || echo "❌ Backend: 시작 실패"
curl -s http://localhost:$FRONTEND_PORT > /dev/null 2>&1 && echo "✅ Frontend: http://localhost:$FRONTEND_PORT" || echo "❌ Frontend: 시작 실패"

echo ""
echo "=== 접속 URL ==="
echo "외부: https://www.pgchae.my"
echo "내부: http://192.168.0.113:$FRONTEND_PORT"

echo ""
echo "=== 로그 확인 ==="
echo "Backend:  tail -f /tmp/backend.log"
echo "Frontend: tail -f /tmp/frontend.log"
echo ""
echo "종료: ./stop.sh"
