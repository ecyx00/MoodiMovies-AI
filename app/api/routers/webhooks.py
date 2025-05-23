"""
Webhook Router

This module implements the API endpoints for webhook configuration management.
It provides endpoints for creating, retrieving, updating, and deleting webhooks.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Response, status
from loguru import logger
import uuid

# Bağımlılık enjeksiyon sağlayıcıları
from app.core.dependencies import get_webhook_manager
from app.security.api_key import verify_api_key

# Pydantic şemaları
from app.schemas.webhook_schemas import (
    WebhookEventType,
    WebhookConfigurationRequest,
    WebhookConfigurationResponse,
    WebhookConfigurationUpdateRequest
)
from app.schemas.recommendation_schemas import ErrorDetail

# Manager sınıfı (tip tanımları için)
from app.core.webhook_manager import WebhookManager

router = APIRouter(
    prefix="/api/v1",
    tags=["Webhooks"],
    dependencies=[Depends(verify_api_key)]  # Apply security at router level
)


@router.post(
    "/webhooks/configure",
    response_model=WebhookConfigurationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"model": WebhookConfigurationResponse, "description": "Webhook configured successfully"},
        400: {"model": ErrorDetail, "description": "Invalid webhook configuration"},
        500: {"model": ErrorDetail, "description": "Internal server error"}
    }
)
async def configure_webhook(
    webhook_config: WebhookConfigurationRequest,
    webhook_manager: WebhookManager = Depends(get_webhook_manager)
):
    """
    Configure a new webhook.
    
    Creates a new webhook configuration that will receive events of the specified type.
    If a user_id is provided, only events for that user will be sent to this webhook.
    """
    # Generate a request ID for tracking
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    logger.info(f"[{request_id}] Configuring new webhook for event type: {webhook_config.event_type}")
    
    try:
        # Create the webhook
        webhook = await webhook_manager.create_webhook(webhook_config)
        
        logger.info(f"[{request_id}] Webhook configured successfully with ID: {webhook.webhook_id}")
        return webhook
        
    except ValueError as e:
        # Handle validation errors
        error_detail = ErrorDetail(
            detail=f"Invalid webhook configuration: {str(e)}",
            error_code="INVALID_WEBHOOK_CONFIG",
            request_id=request_id
        )
        logger.error(f"[{request_id}] {error_detail.detail}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_detail.dict())
        
    except Exception as e:
        # Handle unexpected errors
        error_detail = ErrorDetail(
            detail=f"Error configuring webhook",
            error_code="INTERNAL_SERVER_ERROR",
            request_id=request_id
        )
        logger.error(f"[{request_id}] {error_detail.detail}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_detail.dict())


@router.get(
    "/webhooks",
    response_model=List[WebhookConfigurationResponse],
    responses={
        200: {"model": List[WebhookConfigurationResponse], "description": "List of webhooks"},
        500: {"model": ErrorDetail, "description": "Internal server error"}
    }
)
async def list_webhooks(
    event_type: Optional[WebhookEventType] = Query(None, description="Filter by event type"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    webhook_manager: WebhookManager = Depends(get_webhook_manager)
):
    """
    List webhook configurations.
    
    Returns all webhook configurations matching the specified filters.
    If no filters are provided, returns all webhook configurations.
    """
    # Generate a request ID for tracking
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    logger.info(f"[{request_id}] Listing webhooks (event_type: {event_type}, user_id: {user_id})")
    
    try:
        # Get webhooks matching the filters
        webhooks = await webhook_manager.get_webhooks(event_type=event_type, user_id=user_id)
        
        logger.info(f"[{request_id}] Retrieved {len(webhooks)} webhooks")
        return webhooks
        
    except Exception as e:
        # Handle unexpected errors
        error_detail = ErrorDetail(
            detail=f"Error listing webhooks",
            error_code="INTERNAL_SERVER_ERROR",
            request_id=request_id
        )
        logger.error(f"[{request_id}] {error_detail.detail}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_detail.dict())


@router.get(
    "/webhooks/{webhook_id}",
    response_model=WebhookConfigurationResponse,
    responses={
        200: {"model": WebhookConfigurationResponse, "description": "Webhook details"},
        404: {"model": ErrorDetail, "description": "Webhook not found"},
        500: {"model": ErrorDetail, "description": "Internal server error"}
    }
)
async def get_webhook(
    webhook_id: str = Path(..., description="ID of the webhook to retrieve"),
    webhook_manager: WebhookManager = Depends(get_webhook_manager)
):
    """
    Get details of a specific webhook.
    
    Returns the configuration details of the specified webhook.
    """
    # Generate a request ID for tracking
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    logger.info(f"[{request_id}] Getting webhook with ID: {webhook_id}")
    
    try:
        # Get the webhook
        webhook = await webhook_manager.get_webhook_by_id(webhook_id)
        
        if not webhook:
            error_detail = ErrorDetail(
                detail=f"Webhook not found with ID: {webhook_id}",
                error_code="WEBHOOK_NOT_FOUND",
                request_id=request_id
            )
            logger.warning(f"[{request_id}] {error_detail.detail}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_detail.dict())
        
        logger.info(f"[{request_id}] Successfully retrieved webhook: {webhook_id}")
        return webhook
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
        
    except Exception as e:
        # Handle unexpected errors
        error_detail = ErrorDetail(
            detail=f"Error retrieving webhook",
            error_code="INTERNAL_SERVER_ERROR",
            request_id=request_id
        )
        logger.error(f"[{request_id}] {error_detail.detail}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_detail.dict())


@router.put(
    "/webhooks/{webhook_id}",
    response_model=WebhookConfigurationResponse,
    responses={
        200: {"model": WebhookConfigurationResponse, "description": "Webhook updated successfully"},
        404: {"model": ErrorDetail, "description": "Webhook not found"},
        400: {"model": ErrorDetail, "description": "Invalid webhook configuration"},
        500: {"model": ErrorDetail, "description": "Internal server error"}
    }
)
async def update_webhook(
    webhook_update: WebhookConfigurationUpdateRequest,
    webhook_id: str = Path(..., description="ID of the webhook to update"),
    webhook_manager: WebhookManager = Depends(get_webhook_manager)
):
    """
    Update a webhook configuration.
    
    Updates the specified fields of the webhook configuration.
    Only the provided fields will be updated.
    """
    # Generate a request ID for tracking
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    logger.info(f"[{request_id}] Updating webhook with ID: {webhook_id}")
    
    try:
        # Update the webhook
        updated_webhook = await webhook_manager.update_webhook(
            webhook_id,
            callback_url=webhook_update.callback_url,
            secret_token=webhook_update.secret_token,
            description=webhook_update.description,
            is_active=webhook_update.is_active
        )
        
        if not updated_webhook:
            error_detail = ErrorDetail(
                detail=f"Webhook not found with ID: {webhook_id}",
                error_code="WEBHOOK_NOT_FOUND",
                request_id=request_id
            )
            logger.warning(f"[{request_id}] {error_detail.detail}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_detail.dict())
        
        logger.info(f"[{request_id}] Successfully updated webhook: {webhook_id}")
        return updated_webhook
        
    except ValueError as e:
        # Handle validation errors
        error_detail = ErrorDetail(
            detail=f"Invalid webhook configuration: {str(e)}",
            error_code="INVALID_WEBHOOK_CONFIG",
            request_id=request_id
        )
        logger.error(f"[{request_id}] {error_detail.detail}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_detail.dict())
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
        
    except Exception as e:
        # Handle unexpected errors
        error_detail = ErrorDetail(
            detail=f"Error updating webhook",
            error_code="INTERNAL_SERVER_ERROR",
            request_id=request_id
        )
        logger.error(f"[{request_id}] {error_detail.detail}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_detail.dict())


@router.delete(
    "/webhooks/{webhook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Webhook deleted successfully"},
        404: {"model": ErrorDetail, "description": "Webhook not found"},
        500: {"model": ErrorDetail, "description": "Internal server error"}
    }
)
async def delete_webhook(
    webhook_id: str = Path(..., description="ID of the webhook to delete"),
    webhook_manager: WebhookManager = Depends(get_webhook_manager),
    response: Response = None
):
    """
    Delete a webhook configuration.
    
    Deletes the specified webhook configuration.
    Returns 204 No Content on success.
    """
    # Generate a request ID for tracking
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    logger.info(f"[{request_id}] Deleting webhook with ID: {webhook_id}")
    
    try:
        # Delete the webhook
        deleted = await webhook_manager.delete_webhook(webhook_id)
        
        if not deleted:
            error_detail = ErrorDetail(
                detail=f"Webhook not found with ID: {webhook_id}",
                error_code="WEBHOOK_NOT_FOUND",
                request_id=request_id
            )
            logger.warning(f"[{request_id}] {error_detail.detail}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_detail.dict())
        
        logger.info(f"[{request_id}] Successfully deleted webhook: {webhook_id}")
        
        # Return 204 No Content (already set by FastAPI based on the status_code parameter)
        return None
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
        
    except Exception as e:
        # Handle unexpected errors
        error_detail = ErrorDetail(
            detail=f"Error deleting webhook",
            error_code="INTERNAL_SERVER_ERROR",
            request_id=request_id
        )
        logger.error(f"[{request_id}] {error_detail.detail}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_detail.dict())
