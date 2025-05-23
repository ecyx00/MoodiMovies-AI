"""
Film Recommendation Router

This module implements the API endpoints for film recommendations.
It handles requests to generate recommendations and retrieve existing recommendations.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path, BackgroundTasks, Response
from loguru import logger
import uuid
import traceback
from datetime import datetime, timedelta

# Bağımlılık enjeksiyon sağlayıcıları
from app.core.dependencies import (
    get_film_recommender_agent,
    get_recommendation_repository,
    get_llm_client,
    get_process_status_manager,
    get_webhook_manager,
    get_profile_repository
)
from app.security.api_key import verify_api_key

# Pydantic şemaları
from app.schemas.recommendation_schemas import (
    RecommendationRequest,
    RecommendationResponse,
    RecommendationDetail,
    RecommendationStatusResponse,
    RecommendationGenerateResponse,
    FilmMetadata,
    ErrorDetail
)
from app.schemas.webhook_schemas import WebhookEventType

# Agent ve repository sınıfları (tip tanımları için)
from app.db.repositories import RecommendationRepository, ProfileRepository
from app.agents.film_recommender import FilmRecommenderAgent
from app.core.clients.gemini import GeminiClient
from app.core.webhook_manager import WebhookManager
from app.core.process_status import ProcessStatusManager

router = APIRouter(
    prefix="/api/v1",
    tags=["Film Recommendations"],
    dependencies=[Depends(verify_api_key)]  # Apply security at router level
)

# Background task for generating recommendations
async def generate_recommendations_task(
    user_id: str,
    process_id: str,
    agent: FilmRecommenderAgent,
    status_manager: ProcessStatusManager = None,
    webhook_manager: WebhookManager = None
):
    """Background task for generating film recommendations."""
    # Get managers from dependency injection if not provided
    if status_manager is None:
        status_manager = get_process_status_manager()
    
    if webhook_manager is None:
        webhook_manager = get_webhook_manager()
    
    # Define the stages of the process
    stages = {
        "init": {"message": "Başlatılıyor", "percentage": 5},
        "profile": {"message": "Kişilik profili alınıyor", "percentage": 10},
        "genres": {"message": "Film türleri belirleniyor", "percentage": 30},
        "candidates": {"message": "Aday filmler getiriliyor", "percentage": 50},
        "selection": {"message": "En uygun filmler seçiliyor", "percentage": 75},
        "saving": {"message": "Öneriler kaydediliyor", "percentage": 90},
        "completed": {"message": "Öneriler başarıyla oluşturuldu", "percentage": 100},
    }
    
    try:
        # Initialize task
        logger.info(f"Starting background task to generate recommendations for user: {user_id}, process_id: {process_id}")
        await status_manager.update_status(
            process_id=process_id,
            user_id=user_id,
            status="in_progress",
            message=stages["init"]["message"],
            percentage=stages["init"]["percentage"],
            stage="init"
        )
        
        # Step 1: Get user personality profile
        await status_manager.update_status(
            process_id=process_id,
            status="in_progress",
            message=stages["profile"]["message"],
            percentage=stages["profile"]["percentage"],
            stage="profile"
        )
        profile = await agent._get_user_profile(user_id)
        if not profile:
            error_message = f"No personality profile found for user: {user_id}"
            logger.error(error_message)
            
            # Update status to failed
            await status_manager.update_status(
                process_id=process_id,
                status="failed",
                message="Kişilik profili bulunamadı",
                error_details=error_message
            )
            
            # Send webhook notification for failure
            if webhook_manager:
                await webhook_manager.send_webhook_event(
                    event_type=WebhookEventType.RECOMMENDATION_FAILED,
                    user_id=user_id,
                    data={
                        "process_id": process_id,
                        "error": "No personality profile found",
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            return False
        
        # Step 2: Load personality definitions
        definitions = agent._load_definitions()
        if not definitions:
            error_message = "Failed to load personality definitions"
            logger.error(error_message)
            
            # Update status to failed
            await status_manager.update_status(
                process_id=process_id,
                status="failed",
                message="Tanımlar yüklenemedi",
                error_details=error_message
            )
            
            # Send webhook notification for failure
            if webhook_manager:
                await webhook_manager.send_webhook_event(
                    event_type=WebhookEventType.RECOMMENDATION_FAILED,
                    user_id=user_id,
                    data={
                        "process_id": process_id,
                        "error": "Failed to load definitions",
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            return False
        
        # Step 3: Get all available genres
        all_genres = await agent._get_all_genres()
        if not all_genres:
            error_message = "Failed to get film genres"
            logger.error(error_message)
            
            # Update status to failed
            await status_manager.update_status(
                process_id=process_id,
                status="failed",
                message="Film türleri alınamadı",
                error_details=error_message
            )
            
            # Send webhook notification for failure
            if webhook_manager:
                await webhook_manager.send_webhook_event(
                    event_type=WebhookEventType.RECOMMENDATION_FAILED,
                    user_id=user_id,
                    data={
                        "process_id": process_id,
                        "error": "Failed to get film genres",
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            return False
        
        # Step 4: Get genre recommendations (first Gemini call)
        await status_manager.update_status(
            process_id=process_id,
            status="in_progress",
            message=stages["genres"]["message"],
            percentage=stages["genres"]["percentage"],
            stage="genres"
        )
        genre_recommendation = await agent._get_genre_recommendations(profile, all_genres, definitions)
        if not genre_recommendation:
            error_message = "Failed to get genre recommendations from Gemini"
            logger.error(error_message)
            
            # Update status to failed
            await status_manager.update_status(
                process_id=process_id,
                status="failed",
                message="Film türleri belirlenemedi",
                error_details=error_message
            )
            
            # Send webhook notification for failure
            if webhook_manager:
                await webhook_manager.send_webhook_event(
                    event_type=WebhookEventType.RECOMMENDATION_FAILED,
                    user_id=user_id,
                    data={
                        "process_id": process_id,
                        "error": "Failed to get genre recommendations",
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            return False
        
        # Step 5: Get candidate films based on genres
        await status_manager.update_status(
            process_id=process_id,
            status="in_progress",
            message=stages["candidates"]["message"],
            percentage=stages["candidates"]["percentage"],
            stage="candidates",
            data={
                "include_genres": genre_recommendation.include_genres,
                "exclude_genres": genre_recommendation.exclude_genres
            }
        )
        candidate_films = await agent._get_candidate_films(
            genre_recommendation.include_genres,
            genre_recommendation.exclude_genres
        )
        if not candidate_films:
            error_message = "Failed to get candidate films"
            logger.error(error_message)
            
            # Update status to failed
            await status_manager.update_status(
                process_id=process_id,
                status="failed",
                message="Aday filmler bulunamadı",
                error_details=error_message
            )
            
            # Send webhook notification for failure
            if webhook_manager:
                await webhook_manager.send_webhook_event(
                    event_type=WebhookEventType.RECOMMENDATION_FAILED,
                    user_id=user_id,
                    data={
                        "process_id": process_id,
                        "error": "Failed to get candidate films",
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            return False
        
        # Step 6: Extract domain scores from profile
        domain_scores = agent._extract_domain_scores(profile)
        
        # Step 7: Get film recommendations (second Gemini call)
        await status_manager.update_status(
            process_id=process_id,
            status="in_progress",
            message=stages["selection"]["message"],
            percentage=stages["selection"]["percentage"],
            stage="selection"
        )
        film_ids = await agent._get_film_recommendations(candidate_films, domain_scores)
        if not film_ids:
            error_message = "Failed to get film recommendations from Gemini"
            logger.error(error_message)
            
            # Update status to failed
            await status_manager.update_status(
                process_id=process_id,
                status="failed",
                message="Film önerileri alınamadı",
                error_details=error_message
            )
            
            # Send webhook notification for failure
            if webhook_manager:
                await webhook_manager.send_webhook_event(
                    event_type=WebhookEventType.RECOMMENDATION_FAILED,
                    user_id=user_id,
                    data={
                        "process_id": process_id,
                        "error": "Failed to get film recommendations",
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            return False
        
        # Step 8: Save recommendations to database
        await status_manager.update_status(
            process_id=process_id,
            status="in_progress",
            message=stages["saving"]["message"],
            percentage=stages["saving"]["percentage"],
            stage="saving",
            data={
                "film_count": len(film_ids)
            }
        )
        try:
            await agent._save_recommendations(user_id, film_ids)
        except Exception as save_error:
            error_message = f"Error saving film recommendations: {str(save_error)}"
            logger.error(error_message)
            
            # Update status to failed
            await status_manager.update_status(
                process_id=process_id,
                status="failed",
                message="Öneriler kaydedilemedi",
                error_details=error_message
            )
            
            # Send webhook notification for failure
            if webhook_manager:
                await webhook_manager.send_webhook_event(
                    event_type=WebhookEventType.RECOMMENDATION_FAILED,
                    user_id=user_id,
                    data={
                        "process_id": process_id,
                        "error": "Failed to save recommendations",
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            return False
        
        # Step 9: Successfully completed
        logger.info(f"Successfully generated {len(film_ids)} film recommendations for user: {user_id}")
        await status_manager.update_status(
            process_id=process_id,
            status="completed",
            message=stages["completed"]["message"],
            percentage=stages["completed"]["percentage"],
            stage="completed",
            data={
                "film_ids": film_ids,
                "film_count": len(film_ids),
                "completed_at": datetime.now().isoformat()
            }
        )
        
        # Send webhook notification for successful completion
        if webhook_manager:
            await webhook_manager.send_webhook_event(
                event_type=WebhookEventType.RECOMMENDATIONS_GENERATED,
                user_id=user_id,
                data={
                    "process_id": process_id,
                    "recommendation_id": process_id,  # Using process_id as recommendation_id for simplicity
                    "film_count": len(film_ids),
                    "timestamp": datetime.now().isoformat()
                }
            )
        
        return True
        
    except Exception as e:
        # Get detailed error information
        error_message = f"Error generating recommendations for user {user_id}: {str(e)}"
        error_details = traceback.format_exc()
        logger.error(error_message)
        logger.debug(error_details)
        
        # Update status to failed
        try:
            await status_manager.update_status(
                process_id=process_id,
                status="failed",
                message="Bir hata oluştu",
                error_details=error_message
            )
        except Exception as status_error:
            logger.error(f"Error updating process status: {str(status_error)}")
        
        # Send webhook notification for failure
        try:
            if webhook_manager:
                await webhook_manager.send_webhook_event(
                    event_type=WebhookEventType.RECOMMENDATION_FAILED,
                    user_id=user_id,
                    data={
                        "process_id": process_id,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    }
                )
        except Exception as webhook_error:
            logger.error(f"Error sending webhook notification: {str(webhook_error)}")
        
        return False

@router.post(
    "/recommendations/generate/{user_id}",
    response_model=RecommendationGenerateResponse,
    status_code=202,  # Accepted
    responses={
        202: {"model": RecommendationGenerateResponse, "description": "Recommendation generation accepted"},
        404: {"model": ErrorDetail, "description": "No personality profile found for user"},
        409: {"model": ErrorDetail, "description": "Another recommendation process is already running"},
        500: {"model": ErrorDetail, "description": "Internal server error"}
    }
)
async def request_recommendations(
    user_id: str = Path(..., description="User ID to generate recommendations for"),
    film_count: Optional[int] = Query(5, description="Number of films to recommend", ge=1, le=10),
    background_tasks: BackgroundTasks = None,
    profile_repo: ProfileRepository = Depends(get_profile_repository),
    repo: RecommendationRepository = Depends(get_recommendation_repository),
    agent: FilmRecommenderAgent = Depends(get_film_recommender_agent),
    status_manager: ProcessStatusManager = Depends(get_process_status_manager),
    webhook_manager: WebhookManager = Depends(get_webhook_manager),
    _: bool = Depends(verify_api_key)
):
    """
    Request generation of film recommendations for a user.
    
    This is an asynchronous operation - the recommendations will be generated in the background.
    The response provides a confirmation that the process has started along with a process ID
    that can be used to check the status.
    """
    # Generate a process ID for tracking
    process_id = f"PRC-{uuid.uuid4().hex[:8]}"
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    logger.info(f"[{request_id}] Received recommendation generation request for user: {user_id}, process_id: {process_id}")
    
    try:
        # Step 1: Check if there's an active process already running for this user (optional)
        active_process = await repo.get_active_recommendation_process(user_id)
        if active_process:
            # Check if process started less than 5 minutes ago
            if active_process.get("started_at") and \
               datetime.now() - active_process["started_at"] < timedelta(minutes=5):
                error_detail = ErrorDetail(
                    detail=f"A recommendation process is already running for user: {user_id}",
                    error_code="PROCESS_ALREADY_RUNNING",
                    request_id=request_id
                )
                logger.warning(f"[{request_id}] {error_detail.detail}")
                raise HTTPException(status_code=409, detail=error_detail.dict())
        
        # Step 2: Check if the user has a personality profile
        has_profile = await profile_repo.user_has_profile(user_id)
        if not has_profile:
            error_detail = ErrorDetail(
                detail=f"Cannot generate recommendations: No personality profile found for user: {user_id}",
                error_code="PROFILE_NOT_FOUND",
                request_id=request_id
            )
            logger.error(f"[{request_id}] {error_detail.detail}")
            raise HTTPException(status_code=404, detail=error_detail.dict())
        
        # Step 3: Prepare the recommendation in the database and initialize process status
        recommendation_id = await repo.prepare_recommendation(user_id, process_id=process_id)
        
        if not recommendation_id:
            error_detail = ErrorDetail(
                detail=f"Failed to create recommendation record for user: {user_id}",
                error_code="DATABASE_ERROR",
                request_id=request_id
            )
            logger.error(f"[{request_id}] {error_detail.detail}")
            raise HTTPException(status_code=503, detail=error_detail.dict())
            
        # Initialize process status
        await status_manager.initialize_process(
            process_id=process_id,
            user_id=user_id,
            process_type="recommendation",
            status="queued",
            message="Film önerileri oluşturma talebi alındı",
            percentage=0,
            data={
                "film_count": film_count,
                "recommendation_id": recommendation_id,
                "created_at": datetime.now().isoformat()
            }
        )
        
        # Step 4: Schedule the background task
        if background_tasks is not None:
            # Set film count in agent
            agent.film_count = film_count
            
            # Add task with new parameters
            background_tasks.add_task(
                generate_recommendations_task,
                user_id,
                process_id,
                agent,
                status_manager,
                webhook_manager
            )
            logger.info(f"[{request_id}] Scheduled recommendation generation task for user: {user_id}, process_id: {process_id}")
        else:
            logger.warning(f"[{request_id}] BackgroundTasks not available, recommendation won't be generated automatically")
        
        # Step 5: Update initial status in recommendation repository
        await repo.update_recommendation_status(
            recommendation_id,
            status="in_progress",
            stage="initializing",
            percentage=0
        )
        
        # Step 6: Return success response
        logger.info(f"[{request_id}] Recommendation generation initiated for user: {user_id}, process_id: {process_id}")
        return RecommendationGenerateResponse(
            message="Film recommendations will be generated. Check status endpoint for updates.",
            process_id=process_id,
            status="in_progress",
            estimated_completion_seconds=30,
            user_id=user_id
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle unexpected errors
        error_message = f"Error initiating recommendation generation for user {user_id}: {str(e)}"
        error_details = traceback.format_exc()
        logger.error(f"[{request_id}] {error_message}")
        logger.debug(error_details)
        
        # Try to update status if initialization was successful
        try:
            await status_manager.update_status(
                process_id=process_id,
                status="failed",
                message="Öneri oluşturma işlemi başlatılamadı",
                error_details=error_message
            )
        except Exception as status_error:
            logger.error(f"Error updating process status: {str(status_error)}")
        
        # Try to send webhook notification for failure
        try:
            await webhook_manager.send_webhook_event(
                event_type=WebhookEventType.RECOMMENDATION_FAILED,
                user_id=user_id,
                data={
                    "process_id": process_id,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
            )
        except Exception as webhook_error:
            logger.error(f"Error sending webhook notification: {str(webhook_error)}")
        
        # Return error response
        error_detail = ErrorDetail(
            detail=f"Error initiating recommendation generation",
            error_code="BACKGROUND_TASK_ERROR" if "background" in str(e).lower() else "INTERNAL_SERVER_ERROR",
            request_id=process_id
        )
        logger.error(f"[{request_id}] {error_detail.detail}: {str(e)}")
        raise HTTPException(status_code=500, detail=error_detail.dict())

@router.get(
    "/recommendations/{user_id}",
    response_model=RecommendationResponse,
    responses={
        200: {"model": RecommendationResponse},
        204: {"description": "No recommendations found for user"},
        404: {"model": ErrorDetail, "description": "User not found"},
        503: {"model": ErrorDetail, "description": "Database error"},
        500: {"model": ErrorDetail, "description": "Internal server error"}
    }
)
async def get_user_latest_recommendation(
    user_id: str = Path(..., description="User ID to retrieve recommendations for"),
    repo: RecommendationRepository = Depends(get_recommendation_repository),
    response: Response = None
):
    """
    Retrieve the latest film recommendations for a user.
    
    According to v1.2 API specification, this returns ONLY the film IDs,
    not the full film metadata.
    """
    # Generate a request ID for tracking
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    logger.info(f"[{request_id}] Fetching latest recommendations for user: {user_id}")
    
    try:
        # Step 1: Fetch the latest recommendation IDs and profile info from the repository
        result = await repo.get_latest_recommendation_ids_and_profile_info(user_id)
        
        # Handle various result scenarios
        if not result or (isinstance(result, tuple) and not result[0]):
            logger.warning(f"[{request_id}] No recommendations found for user: {user_id}")
            # Return 204 No Content for empty results
            response.status_code = 204
            return None
        
        # Step 2: Extract data based on result format
        if isinstance(result, tuple) and len(result) >= 3:
            film_ids, profile_id, created_at = result[:3]
            recommendation_id = result[3] if len(result) > 3 else f"rec-{uuid.uuid4().hex[:8]}"
        else:
            # Handle alternative result format if repository uses a different structure
            film_ids = result.get("film_ids", []) if isinstance(result, dict) else result
            profile_id = result.get("profile_id", None) if isinstance(result, dict) else None
            created_at = result.get("created_at", datetime.now()) if isinstance(result, dict) else datetime.now()
            recommendation_id = result.get("recommendation_id", f"rec-{uuid.uuid4().hex[:8]}") if isinstance(result, dict) else f"rec-{uuid.uuid4().hex[:8]}"
        
        # Step 3: Construct the response model
        recommendation_response = RecommendationResponse(
            message="Recommendations retrieved successfully", 
            user_id=user_id,
            generated_at=created_at,
            recommendation_id=recommendation_id,
            film_ids=film_ids
        )
        
        # Step 4: Add cache headers if Response object is available
        if response:
            # Add Cache-Control header
            response.headers["Cache-Control"] = "max-age=1800, public"  # 30-minute cache
            
            # Add ETag based on content
            response.headers["ETag"] = f'"{hash(tuple(film_ids))}"'  # Using film_ids for ETag
        
        logger.info(f"[{request_id}] Successfully retrieved {len(film_ids)} recommendations for user: {user_id}")
        return recommendation_response
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle unexpected errors
        error_detail = ErrorDetail(
            detail=f"Error retrieving recommendations for user: {user_id}",
            error_code="DATABASE_ERROR" if "database" in str(e).lower() else "INTERNAL_SERVER_ERROR",
            request_id=request_id
        )
        logger.error(f"[{request_id}] {error_detail.detail}: {str(e)}")
        
        status_code = 503 if "database" in str(e).lower() else 500
        raise HTTPException(status_code=status_code, detail=error_detail.dict())


# Admin/internal endpoint - not part of the public API v1.2 specification
@router.get(
    "/admin/recommendations/detail/{recommendation_id}",
    response_model=RecommendationDetail,
    responses={
        200: {"model": RecommendationDetail},
        404: {"model": ErrorDetail, "description": "Recommendation not found"},
        500: {"model": ErrorDetail, "description": "Internal server error"}
    }
)
async def get_recommendation_detail(
    recommendation_id: str = Path(..., description="Recommendation ID to retrieve"),
    repo: RecommendationRepository = Depends(get_recommendation_repository)
):
    """
    [ADMIN ONLY] Retrieve detailed information about a specific recommendation set by ID.
    
    This endpoint is for administrative purposes and returns the full film metadata.
    It is NOT part of the public API v1.2 specification.
    """
    try:
        logger.info(f"Fetching detailed recommendation with ID: {recommendation_id}")
        
        # Fetch recommendation using the injected repository
        recommendation = await repo.get_recommendation_by_id(recommendation_id)
        
        if not recommendation:
            error_detail = ErrorDetail(
                detail=f"Recommendation not found with ID: {recommendation_id}",
                error_code="RECOMMENDATION_NOT_FOUND",
                request_id=f"req_{recommendation_id[:8]}"
            )
            logger.warning(error_detail.detail)
            raise HTTPException(status_code=404, detail=error_detail.dict())
        
        logger.info(f"Successfully retrieved detailed recommendation: {recommendation_id}")
        return recommendation
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        error_detail = ErrorDetail(
            detail=f"Error retrieving recommendation detail: {str(e)}",
            error_code="RECOMMENDATION_DETAIL_ERROR",
            request_id=f"req_{recommendation_id[:8]}"
        )
        logger.error(f"Error retrieving recommendation detail: {str(e)}")
        raise HTTPException(status_code=500, detail=error_detail.dict())

@router.get(
    "/recommendations/status/user/{user_id}",
    response_model=RecommendationStatusResponse,
    responses={
        200: {"model": RecommendationStatusResponse},
        404: {"model": ErrorDetail, "description": "No recommendation process found for user"},
        503: {"model": ErrorDetail, "description": "Database error"},
        500: {"model": ErrorDetail, "description": "Internal server error"}
    }
)
async def get_user_recommendation_status(
    user_id: str = Path(..., description="User ID to check recommendation status for"),
    repo: RecommendationRepository = Depends(get_recommendation_repository)
):
    """
    Check the status of the latest recommendation generation process for a user.
    
    Returns detailed information about the recommendation process, including
    the current status, completion percentage, and processing stage.
    """
    # Generate a request ID for tracking
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    logger.info(f"[{request_id}] Checking status of latest recommendation process for user: {user_id}")
    
    try:
        # Fetch status using the injected repository
        process_status = await repo.get_latest_recommendation_status_for_user(user_id)
        
        if not process_status:
            error_detail = ErrorDetail(
                detail=f"No recommendation process found for user: {user_id}",
                error_code="PROCESS_NOT_FOUND",
                request_id=request_id
            )
            logger.warning(f"[{request_id}] {error_detail.detail}")
            raise HTTPException(status_code=404, detail=error_detail.dict())
        
        # Extract status data - handle various possible formats from repository
        if isinstance(process_status, dict):
            # Repository returns dictionary format
            status = process_status.get("status", "unknown")
            message = process_status.get("message", f"Recommendation process is {status}")
            percentage = process_status.get("percentage", 0)
            stage = process_status.get("stage", "unknown")
            last_updated = process_status.get("last_updated", datetime.now())
            error_details = process_status.get("error_details")
            recommendation_id = process_status.get("recommendation_id")
        else:
            # Handle alternative return format if needed
            # This is a fallback in case the repository implementation differs
            status = getattr(process_status, "status", "unknown")
            message = getattr(process_status, "message", f"Recommendation process is {status}")
            percentage = getattr(process_status, "percentage", 0)
            stage = getattr(process_status, "stage", "unknown")
            last_updated = getattr(process_status, "last_updated", datetime.now())
            error_details = getattr(process_status, "error_details", None)
            recommendation_id = getattr(process_status, "recommendation_id", None)
        
        # Construct status response
        status_response = RecommendationStatusResponse(
            status=status,
            message=message,
            percentage=percentage,
            stage=stage,
            last_updated=last_updated,
            error_details=error_details,
            recommendation_id=recommendation_id,
            user_id=user_id
        )
        
        logger.info(f"[{request_id}] Successfully retrieved recommendation status for user: {user_id}, status: {status}, percentage: {percentage}%")
        return status_response
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle unexpected errors
        error_detail = ErrorDetail(
            detail=f"Error retrieving recommendation status for user: {user_id}",
            error_code="DATABASE_ERROR" if "database" in str(e).lower() else "INTERNAL_SERVER_ERROR",
            request_id=request_id
        )
        logger.error(f"[{request_id}] {error_detail.detail}: {str(e)}")
        
        status_code = 503 if "database" in str(e).lower() else 500
        raise HTTPException(status_code=status_code, detail=error_detail.dict())


# Admin/internal endpoint - not part of the public API v1.2 specification
@router.get(
    "/admin/recommendations/status/{recommendation_id}",
    response_model=RecommendationResponse,
    responses={
        200: {"model": RecommendationResponse},
        404: {"model": ErrorDetail, "description": "Recommendation not found"},
        500: {"model": ErrorDetail, "description": "Internal server error"}
    }
)
async def get_recommendation_status_by_id(
    recommendation_id: str = Path(..., description="Recommendation ID to check status for"),
    repo: RecommendationRepository = Depends(get_recommendation_repository)
):
    """
    [ADMIN ONLY] Check the status of a recommendation generation process by its ID.
    
    This endpoint is for administrative purposes. It is NOT part of the public API v1.2 specification.
    
    Returns basic information about the recommendation process, including
    whether it has completed and what film IDs were recommended.
    """
    try:
        logger.info(f"Checking status of recommendation: {recommendation_id}")
        
        # Fetch status using the injected repository
        status = await repo.get_recommendation_status(recommendation_id)
        
        if not status:
            error_detail = ErrorDetail(
                detail=f"Recommendation not found with ID: {recommendation_id}",
                error_code="RECOMMENDATION_NOT_FOUND",
                request_id=f"req_{recommendation_id[:8]}"
            )
            logger.warning(error_detail.detail)
            raise HTTPException(status_code=404, detail=error_detail.dict())
        
        # Extract film IDs from status data (or empty list)
        film_ids = status.get("film_ids", [])
        
        # Construct response from status data
        response = RecommendationResponse(
            message=f"Recommendation {'completed' if film_ids else 'in progress'}",
            user_id=status.get("user_id", "unknown"),
            generated_at=status.get("generated_at"),
            recommendation_id=recommendation_id,
            film_ids=film_ids
        )
        
        logger.info(f"Successfully retrieved status for recommendation: {recommendation_id}")
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        error_detail = ErrorDetail(
            detail=f"Error retrieving recommendation status: {str(e)}",
            error_code="RECOMMENDATION_STATUS_ERROR",
            request_id=f"req_{recommendation_id[:8]}"
        )
        logger.error(error_detail.detail)
        raise HTTPException(status_code=500, detail=error_detail.dict())
