from typing import Any, Dict, List, Optional, Tuple
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator, ConfigDict, model_validator
from datetime import datetime
import json


class ScoreResult(BaseModel):
    """
    Model representing the Big Five personality scores (v1.2).
    
    Contains both domain scores (o, c, e, a, n) and individual facet scores.
    All scores are T-scores, which typically range from 0 to 100 with a mean of 50
    and a standard deviation of 10.
    
    Note: All Decimal values are serialized as strings in JSON output as per API v1.2 specs.
    """
    # Domain scores (T-scores) - lowercase snake_case according to v1.2
    o: Decimal = Field(..., description="Openness T-Score")
    c: Decimal = Field(..., description="Conscientiousness T-Score")
    e: Decimal = Field(..., description="Extraversion T-Score")
    a: Decimal = Field(..., description="Agreeableness T-Score")
    n: Decimal = Field(..., description="Neuroticism T-Score")
    
    # Facet scores (T-scores for all 30 facets)
    facets: Dict[str, Decimal] = Field(
        ..., 
        description="Dictionary of Facet T-Scores with keys like o_f1, c_f2, etc."
    )
    
    # Override the model_json method to format Decimal values as strings
    def model_dump_json(self, **kwargs):
        """Convert model to JSON with Decimal values as strings"""
        # Get the model as a dict
        data = self.model_dump()
        
        # Convert all Decimal values to strings
        for key in ['o', 'c', 'e', 'a', 'n']:
            data[key] = str(data[key])
            
        # Convert all facet Decimal values to strings
        for key, value in data['facets'].items():
            data['facets'][key] = str(value)
            
        # Convert to JSON
        return json.dumps(data, **kwargs)

    @field_validator('facets')
    def check_facet_scores(cls, v):
        if not isinstance(v, dict):
            raise ValueError("Facets must be a dictionary")
        
        expected_facets = set()
        for domain in "ocean":  # lowercase domains per v1.2
            for i in range(1, 7):
                expected_facets.add(f"{domain}_f{i}")  # lowercase facets per v1.2
        
        missing_facets = expected_facets - set(v.keys())
        if missing_facets:
            raise ValueError(f"Missing facets: {missing_facets}")
            
        extra_facets = set(v.keys()) - expected_facets
        if extra_facets:
            # Not raising error, but this could be logged
            pass

        for key, score in v.items():
            if not isinstance(score, (int, float, Decimal)):
                raise ValueError(f"Facet {key} score must be a number, got {type(score)}")
            
            try:
                decimal_score = Decimal(score)
                # Valid range for T-scores is typically 0-100, but realistic range is 10-90
                if not (Decimal("0.0") <= decimal_score <= Decimal("100.0")):
                    raise ValueError(f"Facet {key} score {decimal_score} out of reasonable range (0-100)")
            except Exception as e:
                raise ValueError(f"Error validating facet {key} score {score}: {e}")
                 
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "o": "75.50",
                "c": "62.00",
                "e": "48.75",
                "a": "81.20",
                "n": "39.00",
                "facets": {
                    "o_f1": "72.10",
                    "o_f2": "78.30",
                    "o_f3": "70.50",
                    "o_f4": "76.20",
                    "o_f5": "79.10",
                    "o_f6": "74.80",
                    "c_f1": "61.30",
                    "c_f2": "63.70",
                    "c_f3": "60.20",
                    "c_f4": "64.50",
                    "c_f5": "59.80",
                    "c_f6": "62.40",
                    "e_f1": "49.20",
                    "e_f2": "47.80",
                    "e_f3": "50.30",
                    "e_f4": "46.90",
                    "e_f5": "51.40",
                    "e_f6": "48.10",
                    "a_f1": "80.40",
                    "a_f2": "82.60",
                    "a_f3": "79.70",
                    "a_f4": "83.10",
                    "a_f5": "78.90",
                    "a_f6": "81.80",
                    "n_f1": "38.20",
                    "n_f2": "40.30",
                    "n_f3": "37.40",
                    "n_f4": "41.70",
                    "n_f5": "36.90",
                    "n_f6": "39.50"
                }
            }
        }
    )


class AnalysisResponse(BaseModel):
    """
    Response model for personality analysis API (v1.2).
    
    Contains a message about the analysis status and the profile_id
    of the created or updated profile along with the calculated scores.
    """
    message: str = Field(..., description="Status message about the analysis")
    profile_id: str = Field(..., description="ID of the created or updated profile")
    scores: ScoreResult = Field(..., description="Calculated personality scores")
    
    # API yanıtı serileştirme sorunu için özel bir metod ekliyorum
    def model_dump_json(self, **kwargs):
        """Convert model to JSON with proper serialization"""
        # Get the model as a dict
        data = self.model_dump()
        
        # profile_id'yi kesinlikle string olarak garanti altına alalım
        if 'profile_id' in data:
            data['profile_id'] = str(data['profile_id'])
        
        # scores içindeki domain ve facet'leri de string olarak garanti altına alalım
        # Bu kodlar ScoreResult.model_dump_json metodunu çalıştırmayabilir
        if 'scores' in data:
            for key in ['o', 'c', 'e', 'a', 'n']:
                if key in data['scores']:
                    data['scores'][key] = str(data['scores'][key])
            
            if 'facets' in data['scores']:
                for facet_key, facet_value in data['scores']['facets'].items():
                    data['scores']['facets'][facet_key] = str(facet_value)
            
        # Convert to JSON and ensure non-null values
        return json.dumps(data, **kwargs)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Personality profile successfully analyzed",
                "profile_id": "prof_12345abcde",
                "scores": {
                    "o": "75.50",
                    "c": "62.00",
                    "e": "48.75",
                    "a": "81.20",
                    "n": "39.00",
                    "facets": {
                        "o_f1": "72.10",
                        # ... other facets would be included ...
                        "n_f6": "39.50"
                    }
                }
            }
        }
    )


class ProfileResponse(BaseModel):
    """
    Response model for retrieving a personality profile (v1.2).
    
    Contains all profile information including profile_id, user_id,
    creation timestamp, and all personality scores (domain and facet levels).
    
    Note: All Decimal values are serialized as strings in JSON output as per API v1.2 specs.
    """
    profile_id: str = Field(..., description="Unique identifier for the profile")
    user_id: str = Field(..., description="ID of the user this profile belongs to")
    created: datetime = Field(..., description="Timestamp when the profile was created")
    
    # Domain scores
    o: Decimal = Field(..., description="Openness T-Score")
    c: Decimal = Field(..., description="Conscientiousness T-Score")
    e: Decimal = Field(..., description="Extraversion T-Score")
    a: Decimal = Field(..., description="Agreeableness T-Score")
    n: Decimal = Field(..., description="Neuroticism T-Score")
    
    # All individual facet scores (30 facets)
    o_f1: Decimal = Field(..., description="Openness Facet 1: Imagination")
    o_f2: Decimal = Field(..., description="Openness Facet 2: Artistic Interests")
    o_f3: Decimal = Field(..., description="Openness Facet 3: Emotionality")
    o_f4: Decimal = Field(..., description="Openness Facet 4: Adventurousness")
    o_f5: Decimal = Field(..., description="Openness Facet 5: Intellect")
    o_f6: Decimal = Field(..., description="Openness Facet 6: Liberalism")
    
    c_f1: Decimal = Field(..., description="Conscientiousness Facet 1: Self-Efficacy")
    c_f2: Decimal = Field(..., description="Conscientiousness Facet 2: Orderliness")
    c_f3: Decimal = Field(..., description="Conscientiousness Facet 3: Dutifulness")
    c_f4: Decimal = Field(..., description="Conscientiousness Facet 4: Achievement-Striving")
    c_f5: Decimal = Field(..., description="Conscientiousness Facet 5: Self-Discipline")
    c_f6: Decimal = Field(..., description="Conscientiousness Facet 6: Cautiousness")
    
    e_f1: Decimal = Field(..., description="Extraversion Facet 1: Friendliness")
    e_f2: Decimal = Field(..., description="Extraversion Facet 2: Gregariousness")
    e_f3: Decimal = Field(..., description="Extraversion Facet 3: Assertiveness")
    e_f4: Decimal = Field(..., description="Extraversion Facet 4: Activity Level")
    e_f5: Decimal = Field(..., description="Extraversion Facet 5: Excitement-Seeking")
    e_f6: Decimal = Field(..., description="Extraversion Facet 6: Cheerfulness")
    
    a_f1: Decimal = Field(..., description="Agreeableness Facet 1: Trust")
    a_f2: Decimal = Field(..., description="Agreeableness Facet 2: Morality")
    a_f3: Decimal = Field(..., description="Agreeableness Facet 3: Altruism")
    a_f4: Decimal = Field(..., description="Agreeableness Facet 4: Cooperation")
    a_f5: Decimal = Field(..., description="Agreeableness Facet 5: Modesty")
    a_f6: Decimal = Field(..., description="Agreeableness Facet 6: Sympathy")
    
    n_f1: Decimal = Field(..., description="Neuroticism Facet 1: Anxiety")
    n_f2: Decimal = Field(..., description="Neuroticism Facet 2: Anger")
    n_f3: Decimal = Field(..., description="Neuroticism Facet 3: Depression")
    n_f4: Decimal = Field(..., description="Neuroticism Facet 4: Self-Consciousness")
    n_f5: Decimal = Field(..., description="Neuroticism Facet 5: Immoderation")
    n_f6: Decimal = Field(..., description="Neuroticism Facet 6: Vulnerability")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "profile_id": "prof_12345abcde",
                "user_id": "user_abcde12345",
                "created": "2025-05-05T14:30:45Z",
                "o": "75.50",
                "c": "62.00",
                "e": "48.75",
                "a": "81.20",
                "n": "39.00",
                "o_f1": "72.10",
                "o_f2": "78.30",
                # ... other facets would be here ...
                "n_f6": "39.50"
            }
        }
    )


class ProfileAnalysisResult(BaseModel):
    """
    Result model for personality analysis process (v1.2).
    
    Contains both the profile_id of the created/updated profile
    and the calculated scores for API responses.
    """
    profile_id: str = Field(..., description="ID of the created or updated profile")
    scores: ScoreResult = Field(..., description="Calculated personality scores")
    
    # JSON serileştirme sorunu için özel bir metod ekledim - Burada profil ID'sinin doğru şekilde serileştirilmesini sağlıyoruz
    def model_dump_json(self, **kwargs):
        """Convert model to JSON with proper serialization"""
        # Get the model as a dict
        data = self.model_dump()
        
        # scores zaten ScoreResult sınıfında doğru şekilde serileştiriliyor
        # profile_id'yi string olarak garanti altına alalım
        if 'profile_id' in data:
            data['profile_id'] = str(data['profile_id'])
        
        # Convert to JSON
        return json.dumps(data, **kwargs)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "profile_id": "prof_12345abcde",
                "scores": {
                    "o": "75.50",
                    "c": "62.00",
                    "e": "48.75",
                    "a": "81.20",
                    "n": "39.00",
                    "facets": {
                        "o_f1": "72.10",
                        # ... other facets would be included ...
                        "n_f6": "39.50"
                    }
                }
            }
        }
    )


class ErrorDetail(BaseModel):
    """
    Error response model (v1.2).
    
    Used for standardized error responses across the API.
    """
    detail: str = Field(..., description="Detailed error message")
    error_code: Optional[str] = Field(None, description="Error code for programmatic handling")
    request_id: Optional[str] = Field(None, description="Request ID for tracking/debugging")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detail": "User ID not found in database",
                "error_code": "USER_NOT_FOUND",
                "request_id": "req_1234567890abcdef"
            }
        }
    )
