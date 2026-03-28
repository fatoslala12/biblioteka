from django.core.management.base import BaseCommand

from circulation.services import auto_expire_overdue_reservations


class Command(BaseCommand):
    help = "Skadon automatikisht rezervimet e papërmbushura pas datës së marrjes."

    def handle(self, *args, **options):
        count = auto_expire_overdue_reservations(
            actor=None,
            source_screen="system.reservation.auto_expire",
            reason="Skadim automatik periodik (management command).",
        )
        self.stdout.write(self.style.SUCCESS(f"U skaduan {count} rezervime."))
