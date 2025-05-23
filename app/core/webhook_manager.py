"""
Webhook Manager Module

This module provides functionality for managing webhook configurations and sending webhook events.
"""

import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
import hashlib
import hmac
import json
import httpx
from loguru import logger
from pydantic import AnyHttpUrl

from app.schemas.webhook_schemas import (
    WebhookEventType, 
    WebhookConfigurationRequest,
    WebhookConfigurationResponse
)


class WebhookManager:
    """
    Manager for webhook configurations and event delivery.
    
    This implementation uses in-memory storage for webhook configurations.
    In a production environment, this should be replaced with a database-backed solution.
    """
    
    def __init__(self):
        """Initialize the webhook manager with an empty in-memory store."""
        # In-memory storage: Dict[webhook_id, webhook_data]
        self._webhooks: Dict[str, Dict[str, Any]] = {}
    
    async def create_webhook(self, 
                      webhook_config: WebhookConfigurationRequest) -> WebhookConfigurationResponse:
        """
        Create a new webhook configuration.
        
        Args:
            webhook_config: The webhook configuration data
            
        Returns:
            WebhookConfigurationResponse with the created webhook details
        """
        # Generate a new webhook ID
        webhook_id = f"wh_{uuid.uuid4().hex}"
        
        # Get the current timestamp
        now = datetime.now()
        
        # Create the webhook record
        webhook_data = {
            "webhook_id": webhook_id,
            "event_type": webhook_config.event_type,
            "callback_url": str(webhook_config.callback_url),
            "user_id": webhook_config.user_id,
            "secret_token": webhook_config.secret_token,
            "description": webhook_config.description,
            "is_active": webhook_config.is_active,
            "created_at": now,
            "updated_at": now
        }
        
        # Store the webhook
        self._webhooks[webhook_id] = webhook_data
        
        logger.info(f"Created webhook {webhook_id} for event type {webhook_config.event_type}")
        
        # Return the response (excluding secret_token)
        return WebhookConfigurationResponse(
            webhook_id=webhook_id,
            event_type=webhook_config.event_type,
            callback_url=webhook_config.callback_url,
            user_id=webhook_config.user_id,
            description=webhook_config.description,
            is_active=webhook_config.is_active,
            created_at=now,
            updated_at=now
        )
    
    async def get_webhooks(self, 
                    event_type: Optional[WebhookEventType] = None,
                    user_id: Optional[str] = None) -> List[WebhookConfigurationResponse]:
        """
        Get webhook configurations matching the specified filters.
        
        Args:
            event_type: Optional event type to filter by
            user_id: Optional user ID to filter by
            
        Returns:
            List of webhook configurations matching the filters
        """
        results = []
        
        for webhook_data in self._webhooks.values():
            # Apply filters
            if event_type and webhook_data["event_type"] != event_type:
                continue
                
            if user_id and webhook_data["user_id"] != user_id:
                continue
            
            # Construct response object (excluding secret_token)
            webhook_response = WebhookConfigurationResponse(
                webhook_id=webhook_data["webhook_id"],
                event_type=webhook_data["event_type"],
                callback_url=webhook_data["callback_url"],
                user_id=webhook_data["user_id"],
                description=webhook_data["description"],
                is_active=webhook_data["is_active"],
                created_at=webhook_data["created_at"],
                updated_at=webhook_data["updated_at"]
            )
            
            results.append(webhook_response)
        
        return results
    
    async def get_webhook_by_id(self, webhook_id: str) -> Optional[WebhookConfigurationResponse]:
        """
        Get a webhook configuration by ID.
        
        Args:
            webhook_id: The ID of the webhook to retrieve
            
        Returns:
            The webhook configuration if found, None otherwise
        """
        webhook_data = self._webhooks.get(webhook_id)
        
        if not webhook_data:
            return None
        
        # Construct response object (excluding secret_token)
        return WebhookConfigurationResponse(
            webhook_id=webhook_data["webhook_id"],
            event_type=webhook_data["event_type"],
            callback_url=webhook_data["callback_url"],
            user_id=webhook_data["user_id"],
            description=webhook_data["description"],
            is_active=webhook_data["is_active"],
            created_at=webhook_data["created_at"],
            updated_at=webhook_data["updated_at"]
        )
    
    async def update_webhook(self, 
                      webhook_id: str,
                      callback_url: Optional[AnyHttpUrl] = None,
                      secret_token: Optional[str] = None,
                      description: Optional[str] = None,
                      is_active: Optional[bool] = None) -> Optional[WebhookConfigurationResponse]:
        """
        Update a webhook configuration.
        
        Args:
            webhook_id: The ID of the webhook to update
            callback_url: New callback URL (optional)
            secret_token: New secret token (optional)
            description: New description (optional)
            is_active: New active status (optional)
            
        Returns:
            Updated webhook configuration if found, None otherwise
        """
        webhook_data = self._webhooks.get(webhook_id)
        
        if not webhook_data:
            return None
        
        # Update fields if provided
        if callback_url is not None:
            webhook_data["callback_url"] = str(callback_url)
            
        if secret_token is not None:
            webhook_data["secret_token"] = secret_token
            
        if description is not None:
            webhook_data["description"] = description
            
        if is_active is not None:
            webhook_data["is_active"] = is_active
        
        # Update the 'updated_at' timestamp
        webhook_data["updated_at"] = datetime.now()
        
        # Store the updated webhook
        self._webhooks[webhook_id] = webhook_data
        
        logger.info(f"Updated webhook {webhook_id}")
        
        # Return the updated webhook (excluding secret_token)
        return WebhookConfigurationResponse(
            webhook_id=webhook_data["webhook_id"],
            event_type=webhook_data["event_type"],
            callback_url=webhook_data["callback_url"],
            user_id=webhook_data["user_id"],
            description=webhook_data["description"],
            is_active=webhook_data["is_active"],
            created_at=webhook_data["created_at"],
            updated_at=webhook_data["updated_at"]
        )
    
    async def delete_webhook(self, webhook_id: str) -> bool:
        """
        Delete a webhook configuration.
        
        Args:
            webhook_id: The ID of the webhook to delete
            
        Returns:
            True if the webhook was found and deleted, False otherwise
        """
        if webhook_id not in self._webhooks:
            return False
        
        # Delete the webhook
        del self._webhooks[webhook_id]
        
        logger.info(f"Deleted webhook {webhook_id}")
        
        return True
    
    async def send_webhook_event(self, 
                          event_type: WebhookEventType,
                          user_id: Optional[str] = None,
                          data: Optional[Dict[str, Any]] = None) -> List[bool]:
        """
        Send an event to all matching and active webhooks.
        
        Args:
            event_type: The type of event to send
            user_id: The user ID associated with the event (if any)
            data: Event-specific data to include in the payload
            
        Returns:
            List of booleans indicating success or failure for each matching webhook
        """
        # Create event payload
        event_id = f"evt_{uuid.uuid4().hex}"
        timestamp = datetime.now()
        
        event_payload = {
            "event_id": event_id,
            "event_type": event_type,
            "timestamp": timestamp.isoformat(),
            "user_id": user_id,
            "data": data or {}
        }
        
        # Find matching webhooks
        matching_webhooks = []
        for webhook in self._webhooks.values():
            # Skip inactive webhooks
            if not webhook["is_active"]:
                continue
                
            # Skip webhooks for different event types
            if webhook["event_type"] != event_type:
                continue
                
            # Filter by user_id if specified in the webhook
            if webhook["user_id"] and webhook["user_id"] != user_id:
                continue
                
            matching_webhooks.append(webhook)
        
        # Send the event to each matching webhook
        results = []
        
        for webhook in matching_webhooks:
            success = await self._send_event_to_webhook(
                webhook, 
                event_payload
            )
            results.append(success)
        
        return results
    
    async def _send_event_to_webhook(self, 
                              webhook: Dict[str, Any], 
                              payload: Dict[str, Any]) -> bool:
        """
        Send an event to a specific webhook.
        
        Args:
            webhook: The webhook configuration
            payload: The event payload
            
        Returns:
            True if the event was successfully sent, False otherwise
        """
        try:
            # Convert payload to JSON
            payload_json = json.dumps(payload)
            
            # Prepare headers
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "MoodieMovie-Webhook/1.0"
            }
            
            # Add signature if secret is available
            if webhook.get("secret_token"):
                signature = self._generate_signature(
                    payload_json, 
                    webhook["secret_token"]
                )
                headers["X-Webhook-Signature"] = signature
            
            # Send the request
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    webhook["callback_url"],
                    content=payload_json,
                    headers=headers
                )
                
            # Check if the request was successful
            if response.status_code < 300:
                logger.info(f"Successfully sent event to webhook {webhook['webhook_id']}")
                return True
            else:
                logger.warning(f"Failed to send event to webhook {webhook['webhook_id']}: Status {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending event to webhook {webhook['webhook_id']}: {str(e)}")
            return False
    
    def _generate_signature(self, payload: str, secret: str) -> str:
        """
        Generate a signature for the webhook payload.
        
        Args:
            payload: The JSON payload as a string
            secret: The secret token for the webhook
            
        Returns:
            HMAC SHA-256 signature as a hexadecimal string
        """
        hmac_obj = hmac.new(
            key=secret.encode('utf-8'),
            msg=payload.encode('utf-8'),
            digestmod=hashlib.sha256
        )
        return hmac_obj.hexdigest()
