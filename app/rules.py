from __future__ import annotations

from datetime import date
from decimal import Decimal
from dateutil.relativedelta import relativedelta


LEGAL_RULE_VERSION = (
    "VN-LBHXH-41/2024-QH15@2025-07-01"
    "+ND158/2025/ND-CP"
    "+BHXH-340/CSXH-2026"
)


COEFFICIENTS_2026: dict[int, Decimal] = {
    1994: Decimal("5.81"),  # Used for every year before 1995.
    1995: Decimal("4.91"),
    1996: Decimal("4.65"),
    1997: Decimal("4.50"),
    1998: Decimal("4.18"),
    1999: Decimal("4.01"),
    2000: Decimal("4.07"),
    2001: Decimal("4.09"),
    2002: Decimal("3.94"),
    2003: Decimal("3.81"),
    2004: Decimal("3.54"),
    2005: Decimal("3.27"),
    2006: Decimal("3.05"),
    2007: Decimal("2.81"),
    2008: Decimal("2.29"),
    2009: Decimal("2.14"),
    2010: Decimal("1.96"),
    2011: Decimal("1.65"),
    2012: Decimal("1.51"),
    2013: Decimal("1.42"),
    2014: Decimal("1.36"),
    2015: Decimal("1.36"),
    2016: Decimal("1.32"),
    2017: Decimal("1.28"),
    2018: Decimal("1.23"),
    2019: Decimal("1.20"),
    2020: Decimal("1.16"),
    2021: Decimal("1.14"),
    2022: Decimal("1.11"),
    2023: Decimal("1.07"),
    2024: Decimal("1.03"),
    2025: Decimal("1.00"),
    2026: Decimal("1.00"),
}


def retirement_age_for_year(sex: str, year: int) -> tuple[int, int]:
    """Return statutory normal retirement age as (years, months)."""
    if sex == "male":
        if year <= 2020:
            return 60, 0
        if year >= 2028:
            return 62, 0
        total_months = 60 * 12 + 3 * (year - 2020)
    else:
        if year <= 2020:
            return 55, 0
        if year >= 2035:
            return 60, 0
        total_months = 55 * 12 + 4 * (year - 2020)
    return divmod(total_months, 12)


def normal_retirement_threshold(dob: date, sex: str) -> tuple[date, tuple[int, int]]:
    """
    Find the calendar year whose statutory age yields a threshold date in that year.
    The current stepped schedule starts in 2021.
    """
    for retirement_year in range(2021, 2061):
        years, months = retirement_age_for_year(sex, retirement_year)
        candidate = dob + relativedelta(years=years, months=months)
        if candidate.year == retirement_year:
            return candidate, (years, months)

    # Defensive fallback for very old or unusual dates.
    years, months = retirement_age_for_year(sex, max(2021, dob.year + 60))
    return dob + relativedelta(years=years, months=months), (years, months)


def coefficient_for_year(table: dict[int, Decimal], year: int) -> Decimal:
    if year < 1995:
        return table.get(1994, Decimal("1"))
    if year not in table:
        raise ValueError(
            f"No adjustment coefficient is available for contribution year {year}."
        )
    return table[year]


def state_average_years(first_state_year: int) -> int | None:
    if first_state_year < 1995:
        return 5
    if first_state_year <= 2000:
        return 6
    if first_state_year <= 2006:
        return 8
    if first_state_year <= 2015:
        return 10
    if first_state_year <= 2019:
        return 15
    if first_state_year <= 2024:
        return 20
    return None  # All contribution months.
