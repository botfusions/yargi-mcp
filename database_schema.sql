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
-- SEARCH QUERIES TABLE (Enhanced)
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
-- SEARCH RESULTS TABLE (Enhanced)
-- ========================================
CREATE TABLE IF NOT EXISTS yargi_mcp_search_results (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    query_id UUID NOT NULL,
    
    -- Result data
    results JSONB NOT NULL, -- Full result set
    total_count INTEGER DEFAULT 0,
    page_number INTEGER DEFAULT 1,
    page_size INTEGER DEFAULT 10,
    
    -- Caching
    cache_key TEXT,
    expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '1 hour'),
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Foreign key
    FOREIGN KEY (query_id) REFERENCES yargi_mcp_search_queries(id) ON DELETE CASCADE
);

-- Index for cache lookups
CREATE INDEX IF NOT EXISTS idx_search_results_query_id ON yargi_mcp_search_results(query_id);
CREATE INDEX IF NOT EXISTS idx_search_results_cache_key ON yargi_mcp_search_results(cache_key);

-- ========================================
-- DOCUMENT ACCESS TABLE
-- ========================================
CREATE TABLE IF NOT EXISTS yargi_mcp_document_access (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id TEXT,
    document_id TEXT NOT NULL,
    document_type TEXT NOT NULL, -- yargitay, danistay, emsal, etc.
    
    -- Document details
    document_title TEXT,
    document_url TEXT,
    document_size INTEGER, -- Size in characters
    
    -- Access tracking
    access_count INTEGER DEFAULT 1,
    last_accessed_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Metadata
    ip_address INET,
    user_agent TEXT,
    
    -- Foreign key
    FOREIGN KEY (user_id) REFERENCES yargi_mcp_user_subscriptions(user_id) ON DELETE SET NULL,
    
    -- Unique constraint to prevent duplicates
    UNIQUE(user_id, document_id, document_type)
);

-- Indexes for document analytics
CREATE INDEX IF NOT EXISTS idx_document_access_user_id ON yargi_mcp_document_access(user_id);
CREATE INDEX IF NOT EXISTS idx_document_access_document ON yargi_mcp_document_access(document_id, document_type);

-- ========================================
-- API KEYS TABLE (for API access)
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
-- BILLING HISTORY TABLE
-- ========================================
CREATE TABLE IF NOT EXISTS yargi_mcp_billing_history (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id TEXT NOT NULL,
    
    -- Stripe information
    stripe_invoice_id TEXT UNIQUE,
    stripe_payment_intent_id TEXT,
    stripe_subscription_id TEXT,
    
    -- Billing details
    amount_cents INTEGER NOT NULL, -- Amount in cents
    currency TEXT DEFAULT 'USD',
    plan TEXT NOT NULL,
    billing_period_start TIMESTAMPTZ NOT NULL,
    billing_period_end TIMESTAMPTZ NOT NULL,
    
    -- Status
    status TEXT DEFAULT 'pending', -- pending, paid, failed, refunded
    paid_at TIMESTAMPTZ,
    
    -- Usage during billing period
    total_requests INTEGER DEFAULT 0,
    overage_requests INTEGER DEFAULT 0,
    overage_amount_cents INTEGER DEFAULT 0,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Foreign key
    FOREIGN KEY (user_id) REFERENCES yargi_mcp_user_subscriptions(user_id) ON DELETE CASCADE,
    
    -- Constraints
    CONSTRAINT valid_billing_status CHECK (status IN ('pending', 'paid', 'failed', 'refunded'))
);

-- Index for billing lookups
CREATE INDEX IF NOT EXISTS idx_billing_history_user_id ON yargi_mcp_billing_history(user_id);
CREATE INDEX IF NOT EXISTS idx_billing_history_stripe_invoice ON yargi_mcp_billing_history(stripe_invoice_id);

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

CREATE TRIGGER update_billing_history_updated_at 
    BEFORE UPDATE ON yargi_mcp_billing_history 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to reset monthly usage
CREATE OR REPLACE FUNCTION reset_monthly_usage()
RETURNS void AS $$
BEGIN
    UPDATE yargi_mcp_user_subscriptions 
    SET 
        requests_used = 0,
        last_reset_date = NOW(),
        billing_period_start = NOW(),
        billing_period_end = NOW() + INTERVAL '30 days'
    WHERE 
        billing_period_end < NOW() 
        AND status = 'active';
END;
$$ LANGUAGE plpgsql;

-- ========================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ========================================

-- Enable RLS on sensitive tables
ALTER TABLE yargi_mcp_user_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE yargi_mcp_usage_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE yargi_mcp_search_queries ENABLE ROW LEVEL SECURITY;
ALTER TABLE yargi_mcp_api_keys ENABLE ROW LEVEL SECURITY;

-- Example RLS policies (customize based on your authentication system)
-- Users can only see their own data
CREATE POLICY "Users can view own subscription" ON yargi_mcp_user_subscriptions 
    FOR SELECT USING (auth.uid()::text = user_id);

CREATE POLICY "Users can view own usage logs" ON yargi_mcp_usage_logs 
    FOR SELECT USING (auth.uid()::text = user_id);

CREATE POLICY "Users can view own search queries" ON yargi_mcp_search_queries 
    FOR SELECT USING (auth.uid()::text = user_id);

CREATE POLICY "Users can view own API keys" ON yargi_mcp_api_keys 
    FOR SELECT USING (auth.uid()::text = user_id);

-- ========================================
-- INITIAL DATA
-- ========================================

-- Insert system admin user (optional)
-- INSERT INTO yargi_mcp_user_subscriptions (
--     user_id, email, plan, status, requests_limit
-- ) VALUES (
--     'admin', 'admin@turklawai.com', 'enterprise', 'active', 999999
-- ) ON CONFLICT (user_id) DO NOTHING;

-- ========================================
-- VIEWS FOR ANALYTICS
-- ========================================

-- Daily usage summary view
CREATE OR REPLACE VIEW yargi_mcp_daily_usage_summary AS
SELECT 
    DATE(timestamp) as usage_date,
    user_id,
    COUNT(*) as total_requests,
    COUNT(*) FILTER (WHERE success = true) as successful_requests,
    COUNT(*) FILTER (WHERE success = false) as failed_requests,
    AVG(response_time_ms) as avg_response_time,
    COUNT(DISTINCT endpoint) as unique_endpoints_used
FROM yargi_mcp_usage_logs 
GROUP BY DATE(timestamp), user_id;

-- Popular endpoints view
CREATE OR REPLACE VIEW yargi_mcp_popular_endpoints AS
SELECT 
    endpoint,
    COUNT(*) as total_requests,
    COUNT(DISTINCT user_id) as unique_users,
    AVG(response_time_ms) as avg_response_time,
    COUNT(*) FILTER (WHERE success = true) as successful_requests,
    (COUNT(*) FILTER (WHERE success = true)::float / COUNT(*)::float * 100) as success_rate
FROM yargi_mcp_usage_logs 
WHERE timestamp >= NOW() - INTERVAL '30 days'
GROUP BY endpoint 
ORDER BY total_requests DESC;

-- User activity summary view
CREATE OR REPLACE VIEW yargi_mcp_user_activity_summary AS
SELECT 
    us.user_id,
    us.email,
    us.plan,
    us.status,
    us.requests_used,
    us.requests_limit,
    us.created_at as subscription_created,
    ul.last_activity,
    ul.total_requests_30d,
    ul.avg_daily_requests
FROM yargi_mcp_user_subscriptions us
LEFT JOIN (
    SELECT 
        user_id,
        MAX(timestamp) as last_activity,
        COUNT(*) as total_requests_30d,
        COUNT(*)::float / 30.0 as avg_daily_requests
    FROM yargi_mcp_usage_logs 
    WHERE timestamp >= NOW() - INTERVAL '30 days'
    GROUP BY user_id
) ul ON us.user_id = ul.user_id;

COMMENT ON TABLE yargi_mcp_user_subscriptions IS 'Main subscription management table for TurkLawAI users';
COMMENT ON TABLE yargi_mcp_usage_logs IS 'Detailed API usage logs for billing and analytics';
COMMENT ON TABLE yargi_mcp_search_queries IS 'Search query history with enhanced metadata';
COMMENT ON TABLE yargi_mcp_search_results IS 'Cached search results for performance';
COMMENT ON TABLE yargi_mcp_document_access IS 'Document access tracking for analytics';
COMMENT ON TABLE yargi_mcp_api_keys IS 'API key management for programmatic access';
COMMENT ON TABLE yargi_mcp_billing_history IS 'Complete billing and payment history';
COMMENT ON TABLE yargi_mcp_system_stats IS 'Daily system-wide statistics for monitoring';