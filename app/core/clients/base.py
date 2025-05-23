from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union


class ILlmClient(ABC):
    """Abstract base class for language model clients."""
    
    @abstractmethod
    async def generate(self, prompt: str) -> str:
        """
        Generate a response from the language model.
        
        Args:
            prompt: The input prompt for the language model
            
        Returns:
            The generated text response
            
        Raises:
            ConnectionError: If there's an issue connecting to the LLM service
            ValueError: If the input or output format is invalid
            Exception: For any other errors during generation
        """
        pass


class IDatabaseClient(ABC):
    """Abstract base class for database clients."""
    
    @abstractmethod
    async def connect(self) -> None:
        """
        Establish a connection to the database.
        
        Raises:
            ConnectionError: If unable to connect to the database
            Exception: For any other errors during connection
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """
        Close the database connection.
        
        Raises:
            Exception: If there's an error during disconnection
        """
        pass
    
    @abstractmethod
    async def query_all(
        self, query: str, params: Optional[Union[List[Any], Dict[str, Any], Tuple[Any, ...]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a query and return all results.
        
        Args:
            query: SQL query string
            params: Query parameters for parameterized queries
            
        Returns:
            List of dictionaries representing query results
            
        Raises:
            ValueError: If the query is invalid
            ConnectionError: If the database connection is lost
            Exception: For any other database errors
        """
        pass
    
    @abstractmethod
    async def execute(
        self, query: str, params: Optional[Union[List[Any], Dict[str, Any], Tuple[Any, ...]]] = None
    ) -> int:
        """
        Execute a non-query SQL statement (INSERT, UPDATE, DELETE, etc).
        
        Args:
            query: SQL query string
            params: Query parameters for parameterized queries
            
        Returns:
            Number of affected rows
            
        Raises:
            ValueError: If the query is invalid
            ConnectionError: If the database connection is lost
            Exception: For any other database errors
        """
        pass
