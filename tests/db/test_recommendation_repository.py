import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from app.db.repositories import RecommendationRepository, RepositoryError
from app.core.clients.base import IDatabaseClient

# Gerçek kullanıcı ID'si - Sistemde var olan bir kullanıcı ID'si kullanılmalı
USER_ID = "0000-000007-USR"  # Local veritabanında kayıtlı olan kullanıcı ID'si

# Gerçekçi film ID'leri
FILM_IDS = ["0000-0009RO-FIL", "0000-0009S0-FIL", "0000-0009T1-FIL"]

# Tür örnekleri
GENRES = ["Aksiyon", "Macera", "Dram", "Komedi", "Korku", "Romantik", "Bilim Kurgu", "Gerilim", "Gizem"]

# Mock veritabanı satırları - MOODMOVIES_ALL_FILMS_INFO view'dan dönen filmler
MOCK_FILMS = [
    {
        "FILM_ID": "0000-0009RO-FIL",
        "FILM_NAME": "Ben-Hur",
        "FILM_RAYTING": 7.90,
        "FILM_RELEASE_DATE": datetime(1959, 11, 18),
        "FILM_COUNTRY": "Amerika Birleşik Devletleri",
        "RUNTIME": 222,
        "TUR_1": "Aksiyon",
        "TUR_2": "Macera",
        "TUR_3": "Dram",
        "TUR_4": "Tarih"
    },
    {
        "FILM_ID": "0000-0009S0-FIL",
        "FILM_NAME": "Harry Potter and the Philosopher's Stone",
        "FILM_RAYTING": 7.90,
        "FILM_RELEASE_DATE": datetime(2001, 11, 16),
        "FILM_COUNTRY": "Birleşik Devletler",
        "RUNTIME": 159,
        "TUR_1": "Macera",
        "TUR_2": "Fantastik",
        "TUR_3": None,
        "TUR_4": None
    },
    {
        "FILM_ID": "0000-0009T1-FIL",
        "FILM_NAME": "The Godfather",
        "FILM_RAYTING": 9.20,
        "FILM_RELEASE_DATE": datetime(1972, 3, 24),
        "FILM_COUNTRY": "Amerika Birleşik Devletleri",
        "RUNTIME": 175,
        "TUR_1": "Suç",
        "TUR_2": "Dram",
        "TUR_3": None,
        "TUR_4": None
    }
]

# Genre satırları - MOODMOVIES_GENRE tablosuna uygun
MOCK_GENRES = [
    {"GENRE": "Aksiyon"},
    {"GENRE": "Macera"},
    {"GENRE": "Dram"},
    {"GENRE": "Komedi"},
    {"GENRE": "Korku"},
    {"GENRE": "Romantik"},
    {"GENRE": "Bilim Kurgu"},
    {"GENRE": "Gerilim"},
    {"GENRE": "Gizem"},
    {"GENRE": "Fantastik"},
    {"GENRE": "Suç"},
    {"GENRE": "Tarih"}
]

@pytest.mark.asyncio
async def test_get_all_distinct_genres_success():
    """Test successful retrieval of all distinct genres."""
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    # Mock sonuç olarak türleri döndür
    mock_db_client.query_all.return_value = MOCK_GENRES
    
    # Test edilecek repository oluştur
    repository = RecommendationRepository(db_client=mock_db_client)
    
    # Metodu çağır
    results = await repository.get_all_distinct_genres()
    
    # Beklenen sonuçları kontrol et
    assert len(results) == 12  # Güncellenmiş MOCK_GENRES uzunluğu
    assert "Aksiyon" in results
    assert "Komedi" in results
    assert "Dram" in results
    
    # query_all doğru sorgu ile çağrıldı mı?
    mock_db_client.query_all.assert_awaited_once_with("SELECT DISTINCT GENRE FROM dbo.MOODMOVIES_GENRE")

@pytest.mark.asyncio
async def test_get_all_distinct_genres_empty():
    """Test when no genres are found."""
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    # Boş liste döndür
    mock_db_client.query_all.return_value = []
    
    # Test edilecek repository oluştur
    repository = RecommendationRepository(db_client=mock_db_client)
    
    # Metodu çağır
    results = await repository.get_all_distinct_genres()
    
    # Sonuç doğru mu?
    assert results == []

@pytest.mark.asyncio
async def test_get_all_distinct_genres_db_error():
    """Test handling of database errors."""
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    # Hata fırlat
    mock_db_client.query_all.side_effect = Exception("DB connection failed")
    
    # Test edilecek repository oluştur
    repository = RecommendationRepository(db_client=mock_db_client)
    
    # Exception bekle
    with pytest.raises(RepositoryError, match="DB connection failed"):
        await repository.get_all_distinct_genres()

@pytest.mark.asyncio
async def test_get_film_details_all_films():
    """Test retrieval of all film details."""
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    # Mock sonuç olarak filmleri döndür
    mock_db_client.query_all.return_value = MOCK_FILMS
    
    # Test edilecek repository oluştur
    repository = RecommendationRepository(db_client=mock_db_client)
    
    # Metodu çağır
    results = await repository.get_film_details()
    
    # Sonuçları doğrula
    assert len(results) == 3
    
    # İlk filmin doğru dönüştürülüp dönüştürülmediğini kontrol et
    assert results[0]["film_id"] == "0000-0009RO-FIL"
    assert results[0]["film_name"] == "Ben-Hur"
    assert results[0]["film_rayting"] == 7.90
    assert results[0]["film_release_date"] == datetime(1959, 11, 18)
    assert results[0]["film_country"] == "Amerika Birleşik Devletleri"
    assert results[0]["runtime"] == 222
    assert results[0]["genres"] == ["Aksiyon", "Macera", "Dram", "Tarih"]
    
    # Tüm film verilerini getiren sorgunun çağrıldığını doğrula
    expected_query = """
                    SELECT 
                        FILM_ID, FILM_NAME, FILM_RAYTING, FILM_RELEASE_DATE, FILM_COUNTRY,
                        RUNTIME, TUR_1, TUR_2, TUR_3, TUR_4
                    FROM dbo.MOODMOVIES_ALL_FILMS_INFO
                """
    mock_db_client.query_all.assert_awaited_once()
    actual_query = mock_db_client.query_all.call_args.args[0]
    assert " ".join(actual_query.split()) == " ".join(expected_query.split())

@pytest.mark.asyncio
async def test_get_film_details_specific_films():
    """Test retrieval of specific film details by film IDs."""
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    # Mock sonuç olarak filmleri döndür
    mock_db_client.query_all.return_value = MOCK_FILMS[:2]  # İlk iki film
    
    # Test edilecek repository oluştur
    repository = RecommendationRepository(db_client=mock_db_client)
    
    # Metodu çağır - sadece ilk iki film ID'sini geçir
    film_ids = ["0000-0009RO-FIL", "0000-0009S0-FIL"]
    results = await repository.get_film_details(film_ids=film_ids)
    
    # Sonuçları doğrula
    assert len(results) == 2
    assert results[0]["film_id"] == "0000-0009RO-FIL"
    assert results[1]["film_id"] == "0000-0009S0-FIL"
    
    # Belirli filmleri getiren sorgunun doğru çağrıldığını doğrula
    mock_db_client.query_all.assert_awaited_once()
    call_args = mock_db_client.query_all.call_args
    assert call_args.args[1] == film_ids  # Parametreler doğru mu?
    
    # Dinamik placeholder kontrolü - IN kelimesi ve film_ids uzunluğuna göre doğru sayıda soru işareti
    expected_placeholders = ",".join(["?"] * len(film_ids))
    assert f"WHERE FILM_ID IN ({expected_placeholders})" in call_args.args[0]  # SQL sorgusu doğru mu?

@pytest.mark.asyncio
async def test_get_film_details_empty_id_list():
    """Test retrieval of film details with empty ID list."""
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    # Genel sorgu için tüm filmleri döndür
    mock_db_client.query_all.return_value = MOCK_FILMS
    
    # Test edilecek repository oluştur
    repository = RecommendationRepository(db_client=mock_db_client)
    
    # Boş film ID listesiyle çağır
    results = await repository.get_film_details(film_ids=[])
    
    # Tüm filmleri döndürmesi gerektiğini doğrula
    assert len(results) == 3
    
    # Tüm filmleri getiren sorgu çağrılmalı
    mock_db_client.query_all.assert_awaited_once()
    query = mock_db_client.query_all.call_args.args[0]
    # WHERE FILM_ID IN ifadesi içermemeli
    assert "WHERE FILM_ID IN" not in query

@pytest.mark.asyncio
async def test_get_film_details_db_error():
    """Test DB error handling in get_film_details."""
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    # DB hatası simüle et
    mock_db_client.query_all.side_effect = Exception("DB error when fetching films")
    
    # Test edilecek repository oluştur
    repository = RecommendationRepository(db_client=mock_db_client)
    
    # Exception bekle
    with pytest.raises(Exception, match="DB error when fetching films"):
        await repository.get_film_details(film_ids=FILM_IDS)
    
    # query_all çağrıldı mı?
    mock_db_client.query_all.assert_awaited_once()

@pytest.mark.asyncio
async def test_get_films_by_genre_criteria():
    """Test retrieval of films by genre criteria."""
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    # Mock sonuç olarak filmleri döndür
    mock_db_client.query_all.return_value = MOCK_FILMS
    
    # Test edilecek repository oluştur
    repository = RecommendationRepository(db_client=mock_db_client)
    
    # Metodu çağır
    include_genres = ["Action", "Comedy"]
    exclude_genres = ["Horror"]
    limit = 20
    results = await repository.get_films_by_genre_criteria(
        include_genres=include_genres,
        exclude_genres=exclude_genres,
        limit=limit
    )
    
    # Sonuçları doğrula
    assert len(results) == 3
    
    # query_all'un doğru parametre ve sorgu ile çağrıldığını doğrula
    mock_db_client.query_all.assert_awaited_once()
    call_args = mock_db_client.query_all.call_args
    
    # Sorgunun gerekli bileşenleri içerdiğini kontrol et
    query = call_args.args[0]
    assert f"TOP ({limit})" in query
    assert "TUR_1" in query and "TUR_2" in query
    assert "WHERE" in query
    
    # Parametreler içinde include ve exclude türleri var mı?
    params = call_args.args[1]
    for genre in include_genres:
        assert genre in params
    for genre in exclude_genres:
        assert genre in params

@pytest.mark.asyncio
async def test_get_films_by_genre_criteria_include_only():
    """Test retrieval of films by only include genres."""
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    mock_db_client.query_all.return_value = MOCK_FILMS
    
    # Test edilecek repository oluştur
    repository = RecommendationRepository(db_client=mock_db_client)
    
    # Sadece include_genres ile çağır
    include_genres = ["Action", "Comedy"]
    results = await repository.get_films_by_genre_criteria(
        include_genres=include_genres,
        exclude_genres=[],
        limit=10
    )
    
    # Sonuçları doğrula
    assert len(results) == 3
    
    # query_all'un doğru sorgu ile çağrıldığını doğrula
    mock_db_client.query_all.assert_awaited_once()
    call_args = mock_db_client.query_all.call_args
    
    # Sorgunun sadece include koşulunu içerdiğini kontrol et
    query = call_args.args[0]
    assert "IN" in query
    assert "NOT IN" not in query
    
    # Parametrelerin sadece include_genres içerdiğini kontrol et
    params = call_args.args[1]
    for genre in include_genres:
        assert genre in params
        
    # 8 parametre olmalı (4 genre_field * 2 include_genre)
    assert len(params) == 8

@pytest.mark.asyncio
async def test_get_films_by_genre_criteria_exclude_only():
    """Test retrieval of films by only exclude genres."""
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    mock_db_client.query_all.return_value = MOCK_FILMS
    
    # Test edilecek repository oluştur
    repository = RecommendationRepository(db_client=mock_db_client)
    
    # Sadece exclude_genres ile çağır
    exclude_genres = ["Horror", "Sci-Fi"]
    results = await repository.get_films_by_genre_criteria(
        include_genres=[],
        exclude_genres=exclude_genres,
        limit=10
    )
    
    # Sonuçları doğrula
    assert len(results) == 3
    
    # query_all'un doğru sorgu ile çağrıldığını doğrula
    mock_db_client.query_all.assert_awaited_once()
    call_args = mock_db_client.query_all.call_args
    
    # Sorgunun sadece exclude koşulunu içerdiğini kontrol et
    query = call_args.args[0]
    assert "NOT IN" in query
    assert "IN (" not in query or ("IN (" in query and "NOT IN" in query)
    
    # Parametrelerin sadece exclude_genres içerdiğini kontrol et
    params = call_args.args[1]
    for genre in exclude_genres:
        assert genre in params
        
    # 8 parametre olmalı (4 genre_field * 2 exclude_genre)
    assert len(params) == 8

@pytest.mark.asyncio
async def test_get_films_by_genre_criteria_no_films_found():
    """Test when no films match the genre criteria."""
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    # Boş sonuç döndür
    mock_db_client.query_all.return_value = []
    
    # Test edilecek repository oluştur
    repository = RecommendationRepository(db_client=mock_db_client)
    
    # Metodu çağır
    results = await repository.get_films_by_genre_criteria(
        include_genres=["NonExistentGenre"],
        exclude_genres=[],
        limit=10
    )
    
    # Sonuç boş liste olmalı
    assert results == []
    
    # query_all çağrıldı mı?
    mock_db_client.query_all.assert_awaited_once()

@pytest.mark.asyncio
async def test_get_films_by_genre_criteria_db_error():
    """Test DB error handling in get_films_by_genre_criteria."""
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    # DB hatası simüle et
    mock_db_client.query_all.side_effect = Exception("DB error when fetching films by genre")
    
    # Test edilecek repository oluştur
    repository = RecommendationRepository(db_client=mock_db_client)
    
    # Exception bekle
    with pytest.raises(Exception, match="DB error when fetching films by genre"):
        await repository.get_films_by_genre_criteria(
            include_genres=["Action"],
            exclude_genres=["Horror"],
            limit=10
        )
        
    # query_all çağrıldı mı?
    mock_db_client.query_all.assert_awaited_once()

@pytest.mark.asyncio
async def test_get_films_by_genre_criteria_limit():
    """Test limit parameter in get_films_by_genre_criteria."""
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    mock_db_client.query_all.return_value = MOCK_FILMS
    
    # Test edilecek repository oluştur
    repository = RecommendationRepository(db_client=mock_db_client)
    
    # Özel limit ile çağır
    custom_limit = 5
    await repository.get_films_by_genre_criteria(
        include_genres=["Action"],
        exclude_genres=["Horror"],
        limit=custom_limit
    )
    
    # query_all'un doğru sorgu ile çağrıldığını doğrula
    mock_db_client.query_all.assert_awaited_once()
    query = mock_db_client.query_all.call_args.args[0]
    
    # Sorgunun doğru limit içerdiğini kontrol et
    assert f"TOP ({custom_limit})" in query

@pytest.mark.asyncio
async def test_delete_user_suggestions():
    """Test deletion of user suggestions."""
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    
    # Test edilecek repository oluştur
    repository = RecommendationRepository(db_client=mock_db_client)
    
    # Metodu çağır
    await repository.delete_user_suggestions(USER_ID)
    
    # execute doğru sorgu ve parametrelerle çağrıldı mı?
    mock_db_client.execute.assert_awaited_once()
    call_args = mock_db_client.execute.call_args
    assert call_args.args[0] == "DELETE FROM dbo.MOODMOVIES_SUGGEST WHERE USER_ID = ?"
    assert call_args.args[1] == (USER_ID,)

@pytest.mark.asyncio
async def test_delete_user_suggestions_db_error():
    """Test handling of database errors when deleting suggestions."""
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    # DB hatası simüle et
    mock_db_client.execute.side_effect = Exception("DB connection failed during delete")
    
    # Test edilecek repository oluştur
    repository = RecommendationRepository(db_client=mock_db_client)
    
    # Exception bekle
    with pytest.raises(Exception, match="DB connection failed during delete"):
        await repository.delete_user_suggestions(USER_ID)
    
    # execute çağrıldı mı?
    mock_db_client.execute.assert_awaited_once()
    call_args = mock_db_client.execute.call_args
    assert call_args.args[0] == "DELETE FROM dbo.MOODMOVIES_SUGGEST WHERE USER_ID = ?"
    assert call_args.args[1] == (USER_ID,)

@pytest.mark.asyncio
async def test_save_suggestions():
    """Test saving film suggestions for a user."""
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    
    # Test edilecek repository oluştur
    repository = RecommendationRepository(db_client=mock_db_client)
    
    # delete_user_suggestions metodunu mock'la
    with patch.object(repository, 'delete_user_suggestions', AsyncMock()) as mock_delete:
        # Metodu çağır
        await repository.save_suggestions(USER_ID, FILM_IDS)
        
        # delete_user_suggestions önce çağrıldı mı?
        mock_delete.assert_awaited_once_with(USER_ID)
        
        # Her bir film ID'si için execute çağrıldı mı?
        assert mock_db_client.execute.await_count == len(FILM_IDS)
        
        # Tüm çağrıların SQL sorgusunu ve parametrelerini kontrol et
        for i, call in enumerate(mock_db_client.execute.await_args_list):
            # SQL sorgusu kontrolü
            sql_query = call.args[0]
            # Tam SQL sorgusu doğrulaması
            expected_query = """
        DECLARE @ID varchar(15);
        exec id_generator 'SGT', @ID out;
        
        INSERT INTO dbo.MOODMOVIES_SUGGEST (SUGGEST_ID, USER_ID, FILM_ID, CREATED)
        VALUES (@ID, ?, ?, GETDATE())
        """.strip()
            # Whitespace farklılıkları nedeniyle metinleri normalize ederek karşılaştır
            assert " ".join(sql_query.split()) == " ".join(expected_query.split())
            
            # Parametreleri kontrol et
            params = call.args[1]
            assert len(params) == 2  # USER_ID ve FILM_ID parametreleri
            assert params[0] == USER_ID  # İlk parametre USER_ID
            assert params[1] == FILM_IDS[i]  # İkinci parametre FILM_ID

@pytest.mark.asyncio
async def test_save_suggestions_empty_list():
    """Test saving empty film suggestions list."""
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    
    # Test edilecek repository oluştur
    repository = RecommendationRepository(db_client=mock_db_client)
    
    # delete_user_suggestions metodunu mock'la
    with patch.object(repository, 'delete_user_suggestions', AsyncMock()) as mock_delete:
        # Boş film listesiyle metodu çağır
        await repository.save_suggestions(USER_ID, [])
        
        # delete_user_suggestions önce çağrıldı mı?
        mock_delete.assert_awaited_once_with(USER_ID)
        
        # Boş liste olduğu için execute çağrılmadı mı?
        mock_db_client.execute.assert_not_awaited()

@pytest.mark.asyncio
async def test_save_suggestions_delete_error():
    """Test error handling when deleting existing suggestions fails."""
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    
    # Test edilecek repository oluştur
    repository = RecommendationRepository(db_client=mock_db_client)
    
    # delete_user_suggestions hata fırlatsın
    with patch.object(repository, 'delete_user_suggestions', AsyncMock(side_effect=Exception("Delete error"))) as mock_delete:
        # Exception bekle
        with pytest.raises(Exception, match="Delete error"):
            await repository.save_suggestions(USER_ID, FILM_IDS)
        
        # delete_user_suggestions çağrıldı mı?
        mock_delete.assert_awaited_once_with(USER_ID)
        
        # Silme hatası olduğu için execute hiç çağrılmadı mı?
        mock_db_client.execute.assert_not_awaited()

@pytest.mark.asyncio
async def test_save_suggestions_insert_error():
    """Test error handling when inserting suggestions fails."""
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    # INSERT hatasını simüle et
    mock_db_client.execute.side_effect = Exception("INSERT error")
    
    # Test edilecek repository oluştur
    repository = RecommendationRepository(db_client=mock_db_client)
    
    # delete_user_suggestions metodunu başarıyla çalışacak şekilde mock'la
    with patch.object(repository, 'delete_user_suggestions', AsyncMock()) as mock_delete:
        # Exception bekle
        with pytest.raises(Exception, match="INSERT error"):
            await repository.save_suggestions(USER_ID, FILM_IDS)
        
        # delete_user_suggestions çağrıldı mı?
        mock_delete.assert_awaited_once_with(USER_ID)
        
        # Execute en az bir kez çağrıldı mı?
        mock_db_client.execute.assert_awaited_once()
        
        # İlk film için doğru parametreler kullanıldı mı?
        assert mock_db_client.execute.call_args.args[1] == (USER_ID, FILM_IDS[0])

@pytest.mark.asyncio
async def test_prepare_recommendation():
    """Test preparing a recommendation."""
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    
    # Test edilecek repository oluştur
    repository = RecommendationRepository(db_client=mock_db_client)
    
    # Test verileri
    process_id = "PROC001"
    
    # Metodu çağır
    result = await repository.prepare_recommendation(USER_ID, process_id)
    
    # Sonucu doğrula
    assert result == process_id
    
    # Şu an için veritabanına yazma olmadığından, DB client metotları çağrılmadı mı?
    mock_db_client.execute.assert_not_awaited()
    mock_db_client.query_all.assert_not_awaited()

@pytest.mark.asyncio
async def test_prepare_recommendation_error():
    """Test error handling when preparing a recommendation."""
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    
    # Test edilecek repository oluştur
    repository = RecommendationRepository(db_client=mock_db_client)
    
    # Mock hata
    with patch('app.db.repositories.logger.info', side_effect=Exception("Unexpected error")):
        # RepositoryError bekle
        with pytest.raises(RepositoryError, match=f"Error preparing recommendation for user {USER_ID}"):
            await repository.prepare_recommendation(USER_ID, "PROC001")


@pytest.mark.asyncio
async def test_get_all_distinct_genres_success():
    """
    Test başarılı tür listesi getirme senaryosu.
    """
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    # Mock tür listesi
    expected_genres = ["Action", "Comedy", "Drama", "Horror", "Sci-Fi"]
    mock_rows = [{"GENRE": genre} for genre in expected_genres]
    mock_db_client.query_all.return_value = mock_rows
    
    # Test edilecek repository oluştur
    repository = RecommendationRepository(db_client=mock_db_client)
    
    # Metodu çağır
    result = await repository.get_all_distinct_genres()
    
    # Beklenen SQL sorgusunu doğrula
    mock_db_client.query_all.assert_awaited_once_with("SELECT DISTINCT GENRE FROM dbo.MOODMOVIES_GENRE")
    
    # Sonuçların doğru dönüştürüldüğünü doğrula
    assert result == expected_genres
    assert len(result) == len(expected_genres)


@pytest.mark.asyncio
async def test_get_all_distinct_genres_empty_result():
    """
    Test tür listesi boş döndüğünde.
    """
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    # Boş liste döndür
    mock_db_client.query_all.return_value = []
    
    # Test edilecek repository oluştur
    repository = RecommendationRepository(db_client=mock_db_client)
    
    # Metodu çağır
    result = await repository.get_all_distinct_genres()
    
    # Boş liste dönmeli
    assert result == []
    assert len(result) == 0
    
    # Doğru sorgunun çağrıldığını doğrula
    mock_db_client.query_all.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_all_distinct_genres_db_error():
    """
    Test veritabanı hatası durumunda hata fırlatma.
    """
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    # Hata fırlat
    mock_db_client.query_all.side_effect = Exception("DB connection error")
    
    # Test edilecek repository oluştur
    repository = RecommendationRepository(db_client=mock_db_client)
    
    # Exception bekliyoruz - metot içinde hata fırlatıyor ve wrap etmiyor
    with pytest.raises(Exception, match="DB connection error"):
        await repository.get_all_distinct_genres()


@pytest.mark.asyncio
async def test_update_recommendation_status_success():
    """
    Test başarılı öneri durumu güncelleme.
    """
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    
    # Test edilecek repository oluştur
    repository = RecommendationRepository(db_client=mock_db_client)
    
    # Test parametreleri
    recommendation_id = "REC001"
    status = "in_progress"
    stage = "film_selection"
    percentage = 50
    
    # Metodu çağır - güncellemenin başarılı olduğunu kontrol et
    # Şu anki implementasyonda DB'ye yazma yok, sadece log yazıyor
    result = await repository.update_recommendation_status(
        recommendation_id=recommendation_id,
        status=status,
        stage=stage,
        percentage=percentage
    )
    
    # None döndüğünü kontrol et
    assert result is None
    
    # DB çağrılarının yapılmadığını doğrula
    mock_db_client.execute.assert_not_awaited()
    mock_db_client.query_all.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_recommendation_status_error():
    """
    Test öneri durumu güncelleme hatası.
    """
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    
    # Test edilecek repository oluştur
    repository = RecommendationRepository(db_client=mock_db_client)
    
    # Test parametreleri
    recommendation_id = "REC001"
    status = "in_progress"
    
    # Mock hata oluştur
    with patch('app.db.repositories.logger.info', side_effect=Exception("Log error")):
        # RepositoryError bekle
        with pytest.raises(RepositoryError, match=f"Error updating recommendation status for {recommendation_id}"):
            await repository.update_recommendation_status(
                recommendation_id=recommendation_id,
                status=status
            )
@pytest.mark.asyncio
async def test_get_latest_recommendation_ids_and_profile_info_success():
    """
    Test successful retrieval of latest recommendation IDs and profile info.
    """
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    
    # Sabit tarih değerleri tanımla
    fixed_time = datetime(2025, 6, 1, 10, 0, 0)  # Sabit bir tarih kullan
    
    # Film sorgusu için mock sonuçlar
    film_query_result = [
        {"FILM_ID": "0000-0009RO-FIL", "SUGGEST_ID": "0000-0000C9-SGT"},
        {"FILM_ID": "0000-0009S0-FIL", "SUGGEST_ID": "0000-0000C9-SGT"},
        {"FILM_ID": "0000-0009T1-FIL", "SUGGEST_ID": "0000-0000C9-SGT"}
    ]
    
    # Profil sorgusu için mock sonuçlar
    profile_query_result = [
        {"PROFILE_ID": "0000-00002B-PRF", "CREATED": fixed_time}
    ]
    
    # Öneri ID sorgusu için mock sonuçlar
    recommendation_query_result = [
        {"SUGGEST_ID": "0000-0000C9-SGT", "CREATED": fixed_time}
    ]
    
    # Sorguları ve yan etkileri ayarla
    mock_db_client.query_all.side_effect = [
        film_query_result,
        profile_query_result,
        recommendation_query_result
    ]
    
    # Test edilecek repository oluştur
    repository = RecommendationRepository(db_client=mock_db_client)
    
    # Metodu çağır
    result = await repository.get_latest_recommendation_ids_and_profile_info(USER_ID)
    
    # Sonuç doğru mu?
    assert isinstance(result, tuple)
    assert len(result) == 4
    
    film_ids, profile_id, created_at, recommendation_id = result
    
    # Sonuçları doğrula
    assert film_ids == ["0000-0009RO-FIL", "0000-0009S0-FIL", "0000-0009T1-FIL"]
    assert profile_id == "0000-00002B-PRF"
    assert created_at == fixed_time  # Tarih tam olarak eşit olmalı
    assert recommendation_id == "0000-0000C9-SGT"
    
    # Sorguların doğru çağrıldığını doğrula
    assert mock_db_client.query_all.call_count == 3
    
    # Tüm çağrılarda USER_ID parametresi kullanıldığını doğrula
    for call in mock_db_client.query_all.call_args_list:
        assert call.args[1] == [USER_ID]


@pytest.mark.asyncio
async def test_get_latest_recommendation_ids_and_profile_info_no_profile():
    """
    Test kullanıcının profili olmadığı durum.
    """
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    
    # Sabit tarih değerleri tanımla
    fixed_time = datetime(2025, 6, 1, 10, 0, 0)  # Sabit bir tarih kullan
    
    # Film sonuçları var ama profil yok
    film_results = [
        {"FILM_ID": "0000-0009RO-FIL", "SUGGEST_ID": "0000-0000C9-SGT"}
    ]
    
    # Boş profil sonuçları
    profile_result = []
    
    # Öneri ID sorgusu için mock sonuçlar
    rec_result = [
        {"SUGGEST_ID": "0000-0000C9-SGT", "CREATED": fixed_time}
    ]
    
    # Sorguları ve yan etkileri ayarla
    mock_db_client.query_all.side_effect = [
        film_results,
        profile_result,
        rec_result
    ]
    
    # Test edilecek repository oluştur
    repository = RecommendationRepository(db_client=mock_db_client)
    
    # Metodu çağır
    result = await repository.get_latest_recommendation_ids_and_profile_info(USER_ID)
    
    # Sonuç doğru mu?
    assert isinstance(result, tuple)
    assert len(result) == 4
    
    film_ids, profile_id, created_at, recommendation_id = result
    
    # Sonuçları doğrula
    assert film_ids == ["0000-0009RO-FIL"]
    assert profile_id is None  # Profil bulunamadı
    assert recommendation_id == "0000-0000C9-SGT"
    # Profil olmadığında, created_at değeri datetime.now() olur,
    # ancak test içinde sabit bir değerle karşılaştıramayız
    assert created_at is not None
    
    # Sorguların doğru çağrıldığını doğrula
    assert mock_db_client.query_all.call_count == 3
    
    # Tüm çağrılarda USER_ID parametresi kullanıldığını doğrula
    for call in mock_db_client.query_all.call_args_list:
        assert call.args[1] == [USER_ID]


@pytest.mark.asyncio
async def test_get_latest_recommendation_ids_and_profile_info_no_suggestions():
    """
    Test kullanıcının önerileri olmadığı durum.
    """
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    
    # Sabit tarih değerleri tanımla
    profile_date = datetime(2025, 5, 30, 15, 30, 0)  # Sabit bir tarih
    
    # Boş film ve öneri sonucu
    film_results = []
    rec_result = []
    
    # Profil sonuçları var - gerçekçi ID ve tarih
    profile_result = [
        {"PROFILE_ID": "0000-00002B-PRF", "CREATED": profile_date, "USER_ID": USER_ID}
    ]
    
    # Sorguları ve yan etkileri ayarla
    mock_db_client.query_all.side_effect = [
        film_results,
        profile_result,
        rec_result
    ]
    
    # Test edilecek repository oluştur
    repository = RecommendationRepository(db_client=mock_db_client)
    
    # Metodu çağır
    result = await repository.get_latest_recommendation_ids_and_profile_info(USER_ID)
    
    # Sonuç doğru mu?
    assert isinstance(result, tuple)
    assert len(result) == 4
    
    film_ids, profile_id, created_at, recommendation_id = result
    
    # Sonuçları doğrula
    assert film_ids == []  # Öneri bulunamadı
    assert profile_id == "0000-00002B-PRF"
    assert created_at == profile_date
    assert recommendation_id is not None  # Yeni bir UUID oluşturulmuş olmalı
    assert "REC-" in recommendation_id  # Öneri ID'si "REC-" ile başlamalı
    
    # Sorguların doğru çağrıldığını doğrula
    assert mock_db_client.query_all.call_count == 3
    
    # Tüm çağrılarda USER_ID parametresi kullanıldığını doğrula
    for call in mock_db_client.query_all.call_args_list:
        assert call.args[1] == [USER_ID]


@pytest.mark.asyncio
async def test_get_latest_recommendation_ids_and_profile_info_db_error():
    """
    Test veritabanı hatası durumunda hata fırlatma.
    """
    # Mock veritabanı istemcisi
    mock_db_client = AsyncMock(spec=IDatabaseClient)
    
    # Veritabanı sorgusu için hata ayarla
    db_error = Exception("DB connection error")
    mock_db_client.query_all.side_effect = db_error
    
    # Test edilecek repository oluştur
    repository = RecommendationRepository(db_client=mock_db_client)
    
    # RepositoryError bekle
    with pytest.raises(RepositoryError) as exc_info:
        await repository.get_latest_recommendation_ids_and_profile_info(USER_ID)
    
    # Hata mesajını doğrula
    assert f"Error fetching recommendation IDs for user {USER_ID}" in str(exc_info.value)
    # Orijinal hatayı kontrol et (exception chaining)
    assert exc_info.value.__cause__ == db_error
