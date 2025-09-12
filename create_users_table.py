import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def create_users_table():
    schema = os.getenv("YARGI_SCHEMA", "yargi_mcp")
    
    users_table_sql = f"""
CREATE TABLE IF NOT EXISTS {schema}_users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    plan VARCHAR(50) DEFAULT 'free',
    is_active BOOLEAN DEFAULT true,
    email_verified BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{{}}'
);

CREATE INDEX IF NOT EXISTS idx_{schema}_users_email ON {schema}_users(email);

INSERT INTO {schema}_users (email, password_hash, full_name, plan, is_active, email_verified)
SELECT 
    'admin@turklawai.com',
    'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    'TurkLawAI Admin',
    'enterprise',
    true,
    true
WHERE NOT EXISTS (
    SELECT 1 FROM {schema}_users WHERE email = 'admin@turklawai.com'
);
"""
    
    print("TurkLawAI Users Table SQL:")
    print("-" * 60)
    print(users_table_sql)
    print("-" * 60)
    print("Copy-paste this SQL into Supabase SQL Editor")
    print("Default admin: admin@turklawai.com / admin123")

if __name__ == "__main__":
    asyncio.run(create_users_table())
