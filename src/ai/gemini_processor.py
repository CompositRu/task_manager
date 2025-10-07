import json
import os
import tempfile
from datetime import datetime
from typing import Dict, Any, Optional
import google.generativeai as genai

# Попытка импорта pydub с обработкой ошибки для Python 3.13+
try:
    from pydub import AudioSegment
    AUDIO_PROCESSING_AVAILABLE = True
except (ImportError, ModuleNotFoundError) as e:
    print(f"Warning: Audio processing unavailable - {e}")
    AUDIO_PROCESSING_AVAILABLE = False
    AudioSegment = None


class GeminiProcessor:
    def __init__(self):
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        self.model = genai.GenerativeModel('gemini-1.5-flash')

    def process_task_text(self, text: str) -> Dict[str, Any]:
        """Обработка текста задачи через Gemini с извлечением всех параметров"""
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_day = datetime.now().strftime("%A")

        prompt = f"""
        Сегодня {current_date} ({current_day}).

        Проанализируй текст и создай структурированную задачу.
        Ответь ТОЛЬКО валидным JSON без markdown разметки:
        {{
            "title": "короткое название задачи",
            "description": "подробное описание",
            "conditions": ["условие 1", "условие 2"],
            "priority": "high/medium/low",
            "context": ["дом", "работа", "дорога"],
            "due_date": "YYYY-MM-DD или null",
            "due_time": "HH:MM или null (если указано конкретное время события)",
            "has_specific_date": true/false,
            "has_specific_time": true/false,
            "category": "работа/дом/личное/учеба или null",
            "tags": ["тег1", "тег2"],
            "reminder_needed": true/false,
            "reminder_time": "HH:MM или null"
        }}

        Правила извлечения:
        - Дата: конкретные даты, дни недели, "завтра", "послезавтра"
        - Время события (due_time): если указано конкретное время выполнения задачи ("встреча в 15:00", "позвонить в 10:30")
        - has_specific_time: true если есть конкретное время выполнения задачи
        - Категория: автоматически определи из контекста (работа, дом, личное, учеба)
        - Теги: ключевые слова или проекты из текста
        - Напоминание: если упоминается время или "напомни"
        - Условия: если есть фразы "когда", "если", "после того как"

        Текст: {text}
        """

        try:
            response = self.model.generate_content(prompt)
            json_text = response.text.strip()
            if json_text.startswith('```'):
                json_text = json_text.split('```')[1]
                if json_text.startswith('json'):
                    json_text = json_text[4:]

            result = json.loads(json_text.strip())

            # Валидация даты
            if result.get('due_date'):
                try:
                    parsed_date = datetime.strptime(result['due_date'], '%Y-%m-%d')
                    result['due_date'] = parsed_date.strftime('%Y-%m-%d')
                except:
                    result['due_date'] = None

            return result

        except Exception as e:
            print(f"Ошибка Gemini: {e}")
            return self._get_fallback_result(text)

    def process_condition_check(self, task_title: str, conditions: list) -> str:
        """Генерация вопроса для проверки условий"""
        conditions_text = ", ".join(conditions)

        prompt = f"""
        Создай вежливый вопрос пользователю для проверки выполнения условий задачи.

        Задача: {task_title}
        Условия: {conditions_text}

        Сформулируй короткий вопрос (1-2 предложения), который поможет понять,
        выполнены ли условия и можно ли приступать к задаче.
        """

        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"Ошибка при генерации вопроса: {e}")
            return f"Выполнены ли условия для задачи '{task_title}'? ({conditions_text})"

    async def process_voice_message(self, voice_file_path: str) -> Optional[str]:
        """Обработка голосового сообщения через Gemini Audio API"""
        import os

        print(f"Processing voice file: {voice_file_path}, size: {os.path.getsize(voice_file_path)} bytes")

        try:
            # Попытка прямой загрузки OGG файла без конвертации
            try:
                print("Attempting direct OGG upload to Gemini...")

                # Проверяем, что файл существует и читается
                if not os.path.exists(voice_file_path):
                    print(f"Voice file does not exist: {voice_file_path}")
                    return None

                # Загружаем OGG файл напрямую в Gemini с MIME типом
                audio_file = genai.upload_file(voice_file_path, mime_type="audio/ogg")
                print(f"File uploaded successfully: {audio_file.name}")

                # Транскрибируем через Gemini
                prompt = """
                Транскрибируй это аудио сообщение.
                Верни ТОЛЬКО текст того, что было сказано, без дополнительных комментариев.
                Если язык русский - транскрибируй на русском.
                """

                print("Generating transcription...")
                response = self.model.generate_content([prompt, audio_file])
                text = response.text.strip() if response.text else ""
                print(f"Transcription result: '{text}'")

                # Удаляем файл из Gemini
                genai.delete_file(audio_file.name)

                return text if text else None

            except Exception as direct_error:
                print(f"Direct OGG upload failed: {direct_error}")
                print(f"Error type: {type(direct_error)}")

                # Fallback: попытка конвертации если pydub доступен
                if AUDIO_PROCESSING_AVAILABLE and AudioSegment:
                    print("Attempting OGG to MP3 conversion...")
                    try:
                        # Конвертируем OGG в MP3 (Gemini лучше работает с MP3)
                        audio = AudioSegment.from_ogg(voice_file_path)

                        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_mp3:
                            audio.export(tmp_mp3.name, format="mp3")
                            mp3_path = tmp_mp3.name

                        print(f"Converted to MP3: {mp3_path}, size: {os.path.getsize(mp3_path)} bytes")

                        try:
                            # Загружаем MP3 в Gemini
                            audio_file = genai.upload_file(mp3_path, mime_type="audio/mp3")
                            print(f"MP3 uploaded successfully: {audio_file.name}")

                            # Определяем prompt для MP3
                            mp3_prompt = """
                            Транскрибируй это аудио сообщение.
                            Верни ТОЛЬКО текст того, что было сказано, без дополнительных комментариев.
                            Если язык русский - транскрибируй на русском.
                            """

                            response = self.model.generate_content([mp3_prompt, audio_file])
                            text = response.text.strip() if response.text else ""
                            print(f"MP3 transcription result: '{text}'")

                            # Удаляем файл из Gemini
                            genai.delete_file(audio_file.name)

                            return text if text else None

                        finally:
                            # Удаляем временный MP3 файл
                            if os.path.exists(mp3_path):
                                os.unlink(mp3_path)

                    except Exception as conversion_error:
                        print(f"Conversion failed: {conversion_error}")
                        return None
                else:
                    print("Audio conversion not available (pydub not installed)")
                    # Последняя попытка: возможно, Gemini принимает OGG с правильным MIME типом
                    try:
                        print("Trying OGG with explicit MIME type...")

                        # Копируем файл с правильным расширением
                        import shutil
                        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp_ogg:
                            shutil.copy2(voice_file_path, tmp_ogg.name)
                            ogg_copy_path = tmp_ogg.name

                        try:
                            # Загружаем с явным указанием MIME типа
                            audio_file = genai.upload_file(
                                ogg_copy_path,
                                mime_type="audio/ogg"
                            )
                            print(f"OGG with MIME uploaded successfully: {audio_file.name}")

                            # Определяем prompt для fallback
                            fallback_prompt = """
                            Транскрибируй это аудио сообщение.
                            Верни ТОЛЬКО текст того, что было сказано, без дополнительных комментариев.
                            Если язык русский - транскрибируй на русском.
                            """

                            response = self.model.generate_content([fallback_prompt, audio_file])
                            text = response.text.strip() if response.text else ""
                            print(f"OGG MIME transcription result: '{text}'")

                            # Удаляем файл из Gemini
                            genai.delete_file(audio_file.name)

                            return text if text else None

                        finally:
                            # Удаляем временный файл
                            if os.path.exists(ogg_copy_path):
                                os.unlink(ogg_copy_path)

                    except Exception as mime_error:
                        print(f"MIME type attempt failed: {mime_error}")
                        return None

        except Exception as e:
            print(f"Ошибка при обработке голосового сообщения через Gemini: {e}")
            print(f"Error type: {type(e)}")
            return None

    def is_voice_processing_available(self) -> bool:
        """Проверка доступности обработки голосовых сообщений через Gemini"""
        return bool(os.getenv('GEMINI_API_KEY'))

    def get_voice_status_message(self) -> str:
        """Получить сообщение о статусе голосовой обработки"""
        if not os.getenv('GEMINI_API_KEY'):
            return "❌ Недоступна (нет GEMINI_API_KEY)"
        elif not AUDIO_PROCESSING_AVAILABLE:
            return "✅ Доступна (Gemini Audio, без конвертации)"
        else:
            return "✅ Доступна (Gemini Audio с конвертацией)"

    def _get_fallback_result(self, text: str) -> Dict[str, Any]:
        """Базовый результат при ошибке Gemini"""
        return {
            "title": text[:50],
            "description": text,
            "conditions": [],
            "priority": "medium",
            "context": [],
            "due_date": None,
            "due_time": None,
            "has_specific_date": False,
            "has_specific_time": False,
            "category": None,
            "tags": [],
            "reminder_needed": False,
            "reminder_time": None
        }