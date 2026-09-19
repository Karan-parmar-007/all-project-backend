# app/api/routes/health/health_schemas.py
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    postgres: str
    garage: str
    mongo: str
