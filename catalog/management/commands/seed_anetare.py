"""
Shton 20 anëtarë/përdorues me emra dhe të dhëna shqiptare për testim.
Përdorim: python manage.py seed_anetare
"""
import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from accounts.models import MemberProfile, MemberStatus, MemberType


# Emra dhe mbiemra shqiptarë – djem dhe vajza
EMRA_MESHKUJ = [
    "Erion", "Dritan", "Arben", "Flamur", "Blerim", "Agon", "Klea", "Endrit", "Ardit", "Ermal",
]
EMRA_FEMRA = [
    "Era", "Anila", "Drita", "Elona", "Fjolla", "Gentiana", "Jonida", "Kejsi", "Liridona", "Merita",
]
MBIEMRA = [
    "Hoxha", "Kola", "Bardhi", "Dervishi", "Gjoka", "Hysi", "Leka", "Mema", "Ndoj", "Prifti",
    "Rexha", "Shkreli", "Tahiri", "Veseli", "Zeka", "Kastrati", "Berisha", "Krasniqi", "Hoti",
]

QYTETE_ADRESA = [
    "Tiranë, rruga Myslym Shyri 12",
    "Durrës, bulevardi Dyrrah 45",
    "Vlorë, rruga Sulejman Delvina 8",
    "Shkodër, rruga Oso Kuka 23",
    "Elbasan, rruga Kristaq Rama 5",
    "Korçë, rruga Fan Noli 31",
    "Fier, rruga 1 Maji 17",
    "Berat, rruga Antipatrea 9",
    "Gjirokastër, rruga Kadri Gjata 3",
    "Kukës, rruga Rruga e Kombit 22",
    "Lezhë, rruga Gjergj Kastrioti 14",
    "Sarandë, rruga Jonianët 7",
    "Pogradec, rruga Drilona 11",
    "Kavajë, rruga e Qendrës 6",
    "Lushnjë, rruga e Shkollës 19",
    "Peshkopi, rruga e Dibrës 2",
    "Burrel, rruga e Bashkisë 10",
    "Tepelenë, rruga e Vjetër 4",
    "Krujë, rruga Skënderbeu 15",
]


def _datelindje_rand():
    """Datëlindje e rastësishme 18–60 vjeç."""
    today = date.today()
    start = today - timedelta(days=60 * 365)
    end = today - timedelta(days=18 * 365)
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def _vendlindje():
    return random.choice([
        "Tiranë", "Durrës", "Vlorë", "Shkodër", "Elbasan", "Korçë", "Fier", "Berat",
        "Gjirokastër", "Kukës", "Lezhë", "Sarandë", "Pogradec", "Kavajë", "Lushnjë",
    ])


def _nr_id():
    return f"A{random.randint(100000, 999999)}B"


class Command(BaseCommand):
    help = "Shton 20 anëtarë me emra dhe të dhëna shqiptare për testim."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-input",
            action="store_true",
            help="Ekzekuto pa kërkuar konfirmim",
        )

    def handle(self, *args, **options):
        if not options["no_input"]:
            confirm = input("Shtohen 20 anëtarë me të dhëna shembull. Vazhdoj? (po/jo): ")
            if confirm.lower() not in ("po", "yes", "p", "y"):
                self.stdout.write("Anuluar.")
                return

        existing = MemberProfile.objects.count()
        target = 20
        to_create = max(0, target - existing)
        if to_create == 0:
            self.stdout.write(self.style.WARNING(f"Ekzistojnë tashmë të paktën {target} anëtarë. Shtimi anulohet."))
            return

        used_names = set()
        created = 0

        for i in range(to_create):
            # Përzierje djem/vajza
            if random.choice([True, False]):
                emer = random.choice(EMRA_MESHKUJ)
            else:
                emer = random.choice(EMRA_FEMRA)
            mbiemer = random.choice(MBIEMRA)
            full_name = f"{emer} {mbiemer}"
            if full_name in used_names:
                full_name = f"{emer} {mbiemer} {i + 1}"
            used_names.add(full_name)

            member_type = random.choice([MemberType.STANDARD, MemberType.STANDARD, MemberType.STUDENT, MemberType.VIP])
            phone = f"06{random.randint(70, 79)} {random.randint(100, 999)} {random.randint(100, 999)}"
            address = random.choice(QYTETE_ADRESA)

            MemberProfile.objects.create(
                full_name=full_name,
                phone=phone,
                address=address,
                date_of_birth=_datelindje_rand(),
                place_of_birth=_vendlindje(),
                national_id=_nr_id(),
                status=MemberStatus.ACTIVE,
                member_type=member_type,
            )
            created += 1

        self.stdout.write(
            self.style.SUCCESS(f"U shtuan {created} anëtarë. Fjalëkalimi i përdoruesve: 12345678")
        )
