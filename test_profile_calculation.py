# test_profile_calculation.py
import asyncio
import sys
import os
from pathlib import Path
from pprint import pprint
from decimal import Decimal
from dotenv import load_dotenv

# Python yoluna projenin ana dizinini ekle
current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
print(f"Proje dizini: {current_dir}")
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))
    print(f"'{current_dir}' Python PATH'e eklendi")

# .env dosyasını yükle
dotenv_path = Path(".") / ".env"
print(f".env dosyası yükleniyor: {dotenv_path.resolve()}")
loaded = load_dotenv(dotenv_path=dotenv_path, verbose=True)
if not loaded:
    print(f"UYARI: .env dosyası yüklenemedi!")
    sys.exit(1)
else:
    print(".env dosyası başarıyla yüklendi.")

# Önce temel modülleri import edelim
try:
    from app.core.config import get_settings
    print("Temel modüller başarıyla yüklendi.")
except ImportError as e:
    print(f"\n!!! IMPORT HATASI: Temel modüller bulunamadı. Yolları kontrol edin: {e}")
    sys.exit(1)

async def main():
    """
    Kişilik profili hesaplamalarını test etmek için bir kullanıcının
    yanıtlarını çekip skorlarını hesaplar ve veritabanına kaydeder.
    """
    print("\nKişilik Profili Hesaplama ve Kaydetme Testi Başlatılıyor...")

    # Test kullanıcı ID'si
    test_user_id = "U001"  # Kendi test kullanıcı ID'nizi yazın
    
    # Gerekli bağımlılıkları import et
    try:
        from app.core.clients.mssql import MSSQLClient
        from app.db.repositories import ResponseRepository, ProfileRepository
        from app.agents.calculators.python_score_calculator import PythonScoreCalculator
        from app.agents.personality_profiler import (
            PersonalityDataFetcher, 
            PersonalityResultValidator,
            PersonalityProfileSaver,
            PersonalityProfilerAgent
        )
        print("Gerekli tüm modüller başarıyla import edildi.")
    except ImportError as e:
        print(f"\n!!! IMPORT HATASI: {e}")
        return

    # Ayarları yükle
    print("\nAyarlar yükleniyor...")
    try:
        settings = get_settings()
        print(f"DB Ayarları: Driver='{settings.DB_DRIVER}', Server='{settings.DB_SERVER}', DB='{settings.DB_DATABASE}'")
        print(f"Gemini API Anahtarı: {settings.GEMINI_API_KEY[:4]}...{settings.GEMINI_API_KEY[-4:] if settings.GEMINI_API_KEY else 'YOK'}")
        print(f"Gemini Model: {settings.GEMINI_MODEL}")
    except Exception as e:
        print(f"Ayarlar yüklenirken HATA: {e}")
        return

    # Veritabanı bağlantısı oluştur
    print("\nVeritabanı istemcisi oluşturuluyor...")
    try:
        db_client = MSSQLClient(settings)
        print("Veritabanı istemcisi başarıyla oluşturuldu.")
    except Exception as e:
        print(f"Veritabanı istemcisi oluşturulurken HATA: {e}")
        return

    # Not: Artık Gemini API kullanmıyoruz, Python tabanlı hesaplama kullanıyoruz

    # Repository ve agent bileşenlerini oluştur
    response_repo = ResponseRepository(db_client)
    definitions_path = str(current_dir / "app" / "static" / "definitions.json")
    print(f"Definitions dosyası: {definitions_path}")
    profile_repo = ProfileRepository(db_client, definitions_path)
    
    # PersonalityProfilerAgent bileşenlerini oluştur
    data_fetcher = PersonalityDataFetcher(response_repo)
    score_calculator = PythonScoreCalculator(settings)
    validator = PersonalityResultValidator()
    saver = PersonalityProfileSaver(profile_repo)
    
    # Profiler agent'ı oluştur
    profiler_agent = PersonalityProfilerAgent(
        data_fetcher=data_fetcher,
        score_calculator=score_calculator,
        validator=validator,
        saver=saver
    )
    
    # Test kullanıcısı için profil hesaplama işlemini çalıştır
    print(f"\n'{test_user_id}' için profil hesaplama işlemi başlatılıyor...")
    try:
        # PersonalityProfilerAgent'ın process_user_test metodunu çağır
        profile_id = await profiler_agent.process_user_test(test_user_id)
        print(f"\n>>> İşlem BAŞARILI! Profil ID: {profile_id}")
        
        # Kayıt kontrol - Kullanıcının profilini veritabanından çekelim
        print(f"\nKaydedilen profili veritabanından kontrol ediyoruz...")
        saved_profile = await profile_repo.get_latest_profile(test_user_id)
        
        if saved_profile:
            print("\n>>> Kayıt başarıyla doğrulandı!")
            print("\nProfil özeti:")
            print(f"ID: {saved_profile.get('profile_id')}")
            print(f"Kullanıcı: {saved_profile.get('user_id')}")
            print(f"Oluşturulma: {saved_profile.get('created')}")
            
            # Domain skorlarını göster
            print("\nDomain skorları:")
            for domain in ['O', 'C', 'E', 'A', 'N']:
                score_key = f"{domain.lower()}_domain"
                if score_key in saved_profile:
                    print(f"{domain}: {saved_profile.get(score_key)}")
            
            # Bazı facet skorlarını göster (örnek olarak)
            print("\nBazı facet skorları (örnek):")
            facet_keys = sorted([k for k in saved_profile.keys() if '_facet_' in k])[:6]
            for key in facet_keys:
                print(f"{key}: {saved_profile.get(key)}")
        else:
            print(f"\n!!! HATA: Profil ID '{profile_id}' veritabanında bulunamadı.")
    
    except Exception as e:
        print(f"\n!!! İşlem BAŞARISIZ: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Kişilik Profili Hesaplama Testi Başlatılıyor...")
    # Python 3.7+ için standart async çalıştırma yöntemi
    try:
        asyncio.run(main())
    except RuntimeError as e:
        # Özellikle Jupyter gibi ortamlarda çalışan event loop hatasını yönet
        if "Cannot run the event loop while another loop is running" in str(e):
            print("Mevcut bir event loop üzerinde çalıştırılıyor...")
            loop = asyncio.get_event_loop()
            loop.run_until_complete(main())
        else:
            raise e
    print("\nKişilik Profili Hesaplama Testi Tamamlandı.")
