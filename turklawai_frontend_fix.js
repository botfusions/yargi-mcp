// TurkLawAI.com - Frontend Authentication Integration
// Bu script'i HTML'e ekleyin ve authentication sorununu çözer

// API Base URL
// const API_BASE = 'https://turklawai.com/api';  // Production
const API_BASE = 'http://localhost:8001';   // Development

// Authentication Manager
class TurkLawAuth {
    constructor() {
        this.token = localStorage.getItem('turklawai_token');
        this.user = null;
        this.isAuthenticated = false;
        this.loading = false;
        
        // Auto-verify token on init
        if (this.token) {
            this.verifyToken();
        }
        
        // Setup event listeners
        this.setupEventListeners();
    }
    
    async verifyToken() {
        if (!this.token) return false;
        
        try {
            const response = await fetch(`${API_BASE}/auth/user`, {
                headers: {
                    'Authorization': `Bearer ${this.token}`,
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    this.user = data.user;
                    this.isAuthenticated = true;
                    this.updateUI();
                    return true;
                }
            }
        } catch (error) {
            console.error('Token verification failed:', error);
        }
        
        // Token is invalid
        this.logout();
        return false;
    }
    
    async register(email, password, fullName = '') {
        this.loading = true;
        this.updateUI();
        
        try {
            const response = await fetch(`${API_BASE}/auth/register`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    email: email,
                    password: password,
                    full_name: fullName
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.token = data.token;
                this.user = data.user;
                this.isAuthenticated = true;
                localStorage.setItem('turklawai_token', this.token);
                this.showMessage('Kayıt başarılı! Hoş geldiniz.', 'success');
                this.updateUI();
                return true;
            } else {
                this.showMessage(data.message || 'Kayıt başarısız', 'error');
                return false;
            }
        } catch (error) {
            console.error('Registration error:', error);
            this.showMessage('Kayıt sırasında hata oluştu', 'error');
            return false;
        } finally {
            this.loading = false;
            this.updateUI();
        }
    }
    
    async login(email, password) {
        this.loading = true;
        this.updateUI();
        
        try {
            const response = await fetch(`${API_BASE}/auth/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    email: email,
                    password: password
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.token = data.token;
                this.user = data.user;
                this.isAuthenticated = true;
                localStorage.setItem('turklawai_token', this.token);
                this.showMessage('Giriş başarılı! Hoş geldiniz.', 'success');
                this.updateUI();
                return true;
            } else {
                this.showMessage(data.message || 'Giriş başarısız', 'error');
                return false;
            }
        } catch (error) {
            console.error('Login error:', error);
            this.showMessage('Giriş sırasında hata oluştu', 'error');
            return false;
        } finally {
            this.loading = false;
            this.updateUI();
        }
    }
    
    logout() {
        this.token = null;
        this.user = null;
        this.isAuthenticated = false;
        localStorage.removeItem('turklawai_token');
        this.showMessage('Çıkış yapıldı', 'info');
        this.updateUI();
    }
    
    updateUI() {
        // Update login/logout buttons
        const loginBtns = document.querySelectorAll('[data-auth="login-btn"]');
        const logoutBtns = document.querySelectorAll('[data-auth="logout-btn"]');
        const userInfo = document.querySelectorAll('[data-auth="user-info"]');
        const authForms = document.querySelectorAll('[data-auth="auth-form"]');
        const protectedContent = document.querySelectorAll('[data-auth="protected"]');
        
        if (this.isAuthenticated) {
            // Hide login buttons and forms
            loginBtns.forEach(btn => btn.style.display = 'none');
            authForms.forEach(form => form.style.display = 'none');
            
            // Show logout buttons and user info
            logoutBtns.forEach(btn => btn.style.display = 'inline-block');
            userInfo.forEach(info => {
                info.style.display = 'block';
                info.innerHTML = `
                    <span>Hoş geldin, ${this.user?.full_name || this.user?.email || 'Kullanıcı'}</span>
                    <small>(${this.user?.plan || 'free'} plan)</small>
                `;
            });
            protectedContent.forEach(content => content.style.display = 'block');
            
        } else {
            // Show login buttons and forms
            loginBtns.forEach(btn => btn.style.display = 'inline-block');
            authForms.forEach(form => form.style.display = 'block');
            
            // Hide logout buttons and user info
            logoutBtns.forEach(btn => btn.style.display = 'none');
            userInfo.forEach(info => info.style.display = 'none');
            protectedContent.forEach(content => content.style.display = 'none');
        }
        
        // Update loading state
        const loadingElements = document.querySelectorAll('[data-auth="loading"]');
        loadingElements.forEach(el => {
            el.style.display = this.loading ? 'block' : 'none';
        });
    }
    
    setupEventListeners() {
        // Auto-setup forms and buttons
        document.addEventListener('DOMContentLoaded', () => {
            this.setupLoginForm();
            this.setupRegisterForm();
            this.setupLogoutButtons();
        });
        
        // If DOM is already loaded
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setupForms());
        } else {
            this.setupForms();
        }
    }
    
    setupForms() {
        this.setupLoginForm();
        this.setupRegisterForm();
        this.setupLogoutButtons();
    }
    
    setupLoginForm() {
        const loginForm = document.querySelector('#login-form, [data-auth="login-form"]');
        if (loginForm) {
            loginForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(loginForm);
                const email = formData.get('email');
                const password = formData.get('password');
                
                if (email && password) {
                    await this.login(email, password);
                }
            });
        }
    }
    
    setupRegisterForm() {
        const registerForm = document.querySelector('#register-form, [data-auth="register-form"]');
        if (registerForm) {
            registerForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(registerForm);
                const email = formData.get('email');
                const password = formData.get('password');
                const fullName = formData.get('full_name') || formData.get('fullName') || '';
                
                if (email && password) {
                    await this.register(email, password, fullName);
                }
            });
        }
    }
    
    setupLogoutButtons() {
        const logoutBtns = document.querySelectorAll('[data-auth="logout-btn"], .logout-btn');
        logoutBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                this.logout();
            });
        });
    }
    
    showMessage(message, type = 'info') {
        // Create message element
        const messageDiv = document.createElement('div');
        messageDiv.className = `auth-message auth-message-${type}`;
        messageDiv.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 6px;
            color: white;
            font-weight: 500;
            z-index: 9999;
            opacity: 0;
            transition: opacity 0.3s ease;
        `;
        
        // Set background color based on type
        const colors = {
            success: '#28a745',
            error: '#dc3545',
            info: '#17a2b8',
            warning: '#ffc107'
        };
        messageDiv.style.backgroundColor = colors[type] || colors.info;
        
        messageDiv.textContent = message;
        document.body.appendChild(messageDiv);
        
        // Animate in
        setTimeout(() => messageDiv.style.opacity = '1', 100);
        
        // Remove after 5 seconds
        setTimeout(() => {
            messageDiv.style.opacity = '0';
            setTimeout(() => {
                if (messageDiv.parentNode) {
                    messageDiv.parentNode.removeChild(messageDiv);
                }
            }, 300);
        }, 5000);
    }
    
    // Utility methods
    getUser() {
        return this.user;
    }
    
    getToken() {
        return this.token;
    }
    
    isLoggedIn() {
        return this.isAuthenticated;
    }
}

// Initialize authentication
const turkLawAuth = new TurkLawAuth();

// Make it globally available
window.turkLawAuth = turkLawAuth;

// Compatibility with existing code
window.useSimpleAuth = () => ({
    user: turkLawAuth.user,
    loading: turkLawAuth.loading,
    isAuthenticated: turkLawAuth.isAuthenticated,
    login: (email, password) => turkLawAuth.login(email, password),
    logout: () => turkLawAuth.logout(),
    loginWithOAuth: () => {
        turkLawAuth.showMessage('Google OAuth geçici olarak kullanılamıyor. Email/şifre ile giriş yapın.', 'warning');
    }
});

console.log('✅ TurkLawAI Authentication System Ready');
console.log('- Use: turkLawAuth.login(email, password)');
console.log('- Use: turkLawAuth.register(email, password, fullName)');
console.log('- Use: turkLawAuth.logout()');