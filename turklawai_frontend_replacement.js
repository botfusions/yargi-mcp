// TurkLawAI.com - Complete Frontend Authentication Replacement
// Bu script mevcut Supabase Auth sistemini tamamen değiştirir

// API Base URL - Production için güncellenecek
const API_BASE = 'https://turklawai.com/api';  // Production
// const API_BASE = 'http://localhost:8001';   // Development için

// Global authentication state
window.turkLawAuth = {
    isAuthenticated: false,
    user: null,
    token: null,
    loading: false
};

// Authentication functions
const authAPI = {
    async login(email, password) {
        try {
            this.setLoading(true);
            
            const response = await fetch(`${API_BASE}/auth/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ email, password })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Save authentication data
                localStorage.setItem('turklawai_token', data.token);
                localStorage.setItem('turklawai_user', JSON.stringify(data.user));
                
                // Update global state
                window.turkLawAuth.isAuthenticated = true;
                window.turkLawAuth.user = data.user;
                window.turkLawAuth.token = data.token;
                
                this.showMessage('Giriş başarılı!', 'success');
                this.updateUI();
                
                return { success: true, user: data.user };
            } else {
                this.showMessage(data.message, 'error');
                return { success: false, error: data.message };
            }
        } catch (error) {
            console.error('Login error:', error);
            this.showMessage('Bağlantı hatası', 'error');
            return { success: false, error: error.message };
        } finally {
            this.setLoading(false);
        }
    },

    async register(email, password, fullName) {
        try {
            this.setLoading(true);
            
            const response = await fetch(`${API_BASE}/auth/register`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ 
                    email, 
                    password, 
                    full_name: fullName || '' 
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Auto-login after registration
                localStorage.setItem('turklawai_token', data.token);
                localStorage.setItem('turklawai_user', JSON.stringify(data.user));
                
                window.turkLawAuth.isAuthenticated = true;
                window.turkLawAuth.user = data.user;
                window.turkLawAuth.token = data.token;
                
                this.showMessage('Kayıt başarılı! Hoş geldiniz.', 'success');
                this.updateUI();
                
                return { success: true, user: data.user };
            } else {
                this.showMessage(data.message, 'error');
                return { success: false, error: data.message };
            }
        } catch (error) {
            console.error('Register error:', error);
            this.showMessage('Bağlantı hatası', 'error');
            return { success: false, error: error.message };
        } finally {
            this.setLoading(false);
        }
    },

    async logout() {
        // Clear authentication data
        localStorage.removeItem('turklawai_token');
        localStorage.removeItem('turklawai_user');
        
        // Update global state
        window.turkLawAuth.isAuthenticated = false;
        window.turkLawAuth.user = null;
        window.turkLawAuth.token = null;
        
        this.showMessage('Çıkış yapıldı', 'info');
        this.updateUI();
        
        // Redirect to login page
        if (window.location.pathname !== '/login') {
            window.location.href = '/login';
        }
    },

    async verifyToken() {
        const token = localStorage.getItem('turklawai_token');
        if (!token) return false;
        
        try {
            const response = await fetch(`${API_BASE}/auth/user`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            
            const data = await response.json();
            
            if (data.success && data.user) {
                window.turkLawAuth.isAuthenticated = true;
                window.turkLawAuth.user = data.user;
                window.turkLawAuth.token = token;
                
                localStorage.setItem('turklawai_user', JSON.stringify(data.user));
                this.updateUI();
                return true;
            } else {
                // Token is invalid
                this.logout();
                return false;
            }
        } catch (error) {
            console.error('Token verification error:', error);
            this.logout();
            return false;
        }
    },

    setLoading(loading) {
        window.turkLawAuth.loading = loading;
        this.updateUI();
    },

    updateUI() {
        // Update login/logout buttons
        const loginBtns = document.querySelectorAll('.login-btn, [data-auth="login-btn"]');
        const logoutBtns = document.querySelectorAll('.logout-btn, [data-auth="logout-btn"]');
        const userInfo = document.querySelectorAll('.user-info, [data-auth="user-info"]');
        const protectedContent = document.querySelectorAll('.protected-content, [data-auth="protected"]');
        const guestContent = document.querySelectorAll('.guest-content, [data-auth="guest"]');
        
        if (window.turkLawAuth.isAuthenticated) {
            // Hide login elements
            loginBtns.forEach(btn => btn.style.display = 'none');
            guestContent.forEach(el => el.style.display = 'none');
            
            // Show authenticated elements
            logoutBtns.forEach(btn => btn.style.display = 'inline-block');
            protectedContent.forEach(el => el.style.display = 'block');
            
            // Update user info
            userInfo.forEach(info => {
                info.style.display = 'block';
                info.innerHTML = `
                    <span>Hoş geldin, ${window.turkLawAuth.user?.full_name || window.turkLawAuth.user?.email}</span>
                    <small>(${window.turkLawAuth.user?.plan || 'free'} plan)</small>
                `;
            });
        } else {
            // Show login elements
            loginBtns.forEach(btn => btn.style.display = 'inline-block');
            guestContent.forEach(el => el.style.display = 'block');
            
            // Hide authenticated elements
            logoutBtns.forEach(btn => btn.style.display = 'none');
            protectedContent.forEach(el => el.style.display = 'none');
            userInfo.forEach(info => info.style.display = 'none');
        }
        
        // Update loading state
        const loadingElements = document.querySelectorAll('.loading, [data-auth="loading"]');
        loadingElements.forEach(el => {
            el.style.display = window.turkLawAuth.loading ? 'block' : 'none';
        });
    },

    showMessage(message, type = 'info') {
        // Create or update message element
        let messageEl = document.getElementById('auth-message');
        if (!messageEl) {
            messageEl = document.createElement('div');
            messageEl.id = 'auth-message';
            messageEl.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 15px 20px;
                border-radius: 8px;
                color: white;
                font-weight: 500;
                z-index: 10000;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                transition: opacity 0.3s ease;
            `;
            document.body.appendChild(messageEl);
        }
        
        // Set background color based on type
        const colors = {
            success: '#28a745',
            error: '#dc3545',
            info: '#17a2b8',
            warning: '#ffc107'
        };
        messageEl.style.backgroundColor = colors[type] || colors.info;
        messageEl.textContent = message;
        messageEl.style.opacity = '1';
        
        // Auto hide after 5 seconds
        setTimeout(() => {
            if (messageEl) {
                messageEl.style.opacity = '0';
                setTimeout(() => {
                    if (messageEl.parentNode) {
                        messageEl.parentNode.removeChild(messageEl);
                    }
                }, 300);
            }
        }, 5000);
    }
};

// Initialize authentication on page load
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 TurkLawAI Auth System Initialized');
    
    // Check existing authentication
    const token = localStorage.getItem('turklawai_token');
    const user = localStorage.getItem('turklawai_user');
    
    if (token && user) {
        try {
            window.turkLawAuth.user = JSON.parse(user);
            window.turkLawAuth.token = token;
            window.turkLawAuth.isAuthenticated = true;
            authAPI.verifyToken(); // Verify token is still valid
        } catch (error) {
            console.error('Error parsing stored user data:', error);
            authAPI.logout();
        }
    }
    
    // Setup form event listeners
    setupAuthForms();
    
    // Initial UI update
    authAPI.updateUI();
});

// Setup authentication forms
function setupAuthForms() {
    // Login form
    const loginForm = document.querySelector('#login-form, form[data-auth="login"]');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(loginForm);
            const email = formData.get('email');
            const password = formData.get('password');
            
            if (email && password) {
                const result = await authAPI.login(email, password);
                if (result.success) {
                    // Redirect after successful login
                    const redirect = new URLSearchParams(window.location.search).get('redirect');
                    window.location.href = redirect || '/dashboard';
                }
            }
        });
    }
    
    // Register form
    const registerForm = document.querySelector('#register-form, form[data-auth="register"]');
    if (registerForm) {
        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(registerForm);
            const email = formData.get('email');
            const password = formData.get('password');
            const fullName = formData.get('full_name') || formData.get('name') || '';
            
            if (email && password) {
                const result = await authAPI.register(email, password, fullName);
                if (result.success) {
                    // Redirect after successful registration
                    window.location.href = '/dashboard';
                }
            }
        });
    }
    
    // Logout buttons
    const logoutBtns = document.querySelectorAll('.logout-btn, [data-auth="logout"]');
    logoutBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            authAPI.logout();
        });
    });
}

// Legacy compatibility - Supabase Auth replacement
window.useAuth = () => ({
    user: window.turkLawAuth.user,
    isAuthenticated: window.turkLawAuth.isAuthenticated,
    loading: window.turkLawAuth.loading,
    login: authAPI.login,
    logout: authAPI.logout,
    register: authAPI.register
});

// Supabase client compatibility
window.supabase = {
    auth: {
        signIn: ({ email, password }) => authAPI.login(email, password),
        signUp: ({ email, password, full_name }) => authAPI.register(email, password, full_name),
        signOut: () => authAPI.logout(),
        user: () => window.turkLawAuth.user,
        session: () => window.turkLawAuth.token ? { access_token: window.turkLawAuth.token } : null
    }
};

console.log('✅ TurkLawAI Emergency Auth System Loaded');
console.log('📧 Test with: admin@turklawai.com / admin123');