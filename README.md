# Bitrix Randomizer

Серверная часть приложения для облачного Битрикс24.

## Статус каркаса

Пока реализован только минимальный FastAPI API с маршрутом `GET /health`. OAuth, REST-интеграция, CRM-робот и база данных пока не реализованы.

## Запуск

Требуется Python 3.12+.

```bash
python -m venv .venv
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Windows PowerShell: `.venv\Scripts\Activate.ps1`; macOS/Linux: `source .venv/bin/activate`.

Проверка: `http://127.0.0.1:8000/health`; Swagger: `http://127.0.0.1:8000/docs`.

```bash
pytest
ruff check .
ruff format --check .
```
