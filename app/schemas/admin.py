from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class CreditosRequeridosUpdate(BaseModel):
    creditos_requeridos: Decimal = Field(gt=0)

    @field_validator("creditos_requeridos")
    @classmethod
    def validate_credit_step(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value % Decimal("0.5") != 0:
            raise ValueError("Los créditos requeridos deben avanzar en pasos de 0,5.")
        return value
