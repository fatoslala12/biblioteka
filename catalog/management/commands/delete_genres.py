"""
Fshin të gjitha zhanret dhe lidhjet e tyre me librat.
Përdorim: python manage.py delete_genres [--no-input]
"""
from django.core.management.base import BaseCommand

from catalog.models import Genre


class Command(BaseCommand):
    help = "Fshin të gjitha zhanret dhe lidhjet e tyre me librat."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-input",
            action="store_true",
            help="Ekzekuto pa kërkuar konfirmim",
        )

    def handle(self, *args, **options):
        count = Genre.objects.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS("Nuk ka zhanre për fshirje."))
            return

        if not options["no_input"]:
            confirm = input(f"Fshihen {count} zhanre dhe të gjitha lidhjet me librat. Vazhdoj? (po/jo): ")
            if confirm.lower() not in ("po", "yes", "p", "y"):
                self.stdout.write("Anuluar.")
                return

        # Django fshin automatikisht lidhjet M2M (Book.genres) kur fshijmë Genre
        Genre.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"U fshinë {count} zhanre."))
