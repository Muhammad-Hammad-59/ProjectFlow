"""Request and response models for auth. `Email` is shared: it trims and lowercases."""
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

Email = Annotated[EmailStr, StringConstraints(strip_whitespace=True, to_lower=True)]


class SignupIn(BaseModel):
    email: Email
    password: str = Field(min_length=8, max_length=128)
    full_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class LoginIn(BaseModel):
    email: Email
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    avatar_url: str | None


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserOut
