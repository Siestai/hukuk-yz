import uuid
from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: Literal["admin", "reviewer"]
