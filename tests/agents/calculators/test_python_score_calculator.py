"""
Unit tests for PythonScoreCalculator class.
These tests verify the correct functionality of each method in the calculator.
"""

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch
import asyncio

from app.core.config import Settings
from app.schemas.personality import ResponseDataItem
from app.agents.calculators.python_score_calculator import PythonScoreCalculator


@pytest.fixture
def calculator():
    """Create a PythonScoreCalculator instance with test settings."""
    settings = MagicMock(spec=Settings)
    settings.PERSONALITY_MEAN = Decimal('3.0')
    settings.PERSONALITY_STD_DEV = Decimal('0.5')
    return PythonScoreCalculator(settings=settings)


@pytest.fixture
def sample_responses():
    """Create a sample list of ResponseDataItem objects."""
    return [
        # O domain - normal scoring
        ResponseDataItem(
            response_id="r1", user_id="u1", question_id="q1",
            domain="O", facet=1, facet_code="O_F1",
            reverse_scored=False, answer_id="a4", point=4),
        # C domain - reverse scoring
        ResponseDataItem(
            response_id="r2", user_id="u1", question_id="q2",
            domain="C", facet=1, facet_code="C_F1",
            reverse_scored=True, answer_id="a2", point=2),
        # E domain - multiple responses for same facet
        ResponseDataItem(
            response_id="r3", user_id="u1", question_id="q3",
            domain="E", facet=1, facet_code="E_F1",
            reverse_scored=False, answer_id="a5", point=5),
        ResponseDataItem(
            response_id="r4", user_id="u1", question_id="q4",
            domain="E", facet=1, facet_code="E_F1",
            reverse_scored=False, answer_id="a1", point=1),
        # A domain - boundary values
        ResponseDataItem(
            response_id="r5", user_id="u1", question_id="q5",
            domain="A", facet=1, facet_code="A_F1",
            reverse_scored=False, answer_id="a1", point=1),
        # N domain - another facet
        ResponseDataItem(
            response_id="r6", user_id="u1", question_id="q6",
            domain="N", facet=1, facet_code="N_F1",
            reverse_scored=False, answer_id="a5", point=5),
    ]


def test_group_and_adjust_scores(calculator, sample_responses):
    """Test the _group_and_adjust_scores method."""
    # Act
    facet_adjusted_scores = calculator._group_and_adjust_scores(sample_responses)
    
    # Assert
    assert "O_F1" in facet_adjusted_scores
    assert "C_F1" in facet_adjusted_scores
    assert "E_F1" in facet_adjusted_scores
    assert "A_F1" in facet_adjusted_scores
    assert "N_F1" in facet_adjusted_scores
    
    # Normal scoring - point value remains the same
    assert facet_adjusted_scores["O_F1"] == [4]
    
    # Reverse scoring - point value is reversed (2 -> 4)
    assert facet_adjusted_scores["C_F1"] == [4]  # 2 reversed is 4 (6-2)
    
    # Multiple values for the same facet
    assert sorted(facet_adjusted_scores["E_F1"]) == [1, 5]
    
    # Boundary values
    assert facet_adjusted_scores["A_F1"] == [1]
    assert facet_adjusted_scores["N_F1"] == [5]


def test_calculate_facet_means(calculator):
    """Test the _calculate_facet_means method."""
    # Arrange
    facet_adjusted_scores = {
        "O_F1": [4, 2],         # Multiple values - should average
        "C_F1": [3],            # Single value
        "E_F1": [1, 3, 5],      # Multiple values with different spread
        "A_F1": [],             # Empty (edge case) - should default to mean
        "N_F1": [5, 5, 5, 5]    # All same values
    }
    
    # Act
    facet_raw_scores = calculator._calculate_facet_means(facet_adjusted_scores)
    
    # Assert
    assert facet_raw_scores["O_F1"] == Decimal('3.0')  # (4+2)/2
    assert facet_raw_scores["C_F1"] == Decimal('3.0')  # Single value
    assert facet_raw_scores["E_F1"] == Decimal('3.0')  # (1+3+5)/3
    assert facet_raw_scores["A_F1"] == Decimal('3.0')  # Default to PERSONALITY_MEAN
    assert facet_raw_scores["N_F1"] == Decimal('5.0')  # All 5s


def test_calculate_z_scores(calculator):
    """Test the _calculate_z_scores method."""
    # Arrange
    raw_facet_scores = {
        "O_F1": Decimal('3.0'),  # Equal to mean (z=0)
        "C_F1": Decimal('4.0'),  # Above mean (z=2)
        "E_F1": Decimal('2.0'),  # Below mean (z=-2)
        "A_F1": Decimal('5.0'),  # Maximum value (z=4)
        "N_F1": Decimal('1.0')   # Minimum value (z=-4)
    }
    
    # Act
    z_scores = calculator._calculate_z_scores(raw_facet_scores)
    
    # Assert
    assert z_scores["O_F1"] == Decimal('0')
    assert z_scores["C_F1"] == Decimal('2')
    assert z_scores["E_F1"] == Decimal('-2')
    assert z_scores["A_F1"] == Decimal('4')
    assert z_scores["N_F1"] == Decimal('-4')


def test_calculate_t_scores(calculator):
    """Test the _calculate_t_scores method."""
    # Arrange
    z_scores = {
        "O_F1": Decimal('0'),   # Should result in T=50
        "C_F1": Decimal('2'),   # Should result in T=70
        "E_F1": Decimal('-2'),  # Should result in T=30
        "A_F1": Decimal('4'),   # Should result in T=90
        "N_F1": Decimal('-4')   # Should result in T=10
    }
    
    # Act
    t_scores = calculator._calculate_t_scores(z_scores)
    
    # Assert
    assert t_scores["O_F1"] == Decimal('50.00')
    assert t_scores["C_F1"] == Decimal('70.00')
    assert t_scores["E_F1"] == Decimal('30.00')
    assert t_scores["A_F1"] == Decimal('90.00')
    assert t_scores["N_F1"] == Decimal('10.00')


def test_calculate_domain_means(calculator):
    """Test the _calculate_domain_means method."""
    # Arrange
    facet_t_scores = {
        "O_F1": Decimal('50.00'), "O_F2": Decimal('60.00'), "O_F3": Decimal('70.00'),
        "O_F4": Decimal('40.00'), "O_F5": Decimal('50.00'), "O_F6": Decimal('50.00'),
        
        "C_F1": Decimal('80.00'), "C_F2": Decimal('70.00'), "C_F3": Decimal('60.00'),
        "C_F4": Decimal('60.00'), "C_F5": Decimal('70.00'), "C_F6": Decimal('80.00'),
        
        "E_F1": Decimal('30.00'), "E_F2": Decimal('40.00'), "E_F3": Decimal('50.00'),
        "E_F4": Decimal('50.00'), "E_F5": Decimal('40.00'), "E_F6": Decimal('30.00'),
        
        "A_F1": Decimal('20.00'), "A_F2": Decimal('30.00'), "A_F3": Decimal('40.00'),
        "A_F4": Decimal('40.00'), "A_F5": Decimal('30.00'), "A_F6": Decimal('20.00'),
        
        "N_F1": Decimal('90.00'), "N_F2": Decimal('80.00'), "N_F3": Decimal('70.00'),
        "N_F4": Decimal('70.00'), "N_F5": Decimal('80.00'), "N_F6": Decimal('90.00')
    }
    
    # Act
    domain_t_scores = calculator._calculate_domain_means(facet_t_scores)
    
    # Assert
    assert domain_t_scores["O"] == Decimal('53.33')  # Rounded to 2 decimal places
    assert domain_t_scores["C"] == Decimal('70.00')
    assert domain_t_scores["E"] == Decimal('40.00')
    assert domain_t_scores["A"] == Decimal('30.00')
    assert domain_t_scores["N"] == Decimal('80.00')


def test_calculate_domain_means_missing_facets(calculator):
    """Test _calculate_domain_means with missing facets."""
    # Arrange - Missing O_F2 facet for O domain, but complete for all other domains
    incomplete_facet_t_scores = {
        # O domain - missing O_F2
        "O_F1": Decimal('50.00'), "O_F3": Decimal('70.00'),
        "O_F4": Decimal('40.00'), "O_F5": Decimal('50.00'), "O_F6": Decimal('50.00'),
        
        # Complete C domain
        "C_F1": Decimal('80.00'), "C_F2": Decimal('70.00'), "C_F3": Decimal('60.00'),
        "C_F4": Decimal('60.00'), "C_F5": Decimal('70.00'), "C_F6": Decimal('80.00'),
        
        # Complete E domain
        "E_F1": Decimal('30.00'), "E_F2": Decimal('40.00'), "E_F3": Decimal('50.00'),
        "E_F4": Decimal('50.00'), "E_F5": Decimal('40.00'), "E_F6": Decimal('30.00'),
        
        # Complete A domain
        "A_F1": Decimal('20.00'), "A_F2": Decimal('30.00'), "A_F3": Decimal('40.00'),
        "A_F4": Decimal('40.00'), "A_F5": Decimal('30.00'), "A_F6": Decimal('20.00'),
        
        # Complete N domain
        "N_F1": Decimal('90.00'), "N_F2": Decimal('80.00'), "N_F3": Decimal('70.00'),
        "N_F4": Decimal('70.00'), "N_F5": Decimal('80.00'), "N_F6": Decimal('90.00')
    }
    
    # Act & Assert
    with pytest.raises(ValueError, match="Domain O has 5 facets with scores, expected 6"):
        calculator._calculate_domain_means(incomplete_facet_t_scores)


def test_format_output(calculator):
    """Test the _format_output method."""
    # Arrange
    domain_t_scores = {
        "O": Decimal('53.33'),
        "C": Decimal('70.00'),
        "E": Decimal('40.00'),
        "A": Decimal('30.00'),
        "N": Decimal('80.00')
    }
    
    facet_t_scores = {
        "O_F1": Decimal('50.00'), "O_F2": Decimal('60.00'), "O_F3": Decimal('70.00'),
        "O_F4": Decimal('40.00'), "O_F5": Decimal('50.00'), "O_F6": Decimal('50.00'),
        
        "C_F1": Decimal('80.00'), "C_F2": Decimal('70.00'), "C_F3": Decimal('60.00'),
        "C_F4": Decimal('60.00'), "C_F5": Decimal('70.00'), "C_F6": Decimal('80.00'),
        
        "E_F1": Decimal('30.00'), "E_F2": Decimal('40.00'), "E_F3": Decimal('50.00'),
        "E_F4": Decimal('50.00'), "E_F5": Decimal('40.00'), "E_F6": Decimal('30.00'),
        
        "A_F1": Decimal('20.00'), "A_F2": Decimal('30.00'), "A_F3": Decimal('40.00'),
        "A_F4": Decimal('40.00'), "A_F5": Decimal('30.00'), "A_F6": Decimal('20.00'),
        
        "N_F1": Decimal('90.00'), "N_F2": Decimal('80.00'), "N_F3": Decimal('70.00'),
        "N_F4": Decimal('70.00'), "N_F5": Decimal('80.00'), "N_F6": Decimal('90.00')
    }
    
    # Act
    final_result = calculator._format_output(domain_t_scores, facet_t_scores)
    
    # Assert
    # Check domain scores - API v1.2 format uses lowercase keys
    assert final_result["o"] == Decimal('53.33')
    assert final_result["c"] == Decimal('70.00')
    assert final_result["e"] == Decimal('40.00')
    assert final_result["a"] == Decimal('30.00')
    assert final_result["n"] == Decimal('80.00')
    
    # Check facet scores are in a nested 'facets' key
    assert "facets" in final_result
    assert len(final_result["facets"]) == 30
    assert final_result["facets"]["o_f1"] == Decimal('50.00')
    assert final_result["facets"]["c_f1"] == Decimal('80.00')
    assert final_result["facets"]["e_f1"] == Decimal('30.00')
    assert final_result["facets"]["a_f1"] == Decimal('20.00')
    assert final_result["facets"]["n_f1"] == Decimal('90.00')


@pytest.mark.asyncio
async def test_calculate_scores_integration(calculator, sample_responses):
    """Test the main calculate_scores method integrating all steps."""
    # Act
    result = await calculator.calculate_scores(sample_responses)
    
    # Assert
    # Check that result has the expected structure
    assert isinstance(result, dict)
    assert all(domain in result for domain in ["o", "c", "e", "a", "n"])
    assert "facets" in result
    
    # All domains should have scores between 0 and 100
    for domain, score in result.items():
        if domain != "facets":
            assert Decimal('0') <= score <= Decimal('100')
    
    # Verify a few specific scores based on our sample data
    # (exact values will depend on defaults for missing facets)
    assert result["o"] is not None
    assert result["c"] is not None
    assert result["e"] is not None
    assert result["a"] is not None
    assert result["n"] is not None
    
    # Check facet scores that we explicitly set in sample_responses
    assert result["facets"]["o_f1"] is not None
    assert result["facets"]["c_f1"] is not None
    assert result["facets"]["e_f1"] is not None
    assert result["facets"]["a_f1"] is not None
    assert result["facets"]["n_f1"] is not None
    
    # For E_F1 facet with values 1 and 5, check expected calculation
    # Raw: (1+5)/2 = 3, Z-score: (3-3)/0.5 = 0, T-score: 50+10*0 = 50
    assert result["facets"]["e_f1"] == Decimal('50.00')


@pytest.mark.asyncio
async def test_calculate_scores_empty_responses(calculator):
    """Test calculate_scores with empty responses list."""
    # Act
    result = await calculator.calculate_scores([])
    
    # Assert - should return default values (all T-scores = 50.00)
    assert isinstance(result, dict)
    assert all(domain in result for domain in ["o", "c", "e", "a", "n"])
    assert "facets" in result
    
    # All domain scores should be 50.00
    for domain in ["o", "c", "e", "a", "n"]:
        assert result[domain] == Decimal('50.00')
    
    # All facet scores should be 50.00
    for facet_code in result["facets"]:
        assert result["facets"][facet_code] == Decimal('50.00')


@pytest.mark.asyncio
async def test_calculate_scores_all_invalid_responses(calculator):
    """Test calculate_scores when all responses are invalid but with valid schema."""
    # Arrange
    # Create responses that will be filtered out by the calculator's logic:
    # - Using point values outside the valid range (1-5)
    invalid_responses = [
        ResponseDataItem(
            response_id="r1", user_id="u1", question_id="q1",
            domain="O", facet=1, facet_code="O_F1",
            reverse_scored=False, answer_id="a0", point=0),  # Invalid point (too low)
        ResponseDataItem(
            response_id="r2", user_id="u1", question_id="q2",
            domain="C", facet=1, facet_code="C_F1",
            reverse_scored=True, answer_id="a6", point=6)   # Invalid point (too high)
    ]
    
    # Act
    result = await calculator.calculate_scores(invalid_responses)
    
    # Assert - should return default values (all T-scores = 50.00)
    assert isinstance(result, dict)
    assert all(domain in result for domain in ["o", "c", "e", "a", "n"])
    assert "facets" in result
    
    # All domain scores should be 50.00
    for domain in ["o", "c", "e", "a", "n"]:
        assert result[domain] == Decimal('50.00')
    
    # All facet scores should be 50.00
    for facet_code in result["facets"]:
        assert result["facets"][facet_code] == Decimal('50.00')
