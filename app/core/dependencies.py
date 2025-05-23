from functools import lru_cache
from typing import Optional, List, Dict, Any

from fastapi import Depends
from loguru import logger

# Core client imports
from app.core.clients.base import IDatabaseClient, ILlmClient
from app.core.clients.mssql import MSSQLClient
from app.core.clients.gemini import GeminiClient
from app.core.config import Settings, get_settings
from app.core.webhook_manager import WebhookManager
from app.core.process_status import ProcessStatusManager

# Repository imports
from app.db.repositories import (
    ResponseRepository, 
    ProfileRepository,
    RecommendationRepository
)

# Agent 1 (Personality Profiler) imports
from app.agents.personality_profiler import (
    PersonalityDataFetcher,
    PersonalityResultValidator,
    PersonalityProfileSaver,
    PersonalityProfilerAgent,
)
from app.agents.calculators.python_score_calculator import PythonScoreCalculator

# Agent 2 (Film Recommender) imports
from app.agents.film_recommender import FilmRecommenderAgent


def get_db_client(settings: Settings = Depends(get_settings)) -> IDatabaseClient:
    """
    Create and cache a database client instance.
    
    Args:
        settings: Application settings
        
    Returns:
        A database client implementing IDatabaseClient
    """
    logger.info("Creating and caching database client")
    return MSSQLClient(settings)


def get_llm_client(settings: Settings = Depends(get_settings)) -> ILlmClient:
    """
    Create and cache an LLM client instance.
    
    Args:
        settings: Application settings
        
    Returns:
        An LLM client implementing ILlmClient
    """
    logger.info("Creating and caching LLM client")
    return GeminiClient(settings)


def get_response_repository(
    db_client: IDatabaseClient = Depends(get_db_client)
) -> ResponseRepository:
    """
    Create a response repository instance.
    
    Args:
        db_client: Database client
        
    Returns:
        A response repository
    """
    return ResponseRepository(db_client)


def get_profile_repository(
    db_client: IDatabaseClient = Depends(get_db_client),
    settings: Settings = Depends(get_settings)
) -> ProfileRepository:
    """
    Create a profile repository instance.
    
    Args:
        db_client: Database client
        settings: Application settings
        
    Returns:
        A profile repository
    """
    logger.debug("Creating profile repository")
    return ProfileRepository(db_client, settings.DEFINITIONS_PATH)


def get_recommendation_repository(
    db_client: IDatabaseClient = Depends(get_db_client)
) -> RecommendationRepository:
    """
    Create a recommendation repository instance.
    
    Args:
        db_client: Database client
        
    Returns:
        A recommendation repository
    """
    logger.debug("Creating recommendation repository")
    return RecommendationRepository(db_client)


def get_data_fetcher(
    repository: ResponseRepository = Depends(get_response_repository)
) -> PersonalityDataFetcher:
    """
    Create a personality data fetcher instance.
    
    Args:
        repository: Response repository
        
    Returns:
        A personality data fetcher
    """
    return PersonalityDataFetcher(repository)


# get_prompt_builder fonksiyonu kaldırıldı - artık Python tabanlı hesaplama kullanıldığından gerekli değil


def get_score_calculator(
    settings: Settings = Depends(get_settings)
) -> PythonScoreCalculator:
    """
    Create a personality score calculator instance.
    
    Args:
        settings: Application settings
        
    Returns:
        A personality score calculator using Python implementation
    """
    logger.info("Creating Python score calculator")
    return PythonScoreCalculator(settings)


def get_personality_validator() -> PersonalityResultValidator:
    """
    Create a personality result validator instance.
    
    Returns:
        A personality result validator
    """
    return PersonalityResultValidator()


def get_personality_saver(
    repository: ProfileRepository = Depends(get_profile_repository)
) -> PersonalityProfileSaver:
    """
    Create a personality profile saver instance.
    
    Args:
        repository: Profile repository
        
    Returns:
        A personality profile saver
    """
    return PersonalityProfileSaver(repository)


def get_personality_agent(
    data_fetcher: PersonalityDataFetcher = Depends(get_data_fetcher),
    score_calculator: PythonScoreCalculator = Depends(get_score_calculator),
    validator: PersonalityResultValidator = Depends(get_personality_validator),
    saver: PersonalityProfileSaver = Depends(get_personality_saver)
) -> PersonalityProfilerAgent:
    """
    Create a personality profiler agent instance.
    
    Args:
        data_fetcher: Data fetcher component
        score_calculator: Score calculator component
        validator: Result validator component
        saver: Profile saver component
        
    Returns:
        A personality profiler agent
    """
    logger.debug("Creating personality profiler agent")
    return PersonalityProfilerAgent(
        data_fetcher=data_fetcher,
        score_calculator=score_calculator,
        validator=validator,
        saver=saver
    )


def get_film_recommender_agent(
    db_client: IDatabaseClient = Depends(get_db_client),
    gemini_client: ILlmClient = Depends(get_llm_client),
    settings: Settings = Depends(get_settings)
) -> FilmRecommenderAgent:
    """
    Create a film recommender agent instance.
    
    Args:
        db_client: Database client
        gemini_client: Gemini LLM client
        settings: Application settings
        
    Returns:
        A film recommender agent
    """
    logger.debug("Creating film recommender agent")
    return FilmRecommenderAgent(
        db_client=db_client, 
        gemini_client=gemini_client, 
        definitions_path=settings.DEFINITIONS_PATH
    )


@lru_cache(maxsize=1)
def get_webhook_manager() -> WebhookManager:
    """
    Create or return a cached webhook manager instance.
    
    Note: This implementation uses an in-memory webhook manager which will lose all
    webhook configurations if the application restarts. In a production environment,
    this should be replaced with a database-backed solution.
    
    Returns:
        A webhook manager instance
    """
    logger.debug("Creating webhook manager")
    return WebhookManager()


@lru_cache(maxsize=1)
def get_process_status_manager() -> ProcessStatusManager:
    """
    Create or return a cached process status manager instance.
    
    Note: This implementation uses an in-memory process status manager which will lose all
    process statuses if the application restarts. In a production environment,
    this should be replaced with a database-backed solution.
    
    Returns:
        A process status manager instance
    """
    logger.debug("Creating process status manager")
    return ProcessStatusManager()
