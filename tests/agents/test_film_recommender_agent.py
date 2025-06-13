import pytest
import json
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import pytest_asyncio
from typing import Dict, List, Any

from app.agents.film_recommender import FilmRecommenderAgent
from app.core.clients.base import IDatabaseClient
from app.core.clients.gemini import GeminiClient, GeminiResponseError as GeminiAPIError
from app.core.config import Settings
from app.db.repositories import ProfileRepository, RecommendationRepository, RepositoryError

# NotFoundException projedeki mevcut sınıfları kullanarak tanımlıyoruz
class NotFoundException(Exception):
    """Exception for when a resource is not found."""
    pass

# Test fixtures
@pytest_asyncio.fixture
async def settings():
    """Create a mock settings object."""
    settings = MagicMock(spec=Settings)
    settings.GEMINI_API_KEY = "mock-api-key"
    settings.GEMINI_MODEL = "gemini-pro"
    return settings

@pytest_asyncio.fixture
async def db_client():
    """Create a mock database client."""
    return AsyncMock(spec=IDatabaseClient)

@pytest_asyncio.fixture
async def profile_repository(db_client):
    """Create a mock profile repository."""
    repo = AsyncMock(spec=ProfileRepository)
    return repo

@pytest_asyncio.fixture
async def recommendation_repository(db_client):
    """Create a mock recommendation repository."""
    repo = AsyncMock(spec=RecommendationRepository)
    return repo

@pytest_asyncio.fixture
async def gemini_client():
    """Create a mocked GeminiClient."""
    client = AsyncMock(spec=GeminiClient)
    
    # GeminiClient'ın generate metodunu ekle
    async def mock_generate(prompt):
        return client.mock_response
    
    client.generate = mock_generate
    client.mock_response = ""
    
    return client

@pytest_asyncio.fixture
async def film_recommender(db_client, profile_repository, recommendation_repository, gemini_client):
    """Create a FilmRecommenderAgent with mocked dependencies."""
    with patch('app.agents.film_recommender.ProfileRepository', return_value=profile_repository), \
         patch('app.agents.film_recommender.RecommendationRepository', return_value=recommendation_repository):
        # Definitions yolunu mock'layalım
        with patch('os.path.exists', return_value=True), \
             patch('json.load', return_value={"ocean_domains": {}, "facets": {}}):
            agent = FilmRecommenderAgent(db_client, gemini_client)
            yield agent

# Mock responses and data
@pytest.fixture
def mock_profile_data():
    """Generate mock personality profile data."""
    return {
        "o": Decimal("50.0"),
        "c": Decimal("55.0"),
        "e": Decimal("60.0"),
        "a": Decimal("45.0"),
        "n": Decimal("40.0"),
        "facets": {
            "o_f1": Decimal("50.0"),
            "o_f2": Decimal("51.0"),
            "o_f3": Decimal("52.0"),
            "o_f4": Decimal("53.0"),
            "o_f5": Decimal("54.0"),
            "o_f6": Decimal("55.0"),
            "c_f1": Decimal("55.0"),
            "c_f2": Decimal("56.0"),
            "c_f3": Decimal("57.0"),
            "c_f4": Decimal("58.0"),
            "c_f5": Decimal("59.0"),
            "c_f6": Decimal("60.0"),
            "e_f1": Decimal("60.0"),
            "e_f2": Decimal("61.0"),
            "e_f3": Decimal("62.0"),
            "e_f4": Decimal("63.0"),
            "e_f5": Decimal("64.0"),
            "e_f6": Decimal("65.0"),
            "a_f1": Decimal("45.0"),
            "a_f2": Decimal("46.0"),
            "a_f3": Decimal("47.0"),
            "a_f4": Decimal("48.0"),
            "a_f5": Decimal("49.0"),
            "a_f6": Decimal("50.0"),
            "n_f1": Decimal("40.0"),
            "n_f2": Decimal("41.0"),
            "n_f3": Decimal("42.0"),
            "n_f4": Decimal("43.0"),
            "n_f5": Decimal("44.0"),
            "n_f6": Decimal("45.0")
        }
    }

@pytest.fixture
def mock_candidate_films():
    """Generate mock candidate films."""
    return [
        {
            "FILM_ID": f"FILM_ID_{i}",
            "FILM_NAME": f"Film {i}",
            "FILM_RAYTING": 8.0 - (i * 0.1),
            "FILM_RELEASE_DATE": datetime(2020, 1, 1).isoformat(),
            "FILM_COUNTRY": "USA",
            "RUNTIME": 120,
            "TUR_1": "Drama",
            "TUR_2": "Comedy" if i % 2 == 0 else "Action",
            "TUR_3": None,
            "TUR_4": None
        }
        for i in range(150)  # Generate more than needed to test the limit
    ]

@pytest.fixture
def mock_gemini_genre_response():
    """Generate mock Gemini API response for genre recommendations."""
    return json.dumps({
        "include_genres": ["Drama", "Comedy"],
        "exclude_genres": ["Horror", "Sci-Fi"]
    })

@pytest.fixture
def mock_gemini_film_response():
    """Generate mock Gemini API response for film recommendations."""
    return json.dumps({
        "recommended_film_ids": [f"FILM_ID_{i}" for i in range(70)]
    })

# Tests
@pytest.mark.asyncio
async def test_generate_recommendations_success(
    film_recommender, 
    profile_repository,
    recommendation_repository,
    gemini_client, 
    mock_profile_data, 
    mock_candidate_films,
    mock_gemini_genre_response,
    mock_gemini_film_response
):
    """Test the happy path for generating recommendations."""
    # Setup mocks
    user_id = "test-user-id"
    profile_repository.get_latest_profile.return_value = mock_profile_data
    recommendation_repository.get_films_by_genre_criteria.return_value = mock_candidate_films[:140]  # Return only up to 140 films
    recommendation_repository.get_all_distinct_genres.return_value = ["Drama", "Comedy", "Action", "Horror", "Sci-Fi"]
    
    # Başarılı test için iki farklı yanıtı sırasıyla döndürmesi gereken bir mock_generate metodu tanımlıyoruz
    call_count = 0
    
    async def mock_generate_success(prompt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_gemini_genre_response
        elif call_count == 2:
            return mock_gemini_film_response
        return "{}"
    
    gemini_client.generate = mock_generate_success
    
    # generate_content metodu kullanılırsa diye boş bir mock hazırla
    gemini_client.generate_content = AsyncMock()
    
    recommendation_repository.save_suggestions.return_value = True
    
    # Execute
    result = await film_recommender.generate_recommendations(user_id)
    
    # Assert
    assert result is True
    profile_repository.get_latest_profile.assert_called_once_with(user_id)
    recommendation_repository.get_films_by_genre_criteria.assert_called_once()
    
    # Verify the limit parameter is 140
    assert recommendation_repository.get_films_by_genre_criteria.call_args[1]['limit'] == 140
    
    # Verify save_suggestions was called with the correct number of film IDs (70)
    recommendation_repository.save_suggestions.assert_called_once()
    saved_films = recommendation_repository.save_suggestions.call_args[0][1]
    assert len(saved_films) == 70
    assert saved_films == [f"FILM_ID_{i}" for i in range(70)]

@pytest.mark.asyncio
async def test_generate_recommendations_no_profile_found(
    film_recommender, 
    profile_repository
):
    """Test scenario where no personality profile is found."""
    # Setup
    user_id = "test-user-id"
    profile_repository.get_latest_profile.return_value = None
    
    # Execute
    result = await film_recommender.generate_recommendations(user_id)
    
    # Assert
    assert result is False
    profile_repository.get_latest_profile.assert_called_once_with(user_id)

@pytest.mark.asyncio
async def test_generate_recommendations_no_genres_available(
    film_recommender,
    profile_repository,
    recommendation_repository,
    gemini_client,
    mock_profile_data
):
    """Test scenario where Gemini API fails to provide genre recommendations."""
    # Setup
    user_id = "test-user-id"
    profile_repository.get_latest_profile.return_value = mock_profile_data
    recommendation_repository.get_all_distinct_genres.return_value = []  # No genres available
    
    # Execute
    result = await film_recommender.generate_recommendations(user_id)
    
    # Assert
    assert result is False
    profile_repository.get_latest_profile.assert_called_once_with(user_id)
    recommendation_repository.get_all_distinct_genres.assert_called_once()

@pytest.mark.asyncio
async def test_generate_recommendations_gemini_film_selection_fails(
    film_recommender, 
    profile_repository,
    recommendation_repository,
    gemini_client, 
    mock_profile_data, 
    mock_candidate_films,
    mock_gemini_genre_response
):
    """Test scenario where Gemini API fails when selecting films."""
    # Setup
    user_id = "test-user-id"
    profile_repository.get_latest_profile.return_value = mock_profile_data
    recommendation_repository.get_all_distinct_genres.return_value = ["Drama", "Comedy", "Action", "Horror", "Sci-Fi"]
    recommendation_repository.get_films_by_genre_criteria.return_value = mock_candidate_films[:140]
    
    # İlk çağrıda normal yanıt, ikincisinde hata
    gemini_client.mock_response = mock_gemini_genre_response
    
    # gemini_client.generate için hata fırlatma durumu
    call_count = 0
    
    async def mock_generate_with_error(prompt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_gemini_genre_response
        raise GeminiAPIError("API error")
    
    gemini_client.generate = mock_generate_with_error
    
    # Execute
    result = await film_recommender.generate_recommendations(user_id)
    
    # Assert
    assert result is False
    profile_repository.get_latest_profile.assert_called_once_with(user_id)
    recommendation_repository.get_films_by_genre_criteria.assert_called_once()

@pytest.mark.asyncio
async def test_generate_recommendations_no_candidate_films_found(
    film_recommender, 
    profile_repository,
    recommendation_repository,
    gemini_client, 
    mock_profile_data, 
    mock_gemini_genre_response
):
    """Test scenario where no candidate films are found."""
    # Setup
    user_id = "test-user-id"
    profile_repository.get_latest_profile.return_value = mock_profile_data
    recommendation_repository.get_all_distinct_genres.return_value = ["Drama", "Comedy", "Action", "Horror", "Sci-Fi"]
    recommendation_repository.get_films_by_genre_criteria.return_value = []  # No films found
    gemini_client.mock_response = mock_gemini_genre_response
    
    # Execute
    result = await film_recommender.generate_recommendations(user_id)
    
    # Assert
    assert result is False
    profile_repository.get_latest_profile.assert_called_once_with(user_id)
    recommendation_repository.get_films_by_genre_criteria.assert_called_once()
    recommendation_repository.save_suggestions.assert_not_called()

@pytest.mark.asyncio
async def test_generate_recommendations_save_suggestions_fails(
    film_recommender, 
    profile_repository,
    recommendation_repository,
    gemini_client, 
    mock_profile_data, 
    mock_candidate_films,
    mock_gemini_genre_response,
    mock_gemini_film_response
):
    """Test scenario where saving recommendations fails."""
    # Setup
    user_id = "test-user-id"
    profile_repository.get_latest_profile.return_value = mock_profile_data
    recommendation_repository.get_all_distinct_genres.return_value = ["Drama", "Comedy", "Action", "Horror", "Sci-Fi"]
    recommendation_repository.get_films_by_genre_criteria.return_value = mock_candidate_films[:140]  # Return 140 films
    
    # İki yanıtı sırayla döndüren mock_generate metodu
    call_count = 0
    
    async def mock_generate_for_save_failure(prompt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_gemini_genre_response
        elif call_count == 2:
            return mock_gemini_film_response
        return "{}"
    
    gemini_client.generate = mock_generate_for_save_failure
    recommendation_repository.save_suggestions.side_effect = RepositoryError("Failed to save")
    
    # Execute
    result = await film_recommender.generate_recommendations(user_id)
    
    # Assert
    assert result is False
    profile_repository.get_latest_profile.assert_called_once_with(user_id)
    recommendation_repository.get_films_by_genre_criteria.assert_called_once()
    recommendation_repository.save_suggestions.assert_called_once()
    
    # Verify the correct number of film IDs were passed to save_suggestions (70)
    saved_films = recommendation_repository.save_suggestions.call_args[0][1]
    assert len(saved_films) == 70
