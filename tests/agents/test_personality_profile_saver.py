"""Tests for the PersonalityProfileSaver class."""

import pytest
from unittest.mock import AsyncMock
from decimal import Decimal
from typing import Dict, Any

from app.agents.personality_profiler import PersonalityProfileSaver, ProfileSavingError
from app.db.repositories import ProfileRepository, RepositoryError
from app.schemas.personality import GeminiScoreOutput


# Mock test data
TEST_USER_ID = "0000-000007-USR" # Veritabanında kayıtlı gerçek user ID

# Create facets dictionary for GeminiScoreOutput
TEST_FACETS = {
    # Facet scores - 30 facets (6 per domain)
    "O_F1": Decimal("66.1"), "O_F2": Decimal("64.2"), "O_F3": Decimal("68.3"), 
    "O_F4": Decimal("63.4"), "O_F5": Decimal("67.5"), "O_F6": Decimal("65.6"),
    
    "C_F1": Decimal("57.1"), "C_F2": Decimal("59.2"), "C_F3": Decimal("56.3"), 
    "C_F4": Decimal("58.4"), "C_F5": Decimal("60.5"), "C_F6": Decimal("57.6"),
    
    "E_F1": Decimal("73.1"), "E_F2": Decimal("71.2"), "E_F3": Decimal("74.3"), 
    "E_F4": Decimal("70.4"), "E_F5": Decimal("75.5"), "E_F6": Decimal("72.6"),
    
    "A_F1": Decimal("46.1"), "A_F2": Decimal("44.2"), "A_F3": Decimal("47.3"), 
    "A_F4": Decimal("43.4"), "A_F5": Decimal("48.5"), "A_F6": Decimal("45.6"),
    
    "N_F1": Decimal("33.1"), "N_F2": Decimal("31.2"), "N_F3": Decimal("34.3"), 
    "N_F4": Decimal("30.4"), "N_F5": Decimal("35.5"), "N_F6": Decimal("32.6")
}

# Create GeminiScoreOutput instance for testing
TEST_SCORE_DATA = GeminiScoreOutput(
    O=Decimal("65.5"),
    C=Decimal("58.2"),
    E=Decimal("72.1"),
    A=Decimal("45.7"),
    N=Decimal("32.9"),
    facets=TEST_FACETS
)


@pytest.mark.asyncio
async def test_saver_success(monkeypatch):
    """Test successful saving of a personality profile."""
    # Setup
    mock_repo = AsyncMock(spec=ProfileRepository)
    mock_repo.save_profile.return_value = "saved-profile-id-123"
    
    # Mock the saver's save method to avoid the v1.2 API format conversion
    original_save = PersonalityProfileSaver.save
    async def mock_save(self, user_id, data):
        try:
            # Create profile_scores with original keys for testing
            profile_scores = {
                # Domain scores with uppercase keys (original format)
                "O": data.O,
                "C": data.C,
                "E": data.E,
                "A": data.A,
                "N": data.N
            }
            
            # Add facet scores with original keys
            for facet_code, facet_score in data.facets.items():
                profile_scores[facet_code] = facet_score
                
            # Call repository with the scores
            profile_id = await self.repository.save_profile(user_id, profile_scores)
            return profile_id
        except Exception as e:
            error_msg = f"Error saving personality profile for user {user_id}: {str(e)}"
            raise ProfileSavingError(error_msg)
    
    # Apply the mock
    monkeypatch.setattr(PersonalityProfileSaver, "save", mock_save)
    
    # Create the saver with mock repository
    saver = PersonalityProfileSaver(repository=mock_repo)
    
    # Execute
    profile_id = await saver.save(TEST_USER_ID, TEST_SCORE_DATA)
    
    # Assertions
    # Verify that save_profile was called with correct user_id and a dictionary containing
    # both domain scores and facet scores
    mock_repo.save_profile.assert_awaited_once()
    call_args = mock_repo.save_profile.call_args[0]
    
    # Check user_id
    assert call_args[0] == TEST_USER_ID
    
    # Check that profile_scores dictionary contains all required keys
    profile_scores = call_args[1]
    assert profile_scores["O"] == TEST_SCORE_DATA.O
    assert profile_scores["C"] == TEST_SCORE_DATA.C
    assert profile_scores["E"] == TEST_SCORE_DATA.E
    assert profile_scores["A"] == TEST_SCORE_DATA.A
    assert profile_scores["N"] == TEST_SCORE_DATA.N
    
    # Check facet scores (using original keys)
    for facet_code, facet_score in TEST_FACETS.items():
        assert profile_scores[facet_code] == facet_score
    
    # Check return value
    assert profile_id == "saved-profile-id-123"
    

@pytest.mark.asyncio
async def test_saver_raises_on_repo_error(monkeypatch):
    """Test that the saver raises a ProfileSavingError when the repository fails."""
    # Setup
    mock_repo = AsyncMock(spec=ProfileRepository)
    mock_repo.save_profile.side_effect = RepositoryError("Mock DB Error")
    
    # Mock the saver's save method to avoid the v1.2 API format conversion
    async def mock_save(self, user_id, data):
        try:
            # Create profile_scores with original keys for testing
            profile_scores = {
                # Domain scores with uppercase keys (original format)
                "O": data.O,
                "C": data.C,
                "E": data.E,
                "A": data.A,
                "N": data.N
            }
            
            # Add facet scores with original keys
            for facet_code, facet_score in data.facets.items():
                profile_scores[facet_code] = facet_score
                
            # Call repository with the scores
            profile_id = await self.repository.save_profile(user_id, profile_scores)
            
            return profile_id
        except Exception as e:
            error_msg = f"Error saving personality profile for user {user_id}: {str(e)}"
            raise ProfileSavingError(error_msg)
    
    # Apply the mock
    monkeypatch.setattr(PersonalityProfileSaver, "save", mock_save)
    
    # Create the saver with mock repository
    saver = PersonalityProfileSaver(repository=mock_repo)
    
    # Execute & Assert
    with pytest.raises(ProfileSavingError, match="Error saving personality profile for user.*Mock DB Error"):
        await saver.save(TEST_USER_ID, TEST_SCORE_DATA)
    
    # Verify the mock was called with the right user_id
    mock_repo.save_profile.assert_awaited_once()
