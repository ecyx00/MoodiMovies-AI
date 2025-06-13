"""Mock data for personality profiler tests."""

from typing import Dict, Any, List
from datetime import datetime

# Based on the provided MOODMOVIES_QUESTION table data

# --- Mock Answer Data (Based on actual database format) ---
ANSWERS = {
    "0000-000001-ANS": {"ANSWER_ID": "0000-000001-ANS", "ANSWER": "Çok yanlış", "POINT": 1},
    "0000-000002-ANS": {"ANSWER_ID": "0000-000002-ANS", "ANSWER": "Orta derecede yanlış", "POINT": 2},
    "0000-000003-ANS": {"ANSWER_ID": "0000-000003-ANS", "ANSWER": "Ne doğru ne yanlış", "POINT": 3},
    "0000-000004-ANS": {"ANSWER_ID": "0000-000004-ANS", "ANSWER": "Orta derecede doğru", "POINT": 4},
    "0000-000005-ANS": {"ANSWER_ID": "0000-000005-ANS", "ANSWER": "Çok doğru", "POINT": 5},
}

# --- Helper function to get answer details ---
def get_answer(answer_id: str) -> Dict[str, Any]:
    return ANSWERS[answer_id]

# --- Helper function to determine answer based on scenario and question ---
def determine_answer_id(question: Dict[str, Any], scenario: str) -> str:
    domain = question['DOMAIN']
    keyed = question['KEYED']
    
    if scenario == "neutral":
        return "0000-000003-ANS" # Ne doğru ne yanlış
        
    elif scenario == "high_o_low_c":
        if domain == 'O': # High Openness
            return "0000-000005-ANS" if keyed == 'plus' else "0000-000001-ANS" # Max score (5 or 1 if reversed)
        elif domain == 'C': # Low Conscientiousness
            return "0000-000001-ANS" if keyed == 'plus' else "0000-000005-ANS" # Min score (1 or 5 if reversed)
        else: # E, A, N are neutral
            return "0000-000003-ANS"
            
    elif scenario == "high_n_low_a":
        if domain == 'N':
            return "0000-000005-ANS" if keyed == 'plus' else "0000-000001-ANS" # High N
        elif domain == 'A':
            return "0000-000001-ANS" if keyed == 'plus' else "0000-000005-ANS" # Low A
        else:
            return "0000-000003-ANS" # Neutral for O, C, E
            
    else: # Default to neutral for unknown scenarios
        return "0000-000003-ANS"

# --- Base Question Structure (Populated from provided data) ---
# Manually created based on the screenshot of MOODMOVIES_QUESTION data
# Ensure QUESTION_IDs match the database exactly if possible.
QUESTIONS = [
    {'QUESTION_ID': 'q1', 'QUESTION': 'Şeyler hakkında endişelenirim', 'DOMAIN': 'N', 'FACET': 1, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q2', 'QUESTION': 'Kolayca arkadaş edinirim', 'DOMAIN': 'E', 'FACET': 1, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q3', 'QUESTION': 'Canlı bir hayal gücüm var', 'DOMAIN': 'O', 'FACET': 1, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q4', 'QUESTION': 'Başkalarına güvenirim', 'DOMAIN': 'A', 'FACET': 1, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q5', 'QUESTION': 'Görevleri başarıyla tamamlarım', 'DOMAIN': 'C', 'FACET': 1, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q6', 'QUESTION': 'Kolayca sinirlenirim', 'DOMAIN': 'N', 'FACET': 2, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q7', 'QUESTION': 'Büyük partileri severim', 'DOMAIN': 'E', 'FACET': 2, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q8', 'QUESTION': 'Sanatın önemine inanırım', 'DOMAIN': 'O', 'FACET': 2, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q9', 'QUESTION': 'Başkalarından daha iyi olduğuma inanırım', 'DOMAIN': 'A', 'FACET': 2, 'KEYED': 'minus'},
    {'QUESTION_ID': 'q10', 'QUESTION': 'Etrafı toplamayı severim', 'DOMAIN': 'C', 'FACET': 2, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q11', 'QUESTION': 'Sık sık hüzünlenirim', 'DOMAIN': 'N', 'FACET': 3, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q12', 'QUESTION': 'Kontrolü ele alırım', 'DOMAIN': 'E', 'FACET': 3, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q13', 'QUESTION': 'Duygularımı yoğun bir şekilde yaşarım', 'DOMAIN': 'O', 'FACET': 3, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q14', 'QUESTION': 'Başkalarına yardım etmeyi severim', 'DOMAIN': 'A', 'FACET': 3, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q15', 'QUESTION': 'Sözlerimi tutarım', 'DOMAIN': 'C', 'FACET': 3, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q16', 'QUESTION': 'Başkalarına yaklaşmakta zorlanırım', 'DOMAIN': 'N', 'FACET': 4, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q17', 'QUESTION': 'Her zaman meşgulüm', 'DOMAIN': 'E', 'FACET': 4, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q18', 'QUESTION': 'Rutine göre çeşitliliği tercih ederim', 'DOMAIN': 'O', 'FACET': 4, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q19', 'QUESTION': 'İyi bir tartışmayı severim', 'DOMAIN': 'A', 'FACET': 4, 'KEYED': 'minus'},
    {'QUESTION_ID': 'q20', 'QUESTION': 'Sıkı çalışırım', 'DOMAIN': 'C', 'FACET': 4, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q21', 'QUESTION': 'Aşırıya kaçarım', 'DOMAIN': 'N', 'FACET': 5, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q22', 'QUESTION': 'Heyecanı severim', 'DOMAIN': 'E', 'FACET': 5, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q23', 'QUESTION': 'Zorlayıcı materyalleri okumayı severim', 'DOMAIN': 'O', 'FACET': 5, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q24', 'QUESTION': 'Başkalarından daha iyi olduğuma inanırım', 'DOMAIN': 'A', 'FACET': 5, 'KEYED': 'minus'},
    {'QUESTION_ID': 'q25', 'QUESTION': 'Her zaman hazırlıklıyım', 'DOMAIN': 'C', 'FACET': 5, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q26', 'QUESTION': 'Kolayca paniğe kapılırım', 'DOMAIN': 'N', 'FACET': 6, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q27', 'QUESTION': 'Neşe saçarım', 'DOMAIN': 'E', 'FACET': 6, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q28', 'QUESTION': 'Liberal siyasi adaylara oy verme eğilimindeyim', 'DOMAIN': 'O', 'FACET': 6, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q29', 'QUESTION': 'Evsizlere sempati duyarım', 'DOMAIN': 'A', 'FACET': 6, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q30', 'QUESTION': 'Düşünmeden işlere atlarım', 'DOMAIN': 'C', 'FACET': 6, 'KEYED': 'minus'},
    {'QUESTION_ID': 'q31', 'QUESTION': 'En kötüsünden korkarım', 'DOMAIN': 'N', 'FACET': 1, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q32', 'QUESTION': 'İnsanların yanında rahat hissederim', 'DOMAIN': 'E', 'FACET': 1, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q33', 'QUESTION': 'Vahşi hayal uçuşlarından keyif alırım', 'DOMAIN': 'O', 'FACET': 1, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q34', 'QUESTION': 'Başkalarının iyi niyetli olduğuna inanırım', 'DOMAIN': 'A', 'FACET': 1, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q35', 'QUESTION': 'Yaptığım işte mükemmelim', 'DOMAIN': 'C', 'FACET': 1, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q36', 'QUESTION': 'Kolayca sinirlenirim', 'DOMAIN': 'N', 'FACET': 2, 'KEYED': 'plus'}, # q6 ile aynı metin, ID farklı
    {'QUESTION_ID': 'q37', 'QUESTION': 'Partilerde birçok farklı insanla konuşurum', 'DOMAIN': 'E', 'FACET': 2, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q38', 'QUESTION': 'Başkalarının fark etmeyebileceği şeylerde güzellik görürüm', 'DOMAIN': 'O', 'FACET': 2, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q39', 'QUESTION': 'İlerlemek için hile yaparım', 'DOMAIN': 'A', 'FACET': 2, 'KEYED': 'minus'},
    {'QUESTION_ID': 'q40', 'QUESTION': 'Eşyaları yerlerine koymayı sık sık unuturum', 'DOMAIN': 'C', 'FACET': 2, 'KEYED': 'minus'},
    {'QUESTION_ID': 'q41', 'QUESTION': 'Kendimden hoşlanmam', 'DOMAIN': 'N', 'FACET': 3, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q42', 'QUESTION': 'Başkalarına liderlik etmeye çalışırım', 'DOMAIN': 'E', 'FACET': 3, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q43', 'QUESTION': 'Başkalarının duygularını hissederim', 'DOMAIN': 'O', 'FACET': 3, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q44', 'QUESTION': 'Başkaları için endişelenirim', 'DOMAIN': 'A', 'FACET': 3, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q45', 'QUESTION': 'Doğruyu söylerim', 'DOMAIN': 'C', 'FACET': 3, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q46', 'QUESTION': 'Dikkatleri üzerime çekmekten korkarım', 'DOMAIN': 'N', 'FACET': 4, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q47', 'QUESTION': 'Yerinde duramam', 'DOMAIN': 'E', 'FACET': 4, 'KEYED': 'plus'},
    {'QUESTION_ID': 'q48', 'QUESTION': 'Bildiğim şeylere bağlı kalmayı tercih ederim', 'DOMAIN': 'O', 'FACET': 4, 'KEYED': 'minus'},
    {'QUESTION_ID': 'q49', 'QUESTION': 'İnsanlara bağırırım', 'DOMAIN': 'A', 'FACET': 4, 'KEYED': 'minus'},
    {'QUESTION_ID': 'q50', 'QUESTION': 'Benden beklenenden fazlasını yaparım', 'DOMAIN': 'C', 'FACET': 4, 'KEYED': 'plus'}
]



# --- Generate Mock Responses Function ---
def generate_mock_responses(user_id: str, scenario: str) -> List[Dict[str, Any]]:
    responses = []
    response_date = datetime.now().isoformat()
    for i, q in enumerate(QUESTIONS):
        answer_id = determine_answer_id(q, scenario)
        answer_details = get_answer(answer_id)
        
        # Calculate reverse_scored based on KEYED
        reverse_scored = 1 if q['KEYED'] == 'minus' else 0
        
        # Create facet_code
        facet_code = f"{q['DOMAIN']}_F{q['FACET']}"
        
        responses.append({
            "response_id": f"mock_resp_{user_id}_{i+1}",
            "user_id": user_id,
            "question_id": q['QUESTION_ID'],
            "question": q['QUESTION'],
            "domain": q['DOMAIN'],
            "facet": q['FACET'],
            "reverse_scored": reverse_scored,
            "facet_code": facet_code,
            "answer_id": answer_details['ANSWER_ID'],
            "answer": answer_details['ANSWER'],
            "point": answer_details['POINT'],
        })
    return responses

# --- Specific Mock Response Lists ---

# Scenario 1: All answers are "Neutral" (Score 3)
MOCK_RESPONSES_SCENARIO_NEUTRAL: List[Dict[str, Any]] = generate_mock_responses(
    user_id="test_user_neutral", 
    scenario="neutral"
)

# Scenario 2: High Openness (O), Low Conscientiousness (C), Neutral E, A, N
MOCK_RESPONSES_SCENARIO_HIGH_O_LOW_C: List[Dict[str, Any]] = generate_mock_responses(
    user_id="test_user_high_o_low_c", 
    scenario="high_o_low_c"
)

# Scenario 3: High Neuroticism (N), Low Agreeableness (A), Neutral O, C, E
MOCK_RESPONSES_SCENARIO_HIGH_N_LOW_A: List[Dict[str, Any]] = generate_mock_responses(
    user_id="test_user_high_n_low_a", 
    scenario="high_n_low_a"
)

# Add more scenarios as needed, e.g.:
# MOCK_RESPONSES_SCENARIO_HIGH_N: List[Dict[str, Any]] = generate_mock_responses(...)

# Example usage (optional, for verification):
print("\n----- NEUTRAL SCENARIO -----")
#print(MOCK_RESPONSES_SCENARIO_NEUTRAL)
print(f"Total responses: {len(MOCK_RESPONSES_SCENARIO_NEUTRAL)}")

print("\n----- HIGH O / LOW C SCENARIO -----")
#print(MOCK_RESPONSES_SCENARIO_HIGH_O_LOW_C)
print(f"Total responses: {len(MOCK_RESPONSES_SCENARIO_HIGH_O_LOW_C)}")

print("\n----- HIGH N / LOW A SCENARIO -----")
#print(MOCK_RESPONSES_SCENARIO_HIGH_N_LOW_A)
print(f"Total responses: {len(MOCK_RESPONSES_SCENARIO_HIGH_N_LOW_A)}")
