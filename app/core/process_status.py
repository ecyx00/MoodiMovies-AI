"""
Process Status Manager Module

This module provides functionality for tracking and managing the status of asynchronous processes.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid
from loguru import logger

class ProcessStatusManager:
    """
    Manager for tracking the status of asynchronous processes.
    
    This implementation uses in-memory storage for process statuses.
    In a production environment, this should be replaced with a database-backed solution.
    """
    
    def __init__(self):
        """Initialize the process status manager with an empty in-memory store."""
        # In-memory storage: Dict[user_id/process_id, status_data]
        self._process_statuses: Dict[str, Dict[str, Any]] = {}
        # Index mapping user_id to their latest process_id
        self._user_latest_process: Dict[str, str] = {}
    
    async def initialize_process(
        self,
        process_id: str,
        user_id: str,
        process_type: str,
        status: str = "initialized",
        message: Optional[str] = None,
        percentage: int = 0,
        stage: Optional[str] = "initializing",
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Initialize a new process status.
        
        Args:
            process_id: Unique identifier for the process
            user_id: ID of the user who initiated the process
            process_type: Type of process (e.g., 'recommendation', 'analysis')
            status: Initial status of the process
            message: Human-readable status message
            percentage: Initial completion percentage (default: 0)
            stage: Initial processing stage
            data: Additional data to store with the status
            
        Returns:
            The initialized status data dictionary
        """
        # Create initial status data
        now = datetime.now()
        process_data = {
            "process_id": process_id,
            "user_id": user_id,
            "process_type": process_type,
            "status": status,
            "message": message or f"İşlem başlatıldı: {process_type}",
            "percentage": percentage,
            "stage": stage,
            "started_at": now,
            "updated_at": now,
            "data": data or {}
        }
        
        # Store in memory
        self._process_statuses[process_id] = process_data
        
        # Update user index - associate this user with their latest process
        if user_id:
            self._user_latest_process[user_id] = process_id
        
        logger.debug(f"Initialized process status for {process_id}, user: {user_id}, type: {process_type}")
        return process_data
        
    async def update_status(
        self,
        process_id: str,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        message: Optional[str] = None,
        percentage: Optional[int] = None,
        stage: Optional[str] = None,
        error_details: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Update the status of a process.
        
        Args:
            process_id: The ID of the process to update
            user_id: The ID of the user associated with the process
            status: Current status (e.g., 'in_progress', 'completed', 'failed')
            message: Human-readable status message
            percentage: Completion percentage (0-100)
            stage: Current processing stage
            error_details: Details of any error that occurred
            data: Additional data to store with the status
            
        Returns:
            The updated status data
        """
        # Check if the process exists
        if process_id not in self._process_statuses:
            # Create a new process status
            self._process_statuses[process_id] = {
                "process_id": process_id,
                "user_id": user_id,
                "status": "pending",
                "message": "Process pending",
                "percentage": 0,
                "stage": "initializing",
                "created_at": datetime.now(),
                "last_updated": datetime.now(),
                "error_details": None,
                "data": {}
            }
        
        # Get the current status
        status_data = self._process_statuses[process_id]
        
        # Update the fields if provided
        if user_id is not None:
            status_data["user_id"] = user_id
            # Update the user's latest process
            self._user_latest_process[user_id] = process_id
            
        if status is not None:
            status_data["status"] = status
            
        if message is not None:
            status_data["message"] = message
            
        if percentage is not None:
            status_data["percentage"] = max(0, min(100, percentage))  # Ensure 0-100 range
            
        if stage is not None:
            status_data["stage"] = stage
            
        if error_details is not None:
            status_data["error_details"] = error_details
            
        if data is not None:
            # Merge with existing data
            status_data["data"] = {**status_data.get("data", {}), **data}
        
        # Update the last_updated timestamp
        status_data["last_updated"] = datetime.now()
        
        # Store the updated status
        self._process_statuses[process_id] = status_data
        
        logger.debug(f"Updated status for process {process_id}: {status or status_data['status']}, " 
                    f"{percentage or status_data['percentage']}%, stage: {stage or status_data['stage']}")
        
        return status_data
    
    async def get_status(self, process_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a process by its ID.
        
        Args:
            process_id: The ID of the process
            
        Returns:
            The process status data if found, None otherwise
        """
        return self._process_statuses.get(process_id)
    
    async def get_user_latest_status(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of the latest process for a user.
        
        Args:
            user_id: The ID of the user
            
        Returns:
            The latest process status data if found, None otherwise
        """
        process_id = self._user_latest_process.get(user_id)
        
        if not process_id:
            return None
            
        return await self.get_status(process_id)
    
    async def get_active_processes_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all active processes for a user.
        
        Args:
            user_id: The ID of the user
            
        Returns:
            List of active process status data
        """
        active_processes = []
        
        for status_data in self._process_statuses.values():
            if status_data.get("user_id") == user_id and status_data.get("status") == "in_progress":
                active_processes.append(status_data)
                
        return active_processes
    
    async def create_process(
        self,
        user_id: Optional[str] = None,
        process_type: str = "recommendation",
        initial_status: str = "pending",
        initial_message: str = "Process pending",
        initial_stage: str = "initializing"
    ) -> str:
        """
        Create a new process and return its ID.
        
        Args:
            user_id: The ID of the user associated with the process
            process_type: The type of process (e.g., 'recommendation')
            initial_status: Initial status of the process
            initial_message: Initial status message
            initial_stage: Initial processing stage
            
        Returns:
            The ID of the created process
        """
        process_id = f"{process_type[:3].upper()}-{uuid.uuid4().hex[:8]}"
        
        await self.update_status(
            process_id=process_id,
            user_id=user_id,
            status=initial_status,
            message=initial_message,
            percentage=0,
            stage=initial_stage
        )
        
        logger.info(f"Created new {process_type} process {process_id} for user {user_id}")
        
        return process_id
    
    async def mark_process_completed(
        self,
        process_id: str,
        result_data: Optional[Dict[str, Any]] = None,
        completion_message: str = "Process completed successfully"
    ) -> Dict[str, Any]:
        """
        Mark a process as completed.
        
        Args:
            process_id: The ID of the process to mark as completed
            result_data: Data resulting from the process
            completion_message: Message indicating completion
            
        Returns:
            The updated status data
        """
        return await self.update_status(
            process_id=process_id,
            status="completed",
            message=completion_message,
            percentage=100,
            data=result_data
        )
    
    async def mark_process_failed(
        self,
        process_id: str,
        error_message: str,
        error_details: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Mark a process as failed.
        
        Args:
            process_id: The ID of the process to mark as failed
            error_message: Message indicating the failure
            error_details: Detailed error information
            
        Returns:
            The updated status data
        """
        return await self.update_status(
            process_id=process_id,
            status="failed",
            message=error_message,
            error_details=error_details
        )
