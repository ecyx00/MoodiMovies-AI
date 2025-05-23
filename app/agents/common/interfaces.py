from abc import ABC, abstractmethod
from typing import Any, Dict, List
from decimal import Decimal

from app.schemas.personality import ResponseDataItem
from app.schemas.personality_schemas import ScoreResult


class IScoreCalculator(ABC):
    """Interface for components that calculate personality scores."""
    
    @abstractmethod
    async def calculate_scores(self, responses: List[ResponseDataItem]) -> Dict[str, Any]:
        """
        Calculate personality scores from test responses.
        
        Args:
            responses: List of response data items from the personality test
            
        Returns:
            Dictionary containing calculated personality scores with lowercase keys
            (o, c, e, a, n, facets)
            
        Raises:
            Exception: If there's an error during score calculation
        """
        pass


class IDataFetcher(ABC):
    """Interface for components that fetch user data."""
    
    @abstractmethod
    async def fetch_data(self, user_id: str) -> List[ResponseDataItem]:
        """
        Fetch data for a specific user.
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            List of ResponseDataItem objects containing the user's test responses
            
        Raises:
            Exception: If there's an error fetching data
        """
        pass


class IValidator(ABC):
    """Interface for components that validate data."""
    
    @abstractmethod
    def validate(self, data: Dict[str, Any]) -> ScoreResult:
        """
        Validate personality scores and return validated version.
        
        Args:
            data: Dictionary containing personality scores with lowercase keys
                (o, c, e, a, n, facets)
            
        Returns:
            ScoreResult Pydantic model containing validated scores
            
        Raises:
            ValidationError: If validation fails
            Exception: For other validation errors
        """
        pass


class ISaver(ABC):
    """Interface for components that save data."""
    
    @abstractmethod
    async def save(self, user_id: str, data: ScoreResult) -> str:
        """
        Save data for a specific user.
        
        Args:
            user_id: Unique identifier for the user
            data: ScoreResult Pydantic model containing validated scores to save
            
        Returns:
            profile_id: Unique identifier for the saved profile
            
        Raises:
            Exception: If there's an error saving data
        """
        pass
