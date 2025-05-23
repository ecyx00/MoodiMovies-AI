"""
Webhook API Schemas

This module defines the Pydantic models for webhook configuration and events.
These schemas are used for serialization/deserialization of data in the webhook API endpoints.
"""

from typing import List, Dict, Any, Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field, AnyHttpUrl, validator, ConfigDict
from enum import Enum


class WebhookEventType(str, Enum):
    """Supported webhook event types."""
    PERSONALITY_ANALYSIS_COMPLETED = "personality_analysis_completed"
    RECOMMENDATIONS_GENERATED = "recommendations_generated"
    RECOMMENDATION_FAILED = "recommendation_failed"
    PROFILE_UPDATED = "profile_updated"
    SYSTEM_STATUS = "system_status"


class WebhookConfigurationRequest(BaseModel):
    """Request model for webhook configuration."""
    event_type: WebhookEventType = Field(
        ..., 
        description="Event type this webhook should be triggered for"
    )
    callback_url: AnyHttpUrl = Field(
        ..., 
        description="URL to send webhook events to"
    )
    user_id: Optional[str] = Field(
        None, 
        description="User ID to filter events for (leave empty for system-wide events)"
    )
    secret_token: Optional[str] = Field(
        None, 
        description="Secret token for webhook signature verification"
    )
    description: Optional[str] = Field(
        None, 
        description="Optional description of this webhook configuration"
    )
    is_active: bool = Field(
        True, 
        description="Whether this webhook is active and should receive events"
    )
    
    @validator('callback_url')
    def validate_callback_url(cls, v):
        """Ensure callback URL is valid."""
        if not str(v).startswith(('http://', 'https://')):
            raise ValueError("callback_url must start with http:// or https://")
        return v


class WebhookConfigurationResponse(BaseModel):
    """Response model for webhook configuration."""
    model_config = ConfigDict(json_encoders={datetime: lambda dt: dt.isoformat()})
    
    webhook_id: str = Field(..., description="Unique identifier for this webhook configuration")
    event_type: WebhookEventType = Field(..., description="Event type this webhook is triggered for")
    callback_url: AnyHttpUrl = Field(..., description="URL to send webhook events to")
    user_id: Optional[str] = Field(None, description="User ID to filter events for")
    description: Optional[str] = Field(None, description="Description of this webhook configuration")
    is_active: bool = Field(..., description="Whether this webhook is active")
    created_at: datetime = Field(..., description="When this webhook was created")
    updated_at: datetime = Field(..., description="When this webhook was last updated")
    
    # Intentionally exclude secret_token from response for security


class WebhookConfigurationUpdateRequest(BaseModel):
    """Request model for updating a webhook configuration."""
    callback_url: Optional[AnyHttpUrl] = Field(None, description="URL to send webhook events to")
    secret_token: Optional[str] = Field(None, description="Secret token for webhook signature verification")
    description: Optional[str] = Field(None, description="Description of this webhook configuration")
    is_active: Optional[bool] = Field(None, description="Whether this webhook is active")
    
    @validator('callback_url')
    def validate_callback_url(cls, v):
        """Ensure callback URL is valid if provided."""
        if v is not None and not str(v).startswith(('http://', 'https://')):
            raise ValueError("callback_url must start with http:// or https://")
        return v


class WebhookEvent(BaseModel):
    """Base model for webhook event payloads."""
    model_config = ConfigDict(json_encoders={datetime: lambda dt: dt.isoformat()})
    
    event_id: str = Field(..., description="Unique identifier for this event")
    event_type: WebhookEventType = Field(..., description="Type of event")
    timestamp: datetime = Field(..., description="When the event occurred")
    user_id: Optional[str] = Field(None, description="User ID associated with the event")
    data: Dict[str, Any] = Field(default_factory=dict, description="Event-specific data")
