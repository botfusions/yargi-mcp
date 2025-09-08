// TurkLawAI.com - React Authentication Fix
// useSimpleAuth Context Provider hatası düzeltmesi

import React, { createContext, useContext, useState, useEffect } from 'react';

// ✅ AUTH CONTEXT OLUŞTUR
const SimpleAuthContext = createContext();

// ✅ AUTH PROVIDER COMPONENT
export const SimpleAuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  // Auth state initialization
  useEffect(() => {
    const initAuth = async () => {
      try {
        // Token kontrolü
        const token = localStorage.getItem('turklawai_token');
        
        if (token) {
          // Token validation
          const response = await fetch('/api/auth/validate', {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            }
          });

          if (response.ok) {
            const userData = await response.json();
            setUser(userData.user);
            setIsAuthenticated(true);
          } else {
            // Invalid token - clear storage
            localStorage.removeItem('turklawai_token');
          }
        }
      } catch (error) {
        console.error('Auth initialization error:', error);
        localStorage.removeItem('turklawai_token');
      } finally {
        setLoading(false);
      }
    };

    initAuth();
  }, []);

  // Login function
  const login = async (email, password) => {
    try {
      setLoading(true);
      
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ email, password })
      });

      if (response.ok) {
        const data = await response.json();
        
        // Store token
        localStorage.setItem('turklawai_token', data.token);
        
        // Update state
        setUser(data.user);
        setIsAuthenticated(true);
        
        return { success: true };
      } else {
        const errorData = await response.json();
        return { success: false, error: errorData.message };
      }
    } catch (error) {
      return { success: false, error: error.message };
    } finally {
      setLoading(false);
    }
  };

  // Logout function
  const logout = async () => {
    try {
      // Call logout endpoint
      await fetch('/api/auth/logout', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('turklawai_token')}`
        }
      });
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      // Clear local state
      localStorage.removeItem('turklawai_token');
      setUser(null);
      setIsAuthenticated(false);
    }
  };

  // OAuth login (Clerk/Google)
  const loginWithOAuth = (provider = 'google') => {
    window.location.href = `/api/auth/${provider}/login`;
  };

  // Context value
  const value = {
    user,
    loading,
    isAuthenticated,
    login,
    logout,
    loginWithOAuth
  };

  return (
    <SimpleAuthContext.Provider value={value}>
      {children}
    </SimpleAuthContext.Provider>
  );
};

// ✅ CUSTOM HOOK
export const useSimpleAuth = () => {
  const context = useContext(SimpleAuthContext);
  
  if (context === undefined) {
    throw new Error('useSimpleAuth must be used within a SimpleAuthProvider');
  }
  
  return context;
};

// ✅ AUTH GUARD COMPONENT
export const AuthGuard = ({ children, fallback = <div>Loading...</div> }) => {
  const { isAuthenticated, loading } = useSimpleAuth();

  if (loading) {
    return fallback;
  }

  if (!isAuthenticated) {
    return <LoginForm />;
  }

  return children;
};

// ✅ LOGIN FORM COMPONENT
const LoginForm = () => {
  const { login, loginWithOAuth, loading } = useSimpleAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    const result = await login(email, password);
    
    if (!result.success) {
      setError(result.error);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <h2>TurkLawAI.com</h2>
        <p>Türk Hukukunda AI Destekli Araştırma</p>

        {error && (
          <div className="error-message">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          
          <input
            type="password"
            placeholder="Şifre"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          
          <button type="submit" disabled={loading}>
            {loading ? 'Giriş yapılıyor...' : 'Giriş Yap'}
          </button>
        </form>

        <div className="oauth-buttons">
          <button 
            onClick={() => loginWithOAuth('google')}
            className="google-login"
          >
            Google ile Giriş
          </button>
        </div>
      </div>
    </div>
  );
};

// ✅ USER PROFILE COMPONENT
export const UserProfile = () => {
  const { user, logout } = useSimpleAuth();

  return (
    <div className="user-profile">
      <span>Merhaba, {user?.name || user?.email}</span>
      <button onClick={logout}>Çıkış Yap</button>
    </div>
  );
};