#!/usr/bin/env python
"""
Test script for running both personality profiler and film recommender agents.
This script:
1. Takes a user ID as input
2. Runs the Personality Profiler Agent to calculate and save a personality profile
3. Runs the Film Recommender Agent to generate film recommendations based on that profile
"""

import os
import sys
import asyncio
import logging
from datetime import datetime
from loguru import logger
from dotenv import load_dotenv
from app.core.config import Settings

# --- Explicitly configure logger for DEBUG level --- 
logger.remove() # Remove default handler
logger.add(sys.stderr, level="DEBUG") # Add stderr handler with DEBUG level
# --- End logger configuration ---

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger.add(
    f"logs/test_agents_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
    rotation="500 MB",
    level="INFO"
)

async def run_personality_profiler(user_id: str):
    """
    Run Agent 1: Personality Profiler for the given user.
    
    Args:
        user_id: The ID of the user to process
        
    Returns:
        profile_id: The ID of the generated personality profile
    """
    logger.info(f"Starting Personality Profiler Agent for user: {user_id}")
    
    try:
        # Import here to avoid circular imports
        from app.agents.personality_profiler import (
            PersonalityProfilerAgent, 
            PersonalityDataFetcher,
            PersonalityResultValidator, 
            PersonalityProfileSaver
        )
        from app.agents.calculators.python_score_calculator import PythonScoreCalculator
        from app.core.clients.mssql import MSSQLClient
        from app.db.repositories import ResponseRepository, ProfileRepository
        
        # Create settings and database client
        settings = Settings()
        logger.debug(f"Settings object created: {type(settings)}")
        logger.debug(f"GEMINI_API_KEY loaded in Settings: {settings.GEMINI_API_KEY}") 
        logger.debug(f"GEMINI_MODEL loaded in Settings: {settings.GEMINI_MODEL}") # Added log for model
        db_client = MSSQLClient(settings)
        
        # Create required repositories
        response_repo = ResponseRepository(db_client)
        
        # ProfileRepository için definitions_path parametresi gerekiyor
        import os
        definitions_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                     "app", "static", "definitions.json")
        profile_repo = ProfileRepository(db_client, definitions_path)
        
        # Create all required components for the agent
        data_fetcher = PersonalityDataFetcher(response_repo)
        score_calculator = PythonScoreCalculator(settings)
        validator = PersonalityResultValidator()
        saver = PersonalityProfileSaver(profile_repo)
        
        # Create and run the agent with all components
        agent = PersonalityProfilerAgent(
            data_fetcher=data_fetcher,
            score_calculator=score_calculator,
            validator=validator,
            saver=saver
        )
        
        # Process the user test
        profile_id = await agent.process_user_test(user_id)
        
        logger.success(f"Successfully created personality profile {profile_id} for user {user_id}")
        return profile_id
        
    except Exception as e:
        logger.error(f"Error in Personality Profiler Agent: {e}")
        raise

async def run_film_recommender(user_id: str, settings: Settings): # Restore type hint
    """
    Run Agent 2: Film Recommender for the given user.
    Uses the personality profile created by Agent 1.
    
    Args:
        user_id: The ID of the user to process
        
    Returns:
        suggested_films: List of suggested film IDs
    """
    logger.info(f"Starting Film Recommender Agent for user: {user_id}")
    
    try:
        # Import here to avoid circular imports
        from app.agents.film_recommender import FilmRecommenderAgent
        from app.core.clients.mssql import MSSQLClient
        from app.core.clients.gemini import GeminiClient
        
        # Create database client with settings
        logger.debug(f"Settings object created: {type(settings)}")
        logger.debug(f"GEMINI_API_KEY loaded in Settings: {settings.GEMINI_API_KEY}") 
        logger.debug(f"GEMINI_MODEL loaded in Settings: {settings.GEMINI_MODEL}") # Added log for model
        db_client = MSSQLClient(settings)
        
        # settings nesnesinde Gemini API key zaten yükleniyor (.env dosyasından)
        # Gemini API key'in settings'de doğru ayarlandığından emin olalım

        logger.debug(f"GEMINI_API_KEY from Settings before client creation: {repr(settings.GEMINI_API_KEY)}")

        # GeminiClient'a settings nesnesini verelim
        logger.debug("--- Attempting to create GeminiClient ---")
        gemini_client = GeminiClient(settings=settings)
        logger.debug("--- GeminiClient created ---")
        
        # Definitions path'i belirleyelim (static dosyalar için)
        import os
        definitions_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                      "app", "static", "definitions.json")
        
        # FilmRecommenderAgent artık definitions_path parametresini doğrudan kabul ediyor
        # Bu parametre içeride ProfileRepository'ye geçirilecek
        agent = FilmRecommenderAgent(db_client, gemini_client, definitions_path=definitions_path)
        
        # FilmRecommenderAgent sınıfında 'recommend_films' yerine 'generate_recommendations' metodu var
        success = await agent.generate_recommendations(user_id)
        
        # Film önerilerini getirmek için direkt SQL sorgusu kullanalım
        if success:
            # Önerileri direkt MOODMOVIES_SUGGEST tablosundan oku
            query = "SELECT FILM_ID FROM dbo.MOODMOVIES_SUGGEST WHERE USER_ID = ? ORDER BY CREATED DESC"
            results = await db_client.query_all(query, (user_id,))
            suggested_films = [result['FILM_ID'] for result in results if 'FILM_ID' in result]
            logger.info(f"Found {len(suggested_films)} film suggestions for user {user_id}")
        else:
            # Başarısız ise boş liste dön
            suggested_films = []
        
        logger.success(f"Successfully created {len(suggested_films)} film recommendations for user {user_id}")
        return suggested_films
        
    except Exception as e:
        logger.error(f"Error in Film Recommender Agent: {e}")
        raise

async def run_complete_test(user_id: str):
    """
    Run the complete test workflow: Agent 1 + Agent 2.
    
    Args:
        user_id: The ID of the user to process
    """
    logger.info(f"=== STARTING COMPLETE TEST FOR USER {user_id} ===")
    
    try:
        # Load settings
        load_dotenv()
        
        global_settings = Settings()
        
        # Step 1: Run Personality Profiler
        logger.info("=== STEP 1: PERSONALITY PROFILER ===")
        await run_personality_profiler(user_id) 
        
        logger.info("Pausing for 2 seconds before film recommender...")
        await asyncio.sleep(2) 

        # Step 2: Run Film Recommender, passing the single settings instance
        logger.info("=== STEP 2: FILM RECOMMENDER ===")
        num_suggestions = await run_film_recommender(user_id, settings=global_settings)
        logger.info(f"Generated {num_suggestions} film suggestions")

        logger.success(f"=== COMPLETE TEST FINISHED SUCCESSFULLY FOR USER {user_id} ===")
    except Exception as e:
        logger.error(f"Complete test failed with exception: {e}", exc_info=True)
        logger.error(f"=== TEST FAILED FOR USER {user_id} ===")

async def verify_suggestions(user_id: str, settings: Settings):
    db_client = MSSQLClient(settings)
    try:
        suggestions = await get_generated_suggestions(db_client, user_id)
    except Exception as e:
        logger.error(f"Failed to get suggestions for user {user_id}: {e}")
        return

def main():
    """Main entry point for the script."""
    # Get user ID from command line or use default test user ID
    if len(sys.argv) > 1:
        user_id = sys.argv[1]
    else:
        user_id = "0000-000001-USR"  # Default test user
        logger.info(f"No user ID provided, using default test user: {user_id}")
    
    # Run the complete test
    asyncio.run(run_complete_test(user_id))

if __name__ == "__main__":
    main()
