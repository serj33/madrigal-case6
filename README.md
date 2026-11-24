# Madrigal — Backend API

Локальный FastAPI-сервис для прототипа русскоязычного TTS. Backend не
содержит собственных правил NLP и не имитирует аудио: он подключает реальные
модули через адаптеры.

## Запуск

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Документация API: `http://127.0.0.1:8000/docs`.

## Контракт интеграции

NLP-команда должна добавить `app/nlp_engine.py` с функциями:

```python
analyze_text(text: str) -> dict
apply_pronunciation_choices(text: str, choices: dict[str, str]) -> dict
```

`analyze_text` возвращает `original_text`, `normalized_text`,
`transformations`, `ambiguities` и `warnings`. Для каждой неоднозначности со
статусом `needs_choice` improved-синтез требует choice. Вторая функция должна
вернуть как минимум `{"text_used": "..."}`.

TTS-команда должна добавить `app/tts_engine.py`:

```python
synthesize(text: str, output_path: str, voice: str | None = None,
           settings: dict | None = None) -> dict
```

Она обязана создать непустой WAV по `output_path` и вернуть реальные
`duration_seconds` и `generation_seconds`. Backend генерирует уникальное имя
в `outputs/`, проверяет файл и безопасно публикует его только через
`GET /outputs/{filename}`.

Пока модуль NLP или TTS не подключён, соответствующий endpoint отвечает
`503`; это намеренно, чтобы не выдавать заглушки за готовую интеграцию.

## API

- `GET /api/health`
- `POST /api/analyze` — `{ "text": "..." }`
- `POST /api/synthesize` — `{ "text": "...", "mode": "base|improved", "choices": {}, "voice": null }`
- `GET /outputs/{filename}`

Ограничение текста: 2000 символов. Для `improved` входа с невыбранными
омографами возвращается `409` и их список.

## Проверка

```powershell
pytest -q
```

Тесты используют mock-интеграции и не скачивают TTS-веса. Реальный синтез,
проверку лицензии модели и слуховую оценку требуется выполнить вручную после
подключения `app/tts_engine.py`.
