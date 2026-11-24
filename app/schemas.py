from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import MAX_TEXT_LENGTH


class SynthesisMode(str, Enum):
    base = "base"
    auto = "auto"


class TextRequest(BaseModel):
    text: str = Field(..., max_length=MAX_TEXT_LENGTH)

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Текст не должен быть пустым.")
        return value


class SynthesizeRequest(TextRequest):
    model_config = ConfigDict(extra="forbid")

    mode: SynthesisMode
    voice: str | None = None


class HealthResponse(BaseModel):
    status: str
    service: str
