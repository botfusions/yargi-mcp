# 🚀 TurkLawAI.com Production Deployment - Emergency Auth Fix

## Durum: API server localhost'ta çalışıyor, production'a deploy etmemiz gerekiyor

### 1. ADIM: API Server'ı Sunucuya Yükle

Bu dosyaları turklawai.com sunucusuna kopyala:

```bash
# Ana dizin: /var/www/turklawai/
turklawai_api_server.py         # API server
turklawai_auth_fix.py          # Authentication logic  
supabase_client.py             # Database client
.env                           # Environment variables
```

### 2. ADIM: Sunucuda Dependencies Yükle

```bash
ssh root@turklawai.com
cd /var/www/turklawai/

# Python dependencies
pip3 install fastapi uvicorn supabase python-dotenv python-jose[cryptography] pydantic[email]

# Test installation
python3 -c "import fastapi, uvicorn, supabase; print('Dependencies OK')"
```

### 3. ADIM: API Server'ı Başlat

```bash
# Background'da çalıştır
nohup python3 turklawai_api_server.py > api.log 2>&1 &

# Çalışıyor mu kontrol et
curl http://localhost:8001/health

# Beklenen cevap:
# {"status":"healthy","timestamp":"2025-01-10","services":{"api":"operational","supabase":"connected","authentication":"active"}}
```

### 4. ADIM: Nginx Reverse Proxy Ayarla

`/etc/nginx/sites-available/turklawai.com` dosyasına ekle:

```nginx
# API Proxy
location /api/ {
    proxy_pass http://localhost:8001/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection 'upgrade';
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_cache_bypass $http_upgrade;
    
    # CORS headers
    add_header Access-Control-Allow-Origin *;
    add_header Access-Control-Allow-Methods "GET, POST, OPTIONS";
    add_header Access-Control-Allow-Headers "Content-Type, Authorization";
    
    # Handle preflight requests
    if ($request_method = 'OPTIONS') {
        add_header Access-Control-Allow-Origin *;
        add_header Access-Control-Allow-Methods "GET, POST, OPTIONS";
        add_header Access-Control-Allow-Headers "Content-Type, Authorization";
        add_header Content-Length 0;
        add_header Content-Type text/plain;
        return 200;
    }
}
```

Nginx'i restart et:
```bash
sudo systemctl restart nginx
```

### 5. ADIM: Frontend'i Güncelle

Ana HTML dosyanda Supabase script'lerini çıkar ve bizim sistem'i ekle:

```html
<!-- ESKİ SUPABASE SCRIPTS'LERİNİ ÇİKAR -->
<!-- <script src="supabase-auth.js"></script> -->

<!-- YENİ AUTH SYSTEM -->
<script src="/js/turklawai_frontend_replacement.js"></script>
```

### 6. ADIM: Test Et

```bash
# API server test
curl https://turklawai.com/api/health

# Admin login test
curl -X POST https://turklawai.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@turklawai.com", "password": "admin123"}'

# Beklenen cevap:
# {"success":true,"message":"Giriş başarılı","user":{"id":5,"email":"admin@turklawai.com","full_name":"TurkLawAI Admin","plan":"enterprise"},"token":"eyJ..."}
```

### 7. ADIM: Browser'da Test

1. https://turklawai.com/login sayfasına git
2. admin@turklawai.com / admin123 ile giriş yap
3. Console'da hata olmamalı
4. Başarılı giriş yapmalı

## Önemli Notlar:

- ✅ Admin user database'de var: `admin@turklawai.com` / `admin123`  
- ✅ API server localhost'ta çalışıyor
- ✅ Supabase connection OK
- ❌ Production'a deploy edilmesi gerekiyor

## Sorun Gidermek İçin:

```bash
# API server logs
tail -f /var/www/turklawai/api.log

# Nginx logs  
tail -f /var/log/nginx/error.log

# API server çalışıyor mu?
ps aux | grep turklawai_api_server

# Port dinliyor mu?
netstat -tlnp | grep 8001
```

## Güvenlik:

- API server sadece localhost:8001'de çalışır
- Nginx reverse proxy ile güvenli erişim
- CORS headers düzgün ayarlanmış
- JWT token authentication

Bu adımları takip ettikten sonra authentication sistemi çalışacaktır!