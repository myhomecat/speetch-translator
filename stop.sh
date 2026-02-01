#!/bin/bash

# Speech Translator 서버 종료 스크립트
# 업데이트: 2026-02-01

FRONTEND_PORT=3000

echo "=== Speech Translator 서버 종료 ==="

echo "[1/2] Backend 종료..."
pkill -f "uvicorn app.main:app" 2>/dev/null && echo "  ✅ 종료됨" || echo "  - 실행 중 아님"

echo "[2/2] Frontend 종료..."
fuser -k $FRONTEND_PORT/tcp 2>/dev/null && echo "  ✅ 종료됨" || echo "  - 실행 중 아님"

echo ""
echo "모든 서버가 종료되었습니다."
