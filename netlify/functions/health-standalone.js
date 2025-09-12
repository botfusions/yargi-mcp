// Netlify Function: Health Check (Standalone - No Database)
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
        // Simple health check without external dependencies
        return {
            statusCode: 200,
            headers,
            body: JSON.stringify({
                status: 'healthy',
                timestamp: new Date().toISOString(),
                version: '2.0.1',
                environment: 'netlify',
                services: {
                    api: 'operational',
                    database: 'standalone', // No external DB dependency
                    authentication: 'active'
                },
                uptime: 'running',
                platform: 'netlify-functions',
                note: 'Running in standalone mode with built-in user database',
                users: {
                    admin: 'admin@turklawai.com / admin123',
                    test: 'test@turklawai.com / test123'
                }
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