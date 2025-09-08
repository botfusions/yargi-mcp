#!/usr/bin/env python3
"""Direct table creation via Supabase"""

import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

async def create_subscription_table():
    """Create user subscriptions table directly"""
    
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SERVICE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    # Simple table creation
    admin_user = {
        "user_id": "admin_cenk_tokgoz",
        "email": "cenk.tokgoz@gmail.com",
        "plan": "enterprise", 
        "status": "active",
        "requests_used": 0,
        "requests_limit": 999999,
        "created_at": "2025-01-21T12:00:00Z",
        "updated_at": "2025-01-21T12:00:00Z"
    }
    
    headers = {
        'apikey': SERVICE_KEY,
        'Authorization': f'Bearer {SERVICE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'return=representation'
    }
    
    print(f"Connecting to: {SUPABASE_URL}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        # First try to insert directly - this will fail if table doesn't exist
        print("Attempting to create admin user...")
        try:
            response = await client.post(
                f"{SUPABASE_URL}/rest/v1/yargi_mcp_user_subscriptions",
                headers=headers,
                json=admin_user
            )
            
            print(f"Response status: {response.status_code}")
            print(f"Response: {response.text}")
            
            if response.status_code in [200, 201]:
                print("SUCCESS: Admin user created!")
                print("This means the table already exists.")
                return True
            elif "does not exist" in response.text or "42P01" in response.text:
                print("Table doesn't exist. Need to create schema first.")
                
                # Try to create via SQL endpoint
                print("Creating table via SQL...")
                sql = """
                CREATE TABLE IF NOT EXISTS yargi_mcp_user_subscriptions (
                    user_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    plan TEXT DEFAULT 'free',
                    status TEXT DEFAULT 'active', 
                    requests_used INTEGER DEFAULT 0,
                    requests_limit INTEGER DEFAULT 100,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
                """
                
                sql_response = await client.post(
                    f"{SUPABASE_URL}/sql",
                    headers={
                        'apikey': SERVICE_KEY,
                        'Authorization': f'Bearer {SERVICE_KEY}',
                        'Content-Type': 'text/plain'
                    },
                    content=sql
                )
                
                print(f"SQL response: {sql_response.status_code}")
                print(f"SQL result: {sql_response.text}")
                
                if sql_response.status_code in [200, 201, 204]:
                    print("Table created! Now inserting admin user...")
                    
                    # Try inserting admin user again
                    response = await client.post(
                        f"{SUPABASE_URL}/rest/v1/yargi_mcp_user_subscriptions",
                        headers=headers,
                        json=admin_user
                    )
                    
                    if response.status_code in [200, 201]:
                        print("SUCCESS: Admin user created after table creation!")
                        return True
                
                return False
            else:
                print("Unexpected error:", response.text)
                return False
                
        except Exception as e:
            print(f"Error: {e}")
            return False

async def verify_setup():
    """Verify the setup worked"""
    
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SERVICE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    headers = {
        'apikey': SERVICE_KEY,
        'Authorization': f'Bearer {SERVICE_KEY}',
        'Content-Type': 'application/json'
    }
    
    print("\nVerifying setup...")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{SUPABASE_URL}/rest/v1/yargi_mcp_user_subscriptions?select=*",
                headers=headers
            )
            
            if response.status_code == 200:
                users = response.json()
                print(f"SUCCESS: Found {len(users)} users in database")
                for user in users:
                    print(f"  - {user.get('email')} ({user.get('plan')})")
                return True
            else:
                print(f"Verification failed: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"Verification error: {e}")
            return False

async def main():
    print("=== Direct Supabase Table Creation ===\n")
    
    success = await create_subscription_table()
    
    if success:
        await verify_setup()
        print("\n✓ Basic setup complete!")
        print("✓ Admin user: cenk.tokgoz@gmail.com")
        print("\nNext: Create remaining tables with full schema")
    else:
        print("\n✗ Setup failed")
        print("Manual step needed: Go to Supabase SQL Editor")
    
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)