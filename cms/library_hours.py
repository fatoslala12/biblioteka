"""Orari dhe pushimet zyrtare të Bibliotekës Kamëz."""

OPEN_HOUR = 8
CLOSE_HOUR = 19

# (muaj, ditë) — pushime fikse çdo vit
FIXED_HOLIDAYS: list[tuple[int, int]] = [
    (1, 1),   # Viti i Ri
    (3, 14),  # Dita e Verës
    (3, 22),  # Nevruzi
    (5, 1),   # Dita Ndërkombëtare e Punës
    (5, 5),   # Dita e Dëshmorëve
    (11, 28), # Dita e Pavarësisë
    (11, 29), # Dita e Çlirimit
    (12, 8),  # Dita e Rinisë
]

# Bajramet ndryshojnë sipas kalendarit hënor — përditëso çdo vit.
# 2026 (vlerësim): Fitër ~20 Mars, Kurban ~27 Maj (+ ditën pas për traditë 2-ditore).
VARIABLE_HOLIDAYS_BY_YEAR: dict[int, list[tuple[int, int]]] = {
    2025: [(3, 30), (3, 31), (6, 6), (6, 7)],
    2026: [(3, 20), (3, 21), (5, 27), (5, 28)],
    2027: [(3, 10), (3, 11), (5, 16), (5, 17)],
}


def holidays_for_year(year: int) -> list[tuple[int, int]]:
    out = list(FIXED_HOLIDAYS)
    out.extend(VARIABLE_HOLIDAYS_BY_YEAR.get(year, []))
    return out


def library_clock_context(*, year: int | None = None) -> dict:
    from django.utils import timezone

    y = year if year is not None else timezone.localdate().year
    return {
        "library_open_hour": OPEN_HOUR,
        "library_close_hour": CLOSE_HOUR,
        "library_holidays": holidays_for_year(y),
    }
