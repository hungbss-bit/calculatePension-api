from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from dateutil.relativedelta import relativedelta

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LEGAL_RULE_VERSION = "VN-BHXH-58/VBHN-VPQH-2025+ND158-2025+ND159-2025+DATA-2026+API-V1.0"
SUPPORTED_BENEFIT_YEAR = 2026


@lru_cache(maxsize=None)
def _load_json(name: str) -> dict:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def adjustment_tables() -> tuple[dict[int, Decimal], dict[int, Decimal]]:
    raw = _load_json("adjustment_coefficients_2026.json")
    salary = {int(k): Decimal(str(v)) for k, v in raw["salary_coefficients"].items()}
    voluntary = {
        int(k): Decimal(str(v))
        for k, v in raw["voluntary_income_coefficients"].items()
    }
    return salary, voluntary


def coefficient_for_year(table: dict[int, Decimal], year: int) -> Decimal:
    lookup_year = 1994 if year < 1995 else year
    try:
        return table[lookup_year]
    except KeyError as exc:
        raise ValueError(f"Chưa có hệ số điều chỉnh cho năm đóng {year}.") from exc


def base_salary_for_month(month: date) -> Decimal:
    raw = _load_json("base_salary_timeline.json")
    applicable: Decimal | None = None
    for item in raw["timeline"]:
        effective = date.fromisoformat(item["from"])
        if month >= effective:
            applicable = Decimal(str(item["amount_vnd"]))
        else:
            break
    if applicable is None:
        raise ValueError(
            f"Chưa có mức lương cơ sở/mức tham chiếu cho tháng "
            f"{month.year:04d}-{month.month:02d}."
        )
    return applicable


def retirement_age_for_year(sex: str, year: int) -> tuple[int, int]:
    if year <= 2020:
        return (60, 0) if sex == "male" else (55, 0)
    if sex == "male" and year >= 2028:
        return 62, 0
    if sex == "female" and year >= 2035:
        return 60, 0

    raw = _load_json("retirement_age_schedule.json")
    item = raw["schedule"].get(sex, {}).get(str(year))
    if item:
        return int(item["years"]), int(item["months"])

    if sex == "male":
        total = 60 * 12 + 3 * (year - 2020)
        total = min(total, 62 * 12)
    else:
        total = 55 * 12 + 4 * (year - 2020)
        total = min(total, 60 * 12)
    return divmod(total, 12)


def threshold_date(
    dob: date,
    sex: str,
    retirement_year: int,
    offset_years: int = 0,
) -> date:
    years, months = retirement_age_for_year(sex, retirement_year)
    total_months = years * 12 + months - offset_years * 12
    offset_years_final, offset_months_final = divmod(total_months, 12)
    return dob + relativedelta(
        years=offset_years_final,
        months=offset_months_final,
    )



def earliest_threshold_date(
    dob: date,
    sex: str,
    offset_years: int = 0,
) -> date:
    """Ngày sớm nhất đạt tuổi theo lộ trình, giải tự nhất quán theo năm."""
    legacy_age = (60 if sex == "male" else 55) - offset_years
    legacy_candidate = dob + relativedelta(years=legacy_age)
    if legacy_candidate.year <= 2020:
        return legacy_candidate

    for retirement_year in range(2021, 2071):
        candidate = threshold_date(
            dob,
            sex,
            retirement_year,
            offset_years,
        )
        if candidate.year == retirement_year:
            return candidate

    raise ValueError(
        f"Không xác định được ngày đủ tuổi nghỉ hưu cho ngày sinh {dob.isoformat()}."
    )

def state_average_months(first_state_month: str) -> int | None:
    raw = _load_json("state_average_windows.json")
    for item in raw["windows"]:
        if item["from"] <= first_state_month <= item["to"]:
            return item["months"]
    raise ValueError(
        f"Không xác định được số tháng bình quân lương Nhà nước cho mốc "
        f"{first_state_month}."
    )
