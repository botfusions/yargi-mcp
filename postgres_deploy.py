#!/usr/bin/env python3
"""Direct PostgreSQL connection to Supabase"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def deploy_schema():
    # Supabase PostgreSQL connection string format
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    if not SUPABASE_URL:
        print("ERROR: Missing SUPABASE_URL")
        return False
    
    # Extract host from URL
    host = SUPABASE_URL.replace('https://', '').replace('http://', '')
    
    # Supabase PostgreSQL connection details
    # Format: postgresql://postgres.PROJECT_REF:PASSWORD@aws-0-us-west-1.pooler.supabase.com:5432/postgres
    # For self-hosted: postgresql://postgres:PASSWORD@your-domain.com:5432/postgres
    
    print(f"Connecting to Supabase PostgreSQL at {host}")
    
    # Try different connection methods
    connection_strings = [
        f"postgresql://postgres:postgres@{host}:5432/postgres",
        f"postgresql://postgres:postgres@{host}/postgres",
        f"host={host} port=5432 dbname=postgres user=postgres password=postgres",
    ]
    
    for i, conn_str in enumerate(connection_strings, 1):
        print(f"\nTrying connection method {i}...")
        try:
            conn = psycopg2.connect(conn_str)
            print("Connection successful!")
            
            # Read and execute schema
            with open('database_schema.sql', 'r', encoding='utf-8') as f:
                schema = f.read()
            
            print("Executing schema...")
            cursor = conn.cursor()
            cursor.execute(schema)
            conn.commit()
            
            print("SUCCESS: Schema deployed!")
            
            # Verify tables
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name LIKE 'yargi_mcp_%'
                ORDER BY table_name;
            """)
            tables = cursor.fetchall()
            
            print(f"Created {len(tables)} tables:")
            for table in tables:
                print(f"  - {table[0]}")
            
            cursor.close()
            conn.close()
            return True
            
        except Exception as e:
            print(f"Failed: {e}")
            continue
    
    print("\nAll connection methods failed!")
    print("\nManual steps needed:")
    print("1. Go to Supabase Dashboard > SQL Editor")
    print("2. Copy content from 'database_schema.sql'")
    print("3. Paste and execute")
    return False

if __name__ == "__main__":
    result = deploy_schema()
    print("\nDeployment result:", "SUCCESS" if result else "MANUAL_NEEDED")