# MoodieMovies AI Servisi

AI destekli kişiselleştirilmiş film önerileri sunan MoodieMovies AI Servisi'nin geliştirme deposu.

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/Framework-FastAPI-green.svg)](https://fastapi.tiangolo.com/)

## Proje Hakkında

MoodieMovies AI Servisi, kullanıcıların Big Five (OCEAN) kişilik modelini kullanarak oluşturulan profillerine göre kişiselleştirilmiş film önerileri sunar. Servis, FastAPI ile geliştirilmiş ve Google Gemini API entegrasyonu içermektedir.

İki temel bileşeni vardır:
- **Agent 1: Kişilik Profili Hesaplayıcı** - Kullanıcıların test yanıtlarından kişilik T-skorlarını hesaplar
- **Agent 2: Film Önerici** - Kişilik profiline dayanarak film önerileri oluşturur

Daha detaylı bilgi için [`documentation.md`](documentation.md) dosyasına bakabilirsiniz.

## Kurulum

### Önkoşullar

- Python 3.10 veya daha yeni sürüm
- MS SQL Server veritabanı (MOODMOVIES)
- Google Gemini API erişimi (takım üyeleri ortak API anahtarını kullanabilir)
- Git

### Adım 1: Projeyi Klonlama

```bash
git clone https://github.com/[kullanıcı-adınız]/MoodiMovies-AI.git
cd moodie_ai_service
```

### Adım 2: Sanal Ortam Oluşturma

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/MacOS
python -m venv venv
source venv/bin/activate
```

### Adım 3: Bağımlılıkları Yükleme

```bash
pip install -r requirements.txt
```

### Adım 4: Çevre Değişkenlerini Ayarlama

Proje, `.env` dosyasında bulunan çevre değişkenlerini kullanır. Repo'da bulunan `.env.example` dosyasını `.env` olarak kopyalayın ve kendi değerlerinizi girin:

```bash
# Windows
copy .env.example .env

# Linux/MacOS
cp .env.example .env
```

Daha sonra `.env` dosyasını kendi ortamınıza göre düzenleyin. Dosyada aşağıdaki değişkenler bulunmalıdır:

```
# Veritabanı Ayarları
DB_DRIVER=<SQL Server ODBC Sürücüsü>
DB_SERVER=<SQL Server Adı>
DB_DATABASE=<Veritabanı Adı>

# Gemini API Ayarları
GEMINI_API_KEY=<API Anahtarınız>
GEMINI_MODEL=<Kullanılacak Gemini Model Adı>

# Loglama Ayarları
LOG_LEVEL=<Log Seviyesi>
LOG_FULL_GEMINI_IO=<True/False>
```

**NOT:** Takım yöneticinizden API anahtarlarını ve gerekli bağlantı bilgilerini alın. Bu bilgileri GitHub'a veya herhangi bir halka açık alana yüklemediğinizden emin olun.

## Uygulamayı Çalıştırma

### API Servisini Başlatma

```bash
uvicorn main:app --reload --port 8000
```

Servis başlatıldıktan sonra API dokümantasyonuna `http://localhost:8000/docs` adresinden erişebilirsiniz.

### Test Ajanlarını Çalıştırma

`test_agents.py` dosyası, Agent 1 (Kişilik Profili Hesaplayıcı) ve Agent 2 (Film Önerici) ajanlarını belirli bir kullanıcı için çalıştırmak için tasarlanmıştır. Bu betiği kullanarak kişilik profili hesaplama ve film önerme süreçlerini test edebilirsiniz.

#### Kullanım

```bash
python test_agents.py
```

Bu komut interaktif olarak test etmek istediğiniz kullanıcı ID'sini soracaktır.

Veya belirli bir kullanıcı ID'si ile doğrudan çalıştırmak için:

```bash
python test_agents.py --user_id TEST_USER_001
```

#### Test Kullanıcıları Oluşturma

Test işlemleri için veritabanında test kullanıcıları ve yanıtlarını oluşturmanız gerekir. Örnek SQL komutları:

```sql
-- Test kullanıcısı eklemek için
INSERT INTO MOODMOVIES_USERS (USER_ID, USER_NAME, USER_PASS, CREATED)
VALUES ('TEST_USER_001', 'Test User', 'test123', GETDATE())

-- Test yanıtları eklemek için
INSERT INTO MOODMOVIES_RESPONSE (RESPONSE_ID, USER_ID, QUESTION_ID, ANSWER_ID, RESPONSE_DATE)
VALUES 
('RES001', 'TEST_USER_001', 'Q001', 'A004', GETDATE()),
('RES002', 'TEST_USER_001', 'Q002', 'A001', GETDATE()),
-- Diğer yanıtları da benzer şekilde ekleyin
('RES060', 'TEST_USER_001', 'Q060', 'A002', GETDATE());
```

Not: Veritabanında bulunan gerçek soru ve cevap ID'lerine göre bu değerleri uyarlayın.

## Çalışma Akışı

1. **Kişilik Profili Hesaplama**:
   - `test_agents.py` önce PersonalityProfilerAgent'ı çalıştırır
   - Kullanıcının tüm test yanıtları veritabanından alınır
   - 35 T-skoru (5 domain, 30 facet) hesaplanır ve veritabanına kaydedilir

2. **Film Önerileri Oluşturma**:
   - Kullanıcının profiline göre uygun film türleri belirlenir
   - Belirlenen türlere göre aday filmler seçilir
   - Kişilik profiline en uygun filmler seçilir ve veritabanına kaydedilir

## Sorun Giderme

- **Veritabanı Bağlantı Hatası**: 
  - `.env` dosyasındaki veritabanı bilgilerinin doğru olduğundan emin olun
  - SQL Server'in çalıştığını kontrol edin
  - Gerekli ODBC sürücülerinin kurulu olduğundan emin olun

- **Python Modül Hatası**: 
  - `pip install -r requirements.txt` komutunu çalıştırarak tüm bağımlılıkları yükleyin
  - Sanal ortamın aktif olduğundan emin olun
  - Python sürümünün 3.10 veya daha yeni olduğunu kontrol edin

- **Gemini API Hatası**: 
  - `.env` dosyasındaki API anahtarının doğru olduğunu kontrol edin
  - API kullanım limitlerini aşmadığınızdan emin olun
  - Belirtilen Gemini modelinin mevcut olduğunu doğrulayın

## Takım İçi Geliştirme Süreci

1. En güncel kodu alın: `git pull origin main`
2. Değişikliklerinizi yapın
3. Değişiklikleri commit edin: `git commit -am "Açıklayıcı commit mesajı"`
4. Değişikliklerinizi gönderin: `git push origin main`

Bu repository private olduğu ve sadece takım üyeleri erişebildiği için doğrudan main branch üzerinde çalışabiliriz.

## Lisans

Bu proje özel bir projedir ve tüm hakları saklıdır. Yalnızca takım üyeleri tarafından kullanılabilir.
 #MoodieMovie-AI
