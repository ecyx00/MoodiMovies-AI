import json
from typing import Any, Dict, Optional

import google.generativeai as genai
from loguru import logger
from google.api_core.exceptions import GoogleAPIError

from app.core.config import Settings, get_settings
from app.core.clients.base import ILlmClient
from google.generativeai.types import GenerationConfig


class GeminiClientError(Exception):
    """Base exception for Gemini client errors."""
    pass


class GeminiResponseError(GeminiClientError):
    """Exception for errors in processing Gemini responses."""
    pass


class GeminiClient(ILlmClient):
    """Client for interacting with Google's Gemini API."""
    
    def __init__(self, settings: Settings):
        """
        Initialize the Gemini client with settings.
        
        Args:
            settings: Application settings containing the Gemini API key
        """
        # Use the settings instance passed as an argument
        logger.critical("--- INSIDE GeminiClient __init__ START ---") 
        self.settings = settings 
        self.model_name = settings.GEMINI_MODEL
        
        api_key = settings.GEMINI_API_KEY
        
        # Detailed logging for the API key before configuration
        logger.debug(f"Raw API Key from settings: {repr(api_key)}")
        logger.debug(f"API Key length: {len(api_key) if api_key else 0}")
        
        # Masked key for general logs (keep this)
        masked_key = f"{api_key[:4]}...{api_key[-4:]}" if api_key else "None"
        logger.debug(f"Configuring Gemini with masked key: {masked_key}")

        if not api_key:
            logger.error("GEMINI_API_KEY is not set in settings!")
            raise ValueError("GEMINI_API_KEY must be set.")

        logger.debug(f"Attempting to initialize Gemini with API Key from Settings") 
        try:
            # Log the key being used (masked)
            masked_key = f"{api_key[:4]}...{api_key[-4:]}" if api_key else "None"
            logger.debug(f"Configuring Gemini with API Key: {masked_key}")
            # Use the key from settings
            genai.configure(api_key=api_key) 
            logger.debug("genai.configure called successfully inside GeminiClient.__init__ (using key from settings).")
            # Try a simple API call immediately after configuring
            # models = [m.name for m in genai.list_models()] # Commenting out for now
            # logger.debug(f"Successfully listed models after configure: {models}")
            pass 
        except Exception as e:
            logger.error(f"Error during genai.configure in GeminiClient.__init__ (using key from settings): {e}", exc_info=True)
        logger.critical("--- Exiting GeminiClient.__init__ ---")
        
        # Get the Gemini model
        try:
            # Add log right before model initialization
            logger.debug(f"Attempting to get model: {self.model_name}...") 
            self.model = genai.GenerativeModel(self.model_name)
            logger.info(f"Initialized Gemini client with model: {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini model: {e}")
            raise GeminiClientError(f"Failed to initialize Gemini model: {e}")
    
    async def generate(self, prompt: str) -> str:
        """
        Generate a response from the Gemini model.
        
        Args:
            prompt: The input prompt for the Gemini model
            
        Returns:
            The generated text response
            
        Raises:
            GeminiClientError: For general errors with the Gemini client
            GeminiResponseError: For errors in processing the response
            ConnectionError: If there's an issue connecting to the Gemini API
            ValueError: If the input or output format is invalid
        """
        # Log prompt conditionally based on LOG_FULL_GEMINI_IO setting
        if self.settings.LOG_FULL_GEMINI_IO:
            logger.debug(f"Sending full prompt to Gemini: {prompt}")
        else:
            logger.debug(f"Sending prompt to Gemini (truncated): {prompt[:100]}...")
        
        generation_config = GenerationConfig(
            temperature=0.1,  # Low temperature for more deterministic results
            top_p=0.95,
            top_k=40,
        )
        
        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config=generation_config,
                safety_settings=[
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
                ],
            )
            
            # Check if response was blocked by safety filters
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                error_msg = f"Gemini response blocked: {response.prompt_feedback.block_reason}"
                logger.warning(error_msg)
                raise GeminiResponseError(error_msg)
            
            # Check if response has parts
            if not hasattr(response, 'parts') or not response.parts:
                error_msg = "Gemini response has no parts"
                logger.warning(error_msg)
                raise GeminiResponseError(error_msg)
            
            result_text = response.text
            # Log response conditionally based on LOG_FULL_GEMINI_IO setting
            if self.settings.LOG_FULL_GEMINI_IO:
                logger.debug(f"Received full response from Gemini: {result_text}")
            else:
                logger.debug(f"Received response from Gemini (truncated): {result_text[:100]}...")
            return result_text
            
        except GoogleAPIError as e:
            error_msg = f"Google API error: {str(e)}"
            logger.error(error_msg)
            raise ConnectionError(error_msg)
        except ValueError as e:
            error_msg = f"Value error with Gemini: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error with Gemini: {str(e)}"
            logger.error(error_msg)
            raise GeminiClientError(error_msg)
