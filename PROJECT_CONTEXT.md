# PROJECT_CONTEXT — Madrigal TTS

## Назначение

Madrigal TTS — локальный MVP русскоязычного синтеза речи. Его задача — не просто озвучить строку, а дать пользователю контроль над омографами и передать выбранное ударение локальному Silero TTS.

## Архитектура

```text
browser (app/static) -> FastAPI (app/main.py)
                         -> NLP adapter -> app/nlp_engine.py
                         -> TTS adapter -> app/tts_engine.py -> WAV in outputs/
                         -> pronunciation_dictionary.py -> data/pronunciations.json
```

`app/main.py` обслуживает страницу `/`, статические файлы `/static`, API и безопасную выдачу `/outputs/{filename}`. Тяжёлые NLP/TTS-вызовы выполняются через `run_in_threadpool`.

## Структура каталогов

- `app/main.py` — FastAPI endpoints и интеграция режимов.
- `app/schemas.py` — Pydantic-запросы и `SynthesisMode`.
- `app/nlp_engine.py` — правила нормализации, защищённые фрагменты, омографы и AUTO-эвристики.
- `app/tts_engine.py` — однократная загрузка Silero, PCM16 WAV, 48 kHz и 300 мс тишины в начале.
- `app/services/nlp_adapter.py`, `tts_adapter.py` — контрактные границы движков.
- `app/pronunciation_dictionary.py` — валидация и атомарная запись локального JSON-словаря.
- `app/static/` — vanilla HTML/CSS/JS интерфейс.
- `data/pronunciations.json` — пользовательские записи, сейчас пустой безопасный шаблон.
- `tests/` — unit/API/regression tests.
- `models/V5_ru.pt` — локальная модель, намеренно исключена из Git.

## NLP и ambiguity_id

`analyze_text(text)` возвращает `original_text`, `normalized_text`, `transformations`, `ambiguities`, `warnings`. Каждая неоднозначность содержит уникальный `id` (`amb_0`, `amb_1`, ...), исходные `start`/`end`, слово и варианты. Идентификатор относится к вхождению, а не к строке слова: одинаковые омографы должны выбираться независимо.

`apply_pronunciation_choices(text, choices)` валидирует `{ambiguity_id: option_id}` и применяет замены справа налево по исходным позициям. Он возвращает `text_used`; URL, почта, телефоны, версии и технические идентификаторы защищены от преобразований.

Silero принимает знак `+` непосредственно перед ударной гласной: `з+амок`, `зам+ок`, `мук+а`. Комбинируемый акцент в `display` служит для интерфейса; в TTS передаётся `tts_text` с `+`.

Поддерживаются числа 0–9999, годы 2000–2099 с `г.`, время, `ул.`, `т. д.`, `т. п.`. Правила намеренно консервативны.

## Режимы

- `base`: исходный текст напрямую в Silero, NLP choices не применяются.
- `improved`: анализ, обязательные ручные choices для всех найденных неоднозначностей, затем `text_used` в Silero; без выбора API возвращает 409.
- `auto`: вызывает `auto_resolve_pronunciations`; эвристики используют локальный контекст и отдают qualitative confidence (`высокая`, `средняя`, `низкая`) в `auto_decisions`. Это предположение, не гарантия.

## API

- `GET /api/health` — состояние сервиса.
- `POST /api/analyze` — анализ `{ "text": "..." }`.
- `POST /api/synthesize` — `{ "text", "mode": "base|improved|auto", "choices", "voice" }`; возвращает URL WAV, метрики и `text_used`, а AUTO также `auto_decisions`.
- `GET|POST /api/pronunciations` — список/создание записей словаря.
- `PUT|DELETE /api/pronunciations/{word}` — изменение/удаление записи.
- `GET /outputs/{filename}` — безопасная выдача WAV только из `outputs`.

## Пользовательский словарь

Файл имеет вид:

```json
{"entries":[{"word":"атлас","options":[{"id":"maps","display":"а́тлас","tts_text":"+атлас","meaning":"Сборник карт"}]}]}
```

`word` — только буквенное слово; у записи один или более вариантов. Каждый вариант должен иметь уникальный `id`, непустые `display` и `meaning`, а `tts_text` — ровно один `+`. Редактор UI строит эти данные без ручного JSON. Запись выполняется во временный файл и атомарно заменяет JSON.

## Silero TTS

`app/tts_engine.py` использует Silero V5 RU с голосом `xenia`, 48 000 Hz и mono PCM16. Модель грузится один раз на процесс. После генерации, до записи WAV, добавляются ровно 14 400 нулевых сэмплов (300 мс). Модель не должна попадать в обычный Git: `models/*.pt` в `.gitignore`; путь локально — `models/V5_ru.pt`, либо переменная `MADRIGAL_SILERO_MODEL_PATH`.

## Установка и запуск

Нужно Python 3.12, локальный PyTorch CPU и файл модели. Затем:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8017
```

Тесты: ` .\.venv\Scripts\python.exe -m pytest -q`.

## Важные решения, которые нельзя отменять случайно

- Не заменять реальный Silero фиктивными WAV.
- Не удалять начальную тишину и не менять PCM16/48 kHz без аудиопроверки.
- Не применять choices в BASE.
- Не заменять `ambiguity_id` названием слова.
- Не трогать защищённые фрагменты текста.
- Не коммитить `.venv`, `.env`, outputs, caches или модель 145 MB.
- Не считать AUTO гарантированно правильным и не скрывать его уверенность.

## Подтверждённые проблемы

Пользователь подтвердил: AUTO в живом сценарии выдаёт «Нужен выбор произношения»; режимы в UI названы по-английски; длинная фраза с двумя значениями «мука» визуально показывает одно вхождение; человек ещё не выполнил слуховую оценку. Эти проблемы должны быть воспроизведены и исправлены следующей командой, а не объявлены решёнными только по unit-тестам.

## Как продолжить разработку с другой AI-моделью

Репозиторий: `https://github.com/serj33/madrigal-case6`. После `git clone` создайте Python 3.12 venv, установите `requirements.txt`, отдельно установите совместимый CPU PyTorch и положите полученный Silero `v5_ru.pt` в `models/V5_ru.pt` (либо задайте `MADRIGAL_SILERO_MODEL_PATH`). Запуск: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8017`; тесты: `.\.venv\Scripts\python.exe -m pytest -q`.

Сначала прочитайте этот файл, `NEXT_STEPS.md`, `README.md`, затем `app/main.py`, `app/nlp_engine.py`, `app/tts_engine.py`, адаптеры и тесты. Первые задачи — P0 в `NEXT_STEPS.md`: AUTO, повторные/склоняемые омографы, локализация режимов и воспроизводимая E2E-проверка. Не отменяйте контракт `ambiguity_id`, защищённые текстовые фрагменты, разделение BASE/IMPROVED/AUTO, формат PCM16/48 kHz, 300 мс тишины и исключение модели из Git без необходимости.

Любые ключи новой AI-модели держите только в локальном `.env`, который уже игнорируется; никогда не добавляйте их в исходники, JSON-словарь, тестовые фикстуры, документацию или Git history.
