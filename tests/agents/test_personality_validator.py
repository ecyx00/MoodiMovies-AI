import pytest
from decimal import Decimal
from typing import Dict, Any

# Test edilecek sınıf, fırlatmasını beklediğimiz hata ve başarılı durumda dönen model
from app.agents.personality_profiler import PersonalityResultValidator, ValidationError
from app.schemas.personality import GeminiScoreOutput
from app.schemas.personality_schemas import ScoreResult

# --- Test Verileri ---

# Geçerli skorlar (Tüm 30 facet dahil)
VALID_SCORES: Dict[str, Any] = {
    "o": Decimal("75.50"), "c": Decimal("62.00"), "e": Decimal("48.75"), "a": Decimal("81.20"), "n": Decimal("39.00"),
    "facets": {
        # Openness Facets (o_f1 - o_f6)
        "o_f1": Decimal("72.10"), "o_f2": Decimal("78.30"), "o_f3": Decimal("65.00"),
        "o_f4": Decimal("80.00"), "o_f5": Decimal("70.50"), "o_f6": Decimal("77.25"),
        # Conscientiousness Facets (c_f1 - c_f6)
        "c_f1": Decimal("60.00"), "c_f2": Decimal("65.50"), "c_f3": Decimal("58.90"),
        "c_f4": Decimal("63.10"), "c_f5": Decimal("61.80"), "c_f6": Decimal("59.50"),
        # Extraversion Facets (e_f1 - e_f6)
        "e_f1": Decimal("45.00"), "e_f2": Decimal("50.25"), "e_f3": Decimal("42.80"),
        "e_f4": Decimal("55.00"), "e_f5": Decimal("49.90"), "e_f6": Decimal("46.50"),
        # Agreeableness Facets (a_f1 - a_f6)
        "a_f1": Decimal("10.00"), "a_f2": Decimal("85.30"), "a_f3": Decimal("78.00"),
        "a_f4": Decimal("88.10"), "a_f5": Decimal("75.00"), "a_f6": Decimal("80.90"),
        # Neuroticism Facets (n_f1 - n_f6)
        "n_f1": Decimal("40.00"), "n_f2": Decimal("35.50"), "n_f3": Decimal("42.00"),
        "n_f4": Decimal("33.80"), "n_f5": Decimal("45.10"), "n_f6": Decimal("90.00")
    }
}

# Eksik Domain ('n' eksik)
MISSING_DOMAIN_SCORES = VALID_SCORES.copy()
del MISSING_DOMAIN_SCORES["n"]
# 'facets' anahtarının hala var olduğundan emin olalım (copy() sığ bir kopyadır)
MISSING_DOMAIN_SCORES["facets"] = VALID_SCORES["facets"].copy()


# Eksik Facet ('e_f1' eksik)
MISSING_FACET_SCORES = VALID_SCORES.copy()
MISSING_FACET_SCORES["facets"] = VALID_SCORES["facets"].copy() # Önce facet'leri kopyala
del MISSING_FACET_SCORES["facets"]["e_f1"]

# Yanlış Tip Domain ('o' string)
WRONG_TYPE_DOMAIN_SCORES = VALID_SCORES.copy()
WRONG_TYPE_DOMAIN_SCORES["o"] = "hatalı"
WRONG_TYPE_DOMAIN_SCORES["facets"] = VALID_SCORES["facets"].copy()

# Yanlış Tip Facet ('c_f2' string)
WRONG_TYPE_FACET_SCORES = VALID_SCORES.copy()
WRONG_TYPE_FACET_SCORES["facets"] = VALID_SCORES["facets"].copy()
WRONG_TYPE_FACET_SCORES["facets"]["c_f2"] = "yanlış"

# Düşük Aralık Domain ('a' < 10)
LOW_RANGE_DOMAIN_SCORES = VALID_SCORES.copy()
LOW_RANGE_DOMAIN_SCORES["a"] = Decimal("9.99")
LOW_RANGE_DOMAIN_SCORES["facets"] = VALID_SCORES["facets"].copy()

# Yüksek Aralık Facet ('n_f3' > 90)
HIGH_RANGE_FACET_SCORES = VALID_SCORES.copy()
HIGH_RANGE_FACET_SCORES["facets"] = VALID_SCORES["facets"].copy()
HIGH_RANGE_FACET_SCORES["facets"]["n_f3"] = Decimal("90.01")

# Geçersiz Yapı (facets = None)
INVALID_STRUCTURE_FACETS_NOT_DICT = VALID_SCORES.copy()
INVALID_STRUCTURE_FACETS_NOT_DICT["facets"] = None

# Geçersiz Yapı (facets = [])
INVALID_STRUCTURE_FACETS_NOT_DICT_LIST = VALID_SCORES.copy()
INVALID_STRUCTURE_FACETS_NOT_DICT_LIST["facets"] = []

# --- Test Fonksiyonları ---

@pytest.fixture
def validator() -> PersonalityResultValidator:
    """Fixture to provide a validator instance."""
    return PersonalityResultValidator()

def test_validator_success(validator: PersonalityResultValidator):
    """Test successful validation with valid scores."""
    try:
        result = validator.validate(VALID_SCORES)
        # API v1.2 = ScoreResult, API v1.1 = GeminiScoreOutput
        assert isinstance(result, ScoreResult), "Result should be a ScoreResult instance"
        # Örnek değerleri kontrol et
        assert result.o == VALID_SCORES["o"]  # ScoreResult ve girdi anahtarları küçük harfli (API v1.2)
        assert result.c == VALID_SCORES["c"] 
        assert result.facets["o_f1"] == VALID_SCORES["facets"]["o_f1"]  # ScoreResult ve girdi anahtarları küçük harfli
        assert result.facets["n_f6"] == VALID_SCORES["facets"]["n_f6"]
        assert len(result.facets) == 30
    except ValidationError as e:
        pytest.fail(f"Validation failed unexpectedly: {e}")
    except Exception as e:
         pytest.fail(f"An unexpected error occurred: {e}")


def test_validator_raises_on_missing_domain(validator: PersonalityResultValidator):
    """Test that validation raises ValidationError for missing domain scores."""
    # Gerçek hata mesajına göre güncellendi
    with pytest.raises(ValidationError, match="Missing required domains: {'n'}"):
        validator.validate(MISSING_DOMAIN_SCORES)


def test_validator_raises_on_missing_facet(validator: PersonalityResultValidator):
    """Test that validation raises ValidationError for missing facet scores."""
    # Gerçek hata mesajına göre güncellendi
    with pytest.raises(ValidationError, match="Missing facets: {'e_f1'}"):
         validator.validate(MISSING_FACET_SCORES)


def test_validator_raises_on_wrong_type_domain(validator: PersonalityResultValidator):
    """Test validation raises ValidationError for wrong domain score type."""
    # Gerçek hata mesajına göre güncellendi
    with pytest.raises(ValidationError, match="Domain o score must be a number, got <class 'str'>"):
        validator.validate(WRONG_TYPE_DOMAIN_SCORES)

def test_validator_raises_on_wrong_type_facet(validator: PersonalityResultValidator):
    """Test validation raises ValidationError for wrong facet score type."""
    # Gerçek hata mesajına göre güncellendi
    with pytest.raises(ValidationError, match="Facet c_f2 score must be a number, got <class 'str'>"):
        validator.validate(WRONG_TYPE_FACET_SCORES)

def test_validator_raises_on_low_range_domain(validator: PersonalityResultValidator):
    """Test validation raises ValidationError for domain score below range."""
    # Gerçek hata mesajına göre güncellendi
    with pytest.raises(ValidationError, match="Domain a score must be between 10 and 90, got 9.99"):
        validator.validate(LOW_RANGE_DOMAIN_SCORES)

def test_validator_raises_on_high_range_facet(validator: PersonalityResultValidator):
    """Test validation raises ValidationError for facet score above range."""
    # Gerçek hata mesajına göre güncellendi
    with pytest.raises(ValidationError, match="Facet n_f3 score must be between 10 and 90, got 90.01"):
        validator.validate(HIGH_RANGE_FACET_SCORES)

def test_validator_raises_on_invalid_structure_facets_not_dict(validator: PersonalityResultValidator):
    """Test validation raises ValidationError when 'facets' is not a dictionary."""
    # Gerçek hata mesajına göre güncellendi
    with pytest.raises(ValidationError, match="Facets must be a dictionary, got <class 'NoneType'>"):
        validator.validate(INVALID_STRUCTURE_FACETS_NOT_DICT)

def test_validator_raises_on_invalid_structure_facets_not_dict_list(validator: PersonalityResultValidator):
    """Test validation raises ValidationError when 'facets' is not a dictionary (list case)."""
    # Gerçek hata mesajına göre güncellendi
    with pytest.raises(ValidationError, match="Facets must be a dictionary, got <class 'list'>"):
        validator.validate(INVALID_STRUCTURE_FACETS_NOT_DICT_LIST)
