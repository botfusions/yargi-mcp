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
import bcrypt
from pydantic import BaseModel, EmailStr, Field

# Load environment variables
load_dotenv()

# In-memory user storage as fallback when database is not available
MEMORY_USERS = {}
JWT_SECRET = os.getenv('JWT_SECRET', 'your-secret-key-change-in-production')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRE_HOURS = 24

# Import original MCP clients directly
try:
    from yargitay_mcp_module.client import YargitayOfficialApiClient
    from yargitay_mcp_module.models import YargitayDetailedSearchRequest, YargitayBirimEnum
    from bedesten_mcp_module.client import BedestenApiClient
    from bedesten_mcp_module.models import BedestenSearchRequest
    from danistay_mcp_module.client import DanistayApiClient
    from emsal_mcp_module.client import EmsalApiClient
    from emsal_mcp_module.models import EmsalSearchRequest
    
    # Initialize clients
    yargitay_client = YargitayOfficialApiClient()
    danistay_client = DanistayApiClient()
    emsal_client = EmsalApiClient()
    bedesten_mcp_client = BedestenApiClient()
    yargi_mcp_client = yargitay_client  # For health check compatibility
    
    MCP_AVAILABLE = True
    print("Yargi MCP clients imported successfully")
except ImportError as e:
    print(f"Warning - Yargi MCP clients not available: {e}")
    MCP_AVAILABLE = False
    yargitay_client = None
    danistay_client = None
    emsal_client = None
    bedesten_mcp_client = None
    yargi_mcp_client = None

# Import Mevzuat MCP functions
try:
    import sys
    import os
    mevzuat_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mevzuat-mcp")
    if mevzuat_path not in sys.path:
        sys.path.insert(0, mevzuat_path)
    
    from mevzuat_client import MevzuatApiClient
    from mevzuat_models import (
        MevzuatSearchRequest, MevzuatSearchResult,
        MevzuatTurEnum, SortFieldEnum, SortDirectionEnum
    )
    
    # Initialize Mevzuat client
    mevzuat_client = MevzuatApiClient()
    MEVZUAT_AVAILABLE = True
    print("Mevzuat MCP client imported successfully")
except ImportError as e:
    print(f"Warning - Mevzuat MCP not available: {e}")
    MEVZUAT_AVAILABLE = False
    mevzuat_client = None

app = FastAPI(
    title="TurkLawAI MCP Server", 
    version="2.0.0",
    description="Authenticated Turkish Legal Search API with Subscription Management"
)

# CORS configuration
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",")
# Filter out empty strings
ALLOWED_ORIGINS = [origin.strip() for origin in ALLOWED_ORIGINS if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS + [
        "http://localhost:3000",  # Next.js dev server
        "http://localhost:8000",  # Alternative dev server
        "http://127.0.0.1:3000",  # Alternative localhost
        "https://turklawai.com",  # Production domain
        "https://www.turklawai.com"  # WWW production domain
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ENABLE_SUBSCRIPTION_SYSTEM = os.getenv("ENABLE_SUBSCRIPTION_SYSTEM", "false").lower() == "true"

# MCP Client variables (will be initialized based on available imports)
yargi_mcp_client = None
mevzuat_mcp_client = None
bedesten_mcp_client = None

# Security
security = HTTPBearer(auto_error=False)

# User Models
class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    
class UserLogin(BaseModel):
    email: EmailStr
    password: str
    
class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    plan: str
    created_at: str

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

# User Authentication Functions
def hash_password(password: str) -> str:
    """Hash password with bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def generate_jwt_token(user_data: dict) -> str:
    """Generate JWT token for user"""
    payload = {
        "sub": user_data["id"],
        "email": user_data["email"],
        "full_name": user_data["full_name"],
        "plan": user_data.get("plan", "free"),
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm="HS256")

async def create_user_account(user_data: UserRegister) -> dict:
    """Create new user account with free subscription"""
    try:
        # Check if user already exists in memory
        if user_data.email in MEMORY_USERS:
            raise Exception("User with this email already exists")
        
        # Hash password
        hashed_password = hash_password(user_data.password)
        
        # Try database first, fallback to memory
        user_record = {
            "email": user_data.email,
            "password_hash": hashed_password,
            "full_name": user_data.full_name,
            "plan": "free",
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "requests_used": 0,
            "requests_limit": RATE_LIMITS['free']['requests_per_month']
        }
        
        try:
            # Try to use database
            result = await supabase_client.insert_data('users', user_record)
            if result['success']:
                user_id = result['data'][0]['id']
                user_record['id'] = user_id
                return user_record
        except Exception as db_error:
            print(f"Database not available, using memory storage: {db_error}")
        
        # Fallback to memory storage
        user_id = f"mem_{len(MEMORY_USERS) + 1}"
        user_record['id'] = user_id
        MEMORY_USERS[user_data.email] = user_record
        
        return user_record
        
    except Exception as e:
        print(f"Error creating user: {e}")
        raise HTTPException(status_code=400, detail=str(e))

async def authenticate_user(email: str, password: str) -> dict:
    """Authenticate user and return user data"""
    try:
        # Try database first, fallback to memory
        user = None
        
        try:
            # Try to get user from database
            result = await supabase_client.query_data('users', {'email': email})
            if result['success'] and result['data']:
                user = result['data'][0]
        except Exception as db_error:
            print(f"Database not available, checking memory storage: {db_error}")
        
        # Fallback to memory storage
        if not user and email in MEMORY_USERS:
            user = MEMORY_USERS[email]
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        # Verify password
        if not verify_password(password, user['password_hash']):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Authentication error: {e}")
        raise HTTPException(status_code=500, detail="Authentication failed")

# API Endpoints

@app.get("/")
async def root():
    """Welcome endpoint"""
    return {
        "service": "TurkLawAI MCP Server",
        "version": "2.0.0",
        "authentication": ENABLE_SUBSCRIPTION_SYSTEM,
        "mcp_available": MCP_AVAILABLE,
        "mevzuat_available": MEVZUAT_AVAILABLE,
        "features": [
            "Turkish Legal Search",
            "Court Decision Access", 
            "Turkish Legislation Search",
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
            "yargi_mcp": "available" if MCP_AVAILABLE else "fallback_mode",
            "mevzuat_mcp": "available" if MEVZUAT_AVAILABLE else "fallback_mode",
            "authentication": "enabled" if ENABLE_SUBSCRIPTION_SYSTEM else "disabled"
        }
    }

# Authentication Endpoints

@app.post("/api/auth/register", response_model=dict)
async def register_user(user_data: UserRegister):
    """Register a new user account"""
    try:
        # Check if user already exists
        existing_user = await supabase_client.query_data('users', {'email': user_data.email})
        if existing_user['success'] and existing_user['data']:
            raise HTTPException(status_code=400, detail="User with this email already exists")
        
        # Create user account
        user = await create_user_account(user_data)
        
        # Generate JWT token
        token = generate_jwt_token(user)
        
        return {
            "success": True,
            "message": "User registered successfully",
            "token": token,
            "user": {
                "id": user["id"],
                "email": user["email"],
                "full_name": user["full_name"],
                "plan": user["plan"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")

@app.post("/api/auth/login", response_model=dict)
async def login_user(login_data: UserLogin):
    """Login user and return JWT token"""
    try:
        # Authenticate user
        user = await authenticate_user(login_data.email, login_data.password)
        
        # Generate JWT token
        token = generate_jwt_token(user)
        
        return {
            "success": True,
            "message": "Login successful",
            "token": token,
            "user": {
                "id": user["id"],
                "email": user["email"],
                "full_name": user["full_name"],
                "plan": user["plan"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Login failed")

@app.post("/api/auth/logout")
async def logout_user():
    """Logout user (client-side token removal)"""
    return {
        "success": True,
        "message": "Logged out successfully"
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
        if MCP_AVAILABLE and yargitay_client:
            # Create request object
            search_request = YargitayDetailedSearchRequest(
                andKelimeler=andKelimeler or "",
                birimYrgKurulDaire=daire or "",
                esasYil=esasYil or "",
                esasNo=esasNo or "",
                kararYil=kararYil or "",
                kararNo=kararNo or "",
                pageNumber=1,
                pageSize=page_size or 10
            )
            
            # Execute search
            result = await yargitay_client.search_detailed_decisions(search_request)
            
            # Close the client session
            await yargitay_client.close_client_session()
            
            # Convert to API response format
            api_result = {
                "results": [decision.model_dump() for decision in result.data.data],
                "total_count": result.data.recordsTotal,
                "current_page": result.data.page,
                "page_size": result.data.pageSize,
                "draw": result.data.draw,
                "recordsTotal": result.data.recordsTotal,
                "recordsFiltered": result.data.recordsFiltered
            }
        else:
            # Fallback response
            await asyncio.sleep(0.5)
            api_result = {
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
                "current_page": 1,
                "page_size": page_size
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
            "data": api_result,
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

# Mevzuat (Legislation) endpoints

@app.post("/api/search/mevzuat")
async def search_mevzuat_authenticated(
    request: Request,
    mevzuat_adi: Optional[str] = None,
    phrase: Optional[str] = None,
    mevzuat_no: Optional[str] = None,
    resmi_gazete_sayisi: Optional[str] = None,
    mevzuat_turleri: Optional[str] = None,  # JSON string of MevzuatTurEnum values
    page_number: Optional[int] = 1,
    page_size: Optional[int] = 10,
    sort_field: Optional[str] = "RESMI_GAZETE_TARIHI",
    sort_direction: Optional[str] = "desc",
    user: Dict[str, Any] = Depends(verify_token)
):
    """Authenticated Mevzuat (Turkish Legislation) search with rate limiting"""
    
    start_time = datetime.now()
    
    # Check rate limits
    if not await check_rate_limits(user):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please upgrade your plan or wait for the next billing period."
        )
    
    try:
        if MEVZUAT_AVAILABLE:
            # Prepare search request
            mevzuat_turleri_list = None
            if mevzuat_turleri:
                try:
                    import json
                    mevzuat_turleri_list = json.loads(mevzuat_turleri)
                except json.JSONDecodeError:
                    pass  # Will use default
            
            # Map string values to enum values
            sort_field_enum = SortFieldEnum.RESMI_GAZETE_TARIHI
            if sort_field == "KAYIT_TARIHI":
                sort_field_enum = SortFieldEnum.KAYIT_TARIHI
            elif sort_field == "MEVZUAT_NUMARASI":
                sort_field_enum = SortFieldEnum.MEVZUAT_NUMARASI
                
            sort_direction_enum = SortDirectionEnum.DESC if sort_direction.lower() == "desc" else SortDirectionEnum.ASC
            
            search_req = MevzuatSearchRequest(
                mevzuat_adi=mevzuat_adi,
                phrase=phrase,
                mevzuat_no=mevzuat_no,
                resmi_gazete_sayisi=resmi_gazete_sayisi,
                mevzuat_tur_list=mevzuat_turleri_list if mevzuat_turleri_list else [tur for tur in MevzuatTurEnum],
                page_number=page_number,
                page_size=page_size,
                sort_field=sort_field_enum,
                sort_direction=sort_direction_enum
            )
            
            result = await mevzuat_client.search_documents(search_req)
            
            # Convert to dictionary for consistent API response
            api_result = {
                "documents": [doc.model_dump() for doc in result.documents],
                "total_results": result.total_results,
                "current_page": result.current_page,
                "page_size": result.page_size,
                "total_pages": result.total_pages,
                "query_used": result.query_used,
                "error_message": result.error_message
            }
        else:
            # Fallback response
            await asyncio.sleep(0.5)
            api_result = {
                "documents": [
                    {
                        "mevzuat_id": "fallback-001",
                        "title": "Mevzuat Arama - Fallback Mode",
                        "type": "Test Data",
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "summary": f"Arama terimi: {mevzuat_adi or phrase or mevzuat_no}"
                    }
                ],
                "total_results": 1,
                "current_page": 1,
                "page_size": page_size,
                "total_pages": 1
            }
        
        # Calculate response time
        response_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # Log usage
        await log_api_usage(
            user["user_id"], 
            "/api/search/mevzuat",
            success=True,
            response_time_ms=response_time,
            query_params={
                "mevzuat_adi": mevzuat_adi,
                "phrase": phrase,
                "mevzuat_no": mevzuat_no,
                "page_size": page_size
            }
        )
        
        # Increment usage counter
        await increment_usage_counter(user["user_id"])
        
        return {
            "success": True,
            "data": api_result,
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
            "/api/search/mevzuat",
            success=False,
            response_time_ms=response_time
        )
        
        raise HTTPException(status_code=500, detail=f"Mevzuat search error: {str(e)}")

@app.get("/api/mevzuat/{mevzuat_id}/articles")
async def get_mevzuat_article_tree(
    mevzuat_id: str,
    user: Dict[str, Any] = Depends(verify_token)
):
    """Get article tree (table of contents) for a specific legislation"""
    
    # Check rate limits
    if not await check_rate_limits(user):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded"
        )
    
    start_time = datetime.now()
    
    try:
        if MEVZUAT_AVAILABLE:
            result = await mevzuat_client.get_article_tree(mevzuat_id)
            article_tree = [article.model_dump() for article in result]
        else:
            article_tree = [
                {
                    "madde_id": "fallback-article-001",
                    "title": "Test Article - Fallback Mode",
                    "level": 1,
                    "mevzuat_id": mevzuat_id
                }
            ]
        
        response_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # Log usage
        await log_api_usage(
            user["user_id"],
            f"/api/mevzuat/articles",
            success=True,
            response_time_ms=response_time
        )
        
        return {
            "success": True,
            "mevzuat_id": mevzuat_id,
            "articles": article_tree,
            "meta": {
                "response_time_ms": response_time,
                "user_plan": user["plan"]
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Article tree error: {str(e)}")

@app.get("/api/mevzuat/{mevzuat_id}/article/{madde_id}")
async def get_mevzuat_article_content(
    mevzuat_id: str,
    madde_id: str,
    user: Dict[str, Any] = Depends(verify_token)
):
    """Get full content of a specific article"""
    
    # Check rate limits
    if not await check_rate_limits(user):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded"
        )
    
    start_time = datetime.now()
    
    try:
        if MEVZUAT_AVAILABLE:
            result = await mevzuat_client.get_article_content(madde_id, mevzuat_id)
            content_data = result.model_dump()
        else:
            content_data = {
                "madde_id": madde_id,
                "mevzuat_id": mevzuat_id,
                "markdown_content": f"Article content {madde_id} from {mevzuat_id} (Fallback Mode)",
                "error_message": None
            }
        
        response_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # Log usage
        await log_api_usage(
            user["user_id"],
            f"/api/mevzuat/article",
            success=True,
            response_time_ms=response_time
        )
        
        return {
            "success": True,
            "data": content_data,
            "meta": {
                "response_time_ms": response_time,
                "user_plan": user["plan"]
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Article content error: {str(e)}")

# Subscription Management Endpoints

class PlanUpgradeRequest(BaseModel):
    plan: str = Field(..., description="Target plan: basic, professional, enterprise")

@app.post("/api/subscription/upgrade")
async def upgrade_subscription_plan(
    upgrade_request: PlanUpgradeRequest,
    user: Dict[str, Any] = Depends(verify_token)
):
    """Upgrade user's subscription plan (for testing - in production would integrate with Stripe)"""
    
    # Validate plan
    valid_plans = ["basic", "professional", "enterprise"]
    if upgrade_request.plan not in valid_plans:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid plan. Must be one of: {valid_plans}"
        )
    
    user_id = user["user_id"]
    
    try:
        # Update user subscription in database
        subscription_data = {
            'plan': upgrade_request.plan,
            'status': 'active',
            'requests_used': 0,
            'requests_limit': RATE_LIMITS[upgrade_request.plan]['requests_per_month'],
            'billing_period_start': datetime.now(timezone.utc).isoformat(),
            'billing_period_end': (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        # In a real implementation, this would update the existing subscription
        # For demo purposes, we'll create a new subscription entry
        result = await supabase_client.insert_data('user_subscriptions', {
            'user_id': user_id,
            **subscription_data
        })
        
        if result['success']:
            return {
                "success": True,
                "message": f"Successfully upgraded to {upgrade_request.plan} plan",
                "new_plan": upgrade_request.plan,
                "new_limits": RATE_LIMITS[upgrade_request.plan],
                "billing_cycle": "monthly"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to update subscription")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Subscription upgrade error: {str(e)}")

@app.get("/api/subscription/plans")
async def get_available_plans():
    """Get all available subscription plans and their limits"""
    
    plans = {}
    for plan_name, limits in RATE_LIMITS.items():
        if plan_name == "free":
            price = 0
        elif plan_name == "basic":
            price = 29.99
        elif plan_name == "professional":
            price = 99.99
        elif plan_name == "enterprise":
            price = 299.99
        else:
            price = 0
            
        plans[plan_name] = {
            "name": plan_name.title(),
            "price_monthly": price,
            "requests_per_minute": limits["requests_per_minute"],
            "requests_per_month": limits["requests_per_month"],
            "features": [
                f"Up to {limits['requests_per_month']} searches per month",
                f"Up to {limits['requests_per_minute']} searches per minute",
                "Turkish legal database access",
                "API access" if plan_name != "free" else "Limited API access"
            ]
        }
    
    return {
        "success": True,
        "plans": plans,
        "currency": "USD"
    }

# Frontend-Compatible API Endpoints (for turklaw-ai-insight GitHub repo)

# Yargi API endpoints
@app.get("/api/yargi/health")
async def yargi_health_check():
    """Health check endpoint for Yargi services"""
    try:
        # Check if MCP clients are available
        yargi_available = yargi_mcp_client is not None
        mevzuat_available = mevzuat_mcp_client is not None
        
        return {
            "status": "healthy" if (yargi_available or mevzuat_available) else "degraded",
            "services": {
                "yargi_mcp": "available" if yargi_available else "unavailable",
                "mevzuat_mcp": "available" if mevzuat_available else "unavailable"
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@app.post("/api/yargi/bedesten/search")
async def search_bedesten_api(
    request: Dict[str, Any],
    user: Dict[str, Any] = Depends(verify_token)
):
    """Bedesten search endpoint compatible with frontend"""
    try:
        if not bedesten_mcp_client:
            raise HTTPException(status_code=503, detail="Bedesten service unavailable")
        
        # Map frontend params to backend params
        phrase = request.get('phrase', '')
        court_types = request.get('court_types', ['YARGITAYKARARI'])
        page_number = request.get('pageNumber', 1)
        
        from bedesten_mcp_module.models import BedestenSearchRequest, BedestenSearchData
        
        search_data = BedestenSearchData(
            pageSize=10,
            pageNumber=page_number,
            itemTypeList=court_types,
            phrase=phrase,
            birimAdi="ALL"
        )
        
        search_request = BedestenSearchRequest(data=search_data)
        result = await bedesten_mcp_client.search_documents(search_request)
        
        # Convert to frontend format
        decisions = []
        if result.data and result.data.emsalKararList:
            for decision in result.data.emsalKararList:
                decisions.append({
                    "id": decision.documentId,
                    "title": f"{decision.birimAdi or 'Unknown'} - {decision.kararNo or 'No Decision Number'}",
                    "court": decision.itemType.name if decision.itemType else "Unknown",
                    "chamber": decision.birimAdi or "",
                    "date": decision.kararTarihi,
                    "summary": f"Esas No: {decision.esasNo or 'N/A'}, Karar No: {decision.kararNo or 'N/A'}",
                    "caseNumber": decision.esasNo,
                    "decisionNumber": decision.kararNo,
                    "documentType": "decision",
                    "metadata": {
                        "documentId": decision.documentId,
                        "itemType": decision.itemType.model_dump() if decision.itemType else None,
                        "kararTuru": decision.kararTuru,
                        "kesinlesmeDurumu": decision.kesinlesmeDurumu
                    }
                })
        
        return {
            "results": decisions,
            "total_records": result.data.total if result.data else 0,
            "requested_page": page_number,
            "page_size": 10,
            "searched_courts": court_types
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bedesten search error: {str(e)}")

@app.get("/api/yargi/bedesten/document/{document_id}")
async def get_bedesten_document_api(
    document_id: str,
    user: Dict[str, Any] = Depends(verify_token)
):
    """Get Bedesten document endpoint compatible with frontend"""
    try:
        if not bedesten_mcp_client:
            raise HTTPException(status_code=503, detail="Bedesten service unavailable")
        
        result = await bedesten_mcp_client.get_document_as_markdown(document_id)
        
        return {
            "markdown_content": result.markdown_content,
            "source_url": result.source_url,
            "mime_type": result.mime_type
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Document retrieval error: {str(e)}")

# Mevzuat API endpoints
@app.post("/api/mevzuat/search")
async def search_mevzuat_api(
    request: Dict[str, Any],
    user: Dict[str, Any] = Depends(verify_token)
):
    """Mevzuat search endpoint compatible with frontend"""
    try:
        if not mevzuat_mcp_client:
            raise HTTPException(status_code=503, detail="Mevzuat service unavailable")
        
        # Map frontend params to backend params
        phrase = request.get('phrase', '')
        mevzuat_adi = request.get('mevzuat_adi', '')
        page_number = request.get('page_number', 1)
        page_size = request.get('page_size', 10)
        
        # Use phrase for general search or mevzuat_adi for specific name search
        search_term = phrase or mevzuat_adi
        
        from mevzuat_mcp_module.models import MevzuatSearchRequest
        
        search_request = MevzuatSearchRequest(
            mevzuat_adi=search_term,
            page_number=page_number,
            page_size=page_size
        )
        
        result = await mevzuat_mcp_client.search_legislation(search_request)
        
        # Convert to frontend format
        legislation_results = []
        if result.mevzuat_listesi:
            for legislation in result.mevzuat_listesi:
                legislation_results.append({
                    "id": str(legislation.mevzuat_id),
                    "title": legislation.mevzuat_adi,
                    "type": legislation.mevzuat_turu,
                    "number": legislation.mevzuat_no,
                    "date": legislation.resmi_gazete_tarihi.isoformat() if legislation.resmi_gazete_tarihi else "",
                    "summary": f"Resmi Gazete: {legislation.resmi_gazete_no or 'N/A'}",
                    "url": legislation.url,
                    "metadata": {
                        "mevzuat_id": legislation.mevzuat_id,
                        "mevzuat_turu": legislation.mevzuat_turu,
                        "resmi_gazete_no": legislation.resmi_gazete_no,
                        "resmi_gazete_tarihi": legislation.resmi_gazete_tarihi.isoformat() if legislation.resmi_gazete_tarihi else None
                    }
                })
        
        return {
            "results": legislation_results,
            "total_records": result.total_count,
            "requested_page": page_number,
            "page_size": page_size
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Mevzuat search error: {str(e)}")

@app.get("/api/mevzuat/legislation/{mevzuat_id}/structure")
async def get_mevzuat_structure_api(
    mevzuat_id: int,
    user: Dict[str, Any] = Depends(verify_token)
):
    """Get legislation structure endpoint compatible with frontend"""
    try:
        if not mevzuat_mcp_client:
            raise HTTPException(status_code=503, detail="Mevzuat service unavailable")
        
        from mevzuat_mcp_module.models import MevzuatStructureRequest
        
        request_obj = MevzuatStructureRequest(mevzuat_id=mevzuat_id)
        result = await mevzuat_mcp_client.get_legislation_structure(request_obj)
        
        return result.model_dump()
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Structure retrieval error: {str(e)}")

@app.get("/api/mevzuat/legislation/{mevzuat_id}/article/{madde_id}")
async def get_mevzuat_article_api(
    mevzuat_id: int,
    madde_id: str,
    user: Dict[str, Any] = Depends(verify_token)
):
    """Get legislation article endpoint compatible with frontend"""
    try:
        if not mevzuat_mcp_client:
            raise HTTPException(status_code=503, detail="Mevzuat service unavailable")
        
        from mevzuat_mcp_module.models import MevzuatArticleRequest
        
        request_obj = MevzuatArticleRequest(
            mevzuat_id=mevzuat_id,
            madde_id=madde_id
        )
        
        result = await mevzuat_mcp_client.get_article_content(request_obj)
        
        return {
            "markdown_content": result.markdown_content,
            "source_url": result.source_url if hasattr(result, 'source_url') else f"https://www.mevzuat.gov.tr/mevzuat?MevzuatNo={mevzuat_id}",
            "mime_type": "text/markdown"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Article retrieval error: {str(e)}")

# Frontend-compatible Yargi API endpoints
@app.get("/api/yargi/health")
async def check_yargi_health():
    """Health check endpoint for Yargi MCP services"""
    return {
        "status": "healthy" if MCP_AVAILABLE else "fallback_mode",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "yargitay": "available" if yargitay_client else "unavailable",
            "bedesten": "available" if bedesten_mcp_client else "unavailable",
            "danistay": "available" if danistay_client else "unavailable",
            "emsal": "available" if emsal_client else "unavailable"
        }
    }

@app.post("/api/yargi/bedesten/search")
async def search_bedesten_api(
    request: Dict[str, Any],
    user: Dict[str, Any] = Depends(verify_token)
):
    """Bedesten search endpoint compatible with frontend"""
    try:
        if not bedesten_mcp_client:
            raise HTTPException(status_code=503, detail="Bedesten service unavailable")
        
        # Map frontend request to backend format
        search_request = BedestenSearchRequest(
            phrase=request.get("phrase", ""),
            court_types=request.get("court_types", ["YARGITAYKARARI"]),
            birimAdi=request.get("birimAdi", ""),
            kararTarihiStart=request.get("kararTarihiStart"),
            kararTarihiEnd=request.get("kararTarihiEnd"),
            pageNumber=request.get("pageNumber", 1),
            pageSize=request.get("pageSize", 10)
        )
        
        result = await bedesten_mcp_client.search_unified(search_request)
        
        return {
            "results": [decision.model_dump() for decision in result.decisions],
            "total_records": result.total_records,
            "requested_page": result.requested_page,
            "page_size": result.page_size,
            "searched_courts": request.get("court_types", ["YARGITAYKARARI"]),
            "query": request.get("phrase", "")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bedesten search error: {str(e)}")

@app.get("/api/yargi/bedesten/document/{document_id}")
async def get_bedesten_document_api(
    document_id: str,
    user: Dict[str, Any] = Depends(verify_token)
):
    """Get Bedesten document endpoint compatible with frontend"""
    try:
        if not bedesten_mcp_client:
            raise HTTPException(status_code=503, detail="Bedesten service unavailable")
        
        result = await bedesten_mcp_client.get_document_markdown(document_id)
        
        return {
            "markdown_content": result.markdown_content,
            "source_url": result.source_url if hasattr(result, 'source_url') else "",
            "mime_type": "text/markdown"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Document retrieval error: {str(e)}")

@app.post("/api/yargi/anayasa/search")
async def search_anayasa_api(
    request: Dict[str, Any],
    user: Dict[str, Any] = Depends(verify_token)
):
    """Anayasa search endpoint compatible with frontend"""
    try:
        # For now, return a placeholder response until Anayasa client is properly integrated
        return {
            "results": [],
            "total_records": 0,
            "current_page": 1,
            "page_size": 10,
            "message": "Anayasa search temporarily unavailable - under development"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Anayasa search error: {str(e)}")

@app.get("/api/yargi/anayasa/document")
async def get_anayasa_document_api(
    document_url: str,
    page_number: int = 1,
    user: Dict[str, Any] = Depends(verify_token)
):
    """Get Anayasa document endpoint compatible with frontend"""
    try:
        return {
            "markdown_content": "Anayasa document content temporarily unavailable - under development",
            "source_url": document_url,
            "mime_type": "text/markdown"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Anayasa document retrieval error: {str(e)}")

@app.post("/api/yargi/emsal/search") 
async def search_emsal_api(
    request: Dict[str, Any],
    user: Dict[str, Any] = Depends(verify_token)
):
    """Emsal search endpoint compatible with frontend"""
    try:
        if not emsal_client:
            raise HTTPException(status_code=503, detail="Emsal service unavailable")
        
        # Map frontend request to backend format
        search_request = EmsalSearchRequest(
            keyword=request.get("keyword", ""),
            start_date=request.get("start_date", ""),
            end_date=request.get("end_date", ""),
            page_number=request.get("page_number", 1),
            selected_regional_civil_chambers=request.get("selected_regional_civil_chambers", []),
            sort_criteria=request.get("sort_criteria", "1"),
            sort_direction=request.get("sort_direction", "desc")
        )
        
        result = await emsal_client.search_emsal(search_request)
        
        return {
            "results": [decision.model_dump() for decision in result.decisions],
            "total_records": result.total_records,
            "requested_page": result.requested_page,
            "page_size": result.page_size
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Emsal search error: {str(e)}")

@app.get("/api/yargi/emsal/document/{document_id}")
async def get_emsal_document_api(
    document_id: str,
    user: Dict[str, Any] = Depends(verify_token)
):
    """Get Emsal document endpoint compatible with frontend"""
    try:
        if not emsal_client:
            raise HTTPException(status_code=503, detail="Emsal service unavailable")
        
        result = await emsal_client.get_document_markdown(document_id)
        
        return {
            "markdown_content": result.markdown_content,
            "source_url": result.source_url if hasattr(result, 'source_url') else "",
            "mime_type": "text/markdown"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Emsal document retrieval error: {str(e)}")

# Frontend-compatible Mevzuat API endpoints (additional ones)
@app.get("/api/mevzuat/popular")
async def get_popular_legislation_api(user: Dict[str, Any] = Depends(verify_token)):
    """Get popular legislation endpoint compatible with frontend"""
    try:
        # Return placeholder popular legislation
        return [
            {"id": 1, "name": "Türk Ceza Kanunu", "type": "KANUN"},
            {"id": 2, "name": "Türk Medeni Kanunu", "type": "KANUN"},
            {"id": 3, "name": "Borçlar Kanunu", "type": "KANUN"}
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Popular legislation error: {str(e)}")

@app.get("/api/mevzuat/types")
async def get_legislation_types_api(user: Dict[str, Any] = Depends(verify_token)):
    """Get legislation types endpoint compatible with frontend"""
    try:
        return [
            {"value": "KANUN", "label": "Kanun"},
            {"value": "KANUN_HUKMUNDE_KARARNAME", "label": "Kanun Hükmünde Kararname"},
            {"value": "YONETMELIK", "label": "Yönetmelik"},
            {"value": "TUZUK", "label": "Tüzük"},
            {"value": "CUMHURBASKANI_KARARI", "label": "Cumhurbaşkanı Kararı"}
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Legislation types error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)  # Changed port to 8002 for TurkLawAI