-- Update admin user with real Clerk user ID
-- Real Clerk User ID: user_32KOCwWfWIwvQTgfdI3T7QDsJya

UPDATE yargi_mcp_user_subscriptions 
SET user_id = 'user_32KOCwWfWIwvQTgfdI3T7QDsJya'  
WHERE email = 'cenk.tokgoz@gmail.com';

-- Verify the update
SELECT 
    user_id,
    email,
    plan,
    status,
    requests_limit,
    created_at,
    updated_at
FROM yargi_mcp_user_subscriptions 
WHERE email = 'cenk.tokgoz@gmail.com';

-- Show confirmation message
SELECT 'Admin user successfully updated with real Clerk user ID' as status;