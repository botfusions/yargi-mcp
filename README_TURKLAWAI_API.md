# 🏛️ TurkLawAI MCP Server API

**Version 2.0.0** - Complete Turkish Legal Search API with Authentication & Subscription Management

## 🎯 Overview

TurkLawAI MCP Server transforms MCP (Model Context Protocol) legal search tools into a production-ready HTTP API for the TurkLawAI.com platform. It provides authenticated access to Turkish court decisions and legislation with subscription-based rate limiting.

## ✨ Features

- **Turkish Legal Search**: Access to 192K+ court decisions and 19K+ legislation documents
- **Multi-Court Support**: Yargıtay, Danıştay, Emsal, and more
- **Complete Legislation Database**: Full-text search in Turkish legislation
- **Authentication & Authorization**: JWT-based authentication with subscription tiers
- **Rate Limiting**: Subscription-based quota management
- **Usage Analytics**: Complete API usage tracking
- **CORS Support**: Cross-origin resource sharing for web platforms

## 🏗️ Architecture

### Supported Legal Sources

| Court/Institution | Documents | Status | Endpoint |
|-------------------|-----------|---------|----------|
| **Yargıtay** (Supreme Court) | 192,289+ decisions | ✅ Available | `/api/search/yargitay` |
| **Danıştay** (Council of State) | Available | ⚠️ Fallback | `/api/search/danistay` |
| **Emsal** (UYAP) | Available | ⚠️ Fallback | `/api/document/emsal/{id}` |
| **Mevzuat** (Legislation) | 19,706+ documents | ✅ Available | `/api/search/mevzuat` |

### Subscription Tiers

| Plan | Price/Month | Requests/Month | Rate Limit |
|------|-------------|----------------|------------|
| **Free** | $0 | 100 | 5/min |
| **Basic** | $29.99 | 1,000 | 20/min |
| **Professional** | $99.99 | 5,000 | 60/min |
| **Enterprise** | $299.99 | 25,000+ | 200/min |

## 🚀 Quick Start

### Prerequisites

```bash
# Required dependencies
pip install fastapi uvicorn python-multipart
pip install python-jose[cryptography] pydantic

# MCP modules (should be in same directory)
# yargi-mcp/ and mevzuat-mcp/ directories
```

### Environment Configuration

Create `.env` file:

```bash
# Subscription System
ENABLE_SUBSCRIPTION_SYSTEM=false  # Set to true for production

# JWT Configuration
JWT_SECRET_KEY=your-super-secret-jwt-key-for-turklawai-min-64-chars-long

# Supabase Database
SUPABASE_URL=https://your-supabase-url.com
SUPABASE_ANON_KEY=your-supabase-anon-key

# CORS Configuration
ALLOWED_ORIGINS=http://localhost:3000,https://turklawai.com
```

### Start the Server

```bash
# Development (port 8002)
python turklawai_mcp_server.py

# Production with Uvicorn
uvicorn turklawai_mcp_server:app --host 0.0.0.0 --port 8002
```

## 📚 API Documentation

### Base URL
```
http://localhost:8002  # Development
https://api.turklawai.com  # Production
```

### Health & Status Endpoints

#### GET `/health`
Check service health and availability.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-09-02T07:44:00.110Z",
  "services": {
    "supabase": "connected",
    "yargi_mcp": "available",
    "mevzuat_mcp": "available",
    "authentication": "disabled"
  }
}
```

#### GET `/`
Service information and features.

### Authentication

#### GET `/user/profile`
Get current user's subscription and usage information.

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Response:**
```json
{
  "user_id": "user_123",
  "email": "user@example.com",
  "plan": "professional",
  "usage": {
    "requests_used": 45,
    "requests_limit": 5000,
    "usage_percentage": 0.9
  }
}
```

### Court Decision Search

#### POST `/api/search/yargitay`
Search Yargıtay (Supreme Court) decisions.

**Request Body:**
```json
{
  "andKelimeler": "hukuk mülkiyet",
  "daire": "1. Hukuk Dairesi",
  "esasYil": "2024",
  "esasNo": "123",
  "kararYil": "2024", 
  "kararNo": "456",
  "page_size": 10
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "results": [
      {
        "kararNo": "2024/3463",
        "birimYrgKurulDaire": "1. Hukuk Dairesi",
        "kararTarihi": "2024-08-15",
        "esasNo": "2024/1234"
      }
    ],
    "total_count": 192289,
    "current_page": 1,
    "page_size": 10
  },
  "user": {
    "plan": "free",
    "authenticated": true
  },
  "meta": {
    "response_time_ms": 512,
    "timestamp": "2025-09-02T07:44:00.110Z"
  }
}
```

#### POST `/api/search/danistay`
Search Danıştay (Council of State) decisions.

### Document Retrieval

#### GET `/api/document/{document_type}/{document_id}`
Get full document content in Markdown format.

**Parameters:**
- `document_type`: yargitay, danistay, emsal
- `document_id`: Document identifier from search results

### Turkish Legislation

#### POST `/api/search/mevzuat`
Search Turkish legislation and regulations.

**Request Body:**
```json
{
  "mevzuat_adi": "medeni kanun",
  "phrase": "mülkiyet hakkı", 
  "mevzuat_no": "4721",
  "mevzuat_turleri": "[\"KANUN\", \"YONETMELIK\"]",
  "page_size": 10,
  "sort_field": "RESMI_GAZETE_TARIHI",
  "sort_direction": "desc"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "documents": [
      {
        "mevzuat_id": "343829",
        "mevzuat_adi": "Türk Medeni Kanunu",
        "mevzuat_no": "4721",
        "mevzuat_tur": "KANUN",
        "resmi_gazete_tarihi": "2001-12-08"
      }
    ],
    "total_results": 19706,
    "current_page": 1,
    "page_size": 10
  }
}
```

#### GET `/api/mevzuat/{mevzuat_id}/articles`
Get article tree (table of contents) for legislation.

#### GET `/api/mevzuat/{mevzuat_id}/article/{madde_id}`
Get specific article content in Markdown.

## 🔧 Development

### Testing with curl

```bash
# Health check
curl http://localhost:8002/health

# Search Yargıtay
curl -X POST http://localhost:8002/api/search/yargitay \
  -H "Content-Type: application/json" \
  -d '{"andKelimeler": "hukuk", "page_size": 3}'

# Search Mevzuat
curl -X POST http://localhost:8002/api/search/mevzuat \
  -H "Content-Type: application/json" \
  -d '{"mevzuat_adi": "medeni kanun", "page_size": 5}'
```

### Postman Collection

Import `TurkLawAI_API.postman_collection.json` for complete API testing with pre-configured requests.

## 🔐 Authentication (Production)

### Enable Authentication
Set `ENABLE_SUBSCRIPTION_SYSTEM=true` in `.env`.

### JWT Token Format
```json
{
  "sub": "user_id",
  "email": "user@example.com",
  "exp": 1699123456
}
```

### Protected Endpoints
When authentication is enabled, all `/api/` endpoints require:
```
Authorization: Bearer <jwt_token>
```

## 📊 Rate Limiting

Rate limits are enforced per user based on subscription plan:

- **Per-minute limits**: Prevent API abuse
- **Monthly quotas**: Subscription-based limits
- **Usage tracking**: Complete analytics for billing

Rate limit exceeded response:
```json
{
  "detail": "Rate limit exceeded. Please upgrade your plan or wait for the next billing period."
}
```

## 🎯 Performance

### Response Times (Typical)
- **Health check**: ~50ms
- **Yargıtay search**: ~500ms
- **Mevzuat search**: ~300ms
- **Document retrieval**: ~400ms

### Capacity
- **Concurrent requests**: 100+
- **Database records**: 200K+ legal documents
- **Search accuracy**: Full-text and metadata search

## 🐛 Troubleshooting

### Common Issues

**Import Errors:**
```
Warning - Yargi MCP clients not available
```
- Ensure `yargi-mcp/` and `mevzuat-mcp/` directories are accessible
- Check Python path and module imports

**Authentication Errors:**
```json
{"detail": "Authentication required"}
```
- Set `ENABLE_SUBSCRIPTION_SYSTEM=false` for testing
- Provide valid JWT token in Authorization header

**Rate Limit Errors:**
- Check user subscription plan and usage
- Upgrade subscription or wait for next billing period

### Fallback Mode

When MCP modules are unavailable, the API runs in fallback mode with sample data:

```json
{
  "results": [
    {
      "id": "fallback-001", 
      "title": "Test Data - Fallback Mode",
      "court": "Test Data"
    }
  ]
}
```

## 📈 Monitoring

### Logs
- **File**: `logs/mcp_server.log`
- **Console**: INFO level
- **Format**: Structured JSON logs

### Analytics
All API calls are logged to Supabase with:
- User ID and endpoint
- Response time and success status
- Query parameters for analytics

## 🚀 Deployment

### Docker (Recommended)
```dockerfile
FROM python:3.11
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
EXPOSE 8002
CMD ["python", "turklawai_mcp_server.py"]
```

### Production Checklist
- [ ] Set `ENABLE_SUBSCRIPTION_SYSTEM=true`
- [ ] Configure production JWT secret
- [ ] Setup Supabase production database
- [ ] Configure CORS for your domain
- [ ] Enable SSL/HTTPS
- [ ] Setup monitoring and logging

## 📄 License

This API server is part of the TurkLawAI.com platform. For licensing and usage terms, please contact the development team.

## 🤝 Support

For issues, feature requests, or questions:
- **GitHub Issues**: [Create an issue]
- **Documentation**: Full API docs at `/docs` (FastAPI auto-generated)
- **Email**: Contact the TurkLawAI team

---

**Built with ❤️ for Turkish Legal Research**  
*Democratizing access to legal information through technology*