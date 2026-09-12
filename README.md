# InstrumentPSK

Интернет-магазин профессионального инструмента на Django.

## Разработка

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item DjangoWebProject1/.env.example DjangoWebProject1/.env
```

В локальном `.env` задайте `DEBUG=True`, `ALLOWED_HOSTS=localhost,127.0.0.1`,
случайный `SECRET_KEY` длиной от 50 символов и
`EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend`.
Для генерации ключа: `python -c "import secrets; print(secrets.token_urlsafe(64))"`.
Не публикуйте полученное значение. Затем:

```powershell
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

## Состав репозитория

`DjangoWebProject1/` содержит приложение, миграции, шаблоны и исходную статику.
В корне — Docker/Nginx, зависимости, сборщик релиза и документация.
`tests/` и `.github/workflows/` нужны для проверки изменений.
Старые разовые `sync_*`, `deploy_*`, `check_*`, история ассистентов и IDE-кэши
не входят в Git и не включаются в Docker build context.
