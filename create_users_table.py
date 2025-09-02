"""
Create yargi_mcp_users table in Supabase
"""
import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

async def create_users_table():
    """Create users table using SQL"""
    
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url or not service_role_key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        return False
    
    # SQL to create users table
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS yargi_mcp_users (
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
    
    -- Create index on email for faster lookups
    CREATE INDEX IF NOT EXISTS idx_yargi_mcp_users_email ON yargi_mcp_users(email);
    
    -- Enable RLS (Row Level Security)
    ALTER TABLE yargi_mcp_users ENABLE ROW LEVEL SECURITY;
    
    -- Create policy to allow service role full access
    CREATE POLICY IF NOT EXISTS "Service role can manage users" ON yargi_mcp_users
    FOR ALL USING (auth.role() = 'service_role');
    
    -- Create policy to allow anon role to select and insert (for registration/login)
    CREATE POLICY IF NOT EXISTS "Anon can register users" ON yargi_mcp_users
    FOR INSERT WITH CHECK (true);
    
    CREATE POLICY IF NOT EXISTS "Anon can read users for auth" ON yargi_mcp_users
    FOR SELECT USING (true);
    """
    
    try:
        async with httpx.AsyncClient() as client:
            headers = {
                "apikey": service_role_key,
                "Authorization": f"Bearer {service_role_key}",
                "Content-Type": "application/json"
            }
            
            # Execute SQL using Supabase REST API
            response = await client.post(
                f"{supabase_url}/rest/v1/rpc/exec_sql",
                json={"sql": create_table_sql},
                headers=headers,
                timeout=30.0
            )
            
            if response.status_code == 200:
                print("SUCCESS: yargi_mcp_users table created successfully!")
                print("Table includes:")
                print("- id (Primary Key)")
                print("- email (Unique)")
                print("- password_hash")
                print("- full_name")
                print("- plan (default: 'free')")
                print("- status (default: 'active')")
                print("- requests_used (default: 0)")
                print("- requests_limit (default: 100)")
                print("- created_at, updated_at")
                print("- Row Level Security enabled")
                return True
            else:
                print(f"FAILED: HTTP {response.status_code}")
                print(f"Response: {response.text}")
                
                # Try alternative approach with direct SQL endpoint
                print("\nTrying alternative SQL endpoint...")
                response2 = await client.post(
                    f"{supabase_url}/sql",
                    data=create_table_sql,
                    headers={
                        "apikey": service_role_key,
                        "Authorization": f"Bearer {service_role_key}",
                        "Content-Type": "application/sql"
                    },
                    timeout=30.0
                )
                
                if response2.status_code == 200:
                    print("SUCCESS: Table created via SQL endpoint!")
                    return True
                else:
                    print(f"Alternative also failed: HTTP {response2.status_code}")
                    print(f"Response: {response2.text}")
                    return False
                
    except Exception as e:
        print(f"ERROR: {e}")
        return False

async def test_table_creation():
    """Test the created table"""
    from supabase_client import supabase_client
    
    print("\nTesting created table...")
    result = await supabase_client.query_data('users')
    
    if result["success"]:
        print("SUCCESS: Table is accessible!")
        print(f"Current users: {len(result['data'])}")
        return True
    else:
        print(f"FAILED: {result['error']}")
        return False

async def main():
    """Main function"""
    print("Creating yargi_mcp_users table in Supabase...")
    
    # Create table
    table_created = await create_users_table()
    
    if table_created:
        # Test table
        await asyncio.sleep(1)  # Wait a bit for table to be ready
        await test_table_creation()
        
        print("""
Next steps:
1. Table is ready for use
2. You can now restart the backend server
3. Test user registration and login
""")
    else:
        print("""
Manual SQL needed:
Please run this SQL in your Supabase dashboard:

CREATE TABLE IF NOT EXISTS yargi_mcp_users (
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
""")

if __name__ == "__main__":
    asyncio.run(main())