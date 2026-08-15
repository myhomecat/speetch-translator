import json
import logging
import traceback
import os
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

# 채팅 로그 저장 경로
CHAT_LOG_DIR = os.environ.get("CHAT_LOG_DIR", "/app/chat-log")

def save_chat_log(room_id: str, user_name: str, original_text: str, original_language: str,
                  translated_text: str, translated_language: str):
    """채팅 로그를 JSONL 파일에 저장 (한 줄씩 append - 성능 최적화)"""
    try:
        # 날짜별 파일명 (JSONL 형식)
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(CHAT_LOG_DIR, f"chat_{today}.jsonl")

        # 새 로그 항목
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "room_id": room_id,
            "user_name": user_name,
            "original_text": original_text,
            "original_language": original_language,
            "translated_text": translated_text,
            "translated_language": translated_language
        }

        # 파일 끝에 한 줄 추가 (append 모드)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

        print(f"[ChatLog] Saved: {user_name}: {original_text} -> {translated_text}")
    except Exception as e:
        print(f"[ChatLog] Error saving log: {e}")

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
from ..core.room_manager import room_manager
from ..core.connection_manager import connection_manager
from ..core.gemini_s2st_session import gemini_s2st_session_manager
from ..core.whisper_session import whisper_session_manager
from ..core.soniox_session import soniox_session_manager
from ..core.local_stt_session import local_stt_session_manager
from ..core.tts_session import tts_session_manager
from ..core.text_translator import text_translator
from ..models.room import TranslationMode
from ..models.messages import (
    MessageType,
    JoinMessage,
    RoomInfoMessage,
    UserInfo,
    UserJoinedMessage,
    UserLeftMessage,
    TranscriptMessage,
    RealtimeTranscriptMessage,
    ErrorMessage,
    AudioDataMessage,
)
from ..config import get_settings

router = APIRouter()
settings = get_settings()


@router.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    user_id = None
    user_name = None

    try:
        # Accept connection first
        await websocket.accept()

        # Wait for join message
        initial_data = await websocket.receive_text()
        join_data = json.loads(initial_data)

        if join_data.get("type") != MessageType.JOIN:
            await websocket.send_json(
                ErrorMessage(message="First message must be join").model_dump()
            )
            await websocket.close()
            return

        user_name = join_data.get("user_name", "Anonymous")
        mode_str = join_data.get("translation_mode", "auto")
        translation_mode = TranslationMode(mode_str)

        # Add user to room
        room, user, error = await room_manager.add_user_to_room(
            room_id=room_id,
            user_name=user_name,
            translation_mode=translation_mode
        )

        if error:
            await websocket.send_json(
                ErrorMessage(message=error, code="ROOM_FULL").model_dump()
            )
            await websocket.close()
            return

        user_id = user.id

        # Register connection (don't call accept again)
        if room_id not in connection_manager._connections:
            connection_manager._connections[room_id] = {}
        connection_manager._connections[room_id][user_id] = websocket

        # Send room info to the new user
        users_info = [
            UserInfo(id=u.id, name=u.name, translation_mode=u.translation_mode.value)
            for u in room.users.values()
        ]
        await websocket.send_json(
            RoomInfoMessage(
                room_id=room_id,
                user_id=user_id,
                users=users_info
            ).model_dump()
        )

        # Broadcast user joined to others
        await connection_manager.broadcast_json(
            room_id=room_id,
            message=UserJoinedMessage(
                user=UserInfo(id=user_id, name=user_name, translation_mode=mode_str)
            ),
            exclude_user_id=user_id
        )

        async def on_error(error_msg: str):
            await websocket.send_json(
                ErrorMessage(message=error_msg).model_dump()
            )

        # 세션 변수
        s2st_session = None
        whisper_session = None
        soniox_session = None
        tts_session = None
        local_session = None

        if settings.stt_engine == "local":
            # === 로컬 STT 모드 (sherpa-onnx + faster-whisper, 완전 오프라인) ===
            async def on_local_transcript(text: str, is_final: bool, language: str = None):
                """로컬 STT 자막 콜백 — final일 때 LibreTranslate로 번역"""
                translated_text = None
                target_lang = None

                if is_final and text.strip():
                    try:
                        translated_text, language, target_lang = await text_translator.translate(
                            text, source_lang=language or "auto"
                        )
                    except Exception as e:
                        print(f"[WS] Local translation error: {e}")

                await connection_manager.broadcast_json(
                    room_id=room_id,
                    message=RealtimeTranscriptMessage(
                        user_id=user_id,
                        user_name=user_name,
                        text=text,
                        is_final=is_final,
                        translated_text=translated_text,
                        source_language=language,
                        target_language=target_lang,
                    )
                )

                if is_final and text.strip():
                    await connection_manager.broadcast_json(
                        room_id=room_id,
                        message=TranscriptMessage(
                            user_id=user_id,
                            user_name=user_name,
                            original_text=text,
                            original_language=language or "auto",
                            translated_text=translated_text,
                            translated_language=target_lang,
                        )
                    )
                    save_chat_log(room_id, user_name, text, language or "auto",
                                 translated_text, target_lang)

            try:
                local_session = await local_stt_session_manager.create_session(
                    room_id=room_id,
                    user_id=user_id,
                    translation_mode=translation_mode,
                    on_transcript=on_local_transcript,
                    on_error=on_error,
                )
                print(f"[WS] Local STT session created for user {user_id}")
            except Exception as e:
                print(f"[WS] Local STT session error: {e}")
                traceback.print_exc()

        elif settings.use_soniox:
            # === Soniox 모드 (STT + 번역 자막, 원본 음성 전달) ===
            async def on_soniox_transcript(text: str, is_final: bool, translated_text: str = None, speaker: int = None):
                """Soniox 자막 콜백 - 실시간 텍스트 자막"""
                print(f"[WS] on_soniox_transcript: text='{text}', is_final={is_final}, translated='{translated_text}', speaker={speaker}")

                source_lang = "ko" if translation_mode == TranslationMode.KO_TO_JA else "ja"
                target_lang = "ja" if translation_mode == TranslationMode.KO_TO_JA else "ko"
                if translation_mode == TranslationMode.AUTO:
                    source_lang = "auto"
                    target_lang = "auto"

                try:
                    # 실시간 자막 메시지 브로드캐스트
                    msg = RealtimeTranscriptMessage(
                        user_id=user_id,
                        user_name=user_name,
                        text=text,
                        is_final=is_final,
                        translated_text=translated_text,
                        source_language=source_lang,
                        target_language=target_lang,
                        speaker=speaker
                    )
                    await connection_manager.broadcast_json(
                        room_id=room_id,
                        message=msg
                    )

                    # is_final이고 텍스트가 있으면 영구 저장용 transcript 메시지
                    if is_final and (text or translated_text):
                        transcript_msg = TranscriptMessage(
                            user_id=user_id,
                            user_name=user_name,
                            original_text=text or "(음성 입력)",
                            original_language=source_lang,
                            translated_text=translated_text,
                            translated_language=target_lang,
                            speaker=speaker
                        )
                        await connection_manager.broadcast_json(
                            room_id=room_id,
                            message=transcript_msg
                        )
                        # 채팅 로그 저장
                        save_chat_log(room_id, user_name, text or "(음성 입력)", source_lang,
                                     translated_text, target_lang)

                except Exception as e:
                    print(f"[WS] Soniox transcript error: {e}")
                    traceback.print_exc()

            try:
                # Soniox STT 세션 생성
                soniox_session = await soniox_session_manager.create_session(
                    room_id=room_id,
                    user_id=user_id,
                    translation_mode=translation_mode,
                    on_transcript=on_soniox_transcript,
                    on_error=on_error
                )
                print(f"[WS] Soniox session created for user {user_id}")

            except Exception as e:
                print(f"[WS] Soniox session error: {e}")
                traceback.print_exc()
                # Soniox 실패 시 Gemini로 폴백
                settings.use_soniox = False
                print(f"[WS] Falling back to Gemini S2ST")

        elif settings.use_gemini_s2st:
            # === Gemini S2ST 모드 ===
            async def on_s2st_audio(audio_bytes: bytes):
                """S2ST 번역 오디오 콜백 - 상대방에게 전송"""
                await connection_manager.broadcast_bytes(
                    room_id=room_id,
                    data=audio_bytes,
                    exclude_user_id=user_id  # 본인 제외
                )

            async def on_s2st_transcript(text: str, is_final: bool, translated_text: str = None):
                """S2ST 자막 콜백"""
                print(f"[WS] on_s2st_transcript CALLED: text='{text}', is_final={is_final}, translated='{translated_text}'")
                logger.info(f"[WS] on_s2st_transcript: text='{text}', is_final={is_final}, translated='{translated_text}'")
                source_lang = "ko" if translation_mode == TranslationMode.KO_TO_JA else "ja"
                target_lang = "ja" if translation_mode == TranslationMode.KO_TO_JA else "ko"
                if translation_mode == TranslationMode.AUTO:
                    source_lang = "auto"
                    target_lang = "auto"

                print(f"[WS] Broadcasting realtime_transcript to room {room_id}")
                logger.info(f"[WS] Broadcasting realtime_transcript to room {room_id}")
                try:
                    # 실시간 자막 메시지 (임시 표시용)
                    msg = RealtimeTranscriptMessage(
                        user_id=user_id,
                        user_name=user_name,
                        text=text,
                        is_final=is_final,
                        translated_text=translated_text,
                        source_language=source_lang,
                        target_language=target_lang
                    )
                    print(f"[WS] Message created: {msg.model_dump()}")
                    await connection_manager.broadcast_json(
                        room_id=room_id,
                        message=msg
                    )
                    print(f"[WS] Broadcast completed successfully")

                    # is_final이면 영구 저장용 transcript 메시지도 전송
                    if is_final and (text or translated_text):
                        transcript_msg = TranscriptMessage(
                            user_id=user_id,
                            user_name=user_name,
                            original_text=text or "(음성 입력)",
                            original_language=source_lang,
                            translated_text=translated_text,
                            translated_language=target_lang
                        )
                        await connection_manager.broadcast_json(
                            room_id=room_id,
                            message=transcript_msg
                        )
                        # 채팅 로그 저장
                        save_chat_log(room_id, user_name, text or "(음성 입력)", source_lang,
                                     translated_text, target_lang)
                        print(f"[WS] Transcript message sent for permanent storage")
                except Exception as e:
                    print(f"[WS] Broadcast error: {e}")
                    import traceback
                    traceback.print_exc()

            try:
                s2st_session = await gemini_s2st_session_manager.create_session(
                    room_id=room_id,
                    user_id=user_id,
                    translation_mode=translation_mode,
                    on_audio=on_s2st_audio,
                    on_transcript=on_s2st_transcript,
                    on_error=on_error
                )
                print(f"[WS] Gemini S2ST session created for user {user_id}")
            except Exception as e:
                print(f"[WS] S2ST session error: {e}")
                traceback.print_exc()
                # S2ST 실패 시 Whisper로 폴백
                settings.use_gemini_s2st = False
                print(f"[WS] Falling back to Whisper + LibreTranslate")

        if settings.stt_engine != "local" and soniox_session is None and s2st_session is None:
            # === Whisper + LibreTranslate 모드 (폴백) ===
            async def on_whisper_transcript(text: str, is_final: bool):
                """Whisper 실시간 자막 콜백"""
                translated_text = None
                source_lang = None
                target_lang = None

                # final일 때만 번역 수행
                if is_final and text.strip():
                    try:
                        translated_text, source_lang, target_lang = await text_translator.translate(text)
                        print(f"[WS] Whisper translation: {text} -> {translated_text}")
                    except Exception as e:
                        print(f"[WS] Whisper translation error: {e}")

                await connection_manager.broadcast_json(
                    room_id=room_id,
                    message=RealtimeTranscriptMessage(
                        user_id=user_id,
                        user_name=user_name,
                        text=text,
                        is_final=is_final,
                        translated_text=translated_text,
                        source_language=source_lang,
                        target_language=target_lang
                    )
                )

            try:
                whisper_session = await whisper_session_manager.create_session(
                    room_id=room_id,
                    user_id=user_id,
                    translation_mode=translation_mode,
                    on_transcript=on_whisper_transcript,
                    on_error=on_error
                )
                print(f"[WS] Whisper session created for user {user_id}")
            except Exception as e:
                print(f"Whisper session error (continuing without realtime STT): {e}")
                traceback.print_exc()

        # Main message loop
        while True:
            message = await websocket.receive()

            # Check for disconnect message
            if message["type"] == "websocket.disconnect":
                break

            if "bytes" in message:
                # Binary audio data
                audio_bytes = message["bytes"]

                # 로컬 STT 모드: 원본 음성 전달 + 로컬 STT
                if local_session and local_session.is_connected:
                    await connection_manager.broadcast_bytes(
                        room_id=room_id,
                        data=audio_bytes,
                        exclude_user_id=user_id
                    )
                    await local_session.send_audio(audio_bytes)
                # Soniox 모드: 원본 음성을 상대방에게 전달 + STT
                elif soniox_session and soniox_session.is_connected:
                    # 1. 원본 음성을 상대방에게 전달 (본인 제외)
                    await connection_manager.broadcast_bytes(
                        room_id=room_id,
                        data=audio_bytes,
                        exclude_user_id=user_id
                    )
                    # 2. Soniox로 STT + 번역 (자막용)
                    await soniox_session.send_audio(audio_bytes)
                elif s2st_session and s2st_session.is_connected:
                    await s2st_session.send_audio(audio_bytes)
                elif whisper_session and whisper_session.is_connected:
                    await whisper_session.send_audio(audio_bytes)

            elif "text" in message:
                # JSON control message
                data = json.loads(message["text"])
                msg_type = data.get("type")

                if msg_type == "ping":
                    # Respond with pong to keep connection alive
                    await websocket.send_json({"type": "pong"})
                    continue

                if msg_type == MessageType.MODE_CHANGE:
                    new_mode = TranslationMode(data.get("translation_mode", "auto"))
                    await room_manager.update_user_mode(room_id, user_id, new_mode)

                    # 언어 모드 변경
                    if local_session:
                        local_session.change_language(new_mode)
                    if soniox_session:
                        soniox_session.change_language(new_mode)
                    if tts_session:
                        tts_session.change_language(new_mode)
                    if s2st_session:
                        s2st_session.change_language(new_mode)
                    if whisper_session:
                        whisper_session.change_language(new_mode)
                    print(f"[WS] Mode changed to {new_mode} for user {user_id}")

                elif msg_type == "reset_session":
                    # Reset session for new recording turn
                    print(f"[WS] Resetting sessions for user {user_id}")

                    if local_session:
                        await local_session.reset()
                    if soniox_session:
                        await soniox_session.reset()
                    if s2st_session:
                        await s2st_session.reset()
                    if whisper_session:
                        await whisper_session.reset()

                    print(f"[WS] Sessions reset complete for user {user_id}")

                elif msg_type == "end_audio_stream":
                    print(f"[WS] End audio stream signal for user {user_id}")
                    # Send end-of-turn signal
                    if local_session:
                        await local_session.end_turn()
                    if soniox_session:
                        await soniox_session.end_turn()
                    if s2st_session:
                        await s2st_session.end_turn()

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")
        traceback.print_exc()
    finally:
        # Cleanup
        if user_id:
            # 세션 정리
            await local_stt_session_manager.remove_session(room_id, user_id)
            await soniox_session_manager.remove_session(room_id, user_id)
            await tts_session_manager.remove_session(room_id, user_id)
            await gemini_s2st_session_manager.remove_session(room_id, user_id)
            await whisper_session_manager.remove_session(room_id, user_id)
            await connection_manager.disconnect(room_id, user_id)
            room, removed_user = await room_manager.remove_user_from_room(room_id, user_id)

            # Broadcast user left
            if removed_user:
                await connection_manager.broadcast_json(
                    room_id=room_id,
                    message=UserLeftMessage(
                        user_id=user_id,
                        user_name=removed_user.name
                    )
                )
