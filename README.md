# InstrumentPSK

Интернет-магазин профессионального инструмента на Django.

## Разработка

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item DjangoWebProject1/.env.example DjangoWebProject1/.env
python DjangoWebProject1/manage.py migrate
python DjangoWebProject1/manage.py runserver
```

Секреты, база данных, media и deployment-архивы не входят в Git. Для production
используйте только архив, созданный `python build_release.py` из чистого commit.

## Ветки

- `main` — стабильная история;
- `develop` — интеграция изменений;
- `feature/*` — отдельные задачи;
- `release/production` — версия, разрешённая для развёртывания.

Перед merge обязательны тесты и `python manage.py check --deploy` с production-переменными.
