import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TypeVar, Generic

from loguru import logger
from app.core.clients.base import IDatabaseClient

T = TypeVar('T')  # Generic type for the entity being stored/retrieved


class BaseRepository(ABC, Generic[T]):
    """
    Base repository class providing common database operations.
    
    This abstract class defines the interface for repository classes
    and provides common functionality for database operations.
    """
    
    def __init__(self, db_client: IDatabaseClient):
        """
        Initialize the repository with a database client.
        
        Args:
            db_client: Database client implementing IDatabaseClient
        """
        self.db_client = db_client
    
    @abstractmethod
    async def get_by_id(self, id: str) -> Optional[T]:
        """
        Get an entity by its ID.
        
        Args:
            id: Unique identifier for the entity
            
        Returns:
            The entity if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def create(self, entity: T) -> str:
        """
        Create a new entity in the database.
        
        Args:
            entity: The entity to create
            
        Returns:
            The ID of the created entity
        """
        pass
    
    @abstractmethod
    async def update(self, id: str, entity: T) -> bool:
        """
        Update an existing entity in the database.
        
        Args:
            id: Unique identifier for the entity
            entity: Updated entity data
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def delete(self, id: str) -> bool:
        """
        Delete an entity from the database.
        
        Args:
            id: Unique identifier for the entity
            
        Returns:
            True if successful, False otherwise
        """
        pass
