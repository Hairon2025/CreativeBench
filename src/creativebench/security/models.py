"""Security scan and Red Team benchmark schemas."""

from pydantic import Field

from creativebench.models import RiskType, StrictModel


class SecurityFinding(StrictModel):
    risks: list[RiskType] = Field(min_length=1)
    matched_rule_ids: list[str]
    requires_review: bool


class SecurityCase(StrictModel):
    id: str = Field(pattern=r"^sec-[0-9]{4,}$")
    prompt_text: str = Field(min_length=1)
    expected_risks: list[RiskType] = Field(min_length=1)


class SecurityBenchmarkReport(StrictModel):
    case_count: int = Field(ge=1)
    exact_match: float = Field(ge=0, le=1)
    precision: float = Field(ge=0, le=1)
    recall: float = Field(ge=0, le=1)
    f1: float = Field(ge=0, le=1)
    false_negative_case_ids: list[str]
