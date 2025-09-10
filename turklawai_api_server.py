"""
TurkLawAI.com API Server
Emergency FastAPI server for authentication
"""
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
import asyncio
import uvicorn
import os
from dotenv import load_dotenv

# Import our emergency auth system
from turklawai_auth_fix import emergency_auth

load_dotenv()

app = FastAPI(
    title="TurkLawAI API",
    description="Emergency Authentication API for TurkLawAI.com",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://turklawai.com",
        "https://www.turklawai.com",
        "http://localhost:3000",
        "http://localhost:8080"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer(auto_error=False)

# Pydantic models
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = ""

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class AuthResponse(BaseModel):
    success: bool
    message: str
    user: Optional[Dict[str, Any]] = None
    token: Optional[str] = None

class UserResponse(BaseModel):
    success: bool
    user: Optional[Dict[str, Any]] = None
    message: str

# Authentication dependency
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token required"
        )
    
    result = await emergency_auth.verify_token(credentials.credentials)
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result["message"]
        )
    
    return result["user"]

# Routes
@app.get("/")
async def root():
    return {
        "message": "TurkLawAI API Server",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "register": "/auth/register",
            "login": "/auth/login",
            "profile": "/auth/user",
            "health": "/health"
        }
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": "2025-01-10",
        "services": {
            "api": "operational",
            "supabase": "connected",
            "authentication": "active"
        }
    }

@app.post("/auth/register", response_model=AuthResponse)
async def register(request: RegisterRequest):
    """Register new user"""
    try:
        result = await emergency_auth.register_user(
            email=request.email,
            password=request.password,
            full_name=request.full_name
        )
        
        return AuthResponse(
            success=result["success"],
            message=result["message"],
            user=result.get("user"),
            token=result.get("token")
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

@app.post("/auth/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """Login user"""
    try:
        result = await emergency_auth.login_user(
            email=request.email,
            password=request.password
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=result["message"]
            )
        
        return AuthResponse(
            success=result["success"],
            message=result["message"],
            user=result.get("user"),
            token=result.get("token")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )

@app.get("/auth/user", response_model=UserResponse)
async def get_user_profile(current_user: dict = Depends(get_current_user)):
    """Get current user profile"""
    return UserResponse(
        success=True,
        user=current_user,
        message="User profile retrieved"
    )

@app.post("/auth/logout")
async def logout():
    """Logout user (client-side token removal)"""
    return {
        "success": True,
        "message": "Logout successful - remove token from client"
    }

# Google OAuth placeholder (to be implemented with proper Clerk integration)
@app.get("/auth/google/login")
async def google_oauth_login():
    """Google OAuth login (placeholder)"""
    return {
        "success": False,
        "message": "Google OAuth temporarily unavailable - use email/password login",
        "redirect": "/auth/login"
    }

@app.get("/auth/callback")
async def oauth_callback(code: Optional[str] = None, state: Optional[str] = None):
    """OAuth callback (placeholder)"""
    return {
        "success": False,
        "message": "OAuth callback not implemented - use direct login",
        "redirect": "/"
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8001))
    host = os.getenv("HOST", "0.0.0.0")
    
    print(f"Starting TurkLawAI API Server on {host}:{port}")
    print("Endpoints:")
    print("  - POST /auth/register")
    print("  - POST /auth/login") 
    print("  - GET  /auth/user")
    print("  - GET  /health")
    
    uvicorn.run(
        "turklawai_api_server:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )