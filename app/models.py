from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

YEAR_MONTH_PATTERN = r"^[0-9]{4}-(0[1-9]|1[0-2])$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class Sex(str, Enum):
    male = "male"
    female = "female"


class RetirementCase(str, Enum):
    normal = "normal"
    hazardous_or_special_region = "hazardous_or_special_region"
    underground_coal = "underground_coal"
    reduced_capacity = "reduced_capacity"


class RetirementPolicy(str, Enum):
    none = "none"
    decree_154_streamlining = "decree_154_streamlining"
    other_special_policy = "other_special_policy"


class ParticipationStatus(str, Enum):
    contributed = "contributed"
    credited_duration_only = "credited_duration_only"
    not_participating = "not_participating"


class DurationOnlyReason(str, Enum):
    pre1995_no_salary_or_living_allowance = "pre1995_no_salary_or_living_allowance"


class ContributionType(str, Enum):
    compulsory_state = "compulsory_state"
    compulsory_employer = "compulsory_employer"
    voluntary = "voluntary"


class BasisInputType(str, Enum):
    mau_07_sbh_components = "mau_07_sbh_components"
    monthly_basis_vnd = "monthly_basis_vnd"


class SbhComponentUnit(str, Enum):
    coefficient = "coefficient"
    vnd = "vnd"


class AverageInclusion(str, Enum):
    included = "included"
    excluded = "excluded"


class AverageExclusionReason(str, Enum):
    pre1995_policy = "pre1995_policy"


class BenefitCalculationScope(str, Enum):
    pension_only = "pension_only"
    pension_and_one_time_allowance = "pension_and_one_time_allowance"


class Person(StrictModel):
    date_of_birth: date
    sex: Sex


class SBHComponents(StrictModel):
    unit: SbhComponentUnit
    base_value: Annotated[Decimal, Field(ge=0)]
    position_allowance: Annotated[Decimal, Field(ge=0)] = Decimal("0")
    seniority_beyond_frame_allowance: Annotated[Decimal, Field(ge=0)] = Decimal("0")
    professional_seniority_allowance: Annotated[Decimal, Field(ge=0)] = Decimal("0")
    regional_allowance: Annotated[Decimal, Field(ge=0)] = Decimal("0")
    other_allowance: Annotated[Decimal, Field(ge=0)] = Decimal("0")
    reelection_allowance: Annotated[Decimal, Field(ge=0)] = Decimal("0")

    def total(self) -> Decimal:
        return sum(
            (
                self.base_value,
                self.position_allowance,
                self.seniority_beyond_frame_allowance,
                self.professional_seniority_allowance,
                self.regional_allowance,
                self.other_allowance,
                self.reelection_allowance,
            ),
            Decimal("0"),
        )


class Contribution(StrictModel):
    from_month: str = Field(pattern=YEAR_MONTH_PATTERN)
    to_month: str = Field(pattern=YEAR_MONTH_PATTERN)
    participation_status: ParticipationStatus
    duration_only_reason: DurationOnlyReason | None = None
    contribution_type: ContributionType | None = None
    basis_input_type: BasisInputType | None = None
    monthly_basis_vnd: Annotated[Decimal | None, Field(ge=0)] = None
    sbh_components: SBHComponents | None = None
    average_inclusion: AverageInclusion | None = None
    average_exclusion_reason: AverageExclusionReason | None = None
    after_retirement_age_period: bool = False


class PensionCalculationRequest(StrictModel):
    person: Person
    pension_start_month: str = Field(pattern=YEAR_MONTH_PATTERN)
    retirement_case: RetirementCase
    retirement_policy: RetirementPolicy = RetirementPolicy.none
    impairment_percent: Annotated[Decimal | None, Field(ge=0, le=100)] = None
    contributions: list[Contribution] = Field(min_length=1)
    retirement_age_eligible_month: str | None = Field(
        default=None, pattern=YEAR_MONTH_PATTERN
    )
    benefit_calculation_scope: BenefitCalculationScope = (
        BenefitCalculationScope.pension_and_one_time_allowance
    )


class NormalizedSummary(StrictModel):
    total_contribution_months: int
    excluded_bhtn_months: int
    contribution_count: int


class ValidationResponse(StrictModel):
    validation: bool
    normalized_summary: NormalizedSummary | None = None
    warnings: list[str] = Field(default_factory=list)


class OneTimeRetirementAllowance(StrictModel):
    eligible: bool
    threshold_months: int
    total_excess_months: int
    excess_before_retirement_age_months: int
    excess_after_retirement_age_months: int
    standard_allowance_amount: float
    post_retirement_allowance_amount: float
    total_allowance_amount: float
    average_basis: float
    warnings: list[str] = Field(default_factory=list)


class PensionCalculationResponse(StrictModel):
    total_months: int
    average_salary: float
    replacement_rate: float
    rate_before_early_reduction: float
    contribution_month_remainder_rate: float
    early_retirement_months: int
    early_retirement_reduction: float
    rate_after_reduction: float
    estimated_pension: float
    warnings: list[str] = Field(default_factory=list)
    one_time_retirement_allowance: OneTimeRetirementAllowance | None = None


class ErrorResponse(StrictModel):
    error_code: str
    detail: str
    fields: list[str] = Field(default_factory=list)
