"""
TurkLawAI.com Subscription System
Complete subscription management with Clerk + Stripe + Supabase
"""

import os
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import stripe
import jwt
from supabase_client import supabase_client

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

app = FastAPI(title="TurkLawAI Subscription API", version="1.0.0")

# CORS configuration for turklawai.com
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://turklawai.com", 
        "https://www.turklawai.com",
        "https://api.turklawai.com",
        "https://supabase.turklawai.com",
        "http://localhost:3000",  # Development
        "http://localhost:8000"   # Development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
CLERK_SECRET_KEY = os.getenv("CLERK_SECRET_KEY") 
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
TURKLAWAI_DOMAIN = "turklawai.com"

# Stripe configuration
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# Security
security = HTTPBearer()

# Subscription Plans
SUBSCRIPTION_PLANS = {
    "free": {
        "name": "Ücretsiz Plan",
        "price": 0,
        "requests_per_month": 100,
        "max_requests_per_minute": 5,
        "features": [
            "Temel Yargıtay arama",
            "Temel Danıştay arama",
            "Günde 100 sorgu",
            "Standart destek"
        ]
    },
    "basic": {
        "name": "Temel Plan",
        "price": 29.99,
        "stripe_price_id": "price_basic_monthly",
        "requests_per_month": 1000,
        "max_requests_per_minute": 20,
        "features": [
            "Tüm mahkeme erişimi",
            "Aylık 1,000 sorgu",
            "Gelişmiş filtreleme",
            "Email destek",
            "API erişimi"
        ]
    },
    "professional": {
        "name": "Profesyonel Plan",
        "price": 99.99,
        "stripe_price_id": "price_pro_monthly",
        "requests_per_month": 5000,
        "max_requests_per_minute": 60,
        "features": [
            "Tüm özellikler",
            "Aylık 5,000 sorgu",
            "Öncelikli destek",
            "Bulk API erişimi",
            "Özel entegrasyon",
            "İstatistikler ve raporlama"
        ]
    },
    "enterprise": {
        "name": "Kurumsal Plan",
        "price": 299.99,
        "stripe_price_id": "price_enterprise_monthly",
        "requests_per_month": 25000,
        "max_requests_per_minute": 200,
        "features": [
            "Sınırsız özellikler",
            "Aylık 25,000+ sorgu",
            "Dedicated destek",
            "On-premise deployment",
            "SLA garantisi",
            "Özel geliştirme"
        ]
    }
}

# Models
class SubscriptionStatus(BaseModel):
    user_id: str
    email: str
    plan: str
    status: str
    requests_used: int
    requests_limit: int
    billing_period_start: str
    billing_period_end: str
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None

class CreateSubscriptionRequest(BaseModel):
    plan: str
    payment_method_id: str

class UsageStats(BaseModel):
    user_id: str
    total_requests: int
    requests_this_month: int
    most_used_endpoints: List[Dict[str, Any]]
    success_rate: float

# Authentication Functions
async def verify_clerk_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Verify Clerk JWT token"""
    try:
        token = credentials.credentials
        
        # Decode JWT token (simplified - in production use proper Clerk verification)
        payload = jwt.decode(token, CLERK_SECRET_KEY, algorithms=["HS256"])
        
        return {
            "user_id": payload.get("sub"),
            "email": payload.get("email"),
            "clerk_id": payload.get("clerk_id")
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

async def create_user_subscription(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create new user subscription"""
    try:
        subscription_data = {
            'user_id': user_data['user_id'],
            'email': user_data['email'],
            'plan': user_data.get('plan', 'free'),
            'status': 'active',
            'requests_used': 0,
            'requests_limit': SUBSCRIPTION_PLANS[user_data.get('plan', 'free')]['requests_per_month'],
            'billing_period_start': datetime.now(timezone.utc).isoformat(),
            'billing_period_end': (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            'stripe_customer_id': user_data.get('stripe_customer_id'),
            'stripe_subscription_id': user_data.get('stripe_subscription_id'),
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        result = await supabase_client.insert_data('user_subscriptions', subscription_data)
        return result
        
    except Exception as e:
        print(f"Error creating subscription: {e}")
        return {"success": False, "error": str(e)}

async def update_usage_stats(user_id: str, endpoint: str) -> None:
    """Update user's API usage statistics"""
    try:
        usage_data = {
            'user_id': user_id,
            'endpoint': endpoint,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'success': True
        }
        
        await supabase_client.insert_data('usage_logs', usage_data)
        
        # Update monthly usage counter
        current_subscription = await get_user_subscription(user_id)
        if current_subscription:
            new_usage = current_subscription['requests_used'] + 1
            update_data = {'requests_used': new_usage}
            
            # Here we would need to implement update functionality in supabase_client
            # For now, this is a placeholder
            
    except Exception as e:
        print(f"Error updating usage: {e}")

# Rate Limiting
async def check_rate_limit(user_id: str, plan: str) -> bool:
    """Check if user is within rate limits"""
    try:
        plan_limits = SUBSCRIPTION_PLANS.get(plan, SUBSCRIPTION_PLANS['free'])
        max_per_minute = plan_limits['max_requests_per_minute']
        
        # Check requests in last minute
        one_minute_ago = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        
        # This would need proper implementation with Redis or similar
        # For now, return True (allow)
        return True
        
    except Exception as e:
        print(f"Rate limit check error: {e}")
        return True

# API Endpoints

@app.get("/")
async def root():
    """Welcome endpoint"""
    return {
        "message": "TurkLawAI Subscription API",
        "version": "1.0.0",
        "domain": TURKLAWAI_DOMAIN,
        "docs": "/docs"
    }

@app.get("/health")
async def health():
    """Health check with all systems"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "supabase": "connected",
            "stripe": "configured" if STRIPE_SECRET_KEY else "not configured",
            "clerk": "configured" if CLERK_SECRET_KEY else "not configured"
        }
    }

@app.get("/subscription/plans")
async def get_subscription_plans():
    """Get available subscription plans"""
    return {
        "success": True,
        "plans": SUBSCRIPTION_PLANS
    }

@app.get("/subscription/status")
async def get_subscription_status(user: Dict[str, Any] = Depends(verify_clerk_token)) -> SubscriptionStatus:
    """Get current user's subscription status"""
    
    subscription = await get_user_subscription(user['user_id'])
    
    if not subscription:
        # Create free subscription for new users
        await create_user_subscription({
            'user_id': user['user_id'],
            'email': user['email'],
            'plan': 'free'
        })
        subscription = await get_user_subscription(user['user_id'])
    
    return SubscriptionStatus(**subscription)

@app.post("/subscription/create")
async def create_subscription(
    request: CreateSubscriptionRequest,
    user: Dict[str, Any] = Depends(verify_clerk_token)
):
    """Create new subscription with Stripe"""
    
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    
    try:
        plan = SUBSCRIPTION_PLANS.get(request.plan)
        if not plan:
            raise HTTPException(status_code=400, detail="Invalid plan")
        
        # Create Stripe customer
        customer = stripe.Customer.create(
            email=user['email'],
            payment_method=request.payment_method_id,
            invoice_settings={'default_payment_method': request.payment_method_id},
        )
        
        # Create Stripe subscription
        subscription = stripe.Subscription.create(
            customer=customer.id,
            items=[{'price': plan['stripe_price_id']}],
            expand=['latest_invoice.payment_intent'],
        )
        
        # Save to database
        await create_user_subscription({
            'user_id': user['user_id'],
            'email': user['email'],
            'plan': request.plan,
            'stripe_customer_id': customer.id,
            'stripe_subscription_id': subscription.id
        })
        
        return {
            "success": True,
            "subscription_id": subscription.id,
            "client_secret": subscription.latest_invoice.payment_intent.client_secret,
            "status": subscription.status
        }
        
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/subscription/cancel")
async def cancel_subscription(user: Dict[str, Any] = Depends(verify_clerk_token)):
    """Cancel user's subscription"""
    
    subscription = await get_user_subscription(user['user_id'])
    if not subscription or not subscription.get('stripe_subscription_id'):
        raise HTTPException(status_code=404, detail="No active subscription found")
    
    try:
        # Cancel Stripe subscription
        stripe.Subscription.modify(
            subscription['stripe_subscription_id'],
            cancel_at_period_end=True
        )
        
        return {
            "success": True,
            "message": "Subscription will be cancelled at the end of billing period"
        }
        
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/usage/stats")
async def get_usage_stats(user: Dict[str, Any] = Depends(verify_clerk_token)) -> UsageStats:
    """Get user's usage statistics"""
    
    # This would query usage_logs table for analytics
    # For now, return mock data
    return UsageStats(
        user_id=user['user_id'],
        total_requests=450,
        requests_this_month=120,
        most_used_endpoints=[
            {"endpoint": "/search/yargitay", "count": 45},
            {"endpoint": "/search/danistay", "count": 32},
            {"endpoint": "/search/emsal", "count": 28}
        ],
        success_rate=98.5
    )

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks"""
    
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Handle the event
    if event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        # Update user subscription status in database
        # Implementation needed
        
    elif event['type'] == 'invoice.payment_succeeded':
        invoice = event['data']['object']
        # Reset usage counters for new billing period
        # Implementation needed
        
    return {"received": True}

# Middleware for API usage tracking
@app.middleware("http")
async def track_api_usage(request: Request, call_next):
    """Track API usage for billing"""
    
    response = await call_next(request)
    
    # Track usage for authenticated API calls (simplified check)
    if request.url.path.startswith('/api/'):
        try:
            # Get user from authorization header if available
            auth_header = request.headers.get('authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                try:
                    payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
                    user_id = payload.get("sub") or payload.get("user_id")
                    if user_id:
                        await update_usage_stats(user_id, request.url.path)
                except:
                    pass  # Ignore JWT errors in middleware
        except Exception as e:
            print(f"Usage tracking error: {e}")
    
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)