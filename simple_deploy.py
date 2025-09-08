#!/usr/bin/env python3
"""Simple Supabase Schema Deployment"""

import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

async def deploy_schema():
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SERVICE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    if not SUPABASE_URL or not SERVICE_KEY:
        print("ERROR: Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
        return False
    
    print(f"Connecting to: {SUPABASE_URL}")
    
    # Read schema
    try:
        with open('database_schema.sql', 'r', encoding='utf-8') as f:
            schema = f.read()
        print("Schema file loaded successfully")
    except Exception as e:
        print(f"Cannot read schema: {e}")
        return False
    
    # Execute via SQL endpoint
    headers = {
        'apikey': SERVICE_KEY,
        'Authorization': f'Bearer {SERVICE_KEY}',
        'Content-Type': 'text/plain'
    }
    
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            print("Executing schema...")
            response = await client.post(
                f"{SUPABASE_URL}/sql",
                headers=headers,
                content=schema
            )
            
            if response.status_code in [200, 201, 204]:
                print("SUCCESS: Schema deployed!")
                print("Response:", response.text[:500])
                return True
            else:
                print(f"FAILED: Status {response.status_code}")
                print("Error:", response.text)
                return False
                
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(deploy_schema())
    print("Deployment result:", "SUCCESS" if result else "FAILED")