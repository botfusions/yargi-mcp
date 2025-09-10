#!/usr/bin/env python3
"""
Create admin user for TurkLawAI authentication system
"""
import asyncio
from turklawai_auth_fix import emergency_auth
from supabase_client import supabase_client

async def create_admin_user():
    print("Creating admin user for TurkLawAI...")
    
    # Admin user credentials
    admin_email = "admin@turklawai.com"
    admin_password = "admin123"
    admin_full_name = "TurkLawAI Admin"
    
    # Check if admin already exists
    print(f"\n1. Checking if {admin_email} already exists...")
    existing_result = await supabase_client.query_data("users", {"email": admin_email})
    
    if existing_result['success'] and existing_result['data']:
        print(f"   Admin user already exists!")
        admin_user = existing_result['data'][0]
        print(f"   Email: {admin_user['email']}")
        print(f"   Plan: {admin_user.get('plan', 'unknown')}")
        print(f"   Active: {admin_user.get('is_active', 'unknown')}")
        return
    
    # Create admin user using emergency auth system
    print(f"\n2. Creating admin user...")
    result = await emergency_auth.register_user(
        email=admin_email,
        password=admin_password,
        full_name=admin_full_name
    )
    
    if result['success']:
        print(f"   SUCCESS: Admin user created!")
        print(f"   Email: {result['user']['email']}")
        print(f"   Name: {result['user']['full_name']}")
        print(f"   Plan: {result['user']['plan']}")
        print(f"   Token: {result['token'][:50]}...")
        
        # Now update the user to enterprise plan
        print(f"\n3. Updating admin to enterprise plan...")
        # We need to manually update the plan since it's an admin user
        # For now, let's just confirm the user was created successfully
        
        # Test the login
        print(f"\n4. Testing admin login...")
        login_result = await emergency_auth.login_user(admin_email, admin_password)
        if login_result['success']:
            print(f"   LOGIN SUCCESS: Admin can now log in!")
            print(f"   Message: {login_result['message']}")
        else:
            print(f"   LOGIN FAILED: {login_result['message']}")
    else:
        print(f"   ERROR: Failed to create admin user")
        print(f"   Message: {result['message']}")

if __name__ == "__main__":
    asyncio.run(create_admin_user())