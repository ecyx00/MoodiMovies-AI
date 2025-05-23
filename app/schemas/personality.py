from typing import Any, Dict, List, Optional
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
import json


class ResponseDataItem(BaseModel):
    """
    Model representing a single response from a user to a personality question.
    
    Attributes:
        response_id: Unique identifier for the response record itself
        user_id: Unique identifier for the user
        question_id: Unique identifier for the question
        domain: The personality domain the question relates to (e.g., 'O', 'C')
        facet: The personality facet number the question relates to (e.g., 1-6)
        facet_code: The specific code for the facet (e.g., 'O_F1')
        reverse_scored: Boolean indicating if the score should be reversed
        answer_id: Unique identifier for the answer
        point: The numerical point value associated with the answer (e.g., 1-5)
    """
    response_id: str = Field(alias="RESPONSE_ID")
    user_id: str = Field(alias="USER_ID")
    question_id: str = Field(alias="QUESTION_ID")
    domain: str = Field(alias="DOMAIN")
    facet: int = Field(alias="FACET")
    facet_code: str = Field(alias="FACET_CODE")
    reverse_scored: bool = Field(alias="REVERSE_SCORED")
    answer_id: str = Field(alias="ANSWER_ID")
    point: int = Field(alias="POINT")
    
    model_config = ConfigDict(
        populate_by_name=True
    )


class GeminiScoreOutput(BaseModel):
    """
    Model representing the expected output structure from Gemini API.
    
    Contains both domain scores (O, C, E, A, N) and individual facet scores.
    All scores are T-scores, which typically range from 0 to 100 with a mean of 50
    and a standard deviation of 10.
    """
    # Domain scores (T-scores)
    O: Decimal = Field(..., description="Openness T-Score")
    C: Decimal = Field(..., description="Conscientiousness T-Score")
    E: Decimal = Field(..., description="Extraversion T-Score")
    A: Decimal = Field(..., description="Agreeableness T-Score")
    N: Decimal = Field(..., description="Neuroticism T-Score")
    
    # Facet scores (T-scores for all 30 facets)
    facets: Dict[str, Decimal] = Field(..., description="Dictionary of Facet T-Scores")

    @field_validator('facets')
    def check_facet_scores(cls, v):
        if not isinstance(v, dict):
            raise ValueError("Facets must be a dictionary")
        
        expected_facets = set()
        for domain in "OCEAN":
            for i in range(1, 7):
                expected_facets.add(f"{domain}_F{i}")
        
        missing_facets = expected_facets - set(v.keys())
        if missing_facets:
            raise ValueError(f"Missing facets: {missing_facets}")
            
        extra_facets = set(v.keys()) - expected_facets
        if extra_facets:
            # Log warning for extra facets but don't necessarily fail validation,
            # as they might be ignored later.
            # Consider adding logging here if needed.
            pass # Or raise ValueError(f"Unexpected facets found: {extra_facets}")

        for key, score in v.items():
            # Allow int/float initially, Pydantic will coerce to Decimal if possible
            # But perform validation on the Decimal value
            if not isinstance(score, (int, float, Decimal)):
                raise ValueError(f"Facet {key} score must be a number, got {type(score)}")
            try:
                decimal_score = Decimal(score) # Convert to Decimal for comparison
                # Basic range check (can be more specific if needed)
                # Using Decimal for comparison
                if not (Decimal("0.0") <= decimal_score <= Decimal("100.0")):
                     raise ValueError(f"Facet {key} score {decimal_score} out of reasonable range (0-100)")
            except Exception as e:
                 raise ValueError(f"Error converting or validating facet {key} score {score}: {e}")
                 
        return v # Return original dict, Pydantic handles final type coercion

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "O": "75.50",
                "C": "62.00",
                "E": "48.75",
                "A": "81.20",
                "N": "39.00",
                "facets": {
                    "O_F1": "72.10",
                    "O_F2": "78.30",
                    # ... other facets ...
                    "N_F6": "41.50"
                }
            }
        }
    )


class PersonalityProfileData(BaseModel):
    """
    Complete personality profile data for a user.
    
    Contains domain scores and facet scores as calculated and validated by the LLM.
    """
    # User ID for reference
    user_id: str
    
    # Scores from the Gemini API
    scores: GeminiScoreOutput
    
    @classmethod
    def from_gemini_output(cls, user_id: str, gemini_output: GeminiScoreOutput) -> "PersonalityProfileData":
        """
        Create a profile from Gemini output scores.
        
        Args:
            user_id: Unique identifier for the user
            gemini_output: Validated GeminiScoreOutput with domain and facet scores
            
        Returns:
            A PersonalityProfileData instance
        """
        return cls(
            user_id=user_id,
            scores=gemini_output
        )


class AnalysisRequest(BaseModel):
    """
    Request model for personality analysis.
    """
    user_id: str = Field(alias="userId")
    
    model_config = ConfigDict(
        populate_by_name=True
    )


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
                "userId": "12345",
                "message": "Personality profile analysis started",
                "status": "processing"
            }
        }
    )
