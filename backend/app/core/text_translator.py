"""
LibreTranslate를 사용한 빠른 텍스트 번역
실시간 자막의 final result를 번역하기 위해 사용
"""
import httpx
from ..config import get_settings


class TextTranslator:
    """LibreTranslate를 사용한 텍스트 번역기"""

    def __init__(self):
        self._base_url = get_settings().libretranslate_url
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def detect_language(self, text: str) -> str:
        """언어 감지"""
        try:
            client = self._get_client()
            response = await client.post(
                f"{self._base_url}/detect",
                json={"q": text}
            )
            if response.status_code == 200:
                result = response.json()
                if result and len(result) > 0:
                    return result[0].get("language", "ko")
        except Exception as e:
            print(f"[TextTranslator] Language detection error: {e}")
        return "ko"

    async def translate(
        self,
        text: str,
        source_lang: str = "auto",
        target_lang: str = "auto"
    ) -> tuple[str, str, str]:
        """
        텍스트 번역

        Args:
            text: 번역할 텍스트
            source_lang: 원본 언어 ("ko", "ja", "auto")
            target_lang: 목표 언어 ("ko", "ja", "auto")

        Returns:
            (translated_text, detected_source_lang, target_lang)
        """
        if not text.strip():
            return "", source_lang, target_lang

        try:
            client = self._get_client()

            # 자동 감지일 경우 언어 감지
            if source_lang == "auto":
                source_lang = await self.detect_language(text)

            # 목표 언어 결정
            if target_lang == "auto":
                if source_lang == "ko":
                    target_lang = "ja"
                elif source_lang == "ja":
                    target_lang = "ko"
                else:
                    target_lang = "ko"  # 기본값

            # 번역 요청
            response = await client.post(
                f"{self._base_url}/translate",
                json={
                    "q": text,
                    "source": source_lang,
                    "target": target_lang
                }
            )

            if response.status_code == 200:
                result = response.json()
                translated = result.get("translatedText", "")
                return translated, source_lang, target_lang
            else:
                print(f"[TextTranslator] Translation failed: {response.status_code}")
                return "", source_lang, target_lang

        except Exception as e:
            print(f"[TextTranslator] Translation error: {e}")
            return "", source_lang, target_lang

    async def close(self):
        """클라이언트 종료"""
        if self._client:
            await self._client.aclose()
            self._client = None


# Singleton instance
text_translator = TextTranslator()
