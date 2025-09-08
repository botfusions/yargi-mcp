# React Authentication Error Fix - TurkLawAI.com

## ❌ Hata Analizi
```
ErrorBoundary caught an error: Error: useSimpleAuth must be used within a SimpleAuthProvider
```

**Sorun:** `useSimpleAuth` hook'u `SimpleAuthProvider` context wrapper'ı olmadan kullanılmaya çalışılıyor.

## ✅ Düzeltme Stratejisi

### 1. HEMEN ÇÖZEBİLECEK DÜZELTME (Quick Fix)

Mevcut kodunuzda **App.jsx** veya **main.jsx** dosyasını bulun ve şöyle sarın:

```jsx
// ✅ HIZLI ÇÖZEBİLECEK FİX - main.jsx veya App.jsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';

// ✅ SimpleAuthProvider wrapper ekleyin
const SimpleAuthProvider = ({ children }) => {
  const [user, setUser] = React.useState(null);
  const [loading, setLoading] = React.useState(false);
  const [isAuthenticated, setIsAuthenticated] = React.useState(false);

  const contextValue = {
    user,
    loading,
    isAuthenticated,
    login: () => {},
    logout: () => {},
    loginWithOAuth: () => {}
  };

  return (
    <div>
      {React.cloneElement(children, { authContext: contextValue })}
    </div>
  );
};

// ✅ App'i SimpleAuthProvider ile sarın
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <SimpleAuthProvider>
      <App />
    </SimpleAuthProvider>
  </React.StrictMode>
);
```

### 2. CONTEXT API DÜZELTMESİ (Proper Fix)

Ana uygulamanızın `main.jsx` dosyasında:

```jsx
import React, { createContext, useContext, useState } from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';

// ✅ CONTEXT OLUŞTUR
const SimpleAuthContext = createContext();

// ✅ PROVIDER COMPONENT
const SimpleAuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  const login = async (email, password) => {
    setLoading(true);
    try {
      // Login API call
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      
      if (response.ok) {
        const data = await response.json();
        setUser(data.user);
        setIsAuthenticated(true);
        localStorage.setItem('token', data.token);
      }
    } catch (error) {
      console.error('Login error:', error);
    }
    setLoading(false);
  };

  const logout = () => {
    setUser(null);
    setIsAuthenticated(false);
    localStorage.removeItem('token');
  };

  const loginWithOAuth = (provider) => {
    window.location.href = `/api/auth/${provider}/login`;
  };

  return (
    <SimpleAuthContext.Provider value={{
      user,
      loading,
      isAuthenticated,
      login,
      logout,
      loginWithOAuth
    }}>
      {children}
    </SimpleAuthContext.Provider>
  );
};

// ✅ CUSTOM HOOK
window.useSimpleAuth = () => {
  const context = useContext(SimpleAuthContext);
  if (!context) {
    throw new Error('useSimpleAuth must be used within a SimpleAuthProvider');
  }
  return context;
};

// ✅ APP RENDER WITH PROVIDER
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <SimpleAuthProvider>
      <App />
    </SimpleAuthProvider>
  </React.StrictMode>
);
```

### 3. COMPONENT LEVEL FIX

Eğer belirli component'lerde hata alıyorsanız, o component'leri şöyle sarın:

```jsx
// ✅ Component seviyesinde düzeltme
const YourComponent = () => {
  // Context kontrolü ekle
  let authData;
  try {
    authData = useSimpleAuth();
  } catch (error) {
    // Fallback if not within provider
    authData = {
      user: null,
      loading: false,
      isAuthenticated: false,
      login: () => {},
      logout: () => {},
      loginWithOAuth: () => {}
    };
  }

  const { user, isAuthenticated } = authData;

  return (
    <div>
      {isAuthenticated ? (
        <div>Welcome {user?.name}</div>
      ) : (
        <div>Please login</div>
      )}
    </div>
  );
};
```

## 🚀 Test Etme

Düzeltmeyi uyguladıktan sonra:

```bash
# 1. Browser console'u temizleyin (F12 -> Console -> Clear)

# 2. Sayfayı yeniden yükleyin (Ctrl+F5)

# 3. Console'da error olup olmadığını kontrol edin

# 4. Authentication işlevselliğini test edin
```

## 🔍 Hata Kaynağını Bulma

Hangi component'in soruna neden olduğunu bulmak için:

```jsx
// ✅ Error boundary ekleyin
class AuthErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error) {
    console.log('Auth Error Boundary caught:', error);
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.log('Auth Error Details:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return <h1>Auth system error - check console</h1>;
    }

    return this.props.children;
  }
}

// Kullanım
<AuthErrorBoundary>
  <YourApp />
</AuthErrorBoundary>
```

## 📋 Checklist

- [ ] `SimpleAuthProvider` ana uygulamayı sarıyor mu?
- [ ] `useSimpleAuth` sadece provider içindeki component'lerde kullanılıyor mu?  
- [ ] Context doğru import edilmiş mi?
- [ ] Browser console temizlenip sayfa yenilendi mi?
- [ ] Network tab'de auth API'leri çalışıyor mu?

Bu adımları takip ederek authentication hatası çözülecek! 🔧