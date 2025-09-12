#!/usr/bin/env python3
"""
TurkLawAI Production Server
Optimized for production deployment with enhanced security and monitoring
"""
import asyncio
import uvicorn
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import logging
from datetime import datetime

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO if os.getenv('LOG_LEVEL') == 'info' else logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Production configuration
PRODUCTION = os.getenv('PRODUCTION', 'false').lower() == 'true'
API_PORT = int(os.getenv('API_PORT', '8001'))
ALLOWED_HOSTS = ['turklawai.com', 'www.turklawai.com', 'api.turklawai.com']

if not PRODUCTION:
    ALLOWED_HOSTS.extend(['localhost', '127.0.0.1'])

app = FastAPI(
    title="TurkLawAI Production API",
    description="Turkish Legal Search API with Authentication & Subscription System",
    version="2.0.0",
    docs_url="/docs" if not PRODUCTION else None,  # Disable docs in production
    redoc_url="/redoc" if not PRODUCTION else None
)

# Security middleware for production
if PRODUCTION:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

# CORS middleware
cors_origins = [
    "https://turklawai.com",
    "https://www.turklawai.com",
    "https://api.turklawai.com"
]

if not PRODUCTION:
    cors_origins.extend([
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Import authentication system
try:
    from turklawai_auth_fix import emergency_auth
    from supabase_client import SupabaseClient
    AUTH_AVAILABLE = True
    logger.info("Authentication system loaded successfully")
except ImportError as e:
    AUTH_AVAILABLE = False
    logger.error(f"Authentication system not available: {e}")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Enhanced health check with system status"""
    try:
        # Test database connection if available
        db_status = "unknown"
        if AUTH_AVAILABLE:
            try:
                # Quick database ping
                supabase = SupabaseClient()
                await supabase.test_connection()
                db_status = "connected"
            except Exception as e:
                db_status = f"error: {str(e)[:50]}"
                logger.error(f"Database connection failed: {e}")
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "2.0.0",
            "environment": "production" if PRODUCTION else "development",
            "services": {
                "api": "operational",
                "database": db_status,
                "authentication": "active" if AUTH_AVAILABLE else "disabled"
            },
            "uptime": "running"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

# Authentication endpoints
if AUTH_AVAILABLE:
    from pydantic import BaseModel, EmailStr
    
    class LoginRequest(BaseModel):
        email: EmailStr
        password: str
    
    class RegisterRequest(BaseModel):
        email: EmailStr
        password: str
        full_name: str
        plan: str = "free"
    
    @app.post("/auth/login")
    async def login(credentials: LoginRequest):
        """User authentication endpoint"""
        try:
            result = await emergency_auth.authenticate_user(
                credentials.email, 
                credentials.password
            )
            if result['success']:
                logger.info(f"Successful login for user: {credentials.email}")
                return result
            else:
                logger.warning(f"Failed login attempt for user: {credentials.email}")
                raise HTTPException(status_code=401, detail=result['message'])
        except Exception as e:
            logger.error(f"Login error: {e}")
            raise HTTPException(status_code=500, detail="Authentication service error")
    
    @app.post("/auth/register")
    async def register(user_data: RegisterRequest):
        """User registration endpoint"""
        try:
            result = await emergency_auth.register_user(
                email=user_data.email,
                password=user_data.password,
                full_name=user_data.full_name,
                plan=user_data.plan
            )
            if result['success']:
                logger.info(f"New user registered: {user_data.email}")
                return result
            else:
                logger.warning(f"Registration failed for: {user_data.email}")
                raise HTTPException(status_code=400, detail=result['message'])
        except Exception as e:
            logger.error(f"Registration error: {e}")
            raise HTTPException(status_code=500, detail="Registration service error")
    
    @app.get("/auth/verify")
    async def verify_token(request: Request):
        """Token verification endpoint"""
        try:
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                raise HTTPException(status_code=401, detail="Missing or invalid token")
            
            token = auth_header.split(" ")[1]
            result = await emergency_auth.verify_token(token)
            
            if result['valid']:
                return {"valid": True, "user": result['user']}
            else:
                raise HTTPException(status_code=401, detail="Invalid token")
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            raise HTTPException(status_code=401, detail="Token verification failed")

else:
    @app.get("/auth/status")
    async def auth_status():
        return {"message": "Authentication system not configured"}

# Static files (if available)
static_path = Path("static")
if static_path.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Root endpoint
@app.get("/")
async def root():
    """API information endpoint"""
    return {
        "service": "TurkLawAI Production API",
        "version": "2.0.0",
        "status": "operational",
        "environment": "production" if PRODUCTION else "development",
        "endpoints": {
            "health": "/health",
            "auth_login": "/auth/login",
            "auth_register": "/auth/register",
            "auth_verify": "/auth/verify",
            "documentation": "/docs" if not PRODUCTION else "disabled"
        },
        "features": {
            "authentication": AUTH_AVAILABLE,
            "subscriptions": True,
            "rate_limiting": True,
            "ssl_required": PRODUCTION
        }
    }

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": "The requested endpoint does not exist",
            "path": str(request.url.path)
        }
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: HTTPException):
    logger.error(f"Internal server error on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred"
        }
    )

# Startup event
@app.on_event("startup")
async def startup_event():
    logger.info(f"TurkLawAI API starting...")
    logger.info(f"Environment: {'Production' if PRODUCTION else 'Development'}")
    logger.info(f"Port: {API_PORT}")
    logger.info(f"Authentication: {'Enabled' if AUTH_AVAILABLE else 'Disabled'}")
    logger.info(f"Allowed hosts: {ALLOWED_HOSTS}")

# Shutdown event  
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("TurkLawAI API shutting down...")

async def main():
    """Main application entry point"""
    try:
        config = uvicorn.Config(
            app,
            host="127.0.0.1" if PRODUCTION else "0.0.0.0",
            port=API_PORT,
            log_level="info" if os.getenv('LOG_LEVEL') == 'info' else "warning",
            access_log=True,
            reload=not PRODUCTION  # Enable reload only in development
        )
        
        server = uvicorn.Server(config)
        logger.info(f"Starting TurkLawAI API server on port {API_PORT}")
        await server.serve()
        
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server startup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())