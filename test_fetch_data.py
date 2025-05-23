# test_fetch_data.py (Proje ana dizininde olmalı)
import asyncio
from pprint import pprint # Daha okunaklı yazdırmak için
from decimal import Decimal # Olası Decimal dönüşümlerini görmek için
import os # os modülünü import et
from dotenv import load_dotenv
import sys
from pathlib import Path

# Python yoluna projenin ana dizinini ekle
current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
print(f"Proje dizini: {current_dir}")
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))
    print(f"'{current_dir}' Python PATH'e eklendi")

# .env dosyasını proje kök dizininden yükle
# Bu script kök dizinde olduğu için Path(".") işe yarar
dotenv_path = Path(".") / ".env"
print(f".env dosyası aranıyor: {dotenv_path.resolve()}")
loaded = load_dotenv(dotenv_path=dotenv_path, verbose=True) # verbose=True ekleyerek yükleme detaylarını gör

if not loaded:
    print(f"UYARI: .env dosyası '{dotenv_path.resolve()}' adresinde bulunamadı veya yüklenemedi.")
    print("Lütfen .env dosyasının doğru yerde ve doğru formatta olduğundan emin olun.")
    # .env olmadan devam etmek anlamsız, çıkalım.
    # sys.exit(1) # Hata durumunda çıkmak için yorumu kaldırabilirsiniz
else:
    print(".env dosyası başarıyla yüklendi.")

# Önce temel modülleri import edelim
try:
    from app.core.config import get_settings
    # Dairesel import sorununu önlemek için diğer importları aşağıda main fonksiyonu içinde yapacağız
except ImportError as e:
    print(f"\n!!! IMPORT HATASI: Temel modüller bulunamadı. Yolları kontrol edin: {e}")
    print("Lütfen 'app' klasörünün Python PATH'inizde olduğundan emin olun.")
    sys.exit(1)

async def main():
    """Veritabanından kullanıcı yanıtlarını çekip yazdırır."""
    print("\nAyarlar yükleniyor...")
    try:
        settings = get_settings()
        print(f"DB Ayarları: Driver='{settings.DB_DRIVER}', Server='{settings.DB_SERVER}', DB='{settings.DB_DATABASE}', User='{settings.DB_USERNAME or 'Windows Auth'}'")
    except Exception as e:
        print(f"Ayarlar yüklenirken HATA: {e}")
        return
        
    # Gereken diğer modülleri import et
    try:
        from app.core.clients.mssql import MSSQLClient
        from app.db.repositories import ResponseRepository, RepositoryError
        from app.schemas.personality import ResponseDataItem
        print("Gereken tüm modüller başarıyla import edildi.")
    except ImportError as e:
        print(f"\n!!! IMPORT HATASI: {e}")
        return

    print("\nVeritabanı istemcisi ve repository oluşturuluyor...")
    try:
        db_client = MSSQLClient(settings) # Client'ı başlat (try_connect çağrılacak)
        response_repo = ResponseRepository(db_client)
        print("İstemci ve repository başarıyla oluşturuldu.")
    except Exception as e:
        print(f"İstemci/Repository oluşturulurken HATA: {e}")
        return

    # !!! BURAYA VERİTABANINA EKLEDİĞİNİZ TEST KULLANICISININ ID'sini YAZIN !!!
    test_user_id = "U001" # <<<< KENDİ TEST KULLANICI ID'NİZİ (U001) YAZIN

    print(f"\n'{test_user_id}' için yanıtlar çekiliyor...")
    try:
        # Repository metodunu çağır
        responses_raw = await response_repo.get_user_responses(test_user_id)

        if not responses_raw:
            print(f"\n>>> '{test_user_id}' için veritabanında yanıt bulunamadı.")
            print(">>> Lütfen MOODMOVIES_RESPONSE tablosuna bu kullanıcı için veri eklediğinizden emin olun.")
            return

        print(f"\n>>> {len(responses_raw)} adet ham yanıt bulundu (DB'den geldiği gibi):")
        # İlk birkaç ham yanıtı yazdır (sözlük listesi olmalı)
        for i, row in enumerate(responses_raw[:3]): # İlk 3 tanesini yazdır
            print(f"--- Yanıt {i+1} (Ham Veri) ---")
            pprint(row) # pprint ile daha okunaklı yazdır

        print("\n>>> Yanıtlar kontrol ediliyor...")
        parsed_responses = []
        skipped_count = 0
        for i, row in enumerate(responses_raw):
            try:
                # Nesne türünü kontrol et
                if hasattr(row, '__class__') and row.__class__.__name__ == 'ResponseDataItem':
                    # Zaten ResponseDataItem nesnesi, doğrudan kullan
                    parsed_responses.append(row)
                    print(f"--- Yanıt {i+1} zaten ResponseDataItem formatında ---")
                else:
                    # Sözlük ise Pydantic modeline dönüştür
                    item = ResponseDataItem(**row)
                    parsed_responses.append(item)
                    print(f"--- Yanıt {i+1} ResponseDataItem formatına dönüştürüldü ---")
            except Exception as p_error:
                print(f"--- HATA: Satır {i+1} işlenemedi ---")
                pprint(row)
                print(f"Hata: {p_error}")
                skipped_count += 1

        if parsed_responses:
             print(f"\n>>> Başarıyla parse edilen {len(parsed_responses)} yanıtın ilkinin modeli:")
             # Parse edilmiş ilk Pydantic modelini yazdır
             # .model_dump() Pydantic V2'de kullanılır
             try:
                 print(parsed_responses[0].model_dump())
             except AttributeError:
                 print(parsed_responses[0].dict()) # Eski Pydantic versiyonları için fallback

        if skipped_count > 0:
             print(f"\n>>> DİKKAT: {skipped_count} adet yanıt Pydantic modeline parse edilemedi!")
        else:
             print("\n>>> Tüm yanıtlar başarıyla Pydantic modeline parse edildi.")


    except RepositoryError as repo_err:
        print(f"\n>>> Repository Hatası: {repo_err}")
    except Exception as e:
        print(f"\n>>> Beklenmedik Hata: {e}")

if __name__ == "__main__":
    print("Veri Çekme Testi Başlatılıyor...")
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
    print("\nVeri Çekme Testi Tamamlandı.")
