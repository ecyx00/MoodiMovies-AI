from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict


class AnalysisResponse(BaseModel):
    """
    Response model for personality analysis API.
    """
    user_id: str = Field(alias="userId")
    message: str
    status: str
    
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "userId": "user-123",
                "message": "Personality profile analysis started",
                "status": "processing"
            }
        }
    )


class AnalysisStatusResponse(BaseModel):
    """
    Response model for checking the status of an analysis.
    """
    user_id: str = Field(alias="userId")
    message: str
    status: str
    completed: bool
    
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "userId": "user-123",
                "message": "Personality profile analysis completed",
                "status": "success",
                "completed": True
            }
        }
    )


class ErrorResponse(BaseModel):
    """
    Response model for error responses.
    """
    detail: str
    error_code: Optional[str] = Field(None, alias="errorCode")
    
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "detail": "An error occurred while processing the request",
                "errorCode": "INTERNAL_SERVER_ERROR"
            }
        }
    )


class PersonalityScores(BaseModel):
    """
    Model representing personality scores.
    """
    openness: float
    conscientiousness: float
    extraversion: float
    agreeableness: float
    neuroticism: float
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "openness": 7.5,
                "conscientiousness": 6.2,
                "extraversion": 4.8,
                "agreeableness": 8.1,
                "neuroticism": 3.9
            }
        }
    )


class PersonalityProfileResponse(BaseModel):
    """
    Response model for retrieving a personality profile.
    """
    user_id: str = Field(alias="userId")
    scores: PersonalityScores
    normalized_scores: Optional[Dict[str, float]] = Field(None, alias="normalizedScores")
    created_at: str = Field(alias="createdAt")
    
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "userId": "user-123",
                "scores": {
                    "openness": 7.5,
                    "conscientiousness": 6.2,
                    "extraversion": 4.8,
                    "agreeableness": 8.1,
                    "neuroticism": 3.9
                },
                "normalizedScores": {
                    "openness": 1.0,
                    "conscientiousness": 0.48,
                    "extraversion": -0.08,
                    "agreeableness": 1.24,
                    "neuroticism": -0.44
                },
                "createdAt": "2023-04-01T12:34:56Z"
            }
        }
    )
