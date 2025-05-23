import asyncio
import json
import os
from typing import Any, Dict, List, Optional, Set, Tuple
from decimal import Decimal

from loguru import logger

from app.agents.common.interfaces import IScoreCalculator, IDataFetcher, IValidator, ISaver
from app.core.clients.base import ILlmClient
from app.core.config import Settings
from app.db.repositories import ResponseRepository, ProfileRepository
from app.schemas.personality import ResponseDataItem
from app.schemas.personality_schemas import ScoreResult, ProfileResponse, ProfileAnalysisResult


class PersonalityProfilerError(Exception):
    """Base exception for personality profiler errors."""
    pass


class PersonalityDataFetcherError(PersonalityProfilerError):
    """Exception for errors in fetching personality data."""
    pass


class ScoreCalculationError(PersonalityProfilerError):
    """Exception for errors in calculating personality scores."""
    pass


class ValidationError(PersonalityProfilerError):
    """Exception for errors in validating personality scores."""
    pass


class ProfileSavingError(PersonalityProfilerError):
    """Exception for errors in saving personality profiles."""
    pass


class PersonalityDataFetcher(IDataFetcher):
    """Component for fetching and structuring personality response data."""
    
    def __init__(self, repository: ResponseRepository):
        """
        Initialize the data fetcher with a repository.
        
        Args:
            repository: Repository for accessing user responses
        """
        self.repository = repository

    async def fetch_data(self, user_id: str) -> List[ResponseDataItem]:
        """
        Fetch and structure personality response data for a user.
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            List of structured response data items
            
        Raises:
            PersonalityDataFetcherError: If there's an error fetching or processing data
        """
        try:
            logger.info(f"Fetching personality response data for user: {user_id}")
            
            # Get raw data from repository
            raw_responses = await self.repository.get_user_responses(user_id)
            
            if not raw_responses:
                logger.warning(f"No responses found for user: {user_id}")
                return []
            
            # ResponseRepository'den gelen yanıtlar zaten ResponseDataItem nesneleri
            # Ancak bazı durumlar için bir kontrol ekleyelim
            structured_responses = []
            for response in raw_responses:
                try:
                    # Eğer yanıt zaten ResponseDataItem ise doğrudan kullan
                    if isinstance(response, ResponseDataItem):
                        structured_responses.append(response)
                    # Dict ise ResponseDataItem'a dönüştür
                    elif isinstance(response, dict):
                        item = ResponseDataItem(**response)
                        structured_responses.append(item)
                    else:
                        logger.warning(f"Unexpected response type: {type(response)}, skipping this response")
                        continue
                    
                except Exception as e:
                    logger.warning(f"Error processing response: {str(e)}, skipping this response")
                    continue
            
            logger.info(f"Processed {len(structured_responses)} responses for user: {user_id}")
            return structured_responses
            
        except Exception as e:
            error_msg = f"Error fetching personality data for user {user_id}: {str(e)}"
            logger.error(error_msg)
            raise PersonalityDataFetcherError(error_msg)


# GeminiScoreCalculator class has been replaced by PythonScoreCalculator
# This implementation used Gemini API to calculate T-scores, but now we use
# local Python-based calculation for better reliability, speed, and cost-efficiency
    



class PersonalityResultValidator(IValidator):
    """Component for validating personality score results."""
    
    def __init__(self):
        """Initialize the result validator."""
        pass
    
    def validate(self, scores: Dict[str, Any]) -> ScoreResult:
        """
        Validate personality scores.
        
        Args:
            scores: Dictionary of personality scores to validate with lowercase keys
                   (o, c, e, a, n, facets) as per v1.2 API specification
            
        Returns:
            Validated ScoreResult Pydantic model
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            logger.info("Validating personality scores")
            
            # Validate expected structure before using Pydantic
            if not isinstance(scores, dict):
                raise ValidationError(f"Scores must be a dictionary, got {type(scores)}")
            
            # Check if all required domains are present (lowercase per v1.2 API)
            required_domains = {"o", "c", "e", "a", "n"}
            missing_domains = required_domains - set(scores.keys())
            if missing_domains:
                raise ValidationError(f"Missing required domains: {missing_domains}")
            
            # Check domain score types and ranges
            for domain in required_domains:
                if domain not in scores:
                    raise ValidationError(f"Missing domain: {domain}")
                
                domain_score = scores[domain]
                if not isinstance(domain_score, (int, float, Decimal)):
                    raise ValidationError(f"Domain {domain} score must be a number, got {type(domain_score)}")
                
                # Convert to Decimal for consistent comparison
                domain_score_decimal = Decimal(str(domain_score)) if not isinstance(domain_score, Decimal) else domain_score
                
                # Enforce score range 10-90 as per requirements
                if not (Decimal("10") <= domain_score_decimal <= Decimal("90")):
                    raise ValidationError(f"Domain {domain} score must be between 10 and 90, got {domain_score}")
            
            # Check if facets dictionary is present
            if "facets" not in scores:
                raise ValidationError("Missing 'facets' dictionary in scores")
            
            if not isinstance(scores["facets"], dict):
                raise ValidationError(f"Facets must be a dictionary, got {type(scores['facets'])}")
            
            # Check expected facets (6 for each of the 5 domains) - lowercase per v1.2 API
            expected_facets = set()
            for domain in required_domains:  # lowercase domains
                for i in range(1, 7):
                    expected_facets.add(f"{domain}_f{i}")  # lowercase facet codes
            
            # Check for missing facets
            facets = scores["facets"]
            missing_facets = expected_facets - set(facets.keys())
            if missing_facets:
                raise ValidationError(f"Missing facets: {missing_facets}")
            
            # Check facet score types and ranges
            for facet, score in facets.items():
                if not isinstance(score, (int, float, Decimal)):
                    raise ValidationError(f"Facet {facet} score must be a number, got {type(score)}")
                
                # Convert to Decimal for consistent comparison
                facet_score_decimal = Decimal(str(score)) if not isinstance(score, Decimal) else score
                
                # Enforce score range 10-90 as per requirements
                if not (Decimal("10") <= facet_score_decimal <= Decimal("90")):
                    raise ValidationError(f"Facet {facet} score must be between 10 and 90, got {score}")
            
            # Use Pydantic for final validation and schema conformance
            try:
                # Create ScoreResult using the v1.2 API model (lowercase keys)
                validated_scores = ScoreResult(
                    o=scores["o"],
                    c=scores["c"],
                    e=scores["e"],
                    a=scores["a"],
                    n=scores["n"],
                    facets=scores["facets"]
                )
                
                logger.info("Successfully validated personality scores")
                return validated_scores
                
            except Exception as e:
                logger.error(f"Pydantic validation error: {str(e)}")
                raise ValidationError(f"Error creating ScoreResult model: {str(e)}")
            
        except ValidationError:
            # Re-raise ValidationError with the same message
            raise
            
        except Exception as e:
            error_msg = f"Error validating personality scores: {str(e)}"
            logger.error(error_msg)
            raise ValidationError(error_msg)


class PersonalityProfileSaver(ISaver):
    """Component for saving personality profiles."""
    
    def __init__(self, repository: ProfileRepository):
        """
        Initialize the profile saver with a repository.
        
        Args:
            repository: Repository for saving personality profiles
        """
        self.repository = repository
    
    async def save(self, user_id: str, data: ScoreResult) -> str:
        """
        Save a personality profile for a user.
        
        Args:
            user_id: Unique identifier for the user
            data: Validated ScoreResult containing domain and facet T-scores (lowercase keys)
            
        Returns:
            profile_id: ID of the saved profile
            
        Raises:
            ProfileSavingError: If there's an error saving the profile
        """
        try:
            logger.info(f"Saving personality profile for user: {user_id}")
            
            # Create a dictionary with all scores (domains and facets)
            # using lowercase keys from v1.2 API
            profile_scores = {
                # Domain scores (lowercase as per v1.2 API)
                "o": data.o,
                "c": data.c,
                "e": data.e,
                "a": data.a,
                "n": data.n
            }
            
            # Add facet scores to the same dictionary
            # Facet keys are already lowercase in the ScoreResult model
            for facet_code, facet_score in data.facets.items():
                profile_scores[facet_code] = facet_score
            
            # Save to database
            profile_id = await self.repository.save_profile(user_id, profile_scores)
            
            logger.info(f"Successfully saved personality profile for user {user_id}, ID: {profile_id}")
            
            return profile_id
            
        except Exception as e:
            error_msg = f"Error saving personality profile for user {user_id}: {str(e)}"
            logger.error(error_msg)
            raise ProfileSavingError(error_msg)


# PersonalityPromptBuilder class has been removed
# This class was used to build prompts for Gemini API to calculate T-scores
# Now we use local Python-based calculation, so this is no longer needed




class PersonalityProfilerAgent:
    """Agent for processing personality profiles."""
    
    def __init__(
        self,
        data_fetcher: PersonalityDataFetcher,
        score_calculator: IScoreCalculator,
        validator: PersonalityResultValidator,
        saver: PersonalityProfileSaver
    ):
        """
        Initialize the personality profiler agent with its components.
        
        Args:
            data_fetcher: Component for fetching user response data
            score_calculator: Component for calculating personality scores
            validator: Component for validating results
            saver: Component for saving profiles
        """
        self.data_fetcher = data_fetcher
        self.score_calculator = score_calculator
        self.validator = validator
        self.saver = saver
    
    async def process_user_test(self, user_id: str) -> ProfileAnalysisResult:
        """
        Process a personality test for a user.
        
        This method orchestrates the entire flow from fetching data
        to saving the final personality profile.
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            ProfileAnalysisResult containing both the profile_id and the calculated scores
            
        Raises:
            PersonalityProfilerError: If there's an error during processing
        """
        try:
            logger.info(f"Starting personality test processing for user: {user_id}")
            
            # Step 1: Fetch user responses
            try:
                responses = await self.data_fetcher.fetch_data(user_id)
                if not responses:
                    raise PersonalityDataFetcherError(f"No responses found for user: {user_id}")
                logger.info(f"Fetched {len(responses)} responses for user: {user_id}")
            except Exception as e:
                raise PersonalityDataFetcherError(f"Error fetching data: {str(e)}")
            
            # Step 2: Calculate scores using PythonScoreCalculator
            # This now returns scores with lowercase keys as per v1.2 API
            try:
                scores_dict = await self.score_calculator.calculate_scores(responses)
                logger.info(f"Successfully calculated scores for user: {user_id}")
            except Exception as e:
                raise ScoreCalculationError(f"Error calculating scores: {str(e)}")
            
            # Step 3: Validate results and enforce T-score range 10-90
            try:
                validated_scores = self.validator.validate(scores_dict)
                logger.info(f"Successfully validated scores for user: {user_id}")
            except Exception as e:
                raise ValidationError(f"Error validating scores: {str(e)}")
            
            # Step 4: Save profile
            try:
                profile_id = await self.saver.save(user_id, validated_scores)
                logger.info(f"Successfully processed personality test for user: {user_id}, profile ID: {profile_id}")
                
                # Create and return ProfileAnalysisResult containing both profile_id and scores
                result = ProfileAnalysisResult(
                    profile_id=profile_id,
                    scores=validated_scores
                )
                
                return result
            except Exception as e:
                raise ProfileSavingError(f"Error saving profile: {str(e)}")
            
        except PersonalityProfilerError as e:
            # Re-raise specific errors
            logger.error(f"Error processing personality test: {str(e)}")
            raise
            
        except Exception as e:
            # Catch any unexpected errors
            error_msg = f"Unexpected error processing personality test for user {user_id}: {str(e)}"
            logger.error(error_msg)
            raise PersonalityProfilerError(error_msg)
