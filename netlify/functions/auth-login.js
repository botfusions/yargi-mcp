// Netlify Function: Authentication Login
const { createClient } = require('@supabase/supabase-js');
const jwt = require('jsonwebtoken');
const crypto = require('crypto');

// Environment variables
const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;
const JWT_SECRET = process.env.JWT_SECRET_KEY || 'turklawai-emergency-jwt-key-2025';

// Initialize Supabase client
const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);

// Hash password function
function hashPassword(password) {
    return crypto.createHash('sha256').update(password + 'turklawai_salt').digest('hex');
}

// Create JWT token
function createJWTToken(user) {
    const payload = {
        user_id: user.id,
        email: user.email,
        full_name: user.full_name || '',
        plan: user.plan || 'free',
        exp: Math.floor(Date.now() / 1000) + (24 * 60 * 60), // 24 hours
        iat: Math.floor(Date.now() / 1000)
    };
    return jwt.sign(payload, JWT_SECRET, { algorithm: 'HS256' });
}

exports.handler = async (event, context) => {
    // CORS headers
    const headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Methods': 'POST, OPTIONS'
    };

    // Handle preflight
    if (event.httpMethod === 'OPTIONS') {
        return {
            statusCode: 200,
            headers,
            body: ''
        };
    }

    // Only POST method allowed
    if (event.httpMethod !== 'POST') {
        return {
            statusCode: 405,
            headers,
            body: JSON.stringify({ error: 'Method not allowed' })
        };
    }

    try {
        // Parse request body
        const { email, password } = JSON.parse(event.body);

        if (!email || !password) {
            return {
                statusCode: 400,
                headers,
                body: JSON.stringify({ 
                    success: false, 
                    message: 'Email ve şifre gerekli' 
                })
            };
        }

        // Query user from Supabase
        const { data: users, error } = await supabase
            .from('yargi_mcp_users')
            .select('*')
            .eq('email', email)
            .limit(1);

        if (error) {
            console.error('Supabase error:', error);
            return {
                statusCode: 500,
                headers,
                body: JSON.stringify({ 
                    success: false, 
                    message: 'Database hatası' 
                })
            };
        }

        if (!users || users.length === 0) {
            return {
                statusCode: 401,
                headers,
                body: JSON.stringify({ 
                    success: false, 
                    message: 'Kullanıcı bulunamadı' 
                })
            };
        }

        const user = users[0];

        // Verify password
        const hashedPassword = hashPassword(password);
        if (hashedPassword !== user.password_hash) {
            return {
                statusCode: 401,
                headers,
                body: JSON.stringify({ 
                    success: false, 
                    message: 'Şifre yanlış' 
                })
            };
        }

        // Check if user is active
        if (user.status !== 'active') {
            return {
                statusCode: 401,
                headers,
                body: JSON.stringify({ 
                    success: false, 
                    message: 'Hesap aktif değil' 
                })
            };
        }

        // Create JWT token
        const token = createJWTToken(user);

        // Return successful response
        return {
            statusCode: 200,
            headers,
            body: JSON.stringify({
                success: true,
                message: 'Giriş başarılı',
                user: {
                    id: user.id,
                    email: user.email,
                    full_name: user.full_name,
                    plan: user.plan,
                    status: user.status
                },
                token: token
            })
        };

    } catch (error) {
        console.error('Login error:', error);
        return {
            statusCode: 500,
            headers,
            body: JSON.stringify({ 
                success: false, 
                message: `Authentication error: ${error.message}` 
            })
        };
    }
};