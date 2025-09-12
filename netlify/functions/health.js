// Netlify Function: Health Check
const { createClient } = require('@supabase/supabase-js');

// Environment variables
const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

// Initialize Supabase client
const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);

exports.handler = async (event, context) => {
    // CORS headers
    const headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Methods': 'GET, OPTIONS'
    };

    // Handle preflight
    if (event.httpMethod === 'OPTIONS') {
        return {
            statusCode: 200,
            headers,
            body: ''
        };
    }

    // Only GET method allowed
    if (event.httpMethod !== 'GET') {
        return {
            statusCode: 405,
            headers,
            body: JSON.stringify({ error: 'Method not allowed' })
        };
    }

    try {
        // Test database connection
        let dbStatus = 'unknown';
        try {
            const { data, error } = await supabase
                .from('yargi_mcp_users')
                .select('count')
                .limit(1);
            
            dbStatus = error ? `error: ${error.message.slice(0, 50)}` : 'connected';
        } catch (dbError) {
            dbStatus = `error: ${dbError.message.slice(0, 50)}`;
        }

        return {
            statusCode: 200,
            headers,
            body: JSON.stringify({
                status: 'healthy',
                timestamp: new Date().toISOString(),
                version: '2.0.0',
                environment: 'netlify',
                services: {
                    api: 'operational',
                    database: dbStatus,
                    authentication: 'active'
                },
                uptime: 'running',
                platform: 'netlify-functions'
            })
        };

    } catch (error) {
        console.error('Health check error:', error);
        return {
            statusCode: 503,
            headers,
            body: JSON.stringify({
                status: 'unhealthy',
                error: error.message,
                timestamp: new Date().toISOString(),
                platform: 'netlify-functions'
            })
        };
    }
};