"""
Film Recommendation Agent (Agent 2)

This module implements Agent 2, which is responsible for generating film recommendations
based on personality profiles. It uses the following workflow:
1. Fetches the user's personality profile
2. Uses Gemini API to determine suitable and unsuitable genres
3. Fetches candidate films based on those genres
4. Uses Gemini API again to select the best films for the user
5. Saves the recommendations to the database
"""

import json
import os
from typing import Dict, List, Any, Tuple
import asyncio
from datetime import datetime, date
from decimal import Decimal
from loguru import logger
from pydantic import BaseModel

from app.db.repositories import ProfileRepository, RecommendationRepository
from app.core.clients.base import IDatabaseClient
from app.core.clients.gemini import GeminiClient, GeminiResponseError


class GenreRecommendation(BaseModel):
    """Model for parsing genre recommendations from Gemini API."""
    include_genres: List[str]
    exclude_genres: List[str]


class FilmRecommendation(BaseModel):
    """Model for parsing film recommendations from Gemini API."""
    recommended_film_ids: List[str]


class FilmRecommenderAgent:
    """
    Agent 2: Film Recommender

    Generates film recommendations based on a user's personality profile.
    """

    def __init__(self, db_client: IDatabaseClient, gemini_client: GeminiClient, definitions_path: str = None):
        """
        Initialize the Film Recommender Agent.

        Args:
            db_client: Database client for querying and persisting data
            gemini_client: Client for Gemini API interactions
            definitions_path: Path to definitions.json file (default: None, will use a default path)
        """
        self.db_client = db_client
        self.gemini_client = gemini_client
        
        # Define path to definitions.json
        if definitions_path is None:
            # Varsayılan yolu ayarla
            current_dir = os.path.dirname(os.path.abspath(__file__))
            base_dir = os.path.dirname(os.path.dirname(current_dir))
            self.definitions_path = os.path.join(base_dir, "app", "static", "definitions.json")
        else:
            self.definitions_path = definitions_path
            
        logger.debug(f"Using definitions path: {self.definitions_path}")
        
        # Repository'leri oluştur
        self.profile_repository = ProfileRepository(db_client, self.definitions_path)
        self.recommendation_repository = RecommendationRepository(db_client)

    async def generate_recommendations(self, user_id: str) -> bool:
        """
        Generate film recommendations for a user.

        Args:
            user_id: The user ID to generate recommendations for

        Returns:
            bool: True if recommendations were successfully generated, False otherwise
        """
        try:
            logger.info(f"Generating film recommendations for user: {user_id}")
            
            # 1. Get user personality profile
            profile = await self._get_user_profile(user_id)
            if not profile:
                logger.error(f"No personality profile found for user: {user_id}")
                return False
                
            # 2. Fetch all available genres
            all_genres = await self._get_all_genres()
            if not all_genres:
                logger.error("Failed to fetch genre list")
                return False
                
            # 3. Load personality definitions
            definitions = self._load_definitions()
            if not definitions:
                logger.error("Failed to load personality definitions")
                return False
                
            # 4. Get genre recommendations from Gemini (first prompt)
            genre_recommendation = await self._get_genre_recommendations(
                profile, all_genres, definitions
            )
            if not genre_recommendation:
                logger.error("Failed to get genre recommendations from Gemini")
                return False
                
            # 5. Fetch candidate films based on genre recommendations
            candidate_films = await self._get_candidate_films(
                genre_recommendation.include_genres,
                genre_recommendation.exclude_genres
            )
            if not candidate_films:
                logger.error("No candidate films found matching genre criteria")
                return False
                
            # 6. Get film recommendations from Gemini (second prompt)
            domain_scores = self._extract_domain_scores(profile)
            film_ids = await self._get_film_recommendations(candidate_films, domain_scores)
            if not film_ids:
                logger.error("Failed to get film recommendations from Gemini")
                return False
                
            # 7. Save recommendations to database
            await self._save_recommendations(user_id, film_ids)
            
            logger.info(f"Successfully generated {len(film_ids)} film recommendations for user: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error generating film recommendations for user {user_id}: {e}")
            return False
    
    async def _get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """
        Fetch user's personality profile.
        
        Returns a dictionary with domain and facet scores.
        """
        try:
            # Fetch the latest personality profile for the user
            profile = await self.profile_repository.get_latest_profile(user_id)
            if not profile:
                logger.warning(f"No personality profile found for user: {user_id}")
                return None
                
            logger.info(f"Retrieved personality profile for user: {user_id}")
            return profile
        except Exception as e:
            logger.error(f"Error fetching personality profile for user {user_id}: {e}")
            return None
    
    def _json_serial(self, obj):
        """JSON serializer for objects not serializable by default json code.
        Specifically handles date, Decimal objects, and ProfileResponse.
        """
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        # ProfileResponse sınıfı için
        if obj.__class__.__name__ == 'ProfileResponse':
            return obj.dict() if hasattr(obj, 'dict') else obj.model_dump()
        raise TypeError(f"Type {type(obj)} is not JSON serializable")
    
    async def _get_all_genres(self) -> List[str]:
        """Fetch all distinct genres from the database."""
        try:
            genres = await self.recommendation_repository.get_all_distinct_genres()
            logger.info(f"Retrieved {len(genres)} distinct genres")
            return genres
        except Exception as e:
            logger.error(f"Error fetching genres: {e}")
            return None
    
    def _load_definitions(self) -> Dict[str, Any]:
        """Load personality definitions from JSON file."""
        try:
            # Get the absolute path based on current working directory
            current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            definitions_path = os.path.join(current_dir, self.definitions_path)
            
            with open(definitions_path, 'r', encoding='utf-8') as f:
                definitions = json.load(f)
            
            logger.info(f"Loaded personality definitions from: {definitions_path}")
            return definitions
        except Exception as e:
            logger.error(f"Error loading definitions: {e}")
            return None
    
    async def _get_genre_recommendations(
        self, 
        profile: Dict[str, Any], 
        all_genres: List[str], 
        definitions: Dict[str, Any]
    ) -> GenreRecommendation:
        """
        Get genre recommendations using Gemini API.
        
        First prompt: Determine suitable and unsuitable genres based on personality.
        """
        try:
            # Construct the prompt for Gemini
            prompt = self._construct_genre_selection_prompt(profile, all_genres, definitions)
            
            # Call Gemini API
            response = await self.gemini_client.generate(prompt)
            
            # Parse the response to extract genre recommendations
            genre_recommendation = self._parse_genre_response(response)
            
            logger.info(f"Gemini recommended including genres: {genre_recommendation.include_genres}")
            logger.info(f"Gemini recommended excluding genres: {genre_recommendation.exclude_genres}")
            
            return genre_recommendation
        except Exception as e:
            logger.error(f"Error getting genre recommendations from Gemini: {e}")
            return None
    
    def _construct_genre_selection_prompt(
        self, 
        profile: Dict[str, Any], 
        all_genres: List[str], 
        definitions: Dict[str, Any]
    ) -> str:
        """
        Construct the prompt for the first Gemini call.
        
        This prompt asks Gemini to identify suitable and unsuitable film genres
        based on the user's personality profile.
        """
        # Datetime ve Decimal nesnelerini JSON serileştirilebilir formata çeviren yardımcı fonksiyon
        def json_serial(obj):
            """Datetime ve Decimal nesnelerini JSON serileştirilebilir formata çevirir"""
            if isinstance(obj, datetime):
                return obj.isoformat()
            if isinstance(obj, Decimal):
                # Decimal değerleri float'a çevir
                return float(obj)
            # ProfileResponse sınıfı için
            if obj.__class__.__name__ == 'ProfileResponse':
                return obj.dict() if hasattr(obj, 'dict') else obj.model_dump()
            raise TypeError(f"Type {type(obj)} is not JSON serializable")
        
        # Profil, tanımlar ve türleri JSON string olarak formatla - datetime nesnelerini düzgün çevir
        profile_json_str = json.dumps(profile, indent=2, ensure_ascii=False, default=json_serial)
        definitions_text = json.dumps(definitions, indent=2, ensure_ascii=False, default=json_serial)
        genre_list_text = ", ".join(all_genres)
        
        prompt = f"""
        **SİSTEM İSTEMİ: GELİŞMİŞ KİŞİLİK TEMELLİ TÜR ANALİZİ**

        **ROLÜN:** Sen, yüksek düzeyde uzmanlaşmış bir Yapay Zeka Psikoloğusun. Uzmanlık alanın, bireylerin film türü tercihlerini hassas bir şekilde tahmin etmek için Big Five (OCEAN) kişilik profillerini (T-skorları) analiz etmektir. Analizin **MUTLAKA** titiz ve veriye dayalı olmalıdır.

        **BİRİNCİL HEDEF:** Sağlanan kullanıcı kişilik profilini analiz et ve **TAM OLARAK** 4 adet önerilen tür ve **TAM OLARAK** 2 adet kaçınılması gereken tür içeren bir JSON nesnesi çıktısı ver.

        **GİRDİ VERİLERİ:**

        1.  **`personality_profile` (JSON Nesnesi):** Kullanıcının OCEAN alanları ve 30 alt faktörü için ham T-skorlarını içerir.
            ```json
            {profile_json_str}
            ```
        2.  **`score_interpretation_guide` (Kurallar):** T-skorlarını yorumlamak için **ZORUNLU** kurallar:
            *   Düşük Skor: T < 40
            *   Orta Skor: 40 <= T <= 60
            *   Yüksek Skor: T > 60
        3.  **`personality_definitions` (JSON Nesnesi):** Her alan ve alt faktör skorunun anlamının ayrıntılı açıklamaları. Analiz için **MUTLAKA** kullanmalısın.
            ```json
            {definitions_text}
            ```
        4.  **`allowed_genres` (Liste):** Çıktında kullanabileceğin **TEK** geçerli tür adları.
            [{genre_list_text}]

        **ZORUNLU KİŞİLİK-TÜR EŞLEŞTİRME KILAVUZU:**

        Her kişilik özelliğinin nasıl yorumlanması ve film türleriyle nasıl eşleştirilmesi gerektiğini anlamak için aşağıdaki kılavuzu MUTLAKA takip et:

        1. **Deneyime Açıklık (O):**
           * **Yüksek O (>60):** Sanatsal, yenilikçi, deneysel filmler öner. Yabancı filmler, bağımsız yapımlar, sanat filmleri gibi alışılmadık türleri dahil et.
           * **Düşük O (<40):** Geleneksel, tanıdık ve ana akım filmler öner. Deneysel veya karmaşık türlerden kaçın.

        2. **Sorumluluk (C):**
           * **Yüksek C (>60):** Yapılandırılmış, mantıklı ve düşündürücü filmler öner. Belgeseller, tarihsel dramalar ve biyografik filmler uygundur.
           * **Düşük C (<40):** Spontane, tahmin edilemez veya macera dolu filmler öner. Mantıksız komedi veya kaos içeren filmler dahil edilebilir.

        3. **Dışadönüklük (E):**
           * **Yüksek E (>60):** Sosyal etkileşim içeren, tempolu ve enerjik filmler öner. Komedi, aksiyon, macera türleri uygundur.
           * **Düşük E (<40):** Daha sakin, içe dönük ve düşünmeye yönelten filmler öner. Yavaş tempolu dramalar veya bağımsız filmler uygundur.

        4. **Uyumluluk (A):**
           * **Yüksek A (>60):** Olumlu mesajlar içeren, empatik ve ilişki odaklı filmler öner. Romantik filmler, aile filmleri dahil edilebilir.
           * **Düşük A (<40):** Rekabetçi, çatışma içeren veya provokatif filmler öner. Suç, gerilim gibi türler dahil edilebilir.

        5. **Nevrotiklik (N):** - **ÖNEMLİ NOT: Bu faktör diğerlerinden farklı yorumlanmalıdır!**
           * **Yüksek N (>60):** Bu kişiler kaygılı, stresli ve hassastır. Gerilim, korku, şiddet veya rahatsız edici içerik bulunan türlerden MUTLAKA KAÇIN! Bunun yerine sakinleştirici, rahatlatıcı ve pozitif türleri öner (komedi, aile, animasyon, bazı romantik filmler).
           * **Düşük N (<40):** Bu kişiler duygusal olarak dengeli ve strese dayanıklıdır. Daha yoğun, heyecan verici veya gerilimli türleri tolere edebilirler. Korku, gerilim, aksiyon türleri önerilebilir.

        **ZORUNLU YÜRÜTME PROTOKOLÜ:**

        1.  **SKOR ANALİZİ:**
            *   `personality_profile` içindeki hem alanlar hem de alt faktörler için tüm YÜKSEK (> 60) ve DÜŞÜK (< 40) T-skorlarını belirle.
            *   Belirlenen her yüksek/düşük skor için, psikolojik anlamını anlamak üzere `personality_definitions` kaynağına başvur.
            *   Tanımlar, yukarıdaki kılavuz ve uzmanlığına dayanarak, bu belirli kişilik özelliklerinin potansiyel film türü beğenisi veya beğenmemesiyle nasıl ilişkili olduğunu belirle.
        2.  **TÜR SEÇİMİ (KRİTİK):**
            *   `allowed_genres` listesinden, profilin kullanıcının keyif almasının **EN OLASI** olduğunu gösterdiği **DÖRT (4)** türü seç. Bunlar, analizine dayalı en güçlü pozitif göstergeler **OLMALIDIR**.
            *   `allowed_genres` listesinden, profilin kullanıcının hoşlanmamasının veya kaçınmasının **EN OLASI** olduğunu gösterdiği **İKİ (2)** türü seç. Bunlar, en güçlü negatif göstergeler **OLMALIDIR**.
            *   **ÖNEMLİ NEVROTİKLİK KONTROLÜ:** Eğer kullanıcı **yüksek Nevrotiklik** (N>60) puanına sahipse, **MUTLAKA** korku, gerilim ve yoğun şiddet içeren türleri exclude_genres kısmına ekle. Bu türler kesinlikle önerilmemelidir.
        3.  **ÇIKTI FORMATLAMASI (KESİN):**
            *   **SADECE** tek bir, geçerli JSON nesnesi oluştur.
            *   JSON nesnesi **MUTLAKA** bu **KESİN** yapıyı takip etmelidir:
                ```json
                {{
                  "include_genres": ["TürA", "TürB", "TürC", "TürD"],
                  "exclude_genres": ["TürX", "TürY"]
                }}
                ```
            *   Kullandığın tür adları (`"TürA"`, `"TürX"`, vb.) **MUTLAKA** `allowed_genres` listesinden harfi harfine alınmalıdır.
            *   JSON nesnesinden önce veya sonra **HİÇBİR** metin ekleme. Açıklama yok, selamlama yok, özet yok, markdown formatlaması (```json gibi) yok. Tüm yanıtın **MUTLAKA** JSON nesnesinin kendisi olmalıdır.

        **BAŞARISIZLIK KOŞULLARI (NE PAHASINA OLURSA OLSUN KAÇIN):**
        *   4'ten az veya fazla `include_genres` sağlamak.
        *   2'den az veya fazla `exclude_genres` sağlamak.
        *   `allowed_genres` içinde bulunmayan tür adlarını kullanmak.
        *   Gerekli JSON nesnesi dışında herhangi bir metin çıktısı vermek.
        *   Yanlış JSON formatlaması.
        *   **ÖNEMLİ:** Yüksek Nevrotiklik (N>60) skoruna sahip kullanıcılara korku/gerilim türlerini önermek.

        **ŞİMDİ YÜRÜT.**
        """
        
        return prompt
    
    def _parse_genre_response(self, response: str) -> GenreRecommendation:
        """
        Parse Gemini response to extract genre recommendations.
        
        Extracts the JSON portion of the response and parses it into a GenreRecommendation object.
        """
        try:
            # Extract JSON portion from the response
            # This assumes Gemini will return proper JSON or JSON embedded in text
            # We need to handle both cases
            
            # First try to parse the whole response as JSON
            try:
                data = json.loads(response)
            except json.JSONDecodeError:
                # If that fails, try to extract JSON from the text
                import re
                json_match = re.search(r'({.*})', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                    data = json.loads(json_str)
                else:
                    raise ValueError("No valid JSON found in Gemini response")
            
            # Validate that we have the required fields
            if "include_genres" not in data or "exclude_genres" not in data:
                raise ValueError("Missing required fields in Gemini response")
            
            # Create and return the GenreRecommendation object
            return GenreRecommendation(
                include_genres=data["include_genres"],
                exclude_genres=data["exclude_genres"]
            )
        except Exception as e:
            logger.error(f"Error parsing genre response: {e}")
            logger.error(f"Original response: {response}")
            raise
    
    async def _get_candidate_films(
        self, 
        include_genres: List[str], 
        exclude_genres: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Fetch candidate films based on genre criteria.
        
        Uses the genre recommendations to query the database for matching films.
        """
        try:
            films = await self.recommendation_repository.get_films_by_genre_criteria(
                include_genres=include_genres,
                exclude_genres=exclude_genres,
                limit=140  # Maximum number of candidate films
            )
            
            logger.info(f"Retrieved {len(films)} candidate films based on genre criteria")
            return films
        except Exception as e:
            logger.error(f"Error fetching candidate films: {e}")
            return None
    
    def _extract_domain_scores(self, profile) -> Dict[str, float]:
        """
        Extract just the domain scores from the full personality profile.
        
        For the second Gemini prompt, we only need the main OCEAN scores.
        """
        # ProfileResponse nesnesi için doğrudan özellik erişimi kullanılıyor
        # İhtiyaç halinde bu nesneyi dict formatına çevirebiliriz
        try:
            # ProfileResponse nesnesinden doğrudan erişim
            if hasattr(profile, 'o') and hasattr(profile, 'c') and hasattr(profile, 'e') and hasattr(profile, 'a') and hasattr(profile, 'n'):
                domain_scores = {
                    "O": float(profile.o),
                    "C": float(profile.c),
                    "E": float(profile.e),
                    "A": float(profile.a),
                    "N": float(profile.n)
                }
            # Dict formatında erişim
            elif isinstance(profile, dict):
                domain_scores = {
                    "O": float(profile.get("o", profile.get("O", 0))),
                    "C": float(profile.get("c", profile.get("C", 0))),
                    "E": float(profile.get("e", profile.get("E", 0))),
                    "A": float(profile.get("a", profile.get("A", 0))),
                    "N": float(profile.get("n", profile.get("N", 0)))
                }
            else:
                # Bilinmeyen formatta ise varsayılan değerler kullan
                logger.warning(f"Unknown profile type: {type(profile)}, using default values")
                domain_scores = {"O": 50.0, "C": 50.0, "E": 50.0, "A": 50.0, "N": 50.0}
                
            logger.debug(f"Extracted domain scores: {domain_scores}")
            return domain_scores
        except Exception as e:
            logger.error(f"Error extracting domain scores: {e}")
            # Varsayılan değerler döndür
            return {"O": 50.0, "C": 50.0, "E": 50.0, "A": 50.0, "N": 50.0}
    
    async def _get_film_recommendations(
        self, 
        candidate_films: List[Dict[str, Any]], 
        domain_scores: Dict[str, float]
    ) -> List[str]:
        """
        Get film recommendations using Gemini API.
        
        Second prompt: Determine the best 20 films from candidates based on domain scores.
        """
        try:
            # Construct the prompt for Gemini
            prompt = self._construct_film_selection_prompt(candidate_films, domain_scores)
            
            # Call Gemini API
            response = await self.gemini_client.generate(prompt)
            
            # Parse the response to extract film recommendations
            recommended_films = self._parse_film_response(response)
            
            logger.info(f"Gemini recommended {len(recommended_films)} films")
            
            return recommended_films
        except Exception as e:
            logger.error(f"Error getting film recommendations from Gemini: {e}")
            return None
    
    def _construct_film_selection_prompt(
        self, 
        candidate_films: List[Dict[str, Any]], 
        domain_scores: Dict[str, float]
    ) -> str:
        """
        Construct the prompt for the second Gemini call.
        
        This prompt asks Gemini to identify the best 20 films from the candidates
        based on the user's domain scores (OCEAN).
        
        Args:
            candidate_films: List of candidate films with their metadata
            domain_scores: Dictionary containing the user's OCEAN domain scores
            
        Returns:
            A formatted prompt string for the Gemini API
        """
        # OCEAN domain definitions provided by user
        ocean_definitions = """
O – Deneyime Açıklık

Tanım: Kişinin zihinsel esnekliği, hayal gücü, yaratıcılığı ve yeni fikirlere açıklığını ölçer.

    Yüksek skor: Yaratıcı, özgün, meraklı, hayal gücü güçlü ve yeni deneyimlere açık.

    Düşük skor: Geleneksel, somut düşünen, hayal gücünden uzak ve değişime dirençli.

Açıklama:
Yüksek Deneyime Açıklık puanı, bireyin sanatsal, entelektüel ve soyut düşünceye yatkın olduğunu gösterir. Düşük puanlar ise daha somut, pratik ve rutin yaşamı tercih eden bireyleri yansıtır.
C – Sorumluluk

Tanım: Kişinin düzen, planlama, hedeflere bağlılık ve öz denetim düzeyini ölçer.

    Yüksek skor: Disiplinli, planlı, güvenilir, görev bilinci yüksek.

    Düşük skor: Düzensiz, ertelemeye meyilli, dikkatsiz, sorumluluktan kaçınan.

Açıklama:
Yüksek Sorumluluk skoru, bireyin hedef odaklı, organize ve çalışkan olduğunu gösterir. Düşük skor ise dağınık, ani kararlar alan ve sorumluluk almada zorlanan kişilik yapılarına işaret eder.
E – Dışadönüklük

Tanım: Kişinin sosyal ilişkilerdeki enerjisi, girişkenliği ve kendini ifade etme gücünü ölçer.

    Yüksek skor: Girişken, konuşkan, sosyal ortamlardan beslenen.

    Düşük skor: Sessiz, içe dönük, yalnız kalmayı tercih eden.

Açıklama:
Yüksek Dışadönüklük puanı, sosyal ilişkilerde aktif, dışa açık ve enerjik bireyleri ifade eder. Düşük puanlar ise iç gözleme yatkın, daha sakin ve bireyselliği tercih eden kişilik profillerine işaret eder.
A – Uyumluluk

Tanım: Başkalarına karşı tutumda ne kadar empatik, nazik ve iş birliğine açık olunduğunu ölçer.

    Yüksek skor: Yardımsever, anlayışlı, uzlaşmacı.

    Düşük skor: Rekabetçi, eleştirel, inatçı, mesafeli.

Açıklama:
Yüksek Uyumluluk puanı, ilişkilerde yapıcı, destekleyici ve başkalarını düşünen bireyleri tanımlar. Düşük skor ise daha bireyci, sorgulayıcı ve çatışmaya açık karakter yapılarını gösterir.
N – Nevrotiklik (Duygusal Dengesizlik)

Tanım: Kişinin stres, kaygı, öfke ve duygusal istikrarsızlık düzeyini ölçer.

    Yüksek skor: Kaygılı, stres altında zorlanan, duygusal olarak dengesiz.

    Düşük skor: Sakin, dayanıklı, duygusal olarak dengeli.

Açıklama:
Yüksek Nevrotiklik puanı, bireyin olumsuz duygulara karşı daha hassas olduğunu gösterir. Düşük skor ise daha kontrollü, istikrarlı ve stresle daha iyi başa çıkan birey profillerine işaret eder.
"""

        # T-score interpretation guide
        score_interpretation = """
T-Skor Yorumlama Kılavuzu:
- Düşük: < 40
- Orta: 40-60
- Yüksek: > 60
"""

        # Constructing the entire prompt with new, more analytical format
        prompt = f"""
Sen, OCEAN kişilik profilleri ile film meta verileri arasında ilişki kurarak kişiselleştirilmiş film önerileri üreten, analitik bir Yapay Zeka Film Seçicisisin. Görevin, sağlanan verileri titizlikle analiz ederek en uygun sonuçları çıkarmaktır.

## GÖREV TANIMI

Aşağıda detayları verilen kullanıcının OCEAN T-skorlarını ve 140 aday filmin meta verilerini (isim, türler, rating, çıkış tarihi, ülke, süre) kullanarak, bu kullanıcının kişilik profiline en yüksek uyumu gösteren **TAM OLARAK 70** filmi belirle. Seçimlerin, kişilik özelliklerinin filmlerin içeriksel ve biçimsel özellikleriyle nasıl örtüştüğüne dair mantıksal çıkarımlara dayanmalıdır.

## GİRDİ VERİLERİ

### 1. KULLANICI KİŞİLİK PROFİLİ (OCEAN T-Skorları)

Aşağıdaki JSON nesnesi, kullanıcının 5 ana OCEAN alanındaki T-skorlarını içermektedir:

```json
{json.dumps(domain_scores, indent=2, ensure_ascii=False)}
```

**T-Skor Yorumlama Kılavuzu:**
{score_interpretation}

**OCEAN Alan Tanımları ve Yorumları:**
{ocean_definitions}

### 2. ADAY FİLM METAVERİLERİ

Aşağıdaki JSON dizisi, değerlendirmen gereken 140 aday filmi ve mevcut meta verilerini içermektedir. **ÖNEMLİ NOT:** Bu filmlerin **PLOT (konu özeti) bilgisi YOKTUR.** Analizin sadece sağlanan meta verilere (isim, türler, rating, yıl, ülke, süre) dayanmalıdır.

```json
{json.dumps(candidate_films, indent=2, ensure_ascii=False, default=self._json_serial)}
```

## ANALİZ ve SEÇİM PROTOKOLÜ

1.  **Profil Analizi:** Kullanıcının OCEAN T-skorlarını yorumlama kılavuzu ve alan tanımları ışığında derinlemesine analiz et. Hangi kişilik özelliklerinin (örn. yüksek Açıklık, düşük Uyumluluk) baskın olduğunu belirle ve bu özelliklerin film tercihlerine olası etkilerini değerlendir.
2.  **Metaveri İncelemesi:** Her bir aday filmin sağlanan meta verilerini (türler, rating, çıkış yılı, ülke, süre) dikkatlice incele. Bu verilerden filmin potansiyel atmosferi, teması veya karmaşıklığı hakkında çıkarımlar yap. **PLOT bilgisi olmadığını unutma.**
3.  **Kişilik-Film Eşleştirmesi:** Analitik çıkarımlar yaparak, belirlenen kişilik özellikleri ile film meta verileri arasında anlamlı bağlantılar kur. Örneğin:
    *   *Yüksek Deneyime Açıklık (O):* Sanatsal değeri yüksek, bağımsız yapımlar, farklı kültürlerden filmler, karmaşık veya alışılmadık anlatılara sahip filmler (metaveriden çıkarılabildiği ölçüde).
    *   *Düşük Deneyime Açıklık (O):* Ana akım türler, tanıdık temalar, yüksek ratingli popüler filmler, belirli bir dönemden klasik yapımlar.
    *   *Yüksek Sorumluluk (C):* Belirgin bir yapıya sahip, düşündürücü, belki belgesel veya biyografik filmler (tür bilgisine göre).
    *   *Yüksek Dışadönüklük (E):* Yüksek tempolu aksiyon/macera, komedi, sosyal etkileşim içeren filmler.
    *   *Yüksek Uyumluluk (A):* Olumlu mesajlar veren, romantik, aile odaklı, dramatik ama umut veren yapımlar.
    *   *Yüksek Nevrotiklik (N):* Aşırı şiddet içeren, yoğun korku veya rahatsız edici temalara sahip (tür ve rating bilgisinden çıkarılabilecek) filmlerden kaçınma eğilimi; daha sakinletici veya pozitif filmlere yönelim.
4.  **Nihai Seçim:** Yukarıdaki analitik eşleştirmeye dayanarak, sağlanan 140 aday film arasından kullanıcının kişilik profiline **en uygun olan TAM OLARAK 70** filmi seç. Seçimlerin, profilin bütününü yansıtmalı ve sadece tek bir özelliğe dayanmamalıdır.

## ÇIKTI GEREKSİNİMLERİ

Yanıtın **SADECE ve SADECE** aşağıdaki JSON formatında olmalıdır. JSON nesnesi dışında **kesinlikle** başka hiçbir metin (açıklama, selamlama vb.) ekleme.

```json
{{
  "recommended_film_ids": ["FILM_ID_1", "FILM_ID_2", "FILM_ID_3", ..., "FILM_ID_70"]
}}
```

## KESİN KISITLAMALAR

*   Çıktı **tam olarak 70** film ID'si içermelidir.
*   Sadece `ADAY FİLM METAVERİLERİ` bölümünde sağlanan film ID'lerini kullan.
*   Sağlanan meta verilerin dışına çıkma, varsayım yapma veya harici bilgi kullanma. **PLOT bilgisi olmadığını tekrar hatırla.**
*   Yanıtın sadece belirtilen JSON formatında olsun. Öncesinde veya sonrasında **hiçbir ek metin bulunmamalıdır.**
"""
        
        return prompt
    
    def _parse_film_response(self, response: str) -> List[str]:
        """
        Parse Gemini response to extract film recommendations.
        
        Extracts the JSON portion of the response and parses the recommended film IDs.
        
        Args:
            response: The raw response string from Gemini API
        
        Returns:
            A list of film IDs (up to 70)
            
        Raises:
            ValueError: If the response cannot be parsed or doesn't contain valid film IDs
            json.JSONDecodeError: If the response cannot be parsed as JSON
            TypeError: If the recommended_film_ids field is not a list or contains non-string items
        """
        if not response or not response.strip():
            logger.error("Received empty response from Gemini API")
            raise ValueError("Empty response received from Gemini API")
        
        try:
            # First, try to parse directly as JSON
            try:
                data = json.loads(response)
            except json.JSONDecodeError as jde:
                # If direct parsing fails, try to extract JSON using regex
                import re
                logger.warning(f"Direct JSON parsing failed: {jde}. Attempting regex extraction.")
                
                # Try to find anything that looks like JSON object
                json_match = re.search(r'({.*})', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                    try:
                        data = json.loads(json_str)
                    except json.JSONDecodeError as nested_jde:
                        logger.error(f"Regex-extracted JSON parsing failed: {nested_jde}")
                        raise ValueError(f"Could not parse JSON from Gemini response: {nested_jde}")
                else:
                    logger.error("No JSON-like structure found in Gemini response")
                    raise ValueError("No valid JSON found in Gemini response")
            
            # Validate response structure
            if not isinstance(data, dict):
                logger.error(f"Expected a JSON object, got {type(data).__name__}")
                raise TypeError(f"Expected a JSON object but got {type(data).__name__}")
                
            # Validate that we have the required fields
            if "recommended_film_ids" not in data:
                logger.error("Missing 'recommended_film_ids' field in Gemini response")
                raise ValueError("Missing 'recommended_film_ids' field in Gemini response")
            
            film_ids = data["recommended_film_ids"]
            
            # Validate that film_ids is a list
            if not isinstance(film_ids, list):
                logger.error(f"'recommended_film_ids' should be a list, got {type(film_ids).__name__}")
                raise TypeError(f"'recommended_film_ids' should be a list, got {type(film_ids).__name__}")
            
            # Validate there are films in the list
            if not film_ids:
                logger.error("Gemini returned an empty list of film IDs")
                raise ValueError("Gemini returned an empty list of film IDs")
            
            # Validate all elements are strings and not empty
            non_strings = [i for i, x in enumerate(film_ids) if not isinstance(x, str)]
            if non_strings:
                logger.error(f"Non-string elements found at indexes {non_strings}")
                raise TypeError(f"All film IDs must be strings, found non-string elements at indexes {non_strings}")
                
            empty_strings = [i for i, x in enumerate(film_ids) if isinstance(x, str) and not x.strip()]
            if empty_strings:
                logger.error(f"Empty string elements found at indexes {empty_strings}")
                raise ValueError(f"All film IDs must be non-empty, found empty strings at indexes {empty_strings}")
            
            # Handle case where fewer than 70 films are returned
            if len(film_ids) < 70:
                logger.warning(f"Gemini returned fewer than 70 films ({len(film_ids)}). This might affect recommendation quality.")
            
            # Ensure we don't exceed 70 films
            if len(film_ids) > 70:
                logger.warning(f"Gemini returned more than 70 films ({len(film_ids)}), truncating to 70")
                film_ids = film_ids[:70]
            
            return film_ids
            
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            logger.error(f"Error parsing film response: {e}")
            logger.error(f"Original response: {response[:500]}{'...' if len(response) > 500 else ''}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error parsing film response: {e}")
            logger.error(f"Original response: {response[:500]}{'...' if len(response) > 500 else ''}")
            raise ValueError(f"Unexpected error processing Gemini response: {e}")
    
    async def _save_recommendations(self, user_id: str, film_ids: List[str]) -> None:
        """
        Save film recommendations to the database.
        
        First deletes any existing recommendations for the user, then saves the new ones.
        """
        try:
            # Save recommendations using the repository method
            await self.recommendation_repository.save_suggestions(user_id, film_ids)
            logger.info(f"Saved {len(film_ids)} film recommendations for user: {user_id}")
        except Exception as e:
            logger.error(f"Error saving film recommendations for user {user_id}: {e}")
            raise
