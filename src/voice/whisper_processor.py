# DEPRECATED: OpenAI Whisper implementation - не используется
# Заменен на Gemini Audio API для упрощения и унификации
"""
import os
import tempfile
from typing import Optional
from openai import OpenAI


class WhisperProcessor:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY')) if os.getenv('OPENAI_API_KEY') else None

    async def process_voice_message(self, file_content: bytes, file_extension: str = 'ogg') -> Optional[str]:
        # Обработка голосового сообщения через Whisper API
        if not self.client:
            return None

        try:
            # Создаем временный файл
            with tempfile.NamedTemporaryFile(suffix=f'.{file_extension}', delete=False) as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name

            try:
                # Отправляем на обработку в Whisper
                with open(temp_file_path, 'rb') as audio_file:
                    response = self.client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="ru"  # Указываем русский язык
                    )

                transcribed_text = response.text.strip() if response.text else ""
                return transcribed_text if transcribed_text else None

            finally:
                # Удаляем временный файл
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)

        except Exception as e:
            print(f"Ошибка при обработке голосового сообщения: {e}")
            return None

    def is_voice_processing_available(self) -> bool:
        # Проверка доступности обработки голосовых сообщений
        return self.client is not None
"""


# НОВАЯ РЕАЛИЗАЦИЯ: Gemini Audio API
class VoiceProcessor:
    """Заглушка для совместимости - голосовая обработка перенесена в GeminiProcessor"""

    def __init__(self):
        pass

    def is_voice_processing_available(self) -> bool:
        """Проверка доступности обработки голосовых сообщений через Gemini"""
        import os
        return bool(os.getenv('GEMINI_API_KEY'))