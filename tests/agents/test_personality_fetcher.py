import pytest
from unittest.mock import AsyncMock, MagicMock # Mocking için
from typing import List, Dict, Any
# Test edilecek sınıf ve fırlatmasını beklediğimiz hata
from app.agents.personality_profiler import PersonalityDataFetcher, PersonalityDataFetcherError
# Bağımlı olduğu sınıf (mock edilecek) ve döndürdüğü tip
from app.db.repositories import ResponseRepository, RepositoryError
from app.schemas.personality import ResponseDataItem
# Decimal tipini test verisinde kullanabiliriz
from decimal import Decimal
import logging # Opsiyonel log kontrolü için

# --- Test Verileri ---

USER_ID = "0000-000007-USR" # Veritabanında kayıtlı gerçek user ID

# SQL sorgusundan dönmesi beklenen mock veri (QUESTION ve ANSWER kaldırıldı)
VALID_DB_RESPONSE: List[Dict[str, Any]] = [
    {"RESPONSE_ID": "resp1", "USER_ID": USER_ID, "QUESTION_ID": "q1", "DOMAIN": "O", "FACET": 1, "FACET_CODE": "O1", "REVERSE_SCORED": 0, "ANSWER_ID": "ans1", "POINT": 5},
    {"RESPONSE_ID": "resp2", "USER_ID": USER_ID, "QUESTION_ID": "q2", "DOMAIN": "C", "FACET": 2, "FACET_CODE": "C2", "REVERSE_SCORED": 1, "ANSWER_ID": "ans2", "POINT": 1},
    {"RESPONSE_ID": "resp3", "USER_ID": USER_ID, "QUESTION_ID": "q3", "DOMAIN": "E", "FACET": 3, "FACET_CODE": "E3", "REVERSE_SCORED": 0, "ANSWER_ID": "ans3", "POINT": 4},
    {"RESPONSE_ID": "resp4", "USER_ID": USER_ID, "QUESTION_ID": "q4", "DOMAIN": "N", "FACET": 6, "FACET_CODE": "N6", "REVERSE_SCORED": 1, "ANSWER_ID": "ans4", "POINT": 2},
]

# Pydantic parse hatasına neden olacak geçersiz veritabanı yanıtı (eksik anahtar: POINT eksik, QUESTION/ANSWER kaldırıldı)
INVALID_DB_RESPONSE_MISSING_KEY: List[Dict[str, Any]] = [
    {"RESPONSE_ID": "resp1", "USER_ID": USER_ID, "QUESTION_ID": "q1", "DOMAIN": "O", "FACET": 1, "FACET_CODE": "O1", "REVERSE_SCORED": 0, "ANSWER_ID": "ans1", "POINT": 5},
    # 'POINT' anahtarı eksik, diğer alanlar tam
    {"RESPONSE_ID": "resp2", "USER_ID": USER_ID, "QUESTION_ID": "q2", "DOMAIN": "C", "FACET": 2, "FACET_CODE": "C2", "REVERSE_SCORED": 1, "ANSWER_ID": "ans2"},
    {"RESPONSE_ID": "resp3", "USER_ID": USER_ID, "QUESTION_ID": "q3", "DOMAIN": "E", "FACET": 3, "FACET_CODE": "E3", "REVERSE_SCORED": 0, "ANSWER_ID": "ans3", "POINT": 4},
]

# Pydantic parse hatasına neden olacak geçersiz veritabanı yanıtı (yanlış tip: POINT string, QUESTION/ANSWER kaldırıldı)
INVALID_DB_RESPONSE_WRONG_TYPE: List[Dict[str, Any]] = [
    {"RESPONSE_ID": "resp1", "USER_ID": USER_ID, "QUESTION_ID": "q1", "DOMAIN": "O", "FACET": 1, "FACET_CODE": "O1", "REVERSE_SCORED": 0, "ANSWER_ID": "ans1", "POINT": 5},
    # 'POINT' int olmalı, string verilmiş, diğer alanlar tam
    {"RESPONSE_ID": "resp2", "USER_ID": USER_ID, "QUESTION_ID": "q2", "DOMAIN": "C", "FACET": 2, "FACET_CODE": "C2", "REVERSE_SCORED": 1, "ANSWER_ID": "ans2", "POINT": "one"},
    {"RESPONSE_ID": "resp3", "USER_ID": USER_ID, "QUESTION_ID": "q3", "DOMAIN": "E", "FACET": 3, "FACET_CODE": "E3", "REVERSE_SCORED": 0, "ANSWER_ID": "ans3", "POINT": 4},
]

# Beklenen ResponseDataItem listesi (VALID_DB_RESPONSE'dan parse edilmiş, question/answer kaldırıldı)
EXPECTED_RESPONSE_DATA_ITEMS = [
    ResponseDataItem(response_id="resp1", user_id=USER_ID, question_id="q1", domain="O", facet=1, facet_code="O1", reverse_scored=False, answer_id="ans1", point=5),
    ResponseDataItem(response_id="resp2", user_id=USER_ID, question_id="q2", domain="C", facet=2, facet_code="C2", reverse_scored=True, answer_id="ans2", point=1),
    ResponseDataItem(response_id="resp3", user_id=USER_ID, question_id="q3", domain="E", facet=3, facet_code="E3", reverse_scored=False, answer_id="ans3", point=4),
    ResponseDataItem(response_id="resp4", user_id=USER_ID, question_id="q4", domain="N", facet=6, facet_code="N6", reverse_scored=True, answer_id="ans4", point=2),
]

# --- Test Fonksiyonları ---

@pytest.mark.asyncio
async def test_fetcher_success():
    """Test successful data fetching and parsing with correct fields."""
    # Mock ResponseRepository
    mock_repo = AsyncMock(spec=ResponseRepository)
    mock_repo.get_user_responses.return_value = VALID_DB_RESPONSE

    # Initialize Fetcher with mock repo (using correct argument name 'repository')
    fetcher = PersonalityDataFetcher(repository=mock_repo)

    # Call fetch_data
    result = await fetcher.fetch_data(USER_ID)

    # Assertions
    assert result == EXPECTED_RESPONSE_DATA_ITEMS # Beklenen sonuç listesi artık güncel modellere sahip
    mock_repo.get_user_responses.assert_awaited_once_with(USER_ID)

@pytest.mark.asyncio
async def test_fetcher_no_responses():
    """Test fetching when no responses are found."""
    # Mock ResponseRepository
    mock_repo = AsyncMock(spec=ResponseRepository)
    mock_repo.get_user_responses.return_value = [] # Boş liste döndür

    # Initialize Fetcher (using correct argument name 'repository')
    fetcher = PersonalityDataFetcher(repository=mock_repo)

    # Call fetch_data
    result = await fetcher.fetch_data(USER_ID)

    # Assertions
    assert result == []
    mock_repo.get_user_responses.assert_awaited_once_with(USER_ID)
    # Opsiyonel: Log kontrolü (caplog fixture gerektirir)
    # assert "No responses found for user" in caplog.text

@pytest.mark.asyncio
async def test_fetcher_db_error():
    """Test fetching when the repository raises a database error."""
    # Mock ResponseRepository to raise RepositoryError
    mock_repo = AsyncMock(spec=ResponseRepository)
    db_error_message = "Database connection failed"
    mock_repo.get_user_responses.side_effect = RepositoryError(db_error_message)

    # Initialize Fetcher (using correct argument name 'repository')
    fetcher = PersonalityDataFetcher(repository=mock_repo)

    # Assert that PersonalityDataFetcherError is raised with the exact message
    # Match argümanı doğrudan string olarak ayarlandı
    expected_error_message = f"Error fetching personality data for user {USER_ID}: {db_error_message}"
    with pytest.raises(PersonalityDataFetcherError, match=expected_error_message):
        await fetcher.fetch_data(USER_ID)

    mock_repo.get_user_responses.assert_awaited_once_with(USER_ID)

@pytest.mark.asyncio
async def test_fetcher_parse_error_missing_key(monkeypatch):
    """Test fetching with data causing a Pydantic parse error (missing key)."""
    # Mock ResponseRepository with invalid data (missing key)
    mock_repo = AsyncMock(spec=ResponseRepository)
    mock_repo.get_user_responses.return_value = INVALID_DB_RESPONSE_MISSING_KEY

    # Setup log capture for loguru
    log_messages = []
    def mock_log_warning(message, *args, **kwargs):
        log_messages.append(message)
    
    # Monkeypatch loguru logger.warning
    monkeypatch.setattr("app.agents.personality_profiler.logger.warning", mock_log_warning)

    # Initialize Fetcher
    fetcher = PersonalityDataFetcher(repository=mock_repo)

    # Call fetch_data
    result = await fetcher.fetch_data(USER_ID)

    # Assertions - The item with missing key should be skipped
    assert len(result) == len(INVALID_DB_RESPONSE_MISSING_KEY) - 1
    # Check that the valid items are still returned (Updated expected items without question/answer)
    valid_items_expected = [
        ResponseDataItem(response_id="resp1", user_id=USER_ID, question_id="q1", domain="O", facet=1, facet_code="O1", reverse_scored=False, answer_id="ans1", point=5),
        ResponseDataItem(response_id="resp3", user_id=USER_ID, question_id="q3", domain="E", facet=3, facet_code="E3", reverse_scored=False, answer_id="ans3", point=4),
    ]
    assert result == valid_items_expected
    mock_repo.get_user_responses.assert_awaited_once_with(USER_ID)

    # Check that error messages were logged
    assert any("Error processing response:" in msg for msg in log_messages)
    assert any("skipping this response" in msg for msg in log_messages)

@pytest.mark.asyncio
async def test_fetcher_parse_error_wrong_type(monkeypatch):
    """Test PersonalityDataFetcher parse hata durumunu (yanlış tip)."""
    # Setup mocks
    mock_repo = AsyncMock(spec=ResponseRepository)
    mock_repo.get_user_responses.return_value = INVALID_DB_RESPONSE_WRONG_TYPE
    
    # Setup log capture for loguru
    log_messages = []
    def mock_log_warning(message, *args, **kwargs):
        log_messages.append(message)
    
    # Monkeypatch loguru logger.warning
    monkeypatch.setattr("app.agents.personality_profiler.logger.warning", mock_log_warning)

    # Initialize Fetcher
    fetcher = PersonalityDataFetcher(repository=mock_repo)

    # Call fetch_data
    result = await fetcher.fetch_data(USER_ID)

    # Assertions - The item with wrong type should be skipped
    assert len(result) == len(INVALID_DB_RESPONSE_WRONG_TYPE) - 1
    
    # Check that the valid items are still returned (Updated expected items without question/answer)
    valid_items_expected = [
        ResponseDataItem(response_id="resp1", user_id=USER_ID, question_id="q1", domain="O", facet=1, facet_code="O1", reverse_scored=False, answer_id="ans1", point=5),
        ResponseDataItem(response_id="resp3", user_id=USER_ID, question_id="q3", domain="E", facet=3, facet_code="E3", reverse_scored=False, answer_id="ans3", point=4),
    ]
    assert result == valid_items_expected
    mock_repo.get_user_responses.assert_awaited_once_with(USER_ID)

    # Check that error messages were logged
    assert any("Error processing response:" in msg for msg in log_messages)
    assert any("skipping this response" in msg for msg in log_messages)
