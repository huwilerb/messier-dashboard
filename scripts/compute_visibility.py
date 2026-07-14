"""Compute per-object evening-visibility months for the Messier catalog,
as seen from Fribourg, Switzerland (46.8N), and write them into
messier_catalog.json as the "mois_visibles" field (comma-separated month
numbers, matching ObjetMessier.mois_visibles's storage format).

Approximates each object's position by its constellation's center (RA/Dec
below) rather than per-object coordinates, since the catalog only tracks
constellation and month-level granularity doesn't need more precision.

Method: an object's "opposition month" is when it transits at local
midnight (Sun's RA is 12h away from the object's RA) -- the month it's up
all night and best placed for evening observing. Its visible window is
that month +/- WINDOW months. Objects with declination above
(90 - latitude) are circumpolar (never set) and are visible year-round.
This is the standard "opposition +/- N months" rule of thumb amateur
guides use, rather than a fixed altitude cutoff -- a fixed cutoff either
excludes low-altitude-but-commonly-observed constellations (Sagittarius,
Scorpius) or, if loosened enough to include them, ends up calling almost
every object "visible" most of the year, which defeats the point of a
seasonal filter.

Re-run this script (`python scripts/compute_visibility.py --apply`) if the
catalog's constellation assignments ever change.
"""

import json
import sys
from pathlib import Path

LAT = 46.8  # Fribourg, Switzerland
CIRCUMPOLAR_DEC = 90 - LAT  # 43.2 deg; above this, up all night year-round
WINDOW = 2  # +/- months around opposition -> 5-month primary viewing window

# Approximate (RA hours, Dec degrees) for the center of each constellation
# present in the Messier catalog. Good enough for month-level granularity.
CONSTELLATIONS = {
    "Andromède": (1.0, 40),
    "Baleine": (1.7, -10),
    "Cancer": (8.6, 20),
    "Capricorne": (21.0, -20),
    "Cassiopée": (1.0, 60),
    "Chevelure de Bérénice": (12.8, 23),
    "Chiens de Chasse": (13.0, 40),
    "Cocher": (6.0, 42),
    "Cygne": (20.6, 40),
    "Dragon": (17.0, 65),
    "Grand Chien": (6.8, -22),
    "Grande Ourse": (11.0, 55),
    "Gémeaux": (7.0, 25),
    "Hercule": (17.3, 30),
    "Hydre": (10.3, -15),
    "Licorne": (7.0, -4),
    "Lion": (10.5, 15),
    "Lièvre": (5.5, -18),
    "Lyre": (18.8, 37),
    "Ophiuchus": (17.0, -10),
    "Orion": (5.5, 0),
    "Persée": (3.0, 42),
    "Petit Renard": (20.0, 25),
    "Poissons": (1.0, 10),
    "Poupe": (7.5, -22),
    "Pégase": (22.0, 18),
    "Sagittaire": (18.5, -28),
    "Scorpion": (16.7, -32),
    "Serpent": (16.5, -6),
    "Taureau": (4.5, 18),
    "Triangle": (1.5, 30),
    "Verseau": (22.0, -10),
    "Vierge": (12.5, 8),
    "Écu de Sobieski": (18.6, -9),
}


def opposition_month(ra_h: float) -> int:
    # Sun's RA(day) ~= (day-80)/365.25*24h, day 80 ~= Mar 21 (vernal
    # equinox, RA=0). Opposition: object transits at midnight, i.e.
    # RA_sun = RA_obj - 12h (mod 24).
    target = (ra_h - 12) % 24
    day = (80 + 365.25 * target / 24) % 365.25
    month = int(day // 30.4) + 1
    return min(max(month, 1), 12)


def visible_months(ra_h: float, dec_deg: float) -> list[int]:
    if dec_deg >= CIRCUMPOLAR_DEC:
        return list(range(1, 13))
    peak = opposition_month(ra_h)
    return sorted({((peak - 1 + offset) % 12) + 1 for offset in range(-WINDOW, WINDOW + 1)})


CATALOG_PATH = Path(__file__).resolve().parent.parent / "messier_catalog.json"


def _print_table() -> None:
    for name, (ra, dec) in CONSTELLATIONS.items():
        peak = opposition_month(ra)
        months = visible_months(ra, dec)
        print(f"{name:30s} RA={ra:5.1f}h Dec={dec:+4.0f}  peak_month={peak:2d}  months={months}")


def _apply_to_catalog() -> None:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    month_cache: dict[str, list[int]] = {}
    for obj in catalog:
        constellation = obj["constellation"]
        if constellation not in CONSTELLATIONS:
            raise SystemExit(f"Unknown constellation, add it to CONSTELLATIONS: {constellation!r}")
        if constellation not in month_cache:
            ra, dec = CONSTELLATIONS[constellation]
            month_cache[constellation] = visible_months(ra, dec)
        obj["mois_visibles"] = ",".join(str(m) for m in month_cache[constellation])
    CATALOG_PATH.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Updated {len(catalog)} objects in {CATALOG_PATH}")


if __name__ == "__main__":
    if "--apply" in sys.argv:
        _apply_to_catalog()
    else:
        _print_table()
