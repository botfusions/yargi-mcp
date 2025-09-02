"""
Simple user registration test without database
Creates a test user account for TurkLawAI
"""

import asyncio
import aiohttp
import json

async def create_test_user():
    """Create a test user account"""
    
    # Test data
    test_user = {
        "email": "test@turklawai.com",
        "password": "testpassword123", 
        "full_name": "Test User TurkLawAI"
    }
    
    print("Creating test user for TurkLawAI...")
    print(f"Email: {test_user['email']}")
    print(f"Password: {test_user['password']}")
    print(f"Full Name: {test_user['full_name']}")
    
    try:
        async with aiohttp.ClientSession() as session:
            # Try registration
            async with session.post('http://localhost:8002/auth/register', json=test_user) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"\nSUCCESS: User registered!")
                    print(f"User ID: {data['user']['id']}")
                    print(f"Plan: {data['user']['plan']}")
                    print(f"JWT Token: {data['token'][:50]}...")
                    
                    # Save token for frontend use
                    with open('.env.local', 'w') as f:
                        f.write(f"""# TurkLawAI API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8002
NEXT_PUBLIC_JWT_TOKEN={data['token']}

# Authentication enabled for testing
NEXT_PUBLIC_AUTH_ENABLED=true

# User info for frontend
NEXT_PUBLIC_USER_EMAIL={test_user['email']}
NEXT_PUBLIC_USER_NAME={test_user['full_name']}
""")
                    print("\nToken saved to .env.local for frontend")
                    
                    return data
                    
                else:
                    error = await resp.json()
                    print(f"\nRegistration failed: {error.get('detail')}")
                    
                    # If user exists, try login
                    if "already exists" in error.get('detail', ''):
                        print("\nTrying login instead...")
                        login_data = {"email": test_user["email"], "password": test_user["password"]}
                        
                        async with session.post('http://localhost:8002/auth/login', json=login_data) as login_resp:
                            if login_resp.status == 200:
                                data = await login_resp.json()
                                print(f"Login successful!")
                                print(f"Token: {data['token'][:50]}...")
                                return data
                            else:
                                login_error = await login_resp.json()
                                print(f"Login failed: {login_error.get('detail')}")
                    
                    return None
                    
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    result = asyncio.run(create_test_user())
    
    if result:
        print(f"""
Test user created successfully!

Login credentials:
  Email: test@turklawai.com
  Password: testpassword123

You can now:
1. Visit http://localhost:3000
2. Use these credentials to login
3. Start using TurkLawAI platform

The JWT token has been saved to .env.local for development.
""")
    else:
        print("""
Failed to create test user.
Check if the API server is running on port 8002 and database is configured.
""")