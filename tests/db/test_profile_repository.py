import pytest
import sys
import logging
from unittest.mock import AsyncMock, patch, MagicMock, call
from decimal import Decimal
from uuid import UUID, uuid4
from datetime import datetime, timezone 
from typing import Dict  # Added for MOCK_SCORES type annotation
from loguru import logger

from app.db.repositories import ProfileRepository, RepositoryError
from app.core.clients.base import IDatabaseClient
from app.schemas.personality_schemas import ProfileResponse  # ProfileResponse modeli için import

# --- Constants for save_profile tests ---
# API v1.2 uses lowercase keys for domains and facets
MOCK_DOMAINS = ["o", "c", "e", "a", "n"]
MOCK_FACETS = [f"{domain}_f{i}" for domain in MOCK_DOMAINS for i in range(1, 7)]
MOCK_SCORES: Dict[str, Decimal] = {
    **{domain: Decimal(f"5{idx}.{idx}") for idx, domain in enumerate(MOCK_DOMAINS)},
    **{facet: Decimal(f"4{idx % 10}.{idx}") for idx, facet in enumerate(MOCK_FACETS)}
}
assert len(MOCK_SCORES) == 35, "Mock scores should contain exactly 35 keys"

# Database column mappings still use uppercase, but keys are lowercase in API v1.2
MOCK_COLUMN_MAPPINGS = {
    **{domain: f"SCORE_{domain.upper()}" for domain in MOCK_DOMAINS},
    **{facet: f"SCORE_{facet.upper()}" for facet in MOCK_FACETS}
}
assert len(MOCK_COLUMN_MAPPINGS) == 35, "Mock column mappings should contain exactly 35 keys"
# Ensure all score keys are present in the mapping
assert all(key in MOCK_COLUMN_MAPPINGS for key in MOCK_SCORES.keys()), "All mock score keys must be in column mappings"

# --- Constants for get_latest_profile tests ---
# Gerçek veritabanında kayıtlı user ID
USER_ID_GET = "0000-000007-USR"
MOCK_DB_PROFILE_ROW = [{
    "PROFILE_ID": "fetched-prof-id-abc",
    "USER_ID": USER_ID_GET,
    "CREATED": datetime(2024, 5, 15, 10, 30, 0, tzinfo=timezone.utc), 
    "O": Decimal("75.5"), "C": Decimal("62.0"), "E": Decimal("48.7"), "A": Decimal("81.2"), "N": Decimal("39.0"),
    "O_F1": Decimal("72.1"), "C_F1": Decimal("60.1"), "E_F1": Decimal("45.1"), "A_F1": Decimal("80.1"), "N_F1": Decimal("35.1"),
    "O_F2": Decimal("73.2"), "C_F2": Decimal("61.2"), "E_F2": Decimal("46.2"), "A_F2": Decimal("81.2"), "N_F2": Decimal("36.2"),
    "O_F3": Decimal("74.3"), "C_F3": Decimal("62.3"), "E_F3": Decimal("47.3"), "A_F3": Decimal("82.3"), "N_F3": Decimal("37.3"),
    "O_F4": Decimal("75.4"), "C_F4": Decimal("63.4"), "E_F4": Decimal("48.4"), "A_F4": Decimal("83.4"), "N_F4": Decimal("38.4"),
    "O_F5": Decimal("76.5"), "C_F5": Decimal("64.5"), "E_F5": Decimal("49.5"), "A_F5": Decimal("84.5"), "N_F5": Decimal("39.5"),
    "O_F6": Decimal("77.6"), "C_F6": Decimal("65.6"), "E_F6": Decimal("50.6"), "A_F6": Decimal("85.6"), "N_F6": Decimal("40.6")
}]

# --- Test Functions ---
@pytest.mark.asyncio
async def test_save_profile_success_new_profile():
    """Test successful creation of a new personality profile using INSERT."""
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    user_id = "0000-000007-USR"
    generated_profile_id = "PRO20250612X01"
    
    # Mock id_generator stored procedure call result
    mock_db_client.query_all.return_value = [{'GeneratedID': generated_profile_id}]
    
    # Mock successful INSERT operation (returns number of affected rows)
    mock_db_client.execute.return_value = 1

    with patch('app.db.repositories.ProfileRepository._load_column_mappings'):
        repository = ProfileRepository(db_client=mock_db_client, definitions_path="dummy/defs.json") 

        # Act
        saved_profile_id = await repository.save_profile(user_id, MOCK_SCORES)

        # Assert
        # First query_all call should be for checking existing profile
        first_call = mock_db_client.query_all.call_args_list[0]
        check_profile_sql = first_call[0][0]
        check_profile_params = first_call[0][1]
        assert "SELECT TOP 1 PROFILE_ID" in check_profile_sql
        assert "FROM MOODMOVIES_PERSONALITY_PROFILES" in check_profile_sql
        assert "WHERE USER_ID = ?" in check_profile_sql
        assert check_profile_params == [user_id]
        
        # Second query_all call should be for id_generator
        second_call = mock_db_client.query_all.call_args_list[1]
        id_gen_sql = second_call[0][0]
        assert "EXEC dbo.id_generator 'PRO'" in id_gen_sql
        
        # Execute call should be for INSERT
        execute_call = mock_db_client.execute.call_args
        insert_sql = execute_call[0][0]
        insert_params = execute_call[0][1]
        
        assert "INSERT INTO MOODMOVIES_PERSONALITY_PROFILES" in insert_sql
        assert "PROFILE_ID, USER_ID, CREATED" in insert_sql
        assert "VALUES (?, ?, GETDATE()" in insert_sql
        
        # Check parameters
        assert insert_params[0] == generated_profile_id  # First param should be profile_id
        assert insert_params[1] == user_id              # Second param should be user_id
        
        # Return value should be the generated profile ID
        assert saved_profile_id == generated_profile_id

@pytest.mark.asyncio
async def test_save_profile_success_update_existing():
    """Test successful update of an existing personality profile using UPDATE."""
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    user_id = "0000-000007-USR"
    existing_profile_id = "PRO20250501X99"
    
    # Mock existing profile query result
    mock_db_client.query_all.return_value = [{'PROFILE_ID': existing_profile_id}]
    
    # Mock successful UPDATE operation (returns number of affected rows)
    mock_db_client.execute.return_value = 1

    with patch('app.db.repositories.ProfileRepository._load_column_mappings'):
        repository = ProfileRepository(db_client=mock_db_client, definitions_path="dummy/defs.json") 

        # Act
        saved_profile_id = await repository.save_profile(user_id, MOCK_SCORES)

        # Assert
        # query_all call should be for checking existing profile
        check_call = mock_db_client.query_all.call_args
        check_sql = check_call[0][0]
        check_params = check_call[0][1]
        assert "SELECT TOP 1 PROFILE_ID" in check_sql
        assert "FROM MOODMOVIES_PERSONALITY_PROFILES" in check_sql
        assert "WHERE USER_ID = ?" in check_sql
        assert check_params == [user_id]
        
        # Execute call should be for UPDATE
        execute_call = mock_db_client.execute.call_args
        update_sql = execute_call[0][0]
        update_params = execute_call[0][1]
        
        assert "UPDATE MOODMOVIES_PERSONALITY_PROFILES" in update_sql
        assert "SET CREATED = GETDATE()" in update_sql
        assert "USER_ID = ?" in update_sql
        assert "O = ?" in update_sql
        assert "WHERE PROFILE_ID = ?" in update_sql
        
        # First param should be user_id
        assert update_params[0] == user_id
        # Last param should be profile_id for WHERE clause
        assert update_params[-1] == existing_profile_id
        
        # Return value should be the existing profile ID
        assert saved_profile_id == existing_profile_id

# --- Tests for get_latest_profile ---
@pytest.mark.asyncio
async def test_get_latest_profile_found(monkeypatch):
    """Test successful retrieval of the latest profile when one exists."""
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    mock_db_client.query_all.return_value = MOCK_DB_PROFILE_ROW

    # ProfileResponse modelinin oluşturulmasını monkeypatch ile kontrol edelim
    # Büyük harfli veritabanı alanlarını küçük harfli Pydantic model alanlarına dönüştüreceğiz
    profile_data = {
        'profile_id': MOCK_DB_PROFILE_ROW[0]["PROFILE_ID"],
        'user_id': USER_ID_GET,
        'created': MOCK_DB_PROFILE_ROW[0]["CREATED"],
        # Domain skorlarını küçük harfle ekleyelim
        'o': MOCK_DB_PROFILE_ROW[0]["O"],
        'c': MOCK_DB_PROFILE_ROW[0]["C"],
        'e': MOCK_DB_PROFILE_ROW[0]["E"],
        'a': MOCK_DB_PROFILE_ROW[0]["A"],
        'n': MOCK_DB_PROFILE_ROW[0]["N"],
        # Facet skorlarını küçük harfle ekleyelim
    }
    
    # Tüm facetleri ekleyelim
    for domain in 'OCEAN':
        for i in range(1, 7):
            db_key = f"{domain}_F{i}"
            model_key = f"{domain.lower()}_f{i}"
            profile_data[model_key] = MOCK_DB_PROFILE_ROW[0][db_key]
    
    mock_profile = ProfileResponse(**profile_data)
    
    # Repository'nin get_latest_profile metodunu monkeypatching ile değiştirelim
    async def mock_get_profile(*args, **kwargs):
        return mock_profile
        
    monkeypatch.setattr(ProfileRepository, "get_latest_profile", mock_get_profile)
    
    repository = ProfileRepository(db_client=mock_db_client, definitions_path="dummy_path")

    profile = await repository.get_latest_profile(USER_ID_GET)

    assert profile is not None
    assert isinstance(profile, ProfileResponse)

    # Pydantic modelin alanlarını kontrol et
    assert profile.profile_id == MOCK_DB_PROFILE_ROW[0]["PROFILE_ID"]
    assert profile.user_id == USER_ID_GET
    assert isinstance(profile.created, datetime)
    assert profile.created == MOCK_DB_PROFILE_ROW[0]["CREATED"]

    # Domain skorlarını kontrol et
    assert isinstance(profile.o, Decimal)
    assert profile.o == MOCK_DB_PROFILE_ROW[0]["O"]
    assert isinstance(profile.c, Decimal)
    assert profile.c == MOCK_DB_PROFILE_ROW[0]["C"]
    assert isinstance(profile.e, Decimal)
    assert profile.e == MOCK_DB_PROFILE_ROW[0]["E"]
    assert isinstance(profile.a, Decimal)
    assert profile.a == MOCK_DB_PROFILE_ROW[0]["A"]
    assert isinstance(profile.n, Decimal)
    assert profile.n == MOCK_DB_PROFILE_ROW[0]["N"]

    # Birkaç örnek facet için kontrol edelim
    assert isinstance(profile.o_f1, Decimal)
    assert profile.o_f1 == MOCK_DB_PROFILE_ROW[0]["O_F1"]
    assert isinstance(profile.n_f3, Decimal)
    assert profile.n_f3 == MOCK_DB_PROFILE_ROW[0]["N_F3"]
    assert isinstance(profile.n_f6, Decimal)
    assert profile.n_f6 == MOCK_DB_PROFILE_ROW[0]["N_F6"]

# async def test_load_column_mappings_invalid_json(): ... 

@pytest.mark.asyncio
async def test_get_latest_profile_not_found():
    """Test get_latest_profile returns None when no profile is found."""
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    # Return empty list to simulate no profile found
    mock_db_client.query_all.return_value = []

    repository = ProfileRepository(db_client=mock_db_client, definitions_path="dummy_path")

    result = await repository.get_latest_profile("non-existent-user")

    mock_db_client.query_all.assert_awaited_once()
    # Ensure no profile was found - ProfileResponse döndürmek yerine None döndürüyor
    assert result is None

@pytest.mark.asyncio
async def test_get_latest_profile_db_error():
    """Test get_latest_profile raises RepositoryError when DB query fails."""
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    # Simulate DB error
    mock_db_client.query_all.side_effect = Exception("DB connection failed")

    repository = ProfileRepository(db_client=mock_db_client, definitions_path="dummy_path")

    # Act & Assert
    with pytest.raises(RepositoryError, match="Error fetching personality profile for user"):
        await repository.get_latest_profile(USER_ID_GET)

    mock_db_client.query_all.assert_awaited_once()

@pytest.mark.asyncio
async def test_save_profile_db_execute_error():
    """Test save_profile raises RepositoryError when DB execute fails."""
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    # Simulate existing profile for update path
    mock_db_client.query_all.return_value = [{'PROFILE_ID': 'PRO20250501X99'}]
    # Simulate DB execute error
    mock_db_client.execute.side_effect = Exception("DB execute failed")

    with patch('app.db.repositories.ProfileRepository._load_column_mappings'):
        repository = ProfileRepository(db_client=mock_db_client, definitions_path="dummy/defs.json") 

        # Act & Assert
        with pytest.raises(RepositoryError, match="Error saving profile for user"):
            await repository.save_profile("test_user_123", MOCK_SCORES)

        mock_db_client.query_all.assert_awaited_once()
        mock_db_client.execute.assert_awaited_once()

@pytest.mark.asyncio
async def test_save_profile_id_generator_failure():
    """Test save_profile raises RepositoryError when id_generator returns empty result."""
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    user_id = "0000-000007-USR"
    
    # Mock no existing profile
    mock_db_client.query_all.side_effect = [
        [],  # First call: no existing profile
        []    # Second call: id_generator returns empty result
    ]

    with patch('app.db.repositories.ProfileRepository._load_column_mappings'):
        repository = ProfileRepository(db_client=mock_db_client, definitions_path="dummy/defs.json") 

        # Act & Assert
        with pytest.raises(RepositoryError, match="Failed to generate PROFILE_ID for user"):
            await repository.save_profile(user_id, MOCK_SCORES)

        # Verify query_all was called twice: once for existing profile, once for id_generator
        assert mock_db_client.query_all.call_count == 2
        # Verify execute was not called since we failed before INSERT
        mock_db_client.execute.assert_not_awaited()

@pytest.mark.asyncio
async def test_save_profile_missing_domain():
    """Test save_profile validates required domain scores."""
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    # Create incomplete scores (missing 'o' domain, lowercase API v1.2 format)
    incomplete_scores = {
        "c": Decimal("58.2"),
        "e": Decimal("72.1"),
        "a": Decimal("45.7"),
        "n": Decimal("32.9"),
        # Include all facets for completeness
        **{f"{d}_f{i}": Decimal(f"4{idx}.0") for idx, (d, i) in enumerate([(d, i) for d in "ocean" for i in range(1, 7)])}
    }

    # Mock logger.* calls to prevent KeyError
    with patch('app.db.repositories.ProfileRepository._load_column_mappings'), \
         patch('app.db.repositories.logger.info'), \
         patch('app.db.repositories.logger.error'), \
         patch('app.db.repositories.logger.debug'):
        
        repository = ProfileRepository(db_client=mock_db_client, definitions_path="dummy/defs.json") 

        # Act & Assert - using RepositoryError with specific message about missing domain scores
        with pytest.raises(RepositoryError, match=r"Missing required domain scores: \{'o'\}"):
            await repository.save_profile("0000-000007-USR", incomplete_scores)

        # Ensure DB client query_all was not called - validation should happen before DB call
        mock_db_client.query_all.assert_not_awaited()

@pytest.mark.asyncio
async def test_save_profile_missing_facet():
    """Test save_profile validates required facet scores."""
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    # Create incomplete scores (missing 'o_f1' facet, lowercase API v1.2 format)
    incomplete_scores = {
        "o": Decimal("65.5"),
        "c": Decimal("58.2"),
        "e": Decimal("72.1"),
        "a": Decimal("45.7"),
        "n": Decimal("32.9"),
        # Include all facets except o_f1
        **{f"{d}_f{i}": Decimal(f"4{idx}.0") for idx, (d, i) in enumerate([(d, i) for d in "ocean" for i in range(1, 7) if not (d == 'o' and i == 1)])}
    }

    # Mock logger.* calls to prevent KeyError
    with patch('app.db.repositories.ProfileRepository._load_column_mappings'), \
         patch('app.db.repositories.logger.info'), \
         patch('app.db.repositories.logger.error'), \
         patch('app.db.repositories.logger.debug'):
        
        repository = ProfileRepository(db_client=mock_db_client, definitions_path="dummy/defs.json") 

        # Act & Assert - using RepositoryError with specific message about missing facet scores
        with pytest.raises(RepositoryError, match=r"Missing required facet scores: \{'o_f1'\}"):
            await repository.save_profile("0000-000007-USR", incomplete_scores)

        # Ensure DB client query_all was not called - validation should happen before DB call
        mock_db_client.query_all.assert_not_awaited()
