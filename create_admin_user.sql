-- Create Admin User for TurkLawAI System
-- This script creates the initial admin user with full access

-- Insert admin user subscription
INSERT INTO yargi_mcp_user_subscriptions (
    user_id, 
    email, 
    plan, 
    status, 
    requests_limit,
    requests_used,
    created_at,
    updated_at,
    last_login
) VALUES (
    'user_2qXXXXXXXXXXXXXXXXXXXXXXXX', -- This should match Clerk user ID
    'cenk.tokgoz@gmail.com',
    'enterprise',
    'active',
    999999, -- Unlimited requests for admin
    0,
    NOW(),
    NOW(),
    NOW()
) ON CONFLICT (user_id) DO UPDATE SET
    email = EXCLUDED.email,
    plan = EXCLUDED.plan,
    status = EXCLUDED.status,
    requests_limit = EXCLUDED.requests_limit,
    updated_at = NOW();

-- Create system statistics entry for today if doesn't exist
INSERT INTO yargi_mcp_system_stats (
    stat_date,
    total_users,
    active_users,
    new_users,
    enterprise_users,
    total_requests,
    successful_requests,
    failed_requests,
    daily_revenue_cents,
    new_subscriptions
) VALUES (
    CURRENT_DATE,
    1,
    1,
    1,
    1,
    0,
    0,
    0,
    0,
    1
) ON CONFLICT (stat_date) DO UPDATE SET
    total_users = yargi_mcp_system_stats.total_users + 1,
    enterprise_users = yargi_mcp_system_stats.enterprise_users + 1,
    new_subscriptions = yargi_mcp_system_stats.new_subscriptions + 1,
    updated_at = NOW();

-- Verify the user was created
SELECT 
    user_id,
    email,
    plan,
    status,
    requests_limit,
    created_at
FROM yargi_mcp_user_subscriptions 
WHERE email = 'cenk.tokgoz@gmail.com';

COMMENT ON TABLE yargi_mcp_user_subscriptions IS 'Admin user created for cenk.tokgoz@gmail.com with enterprise plan and unlimited requests';