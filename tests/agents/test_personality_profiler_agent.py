"""Tests for the PersonalityProfilerAgent class."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal
from typing import Dict, Any, List

from app.agents.personality_profiler import (
    PersonalityProfilerAgent,
    PersonalityProfilerError,
    PersonalityDataFetcherError,
    ScoreCalculationError,
    ValidationError,
    ProfileSavingError,
    PersonalityDataFetcher,
    PersonalityResultValidator,
    PersonalityProfileSaver
)
from app.agents.common.interfaces import IDataFetcher, IScoreCalculator, IValidator, ISaver
from app.schemas.personality import ResponseDataItem, GeminiScoreOutput
from app.schemas.personality_schemas import ProfileAnalysisResult, ScoreResult


# Create some mock response data
MOCK_RESPONSES = [
    ResponseDataItem(
        RESPONSE_ID="resp-1",
        USER_ID="0000-000007-USR",
        QUESTION_ID="q-001",
        DOMAIN="O",
        FACET=1,
        FACET_CODE="O_F1",
        REVERSE_SCORED=False,
        ANSWER_ID="a-001",
        POINT=4
    ),
    ResponseDataItem(
        RESPONSE_ID="resp-2",
        USER_ID="0000-000007-USR",
        QUESTION_ID="q-002",
        DOMAIN="C",
        FACET=2,
        FACET_CODE="C_F2",
        REVERSE_SCORED=True,
        ANSWER_ID="a-002",
        POINT=2
    )
]

# Create mock scores dictionary (what calculator returns)
MOCK_SCORES_DICT = {
    "O": Decimal("65.5"),
    "C": Decimal("58.2"),
    "E": Decimal("72.1"),
    "A": Decimal("45.7"),
    "N": Decimal("32.9"),
    "facets": {
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
}

# Create mock validated scores (what validator returns)
MOCK_VALIDATED_SCORES = GeminiScoreOutput(
    O=Decimal("65.5"),
    C=Decimal("58.2"),
    E=Decimal("72.1"),
    A=Decimal("45.7"),
    N=Decimal("32.9"),
    facets={
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
)


@pytest.mark.asyncio
async def test_agent_success_flow():
    """Test the successful flow of the personality profiler agent."""
    # Create mock dependencies
    mock_fetcher = AsyncMock(spec=IDataFetcher)
    mock_calculator = AsyncMock(spec=IScoreCalculator)
    mock_validator = MagicMock(spec=IValidator)
    mock_saver = AsyncMock(spec=ISaver)
    
    # Configure mock return values
    mock_fetcher.fetch_data.return_value = MOCK_RESPONSES
    mock_calculator.calculate_scores.return_value = MOCK_SCORES_DICT
    
    # MOCK_VALIDATED_SCORES bir GeminiScoreOutput nesnesi, onun yerine ScoreResult nesnesi kullanalım
    # GeminiScoreOutput -> ScoreResult dönüştürme fonksiyonu
    def convert_to_score_result(gemini_output):
        return ScoreResult(
            # Domain skorları küçük harfle (API v1.2 formatı)
            o=gemini_output.O,
            c=gemini_output.C,
            e=gemini_output.E,
            a=gemini_output.A,
            n=gemini_output.N,
            # Facet skorlarını küçük harfle anahtarlarla oluştur
            facets={
                k.lower(): v for k, v in gemini_output.facets.items()
            }
        )
    
    # Validator'un ScoreResult döndürmesini sağla (GeminiScoreOutput yerine)
    mock_validator.validate.return_value = convert_to_score_result(MOCK_VALIDATED_SCORES)
    
    # mock_saver.save'in dönüş değerini profile_id olarak ayarla
    mock_saver.save.return_value = "final-saved-profile-id"
    
    # Create the agent with mock dependencies
    agent = PersonalityProfilerAgent(
        data_fetcher=mock_fetcher,
        score_calculator=mock_calculator,
        validator=mock_validator,
        saver=mock_saver
    )
    
    # Call the method to test
    result = await agent.process_user_test("0000-000007-USR")
    
    # Verify the fetcher was called correctly
    mock_fetcher.fetch_data.assert_called_once_with("0000-000007-USR")
    
    # Verify the calculator was called with responses from fetcher
    mock_calculator.calculate_scores.assert_called_once_with(MOCK_RESPONSES)
    
    # Verify the validator was called with scores from calculator
    mock_validator.validate.assert_called_once_with(MOCK_SCORES_DICT)
    
    # Verify the saver was called with validated scores
    mock_saver.save.assert_called_once_with("0000-000007-USR", convert_to_score_result(MOCK_VALIDATED_SCORES))
    
    # Verify the returned profile_id matches what was returned by the saver
    assert result.profile_id == "final-saved-profile-id"
    
    # Verify scores is a ScoreResult type
    assert isinstance(result.scores, ScoreResult)


@pytest.mark.asyncio
async def test_agent_handles_fetcher_error():
    """Test that the agent properly handles errors from the data fetcher."""
    # Setup mock dependencies
    mock_fetcher = AsyncMock(spec=IDataFetcher)
    mock_calculator = AsyncMock(spec=IScoreCalculator)
    mock_validator = AsyncMock(spec=IValidator)
    mock_saver = AsyncMock(spec=ISaver)
    
    # Configure mock to raise an error
    mock_fetcher.fetch_data.side_effect = PersonalityDataFetcherError("Fetch failed")
    
    # Create the agent with mock dependencies
    agent = PersonalityProfilerAgent(
        data_fetcher=mock_fetcher,
        score_calculator=mock_calculator,
        validator=mock_validator,
        saver=mock_saver
    )
    
    # Execute and assert the expected error is raised
    with pytest.raises(PersonalityDataFetcherError, match="Fetch failed"):
        await agent.process_user_test("test-user-id")
    
    # Verify that fetch_data was called, but no other methods were called
    mock_fetcher.fetch_data.assert_awaited_once()
    mock_calculator.calculate_scores.assert_not_awaited()
    mock_validator.validate.assert_not_called()
    mock_saver.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_agent_handles_calculator_error():
    """Test that the agent properly handles errors from the score calculator."""
    # Setup mock dependencies
    mock_fetcher = AsyncMock(spec=IDataFetcher)
    mock_calculator = AsyncMock(spec=IScoreCalculator)
    mock_validator = AsyncMock(spec=IValidator)
    mock_saver = AsyncMock(spec=ISaver)
    
    # Configure mocks for the test scenario
    mock_fetcher.fetch_data.return_value = MOCK_RESPONSES
    mock_calculator.calculate_scores.side_effect = ValueError("Calc failed")
    
    # Create the agent with mock dependencies
    agent = PersonalityProfilerAgent(
        data_fetcher=mock_fetcher,
        score_calculator=mock_calculator,
        validator=mock_validator,
        saver=mock_saver
    )
    
    # Execute and assert the expected error is raised
    with pytest.raises(ScoreCalculationError, match="Error calculating scores: Calc failed"):
        await agent.process_user_test("test-user-id")
    
    # Verify correct methods were called/not called
    mock_fetcher.fetch_data.assert_awaited_once()
    mock_calculator.calculate_scores.assert_awaited_once_with(MOCK_RESPONSES)
    mock_validator.validate.assert_not_called()
    mock_saver.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_agent_handles_validator_error():
    """Test that the agent properly handles errors from the validator."""
    # Setup mock dependencies
    mock_fetcher = AsyncMock(spec=IDataFetcher)
    mock_calculator = AsyncMock(spec=IScoreCalculator)
    mock_validator = AsyncMock(spec=IValidator)
    mock_saver = AsyncMock(spec=ISaver)
    
    # Configure mocks for the test scenario
    mock_fetcher.fetch_data.return_value = MOCK_RESPONSES
    mock_calculator.calculate_scores.return_value = MOCK_SCORES_DICT
    mock_validator.validate.side_effect = ValidationError("Validation failed")
    
    # Create the agent with mock dependencies
    agent = PersonalityProfilerAgent(
        data_fetcher=mock_fetcher,
        score_calculator=mock_calculator,
        validator=mock_validator,
        saver=mock_saver
    )
    
    # Execute and assert the expected error is raised
    with pytest.raises(ValidationError, match="Validation failed"):
        await agent.process_user_test("test-user-id")
    
    # Verify correct methods were called/not called
    mock_fetcher.fetch_data.assert_awaited_once()
    mock_calculator.calculate_scores.assert_awaited_once()
    mock_validator.validate.assert_called_once_with(MOCK_SCORES_DICT)
    mock_saver.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_agent_handles_saver_error():
    """Test that the agent properly handles errors from the saver."""
    # Setup mock dependencies
    mock_fetcher = AsyncMock(spec=IDataFetcher)
    mock_calculator = AsyncMock(spec=IScoreCalculator)
    mock_validator = AsyncMock(spec=IValidator)
    mock_saver = AsyncMock(spec=ISaver)
    
    # Configure mocks for the test scenario
    mock_fetcher.fetch_data.return_value = MOCK_RESPONSES
    mock_calculator.calculate_scores.return_value = MOCK_SCORES_DICT
    mock_validator.validate.return_value = MOCK_VALIDATED_SCORES
    mock_saver.save.side_effect = ProfileSavingError("Save failed")
    
    # Create the agent with mock dependencies
    agent = PersonalityProfilerAgent(
        data_fetcher=mock_fetcher,
        score_calculator=mock_calculator,
        validator=mock_validator,
        saver=mock_saver
    )
    
    # Execute and assert the expected error is raised
    with pytest.raises(ProfileSavingError, match="Error saving profile: Save failed"):
        await agent.process_user_test("test-user-id")
    
    # Verify all methods up to save were called correctly
    mock_fetcher.fetch_data.assert_awaited_once()
    mock_calculator.calculate_scores.assert_awaited_once()
    mock_validator.validate.assert_called_once()
    mock_saver.save.assert_awaited_once_with("test-user-id", MOCK_VALIDATED_SCORES)
