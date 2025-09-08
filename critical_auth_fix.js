// 🚨 CRITICAL AUTHENTICATION FIX - Production Build
// En güçlü fix - tüm React authentication sorunları için

(function() {
    'use strict';
    
    console.log('🔧 CRITICAL AUTH FIX - Loading...');
    
    // 1. GLOBAL CONTEXT OVERRIDE - Production build için
    const createGlobalAuthContext = () => {
        if (typeof window === 'undefined') return;
        
        // Default auth state
        const defaultAuthState = {
            user: null,
            loading: false,
            isAuthenticated: false,
            login: async (email, password) => {
                console.log('🔑 Global login called:', email);
                try {
                    const response = await fetch('/api/auth/login', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ email, password })
                    });
                    
                    if (response.ok) {
                        const data = await response.json();
                        window._globalAuthState = {
                            ...defaultAuthState,
                            user: data.user,
                            isAuthenticated: true
                        };
                        localStorage.setItem('turklawai_token', data.token);
                        return { success: true, user: data.user };
                    } else {
                        return { success: false, error: 'Login failed' };
                    }
                } catch (error) {
                    console.error('Login error:', error);
                    return { success: false, error: error.message };
                }
            },
            logout: () => {
                console.log('🚪 Global logout called');
                window._globalAuthState = defaultAuthState;
                localStorage.removeItem('turklawai_token');
            },
            loginWithOAuth: (provider = 'google') => {
                console.log('🔗 OAuth login:', provider);
                window.location.href = `/api/auth/${provider}/login`;
            }
        };
        
        // Set global state
        window._globalAuthState = defaultAuthState;
        
        return defaultAuthState;
    };
    
    // 2. REACT CONTEXT OVERRIDE - En agresif yaklaşım
    const setupReactContextOverride = () => {
        // React yüklenmesini bekle
        const waitForReact = setInterval(() => {
            if (window.React && window.React.createContext && window.React.useContext) {
                console.log('⚛️ React detected - Setting up context override');
                clearInterval(waitForReact);
                
                try {
                    // Global context oluştur
                    if (!window.SimpleAuthContext) {
                        window.SimpleAuthContext = window.React.createContext(window._globalAuthState);
                        console.log('✅ SimpleAuthContext created globally');
                    }
                    
                    // useSimpleAuth hook'unu tamamen override et
                    const originalUseContext = window.React.useContext;
                    
                    window.useSimpleAuth = function() {
                        console.log('🎣 useSimpleAuth hook called');
                        
                        try {
                            // Context'i almaya çalış
                            if (window.SimpleAuthContext && originalUseContext) {
                                const contextValue = originalUseContext(window.SimpleAuthContext);
                                if (contextValue && contextValue !== null) {
                                    console.log('✅ Context found, returning context value');
                                    return contextValue;
                                }
                            }
                        } catch (error) {
                            console.warn('⚠️ Context access failed:', error.message);
                        }
                        
                        // Fallback - global state döndür
                        console.log('🔄 Using global fallback state');
                        return window._globalAuthState || {
                            user: null,
                            loading: false,
                            isAuthenticated: false,
                            login: () => Promise.resolve({ success: false }),
                            logout: () => {},
                            loginWithOAuth: () => {}
                        };
                    };
                    
                    // Provider override
                    const originalCreateElement = window.React.createElement;
                    window.React.createElement = function(component, props, ...children) {
                        // SimpleAuthProvider'ı intercept et
                        if (typeof component === 'function' && 
                            (component.name === 'SimpleAuthProvider' || 
                             component.displayName === 'SimpleAuthProvider')) {
                            
                            console.log('🔧 Intercepting SimpleAuthProvider');
                            
                            // Wrapper component oluştur
                            return originalCreateElement(
                                window.SimpleAuthContext.Provider,
                                { value: window._globalAuthState },
                                children.length > 0 ? children : props.children
                            );
                        }
                        
                        return originalCreateElement.apply(this, arguments);
                    };
                    
                    console.log('✅ React context override complete');
                    
                } catch (error) {
                    console.error('❌ React setup failed:', error);
                }
            }
        }, 50);
        
        // 10 saniye timeout
        setTimeout(() => {
            clearInterval(waitForReact);
            console.warn('⏰ React detection timeout');
        }, 10000);
    };
    
    // 3. ERROR BOUNDARY OVERRIDE - Tüm authentication errorları yakala
    const setupErrorBoundary = () => {
        // Unhandled errors
        window.addEventListener('error', (event) => {
            if (event.error && event.error.message) {
                const message = event.error.message;
                
                if (message.includes('useSimpleAuth') || 
                    message.includes('SimpleAuthProvider') ||
                    message.includes('SimpleAuthContext')) {
                    
                    console.error('🚨 AUTH ERROR CAUGHT:', message);
                    console.log('🔧 Applying emergency recovery...');
                    
                    // Error'u prevent et
                    event.preventDefault();
                    event.stopPropagation();
                    
                    // Emergency auth state inject
                    if (window.React && window.React.useContext) {
                        const originalUseContext = window.React.useContext;
                        window.React.useContext = function(context) {
                            try {
                                return originalUseContext(context);
                            } catch (err) {
                                console.warn('🔄 useContext error, using fallback');
                                return window._globalAuthState;
                            }
                        };
                    }
                    
                    // Show user message
                    showEmergencyMessage();
                    
                    return false;
                }
            }
        });
        
        // Promise rejections
        window.addEventListener('unhandledrejection', (event) => {
            if (event.reason && event.reason.message && 
                event.reason.message.includes('useSimpleAuth')) {
                
                console.warn('🚨 AUTH PROMISE REJECTION:', event.reason.message);
                event.preventDefault();
            }
        });
    };
    
    // 4. USER FEEDBACK - Hata durumunda kullanıcıya bilgi ver
    const showEmergencyMessage = () => {
        const existingMessage = document.getElementById('auth-emergency-message');
        if (existingMessage) return;
        
        const messageDiv = document.createElement('div');
        messageDiv.id = 'auth-emergency-message';
        messageDiv.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 16px 20px;
            border-radius: 12px;
            box-shadow: 0 8px 25px rgba(0,0,0,0.2);
            z-index: 10000;
            max-width: 350px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 14px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
        `;
        messageDiv.innerHTML = `
            <div style="font-weight: bold; margin-bottom: 8px;">
                🔧 Sistem Yeniden Başlatılıyor...
            </div>
            <div style="font-size: 12px; opacity: 0.9; margin-bottom: 12px;">
                TurkLawAI.com authentication sistemi güncelleniyor.
                Sayfa birkaç saniye içinde otomatik yenilenecek.
            </div>
            <div style="text-align: center;">
                <button onclick="window.location.reload()" style="
                    background: rgba(255,255,255,0.2);
                    border: 1px solid rgba(255,255,255,0.3);
                    color: white;
                    padding: 8px 16px;
                    border-radius: 6px;
                    cursor: pointer;
                    font-size: 12px;
                ">
                    Şimdi Yenile
                </button>
            </div>
        `;
        
        document.body.appendChild(messageDiv);
        
        // 5 saniye sonra otomatik yenile
        setTimeout(() => {
            window.location.reload();
        }, 5000);
    };
    
    // 5. INITIALIZATION - Herşeyi başlat
    const initialize = () => {
        console.log('🚀 Critical Auth Fix - Initializing...');
        
        // Global state oluştur
        createGlobalAuthContext();
        
        // Error handling setup
        setupErrorBoundary();
        
        // React override setup (DOM ready'den sonra)
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', setupReactContextOverride);
        } else {
            setupReactContextOverride();
        }
        
        console.log('✅ Critical Auth Fix - Ready!');
    };
    
    // Hemen başlat
    initialize();
    
    // Export global functions for debugging
    window._authFixDebug = {
        state: () => window._globalAuthState,
        reload: () => window.location.reload(),
        reset: () => {
            localStorage.removeItem('turklawai_token');
            window._globalAuthState = createGlobalAuthContext();
        }
    };
    
})();