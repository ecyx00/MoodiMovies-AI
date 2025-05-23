# test_db_connection.py (Proje ana dizininde olmalı)
import pyodbc
import os
from dotenv import load_dotenv
import sys
from pathlib import Path # Path kullanımı için

# .env dosyasını proje kök dizininden yükle
# Bu script kök dizinde olduğu için Path(".") işe yarar
dotenv_path = Path(".") / ".env"
loaded = load_dotenv(dotenv_path=dotenv_path)

if not loaded:
    print(f"UYARI: .env dosyası '{dotenv_path.resolve()}' adresinde bulunamadı veya yüklenemedi.")
    print("Lütfen .env dosyasının doğru yerde ve doğru formatta olduğundan emin olun.")
    # .env olmadan devam etmek anlamsız, çıkalım.
    # sys.exit(1) # Hata durumunda çıkmak için yorumu kaldırabilirsiniz

# .env'den veya varsayılanlardan (varsa) değerleri oku
db_driver = os.getenv('DB_DRIVER')
db_server = os.getenv('DB_SERVER')
db_database = os.getenv('DB_DATABASE')
db_username = os.getenv('DB_USERNAME') # None veya boş olabilir
db_password = os.getenv('DB_PASSWORD') # None veya boş olabilir

if not all([db_driver, db_server, db_database]):
    print("\nHATA: .env dosyasındaki DB_DRIVER, DB_SERVER, DB_DATABASE bilgileri eksik veya yüklenemedi!")
    print(f"DB_DRIVER: {db_driver}")
    print(f"DB_SERVER: {db_server}")
    print(f"DB_DATABASE: {db_database}")
    sys.exit(1)

# Bağlantı dizesini oluştur
connection_params = [
    f"DRIVER={{{db_driver}}}",
    f"SERVER={db_server}",
    f"DATABASE={db_database}",
    "TrustServerCertificate=yes" # SSMS ekran görüntüsüne göre ekledik
]

if db_username and db_password:
    # SQL Server Authentication
    print("SQL Server Authentication kullanılıyor...")
    connection_params.append(f"UID={db_username}")
    connection_params.append(f"PWD={db_password}") # Süslü parantez genellikle PWD için gereksiz
else:
    # Windows Authentication
    print("Windows Authentication (Trusted Connection) kullanılıyor...")
    connection_params.append("Trusted_Connection=yes")

conn_str = ";".join(connection_params)

print("\nAşağıdaki bağlantı dizesi denenecek:")
# Şifreyi yazdırmadan gösterelim
print(conn_str.replace(f"PWD={db_password}", "PWD=*****") if db_password else conn_str)

try:
    # Kısa bir timeout ile bağlanmayı dene
    print("\nBağlanılıyor...")
    conn = pyodbc.connect(conn_str, timeout=5)
    print(">>> Bağlantı BAŞARILI!")
    cursor = conn.cursor()
    print(">>> Basit bir sorgu çalıştırılıyor (SELECT @@SERVERNAME)...") # @@VERSION yerine @@SERVERNAME daha basit
    cursor.execute("SELECT @@SERVERNAME;")
    row = cursor.fetchone()
    if row:
        print(">>> Sorgu Başarılı! Bağlanılan Sunucu:")
        print(row[0])
    else:
        print(">>> Sorgu çalıştı ama sonuç dönmedi.")
    cursor.close()
    conn.close()
    print(">>> Bağlantı kapatıldı.")
except Exception as e:
    print(f"\n>>> Bağlantı HATASI: {e}")
    print(">>> Lütfen .env dosyasındaki bilgileri (DRIVER, SERVER, DATABASE), ODBC sürücüsünü ve")
    print(">>> SQL Server'daki kullanıcı izinlerini/Windows Authentication ayarlarını kontrol edin.")
    print(">>> Ayrıca ağ bağlantınızı ve güvenlik duvarı ayarlarınızı gözden geçirin.")
