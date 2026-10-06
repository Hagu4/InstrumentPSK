from django.core.management.base import BaseCommand, CommandError

from app.price_sync.services import cleanup_old_price_import_details


class Command(BaseCommand):
    help = "Удаляет файлы и строки старых успешных импортов цен"

    def add_arguments(self, parser):
        parser.add_argument("--keep", type=int, default=12)

    def handle(self, *args, **options):
        try:
            result = cleanup_old_price_import_details(keep=options["keep"])
        except ValueError as error:
            raise CommandError(str(error)) from error

        self.stdout.write(
            self.style.SUCCESS(
                "Очистка завершена: "
                f"импортов {result.cleaned_imports}, "
                f"файлов {result.deleted_files}, "
                f"строк {result.deleted_rows}."
            )
        )
