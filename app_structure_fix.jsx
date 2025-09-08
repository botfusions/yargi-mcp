// TurkLawAI.com - App.jsx Structure Fix
// SimpleAuthProvider wrapper düzeltmesi

import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { SimpleAuthProvider, useSimpleAuth, AuthGuard, UserProfile } from './react_auth_fix.jsx';

// ✅ MAIN APP COMPONENT
const App = () => {
  return (
    <SimpleAuthProvider>
      <Router>
        <div className="app">
          <Header />
          <main className="main-content">
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/search" element={
                <AuthGuard>
                  <SearchPage />
                </AuthGuard>
              } />
              <Route path="/dashboard" element={
                <AuthGuard>
                  <Dashboard />
                </AuthGuard>
              } />
              <Route path="/about" element={<AboutPage />} />
            </Routes>
          </main>
          <Footer />
        </div>
      </Router>
    </SimpleAuthProvider>
  );
};

// ✅ HEADER COMPONENT
const Header = () => {
  const { isAuthenticated, loading } = useSimpleAuth();

  return (
    <header className="header">
      <div className="container">
        <div className="logo">
          <h1>TurkLawAI.com</h1>
        </div>
        
        <nav className="navigation">
          <a href="/">Ana Sayfa</a>
          <a href="/search">Arama</a>
          <a href="/about">Hakkında</a>
        </nav>

        <div className="auth-section">
          {!loading && (
            isAuthenticated ? (
              <UserProfile />
            ) : (
              <a href="/login" className="login-button">
                Giriş Yap
              </a>
            )
          )}
        </div>
      </div>
    </header>
  );
};

// ✅ HOME PAGE
const HomePage = () => {
  const { isAuthenticated } = useSimpleAuth();

  return (
    <div className="homepage">
      <section className="hero">
        <h1>Türk Hukukunda AI Destekli Araştırma</h1>
        <p>21 farklı hukuki araçla kapsamlı mahkeme kararı araştırması</p>
        
        {isAuthenticated ? (
          <a href="/search" className="cta-button">
            Aramaya Başla
          </a>
        ) : (
          <a href="/login" className="cta-button">
            Ücretsiz Deneyin
          </a>
        )}
      </section>

      <section className="features">
        <div className="feature-grid">
          <div className="feature-card">
            <h3>🏛️ 11 Mahkeme Sistemi</h3>
            <p>Yargıtay, Danıştay, Anayasa Mahkemesi ve daha fazlası</p>
          </div>
          
          <div className="feature-card">
            <h3>🤖 AI Hukuki Analiz</h3>
            <p>Uzman düzeyinde hukuki risk değerlendirmesi</p>
          </div>
          
          <div className="feature-card">
            <h3>⚡ 10x Hızlı</h3>
            <p>6 saatlik araştırmayı 10 dakikaya indirin</p>
          </div>
        </div>
      </section>
    </div>
  );
};

// ✅ SEARCH PAGE
const SearchPage = () => {
  const [query, setQuery] = React.useState('');
  const [results, setResults] = React.useState([]);
  const [loading, setLoading] = React.useState(false);
  
  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    try {
      const token = localStorage.getItem('turklawai_token');
      
      const response = await fetch('/api/legal-analysis', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          question: query,
          analysis_depth: 'standard'
        })
      });

      if (response.ok) {
        const data = await response.json();
        setResults(data.data.sources || []);
      } else {
        console.error('Search failed:', response.statusText);
      }
    } catch (error) {
      console.error('Search error:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="search-page">
      <div className="search-container">
        <form onSubmit={handleSearch} className="search-form">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Hukuki sorunuzu yazın... (örn: tapu iptali davası)"
            className="search-input"
          />
          <button type="submit" disabled={loading}>
            {loading ? 'Araştırılıyor...' : 'Ara'}
          </button>
        </form>

        {results.length > 0 && (
          <div className="search-results">
            <h3>Bulunan Kararlar ({results.length})</h3>
            
            <div className="results-grid">
              {results.map((result, index) => (
                <div key={index} className="result-card">
                  <h4>{result.title}</h4>
                  <p className="court-info">{result.court}</p>
                  <p className="summary">{result.summary}</p>
                  
                  <div className="result-meta">
                    <span className="confidence">
                      Uygunluk: {Math.round(result.confidence * 100)}%
                    </span>
                    <span className="date">{result.date}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// ✅ DASHBOARD
const Dashboard = () => {
  const { user } = useSimpleAuth();

  return (
    <div className="dashboard">
      <h2>Dashboard</h2>
      <div className="dashboard-grid">
        <div className="stats-card">
          <h3>Aramalarım</h3>
          <p className="big-number">24</p>
        </div>
        
        <div className="stats-card">
          <h3>Bu Ay</h3>
          <p className="big-number">8</p>
        </div>
        
        <div className="stats-card">
          <h3>Planım</h3>
          <p className="plan-info">{user?.plan || 'Free'}</p>
        </div>
      </div>
    </div>
  );
};

// ✅ ABOUT PAGE
const AboutPage = () => {
  return (
    <div className="about-page">
      <h2>TurkLawAI.com Hakkında</h2>
      <p>Türkiye'nin ilk AI destekli kapsamlı hukuki araştırma platformu.</p>
    </div>
  );
};

// ✅ FOOTER
const Footer = () => {
  return (
    <footer className="footer">
      <div className="container">
        <p>&copy; 2025 TurkLawAI.com - Tüm hakları saklıdır.</p>
      </div>
    </footer>
  );
};

export default App;