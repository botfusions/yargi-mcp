#!/usr/bin/env python3
"""Deploy schema using Supabase REST API"""

import os
import asyncio
import httpx
import json
from dotenv import load_dotenv

load_dotenv()

async def test_supabase_connection():
    """Test Supabase connection and create first table"""
    
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SERVICE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    if not SUPABASE_URL or not SERVICE_KEY:
        print("ERROR: Missing environment variables")
        return False
    
    print(f"Testing connection to: {SUPABASE_URL}")
    
    headers = {
        'apikey': SERVICE_KEY,
        'Authorization': f'Bearer {SERVICE_KEY}',
        'Content-Type': 'application/json'
    }
    
    # First, try to test the connection with a simple query
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Test connection
            print("Testing connection...")
            response = await client.get(
                f"{SUPABASE_URL}/rest/v1/",
                headers=headers
            )
            print(f"Connection test: Status {response.status_code}")
            print(f"Response: {response.text[:200]}")
            
            # Try to list existing tables
            print("\nListing existing tables...")
            response = await client.get(
                f"{SUPABASE_URL}/rest/v1/information_schema.tables?table_schema=eq.public&select=table_name",
                headers=headers
            )
            
            if response.status_code == 200:
                tables = response.json()
                print(f"Found {len(tables)} existing tables:")
                for table in tables[:10]:  # Show first 10
                    print(f"  - {table.get('table_name', 'N/A')}")
                return True
            else:
                print(f"Failed to list tables: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

async def create_first_table():
    """Create the user subscriptions table using direct SQL"""
    
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SERVICE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    # SQL for creating the main subscriptions table
    sql = """
    -- Enable necessary extensions
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    CREATE EXTENSION IF NOT EXISTS "pgcrypto";
    
    -- Create the main user subscriptions table
    CREATE TABLE IF NOT EXISTS yargi_mcp_user_subscriptions (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        user_id TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL,
        plan TEXT NOT NULL DEFAULT 'free',
        status TEXT NOT NULL DEFAULT 'active',
        requests_used INTEGER DEFAULT 0,
        requests_limit INTEGER DEFAULT 100,
        last_reset_date TIMESTAMPTZ DEFAULT NOW(),
        billing_period_start TIMESTAMPTZ DEFAULT NOW(),
        billing_period_end TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '30 days'),
        stripe_customer_id TEXT UNIQUE,
        stripe_subscription_id TEXT UNIQUE,
        stripe_payment_method_id TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        last_login TIMESTAMPTZ,
        CONSTRAINT valid_plan CHECK (plan IN ('free', 'basic', 'professional', 'enterprise')),
        CONSTRAINT valid_status CHECK (status IN ('active', 'cancelled', 'expired', 'suspended'))
    );
    
    -- Create index for fast lookups
    CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user_id ON yargi_mcp_user_subscriptions(user_id);
    CREATE INDEX IF NOT EXISTS idx_user_subscriptions_email ON yargi_mcp_user_subscriptions(email);
    """
    
    print("Creating first table: yargi_mcp_user_subscriptions")
    
    headers = {
        'apikey': SERVICE_KEY,
        'Authorization': f'Bearer {SERVICE_KEY}',
        'Content-Type': 'text/plain'
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{SUPABASE_URL}/sql",
                headers=headers,
                content=sql
            )
            
            if response.status_code in [200, 201, 204]:
                print("SUCCESS: Main table created!")
                print("Response:", response.text[:300])
                
                # Verify table exists
                await verify_table_creation()
                return True
            else:
                print(f"FAILED: Status {response.status_code}")
                print("Error:", response.text)
                return False
                
        except Exception as e:
            print(f"ERROR: {e}")
            return False

async def verify_table_creation():
    """Verify that the table was created"""
    
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SERVICE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    headers = {
        'apikey': SERVICE_KEY,
        'Authorization': f'Bearer {SERVICE_KEY}',
        'Content-Type': 'application/json'
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{SUPABASE_URL}/rest/v1/yargi_mcp_user_subscriptions?limit=1",
                headers=headers
            )
            
            if response.status_code == 200:
                print("SUCCESS: Table verified - can query yargi_mcp_user_subscriptions")
                return True
            else:
                print(f"Cannot query table: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"Verification error: {e}")
            return False

async def create_admin_user():
    """Create admin user in the subscriptions table"""
    
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SERVICE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    admin_data = {
        "user_id": "admin_user_cenk_tokgoz",
        "email": "cenk.tokgoz@gmail.com", 
        "plan": "enterprise",
        "status": "active",
        "requests_limit": 999999,
        "requests_used": 0
    }
    
    headers = {
        'apikey': SERVICE_KEY,
        'Authorization': f'Bearer {SERVICE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'return=minimal'
    }
    
    print(f"Creating admin user: {admin_data['email']}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{SUPABASE_URL}/rest/v1/yargi_mcp_user_subscriptions",
                headers=headers,
                json=admin_data
            )
            
            if response.status_code in [200, 201]:
                print("SUCCESS: Admin user created!")
                return True
            else:
                print(f"Failed to create admin user: {response.status_code}")
                print(f"Response: {response.text}")
                
                # Try to update if already exists
                if "duplicate" in response.text.lower() or "already exists" in response.text.lower():
                    print("User already exists, trying to update...")
                    # Try update instead
                    response = await client.patch(
                        f"{SUPABASE_URL}/rest/v1/yargi_mcp_user_subscriptions?user_id=eq.admin_user_cenk_tokgoz",
                        headers=headers,
                        json=admin_data
                    )
                    
                    if response.status_code in [200, 204]:
                        print("SUCCESS: Admin user updated!")
                        return True
                
                return False
                
        except Exception as e:
            print(f"ERROR creating admin user: {e}")
            return False

async def main():
    """Main deployment function"""
    print("=== Supabase Schema Deployment ===")
    
    # Step 1: Test connection
    print("\n1. Testing Supabase connection...")
    if not await test_supabase_connection():
        print("Connection failed. Check your Supabase configuration.")
        return False
    
    # Step 2: Create main table
    print("\n2. Creating main subscription table...")
    if not await create_first_table():
        print("Failed to create main table.")
        return False
    
    # Step 3: Create admin user
    print("\n3. Creating admin user...")
    if not await create_admin_user():
        print("Failed to create admin user.")
        return False
    
    print("\n=== SUCCESS ===")
    print("✓ Supabase connection working")
    print("✓ Main table created: yargi_mcp_user_subscriptions") 
    print("✓ Admin user created: cenk.tokgoz@gmail.com")
    print("\nNext steps:")
    print("1. Create remaining tables by running full schema")
    print("2. Set up Clerk authentication")
    print("3. Test admin dashboard")
    
    return True

if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)