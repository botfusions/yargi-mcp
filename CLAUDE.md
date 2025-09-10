# CLAUDE.md

FastMCP server providing access to Turkish legal databases through Model Context Protocol (MCP).

## Project Overview

**🎯 OPTIMIZED**: 56.8% token reduction (14,061→6,073 tokens), 19 active tools across 9 legal institutions  
**✅ PRODUCTION**: Deployed on Fly.io with OAuth 2.0, JWT authentication, Claude AI integration

## Key Commands

### Installation
```bash
# Production (recommended)
pip install yargi-mcp
yargi-mcp

# Development
uv sync
uv run mcp_server_main.py

# ASGI Web Service
uvicorn asgi_app:app --host 0.0.0.0 --port 8000
```

### Testing
```bash
# Quick tests
uv run test_core_tools_quick.py
uv run test_kik_client.py

# HTTP testing
curl -X POST http://127.0.0.1:8000/mcp/ \
  -H "Content-Type: application/json" \
  -H "Session-ID: test" \
  -d '{"jsonrpc": "2.0", "method": "tools/list", "id": 1}'
```

## Optimization Summary

**Results**: 14,061 → 6,073 tokens (56.8% reduction), 30 → 19 active tools

**Key Changes**:
- Unified tools: Bedesten (5→2), Constitutional (4→2), Sayıştay (6→2)  
- Simplified parameters: `Optional[str] = Field(None)` → `str = Field("")`
- Deactivated redundant primary APIs (Bedesten unified covers all functionality)

## Architecture

### Core Structure
- **mcp_server_main.py**: Main server entry point, defines 19 MCP tools
- **{module}_mcp_module/**: Each legal database module (client.py, models.py)

### Legal Databases (19 Active Tools)
1. **Bedesten**: Unified API for Yargıtay, Danıştay, local courts (2 tools)
2. **Emsal**: UYAP precedent decisions (2 tools)  
3. **Uyuşmazlık**: Jurisdictional disputes (2 tools)
4. **Anayasa**: Constitutional Court unified (2 tools)
5. **KİK**: Public procurement (2 tools)
6. **Rekabet**: Competition Authority (2 tools)  
7. **KVKK**: Data protection via Brave API (2 tools)
8. **BDDK**: Banking regulation via Tavily API (2 tools)
9. **Sayıştay**: Court of Accounts unified (3 tools)

### Key Patterns
- **FastMCP Framework**: Async HTTP clients, Pydantic models
- **HTML→Markdown**: BytesIO optimization, 5K character pagination
- **Empty String Defaults**: Optimized for token efficiency

### Search Tools Usage

**Bedesten Unified API** (Primary - Active):
- **Court types**: `["YARGITAYKARARI"]`, `["DANISTAYKARAR"]`, `["YERELHUKUK"]`, `["ISTINAFHUKUK"]`, `["KYB"]`
- **Exact phrases**: `phrase="\"mülkiyet kararı\""` (precise matching)
- **Boolean operators**: AND, OR, NOT, +term, -term 
- **Chamber filtering**: 49 Yargıtay + 27 Danıştay chambers
- **Date filtering**: ISO 8601 format (`kararTarihiStart`/`kararTarihiEnd`)

**Note**: Primary Yargıtay/Danıştay APIs deactivated for token optimization - use Bedesten unified instead.

### Specialized APIs

**Sayıştay (Court of Accounts)** - Unified search for audit decisions:
- General Assembly, Appeals Board, Chamber decisions
- Filter by chamber, year, administration type

**KVKK (Data Protection)** - Via Brave Search API:
- Turkish GDPR equivalent decisions  
- Site-targeted search: `site:kvkk.gov.tr`
- Paginated Markdown conversion (5K chunks)

**BDDK (Banking Regulation)** - Via Tavily API:
- Banking licenses, payment services, crypto guidance
- URL filtering: `bddk.org.tr/Mevzuat/DokumanGetir`

## Usage Examples

```python
# Multi-court search via Bedesten unified
await search_bedesten_unified(
    phrase="\"mülkiyet hakkı\"",  # Exact phrase
    court_types=["YARGITAYKARARI", "DANISTAYKARAR"],
    birimAdi="1. Hukuk Dairesi",
    kararTarihiStart="2024-01-01T00:00:00.000Z"
)

# Specialized searches
await search_kvkk_decisions(keywords="açık rıza")
await search_sayistay_unified(decision_type="genel_kurul")
await search_rekabet_kurumu_decisions(KararTuru="Birleşme")
```

## Configuration

### Dependencies
- **fastmcp**: MCP server framework
- **httpx, pydantic**: Async HTTP, data validation  
- **markitdown[pdf], playwright**: Document conversion, browser automation

### Environment
- Python 3.11+ required
- Optional: `BRAVE_API_TOKEN` for KVKK search (fallback available)

### Authentication
**Production**: Clerk OAuth 2.0 + JWT Bearer tokens  
**Cross-origin**: `yargimcp.com` → `api.yargimcp.com`

```bash
# Environment setup
ENABLE_AUTH=true
CLERK_SECRET_KEY=sk_live_xxx
CLERK_PUBLISHABLE_KEY=pk_live_xxx
```

## Production Deployment

**Status**: ✅ Fully operational on Fly.io
- **URL**: https://api.yargimcp.com
- **Authentication**: OAuth 2.0 + Bearer JWT working
- **Tools**: All 19 tools integrated with Claude AI

### Quick Deploy
```bash
# Deploy to Fly.io
fly deploy

# Check status  
curl https://api.yargimcp.com/health
```

### Endpoints
- **MCP (HTTP)**: https://api.yargimcp.com/mcp/
- **MCP (SSE)**: https://api.yargimcp.com/sse/  
- **OAuth**: https://api.yargimcp.com/auth/login
- **Health**: https://api.yargimcp.com/health

## Development Notes

**Testing Strategy**: 
1. Individual API clients: `uv run test_kik_client.py`
2. FastMCP integration: In-memory client testing
3. HTTP via curl: JSON-RPC format testing

**Search Features**:
- **Date filtering**: ISO 8601 format (`YYYY-MM-DDTHH:MM:SS.000Z`)
- **Exact phrases**: `phrase="\"mülkiyet kararı\""` vs `phrase="mülkiyet kararı"`
- **Boolean operators**: AND, OR, NOT, +required, -excluded
- **Pagination**: Configurable page size and number

## Summary

**Current Status**: ✅ Production ready with 19 optimized tools across 9 Turkish legal institutions  

**Tool Architecture**:
1. **Bedesten Unified**: 2 tools (covers Yargıtay, Danıştay, local courts)  
2. **Emsal, Uyuşmazlık, KİK, Rekabet**: 2 tools each (search + document)
3. **Constitutional Court**: 2 unified tools (norm control + individual applications)
4. **KVKK, BDDK**: 2 tools each (via Brave/Tavily APIs)
5. **Sayıştay**: 3 tools (unified audit decisions)

**Key Features**:
- **56.8% token optimization**: 14,061 → 6,073 tokens
- **Production deployment**: https://api.yargimcp.com with OAuth 2.0  
- **Claude AI integration**: All tools verified working
- **PyPI published**: `pip install yargi-mcp`
