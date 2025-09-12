// Netlify Function: Authentication Login with SQLite
const crypto = require('crypto');
const jwt = require('jsonwebtoken');

// Environment variables
const JWT_SECRET = process.env.JWT_SECRET_KEY || 'turklawai-emergency-jwt-key-2025';

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

// Mock database (replace with real DB later)
const MOCK_USERS = {
    'admin@turklawai.com': {
        id: 1,
        email: 'admin@turklawai.com',
        password_hash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', // admin123
        full_name: 'TurkLawAI Admin',
        plan: 'enterprise',
        status: 'active'
    },
    'test@turklawai.com': {
        id: 2,
        email: 'test@turklawai.com', 
        password_hash: '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08', // test123
        full_name: 'Test User',
        plan: 'free',
        status: 'active'
    }
};

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

        // Find user in mock database
        const user = MOCK_USERS[email.toLowerCase()];
        
        if (!user) {
            return {
                statusCode: 401,
                headers,
                body: JSON.stringify({ 
                    success: false, 
                    message: 'Kullanıcı bulunamadı' 
                })
            };
        }

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