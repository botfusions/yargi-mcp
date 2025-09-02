"""
Create yargi_mcp_users table using service role key via REST API
"""
import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

async def create_table_via_rest():
    """Create table using service role key directly via REST"""
    
    supabase_url = os.getenv("SUPABASE_URL")
    service_key = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJzdXBhYmFzZSIsImlhdCI6MTc1NjY1MTM4MCwiZXhwIjo0OTEyMzI0OTgwLCJyb2xlIjoic2VydmljZV9yb2xlIn0.cZoxspdisEpO8BQh-EGiMtOGTqhjnLGzP92Y7IPuCrw"
    
    # First, try to create the table by inserting a dummy record
    # This will force table creation if using auto-schema generation
    
    test_record = {
        "email": "setup@turklawai.com",
        "password_hash": "dummy_hash_for_setup", 
        "full_name": "Setup User",
        "plan": "free",
        "status": "setup",
        "requests_used": 0,
        "requests_limit": 100
    }
    
    try:
        async with httpx.AsyncClient() as client:
            headers = {
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            }
            
            print("Trying to create/test yargi_mcp_users table...")
            
            # Try to insert a record - this might create the table
            response = await client.post(
                f"{supabase_url}/rest/v1/yargi_mcp_users",
                json=test_record,
                headers=headers,
                timeout=30.0
            )
            
            print(f"Insert attempt: HTTP {response.status_code}")
            print(f"Response: {response.text}")
            
            if response.status_code == 201:
                print("SUCCESS: Table created and record inserted!")
                
                # Now clean up the setup record
                cleanup_response = await client.delete(
                    f"{supabase_url}/rest/v1/yargi_mcp_users?email=eq.setup@turklawai.com",
                    headers=headers
                )
                print(f"Cleanup: HTTP {cleanup_response.status_code}")
                return True
                
            elif response.status_code == 404:
                print("Table doesn't exist and auto-creation failed")
                print("Need manual SQL execution")
                return False
                
            else:
                print(f"Unexpected response: {response.status_code}")
                print(f"Body: {response.text}")
                return False
                
    except Exception as e:
        print(f"ERROR: {e}")
        return False

async def test_existing_table():
    """Test if table already exists and is accessible"""
    
    supabase_url = os.getenv("SUPABASE_URL")  
    service_key = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJzdXBhYmFzZSIsImlhdCI6MTc1NjY1MTM4MCwiZXhwIjo0OTEyMzI0OTgwLCJyb2xlIjoic2VydmljZV9yb2xlIn0.cZoxspdisEpO8BQh-EGiMtOGTqhjnLGzP92Y7IPuCrw"
    
    try:
        async with httpx.AsyncClient() as client:
            headers = {
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Content-Type": "application/json"
            }
            
            # Try to query the table
            response = await client.get(
                f"{supabase_url}/rest/v1/yargi_mcp_users?select=*&limit=1",
                headers=headers,
                timeout=10.0
            )
            
            print(f"Table query: HTTP {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"SUCCESS: Table exists with {len(data)} records")
                return True
            elif response.status_code == 404:
                print("Table doesn't exist")
                return False
            else:
                print(f"Error: {response.status_code} - {response.text}")
                return False
                
    except Exception as e:
        print(f"ERROR: {e}")
        return False

async def main():
    """Main function"""
    print("Testing Supabase table with service role key...")
    print("Service Key:", "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...cZoxspdisEpO8BQh-EGiMtOGTqhjnLGzP92Y7IPuCrw"[:50] + "...")
    
    # First test if table exists
    exists = await test_existing_table()
    
    if exists:
        print("\nTable already exists! ✅")
    else:
        print("\nTable doesn't exist. Trying to create it...")
        created = await create_table_via_rest()
        
        if created:
            print("\n✅ SUCCESS: Table created successfully!")
        else:
            print("""
❌ FAILED: Need manual table creation
            
Please execute this SQL in your Supabase SQL Editor:

CREATE TABLE yargi_mcp_users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    plan VARCHAR(50) DEFAULT 'free',
    status VARCHAR(50) DEFAULT 'active',
    requests_used INTEGER DEFAULT 0,
    requests_limit INTEGER DEFAULT 100,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE yargi_mcp_users ENABLE ROW LEVEL SECURITY;

-- Policies  
CREATE POLICY "anon_insert" ON yargi_mcp_users FOR INSERT WITH CHECK (true);
CREATE POLICY "anon_select" ON yargi_mcp_users FOR SELECT USING (true);
CREATE POLICY "service_all" ON yargi_mcp_users FOR ALL USING (auth.role() = 'service_role');
""")

if __name__ == "__main__":
    asyncio.run(main())