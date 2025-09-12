// TurkLawAI Frontend Integration for Netlify Functions
// Bu dosyayı Lovable projesine ekle veya mevcut auth dosyasını güncelle

class TurkLawAIAuth {
    constructor() {
        this.apiBase = '/.netlify/functions'; // Netlify functions path
        this.token = localStorage.getItem('turklawai_token');
    }

    // Login function
    async login(email, password) {
        try {
            const response = await fetch(`${this.apiBase}/auth-login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ email, password })
            });

            const data = await response.json();

            if (data.success) {
                // Save token and user data
                localStorage.setItem('turklawai_token', data.token);
                localStorage.setItem('turklawai_user', JSON.stringify(data.user));
                this.token = data.token;
                
                // Trigger login success event
                window.dispatchEvent(new CustomEvent('turklawai-login-success', {
                    detail: { user: data.user, token: data.token }
                }));

                return { success: true, user: data.user, token: data.token };
            } else {
                return { success: false, message: data.message };
            }
        } catch (error) {
            console.error('Login error:', error);
            return { success: false, message: 'Giriş sırasında hata oluştu' };
        }
    }

    // Logout function
    logout() {
        localStorage.removeItem('turklawai_token');
        localStorage.removeItem('turklawai_user');
        this.token = null;
        
        // Trigger logout event
        window.dispatchEvent(new CustomEvent('turklawai-logout'));
        
        return { success: true };
    }

    // Check if user is authenticated
    isAuthenticated() {
        return !!this.token && this.token !== 'null';
    }

    // Get current user
    getCurrentUser() {
        const userStr = localStorage.getItem('turklawai_user');
        return userStr ? JSON.parse(userStr) : null;
    }

    // Check API health
    async healthCheck() {
        try {
            const response = await fetch(`${this.apiBase}/health`);
            const data = await response.json();
            return data;
        } catch (error) {
            console.error('Health check error:', error);
            return { status: 'error', message: error.message };
        }
    }

    // Get authorization headers
    getAuthHeaders() {
        return {
            'Authorization': `Bearer ${this.token}`,
            'Content-Type': 'application/json'
        };
    }

    // Make authenticated request
    async authenticatedRequest(endpoint, options = {}) {
        if (!this.isAuthenticated()) {
            throw new Error('User not authenticated');
        }

        const defaultOptions = {
            headers: this.getAuthHeaders(),
            ...options
        };

        try {
            const response = await fetch(endpoint, defaultOptions);
            
            if (response.status === 401) {
                // Token expired, logout user
                this.logout();
                window.location.href = '/login';
                return null;
            }

            return await response.json();
        } catch (error) {
            console.error('Authenticated request error:', error);
            throw error;
        }
    }
}

// Initialize global auth instance
window.turkLawAuth = new TurkLawAIAuth();

// DOM ready setup
document.addEventListener('DOMContentLoaded', function() {
    // Auto-fill login form for testing (remove in production)
    const emailInput = document.querySelector('input[type="email"]');
    const passwordInput = document.querySelector('input[type="password"]');
    
    if (emailInput && passwordInput && !emailInput.value) {
        emailInput.value = 'admin@turklawai.com';
        passwordInput.value = 'admin123';
        console.log('🔧 Auto-filled login form for testing');
    }

    // Handle login form submission
    const loginForm = document.querySelector('form');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const email = emailInput?.value;
            const password = passwordInput?.value;
            
            if (!email || !password) {
                alert('Email ve şifre gerekli');
                return;
            }

            // Show loading state
            const submitBtn = loginForm.querySelector('button[type="submit"]');
            const originalText = submitBtn?.textContent;
            if (submitBtn) submitBtn.textContent = 'Giriş yapılıyor...';

            try {
                const result = await window.turkLawAuth.login(email, password);
                
                if (result.success) {
                    alert('Giriş başarılı!');
                    // Redirect to dashboard or reload page
                    window.location.href = '/dashboard';
                } else {
                    alert(result.message || 'Giriş başarısız');
                }
            } catch (error) {
                alert('Giriş sırasında hata oluştu: ' + error.message);
            } finally {
                if (submitBtn) submitBtn.textContent = originalText;
            }
        });
    }

    // Check if user is already authenticated
    if (window.turkLawAuth.isAuthenticated()) {
        const user = window.turkLawAuth.getCurrentUser();
        console.log('✅ User already authenticated:', user);
        
        // Update UI to show user is logged in
        const userInfo = document.querySelector('.user-info');
        if (userInfo) {
            userInfo.innerHTML = `
                <div>Hoş geldiniz, ${user.full_name || user.email}</div>
                <div>Plan: ${user.plan}</div>
                <button onclick="window.turkLawAuth.logout(); location.reload();">Çıkış</button>
            `;
        }
    }
});

// Health check on load
window.turkLawAuth.healthCheck().then(health => {
    console.log('🏥 API Health:', health);
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TurkLawAIAuth;
}

console.log('🚀 TurkLawAI Netlify Functions integration loaded!');