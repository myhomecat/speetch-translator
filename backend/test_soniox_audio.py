"""Soniox API 오디오 파일 테스트"""
import asyncio
import json
import subprocess
import tempfile
import os
from websockets.asyncio.client import connect

SONIOX_WS_URL = "wss://stt-rt.soniox.com/transcribe-websocket"
API_KEY = "c34927786ea86e86a6fc15af36e56f23c087da9c4edfdfb42878c969b0c1234c"

async def test_audio_file(audio_path: str):
    print(f"[TEST] Testing with: {audio_path}")

    # m4a를 PCM으로 변환 (ffmpeg 사용)
    print("[TEST] Converting to PCM...")
    with tempfile.NamedTemporaryFile(suffix='.pcm', delete=False) as tmp:
        pcm_path = tmp.name

    try:
        # ffmpeg로 변환: 16kHz, mono, 16-bit signed little-endian PCM
        cmd = [
            'ffmpeg', '-y', '-i', audio_path,
            '-ar', '16000',  # 16kHz
            '-ac', '1',       # mono
            '-f', 's16le',    # 16-bit signed little-endian
            pcm_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[TEST] FFmpeg error: {result.stderr}")
            return

        print(f"[TEST] PCM file created: {pcm_path}")

        # PCM 파일 읽기
        with open(pcm_path, 'rb') as f:
            pcm_data = f.read()
        print(f"[TEST] PCM data size: {len(pcm_data)} bytes")

        # Soniox 연결
        print("[TEST] Connecting to Soniox...")
        ws = await connect(SONIOX_WS_URL)
        print("[TEST] Connected!")

        # 설정 전송 (한국어 → 일본어 번역)
        config = {
            "api_key": API_KEY,
            "model": "stt-rt-v3",
            "audio_format": "s16le",
            "sample_rate": 16000,
            "num_channels": 1,
            "language_hints": ["ko"],
            "translation": {
                "type": "one_way",
                "target_language": "ja"
            },
            "enable_endpoint_detection": True,
        }

        print(f"[TEST] Sending config (ko -> ja translation)...")
        await ws.send(json.dumps(config))

        # 초기 응답 확인
        response = await asyncio.wait_for(ws.recv(), timeout=10)
        response_data = json.loads(response)
        print(f"[TEST] Initial response: {response_data}")

        if "error" in response_data:
            print(f"[TEST] ERROR: {response_data['error']}")
            await ws.close()
            return

        # 오디오 청크로 전송 (3840 bytes = 120ms at 16kHz mono 16-bit)
        chunk_size = 3840
        total_chunks = len(pcm_data) // chunk_size
        print(f"[TEST] Sending {total_chunks} audio chunks...")

        # 수신 태스크 시작
        results = []

        async def receive_results():
            try:
                async for message in ws:
                    print(f"[TEST] RAW MESSAGE: {message[:500] if len(str(message)) > 500 else message}")
                    data = json.loads(message)
                    results.append(data)

                    # 에러 체크
                    if "error" in data:
                        print(f"[TEST] SERVER ERROR: {data['error']}")

                    # 토큰 출력
                    if "tokens" in data and data["tokens"]:
                        for token in data["tokens"]:
                            text = token.get("text", "")
                            is_final = token.get("is_final", False)
                            translation = token.get("translation", "")
                            if text or translation:
                                status = "[FINAL]" if is_final else "[partial]"
                                print(f"  {status} 원문: '{text}' → 번역: '{translation}'")

                    # 세그먼트 끝
                    if data.get("segment_end"):
                        print("  [SEGMENT END]")

            except Exception as e:
                print(f"[TEST] Receive error: {e}")

        receive_task = asyncio.create_task(receive_results())

        # 오디오 전송
        for i in range(0, len(pcm_data), chunk_size):
            chunk = pcm_data[i:i+chunk_size]
            await ws.send(chunk)
            await asyncio.sleep(0.12)  # 120ms 간격 (실시간 시뮬레이션)

            if (i // chunk_size) % 50 == 0:
                print(f"[TEST] Sent {i // chunk_size}/{total_chunks} chunks...")

        print("[TEST] All audio sent, waiting for final results...")

        # 빈 프레임 전송 (스트림 종료)
        await ws.send(b"")

        # 결과 대기
        await asyncio.sleep(3)
        receive_task.cancel()

        try:
            await receive_task
        except asyncio.CancelledError:
            pass

        await ws.close()
        print("\n[TEST] DONE!")

        # 최종 결과 요약
        print("\n=== 결과 요약 ===")
        full_text = ""
        full_translation = ""
        for r in results:
            if "tokens" in r:
                for token in r["tokens"]:
                    if token.get("is_final"):
                        full_text += token.get("text", "")
                        full_translation += token.get("translation", "")

        print(f"원문: {full_text}")
        print(f"번역: {full_translation}")

    finally:
        # 임시 파일 삭제
        if os.path.exists(pcm_path):
            os.remove(pcm_path)

if __name__ == "__main__":
    import sys
    audio_path = sys.argv[1] if len(sys.argv) > 1 else "/home/pgchae/바탕화면/test/산나비1.m4a"
    asyncio.run(test_audio_file(audio_path))
