# TurkLawAI.com Deployment Rehberi

**Güncelleme Tarihi:** 2025-09-08 17:10:11

## Hızlı Başlangıç

### 1. Yargi-MCP Backend
```bash
# Kurulum
pip install yargi-mcp

# Çalıştırma
yargi-mcp
```

### 2. TurkLawAI Integration
```bash
# Bağımlılıkları kur
pip install -r requirements.txt

# Integration server'ı başlat
python turklawai_integration.py
```

## Production Deployment

### Fly.io Deployment
```bash
# Fly.io'ya deploy
fly deploy

# Status kontrolü
fly status

# Health check
curl https://api.yargimcp.com/health
```

### Environment Variables
```bash
CLERK_SECRET_KEY=sk_live_...
CLERK_PUBLISHABLE_KEY=pk_live_...
SUPABASE_URL=https://...
SUPABASE_ANON_KEY=eyJ...
```

## Monitoring

### Health Checks
- **Backend:** https://api.yargimcp.com/health
- **MCP Tools:** 21 aktif tool
- **Database:** Supabase connection
- **Authentication:** Clerk OAuth

### Performance Metrics
- **Response Time:** <2s average
- **Uptime:** >99.5%
- **Token Efficiency:** 56.8% optimized
- **Error Rate:** <1%

