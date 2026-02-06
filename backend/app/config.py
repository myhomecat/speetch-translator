from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Gemini API
    gemini_api_key: str

    # Vertex AI API Key (S2ST용)
    vertex_ai_api_key: str = ""

    # AssemblyAI API (실시간 자막용)
    assemblyai_api_key: str = ""

    # Soniox API (실시간 STT + 번역)
    soniox_api_key: str = ""

    # CORS
    allowed_origins: str = "http://localhost:3000,http://192.168.0.113:3000,http://58.227.107.5:10112,http://58.227.107.5:3000,*"

    # Room settings
    max_users_per_room: int = 3

    # Audio settings
    input_sample_rate: int = 16000  # Client -> Server
    output_sample_rate: int = 24000  # Server -> Client (TTS)

    # Gemini model (bidiGenerateContent supported, Free tier)
    gemini_model: str = "gemini-2.5-flash-native-audio-preview-12-2025"

    # Gemini Live API (Native Audio with Translation)
    use_gemini_s2st: bool = False  # False: Soniox + TTS, True: Gemini Live API
    gemini_s2st_model: str = "gemini-live-2.5-flash-native-audio"

    # Soniox 설정
    use_soniox: bool = True  # True: Soniox + TTS, False: Gemini
    soniox_model: str = "stt-rt-v4"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
