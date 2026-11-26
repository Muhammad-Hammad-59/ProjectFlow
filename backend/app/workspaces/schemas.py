"""Request and response models for workspaces and their calendar.

Working days use ISO numbers like the database: 1 = Monday ... 7 = Sunday.
(The scheduling engine uses 0 = Monday; convert when building its Calendar.)
"""
import datetime as dt
import uuid
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Slug = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_lower=True, max_length=48, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$"),
]
Weekday = Annotated[int, Field(ge=1, le=7)]


def _sorted_unique(days: list[int]) -> list[int]:
    return sorted(set(days))


WorkingDays = Annotated[list[Weekday], Field(min_length=1, max_length=7), AfterValidator(_sorted_unique)]
Role = Literal["owner", "member", "viewer"]


class WorkspaceCreate(BaseModel):
    name: Name
    slug: Slug
    working_days: WorkingDays = [1, 2, 3, 4, 5]


class WorkspaceUpdate(BaseModel):
    """Owner-only settings. Send only the fields you want to change."""

    name: Name | None = None
    slug: Slug | None = None
    working_days: WorkingDays | None = None


class WorkspaceOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    working_days: list[int]
    hours_per_day: float
    role: Role


class HolidayIn(BaseModel):
    date: dt.date
    name: Name


class HolidayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    date: dt.date = Field(validation_alias="holiday_date")
    name: str
