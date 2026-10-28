from decimal import Decimal
from app.core.campaign import Category
from pydantic import BaseModel, Field, ConfigDict, StrictInt

class DonationInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    alias: str = Field(min_length=1, max_length=80)
    category: Category
    quantity: int = Field(strict=True, ge=1, le=10000)
    weight_kg: Decimal = Field(ge=0, le=10000, max_digits=8, decimal_places=3)

class Answers(BaseModel):
    answers: list[StrictInt] = Field(min_length=3, max_length=3)

class Redemption(BaseModel):
    token: str = Field(min_length=6, max_length=40)

class QuestionAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_index: StrictInt = Field(ge=0, le=2)
    answer: StrictInt = Field(ge=0, le=2)
