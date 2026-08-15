"""로컬 STT 엔진 백엔드 E2E 테스트

실제 서버(uvicorn)를 로컬 STT 모드로 띄우고, WebSocket 클라이언트가
진짜 한국어/일본어 음성(PCM)을 스트리밍하여 자막·번역 메시지 수신까지 검증한다.
LibreTranslate는 API 형식이 동일한 로컬 스텁(:15005)으로 대체 (플럼빙 검증용).

사용법:
  python tests/e2e_ws_local.py <ko_wav> <ja_wav>
필요 환경변수는 스크립트가 직접 설정해 uvicorn을 서브프로세스로 띄운다.
"""
import asyncio
import json
import os
import subprocess
import sys
import threading
import time
import wave
from http.server import BaseHTTPRequestHandler, HTTPServer

import websockets

BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..")
PORT = 18113
LT_PORT = 15005

# 스텁 번역 사전 (실제 LibreTranslate 대신 플럼빙 검증)
CANNED = {
    "ko->ja": "(JA번역) ",
    "ja->ko": "(KO번역) ",
}


class LTStub(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/detect":
            q = body.get("q", "")
            # 히라가나/가타카나/한자 → ja, 한글 → ko
            lang = "ja" if any(
                "぀" <= ch <= "ヿ" or "一" <= ch <= "鿿" for ch in q
            ) else "ko"
            payload = [{"language": lang, "confidence": 99}]
        else:  # /translate
            src, tgt = body.get("source"), body.get("target")
            prefix = CANNED.get(f"{src}->{tgt}", "(번역) ")
            payload = {"translatedText": prefix + body.get("q", "")}
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def read_pcm(path: str) -> bytes:
    with wave.open(path) as w:
        assert w.getframerate() == 16000 and w.getnchannels() == 1
        return w.readframes(w.getnframes())


async def stream_and_collect(room: str, wav_path: str, label: str):
    """방에 접속해 음성 스트리밍 후 final transcript까지 수신"""
    pcm = read_pcm(wav_path)
    uri = f"ws://127.0.0.1:{PORT}/ws/{room}"
    messages = []

    async with websockets.connect(uri, max_size=None) as ws:
        await ws.send(json.dumps({"type": "join", "user_name": "tester",
                                  "translation_mode": "auto"}))

        async def receiver():
            try:
                while True:
                    raw = await ws.recv()
                    if isinstance(raw, bytes):
                        continue
                    msg = json.loads(raw)
                    messages.append(msg)
                    if msg.get("type") == "transcript":
                        return  # 최종 자막 수신 완료
            except websockets.ConnectionClosed:
                pass

        recv_task = asyncio.create_task(receiver())

        # 100ms 청크(3200바이트)로 4배속 스트리밍 (VAD는 샘플 기반이라 무관)
        CHUNK = 3200
        for i in range(0, len(pcm), CHUNK):
            await ws.send(pcm[i:i + CHUNK])
            await asyncio.sleep(0.025)
        # 침묵 1.2초 추가 → 서버 VAD 엔드포인트 트리거
        silence = b"\x00" * 3200
        for _ in range(12):
            await ws.send(silence)
            await asyncio.sleep(0.025)
        await ws.send(json.dumps({"type": "end_audio_stream"}))

        try:
            await asyncio.wait_for(recv_task, timeout=30)
        except asyncio.TimeoutError:
            recv_task.cancel()

    partials = [m for m in messages if m.get("type") == "realtime_transcript"
                and not m.get("is_final")]
    finals = [m for m in messages if m.get("type") == "transcript"]
    print(f"\n=== {label} ===")
    print(f"부분자막 수신: {len(partials)}건")
    if partials:
        print(f"  첫 부분자막: {partials[0].get('text', '')[:40]!r}")
        print(f"  마지막 부분자막: {partials[-1].get('text', '')[:60]!r}")
    for f in finals:
        print(f"  최종: [{f.get('original_language')}] {f.get('original_text')!r}")
        print(f"  번역: [{f.get('translated_language')}] {f.get('translated_text')!r}")
    return partials, finals


async def main(ko_wav: str, ja_wav: str):
    ok = True

    ko_partials, ko_finals = await stream_and_collect("e2e-ko", ko_wav, "한국어 E2E")
    assert ko_finals, "한국어 최종 자막 미수신"
    ko_final = ko_finals[0]
    assert ko_final["original_language"] == "ko", f"언어 오판별: {ko_final}"
    if "미팅" not in ko_final["original_text"]:
        print("  !! 경고: whisper 최종 자막에 '미팅' 미포함")
        ok = False
    assert ko_final["translated_text"], "번역 미수행"
    assert ko_final["translated_language"] == "ja"
    assert ko_partials, "한국어 부분자막 미수신 (sherpa 스트리밍 미동작)"

    ja_partials, ja_finals = await stream_and_collect("e2e-ja", ja_wav, "일본어 E2E")
    assert ja_finals, "일본어 최종 자막 미수신"
    ja_final = ja_finals[0]
    assert ja_final["original_language"] == "ja", f"언어 오판별: {ja_final}"
    if "納期" not in ja_final["original_text"]:
        print("  !! 경고: ja 최종 자막에 '納期' 미포함")
        ok = False
    assert ja_final["translated_text"], "번역 미수행"
    assert ja_final["translated_language"] == "ko"

    print("\n" + ("E2E 전체 통과" if ok else "E2E 통과 (품질 경고 있음)"))
    return ok


if __name__ == "__main__":
    ko_wav, ja_wav = sys.argv[1], sys.argv[2]

    # 1) LibreTranslate 스텁 기동
    stub = HTTPServer(("127.0.0.1", LT_PORT), LTStub)
    threading.Thread(target=stub.serve_forever, daemon=True).start()
    print(f"[E2E] LibreTranslate stub on :{LT_PORT}")

    # 2) 백엔드 서버 기동 (로컬 STT 모드)
    env = os.environ.copy()
    env.update({
        "STT_ENGINE": "local",
        "LIBRETRANSLATE_URL": f"http://127.0.0.1:{LT_PORT}",
        "CHAT_LOG_DIR": os.environ.get("TMPDIR", "/tmp"),
        "USE_SONIOX": "false",
        "USE_GEMINI_S2ST": "false",
        "LOCAL_STT_KO_MODEL_DIR": os.path.expanduser(
            "~/Models/stt/sherpa-onnx-streaming-zipformer-korean-2024-06-16"),
        "LOCAL_STT_JA_MODEL_DIR": os.path.expanduser(
            "~/Models/stt/sherpa-onnx-zipformer-ja-reazonspeech-2024-08-01"),
    })
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(PORT), "--log-level", "warning"],
        cwd=BACKEND_DIR, env=env,
    )
    try:
        # 모델 프리로드 대기 (health 폴링)
        import urllib.request
        for _ in range(120):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=1)
                break
            except Exception:
                time.sleep(1)
        else:
            raise RuntimeError("서버 기동 실패")
        print("[E2E] backend ready")

        ok = asyncio.run(main(ko_wav, ja_wav))
        sys.exit(0 if ok else 2)
    finally:
        server.terminate()
        server.wait(timeout=10)
        stub.shutdown()
