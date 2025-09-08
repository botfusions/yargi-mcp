#!/usr/bin/env python3
"""
Supabase Schema Deployment Script
Deploys the complete TurkLawAI database schema to Supabase
"""

import os
import sys
import asyncio
from typing import Dict, Any
import json
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class SupabaseDeployer:
    def __init__(self):
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.service_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        
        if not self.supabase_url or not self.service_key:
            raise ValueError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in environment")
        
        self.headers = {
            'apikey': self.service_key,
            'Authorization': f'Bearer {self.service_key}',
            'Content-Type': 'application/json'
        }
        
        print(f"Connecting to Supabase: {self.supabase_url}")
    
    async def execute_sql(self, sql: str, description: str) -> Dict[str, Any]:
        """Execute SQL command via Supabase REST API"""
        url = f"{self.supabase_url}/rest/v1/rpc/execute_sql"
        
        payload = {
            "sql": sql
        }
        
        try:
            async with httpx.AsyncClient() as client:
                print(f"Running {description}...")
                response = await client.post(
                    url, 
                    headers=self.headers, 
                    json=payload,
                    timeout=60.0
                )
                
                if response.status_code in [200, 201, 204]:
                    print(f"SUCCESS: {description}")
                    try:
                        return response.json() if response.text else {"status": "success"}
                    except:
                        return {"status": "success", "message": "No JSON response"}
                else:
                    print(f"❌ {description} - FAILED")
                    print(f"   Status: {response.status_code}")
                    print(f"   Response: {response.text}")
                    return {"error": response.text, "status_code": response.status_code}
                    
        except Exception as e:
            print(f"❌ {description} - ERROR: {str(e)}")
            return {"error": str(e)}
    
    async def execute_sql_direct(self, sql: str, description: str) -> Dict[str, Any]:
        """Execute SQL directly via Supabase SQL endpoint"""
        url = f"{self.supabase_url}/sql"
        
        try:
            async with httpx.AsyncClient() as client:
                print(f"🔧 {description}...")
                response = await client.post(
                    url, 
                    headers={
                        'apikey': self.service_key,
                        'Authorization': f'Bearer {self.service_key}',
                        'Content-Type': 'text/plain'
                    },
                    content=sql,
                    timeout=120.0
                )
                
                if response.status_code in [200, 201, 204]:
                    print(f"✅ {description} - SUCCESS")
                    return {"status": "success", "result": response.text}
                else:
                    print(f"❌ {description} - FAILED")
                    print(f"   Status: {response.status_code}")
                    print(f"   Response: {response.text}")
                    return {"error": response.text, "status_code": response.status_code}
                    
        except Exception as e:
            print(f"❌ {description} - ERROR: {str(e)}")
            return {"error": str(e)}
    
    async def check_connection(self) -> bool:
        """Test Supabase connection"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.supabase_url}/rest/v1/",
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    print("✅ Supabase connection successful")
                    return True
                else:
                    print(f"❌ Supabase connection failed: {response.status_code}")
                    return False
                    
        except Exception as e:
            print(f"❌ Supabase connection error: {str(e)}")
            return False
    
    async def deploy_schema(self):
        """Deploy the complete database schema"""
        print("🚀 Starting Supabase Schema Deployment")
        print("=" * 50)
        
        # Check connection
        if not await self.check_connection():
            print("❌ Cannot connect to Supabase. Deployment aborted.")
            return False
        
        # Read schema file
        try:
            with open('database_schema.sql', 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            print("✅ Schema file loaded successfully")
        except Exception as e:
            print(f"❌ Cannot read schema file: {str(e)}")
            return False
        
        # Split schema into manageable chunks
        sql_statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
        
        print(f"📊 Found {len(sql_statements)} SQL statements to execute")
        
        # Execute schema
        success_count = 0
        for i, statement in enumerate(sql_statements, 1):
            if not statement:
                continue
                
            # Skip comments
            if statement.startswith('--') or statement.startswith('COMMENT'):
                continue
            
            description = f"Executing statement {i}/{len(sql_statements)}"
            if 'CREATE TABLE' in statement:
                table_name = statement.split('CREATE TABLE IF NOT EXISTS')[1].split('(')[0].strip()
                description = f"Creating table: {table_name}"
            elif 'CREATE INDEX' in statement:
                description = f"Creating index ({i}/{len(sql_statements)})"
            elif 'CREATE OR REPLACE FUNCTION' in statement:
                description = f"Creating function ({i}/{len(sql_statements)})"
            elif 'CREATE TRIGGER' in statement:
                description = f"Creating trigger ({i}/{len(sql_statements)})"
            elif 'CREATE OR REPLACE VIEW' in statement:
                description = f"Creating view ({i}/{len(sql_statements)})"
            elif 'ALTER TABLE' in statement:
                description = f"Altering table ({i}/{len(sql_statements)})"
            
            result = await self.execute_sql_direct(statement + ';', description)
            
            if 'error' not in result:
                success_count += 1
            else:
                # Some errors are expected (e.g., table already exists)
                if any(msg in str(result.get('error', '')).lower() for msg in ['already exists', 'duplicate']):
                    print(f"⚠️  {description} - Already exists (skipped)")
                    success_count += 1
                else:
                    print(f"❌ {description} - Failed: {result.get('error', 'Unknown error')}")
        
        print("=" * 50)
        print(f"📊 Deployment Summary:")
        print(f"   Total statements: {len(sql_statements)}")
        print(f"   Successful: {success_count}")
        print(f"   Failed: {len(sql_statements) - success_count}")
        
        if success_count > 0:
            print("✅ Schema deployment completed successfully!")
            return True
        else:
            print("❌ Schema deployment failed!")
            return False
    
    async def list_tables(self):
        """List all tables in the database"""
        sql = """
        SELECT table_name, table_type 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name LIKE 'yargi_mcp_%'
        ORDER BY table_name;
        """
        
        result = await self.execute_sql_direct(sql, "Listing database tables")
        
        if 'error' not in result:
            print("📋 Database Tables:")
            print(result.get('result', 'No tables found'))
        else:
            print(f"❌ Cannot list tables: {result.get('error')}")

async def main():
    """Main deployment function"""
    deployer = SupabaseDeployer()
    
    print("🏛️ TurkLawAI Database Schema Deployment")
    print("=====================================")
    
    # Deploy schema
    success = await deployer.deploy_schema()
    
    if success:
        print("\n🔍 Verifying deployment...")
        await deployer.list_tables()
        
        print("\n🎉 Next steps:")
        print("1. ✅ Schema deployed successfully")
        print("2. 🔄 Run create_admin_user.sql script")
        print("3. 👤 Create user in Clerk Dashboard")
        print("4. 🧪 Test admin dashboard access")
    else:
        print("\n❌ Deployment failed. Please check the errors above.")
    
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)