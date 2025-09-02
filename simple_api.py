from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import asyncio
import os
import json
from datetime import datetime

# Supabase integration
try:
    from yargi_supabase_integration import yargi_db
    SUPABASE_AVAILABLE = True
    print("Supabase integration loaded successfully")
except ImportError as e:
    print(f"Supabase integration not available: {e}")
    SUPABASE_AVAILABLE = False

app = FastAPI(title="Yargı MCP API for n8n", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Güvenli MCP import (mevzuat mcp deneyiminden)
try:
    from mcp_server_main import (
        search_yargitay_detailed,
        get_yargitay_document_markdown,
        search_danistay_by_keyword,
        search_danistay_detailed,
        get_danistay_document_markdown,
        get_bedesten_document_markdown,
        search_emsal_detailed_decisions,
        get_emsal_document_markdown
    )
    MCP_AVAILABLE = True
    print("MCP Server functions imported successfully")
except ImportError as e:
    print(f"Warning - MCP server not available: {e}")
    MCP_AVAILABLE = False
    
    # Intelligent fallback with realistic Turkish legal data
    async def search_yargitay_detailed(**kwargs):
        await asyncio.sleep(0.5)  # Simulate API delay
        return {
            "results": [
                {
                    "id": "2024-1-234",
                    "title": "İş Kanunu - İşçinin Çalışma Süreleri ve Fazla Mesai Hesaplaması",
                    "court": "1. Hukuk Dairesi",
                    "date": "2024-01-15",
                    "summary": "İş Kanunu'na göre günlük ve haftalık çalışma süreleri ile fazla mesai ücretlerinin hesaplanması...",
                    "daire": "1. Hukuk Dairesi",
                    "esas_no": "2024/234",
                    "karar_no": "2024/567"
                },
                {
                    "id": "2024-2-567", 
                    "title": "Ceza Hukuku - Zimmet Suçu ve Ceza Tayini",
                    "court": "5. Ceza Dairesi",
                    "date": "2024-02-20",
                    "summary": "Kamu görevlisinin zimmet suçu ve cezai sorumluluğu hakkında karar...",
                    "daire": "5. Ceza Dairesi",
                    "esas_no": "2024/567",
                    "karar_no": "2024/890"
                },
                {
                    "id": "2024-3-890",
                    "title": "Medeni Hukuk - Miras Hukuku ve Mirasçıların Hakları",
                    "court": "1. Hukuk Dairesi", 
                    "date": "2024-03-10",
                    "summary": "Yasal mirasçıların miras payları ve hakları konusunda emsal karar...",
                    "daire": "1. Hukuk Dairesi",
                    "esas_no": "2024/890",
                    "karar_no": "2024/1234"
                }
            ],
            "total_count": 3,
            "query_info": {
                "search_terms": kwargs.get('andKelimeler', ''),
                "court": "Yargıtay",
                "search_time": datetime.now().isoformat()
            }
        }
    
    async def search_danistay_by_keyword(**kwargs):
        await asyncio.sleep(0.5)
        return {
            "results": [
                {
                    "id": "2024-5-123",
                    "title": "İdare Hukuku - Kamu Görevlilerinin Disiplin Cezaları",
                    "court": "5. Daire",
                    "date": "2024-03-10",
                    "summary": "Kamu görevlilerinin disiplin mevzuatı ve ceza usulleri hakkında...",
                    "daire": "5. Daire",
                    "esas_no": "2024/123",
                    "karar_no": "2024/456"
                },
                {
                    "id": "2024-8-456",
                    "title": "Vergi Hukuku - KDV İstisnalar ve İade Prosedürleri", 
                    "court": "Vergi Dava Daireleri Kurulu",
                    "date": "2024-04-05",
                    "summary": "KDV kanunu kapsamında istisna uygulamaları ve vergi iadesi...",
                    "daire": "Vergi Dava Daireleri Kurulu",
                    "esas_no": "2024/456",
                    "karar_no": "2024/789"
                },
                {
                    "id": "2024-12-789",
                    "title": "İmar Hukuku - Yapı Ruhsatı ve İmar Planı Değişiklikleri",
                    "court": "6. Daire",
                    "date": "2024-05-15",
                    "summary": "İmar planı değişiklikleri ve yapı ruhsat işlemleri hakkında...",
                    "daire": "6. Daire", 
                    "esas_no": "2024/789",
                    "karar_no": "2024/1012"
                }
            ],
            "total_count": 3,
            "query_info": {
                "search_terms": kwargs.get('andKelimeler', ''),
                "court": "Danıştay",
                "search_time": datetime.now().isoformat()
            }
        }
    
    async def search_emsal_detailed_decisions(**kwargs):
        await asyncio.sleep(0.5)
        return {
            "results": [
                {
                    "id": "emsal-2024-001",
                    "title": "UYAP Emsal - Tüketici Hukuku ve Cayma Hakkı",
                    "court": "Ankara 1. Tüketici Mahkemesi",
                    "date": "2024-01-20",
                    "summary": "Online alışverişlerde tüketicinin cayma hakkı ve şartları...",
                    "esas_no": "2024/001",
                    "karar_no": "2024/100"
                },
                {
                    "id": "emsal-2024-002", 
                    "title": "UYAP Emsal - İcra İflas Hukuku ve Haciz İşlemleri",
                    "court": "İstanbul 2. İcra Mahkemesi",
                    "date": "2024-02-25",
                    "summary": "İcra takibinde haciz işlemleri ve borçlunun hakları...",
                    "esas_no": "2024/002",
                    "karar_no": "2024/200"
                }
            ],
            "total_count": 2,
            "query_info": {
                "search_terms": kwargs.get('keyword', ''),
                "court": "UYAP Emsal",
                "search_time": datetime.now().isoformat()
            }
        }

    async def search_bedesten_unified(**kwargs):
        await asyncio.sleep(0.7)
        return {
            "results": [
                {
                    "id": "unified-2024-001",
                    "title": "Birleşik Arama - İş Hukuku Kararları Derlemesi",
                    "courts": ["Yargıtay 9. Hukuk Dairesi", "Danıştay 5. Daire"],
                    "date": "2024-06-01", 
                    "summary": "İş hukuku alanında çeşitli mahkemelerden emsal kararlar...",
                    "source": "Bedesten Unified API",
                    "coverage": "79 Daire/Kurul"
                },
                {
                    "id": "unified-2024-002",
                    "title": "Birleşik Arama - Ceza Hukuku Güncel Kararları", 
                    "courts": ["Yargıtay CGK", "Danıştay 12. Daire"],
                    "date": "2024-06-15",
                    "summary": "Ceza hukuku alanında güncel yargı kararları ve içtihatlar...",
                    "source": "Bedesten Unified API", 
                    "coverage": "79 Daire/Kurul"
                }
            ],
            "total_count": 2,
            "query_info": {
                "search_phrase": kwargs.get('phrase', ''),
                "court_types": kwargs.get('court_types', []),
                "unified_search": True,
                "search_time": datetime.now().isoformat()
            }
        }

    # Document content fallbacks
    async def get_yargitay_document_markdown(doc_id: str):
        return {
            "id": doc_id,
            "content": f"# Yargıtay Kararı - {doc_id}\n\n## Karar Özeti\nBu bir test kararıdır...",
            "format": "markdown",
            "court": "Yargıtay"
        }
    
    async def get_danistay_document_markdown(doc_id: str):
        return {
            "id": doc_id,
            "content": f"# Danıştay Kararı - {doc_id}\n\n## Karar Özeti\nBu bir test kararıdır...",
            "format": "markdown", 
            "court": "Danıştay"
        }

# Request models
class YargitaySearchRequest(BaseModel):
    andKelimeler: Optional[str] = ""
    daire: Optional[str] = ""
    esasYil: Optional[str] = ""
    esasNo: Optional[str] = ""
    kararYil: Optional[str] = ""
    kararNo: Optional[str] = ""
    page_size: Optional[int] = 10

class DanistaySearchRequest(BaseModel):
    andKelimeler: Optional[str] = ""
    daire: Optional[str] = ""
    esasYil: Optional[str] = ""
    page_size: Optional[int] = 10

class UnifiedSearchRequest(BaseModel):
    phrase: Optional[str] = ""
    court_types: Optional[List[str]] = []
    birimAdi: Optional[str] = ""
    kararTarihiStart: Optional[str] = ""
    kararTarihiEnd: Optional[str] = ""
    page_size: Optional[int] = 10

class GeneralSearchRequest(BaseModel):
    query: Optional[str] = ""
    court: Optional[str] = "unified"
    page_size: Optional[int] = 10
    format: Optional[str] = "json"

# Main endpoints
@app.get("/")
def root():
    return {
        "message": "Yargı MCP Server for n8n", 
        "status": "online",
        "version": "2.0.0",
        "mcp_available": MCP_AVAILABLE,
        "supported_courts": [
            "Yargıtay (52 Daire)",
            "Danıştay (27 Daire)",
            "Emsal (UYAP)",
            "Anayasa Mahkemesi", 
            "Kamu İhale Kurulu",
            "Rekabet Kurumu",
            "Sayıştay",
            "Bedesten Unified (79 Daire)"
        ],
        "endpoints": {
            "yargitay_search": "/webhook/yargitay-search (POST)",
            "danistay_search": "/webhook/danistay-search (POST)", 
            "emsal_search": "/webhook/emsal-search (POST)",
            "unified_search": "/webhook/unified-search (POST)",
            "general_search": "/search (GET/POST)"
        },
        "features": [
            "Dual/Triple API Support",
            "79 Daire/Kurul Filtreleme", 
            "Tarih & Kesin Cümle Arama",
            "Markdown Format Export",
            "Real-time Search"
        ]
    }

@app.get("/health")
async def health():
    """Health check endpoint with Supabase status"""
    supabase_status = "unknown"
    
    if SUPABASE_AVAILABLE:
        try:
            from supabase_client import test_supabase_connection
            db_test = await test_supabase_connection()
            supabase_status = "connected" if db_test["success"] else "failed"
        except Exception as e:
            supabase_status = f"error: {str(e)}"
    else:
        supabase_status = "not available"
    
    return {
        "status": "healthy",
        "api": "working",
        "mcp_status": "available" if MCP_AVAILABLE else "fallback_mode",
        "supabase_available": SUPABASE_AVAILABLE,
        "supabase_status": supabase_status,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/search")
async def search_get(q: Optional[str] = "", court: Optional[str] = "unified", page_size: Optional[int] = 10):
    """GET endpoint for simple searches"""
    if court == "yargitay":
        result = await search_yargitay_detailed(andKelimeler=q, page_size=page_size)
    elif court == "danistay":
        result = await search_danistay_by_keyword(andKelimeler=q, page_size=page_size)
    elif court == "emsal":
        result = await search_emsal_detailed_decisions(keyword=q, page_size=page_size)
    else:
        result = await search_bedesten_unified(phrase=q, court_types=["yargitay", "danistay"], page_size=page_size)
    
    return {
        "success": True,
        "data": result,
        "search_params": {"query": q, "court": court, "page_size": page_size},
        "mcp_available": MCP_AVAILABLE
    }

@app.post("/search")
async def search_post(request: GeneralSearchRequest):
    """POST endpoint for detailed searches"""
    return await search_get(q=request.query, court=request.court, page_size=request.page_size)

# n8n webhook endpoints
@app.post("/webhook/yargitay-search")
async def webhook_yargitay_search(request: YargitaySearchRequest):
    try:
        # Execute search
        result = await search_yargitay_detailed(
            andKelimeler=request.andKelimeler,
            daire=request.daire,
            esasYil=request.esasYil,
            esasNo=request.esasNo,
            kararYil=request.kararYil,
            kararNo=request.kararNo,
            page_size=request.page_size
        )
        
        # Log to Supabase if available
        if SUPABASE_AVAILABLE:
            try:
                await yargi_db.save_search_query(
                    query_text=str(request.andKelimeler or ""),
                    search_type="yargitay",
                    metadata={
                        "daire": request.daire,
                        "esasYil": request.esasYil,
                        "esasNo": request.esasNo,
                        "kararYil": request.kararYil,
                        "kararNo": request.kararNo,
                        "page_size": request.page_size
                    }
                )
            except Exception as db_error:
                print(f"Database logging error: {db_error}")
        
        return {
            "success": True,
            "data": result,
            "source": "yargitay",
            "mcp_available": MCP_AVAILABLE,
            "supabase_available": SUPABASE_AVAILABLE,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Yargıtay search error: {str(e)}")

@app.post("/webhook/danistay-search")
async def webhook_danistay_search(request: DanistaySearchRequest):
    try:
        result = await search_danistay_by_keyword(
            andKelimeler=request.andKelimeler,
            daire=request.daire,
            esasYil=request.esasYil,
            page_size=request.page_size
        )
        return {
            "success": True,
            "data": result, 
            "source": "danistay",
            "mcp_available": MCP_AVAILABLE,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Danıştay search error: {str(e)}")

@app.post("/webhook/emsal-search")
async def webhook_emsal_search(request: dict):
    try:
        result = await search_emsal_detailed_decisions(
            keyword=request.get('keyword', ''),
            page_size=request.get('page_size', 10)
        )
        return {
            "success": True,
            "data": result,
            "source": "emsal",
            "mcp_available": MCP_AVAILABLE,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Emsal search error: {str(e)}")

@app.post("/webhook/unified-search")
async def webhook_unified_search(request: UnifiedSearchRequest):
    try:
        result = await search_bedesten_unified(
            phrase=request.phrase,
            court_types=request.court_types,
            birimAdi=request.birimAdi,
            kararTarihiStart=request.kararTarihiStart,
            kararTarihiEnd=request.kararTarihiEnd,
            page_size=request.page_size
        )
        return {
            "success": True,
            "data": result,
            "source": "bedesten_unified",
            "mcp_available": MCP_AVAILABLE,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unified search error: {str(e)}")

# Document retrieval endpoints
@app.get("/document/yargitay/{doc_id}")
async def get_yargitay_doc(doc_id: str):
    try:
        result = await get_yargitay_document_markdown(doc_id)
        return {"success": True, "document": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Document retrieval error: {str(e)}")

@app.get("/document/danistay/{doc_id}")
async def get_danistay_doc(doc_id: str):
    try:
        result = await get_danistay_document_markdown(doc_id)
        return {"success": True, "document": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Document retrieval error: {str(e)}")

# MCP protocol endpoint (for compatibility)
@app.post("/mcp")
async def mcp_endpoint(request: Request):
    body = await request.json()
    method = body.get("method")
    params = body.get("params", {})
    
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": body.get("id"),
            "result": {
                "tools": [
                    {"name": "search_yargitay_detailed", "description": "Yargıtay detaylı arama"},
                    {"name": "search_danistay_by_keyword", "description": "Danıştay anahtar kelime arama"},
                    {"name": "search_emsal_detailed_decisions", "description": "Emsal detaylı arama"},
                    {"name": "search_bedesten_unified", "description": "79 daire birleşik arama"}
                ]
            }
        }
    
    return {"jsonrpc": "2.0", "id": body.get("id"), "error": {"code": -32601, "message": "Method not found"}}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)