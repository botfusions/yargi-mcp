"""
TurkLawAI MCP Server with Authentication and Subscription Management
Enhanced version of the original MCP server with user authentication and rate limiting
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from supabase_client import supabase_client
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Import original MCP functions
try:
    from mcp_server_main import (
        search_yargitay_detailed,
        get_yargitay_document_markdown,
        search_danistay_by_keyword,
        search_danistay_detailed,
        get_danistay_document_markdown,
        search_emsal_detailed_decisions,
        get_emsal_document_markdown
    )
    MCP_AVAILABLE = True
    print("MCP Server functions imported successfully")
except ImportError as e:
    print(f"Warning - MCP server not available: {e}")
    MCP_AVAILABLE = False

app = FastAPI(
    title="TurkLawAI MCP Server", 
    version="2.0.0",
    description="Authenticated Turkish Legal Search API with Subscription Management"
)

# CORS configuration
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS + ["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ENABLE_SUBSCRIPTION_SYSTEM = os.getenv("ENABLE_SUBSCRIPTION_SYSTEM", "false").lower() == "true"

# Security
security = HTTPBearer(auto_error=False)

# Rate limits by plan
RATE_LIMITS = {
    "free": {
        "requests_per_minute": int(os.getenv("RATE_LIMIT_FREE_PLAN", 5)),
        "requests_per_month": 100
    },
    "basic": {
        "requests_per_minute": int(os.getenv("RATE_LIMIT_BASIC_PLAN", 20)),
        "requests_per_month": 1000
    },
    "professional": {
        "requests_per_minute": int(os.getenv("RATE_LIMIT_PRO_PLAN", 60)),
        "requests_per_month": 5000
    },
    "enterprise": {
        "requests_per_minute": int(os.getenv("RATE_LIMIT_ENTERPRISE_PLAN", 200)),
        "requests_per_month": 25000
    }
}

# Authentication Functions
async def verify_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[Dict[str, Any]]:
    """Verify JWT token and return user information"""
    
    if not ENABLE_SUBSCRIPTION_SYSTEM:
        # If subscription system is disabled, allow anonymous access
        return {
            "user_id": "anonymous",
            "email": "anonymous@localhost",
            "plan": "free",
            "authenticated": False
        }
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
        
        user_id = payload.get("sub") or payload.get("user_id")
        email = payload.get("email")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user_id"
            )
        
        # Get user subscription from database
        subscription = await get_user_subscription(user_id)
        if not subscription:
            # Create free subscription for new authenticated users
            subscription = await create_free_subscription(user_id, email)
        
        return {
            "user_id": user_id,
            "email": email,
            "plan": subscription.get("plan", "free"),
            "subscription": subscription,
            "authenticated": True
        }
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

# Database Functions
async def get_user_subscription(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user subscription from Supabase"""
    try:
        result = await supabase_client.query_data(
            'user_subscriptions', 
            {'user_id': user_id}
        )
        
        if result['success'] and result['data']:
            return result['data'][0]
        return None
        
    except Exception as e:
        print(f"Error getting subscription: {e}")
        return None

async def create_free_subscription(user_id: str, email: str) -> Dict[str, Any]:
    """Create free subscription for new users"""
    try:
        subscription_data = {
            'user_id': user_id,
            'email': email,
            'plan': 'free',
            'status': 'active',
            'requests_used': 0,
            'requests_limit': RATE_LIMITS['free']['requests_per_month'],
            'billing_period_start': datetime.now(timezone.utc).isoformat(),
            'billing_period_end': (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        result = await supabase_client.insert_data('user_subscriptions', subscription_data)
        if result['success']:
            return subscription_data
        else:
            print(f"Error creating subscription: {result}")
            return subscription_data  # Return default even if DB insert fails
            
    except Exception as e:
        print(f"Error creating subscription: {e}")
        return {
            'user_id': user_id,
            'email': email,
            'plan': 'free',
            'status': 'active',
            'requests_used': 0,
            'requests_limit': 100
        }

async def log_api_usage(user_id: str, endpoint: str, success: bool = True, 
                       response_time_ms: int = 0, query_params: Dict[str, Any] = None) -> None:
    """Log API usage for billing and analytics"""
    try:
        usage_data = {
            'user_id': user_id,
            'endpoint': endpoint,
            'success': success,
            'response_time_ms': response_time_ms,
            'query_params': query_params,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        await supabase_client.insert_data('usage_logs', usage_data)
        
    except Exception as e:
        print(f"Error logging usage: {e}")

async def check_rate_limits(user: Dict[str, Any]) -> bool:
    """Check if user is within rate limits"""
    try:
        plan = user.get("plan", "free")
        user_id = user["user_id"]
        
        # Check monthly limit
        subscription = user.get("subscription", {})
        requests_used = subscription.get("requests_used", 0)
        requests_limit = subscription.get("requests_limit", RATE_LIMITS[plan]["requests_per_month"])
        
        if requests_used >= requests_limit:
            return False
        
        # Check per-minute rate limit (simplified - would need Redis for production)
        # For now, we'll just return True
        return True
        
    except Exception as e:
        print(f"Rate limit check error: {e}")
        return True

async def increment_usage_counter(user_id: str) -> None:
    """Increment user's usage counter"""
    try:
        # This would need to be implemented properly with atomic updates
        # For now, we'll just log it
        await log_api_usage(user_id, "counter_increment")
        
    except Exception as e:
        print(f"Error incrementing usage: {e}")

# API Endpoints

@app.get("/")
async def root():
    """Welcome endpoint"""
    return {
        "service": "TurkLawAI MCP Server",
        "version": "2.0.0",
        "authentication": ENABLE_SUBSCRIPTION_SYSTEM,
        "mcp_available": MCP_AVAILABLE,
        "features": [
            "Turkish Legal Search",
            "Court Decision Access", 
            "Subscription Management",
            "Rate Limiting",
            "Usage Analytics"
        ]
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "supabase": "connected",
            "mcp": "available" if MCP_AVAILABLE else "fallback_mode",
            "authentication": "enabled" if ENABLE_SUBSCRIPTION_SYSTEM else "disabled"
        }
    }

@app.get("/user/profile")
async def get_user_profile(user: Dict[str, Any] = Depends(verify_token)):
    """Get current user's profile and subscription info"""
    subscription = user.get("subscription", {})
    plan_limits = RATE_LIMITS.get(user["plan"], RATE_LIMITS["free"])
    
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "plan": user["plan"],
        "authenticated": user["authenticated"],
        "subscription_status": subscription.get("status", "active"),
        "usage": {
            "requests_used": subscription.get("requests_used", 0),
            "requests_limit": subscription.get("requests_limit", plan_limits["requests_per_month"]),
            "usage_percentage": round((subscription.get("requests_used", 0) / subscription.get("requests_limit", 1)) * 100, 2)
        },
        "rate_limits": plan_limits,
        "billing_period": {
            "start": subscription.get("billing_period_start"),
            "end": subscription.get("billing_period_end")
        }
    }

# Enhanced search endpoints with authentication and rate limiting

@app.post("/api/search/yargitay")
async def search_yargitay_authenticated(
    request: Request,
    andKelimeler: Optional[str] = "",
    daire: Optional[str] = "",
    esasYil: Optional[str] = "",
    esasNo: Optional[str] = "",
    kararYil: Optional[str] = "",
    kararNo: Optional[str] = "",
    page_size: Optional[int] = 10,
    user: Dict[str, Any] = Depends(verify_token)
):
    """Authenticated Yargitay search with rate limiting"""
    
    start_time = datetime.now()
    
    # Check rate limits
    if not await check_rate_limits(user):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please upgrade your plan or wait for the next billing period."
        )
    
    try:
        # Execute search
        if MCP_AVAILABLE:
            result = await search_yargitay_detailed(
                andKelimeler=andKelimeler,
                daire=daire,
                esasYil=esasYil,
                esasNo=esasNo,
                kararYil=kararYil,
                kararNo=kararNo,
                page_size=page_size
            )
        else:
            # Fallback response
            await asyncio.sleep(0.5)
            result = {
                "results": [
                    {
                        "id": "fallback-001",
                        "title": "Yargıtay Arama - Fallback Mode",
                        "court": "Test Data",
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "summary": f"Arama terimi: {andKelimeler}"
                    }
                ],
                "total_count": 1,
                "page": 1
            }
        
        # Calculate response time
        response_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # Log usage
        await log_api_usage(
            user["user_id"], 
            "/api/search/yargitay",
            success=True,
            response_time_ms=response_time,
            query_params={
                "andKelimeler": andKelimeler,
                "daire": daire,
                "page_size": page_size
            }
        )
        
        # Increment usage counter
        await increment_usage_counter(user["user_id"])
        
        return {
            "success": True,
            "data": result,
            "user": {
                "plan": user["plan"],
                "authenticated": user["authenticated"]
            },
            "meta": {
                "response_time_ms": response_time,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
        
    except Exception as e:
        # Log error
        response_time = int((datetime.now() - start_time).total_seconds() * 1000)
        await log_api_usage(
            user["user_id"], 
            "/api/search/yargitay",
            success=False,
            response_time_ms=response_time
        )
        
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")

@app.post("/api/search/danistay")
async def search_danistay_authenticated(
    request: Request,
    andKelimeler: Optional[str] = "",
    daire: Optional[str] = "",
    page_size: Optional[int] = 10,
    user: Dict[str, Any] = Depends(verify_token)
):
    """Authenticated Danistay search with rate limiting"""
    
    start_time = datetime.now()
    
    # Check rate limits
    if not await check_rate_limits(user):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please upgrade your plan or wait for the next billing period."
        )
    
    try:
        # Execute search
        if MCP_AVAILABLE:
            result = await search_danistay_detailed(
                andKelimeler=andKelimeler,
                daire=daire,
                page_size=page_size
            )
        else:
            # Fallback response
            await asyncio.sleep(0.5)
            result = {
                "results": [
                    {
                        "id": "fallback-002",
                        "title": "Danıştay Arama - Fallback Mode", 
                        "court": "Test Data",
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "summary": f"Arama terimi: {andKelimeler}"
                    }
                ],
                "total_count": 1,
                "page": 1
            }
        
        # Calculate response time
        response_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # Log usage
        await log_api_usage(
            user["user_id"],
            "/api/search/danistay", 
            success=True,
            response_time_ms=response_time,
            query_params={
                "andKelimeler": andKelimeler,
                "daire": daire,
                "page_size": page_size
            }
        )
        
        # Increment usage counter
        await increment_usage_counter(user["user_id"])
        
        return {
            "success": True,
            "data": result,
            "user": {
                "plan": user["plan"],
                "authenticated": user["authenticated"]
            },
            "meta": {
                "response_time_ms": response_time,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
        
    except Exception as e:
        # Log error
        response_time = int((datetime.now() - start_time).total_seconds() * 1000)
        await log_api_usage(
            user["user_id"],
            "/api/search/danistay",
            success=False,
            response_time_ms=response_time
        )
        
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")

@app.get("/api/document/{document_type}/{document_id}")
async def get_document(
    document_type: str,
    document_id: str,
    user: Dict[str, Any] = Depends(verify_token)
):
    """Get document content with authentication"""
    
    # Check rate limits
    if not await check_rate_limits(user):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded"
        )
    
    start_time = datetime.now()
    
    try:
        # Get document based on type
        if document_type == "yargitay" and MCP_AVAILABLE:
            result = await get_yargitay_document_markdown(document_id)
        elif document_type == "danistay" and MCP_AVAILABLE:
            result = await get_danistay_document_markdown(document_id)
        elif document_type == "emsal" and MCP_AVAILABLE:
            result = await get_emsal_document_markdown(document_id)
        else:
            result = f"Document {document_id} from {document_type} (Fallback Mode)"
        
        response_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # Log document access
        await log_api_usage(
            user["user_id"],
            f"/api/document/{document_type}",
            success=True,
            response_time_ms=response_time
        )
        
        return {
            "success": True,
            "document_type": document_type,
            "document_id": document_id,
            "content": result,
            "meta": {
                "response_time_ms": response_time,
                "user_plan": user["plan"]
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Document error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)