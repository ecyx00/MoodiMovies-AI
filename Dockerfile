# Python 3.10 slim imajını kullan
FROM python:3.10-slim

# Çalışma dizinini ayarla
WORKDIR /app

# Sistem paket listesini güncelle ve gerekli araçları kur
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    unixodbc \
    unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

# Microsoft GPG anahtarını ekle
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -

# Microsoft Debian deposunu ekle (Debian 11/Bullseye için)
RUN curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list

# Paket listesini tekrar güncelle ve ODBC sürücüsünü kur
RUN apt-get update && ACCEPT_EULA=Y apt-get install -y --no-install-recommends \
    msodbcsql17 \
    && apt-get purge -y --auto-remove curl gnupg \
    && rm -rf /var/lib/apt/lists/*

# Python bağımlılıklarını kur
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Gunicorn ekle (üretim ortamı için ASGI sunucusu)
RUN pip install --no-cache-dir gunicorn

# Uygulama kodunu kopyala
COPY ./app /app/app
COPY ./main.py /app/main.py

# Statik dosyaları ve definitions.json dosyasını kopyala
COPY ./app/static /app/app/static

# 8001 portunu dışarıya aç
EXPOSE 8001

# Üretim ortamı için çalıştırma komutu (gunicorn ile uvicorn worker'ları)
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8001", "main:app"]
