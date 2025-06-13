import pytest
import asyncio
from decimal import Decimal
from app.core.config import get_settings
from app.agents.personality_profiler import PersonalityProfilerAgent, PersonalityResultValidator
from app.agents.calculators.python_score_calculator import PythonScoreCalculator
from app.schemas.personality import ResponseDataItem

# Import mock data and scenarios
from tests.agents.mock_data import (
    MOCK_RESPONSES_SCENARIO_NEUTRAL,
    MOCK_RESPONSES_SCENARIO_HIGH_O_LOW_C,
    MOCK_RESPONSES_SCENARIO_HIGH_N_LOW_A
)

# --- Golden Results (Placeholder - Calculate these externally!) ---

# Note: Facet keys should ideally match the exact keys returned by your calculation logic
# Example: "O_F1", "C_F1", etc. Adjust if your keys are different.

GOLDEN_RESULTS_NEUTRAL = {
    "o": Decimal("50.00"), "c": Decimal("50.00"), "e": Decimal("50.00"), "a": Decimal("50.00"), "n": Decimal("50.00"),
    "facets": {
        # Add all 30 facets with expected 50.0 for neutral
        "o_f1": Decimal("50.00"), "o_f2": Decimal("50.00"), "o_f3": Decimal("50.00"), "o_f4": Decimal("50.00"), "o_f5": Decimal("50.00"), "o_f6": Decimal("50.00"),
        "c_f1": Decimal("50.00"), "c_f2": Decimal("50.00"), "c_f3": Decimal("50.00"), "c_f4": Decimal("50.00"), "c_f5": Decimal("50.00"), "c_f6": Decimal("50.00"),
        "e_f1": Decimal("50.00"), "e_f2": Decimal("50.00"), "e_f3": Decimal("50.00"), "e_f4": Decimal("50.00"), "e_f5": Decimal("50.00"), "e_f6": Decimal("50.00"),
        "a_f1": Decimal("50.00"), "a_f2": Decimal("50.00"), "a_f3": Decimal("50.00"), "a_f4": Decimal("50.00"), "a_f5": Decimal("50.00"), "a_f6": Decimal("50.00"),
        "n_f1": Decimal("50.00"), "n_f2": Decimal("50.00"), "n_f3": Decimal("50.00"), "n_f4": Decimal("50.00"), "n_f5": Decimal("50.00"), "n_f6": Decimal("50.00"),
    }
}

GOLDEN_RESULTS_HIGH_O_LOW_C = {
    "o": Decimal("90.00"), 
    "c": Decimal("10.00"), 
    "e": Decimal("50.00"), 
    "a": Decimal("50.00"), 
    "n": Decimal("50.00"), 
    "facets": {
        # Add all 30 facets with externally calculated values
        "o_f1": Decimal("90.00"), "o_f2": Decimal("90.00"), "o_f3": Decimal("90.00"), "o_f4": Decimal("90.00"), "o_f5": Decimal("90.00"), "o_f6": Decimal("90.00"),
        "c_f1": Decimal("10.00"), "c_f2": Decimal("10.00"), "c_f3": Decimal("10.00"), "c_f4": Decimal("10.00"), "c_f5": Decimal("10.00"), "c_f6": Decimal("10.00"),
        "e_f1": Decimal("50.00"), "e_f2": Decimal("50.00"), "e_f3": Decimal("50.00"), "e_f4": Decimal("50.00"), "e_f5": Decimal("50.00"), "e_f6": Decimal("50.00"),
        "a_f1": Decimal("50.00"), "a_f2": Decimal("50.00"), "a_f3": Decimal("50.00"), "a_f4": Decimal("50.00"), "a_f5": Decimal("50.00"), "a_f6": Decimal("50.00"),
        "n_f1": Decimal("50.00"), "n_f2": Decimal("50.00"), "n_f3": Decimal("50.00"), "n_f4": Decimal("50.00"), "n_f5": Decimal("50.00"), "n_f6": Decimal("50.00"),
    }
}

GOLDEN_RESULTS_HIGH_N_LOW_A = {
    # !!! CALCULATE THESE VALUES EXTERNALLY !!!
    "o": Decimal("50.00"), 
    "c": Decimal("50.00"), 
    "e": Decimal("50.00"), 
    "a": Decimal("10.00"), 
    "n": Decimal("90.00"), 
    "facets": {
        # Add all 30 facets with externally calculated values
        "o_f1": Decimal("50.00"), "o_f2": Decimal("50.00"), "o_f3": Decimal("50.00"), "o_f4": Decimal("50.00"), "o_f5": Decimal("50.00"), "o_f6": Decimal("50.00"),
        "c_f1": Decimal("50.00"), "c_f2": Decimal("50.00"), "c_f3": Decimal("50.00"), "c_f4": Decimal("50.00"), "c_f5": Decimal("50.00"), "c_f6": Decimal("50.00"),
        "e_f1": Decimal("50.00"), "e_f2": Decimal("50.00"), "e_f3": Decimal("50.00"), "e_f4": Decimal("50.00"), "e_f5": Decimal("50.00"), "e_f6": Decimal("50.00"),
        "a_f1": Decimal("10.00"), "a_f2": Decimal("10.00"), "a_f3": Decimal("10.00"), "a_f4": Decimal("10.00"), "a_f5": Decimal("10.00"), "a_f6": Decimal("10.00"),
        "n_f1": Decimal("90.00"), "n_f2": Decimal("90.00"), "n_f3": Decimal("90.00"), "n_f4": Decimal("90.00"), "n_f5": Decimal("90.00"), "n_f6": Decimal("90.00"),
    }
}

# --- Test Cases --- 
test_cases = [
    {
        "id": "neutral_scenario",
        "responses": MOCK_RESPONSES_SCENARIO_NEUTRAL,
        "expected": GOLDEN_RESULTS_NEUTRAL
    },
    {
        "id": "high_o_low_c_scenario",
        "responses": MOCK_RESPONSES_SCENARIO_HIGH_O_LOW_C,
        "expected": GOLDEN_RESULTS_HIGH_O_LOW_C
    },
    {
        "id": "high_n_low_a_scenario",
        "responses": MOCK_RESPONSES_SCENARIO_HIGH_N_LOW_A,
        "expected": GOLDEN_RESULTS_HIGH_N_LOW_A
    },
]

# --- Pytest Fixture (Example) ---
# You might use fixtures to set up the agent or other dependencies
# @pytest.fixture
# def profiler_agent():
#     # Setup agent with mock dependencies if needed
#     return PersonalityProfilerAgent(...)

# --- Test Function (Placeholder - Implement actual test logic) ---
@pytest.mark.asyncio
@pytest.mark.parametrize("test_case", test_cases, ids=[tc["id"] for tc in test_cases])
async def test_personality_calculation(test_case): 
    """Tests the personality calculation for different scenarios."""
    # 1. Arrange:
    mock_responses = test_case["responses"]
    expected_results = test_case["expected"]
    user_id = mock_responses[0]["user_id"] # Assuming all responses have the same user_id

    # Instantiate necessary components
    settings = get_settings()
    score_calculator = PythonScoreCalculator(settings=settings)
    result_validator = PersonalityResultValidator() # Instantiate validator

    print(f"\nTesting scenario: {test_case['id']}")

    # 2. Act:
    # Convert mock response dicts to Pydantic models
    try:
        response_data_items = [ResponseDataItem(**resp) for resp in mock_responses]
    except Exception as e:
        pytest.fail(f"Failed to parse mock responses for scenario {test_case['id']}: {e}")

    # Calculate scores directly using PythonScoreCalculator
    try:
        # This uses local Python calculation instead of Gemini API
        actual_scores_dict = await score_calculator.calculate_scores(response_data_items)
    except Exception as e:
        pytest.fail(f"Score calculation failed for scenario {test_case['id']}: {e}")

    # Validate the raw dictionary first (mimics agent's validation step)
    try:
        validated_scores_obj = result_validator.validate(actual_scores_dict)
    except Exception as e:
        pytest.fail(f"Validation failed for scenario {test_case['id']}: {e}")

    # 3. Assert:
    tolerance = Decimal("1.0") # Define tolerance as Decimal

    # Compare domain scores (validated scores are now Decimal)
    expected_domains = {k: v for k, v in expected_results.items() if k != 'facets'}
    actual_domains = {k: v for k, v in validated_scores_obj.model_dump().items() if k != 'facets'}

    assert actual_domains.keys() == expected_domains.keys(), \
        f"Domain keys mismatch for {test_case['id']}. Expected: {expected_domains.keys()}, Got: {actual_domains.keys()}"

    for domain in expected_domains:
        assert actual_domains[domain] == pytest.approx(expected_domains[domain], abs=tolerance), \
            f"Domain '{domain}' score mismatch for {test_case['id']}. Expected: {expected_domains[domain]}, Got: {actual_domains[domain]}"

    # Compare facet scores (validated scores are now Decimal)
    assert validated_scores_obj.facets is not None, f"Missing 'facets' key in validated results for {test_case['id']}"
    actual_facets = validated_scores_obj.facets
    expected_facets = expected_results.get("facets", {})

    # Ensure both actual and expected facets exist before comparing keys
    if not expected_facets:
         pytest.fail(f"Expected facets are missing or empty for scenario {test_case['id']}")
    # It's possible the LLM doesn't return the 'facets' key if something goes wrong
    if not actual_facets:
         pytest.fail(f"Actual facets are missing or empty in results for {test_case['id']}")

    assert actual_facets.keys() == expected_facets.keys(), \
        f"Facet keys mismatch for {test_case['id']}. Expected: {sorted(expected_facets.keys())}, Got: {sorted(actual_facets.keys())}"

    for facet_key in expected_facets:
        assert facet_key in actual_facets, f"Expected facet key '{facet_key}' not found in actual results for {test_case['id']}"
        assert actual_facets[facet_key] == pytest.approx(expected_facets[facet_key], abs=tolerance), \
            f"Facet '{facet_key}' score mismatch for {test_case['id']}. Expected: {expected_facets[facet_key]}, Got: {actual_facets[facet_key]}"

# Add more tests as needed, e.g., testing edge cases, error handling, etc.
