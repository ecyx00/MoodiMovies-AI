import pytest
from unittest.mock import AsyncMock, patch
from decimal import Decimal

from app.db.repositories import ResponseRepository, RepositoryError
from app.core.clients.base import IDatabaseClient
from app.schemas.personality import ResponseDataItem

# Gerçek kullanıcı ID'si
USER_ID = "0000-000007-USR"

# Mock veritabanı satırları - farklı DOMAIN ve FACET kombinasyonları içerir
MOCK_DB_ROWS = [
    {
        "response_id": "resp1",
        "user_id": USER_ID,
        "question_id": "q1",
        "domain": "N",
        "facet": 1,
        "facet_code": "N_F1",  # facet_code hesaplamasını test eder
        "reverse_scored": 1,    # True olarak dönüşmeli
        "answer_id": "a1",
        "point": 5
    },
    {
        "response_id": "resp2",
        "user_id": USER_ID,
        "question_id": "q2",
        "domain": "E",
        "facet": 2,
        "facet_code": "E_F2",  # farklı domain ve facet kombinasyonu
        "reverse_scored": 0,    # False olarak dönüşmeli
        "answer_id": "a2",
        "point": 3
    },
    {
        "response_id": "resp3",
        "user_id": USER_ID,
        "question_id": "q3",
        "domain": "O",
        "facet": 3,
        "facet_code": "O_F3",  # başka bir kombinasyon
        "reverse_scored": 1,    # True olarak dönüşmeli
        "answer_id": "a3",
        "point": 2
    },
    {
        "response_id": "resp4",
        "user_id": USER_ID,
        "question_id": "q4",
        "domain": "C",
        "facet": 10,           # çift haneli facet numarası
        "facet_code": "C_F10", # çift haneli facet_code testi
        "reverse_scored": 0,    # False olarak dönüşmeli
        "answer_id": "a4",
        "point": 4
    },
    {
        "response_id": "resp001",
        "user_id": USER_ID,
        "question_id": "q001",
        "domain": "O",
        "facet": 1,
        "facet_code": "O_F1",
        "reverse_scored": 1,  # True
        "answer_id": "a003",
        "point": 3
    },
    {
        "response_id": "resp002",
        "user_id": USER_ID,
        "question_id": "q002",
        "domain": "C",
        "facet": 2,
        "facet_code": "C_F2",
        "reverse_scored": 0,  # False
        "answer_id": "a005",
        "point": 5
    },
    {
        "response_id": "resp003",
        "user_id": USER_ID,
        "question_id": "q003",
        "domain": "E",
        "facet": 3,
        "facet_code": "E_F3",
        "reverse_scored": 1,  # True
        "answer_id": "a002",
        "point": 2
    }
]

@pytest.mark.asyncio
async def test_get_user_responses_success():
    """Test successful retrieval of user responses."""
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    # Mock sonuç olarak test verilerini döndür
    mock_db_client.query_all.return_value = MOCK_DB_ROWS
    
    # Test edilecek repository oluştur
    repository = ResponseRepository(db_client=mock_db_client)
    
    # Metodu çağır
    results = await repository.get_user_responses(USER_ID)
    
    # Beklenen SQL sorgusu - ResponseRepository'deki gerçek sorguyla eşleşmeli
    expected_query = """
                SELECT 
                    r.RESPONSE_ID AS response_id,
                    r.USER_ID AS user_id,
                    r.QUESTION_ID AS question_id,
                    q.DOMAIN AS domain,
                    q.FACET AS facet,
                    q.DOMAIN + '_F' + CAST(q.FACET AS VARCHAR) AS facet_code, -- Constructed FACET_CODE
                    CASE 
                        WHEN LOWER(q.KEYED) = 'minus' THEN 1 -- Convert KEYED='minus' to True (1)
                        ELSE 0 -- Assume 'plus' or others are False (0)
                    END AS reverse_scored, 
                    r.ANSWER_ID AS answer_id,
                    a.POINT AS point
                FROM 
                    MOODMOVIES_RESPONSE r
                JOIN 
                    MOODMOVIES_QUESTION q ON r.QUESTION_ID = q.QUESTION_ID
                JOIN 
                    MOODMOVIES_ANSWER a ON r.ANSWER_ID = a.ANSWER_ID
                WHERE 
                    r.USER_ID = ?
                ORDER BY 
                    q.DOMAIN, q.FACET, r.RESPONSE_DATE -- Use RESPONSE_DATE for ordering
            """
    
    # query_all doğru sorgu ve parametrelerle çağrıldı mı?
    mock_db_client.query_all.assert_awaited_once()
    call_args = mock_db_client.query_all.call_args
    assert call_args.args[1] == [USER_ID]  # Parametreler doğru mu?
    
    # SQL sorgu metni - boşlukları ve yeni satır karakterlerini kaldır
    actual_query = call_args.args[0].replace('\n', ' ').replace('\t', ' ')
    # Gereksiz boşlukları temizle
    actual_query = ' '.join([s for s in actual_query.split(' ') if s])
    
    # Sorgu içeriğinin ana öğeleri kontrol edilir
    assert "SELECT" in actual_query
    assert "r.RESPONSE_ID" in actual_query
    assert "r.USER_ID" in actual_query
    assert "FROM MOODMOVIES_RESPONSE" in actual_query
    assert "MOODMOVIES_QUESTION" in actual_query
    assert "MOODMOVIES_ANSWER" in actual_query
    assert "WHERE r.USER_ID = ?" in actual_query
    assert "ORDER BY" in actual_query
    
    # Sonuç doğru bir ResponseDataItem listesi mi?
    assert len(results) == len(MOCK_DB_ROWS)  # Tüm mock satırların karşılığı olmalı
    assert all(isinstance(item, ResponseDataItem) for item in results)
    
    # Eklenen yeni mock verilerin doğru şekilde işlendiğini doğrula
    # Çeşitli domain ve facet kombinasyonlarını kontrol et
    
    # 'N' domaini, facet 1 kontrolü
    n_f1_item = next((item for item in results if item.facet_code == "N_F1"), None)
    assert n_f1_item is not None
    assert n_f1_item.domain == "N"
    assert n_f1_item.facet == 1
    assert n_f1_item.reverse_scored is True  # 1 değeri True'ya dönüştürülmeli
    
    # 'E' domaini, facet 2 kontrolü
    e_f2_item = next((item for item in results if item.facet_code == "E_F2"), None)
    assert e_f2_item is not None
    assert e_f2_item.domain == "E"
    assert e_f2_item.facet == 2
    assert e_f2_item.reverse_scored is False  # 0 değeri False'a dönüştürülmeli
    
    # 'O' domaini, facet 3 kontrolü
    o_f3_item = next((item for item in results if item.facet_code == "O_F3"), None)
    assert o_f3_item is not None
    assert o_f3_item.domain == "O"
    assert o_f3_item.facet == 3
    assert o_f3_item.reverse_scored is True
    
    # 'C' domaini, çift haneli facet (10) kontrolü - facet_code formatını doğrula
    c_f10_item = next((item for item in results if item.facet_code == "C_F10"), None)
    assert c_f10_item is not None
    assert c_f10_item.domain == "C"
    assert c_f10_item.facet == 10
    assert c_f10_item.reverse_scored is False
    
    # Orijinal test edilen öğeleri de kontrol et
    # 'O' domaini, facet 1
    o_f1_item = next((item for item in results if item.response_id == "resp001"), None)
    assert o_f1_item is not None
    assert o_f1_item.facet_code == "O_F1"
    assert o_f1_item.reverse_scored is True
    
    # 'C' domaini, facet 2
    c_f2_item = next((item for item in results if item.response_id == "resp002"), None)
    assert c_f2_item is not None
    assert c_f2_item.facet_code == "C_F2"
    assert c_f2_item.reverse_scored is False

@pytest.mark.asyncio
async def test_get_user_responses_no_responses_found():
    """Test when no responses are found for the user."""
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    # Boş liste döndür - yanıt yok
    mock_db_client.query_all.return_value = []
    
    # Test edilecek repository oluştur
    repository = ResponseRepository(db_client=mock_db_client)
    
    # Metodu çağır
    results = await repository.get_user_responses(USER_ID)
    
    # Sonuç doğru mu? (boş liste olmalı)
    assert results == []
    assert len(results) == 0
    
    # query_all doğru sorgu ve parametre ile çağrıldı mı?
    mock_db_client.query_all.assert_awaited_once()
    call_args = mock_db_client.query_all.call_args
    assert call_args.args[1] == [USER_ID]  # Parametreler doğru mu?
    
    # SQL sorgu metni - boşlukları ve yeni satır karakterlerini kaldır
    actual_query = call_args.args[0].replace('\n', ' ').replace('\t', ' ')
    # Gereksiz boşlukları temizle
    actual_query = ' '.join([s for s in actual_query.split(' ') if s])
    
    # Sorgu içeriğinin ana öğeleri kontrol edilir
    assert "SELECT" in actual_query
    assert "r.RESPONSE_ID" in actual_query
    assert "r.USER_ID" in actual_query
    assert "FROM MOODMOVIES_RESPONSE" in actual_query
    assert "MOODMOVIES_QUESTION" in actual_query
    assert "MOODMOVIES_ANSWER" in actual_query
    assert "WHERE r.USER_ID = ?" in actual_query
    assert "ORDER BY" in actual_query

@pytest.mark.asyncio
async def test_get_user_responses_db_error():
    """Test handling of database errors."""
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    # Hata fırlat
    mock_db_client.query_all.side_effect = Exception("DB connection failed")
    
    # Test edilecek repository oluştur
    repository = ResponseRepository(db_client=mock_db_client)
    
    # RepositoryError bekle
    with pytest.raises(RepositoryError, match=f"Error fetching responses for user {USER_ID}"):
        await repository.get_user_responses(USER_ID)
    
    # query_all çağrıldı mı?
    mock_db_client.query_all.assert_awaited_once()

@pytest.mark.asyncio
async def test_get_user_responses_invalid_row_data():
    """Test handling of invalid row data with different validation errors."""
    # Örnek 1: Eksik alan (FACET)
    missing_field_row = {
        "RESPONSE_ID": "RESP004",
        "USER_ID": USER_ID,
        "QUESTION_ID": "Q004",
        "DOMAIN": "N",
        # FACET eksik - Pydantic doğrulama hatası oluşturmalı
        "FACET_CODE": "N_F4",
        "REVERSE_SCORED": 0,
        "ANSWER_ID": "A004",
        "POINT": 4
    }
    
    # Örnek 2: Yanlış veri tipi (POINT string olmamalı)
    wrong_type_row = {
        "RESPONSE_ID": "RESP005",
        "USER_ID": USER_ID,
        "QUESTION_ID": "Q005",
        "DOMAIN": "E",
        "FACET": 5,
        "FACET_CODE": "E_F5",
        "REVERSE_SCORED": 1,
        "ANSWER_ID": "A005",
        "POINT": "not_a_number"  # Sayı değil string - Pydantic hatası oluşturmalı
    }
    
    # Örnek 3: Yanlış boolean değeri
    wrong_bool_row = {
        "RESPONSE_ID": "RESP006",
        "USER_ID": USER_ID,
        "QUESTION_ID": "Q006",
        "DOMAIN": "C",
        "FACET": 6,
        "FACET_CODE": "C_F6",
        "REVERSE_SCORED": "yes",  # 0/1 yerine string - Pydantic bool dönüşüm hatası
        "ANSWER_ID": "A006",
        "POINT": 3
    }
    
    # Her bir geçersiz veri tipini ayrı test et
    for invalid_case, invalid_row in [
        ("missing field", missing_field_row),
        ("wrong type", wrong_type_row),
        ("wrong boolean", wrong_bool_row)
    ]:
        # Mock veritabanı istemcisi
        mock_db_client = AsyncMock(spec=IDatabaseClient)
        # İlk satır geçersiz, diğerleri geçerli
        mock_db_client.query_all.return_value = [invalid_row] + MOCK_DB_ROWS[:1]  # Sadece 1 geçerli satır
        
        # Test edilecek repository oluştur
        repository = ResponseRepository(db_client=mock_db_client)
        
        # Pydantic doğrulama hatası durumunda RepositoryError bekle
        with pytest.raises(RepositoryError) as excinfo:
            await repository.get_user_responses(USER_ID)
        
        # Hata mesajının "Error parsing" veya "Error fetching" ile başladığını doğrula
        error_message = str(excinfo.value)
        assert ("Error parsing response data for user" in error_message or 
                "Error fetching responses for user" in error_message), f"Test case '{invalid_case}' failed"
        
        # Orijinal bir hatanın var olduğunu doğrula
        assert excinfo.value.__cause__ is not None, f"Test case '{invalid_case}' failed"
        
        # query_all çağrıldı mı?
        mock_db_client.query_all.assert_awaited_once()
