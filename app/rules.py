from __future__ import annotations

from datetime import date
from decimal import Decimal
from dateutil.relativedelta import relativedelta

LEGAL_RULE_VERSION = (
    "VN-LBHXH-41/2024-QH15@2025-07-01"
    "+ND158/2025/ND-CP"
    "+ND159/2025/ND-CP"
    "+TT12/2025/TT-BNV"
    "+ND135/2020/ND-CP"
    "+BHXH-340/CSXH-2026+PRE1995-NO-SALARY-DURATION-ONLY"
)

LEGAL_REFERENCES = [
    {
        "document": "Luật Bảo hiểm xã hội số 41/2024/QH15",
        "provisions": "Điều 64, 65, 66, 68, 72, 73 và 111",
        "purpose": "Điều kiện hưởng, tỷ lệ, giảm do nghỉ trước tuổi, trợ cấp một lần, mức bình quân và quá trình hỗn hợp.",
    },
    {
        "document": "Nghị định 158/2025/NĐ-CP",
        "provisions": "Điều 15, Điều 16 và quy định về thời gian đóng hỗn hợp",
        "purpose": (
            "Mức bình quân, điều chỉnh tiền lương; loại khỏi mức bình quân thời gian "
            "trước 01/01/1995 được công nhận nhưng không hưởng lương/sinh hoạt phí; "
            "xác định chính sách áp dụng khi có quá trình hỗn hợp."
        ),
    },
    {
        "document": "Nghị định 159/2025/NĐ-CP",
        "provisions": "Điều 11",
        "purpose": "Điều kiện, tỷ lệ và mức bình quân đối với quá trình bắt buộc kết hợp tự nguyện.",
    },
    {
        "document": "Thông tư 12/2025/TT-BNV",
        "provisions": "Công thức mức bình quân tiền lương làm căn cứ đóng BHXH",
        "purpose": "Công thức bình quân lương Nhà nước, lương doanh nghiệp và quá trình hỗn hợp.",
    },
    {
        "document": "Nghị định 135/2020/NĐ-CP",
        "provisions": "Lộ trình tuổi nghỉ hưu",
        "purpose": "Xác định tuổi nghỉ hưu theo năm nghỉ.",
    },
    {
        "document": "Công văn 340/BHXH-CSXH ngày 03/02/2026",
        "provisions": "Hệ số điều chỉnh năm 2026",
        "purpose": "Điều chỉnh tiền lương và thu nhập tháng đã đóng BHXH khi giải quyết trong năm 2026.",
    },
]

COEFFICIENTS_2026: dict[int, Decimal] = {
    1994: Decimal("5.81"),
    1995: Decimal("4.91"), 1996: Decimal("4.65"), 1997: Decimal("4.50"),
    1998: Decimal("4.18"), 1999: Decimal("4.01"), 2000: Decimal("4.07"),
    2001: Decimal("4.09"), 2002: Decimal("3.94"), 2003: Decimal("3.81"),
    2004: Decimal("3.54"), 2005: Decimal("3.27"), 2006: Decimal("3.05"),
    2007: Decimal("2.81"), 2008: Decimal("2.29"), 2009: Decimal("2.14"),
    2010: Decimal("1.96"), 2011: Decimal("1.65"), 2012: Decimal("1.51"),
    2013: Decimal("1.42"), 2014: Decimal("1.36"), 2015: Decimal("1.36"),
    2016: Decimal("1.32"), 2017: Decimal("1.28"), 2018: Decimal("1.23"),
    2019: Decimal("1.20"), 2020: Decimal("1.16"), 2021: Decimal("1.14"),
    2022: Decimal("1.11"), 2023: Decimal("1.07"), 2024: Decimal("1.03"),
    2025: Decimal("1.00"), 2026: Decimal("1.00"),
}

VOLUNTARY_COEFFICIENTS_2026: dict[int, Decimal] = {
    year: value for year, value in COEFFICIENTS_2026.items() if year >= 2008
}


def retirement_age_for_year(sex: str, year: int) -> tuple[int, int]:
    """Tuổi nghỉ hưu bình thường áp dụng trong năm nghỉ hưu."""
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


def age_after_offset(sex: str, retirement_year: int, offset_years: int) -> tuple[int, int]:
    years, months = retirement_age_for_year(sex, retirement_year)
    total = years * 12 + months - offset_years * 12
    return divmod(total, 12)


def threshold_date_for_retirement_year(
    dob: date, sex: str, retirement_year: int, offset_years: int = 0
) -> tuple[date, tuple[int, int]]:
    years, months = age_after_offset(sex, retirement_year, offset_years)
    return dob + relativedelta(years=years, months=months), (years, months)


def earliest_threshold_for_schedule(
    dob: date, sex: str, offset_years: int = 0
) -> tuple[date, tuple[int, int]]:
    """Tìm ngày đầu tiên người lao động đạt tuổi theo lộ trình từng năm."""
    for retirement_year in range(2021, 2071):
        candidate, age = threshold_date_for_retirement_year(
            dob, sex, retirement_year, offset_years
        )
        if candidate.year == retirement_year:
            return candidate, age
    candidate, age = threshold_date_for_retirement_year(
        dob, sex, max(2021, dob.year + 60), offset_years
    )
    return candidate, age


def coefficient_for_year(table: dict[int, Decimal], year: int) -> Decimal:
    if year < 1995 and 1994 in table:
        return table[1994]
    if year not in table:
        raise ValueError(f"Chưa có hệ số điều chỉnh cho năm đóng {year}.")
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
    return None
