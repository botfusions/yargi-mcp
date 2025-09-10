#!/usr/bin/env python3
"""
Direct admin user creation using Supabase client
"""
import asyncio
from datetime import datetime
from supabase_client import supabase_client
from turklawai_auth_fix import emergency_auth

async def create_admin_direct():
    print("Creating admin user directly in database...")
    
    # Admin user data
    admin_email = "admin@turklawai.com"
    admin_password = "admin123"
    
    # Hash the password
    hashed_password = emergency_auth.hash_password(admin_password)
    print(f"Password hash: {hashed_password}")
    
    # Create user data (matching real table structure)
    user_data = {
        "email": admin_email,
        "password_hash": hashed_password,
        "full_name": "TurkLawAI Admin",
        "plan": "enterprise",
        "status": "active",
        "requests_used": 0,
        "requests_limit": 1000,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    
    print(f"\nInserting user data: {user_data}")
    
    # Insert directly
    result = await supabase_client.insert_data("users", user_data)
    
    if result['success']:
        print(f"SUCCESS: Admin user created directly!")
        print(f"Data: {result['data']}")
        
        # Test login
        print(f"\nTesting login...")
        login_result = await emergency_auth.login_user(admin_email, admin_password)
        if login_result['success']:
            print(f"LOGIN SUCCESS: {login_result['message']}")
            print(f"Token: {login_result['token'][:50]}...")
        else:
            print(f"LOGIN FAILED: {login_result['message']}")
    else:
        print(f"ERROR: {result['error']}")
        print(f"Message: {result['message']}")

if __name__ == "__main__":
    asyncio.run(create_admin_direct())