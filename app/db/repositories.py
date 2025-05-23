import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Tuple
import uuid
from loguru import logger
from decimal import Decimal

from app.core.clients.base import IDatabaseClient
from app.db.base_repository import BaseRepository
from app.schemas.personality_schemas import ProfileResponse, ScoreResult, ErrorDetail
from app.schemas.personality import ResponseDataItem


class RepositoryError(Exception):
    """Base class for repository-related exceptions."""
    pass


class ResponseRepository:
    """Repository for handling user responses to personality questions."""
    
    def __init__(self, db_client: IDatabaseClient):
        """
        Initialize the repository with a database client.
        
        Args:
            db_client: Database client implementing IDatabaseClient
        """
        self.db_client = db_client
        
    async def get_user_responses(self, user_id: str) -> List[ResponseDataItem]:
        """
        Get all responses for a specific user.
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            List of ResponseDataItem objects
            
        Raises:
            RepositoryError: If there's an error fetching the data
        """
        try:
            # NOTE: Assuming 'minus' in KEYED column means reverse scoring.
            query = """
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
            
            logger.info(f"Fetching responses for user: {user_id}")
            # Ensure the database client returns results as dictionaries with lowercase keys
            # Pydantic will handle the mapping from dict keys to model fields
            results = await self.db_client.query_all(query, [user_id]) 
            logger.info(f"Found {len(results)} responses for user: {user_id}")
            
            # Convert raw results into ResponseDataItem objects
            response_data_items = []
            for row in results:
                # Pydantic V2 automatically handles bool conversion if the type hint is bool
                row['reverse_scored'] = bool(row['reverse_scored'])
                try:
                    # Use ResponseDataItem from app.schemas.personality since it handles aliases
                    response_data_items.append(ResponseDataItem(**row))
                except Exception as pydantic_error: # Catch potential Pydantic validation errors
                    logger.error(f"Error parsing response row for user {user_id}: {row}. Error: {pydantic_error}")
                    raise RepositoryError(f"Error parsing response data for user {user_id}") from pydantic_error

            return response_data_items
            
        except Exception as e:
            # Avoid catching and re-raising RepositoryError if it's already the correct type
            if isinstance(e, RepositoryError):
                raise e
            error_msg = f"Error fetching responses for user {user_id}: {str(e)}"
            logger.error(error_msg)
            raise RepositoryError(error_msg) from e


class ProfileRepository:
    """Repository for handling personality profiles."""
    
    def __init__(self, db_client: IDatabaseClient, definitions_path: str):
        """
        Initialize the repository with a database client.
        
        Args:
            db_client: Database client implementing IDatabaseClient
            definitions_path: Path to definitions.json file containing DB column mappings
        """
        self.db_client = db_client
        self.definitions_path = definitions_path
        self.column_mappings = None
        
    async def _load_column_mappings(self):
        """
        Load column mappings from definitions.json if not already loaded.
        
        This method parses the definitions.json file to create mappings between 
        domain/facet codes and their corresponding database column names.
        """
        if self.column_mappings is not None:
            return
            
        try:
            with open(self.definitions_path, 'r', encoding='utf-8') as f:
                definitions = json.load(f)
                
            # Initialize mappings dictionary
            mappings = {}
            
            # Process each domain
            for domain_code, domain_data in definitions.items():
                # Add domain mapping (O -> O, C -> C, etc.)
                mappings[domain_code] = domain_code
                
                # Add facet mappings from the db_column field
                for facet_code, facet_data in domain_data.get('facets', {}).items():
                    db_column = facet_data.get('db_column')
                    if db_column:
                        mappings[facet_code] = db_column
            
            self.column_mappings = mappings
            logger.debug(f"Loaded column mappings from definitions.json: {self.column_mappings}")
            
        except Exception as e:
            error_msg = f"Error loading column mappings from {self.definitions_path}: {str(e)}"
            logger.error(error_msg)
            # Set default mappings for domains if file can't be loaded
            self.column_mappings = {
                "O": "O", "C": "C", "E": "E", "A": "A", "N": "N"
            }
            logger.warning(f"Using default column mappings: {self.column_mappings}")
    
    async def save_profile(self, user_id: str, scores: Dict[str, Decimal]) -> str:
        """
        Save or update personality profile scores for a user.
        
        Args:
            user_id: Unique identifier for the user
            scores: Dictionary containing validated T-scores. Expected format:
                   {'o': Decimal, 'c': Decimal, 'e': Decimal, 'a': Decimal, 'n': Decimal,
                    'o_f1': Decimal, ..., 'n_f6': Decimal}
                   Note: Keys are lowercase as per v1.2 API specification
            
        Returns:
            ID of the created/updated profile (varchar(15))
            
        Raises:
            RepositoryError: If there's an error saving the profile or if required scores are missing
        """
        try:
            # Adım 1: Gerekli skorların kontrolü
            required_domains = {"o", "c", "e", "a", "n"}
            missing_domains = required_domains - set(k.lower() for k in scores.keys())
            if missing_domains:
                raise RepositoryError(f"Missing required domain scores: {missing_domains}")
            
            required_facets = {f"{d}_f{i}" for d in "ocean" for i in range(1, 7)}
            missing_facets = required_facets - set(k.lower() for k in scores.keys())
            if missing_facets:
                raise RepositoryError(f"Missing required facet scores: {missing_facets}")
            
            # Adım 2: Mevcut profili kontrol et
            logger.info(f"Checking for existing profile for user: {user_id}")
            existing_profile_query = """
                SELECT TOP 1 PROFILE_ID 
                FROM MOODMOVIES_PERSONALITY_PROFILES 
                WHERE USER_ID = ? 
                ORDER BY CREATED DESC
            """
            existing_profile_rows = await self.db_client.query_all(existing_profile_query, [user_id])
            
            # Adım 3: PROFILE_ID'nin belirlenmesi
            is_new_profile = False
            profile_id_to_use = None
            
            if existing_profile_rows and len(existing_profile_rows) > 0 and existing_profile_rows[0].get('PROFILE_ID'):
                # Mevcut profil bulundu - güncelleme yapılacak
                profile_id_to_use = str(existing_profile_rows[0]['PROFILE_ID'])
                logger.info(f"Found existing profile ID: {profile_id_to_use} for user: {user_id}")
            else:
                # Mevcut profil bulunamadı - yeni profil oluşturulacak
                is_new_profile = True
                logger.info(f"No existing profile found for user: {user_id}. Generating new PROFILE_ID")
                
                # id_generator'ı çağırmak için SQL. OUTPUT parametresini doğrudan SELECT ile alıyoruz.
                # SET NOCOUNT ON; performansı artırabilir ve gereksiz DONE_IN_PROC mesajlarını engelleyebilir.
                id_gen_sql = """
                SET NOCOUNT ON;
                DECLARE @NewProfileID VARCHAR(15);
                EXEC dbo.id_generator 'PRO', @NewProfileID OUTPUT;
                SELECT @NewProfileID AS GeneratedID;
                SET NOCOUNT OFF;
                """
                # Bu sorgu tek bir satır ve tek bir kolon ('GeneratedID') döndürmeli.
                id_result_rows = await self.db_client.query_all(id_gen_sql) # Parametre yok

                if not id_result_rows or len(id_result_rows) == 0 or \
                   id_result_rows[0].get('GeneratedID') is None or \
                   not str(id_result_rows[0].get('GeneratedID', '')).strip():  # Ekstra kontrol: Boş string değil
                    logger.error(f"Failed to generate PROFILE_ID for user {user_id}. id_generator result: {id_result_rows}")
                    raise RepositoryError(f"Failed to generate PROFILE_ID for user {user_id} using id_generator")
                
                profile_id_to_use = str(id_result_rows[0]['GeneratedID']).strip()  # .strip() eklendi
                logger.info(f"Generated new PROFILE_ID: {profile_id_to_use} for user: {user_id}")
            
            # Adım 4: SQL parametrelerinin hazırlanması
            # Domain skorları
            domain_params = []
            for domain in "ocean":
                domain_params.append(scores[domain])
            
            # Facet skorları
            facet_params = []
            for domain in "ocean":
                for i in range(1, 7):
                    facet_key = f"{domain}_f{i}"
                    facet_params.append(scores[facet_key])
            
            # Tüm skor parametreleri (domain + facet)
            score_params = domain_params + facet_params
            
            # Adım 5: Veritabanı işlemi (INSERT veya UPDATE)
            if is_new_profile:
                # Yeni profil için INSERT
                logger.info(f"Inserting new profile with ID: {profile_id_to_use} for user: {user_id}")
                
                insert_sql = """
                INSERT INTO MOODMOVIES_PERSONALITY_PROFILES 
                (PROFILE_ID, USER_ID, CREATED, 
                 O, C, E, A, N, 
                 O_F1, O_F2, O_F3, O_F4, O_F5, O_F6, 
                 C_F1, C_F2, C_F3, C_F4, C_F5, C_F6, 
                 E_F1, E_F2, E_F3, E_F4, E_F5, E_F6, 
                 A_F1, A_F2, A_F3, A_F4, A_F5, A_F6, 
                 N_F1, N_F2, N_F3, N_F4, N_F5, N_F6)
                VALUES (?, ?, GETDATE(), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                
                # İlk iki parametre PROFILE_ID ve USER_ID, sonra skorlar
                insert_params = [profile_id_to_use, user_id] + score_params
                
                # INSERT sorgusunu çalıştır
                affected_rows = await self.db_client.execute(insert_sql, insert_params)
                logger.info(f"Insert operation affected {affected_rows} rows for profile: {profile_id_to_use}")
                
            else:
                # Mevcut profil için UPDATE
                logger.info(f"Updating existing profile with ID: {profile_id_to_use} for user: {user_id}")
                
                update_sql = """
                UPDATE MOODMOVIES_PERSONALITY_PROFILES 
                SET CREATED = GETDATE(),
                    USER_ID = ?,
                    O = ?, C = ?, E = ?, A = ?, N = ?,
                    O_F1 = ?, O_F2 = ?, O_F3 = ?, O_F4 = ?, O_F5 = ?, O_F6 = ?,
                    C_F1 = ?, C_F2 = ?, C_F3 = ?, C_F4 = ?, C_F5 = ?, C_F6 = ?,
                    E_F1 = ?, E_F2 = ?, E_F3 = ?, E_F4 = ?, E_F5 = ?, E_F6 = ?,
                    A_F1 = ?, A_F2 = ?, A_F3 = ?, A_F4 = ?, A_F5 = ?, A_F6 = ?,
                    N_F1 = ?, N_F2 = ?, N_F3 = ?, N_F4 = ?, N_F5 = ?, N_F6 = ?
                WHERE PROFILE_ID = ?
                """
                
                # İlk parametre USER_ID, sonra skorlar, en son WHERE için PROFILE_ID
                update_params = [user_id] + score_params + [profile_id_to_use]
                
                # UPDATE sorgusunu çalıştır
                affected_rows = await self.db_client.execute(update_sql, update_params)
                logger.info(f"Update operation affected {affected_rows} rows for profile: {profile_id_to_use}")
            
            # Adım 6: Sonucu döndür
            logger.info(f"Successfully saved/updated personality profile for user {user_id}, profile ID: {profile_id_to_use}")
            return profile_id_to_use
                
        except Exception as e:
            error_msg = f"Error saving profile for user {user_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise RepositoryError(error_msg) from e

    async def user_has_profile(self, user_id: str) -> bool:
        """
        Check if a user has a personality profile.
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            True if the user has at least one personality profile, False otherwise
            
        Raises:
            RepositoryError: If there's an error checking the profile existence
        """
        try:
            query = """
                SELECT TOP 1 1
                FROM MOODMOVIES_PERSONALITY_PROFILES
                WHERE USER_ID = ?
            """
            
            logger.debug(f"Checking if user {user_id} has a personality profile")
            results = await self.db_client.query_all(query, [user_id])
            
            has_profile = len(results) > 0
            logger.info(f"User {user_id} has profile: {has_profile}")
            return has_profile
            
        except Exception as e:
            error_msg = f"Error checking if user {user_id} has a profile: {str(e)}"
            logger.error(error_msg)
            raise RepositoryError(error_msg) from e

    async def get_latest_profile(self, user_id: str) -> Optional[ProfileResponse]:
        """
        Get the most recent personality profile for a user.
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            ProfileResponse object containing user's personality profile data
            or None if no profile exists
            
        Raises:
            RepositoryError: If there's an error fetching the profile
        """
        try:
            query = """
                SELECT TOP 1
                    *
                FROM MOODMOVIES_PERSONALITY_PROFILES
                WHERE USER_ID = ?
                ORDER BY CREATED DESC
            """
            
            logger.info(f"Fetching latest personality profile for user: {user_id}")
            results = await self.db_client.query_all(query, [user_id])
            
            if results and len(results) > 0:
                profile = results[0]
                
                # Convert profile to a dictionary with lowercase keys for v1.2 API
                profile_dict = {
                    'profile_id': str(profile['PROFILE_ID']),
                    'user_id': str(profile['USER_ID']),
                    'created': profile['CREATED']
                }
                
                # Add domain scores (convert to lowercase)
                for db_domain in ['O', 'C', 'E', 'A', 'N']:
                    if db_domain in profile:
                        v1_2_domain = db_domain.lower()  # Convert to v1.2 format (lowercase)
                        profile_dict[v1_2_domain] = Decimal(profile[db_domain])
                
                # Add facet scores (convert to lowercase)
                for domain in 'OCEAN':
                    for i in range(1, 7):
                        db_facet = f"{domain}_F{i}"  # Database format
                        v1_2_facet = f"{domain.lower()}_f{i}"  # v1.2 format (lowercase)
                        if db_facet in profile:
                            profile_dict[v1_2_facet] = Decimal(profile[db_facet])
                
                logger.info(f"Found profile for user {user_id}")
                # Convert to Pydantic model
                try:
                    return ProfileResponse(**profile_dict)
                except Exception as e:
                    logger.error(f"Error converting profile to ProfileResponse: {str(e)}")
                    raise RepositoryError(f"Error converting profile data: {str(e)}")
            else:
                logger.info(f"No profile found for user {user_id}")
                return None
                
        except Exception as e:
            error_msg = f"Error fetching personality profile for user {user_id}: {str(e)}"
            logger.error(error_msg)
            raise RepositoryError(error_msg)


    async def get_profile_by_id(self, profile_id: str) -> Optional[ProfileResponse]:
        """
        Get a personality profile by its unique identifier.
        
        Args:
            profile_id: Unique identifier for the profile
            
        Returns:
            ProfileResponse object containing the personality profile data
            or None if no profile exists with that ID
            
        Raises:
            RepositoryError: If there's an error fetching the profile
        """
        try:
            query = """
                SELECT *
                FROM MOODMOVIES_PERSONALITY_PROFILES
                WHERE PROFILE_ID = ?
            """
            
            logger.info(f"Fetching personality profile with ID: {profile_id}")
            # MSSQLClient'da fetch_one metodu yok, query_all kullanıp ilk sonucu alacağız
            results = await self.db_client.query_all(query, [profile_id])
            
            if results and len(results) > 0:
                result = results[0]  # İlk sonucu al
                # Convert profile to a dictionary with lowercase keys for v1.2 API
                profile_dict = {
                    'profile_id': str(result['PROFILE_ID']),
                    'user_id': str(result['USER_ID']),
                    'created': result['CREATED']
                }
                
                # Add domain scores (convert to lowercase)
                for db_domain in ['O', 'C', 'E', 'A', 'N']:
                    if db_domain in result:
                        v1_2_domain = db_domain.lower()  # Convert to v1.2 format (lowercase)
                        profile_dict[v1_2_domain] = Decimal(result[db_domain])
                
                # Add facet scores (convert to lowercase)
                for domain in 'OCEAN':
                    for i in range(1, 7):
                        db_facet = f"{domain}_F{i}"  # Database format
                        v1_2_facet = f"{domain.lower()}_f{i}"  # v1.2 format (lowercase)
                        if db_facet in result:
                            profile_dict[v1_2_facet] = Decimal(result[db_facet])
                
                logger.info(f"Found profile with ID: {profile_id}")
                # Convert to Pydantic model
                try:
                    return ProfileResponse(**profile_dict)
                except Exception as e:
                    logger.error(f"Error converting profile to ProfileResponse: {str(e)}")
                    raise RepositoryError(f"Error converting profile data: {str(e)}")
            else:
                logger.info(f"No profile found with ID: {profile_id}")
                return None
                
        except Exception as e:
            error_msg = f"Error fetching personality profile with ID {profile_id}: {str(e)}"
            logger.error(error_msg)
            raise RepositoryError(error_msg)
    
    async def get_profiles_by_user_id(self, user_id: str, page: int = 1, limit: int = 10) -> Tuple[List[ProfileResponse], int]:
        """
        Get a paginated list of personality profiles for a specific user.
        
        Args:
            user_id: Unique identifier for the user
            page: Page number (1-indexed)
            limit: Number of items per page
            
        Returns:
            Tuple containing:
            - List of ProfileResponse objects for the user
            - Total count of profiles for pagination
            
        Raises:
            RepositoryError: If there's an error fetching the profiles
        """
        try:
            # Calculate offset for pagination
            # Sayfa numarasının 1 veya daha büyük olduğundan emin olalım
            page = max(1, page)
            offset = (page - 1) * limit
            
            # Get total count of profiles for this user
            count_query = """
                SELECT COUNT(*) AS total
                FROM MOODMOVIES_PERSONALITY_PROFILES
                WHERE USER_ID = ?
            """
            
            # MSSQLClient'da fetch_one metodu yok, query_all kullanıp ilk sonucu alacağız
            count_results = await self.db_client.query_all(count_query, [user_id])
            count_result = count_results[0] if count_results and len(count_results) > 0 else None
            total_count = count_result['total'] if count_result and 'total' in count_result else 0
            
            # If no profiles exist, return early
            if total_count == 0:
                return [], 0
            
            # Get paginated profiles
            query = """
                SELECT *
                FROM MOODMOVIES_PERSONALITY_PROFILES
                WHERE USER_ID = ?
                ORDER BY CREATED DESC
                OFFSET ? ROWS
                FETCH NEXT ? ROWS ONLY
            """
            
            logger.info(f"Fetching personality profiles for user: {user_id} (page {page}, limit {limit}, offset {offset})")
            results = await self.db_client.query_all(query, [user_id, offset, limit])
            
            # Convert results to ProfileResponse objects
            profiles = []
            for profile in results:
                # Convert profile to a dictionary with lowercase keys for v1.2 API
                profile_dict = {
                    'profile_id': str(profile['PROFILE_ID']),
                    'user_id': str(profile['USER_ID']),
                    'created': profile['CREATED']
                }
                
                # Add domain scores (convert to lowercase)
                for db_domain in ['O', 'C', 'E', 'A', 'N']:
                    if db_domain in profile:
                        v1_2_domain = db_domain.lower()  # Convert to v1.2 format (lowercase)
                        profile_dict[v1_2_domain] = Decimal(profile[db_domain])
                
                # Add facet scores (convert to lowercase)
                for domain in 'OCEAN':
                    for i in range(1, 7):
                        db_facet = f"{domain}_F{i}"  # Database format
                        v1_2_facet = f"{domain.lower()}_f{i}"  # v1.2 format (lowercase)
                        if db_facet in profile:
                            profile_dict[v1_2_facet] = Decimal(profile[db_facet])
                
                try:
                    profiles.append(ProfileResponse(**profile_dict))
                except Exception as e:
                    logger.error(f"Error converting profile to ProfileResponse: {str(e)}")
                    # Continue with other profiles even if one fails
            
            logger.info(f"Found {len(profiles)} profiles for user {user_id} (total: {total_count})")
            return profiles, total_count
                
        except Exception as e:
            error_msg = f"Error fetching personality profiles for user {user_id}: {str(e)}"
            logger.error(error_msg)
            raise RepositoryError(error_msg)


class RecommendationRepository:
    """Repository for managing movie suggestions in MOODMOVIES_SUGGEST table."""

    def __init__(self, db_client: IDatabaseClient):
        """Initialize the repository with a database client."""
        self.db_client = db_client
        logger.info("RecommendationRepository initialized.")
        
    async def get_all_distinct_genres(self) -> List[str]:
        """
        Fetch all distinct film genres from the database.
        
        Returns:
            A list of unique genre names.
            
        Raises:
            Exception: If there's an error during the database operation.
        """
        query = "SELECT DISTINCT GENRE FROM dbo.MOODMOVIES_GENRE"
        try:
            logger.info("Fetching all distinct film genres")
            results = await self.db_client.query_all(query)
            
            # Extract genre names from result rows
            genres = [row['GENRE'] for row in results if 'GENRE' in row]
            
            logger.info(f"Found {len(genres)} distinct film genres")
            return genres
        except Exception as e:
            logger.error(f"Error fetching film genres: {e}")
            raise

    async def get_film_details(self, film_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Fetch film details from the MOODMOVIES_ALL_FILMS_INFO view.
        
        Args:
            film_ids: Optional list of film IDs to filter. If None, all films are returned.
            
        Returns:
            List of dictionaries containing film details with fields:
            - film_id: Unique film identifier
            - film_name: Title of the film
            - film_rayting: Rating of the film (decimal)
            - film_release_date: Release date
            - film_country: Country of origin
            - runtime: Runtime in minutes
            - plot: Plot summary
            - tür_1, tür_2, tür_3, tür_4: Genres (may be None)
            
        Raises:
            Exception: If there's an error during the database operation.
        """
        try:
            if film_ids:
                # If film IDs are provided, filter by them
                placeholders = ",".join(["?" for _ in film_ids])
                query = f"""
                    SELECT 
                        FILM_ID, FILM_NAME, FILM_RAYTING, FILM_RELEASE_DATE, FILM_COUNTRY,
                        RUNTIME, TUR_1, TUR_2, TUR_3, TUR_4
                    FROM dbo.MOODMOVIES_ALL_FILMS_INFO
                    WHERE FILM_ID IN ({placeholders})
                """
                logger.info(f"Fetching details for {len(film_ids)} specific films")
                results = await self.db_client.query_all(query, film_ids)
            else:
                # Otherwise, get all films
                query = """
                    SELECT 
                        FILM_ID, FILM_NAME, FILM_RAYTING, FILM_RELEASE_DATE, FILM_COUNTRY,
                        RUNTIME, TUR_1, TUR_2, TUR_3, TUR_4
                    FROM dbo.MOODMOVIES_ALL_FILMS_INFO
                """
                logger.info("Fetching details for all films")
                results = await self.db_client.query_all(query)
            
            # Convert DB results to a list of dictionaries
            films = []
            for row in results:
                film = {
                    'film_id': str(row['FILM_ID']),
                    'film_name': row['FILM_NAME'],
                    'film_rayting': float(row['FILM_RAYTING']) if row['FILM_RAYTING'] else None,
                    'film_release_date': row['FILM_RELEASE_DATE'],
                    'film_country': row['FILM_COUNTRY'],
                    'runtime': int(row['RUNTIME']) if row['RUNTIME'] else None,
                    'genres': []
                }
                
                # Add non-null genres to a list
                for genre_field in ['TUR_1', 'TUR_2', 'TUR_3', 'TUR_4']:
                    if row[genre_field]:
                        film['genres'].append(row[genre_field])
                
                films.append(film)
            
            logger.info(f"Found {len(films)} films")
            return films
            
        except Exception as e:
            logger.error(f"Error fetching film details: {e}")
            raise
            
    async def get_films_by_genre_criteria(self, include_genres: List[str], exclude_genres: List[str], limit: int = 50) -> List[Dict[str, Any]]:
        """
        Fetches films based on included and excluded genres, limited to a specified number.
        Filters films that have at least one of the included genres and none of the excluded genres.

        Args:
            include_genres: List of genres to include (at least one must match).
            exclude_genres: List of genres to exclude (none must match).
            limit: Maximum number of films to return (default: 50).

        Returns:
            A list of dictionaries with film details (excluding plot).

        Raises:
            Exception: If there's an error during the database operation.
        """
        base_query = f"""
            SELECT TOP ({limit})
                FILM_ID, FILM_NAME, FILM_RAYTING, FILM_RELEASE_DATE, FILM_COUNTRY,
                RUNTIME, TUR_1, TUR_2, TUR_3, TUR_4
            FROM dbo.MOODMOVIES_ALL_FILMS_INFO
        """
        conditions = []
        params = []

        # Build conditions for included genres (at least one must match)
        if include_genres:
            include_conditions = []
            for genre_field in ['TUR_1', 'TUR_2', 'TUR_3', 'TUR_4']:
                placeholders = ', '.join(['?'] * len(include_genres))
                include_conditions.append(f"ISNULL({genre_field}, '') IN ({placeholders})")
                params.extend(include_genres)
            
            conditions.append(f"({' OR '.join(include_conditions)})")

        # Build conditions for excluded genres (none must match)
        if exclude_genres:
            exclude_conditions = []
            for genre_field in ['TUR_1', 'TUR_2', 'TUR_3', 'TUR_4']:
                placeholders = ', '.join(['?'] * len(exclude_genres))
                exclude_conditions.append(f"ISNULL({genre_field}, '') NOT IN ({placeholders})")
                params.extend(exclude_genres)
            
            conditions.append(f"({' AND '.join(exclude_conditions)})")

        # Finalize query
        query = base_query
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        # Add ORDER BY for consistent results
        query += " ORDER BY FILM_RAYTING DESC, FILM_RELEASE_DATE DESC"

        try:
            logger.info(f"Fetching up to {limit} films matching genre criteria")
            logger.debug(f"Query: {query}")
            logger.debug(f"Params: {params}")
            
            results = await self.db_client.query_all(query, tuple(params))
            
            # Convert DB results to a list of dictionaries
            films = []
            for row in results:
                film = {
                    'film_id': str(row['FILM_ID']),
                    'film_name': row['FILM_NAME'],
                    'film_rayting': float(row['FILM_RAYTING']) if row['FILM_RAYTING'] else None,
                    'film_release_date': row['FILM_RELEASE_DATE'],
                    'film_country': row['FILM_COUNTRY'],
                    'runtime': int(row['RUNTIME']) if row['RUNTIME'] else None,
                    # No plot included
                    'genres': []
                }
                
                # Add non-null genres to the list
                for genre_field in ['TUR_1', 'TUR_2', 'TUR_3', 'TUR_4']:
                    if row[genre_field]:
                        film['genres'].append(row[genre_field])
                
                films.append(film)
            
            logger.info(f"Found {len(films)} films matching the genre criteria")
            return films
            
        except Exception as e:
            logger.error(f"Error fetching films by genre criteria: {e}")
            logger.error(f"Failed query: {query}")
            raise
            
    async def delete_user_suggestions(self, user_id: str) -> None:
        """
        Deletes all existing suggestions for a given user.

        Args:
            user_id: The ID of the user whose suggestions should be deleted.

        Raises:
            Exception: If there's an error during the database operation.
        """
        query = "DELETE FROM dbo.MOODMOVIES_SUGGEST WHERE USER_ID = ?"
        try:
            logger.info(f"Deleting existing suggestions for user: {user_id}")
            # Pass user_id as a tuple for parameterized query
            await self.db_client.execute(query, (user_id,))
            logger.info(f"Successfully deleted suggestions for user: {user_id}")
        except Exception as e:
            logger.error(f"Error deleting suggestions for user {user_id}: {e}")
            raise

    # _generate_id metodu kaldırıldı - ID'ler artık doğrudan SQL sorgularında üretiliyor
    
    async def save_suggestions(self, user_id: str, film_ids: List[str]) -> None:
        """
        Saves a list of film suggestions for a given user, replacing any existing ones.
        First deletes old suggestions, then inserts new ones.

        Args:
            user_id: The ID of the user.
            film_ids: A list of film IDs (VARCHAR(15)) to be saved as suggestions.

        Raises:
            Exception: If there's an error during the database operation.
        """
        # 1. Önce eski önerileri sil
        try:
            await self.delete_user_suggestions(user_id)
        except Exception as e:
            logger.error(f"Failed to delete existing suggestions for user {user_id}: {e}")
            # Re-raise to stop the process if we couldn't delete old suggestions
            raise

        # 2. Yeni önerileri ekle
        if not film_ids:
            logger.info(f"No new film IDs provided for user {user_id}. No suggestions saved.")
            return

        insert_query = """
        DECLARE @ID varchar(15);
        exec id_generator 'SGT', @ID out;
        
        INSERT INTO dbo.MOODMOVIES_SUGGEST (SUGGEST_ID, USER_ID, FILM_ID, CREATED)
        VALUES (@ID, ?, ?, GETDATE())
        """
        
        try:
            # Prepare parameters for bulk insertion
            params = []
            for film_id in film_ids:
                # Instead of generating IDs separately, they will be generated in the SQL query
                params.append((user_id, film_id))
            
            logger.info(f"Saving {len(params)} suggestions for user: {user_id}")
            
            # Can't use executemany since we need a unique ID for each row
            # Execute individual inserts for each film recommendation
            for param_set in params:
                await self.db_client.execute(insert_query, param_set)
                    
            logger.info(f"Successfully saved {len(params)} suggestions for user: {user_id}")
            
        except Exception as e:
            logger.error(f"Error saving suggestions for user {user_id}: {e}")
            raise

    async def prepare_recommendation(self, user_id: str, process_id: str) -> str:
        """
        Prepare a new recommendation record for a user.
        
        Args:
            user_id: The ID of the user to prepare a recommendation for.
            process_id: The ID of the process that will generate the recommendation.
            
        Returns:
            The ID of the created recommendation record.
            
        Raises:
            RepositoryError: If there's an error preparing the recommendation.
        """
        try:
            # Şu anda DB'ye kaydetmeye gerek yok, process_id'yi dönüyoruz
            # İleriki implementasyonda veritabanına kaydedilebilir
            logger.info(f"Preparing recommendation for user: {user_id} with process_id: {process_id}")
            return process_id
        except Exception as e:
            error_msg = f"Error preparing recommendation for user {user_id}: {str(e)}"
            logger.error(error_msg)
            raise RepositoryError(error_msg) from e
            
    async def update_recommendation_status(self, recommendation_id: str, status: str, stage: str = None, percentage: int = None) -> None:
        """
        Update the status of a recommendation process.
        
        Args:
            recommendation_id: The ID of the recommendation process to update.
            status: The new status (e.g., 'in_progress', 'completed', 'failed').
            stage: The current processing stage.
            percentage: The completion percentage (0-100).
            
        Raises:
            RepositoryError: If there's an error updating the status.
        """
        try:
            # Şu anda DB'ye kaydetmeye gerek yok, sadece log yazıyoruz
            # İleriki implementasyonda veritabanına kaydedilebilir
            logger.info(f"Updating recommendation status for {recommendation_id}: status={status}, stage={stage}, percentage={percentage}")
            return
        except Exception as e:
            error_msg = f"Error updating recommendation status for {recommendation_id}: {str(e)}"
            logger.error(error_msg)
            raise RepositoryError(error_msg) from e

    async def get_active_recommendation_process(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Check if there is an active recommendation process for a user.
        
        Args:
            user_id: The ID of the user to check.
            
        Returns:
            A dictionary with process details if an active process exists, None otherwise.
            
        Raises:
            Exception: If there's an error during the database operation.
        """
        try:
            # Bu metot aslında in-memory process_status_manager verilerine bakmalı
            # ancak basitlik için şimdilik None döndürüyoruz ve process'in olmadığını varsayıyoruz
            logger.debug(f"Checking for active recommendation process for user: {user_id}")
            return None
        except Exception as e:
            logger.error(f"Error checking active process for user {user_id}: {e}")
            raise
            
    async def get_latest_recommendation_status_for_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of the latest recommendation process for a user.
        
        Args:
            user_id: The ID of the user to check.
            
        Returns:
            A dictionary with process status details if found, None otherwise.
            
        Raises:
            RepositoryError: If there's an error fetching the status.
        """
        try:
            # ProcessStatusManager'dan süreci kontrol et
            from app.core.dependencies import get_process_status_manager
            process_manager = get_process_status_manager()
            process_id = f"recommendation-{user_id}"
            
            # Süreci al - process_manager sınıfında get_status metodu kullanılıyor
            process_status = await process_manager.get_status(process_id)
            
            if process_status:
                # Süreci dönüştür ve döndür
                status = {
                    "process_id": process_id,
                    "user_id": user_id,
                    "status": process_status.status,
                    "message": process_status.message or "Film önerileri hazırlanıyor",
                    "percentage": process_status.percentage,
                    "stage": process_status.stage or "film_selection",
                    "started_at": process_status.started_at,
                    "updated_at": process_status.updated_at,
                    "data": process_status.data or {"film_count": 20}
                }
            else:
                # İşlem bulunamadıysa, ilk kez öneri isteniyor olabilir
                query = """
                SELECT TOP 1 1 
                FROM dbo.MOODMOVIES_SUGGEST 
                WHERE USER_ID = ?
                """
                
                result = await self.db_client.query_all(query, [user_id])
                
                if result and len(result) > 0:
                    # Önceden öneriler oluşturulmuş ama süreç bilgisi kayıtlı değil
                    status = {
                        "process_id": process_id,
                        "user_id": user_id,
                        "status": "completed",
                        "message": "Film önerileri hazır",
                        "percentage": 100,
                        "stage": "completed",
                        "started_at": datetime.now() - timedelta(minutes=5),
                        "updated_at": datetime.now(),
                        "data": {"film_count": 20}
                    }
                else:
                    # Henüz hiç öneri yok
                    return None
            
            logger.info(f"Retrieved recommendation status for user: {user_id}")
            return status
            
        except Exception as e:
            error_msg = f"Error fetching recommendation status for user {user_id}: {str(e)}"
            logger.error(error_msg)
            raise RepositoryError(error_msg) from e
            
    async def get_latest_recommendation_ids_and_profile_info(self, user_id: str) -> Optional[tuple]:
        """
        Get the latest film recommendation IDs and profile information for a user.
        
        Args:
            user_id: The ID of the user to fetch recommendations for.
            
        Returns:
            A tuple containing (film_ids, profile_id, created_at, recommendation_id) or None if no recommendations found.
            
        Raises:
            RepositoryError: If there's an error fetching the recommendations.
        """
        try:
            # Film önerilerini SUGGEST_ID sırasına göre sıralayarak al
            film_query = """
            SELECT 
                s.FILM_ID, s.SUGGEST_ID
            FROM 
                dbo.MOODMOVIES_SUGGEST s
            WHERE 
                s.USER_ID = ?
            ORDER BY
                s.SUGGEST_ID ASC
            """
            
            # Öneri ID'sini al
            recommendation_query = """
            SELECT TOP 1
                SUGGEST_ID, CREATED
            FROM 
                dbo.MOODMOVIES_SUGGEST
            WHERE 
                USER_ID = ?
            ORDER BY 
                CREATED DESC
            """
            
            # Profil bilgisini sorgula
            profile_query = """
            SELECT TOP 1
                PROFILE_ID, CREATED
            FROM 
                MOODMOVIES_PERSONALITY_PROFILES
            WHERE 
                USER_ID = ?
            ORDER BY 
                CREATED DESC
            """
            
            # Film önerilerini al
            logger.info(f"Fetching film recommendations for user: {user_id}")
            film_results = await self.db_client.query_all(film_query, [user_id])
            
            # SQL sorgumuz zaten CREATED sırasına göre sıralama yapıyor,
            # bu yüzden sadece sonuçları sırayla almak yeterli
            film_ids = [str(row['FILM_ID']) for row in film_results] if film_results else []
            
            # Profil bilgilerini al
            logger.info(f"Fetching profile info for user: {user_id}")
            profile_result = await self.db_client.query_all(profile_query, [user_id])
            
            if profile_result and len(profile_result) > 0:
                profile_id = str(profile_result[0]['PROFILE_ID'])
                created_at = profile_result[0]['CREATED']
            else:
                profile_id = None
                created_at = datetime.now()
            
            # Öneri ID'sini al
            logger.info(f"Fetching recommendation ID for user: {user_id}")
            rec_result = await self.db_client.query_all(recommendation_query, [user_id])
            
            if rec_result and len(rec_result) > 0:
                recommendation_id = str(rec_result[0]['SUGGEST_ID'])
            else:
                # Eğer bulunamazsa yeni bir ID oluştur
                recommendation_id = f"REC-{uuid.uuid4().hex[:8]}"
            
            logger.info(f"Retrieved {len(film_ids)} recommendation IDs for user: {user_id}")
            return (film_ids, profile_id, created_at, recommendation_id)
            
        except Exception as e:
            error_msg = f"Error fetching recommendation IDs for user {user_id}: {str(e)}"
            logger.error(error_msg)
            raise RepositoryError(error_msg) from e
