"""
Recommendation API Schemas

This module defines the Pydantic models for the film recommendation API according to v1.2 specifications.
These schemas are used for serialization/deserialization of data in the API endpoints.
"""

from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ConfigDict

class FilmMetadata(BaseModel):
    """Base model for film metadata."""
    film_id: str = Field(..., description="Unique identifier for the film")
    title: str = Field(..., description="Title of the film")
    year: Optional[int] = Field(None, description="Release year of the film")
    genres: List[str] = Field(default_factory=list, description="List of genres for the film")
    rating: Optional[float] = Field(None, description="Average rating of the film")
    poster_url: Optional[str] = Field(None, description="URL to the film poster image")
    description: Optional[str] = Field(None, description="Brief description of the film")

class RecommendationRequest(BaseModel):
    """Request model for generating recommendations."""
    user_id: str = Field(..., description="User ID to generate recommendations for")

class RecommendationResponse(BaseModel):
    """Response model for film recommendations (v1.2).
    
    According to v1.2 spec, this model only returns the list of film IDs,
    not the full film metadata.
    """
    model_config = ConfigDict(json_encoders={datetime: lambda dt: dt.isoformat()})
    
    message: str = Field(..., description="Status message")
    user_id: str = Field(..., description="User ID the recommendations are for")
    generated_at: datetime = Field(..., description="When recommendations were generated")
    recommendation_id: str = Field(..., description="Unique ID for this recommendation set")
    film_ids: List[str] = Field(..., description="List of recommended film IDs")
    
    @property
    def film_count(self) -> int:
        """Get the number of recommended films"""
        return len(self.film_ids)

# This model is for internal use and administration only, not part of the v1.2 API
class RecommendationDetail(BaseModel):
    """Detailed model for a recommendation set, including full film data.
    
    Note: This is for internal/admin use only. According to v1.2 spec,
    the public API only returns film IDs, not full metadata.
    """
    recommendation_id: str = Field(..., description="Unique ID for this recommendation set")
    user_id: str = Field(..., description="User ID the recommendations are for")
    profile_id: Optional[str] = Field(None, description="Profile ID used for recommendations")
    generated_at: datetime = Field(..., description="When recommendations were generated")
    films: List[FilmMetadata] = Field(..., description="List of recommended films with metadata")
    
    def to_recommendation_response(self) -> RecommendationResponse:
        """Convert to the public API response model"""
        return RecommendationResponse(
            message="Film recommendations retrieved successfully",
            user_id=self.user_id,
            generated_at=self.generated_at,
            recommendation_id=self.recommendation_id,
            film_ids=[film.film_id for film in self.films]
        )
    
class RecommendationStatusResponse(BaseModel):
    """Response model for recommendation process status (v1.2)."""
    model_config = ConfigDict(json_encoders={datetime: lambda dt: dt.isoformat()})
    
    status: str = Field(..., description="Current status of the recommendation generation process (e.g., 'in_progress', 'completed', 'failed')")
    message: str = Field(..., description="Human-readable status message")
    percentage: int = Field(..., ge=0, le=100, description="Percentage completion (0-100)")
    stage: str = Field(..., description="Current processing stage")
    last_updated: datetime = Field(..., description="When status was last updated")
    error_details: Optional[str] = Field(None, description="Error details if status is 'failed'")
    recommendation_id: Optional[str] = Field(None, description="ID of the recommendation being generated, if available")
    user_id: str = Field(..., description="User ID the recommendation is for")

class RecommendationGenerateResponse(BaseModel):
    """Response model for initiating a recommendation generation process (v1.2)."""
    model_config = ConfigDict(json_encoders={datetime: lambda dt: dt.isoformat()})
    
    message: str = Field(..., description="Status message about the initiated process")
    process_id: str = Field(..., description="Unique ID for tracking the recommendation generation process")
    status: str = Field("in_progress", description="Initial status of the process")
    estimated_completion_seconds: int = Field(30, description="Estimated time to completion in seconds")
    user_id: str = Field(..., description="User ID the recommendations are for")

class ErrorDetail(BaseModel):
    """Model for API error responses."""
    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code for client handling")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")
