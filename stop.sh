#!/bin/bash

# Speech Translator 서버 종료 스크립트

echo "=== Speech Translator 서버 종료 ==="

echo "[1/3] Backend 종료..."
pkill -f "uvicorn app.main:app" 2>/dev/null && echo "  ✅ 종료됨" || echo "  - 실행 중 아님"

echo "[2/3] LibreTranslate 종료..."
pkill -f "libretranslate" 2>/dev/null && echo "  ✅ 종료됨" || echo "  - 실행 중 아님"

echo "[3/3] Frontend 종료..."
pkill -f "next dev" 2>/dev/null && echo "  ✅ 종료됨" || echo "  - 실행 중 아님"

echo ""
echo "모든 서버가 종료되었습니다."
