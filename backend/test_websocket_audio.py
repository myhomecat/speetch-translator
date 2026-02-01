"""WebSocket을 통한 오디오 파일 테스트"""
import asyncio
import json
import subprocess
import tempfile
import os
from websockets.asyncio.client import connect

BACKEND_WS_URL = "ws://localhost:10113/ws/test-room"

async def test_with_audio_file(audio_path: str):
    print(f"[TEST] Testing with: {audio_path}")

    # m4a를 PCM으로 변환
    print("[TEST] Converting to PCM...")
    with tempfile.NamedTemporaryFile(suffix='.pcm', delete=False) as tmp:
        pcm_path = tmp.name

    try:
        cmd = [
            'ffmpeg', '-y', '-i', audio_path,
            '-ar', '16000', '-ac', '1', '-f', 's16le',
            pcm_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[TEST] FFmpeg error: {result.stderr}")
            return

        with open(pcm_path, 'rb') as f:
            pcm_data = f.read()
        print(f"[TEST] PCM data size: {len(pcm_data)} bytes")

        # WebSocket 연결
        print(f"[TEST] Connecting to {BACKEND_WS_URL}...")
        ws = await connect(BACKEND_WS_URL)
        print("[TEST] Connected!")

        # Join 메시지 전송
        join_msg = {
            "type": "join",
            "user_name": "TestUser",
            "translation_mode": "ko_to_ja"
        }
        await ws.send(json.dumps(join_msg))
        print("[TEST] Join message sent")

        # 응답 수신 태스크
        async def receive_messages():
            try:
                async for message in ws:
                    if isinstance(message, bytes):
                        print(f"[TEST] Received AUDIO: {len(message)} bytes")
                    else:
                        data = json.loads(message)
                        msg_type = data.get("type", "unknown")

                        if msg_type == "room_info":
                            print(f"[TEST] Joined room as user: {data.get('user_id')}")
                        elif msg_type == "realtime_transcript":
                            text = data.get("text", "")
                            translated = data.get("translated_text", "")
                            is_final = data.get("is_final", False)
                            status = "[FINAL]" if is_final else "[partial]"
                            if text or translated:
                                print(f"  {status} 원문: '{text}' → 번역: '{translated}'")
                        elif msg_type == "transcript":
                            print(f"[TEST] TRANSCRIPT: {data.get('original_text')} → {data.get('translated_text')}")
                        elif msg_type == "error":
                            print(f"[TEST] ERROR: {data.get('message')}")
                        elif msg_type == "pong":
                            pass  # ping/pong 무시
                        else:
                            print(f"[TEST] Message: {msg_type}")
            except Exception as e:
                if "closed" not in str(e).lower():
                    print(f"[TEST] Receive error: {e}")

        receive_task = asyncio.create_task(receive_messages())

        # 잠시 대기 (room_info 수신)
        await asyncio.sleep(1)

        # 오디오 청크로 전송 (3840 bytes = 120ms)
        chunk_size = 3840
        total_chunks = len(pcm_data) // chunk_size
        print(f"[TEST] Sending {total_chunks} audio chunks...")

        for i in range(0, len(pcm_data), chunk_size):
            chunk = pcm_data[i:i+chunk_size]
            await ws.send(chunk)
            await asyncio.sleep(0.12)  # 120ms 간격

            if (i // chunk_size) % 100 == 0:
                print(f"[TEST] Progress: {i // chunk_size}/{total_chunks}")

        print("[TEST] All audio sent!")

        # end_audio_stream 신호 전송
        await ws.send(json.dumps({"type": "end_audio_stream"}))
        print("[TEST] End audio stream signal sent")

        # 결과 대기
        print("[TEST] Waiting for results...")
        await asyncio.sleep(5)

        receive_task.cancel()
        try:
            await receive_task
        except asyncio.CancelledError:
            pass

        await ws.close()
        print("\n[TEST] DONE!")

    finally:
        if os.path.exists(pcm_path):
            os.remove(pcm_path)

if __name__ == "__main__":
    import sys
    audio_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/test_audio.m4a"
    asyncio.run(test_with_audio_file(audio_path))
