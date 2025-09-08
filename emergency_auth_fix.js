// TurkLawAI.com - Emergency Authentication Fix
// Production build için hızlı düzeltme

// ✅ HEMEN ÇÖZEBİLECEK FIX - HTML'e script tag olarak ekleyin

// 1. SimpleAuthProvider'ı global olarak tanımla
window.SimpleAuthContext = React.createContext();

// 2. SimpleAuthProvider component'i
window.SimpleAuthProvider = ({ children }) => {
  const [authState, setAuthState] = React.useState({
    user: null,
    loading: false,
    isAuthenticated: false
  });

  const login = async (email, password) => {
    setAuthState(prev => ({ ...prev, loading: true }));
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      
      if (response.ok) {
        const data = await response.json();
        setAuthState({
          user: data.user,
          loading: false,
          isAuthenticated: true
        });
        localStorage.setItem('turklawai_token', data.token);
      }
    } catch (error) {
      console.error('Login error:', error);
      setAuthState(prev => ({ ...prev, loading: false }));
    }
  };

  const logout = () => {
    setAuthState({
      user: null,
      loading: false,
      isAuthenticated: false
    });
    localStorage.removeItem('turklawai_token');
  };

  const loginWithOAuth = (provider = 'google') => {
    window.location.href = `/api/auth/${provider}/login`;
  };

  const contextValue = {
    ...authState,
    login,
    logout,
    loginWithOAuth
  };

  return React.createElement(
    window.SimpleAuthContext.Provider,
    { value: contextValue },
    children
  );
};

// 3. useSimpleAuth hook'unu override et
window.useSimpleAuth = () => {
  const context = React.useContext(window.SimpleAuthContext);
  
  if (!context) {
    // Emergency fallback - hata yerine default state döndür
    console.warn('SimpleAuthProvider not found, using fallback auth state');
    return {
      user: null,
      loading: false,
      isAuthenticated: false,
      login: () => Promise.resolve(),
      logout: () => {},
      loginWithOAuth: () => {}
    };
  }
  
  return context;
};

// 4. Mevcut React app'i yeniden wrap et
document.addEventListener('DOMContentLoaded', () => {
  // Root element'i bul
  const rootElement = document.getElementById('root');
  
  if (rootElement && window.React && window.ReactDOM) {
    // Mevcut app'i koru ama SimpleAuthProvider ile sar
    const originalApp = rootElement.innerHTML;
    
    // React 18 ile uyumlu render
    if (window.ReactDOM.createRoot) {
      const root = window.ReactDOM.createRoot(rootElement);
      root.render(
        React.createElement(
          window.SimpleAuthProvider,
          null,
          React.createElement('div', { dangerouslySetInnerHTML: { __html: originalApp } })
        )
      );
    } else {
      // React 17 fallback
      window.ReactDOM.render(
        React.createElement(
          window.SimpleAuthProvider,
          null,
          React.createElement('div', { dangerouslySetInnerHTML: { __html: originalApp } })
        ),
        rootElement
      );
    }
  }
});

// 5. Global error handler - auth hatalarını yakala
window.addEventListener('error', (event) => {
  if (event.error && event.error.message && event.error.message.includes('useSimpleAuth')) {
    console.warn('Caught useSimpleAuth error, attempting recovery...');
    
    // Fallback auth state'i tüm component'lere inject et
    if (window.React && window.React.useContext) {
      const originalUseContext = window.React.useContext;
      window.React.useContext = (context) => {
        try {
          return originalUseContext(context);
        } catch (error) {
          if (error.message.includes('useSimpleAuth')) {
            return {
              user: null,
              loading: false,
              isAuthenticated: false,
              login: () => Promise.resolve(),
              logout: () => {},
              loginWithOAuth: () => {}
            };
          }
          throw error;
        }
      };
    }
    
    // Sayfayı yenile (son çare)
    setTimeout(() => {
      window.location.reload();
    }, 1000);
    
    event.preventDefault();
    return false;
  }
});

// 6. Console'a debug bilgisi
console.log('🔧 TurkLawAI Emergency Auth Fix loaded');
console.log('- SimpleAuthProvider:', typeof window.SimpleAuthProvider);
console.log('- useSimpleAuth:', typeof window.useSimpleAuth);
console.log('- React:', typeof window.React);
console.log('- ReactDOM:', typeof window.ReactDOM);