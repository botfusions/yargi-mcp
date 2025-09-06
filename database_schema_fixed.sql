-- TurkLawAI Subscription System Database Schema
-- Self-hosted Supabase with schema-based organization
-- Tables will be created as: yargi_mcp_[table_name]

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ========================================
-- USER SUBSCRIPTIONS TABLE
-- ========================================
CREATE TABLE IF NOT EXISTS yargi_mcp_user_subscriptions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE, -- Clerk user ID
    email TEXT NOT NULL,
    plan TEXT NOT NULL DEFAULT 'free', -- free, basic, professional, enterprise
    status TEXT NOT NULL DEFAULT 'active', -- active, cancelled, expired, suspended
    
    -- Usage tracking
    requests_used INTEGER DEFAULT 0,
    requests_limit INTEGER DEFAULT 100,
    last_reset_date TIMESTAMPTZ DEFAULT NOW(),
    
    -- Billing information
    billing_period_start TIMESTAMPTZ DEFAULT NOW(),
    billing_period_end TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '30 days'),
    
    -- Stripe integration
    stripe_customer_id TEXT UNIQUE,
    stripe_subscription_id TEXT UNIQUE,
    stripe_payment_method_id TEXT,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_login TIMESTAMPTZ,
    
    -- Indexes
    CONSTRAINT valid_plan CHECK (plan IN ('free', 'basic', 'professional', 'enterprise')),
    CONSTRAINT valid_status CHECK (status IN ('active', 'cancelled', 'expired', 'suspended'))
);

-- Index for fast user lookups
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user_id ON yargi_mcp_user_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_email ON yargi_mcp_user_subscriptions(email);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_stripe_customer ON yargi_mcp_user_subscriptions(stripe_customer_id);

-- ========================================
-- USAGE LOGS TABLE
-- ========================================
CREATE TABLE IF NOT EXISTS yargi_mcp_usage_logs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id TEXT NOT NULL,
    endpoint TEXT NOT NULL, -- /search/yargitay, /search/danistay, etc.
    method TEXT DEFAULT 'POST', -- HTTP method
    
    -- Request details
    query_params JSONB, -- Search parameters used
    response_size INTEGER, -- Response size in bytes
    response_time_ms INTEGER, -- Response time in milliseconds
    
    -- Status
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    http_status_code INTEGER DEFAULT 200,
    
    -- Metadata
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    ip_address INET,
    user_agent TEXT,
    
    -- Foreign key
    FOREIGN KEY (user_id) REFERENCES yargi_mcp_user_subscriptions(user_id) ON DELETE CASCADE
);

-- Indexes for analytics and rate limiting
CREATE INDEX IF NOT EXISTS idx_usage_logs_user_id ON yargi_mcp_usage_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_usage_logs_timestamp ON yargi_mcp_usage_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_usage_logs_endpoint ON yargi_mcp_usage_logs(endpoint);
CREATE INDEX IF NOT EXISTS idx_usage_logs_user_timestamp ON yargi_mcp_usage_logs(user_id, timestamp);

-- ========================================
-- SEARCH QUERIES TABLE
-- ========================================
CREATE TABLE IF NOT EXISTS yargi_mcp_search_queries (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id TEXT,
    query_text TEXT NOT NULL,
    search_type TEXT NOT NULL, -- yargitay, danistay, emsal, etc.
    
    -- Enhanced query details
    filters JSONB, -- Advanced filters used (daire, tarih, etc.)
    results_count INTEGER DEFAULT 0,
    total_results INTEGER DEFAULT 0,
    
    -- Performance metrics
    execution_time_ms INTEGER,
    cache_hit BOOLEAN DEFAULT false,
    
    -- Status and metadata
    status TEXT DEFAULT 'completed', -- pending, completed, failed
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Analytics
    ip_address INET,
    user_agent TEXT,
    
    -- Foreign key
    FOREIGN KEY (user_id) REFERENCES yargi_mcp_user_subscriptions(user_id) ON DELETE SET NULL
);

-- Indexes for search analytics
CREATE INDEX IF NOT EXISTS idx_search_queries_user_id ON yargi_mcp_search_queries(user_id);
CREATE INDEX IF NOT EXISTS idx_search_queries_type ON yargi_mcp_search_queries(search_type);
CREATE INDEX IF NOT EXISTS idx_search_queries_created ON yargi_mcp_search_queries(created_at);

-- ========================================
-- API KEYS TABLE
-- ========================================
CREATE TABLE IF NOT EXISTS yargi_mcp_api_keys (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id TEXT NOT NULL,
    key_name TEXT NOT NULL,
    api_key TEXT NOT NULL UNIQUE,
    api_key_hash TEXT NOT NULL, -- Bcrypt hash of the key
    
    -- Permissions
    scopes TEXT[] DEFAULT ARRAY['search'], -- Array of allowed operations
    rate_limit_override INTEGER, -- Custom rate limit for this key
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Foreign key
    FOREIGN KEY (user_id) REFERENCES yargi_mcp_user_subscriptions(user_id) ON DELETE CASCADE
);

-- Index for API key lookups
CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON yargi_mcp_api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON yargi_mcp_api_keys(api_key_hash);

-- ========================================
-- SYSTEM STATISTICS TABLE
-- ========================================
CREATE TABLE IF NOT EXISTS yargi_mcp_system_stats (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    stat_date DATE NOT NULL DEFAULT CURRENT_DATE,
    
    -- Usage statistics
    total_users INTEGER DEFAULT 0,
    active_users INTEGER DEFAULT 0, -- Users who made requests today
    new_users INTEGER DEFAULT 0,
    
    -- Plan distribution
    free_users INTEGER DEFAULT 0,
    basic_users INTEGER DEFAULT 0,
    professional_users INTEGER DEFAULT 0,
    enterprise_users INTEGER DEFAULT 0,
    
    -- Request statistics
    total_requests INTEGER DEFAULT 0,
    successful_requests INTEGER DEFAULT 0,
    failed_requests INTEGER DEFAULT 0,
    avg_response_time_ms FLOAT DEFAULT 0,
    
    -- Revenue statistics
    daily_revenue_cents INTEGER DEFAULT 0,
    new_subscriptions INTEGER DEFAULT 0,
    cancelled_subscriptions INTEGER DEFAULT 0,
    
    -- Popular endpoints
    top_endpoints JSONB, -- {"endpoint": "/search/yargitay", "count": 1234}
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Unique constraint on date
    UNIQUE(stat_date)
);

-- Index for date-based queries
CREATE INDEX IF NOT EXISTS idx_system_stats_date ON yargi_mcp_system_stats(stat_date);

-- ========================================
-- FUNCTIONS AND TRIGGERS
-- ========================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
CREATE TRIGGER update_user_subscriptions_updated_at 
    BEFORE UPDATE ON yargi_mcp_user_subscriptions 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_api_keys_updated_at 
    BEFORE UPDATE ON yargi_mcp_api_keys 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();