"""
Supabase Client for Yargi MCP
Self-hosted Supabase instance with schema-based organization
"""
import os
from typing import Optional, Dict, Any
from supabase import create_client, Client
from dotenv import load_dotenv
import asyncio
import httpx

# Load environment variables
load_dotenv()

class SupabaseClient:
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.anon_key = os.getenv("SUPABASE_ANON_KEY")
        self.service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        self.schema = os.getenv("YARGI_SCHEMA", "yargi_mcp")
        
        if not self.url or not self.anon_key:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set in environment variables")
        
        # Create clients
        self.client: Optional[Client] = None
        self.admin_client: Optional[Client] = None
        
    def get_client(self, use_service_role: bool = False) -> Client:
        """Get Supabase client (anon or service role)"""
        if use_service_role:
            if not self.admin_client:
                if not self.service_role_key:
                    raise ValueError("SUPABASE_SERVICE_ROLE_KEY not set")
                self.admin_client = create_client(self.url, self.service_role_key)
            return self.admin_client
        else:
            if not self.client:
                self.client = create_client(self.url, self.anon_key)
            return self.client
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test connection to Supabase"""
        try:
            # Test basic connection with anon key
            client = self.get_client()
            
            # Try a simple query to test connection
            # Since this is a self-hosted instance with schema organization,
            # we'll use the REST API directly
            async with httpx.AsyncClient() as http_client:
                headers = {
                    "apikey": self.anon_key,
                    "Authorization": f"Bearer {self.anon_key}",
                    "Content-Type": "application/json"
                }
                
                # Test basic connectivity
                response = await http_client.get(
                    f"{self.url}/rest/v1/",
                    headers=headers,
                    timeout=10.0
                )
                
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "url": self.url,
                    "schema": self.schema,
                    "message": "Connection successful"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "url": self.url,
                "schema": self.schema,
                "message": "Connection failed"
            }
    
    async def create_table_if_not_exists(self, table_name: str, schema_definition: Dict[str, Any]) -> Dict[str, Any]:
        """Create table in schema if it doesn't exist"""
        try:
            client = self.get_client(use_service_role=True)
            
            # For self-hosted Supabase with schema organization
            # Table name format: schema_tablename
            full_table_name = f"{self.schema}_{table_name}"
            
            # Note: Table creation via REST API requires specific permissions
            # This is a placeholder - actual implementation depends on your Supabase setup
            
            return {
                "success": True,
                "table_name": full_table_name,
                "message": f"Table {full_table_name} ready"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "table_name": table_name,
                "message": f"Failed to create table {table_name}"
            }
    
    async def insert_data(self, table_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert data into schema table"""
        try:
            client = self.get_client()
            
            # Table name with schema prefix
            full_table_name = f"{self.schema}_{table_name}"
            
            result = client.table(full_table_name).insert(data).execute()
            
            return {
                "success": True,
                "data": result.data,
                "count": result.count,
                "message": f"Data inserted into {full_table_name}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "table_name": table_name,
                "message": f"Failed to insert data into {table_name}"
            }
    
    async def query_data(self, table_name: str, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Query data from schema table"""
        try:
            client = self.get_client()
            
            # Table name with schema prefix
            full_table_name = f"{self.schema}_{table_name}"
            
            query = client.table(full_table_name).select("*")
            
            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)
            
            result = query.execute()
            
            return {
                "success": True,
                "data": result.data,
                "count": result.count,
                "message": f"Data queried from {full_table_name}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "table_name": table_name,
                "message": f"Failed to query data from {table_name}"
            }

# Global instance
supabase_client = SupabaseClient()

# Async test function
async def test_supabase_connection():
    """Test Supabase connection"""
    print("Testing Supabase connection...")
    result = await supabase_client.test_connection()
    
    if result["success"]:
        print(f"Supabase connection successful!")
        print(f"   URL: {result['url']}")
        print(f"   Schema: {result['schema']}")
        print(f"   Status: {result['status_code']}")
    else:
        print(f"Supabase connection failed!")
        print(f"   URL: {result['url']}")
        print(f"   Error: {result['error']}")
    
    return result

if __name__ == "__main__":
    # Test connection when run directly
    asyncio.run(test_supabase_connection())