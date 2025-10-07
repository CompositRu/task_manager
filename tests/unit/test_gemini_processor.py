"""
Unit тесты для GeminiProcessor с мокированием Gemini API
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from src.ai.gemini_processor import GeminiProcessor


@pytest.fixture
def gemini_processor():
    """Фикстура для GeminiProcessor"""
    with patch('src.ai.gemini_processor.genai'):
        processor = GeminiProcessor()
        return processor


@pytest.fixture
def mock_gemini_response():
    """Мок ответа от Gemini API"""
    def _create_response(json_data: str):
        mock_response = Mock()
        mock_response.text = json_data
        return mock_response
    return _create_response


def test_process_task_text_simple(gemini_processor, mock_gemini_response):
    """Тест обработки простого текста задачи"""
    json_response = """{
        "title": "Купить молоко",
        "description": "Купить молоко в магазине",
        "conditions": [],
        "priority": "medium",
        "context": ["дом"],
        "due_date": "2025-10-08",
        "due_time": null,
        "has_specific_date": true,
        "has_specific_time": false,
        "category": "дом",
        "tags": ["покупки"],
        "reminder_needed": false,
        "reminder_time": null
    }"""

    gemini_processor.model.generate_content = Mock(
        return_value=mock_gemini_response(json_response)
    )

    result = gemini_processor.process_task_text("Купить молоко завтра")

    assert result['title'] == "Купить молоко"
    assert result['priority'] == "medium"
    assert result['category'] == "дом"
    assert result['has_specific_date'] is True
    assert result['has_specific_time'] is False


def test_process_task_text_with_time(gemini_processor, mock_gemini_response):
    """Тест обработки задачи с конкретным временем"""
    json_response = """{
        "title": "Встреча с клиентом",
        "description": "Встреча с клиентом для обсуждения проекта",
        "conditions": [],
        "priority": "high",
        "context": ["работа"],
        "due_date": "2025-10-08",
        "due_time": "15:00",
        "has_specific_date": true,
        "has_specific_time": true,
        "category": "работа",
        "tags": ["встречи", "клиенты"],
        "reminder_needed": true,
        "reminder_time": "14:30"
    }"""

    gemini_processor.model.generate_content = Mock(
        return_value=mock_gemini_response(json_response)
    )

    result = gemini_processor.process_task_text("Встреча с клиентом завтра в 15:00")

    assert result['title'] == "Встреча с клиентом"
    assert result['due_time'] == "15:00"
    assert result['has_specific_time'] is True
    assert result['reminder_needed'] is True
    assert result['priority'] == "high"


def test_process_task_text_with_conditions(gemini_processor, mock_gemini_response):
    """Тест обработки задачи с условиями"""
    json_response = """{
        "title": "Позвонить менеджеру",
        "description": "Позвонить менеджеру после получения документов",
        "conditions": ["получить документы", "рабочее время"],
        "priority": "high",
        "context": ["работа"],
        "due_date": null,
        "due_time": null,
        "has_specific_date": false,
        "has_specific_time": false,
        "category": "работа",
        "tags": ["звонки"],
        "reminder_needed": false,
        "reminder_time": null
    }"""

    gemini_processor.model.generate_content = Mock(
        return_value=mock_gemini_response(json_response)
    )

    result = gemini_processor.process_task_text(
        "Позвонить менеджеру после того как получу документы"
    )

    assert result['title'] == "Позвонить менеджеру"
    assert len(result['conditions']) == 2
    assert "получить документы" in result['conditions']
    assert result['has_specific_date'] is False


def test_process_task_text_markdown_cleanup(gemini_processor, mock_gemini_response):
    """Тест очистки markdown разметки из ответа Gemini"""
    json_response = """```json
{
    "title": "Тестовая задача",
    "description": "Описание",
    "conditions": [],
    "priority": "low",
    "context": [],
    "due_date": null,
    "due_time": null,
    "has_specific_date": false,
    "has_specific_time": false,
    "category": null,
    "tags": [],
    "reminder_needed": false,
    "reminder_time": null
}
```"""

    gemini_processor.model.generate_content = Mock(
        return_value=mock_gemini_response(json_response)
    )

    result = gemini_processor.process_task_text("Тестовая задача")

    assert result['title'] == "Тестовая задача"
    assert result['priority'] == "low"


def test_process_task_text_invalid_date(gemini_processor, mock_gemini_response):
    """Тест обработки невалидной даты"""
    json_response = """{
        "title": "Задача с неверной датой",
        "description": "Описание",
        "conditions": [],
        "priority": "medium",
        "context": [],
        "due_date": "invalid-date",
        "due_time": null,
        "has_specific_date": false,
        "has_specific_time": false,
        "category": null,
        "tags": [],
        "reminder_needed": false,
        "reminder_time": null
    }"""

    gemini_processor.model.generate_content = Mock(
        return_value=mock_gemini_response(json_response)
    )

    result = gemini_processor.process_task_text("Задача с неверной датой")

    # Невалидная дата должна быть заменена на None
    assert result['due_date'] is None


def test_process_task_text_api_error(gemini_processor):
    """Тест обработки ошибки API (fallback)"""
    gemini_processor.model.generate_content = Mock(
        side_effect=Exception("API Error")
    )

    text = "Тестовая задача при ошибке API"
    result = gemini_processor.process_task_text(text)

    # Должен вернуться fallback результат
    assert result['title'] == text[:50]
    assert result['description'] == text
    assert result['priority'] == "medium"
    assert result['conditions'] == []
    assert result['due_date'] is None


def test_process_condition_check(gemini_processor, mock_gemini_response):
    """Тест генерации вопроса для проверки условий"""
    question = "Вы получили документы от бухгалтерии?"

    gemini_processor.model.generate_content = Mock(
        return_value=mock_gemini_response(question)
    )

    result = gemini_processor.process_condition_check(
        "Позвонить менеджеру",
        ["получить документы"]
    )

    assert len(result) > 0
    assert isinstance(result, str)


def test_process_condition_check_error(gemini_processor):
    """Тест fallback при ошибке генерации вопроса"""
    gemini_processor.model.generate_content = Mock(
        side_effect=Exception("API Error")
    )

    task_title = "Тестовая задача"
    conditions = ["условие 1", "условие 2"]

    result = gemini_processor.process_condition_check(task_title, conditions)

    # Должен вернуться fallback вопрос
    assert task_title in result
    assert "условие 1" in result or "условие 2" in result


@pytest.mark.asyncio
async def test_process_voice_message_success(gemini_processor, tmp_path):
    """Тест успешной обработки голосового сообщения"""
    # Создаём временный файл
    voice_file = tmp_path / "test_voice.ogg"
    voice_file.write_bytes(b"fake audio data")

    # Мокируем загрузку и обработку
    mock_audio_file = Mock()
    mock_audio_file.name = "test_audio_123"

    mock_response = Mock()
    mock_response.text = "Купить молоко завтра"

    with patch('src.ai.gemini_processor.genai') as mock_genai:
        mock_genai.upload_file = Mock(return_value=mock_audio_file)
        mock_genai.delete_file = Mock()

        gemini_processor.model.generate_content = Mock(return_value=mock_response)

        result = await gemini_processor.process_voice_message(str(voice_file))

        assert result == "Купить молоко завтра"
        mock_genai.upload_file.assert_called_once()
        mock_genai.delete_file.assert_called_once()


@pytest.mark.asyncio
async def test_process_voice_message_file_not_found(gemini_processor):
    """Тест обработки несуществующего файла"""
    # Код пытается получить размер файла перед проверкой существования,
    # поэтому нужно перехватывать исключение на уровне теста
    with pytest.raises((FileNotFoundError, OSError)):
        await gemini_processor.process_voice_message("/nonexistent/file.ogg")


@pytest.mark.asyncio
async def test_process_voice_message_empty_transcription(gemini_processor, tmp_path):
    """Тест обработки пустой транскрипции"""
    voice_file = tmp_path / "test_voice.ogg"
    voice_file.write_bytes(b"fake audio data")

    mock_audio_file = Mock()
    mock_audio_file.name = "test_audio_123"

    mock_response = Mock()
    mock_response.text = ""  # Пустая транскрипция

    with patch('src.ai.gemini_processor.genai') as mock_genai:
        mock_genai.upload_file = Mock(return_value=mock_audio_file)
        mock_genai.delete_file = Mock()

        gemini_processor.model.generate_content = Mock(return_value=mock_response)

        result = await gemini_processor.process_voice_message(str(voice_file))

        assert result is None


def test_is_voice_processing_available_with_key():
    """Тест проверки доступности голосовой обработки с ключом"""
    with patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
        with patch('src.ai.gemini_processor.genai'):
            processor = GeminiProcessor()
            assert processor.is_voice_processing_available() is True


def test_is_voice_processing_available_without_key():
    """Тест проверки доступности голосовой обработки без ключа"""
    with patch.dict('os.environ', {}, clear=True):
        with patch('src.ai.gemini_processor.genai'):
            processor = GeminiProcessor()
            assert processor.is_voice_processing_available() is False


def test_get_voice_status_message_with_key():
    """Тест сообщения о статусе с API ключом"""
    with patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
        with patch('src.ai.gemini_processor.genai'):
            processor = GeminiProcessor()
            status = processor.get_voice_status_message()
            assert "✅" in status
            assert "Доступна" in status


def test_get_voice_status_message_without_key():
    """Тест сообщения о статусе без API ключа"""
    with patch.dict('os.environ', {}, clear=True):
        with patch('src.ai.gemini_processor.genai'):
            processor = GeminiProcessor()
            status = processor.get_voice_status_message()
            assert "❌" in status
            assert "Недоступна" in status


def test_fallback_result(gemini_processor):
    """Тест получения fallback результата"""
    text = "Длинный текст задачи, который должен быть обрезан до 50 символов для title"

    result = gemini_processor._get_fallback_result(text)

    assert len(result['title']) <= 50
    assert result['description'] == text
    assert result['priority'] == "medium"
    assert result['conditions'] == []
    assert result['context'] == []
    assert result['due_date'] is None
    assert result['due_time'] is None
    assert result['has_specific_date'] is False
    assert result['has_specific_time'] is False
    assert result['category'] is None
    assert result['tags'] == []
    assert result['reminder_needed'] is False
    assert result['reminder_time'] is None
