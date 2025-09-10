# 🛠️ TurkLawAI.com Authentication Fix - Deployment Guide

## 🔍 Problem Tespiti TAMAMLANDI ✅

**Ana Sorunlar:**
- ❌ Clerk authentication keys placeholder değerlerinde
- ❌ Google OAuth düzgün configure edilmemiş  
- ❌ Kayıt sistemi çalışmıyor
- ❌ Admin girişi yapılamıyor

## 🚀 Çözüm - 3 Aşamalı Deployment

### AŞAMA 1: Supabase Database Setup

1. **Supabase SQL Editor'e Git**: https://supabase.turklawai.com/dashboard/sql

2. **Users Tablosunu Oluştur** (Bu SQL'i çalıştır):

```sql
CREATE TABLE IF NOT EXISTS yargi_mcp_users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    plan VARCHAR(50) DEFAULT 'free',
    is_active BOOLEAN DEFAULT true,
    email_verified BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_yargi_mcp_users_email ON yargi_mcp_users(email);

INSERT INTO yargi_mcp_users (email, password_hash, full_name, plan, is_active, email_verified)
SELECT 
    'admin@turklawai.com',
    'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    'TurkLawAI Admin',
    'enterprise',
    true,
    true
WHERE NOT EXISTS (
    SELECT 1 FROM yargi_mcp_users WHERE email = 'admin@turklawai.com'
);
```

**Default Admin Hesabı:** admin@turklawai.com / admin123

---

### AŞAMA 2: Backend API Server Deploy

1. **API Server'ı Deploy Et:**

```bash
# Dosyaları sunucuya kopyala
scp turklawai_api_server.py root@turklawai.com:/var/www/turklawai/
scp turklawai_auth_fix.py root@turklawai.com:/var/www/turklawai/
scp supabase_client.py root@turklawai.com:/var/www/turklawai/

# Sunucuda çalıştır
ssh root@turklawai.com
cd /var/www/turklawai/
python3 turklawai_api_server.py
```

2. **Nginx Reverse Proxy Ekle:**

```nginx
# /etc/nginx/sites-available/turklawai.com
server {
    listen 443 ssl http2;
    server_name turklawai.com www.turklawai.com;

    # Existing SSL config...

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
    }

    # Static files
    location / {
        root /var/www/turklawai/public;
        try_files $uri $uri/ /index.html;
    }
}
```

```bash
# Nginx'i restart et
sudo systemctl restart nginx
```

---

### AŞAMA 3: Frontend Integration

1. **Ana HTML dosyana bu script'leri ekle:**

```html
<!-- TurkLawAI Authentication Fix -->
<script src="/js/turklawai_frontend_fix.js"></script>

<!-- Existing authentication forms'larına data attributes ekle -->
<form id="login-form" data-auth="login-form">
    <input type="email" name="email" required>
    <input type="password" name="password" required>
    <button type="submit">Giriş Yap</button>
</form>

<form id="register-form" data-auth="register-form">
    <input type="text" name="full_name" placeholder="Ad Soyad">
    <input type="email" name="email" required>
    <input type="password" name="password" required>
    <button type="submit">Kayıt Ol</button>
</form>

<!-- User info display -->
<div data-auth="user-info" class="hidden"></div>

<!-- Logout button -->
<button data-auth="logout-btn" class="hidden">Çıkış Yap</button>

<!-- Protected content -->
<div data-auth="protected" class="hidden">
    <p>Bu içerik sadece giriş yapmış kullanıcılar için.</p>
</div>
```

2. **JavaScript dosyasını kopyala:**

```bash
# turklawai_frontend_fix.js dosyasını /var/www/turklawai/public/js/ klasörüne kopyala
scp turklawai_frontend_fix.js root@turklawai.com:/var/www/turklawai/public/js/
```

---

## 🧪 Test Adımları

### 1. API Server Test
```bash
# Health check
curl https://turklawai.com/api/health

# Test registration
curl -X POST https://turklawai.com/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@turklawai.com",
    "password": "test123456",
    "full_name": "Test User"
  }'

# Test login
curl -X POST https://turklawai.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@turklawai.com",
    "password": "admin123"
  }'
```

### 2. Frontend Test
1. https://turklawai.com'a git
2. "Kayıt Ol" formunu test et
3. "Giriş Yap" formunu test et
4. Admin hesabıyla giriş yap: admin@turklawai.com / admin123

---

## 📋 Checklist

- [ ] ✅ Supabase users tablosu oluşturuldu
- [ ] ✅ API server deploy edildi ve çalışıyor
- [ ] ✅ Nginx reverse proxy ayarlandı
- [ ] ✅ Frontend JavaScript entegre edildi
- [ ] ✅ Registration test edildi
- [ ] ✅ Login test edildi
- [ ] ✅ Admin girişi test edildi
- [ ] ✅ User session management çalışıyor

---

## 🔧 Troubleshooting

### Problem: API Server Çalışmıyor
**Çözüm:**
```bash
# Logs kontrol et
journalctl -u turklawai-api -f

# Manual olarak başlat
cd /var/www/turklawai
python3 turklawai_api_server.py
```

### Problem: CORS Hatası
**Çözüm:**
- `turklawai_api_server.py` içinde `CORS_ORIGINS` listesini kontrol et
- `https://turklawai.com` adresinin listeye ekli olduğundan emin ol

### Problem: Database Connection
**Çözüm:**
```bash
# Environment variables kontrol et
echo $SUPABASE_URL
echo $SUPABASE_ANON_KEY

# Connection test
python3 -c "
from supabase_client import supabase_client
import asyncio
asyncio.run(supabase_client.test_connection())
"
```

---

## 🔄 Gelecekteki Clerk OAuth Entegrasyonu

Bu emergency fix çalıştıktan sonra, ileride proper Clerk OAuth'u entegre etmek için:

1. **Clerk Dashboard'da proje oluştur**
2. **Real API keys'leri .env'e ekle**
3. **Google OAuth provider'ı configure et**
4. **Frontend'i Clerk SDK ile güncelle**

**Rehber:** `CLERK_SETUP_GUIDE.md` dosyasına bakın.

---

## 📞 Destek

Bu deployment ile ilgili sorularınız için:
- API Endpoint'leri: `/api/auth/register`, `/api/auth/login`, `/api/auth/user`
- Admin hesap: admin@turklawai.com / admin123
- Test hesap: test@turklawai.com / test123456

**Deployment tamamlandıktan sonra bu rehberi takip ederek sistemi test edin!**