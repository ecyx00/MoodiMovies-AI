from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, BackgroundTasks, Response
from loguru import logger
import uuid
import hashlib
from datetime import datetime

# Bağımlılık enjeksiyon sağlayıcıları
from app.core.dependencies import (
    get_personality_agent,
    get_profile_repository,
    get_film_recommender_agent
)
from app.security.api_key import verify_api_key

# Pydantic şemaları
from app.schemas.personality_schemas import (
    AnalysisResponse, 
    ProfileResponse, 
    ErrorDetail, 
    ScoreResult, 
    ProfileAnalysisResult
)

# Agent ve repository sınıfları (tip tanımları için)
from app.db.repositories import ProfileRepository
from app.agents.personality_profiler import PersonalityProfilerAgent
from app.agents.film_recommender import FilmRecommenderAgent
from app.agents.personality_profiler import (
    PersonalityDataFetcherError,
    ScoreCalculationError,
    ValidationError,
    ProfileSavingError,
    PersonalityProfilerError
)

router = APIRouter(
    prefix="/api/v1",
    tags=["Personality & Profiles"],
    dependencies=[Depends(verify_api_key)]  # Apply security at router level
)

# --- Personality and Profile Endpoints ---

@router.post(
    "/analyze/personality/{user_id}",
    response_model=AnalysisResponse,
    responses={
        200: {"model": AnalysisResponse},
        404: {"model": ErrorDetail, "description": "User not found or has no test responses"},
        422: {"model": ErrorDetail, "description": "Validation error in personality scores"},
        503: {"model": ErrorDetail, "description": "Database error"},
        500: {"model": ErrorDetail, "description": "Internal server error during analysis"}
    }
)
async def analyze_personality(
    user_id: str = Path(..., description="User ID to analyze personality for"),
    background_tasks: BackgroundTasks = None,
    agent: PersonalityProfilerAgent = Depends(get_personality_agent),
    recommender_agent: FilmRecommenderAgent = Depends(get_film_recommender_agent)
):
    """
    Analyzes personality based on user's test responses.
    
    Fetches user responses, calculates OCEAN scores, validates results,
    and saves a profile to the database.
    
    Returns both the profile ID and the calculated scores.
    """
    # Generate a request ID for tracking
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    logger.info(f"[{request_id}] Processing personality analysis request for user: {user_id}")
    
    try:
        # Step 1: Process the personality test using Agent 1
        result: ProfileAnalysisResult = await agent.process_user_test(user_id)
        
        # Detaylı loglama
        logger.info(f"[{request_id}] Personality analysis completed for user: {user_id}")
        logger.info(f"[{request_id}] DEBUG - result.profile_id tipi: {type(result.profile_id)}")
        logger.info(f"[{request_id}] DEBUG - result.profile_id değeri: '{result.profile_id}'")
        
        # Direkt loglamaya ek olarak, ayrıca döküm
        import inspect
        logger.info(f"[{request_id}] ProfileAnalysisResult sınıfının yapısı: {inspect.getmembers(result)}")
        logger.info(f"[{request_id}] ProfileAnalysisResult.dict(): {result.model_dump()}")
        
        # Başarı durumu
        if result.profile_id and result.profile_id != "":
            logger.info(f"[{request_id}] PROFİL ID BAŞARILI: {result.profile_id}")
        else:
            logger.error(f"[{request_id}] !!! PROFİL ID BOŞ: '{result.profile_id}' !!!")
            
        # ProfileAnalysisResult ve ProfileResponse sınıflarının import edildiğini kontrol et
        from app.schemas.personality_schemas import ProfileAnalysisResult, ScoreResult
        
        # Step 2: Schedule Agent 2 (Film Recommender) to run in the background
        try:
            if background_tasks is not None:
                background_tasks.add_task(
                    recommender_agent.generate_recommendations,
                    user_id
                )
                logger.info(f"[{request_id}] Film recommendation generation scheduled in background for user: {user_id}")
            else:
                logger.warning(f"[{request_id}] BackgroundTasks not available, skipping film recommendation for user: {user_id}")
        except Exception as bg_error:
            # Log the error but don't fail the whole request if just the background task fails
            logger.error(f"[{request_id}] Error scheduling film recommendation task: {str(bg_error)}")
            # We continue with the response even if background task scheduling fails
        
        # Step 3: Profil oluşturma işlemi başarılı, yanıtı dön
        
        # Step 3: ProfileAnalysisResult'dan doğrudan yanıt dön - JSON serileştirmesi schema sınıfında özel olarak tanımlanmıştır
        
        return AnalysisResponse(
            message="Personality analysis completed successfully",
            profile_id=result.profile_id,  # Doğru profil ID'yi result üzerinden alıyoruz
            scores=result.scores
        )
    
    except PersonalityDataFetcherError as e:
        error_detail = ErrorDetail(
            detail=f"No test responses found for user: {user_id}",
            error_code="USER_RESPONSES_NOT_FOUND",
            request_id=request_id
        )
        logger.error(f"[{request_id}] {error_detail.detail}: {str(e)}")
        raise HTTPException(status_code=404, detail=error_detail.dict())
        
    except ValidationError as e:
        error_detail = ErrorDetail(
            detail=f"Validation error in personality scores: {str(e)}",
            error_code="VALIDATION_ERROR",
            request_id=request_id
        )
        logger.error(f"[{request_id}] {error_detail.detail}")
        raise HTTPException(status_code=422, detail=error_detail.dict())
        
    except ScoreCalculationError as e:
        error_detail = ErrorDetail(
            detail=f"Error calculating personality scores: {str(e)}",
            error_code="SCORE_CALCULATION_ERROR",
            request_id=request_id
        )
        logger.error(f"[{request_id}] {error_detail.detail}")
        raise HTTPException(status_code=422, detail=error_detail.dict())
        
    except ProfileSavingError as e:
        error_detail = ErrorDetail(
            detail=f"Database error while saving profile: {str(e)}",
            error_code="DATABASE_ERROR",
            request_id=request_id
        )
        logger.error(f"[{request_id}] {error_detail.detail}")
        raise HTTPException(status_code=503, detail=error_detail.dict())
        
    except PersonalityProfilerError as e:
        # Catch any other known agent errors
        error_detail = ErrorDetail(
            detail=f"Error in personality profiler: {str(e)}",
            error_code="AGENT_ERROR",
            request_id=request_id
        )
        logger.error(f"[{request_id}] {error_detail.detail}")
        raise HTTPException(status_code=500, detail=error_detail.dict())
        
    except Exception as e:
        # Catch any unexpected errors
        error_detail = ErrorDetail(
            detail=f"Unexpected error processing personality analysis: {str(e)}",
            error_code="INTERNAL_SERVER_ERROR",
            request_id=request_id
        )
        logger.error(f"[{request_id}] {error_detail.detail}")
        raise HTTPException(status_code=500, detail=error_detail.dict())

@router.get(
    "/profiles/{profile_id}",
    response_model=ProfileResponse,
    responses={
        200: {"model": ProfileResponse},
        404: {"model": ErrorDetail, "description": "Profile not found"},
        503: {"model": ErrorDetail, "description": "Database error"},
        500: {"model": ErrorDetail, "description": "Internal server error"}
    }
)
async def get_profile(
    profile_id: str = Path(..., description="Profile ID to retrieve"),
    profile_repo: ProfileRepository = Depends(get_profile_repository),
    response: Response = None
):
    """
    Retrieves a personality profile by ID.
    
    Returns a complete profile with all scores and metadata.
    """
    # Generate a request ID for tracking
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    logger.info(f"[{request_id}] Fetching profile with ID: {profile_id}")
    
    try:
        # Fetch profile using the injected repository
        profile = await profile_repo.get_profile_by_id(profile_id)
        
        # Handle not found case
        if not profile:
            error_detail = ErrorDetail(
                detail=f"Profile not found with ID: {profile_id}",
                error_code="PROFILE_NOT_FOUND",
                request_id=request_id
            )
            logger.warning(f"[{request_id}] {error_detail.detail}")
            raise HTTPException(status_code=404, detail=error_detail.dict())
        
        # Log success
        logger.info(f"[{request_id}] Successfully retrieved profile: {profile_id}")
        
        # Add cache headers if Response object is available
        if response:
            # Add Cache-Control header (1 hour cache)
            response.headers["Cache-Control"] = "max-age=3600, public"
            
            # Generate ETag based on profile content and last updated timestamp
            if hasattr(profile, 'updated_at') and profile.updated_at:
                # Use updated_at timestamp if available
                etag_content = f"{profile_id}:{profile.updated_at}"
            else:
                # Otherwise use current timestamp
                etag_content = f"{profile_id}:{datetime.now().isoformat()}"
                
            etag = hashlib.md5(etag_content.encode()).hexdigest()
            response.headers["ETag"] = f'"{etag}"'
        
        return profile
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle unexpected errors
        error_detail = ErrorDetail(
            detail=f"Error retrieving profile",
            error_code="DATABASE_ERROR" if "database" in str(e).lower() else "INTERNAL_SERVER_ERROR",
            request_id=request_id
        )
        logger.error(f"[{request_id}] {error_detail.detail}: {str(e)}")
        
        status_code = 503 if "database" in str(e).lower() else 500
        raise HTTPException(status_code=status_code, detail=error_detail.dict())

@router.get(
    "/profiles/user/{user_id}",
    response_model=List[ProfileResponse],
    responses={
        200: {"model": List[ProfileResponse]},
        404: {"model": ErrorDetail, "description": "No profiles found for user"},
        503: {"model": ErrorDetail, "description": "Database error"},
        500: {"model": ErrorDetail, "description": "Internal server error"}
    }
)
async def get_user_profiles(
    user_id: str = Path(..., description="User ID to retrieve profiles for"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of profiles per page"),
    profile_repo: ProfileRepository = Depends(get_profile_repository),
    response: Response = None
):
    """
    Retrieves all personality profiles for a specific user.
    
    Supports pagination with page and limit parameters.
    Returns a list of profiles with all scores and metadata.
    Also provides X-Total-Count and Link headers for pagination.
    """
    # Generate a request ID for tracking
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    logger.info(f"[{request_id}] Fetching profiles for user: {user_id} (page: {page}, limit: {limit})")
    
    # Calculate skip value from page and limit
    skip = (page - 1) * limit
    
    try:
        # Fetch profiles and total count using the injected repository
        # We expect the repository to return (profiles, total_count)
        profiles_data = await profile_repo.get_profiles_by_user_id(user_id, skip, limit)
        
        # Handle repository return format - could be tuple or just profiles list
        if isinstance(profiles_data, tuple) and len(profiles_data) == 2:
            profiles, total_count = profiles_data
        else:
            profiles = profiles_data
            # If repository doesn't return count, we'll use list length as our count
            total_count = len(profiles)
        
        # Even if no profiles found, return empty list (not 404)
        if not profiles:
            logger.warning(f"[{request_id}] No profiles found for user: {user_id}")
            # Return empty list instead of 404 error as per API best practices
            if response:
                response.headers["X-Total-Count"] = "0"
            return []
        
        logger.info(f"[{request_id}] Successfully retrieved {len(profiles)} profiles for user: {user_id} (total: {total_count})")
        
        # Add pagination headers if Response object is available
        if response:
            # Add total count header
            response.headers["X-Total-Count"] = str(total_count)
            
            # Add Link header for pagination (RFC 8288)
            base_url = f"/api/v1/profiles/user/{user_id}"
            links = []
            
            # Calculate total pages
            total_pages = (total_count + limit - 1) // limit  # Ceiling division
            
            # Add first page link
            links.append(f'<{base_url}?page=1&limit={limit}>; rel="first"')
            
            # Add prev page link if not on first page
            if page > 1:
                links.append(f'<{base_url}?page={page-1}&limit={limit}>; rel="prev"')
            
            # Add next page link if not on last page
            if page < total_pages:
                links.append(f'<{base_url}?page={page+1}&limit={limit}>; rel="next"')
            
            # Add last page link
            links.append(f'<{base_url}?page={total_pages}&limit={limit}>; rel="last"')
            
            # Set Link header
            response.headers["Link"] = ", ".join(links)
            
            # Add Cache-Control header (shorter cache for user profile lists)
            response.headers["Cache-Control"] = "max-age=600, public"
        
        return profiles
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle unexpected errors
        error_detail = ErrorDetail(
            detail=f"Error retrieving profiles for user: {user_id}",
            error_code="DATABASE_ERROR" if "database" in str(e).lower() else "INTERNAL_SERVER_ERROR",
            request_id=request_id
        )
        logger.error(f"[{request_id}] {error_detail.detail}: {str(e)}")
        
        status_code = 503 if "database" in str(e).lower() else 500
        raise HTTPException(status_code=status_code, detail=error_detail.dict())
