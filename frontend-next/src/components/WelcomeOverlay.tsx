'use client';

import { useState, useEffect } from 'react';
import type { User } from '@/types';
import { login, register, guestLogin } from '@/lib/api';

interface WelcomeOverlayProps {
  onLogin: () => void;
  onGuest: () => void;
  onAuth: (user: User) => void;
}

const FEATURES = [
  { icon: '🔍', title: 'Smart Flight Search', desc: 'Search one-way & round-trip flights across airlines with natural language' },
  { icon: '🎫', title: 'Instant Booking', desc: 'Book tickets, select seats, add meals & baggage — all in chat' },
  { icon: '✅', title: 'Web Check-in', desc: 'Check in online and download your boarding pass instantly' },
  { icon: '💰', title: 'Refund Tracking', desc: 'Check refund status and manage cancellations effortlessly' },
  { icon: '📊', title: 'Flight Status', desc: 'Real-time flight status updates with gate & delay info' },
  { icon: '🤝', title: 'Human Agent', desc: 'Seamless escalation to human support when you need it' },
];

const STATS = [
  { value: '50+', label: 'Airports' },
  { value: '500+', label: 'Daily Flights' },
  { value: '24/7', label: 'AI Support' },
  { value: '<3s', label: 'Avg Response' },
];

export default function WelcomeOverlay({ onLogin, onGuest, onAuth }: WelcomeOverlayProps) {
  const [mounted, setMounted] = useState(false);
  const [showAuthCard, setShowAuthCard] = useState(false);
  const [authTab, setAuthTab] = useState<'login' | 'guest'>('login');
  const [showRegister, setShowRegister] = useState(false);
  const [authError, setAuthError] = useState('');

  useEffect(() => {
    setMounted(true);
  }, []);

  const openAuth = (tab: 'login' | 'guest' = 'login') => {
    setAuthTab(tab);
    setShowRegister(false);
    setAuthError('');
    setShowAuthCard(true);
  };

  const closeAuth = () => {
    setShowAuthCard(false);
    setAuthError('');
  };

  const switchAuthTab = (t: 'login' | 'guest') => {
    setAuthTab(t);
    setShowRegister(false);
    setAuthError('');
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    const form = e.target as HTMLFormElement;
    const email = (form.elements.namedItem('login-email') as HTMLInputElement).value;
    const password = (form.elements.namedItem('login-password') as HTMLInputElement).value;
    try {
      const user = await login(email, password);
      onAuth(user);
    } catch (err) {
      setAuthError((err as Error).message);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    const form = e.target as HTMLFormElement;
    const name = (form.elements.namedItem('reg-name') as HTMLInputElement).value;
    const email = (form.elements.namedItem('reg-email') as HTMLInputElement).value;
    const phone = (form.elements.namedItem('reg-phone') as HTMLInputElement).value;
    const password = (form.elements.namedItem('reg-password') as HTMLInputElement).value;
    try {
      const user = await register(name, email, phone, password);
      onAuth(user);
    } catch (err) {
      setAuthError((err as Error).message);
    }
  };

  const handleGuest = async (e: React.FormEvent) => {
    e.preventDefault();
    const form = e.target as HTMLFormElement;
    const name = (form.elements.namedItem('guest-name') as HTMLInputElement).value;
    const phone = (form.elements.namedItem('guest-phone') as HTMLInputElement).value;
    try {
      const user = await guestLogin(name, phone);
      onAuth(user);
    } catch (err) {
      setAuthError((err as Error).message);
    }
  };

  return (
    <div className="welcome-overlay-v2">
      <img
        className="welcome-bg-img"
        src="/img/home-bg.png"
        alt=""
        onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
      />
      <div className="welcome-bg-gradient" />

      <div className={`welcome-v2-content ${mounted ? 'mounted' : ''}`}>
        {/* Nav Bar */}
        <nav className="welcome-v2-nav">
          <div className="welcome-v2-brand">
            <span className="welcome-v2-logo">✈️</span>
            <span className="welcome-v2-brand-name">SkyBook AI</span>
            <span className="welcome-v2-badge">Powered by LangGraph</span>
          </div>
          <div className="welcome-v2-nav-actions">
            <button onClick={() => openAuth('guest')} className="welcome-v2-nav-link">Explore as Guest</button>
            <button onClick={() => openAuth('login')} className="welcome-v2-nav-btn">Login / Register</button>
          </div>
        </nav>

        {/* Hero Section */}
        <section className="welcome-v2-hero">
          <div className="welcome-v2-hero-badge">
            <span className="welcome-v2-hero-badge-dot" />
            AI-Powered Airline Reservation
          </div>
          <h1 className="welcome-v2-hero-title">
            Your AI Co-Pilot for<br />
            <span className="welcome-v2-hero-title-gradient">Seamless Flight Bookings</span>
          </h1>
          <p className="welcome-v2-hero-desc">
            Search flights, book tickets, check in, manage trips, and track refunds —
            all through a simple chat conversation powered by AI.
          </p>

          <div className="welcome-v2-hero-actions">
            <button onClick={() => openAuth('login')} className="welcome-v2-cta-primary">
              <span>Start Your Journey</span>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="5" y1="12" x2="19" y2="12" />
                <polyline points="12 5 19 12 12 19" />
              </svg>
            </button>
            <button onClick={() => openAuth('guest')} className="welcome-v2-cta-secondary">
              Explore as Guest
            </button>
          </div>

          <div className="welcome-v2-stats">
            {STATS.map((s) => (
              <div key={s.label} className="welcome-v2-stat">
                <div className="welcome-v2-stat-value">{s.value}</div>
                <div className="welcome-v2-stat-label">{s.label}</div>
              </div>
            ))}
          </div>
        </section>

        {/* Features Grid */}
        <section className="welcome-v2-features">
          <h2 className="welcome-v2-section-title">Everything you need, in one chat</h2>
          <p className="welcome-v2-section-subtitle">
            From search to boarding — your entire flight experience powered by conversational AI
          </p>
          <div className="welcome-v2-features-grid">
            {FEATURES.map((f) => (
              <div key={f.title} className="welcome-v2-feature-card">
                <div className="welcome-v2-feature-icon">{f.icon}</div>
                <h3 className="welcome-v2-feature-title">{f.title}</h3>
                <p className="welcome-v2-feature-desc">{f.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* How It Works */}
        <section className="welcome-v2-how">
          <h2 className="welcome-v2-section-title">How it works</h2>
          <div className="welcome-v2-steps">
            <div className="welcome-v2-step">
              <div className="welcome-v2-step-num">1</div>
              <div className="welcome-v2-step-content">
                <h4>Tell us what you need</h4>
                <p>Just type naturally — &ldquo;I need a flight from Bangalore to Delhi tomorrow&rdquo;</p>
              </div>
            </div>
            <div className="welcome-v2-step-connector" />
            <div className="welcome-v2-step">
              <div className="welcome-v2-step-num">2</div>
              <div className="welcome-v2-step-content">
                <h4>AI finds the best options</h4>
                <p>Compare fares, cabin classes, and schedules across available flights</p>
              </div>
            </div>
            <div className="welcome-v2-step-connector" />
            <div className="welcome-v2-step">
              <div className="welcome-v2-step-num">3</div>
              <div className="welcome-v2-step-content">
                <h4>Book &amp; manage in chat</h4>
                <p>Select seats, add meals, pay securely, check in, and download your boarding pass</p>
              </div>
            </div>
          </div>
        </section>

        {/* CTA Section */}
        <section className="welcome-v2-cta-section">
          <div className="welcome-v2-cta-card">
            <h2 className="welcome-v2-cta-title">Ready to take off? ✈️</h2>
            <p className="welcome-v2-cta-desc">
              Join thousands of travelers using SkyBook AI for hassle-free flight bookings.
              No account needed to search — login for full booking management &amp; history.
            </p>
            <div className="welcome-v2-cta-actions">
              <button onClick={() => openAuth('login')} className="welcome-v2-cta-primary">
                <span>Get Started</span>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="5" y1="12" x2="19" y2="12" />
                  <polyline points="12 5 19 12 12 19" />
                </svg>
              </button>
              <button onClick={() => openAuth('guest')} className="welcome-v2-cta-secondary">
                Continue as Guest
              </button>
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer className="welcome-v2-footer">
          <div className="welcome-v2-footer-brand">
            <span>✈️ SkyBook AI</span>
            <span className="welcome-v2-footer-sep">·</span>
            <span>Powered by LangGraph &amp; FastAPI</span>
          </div>
          <div className="welcome-v2-footer-links">
            <button onClick={() => openAuth('login')}>Login</button>
            <button onClick={() => openAuth('guest')}>Guest Access</button>
            <a href="/admin">Admin Portal</a>
          </div>
        </footer>
      </div>

      {/* Auth Card — embedded in welcome page */}
      {showAuthCard && (
        <div className="welcome-auth-overlay" onClick={closeAuth}>
          <div className="welcome-auth-card" onClick={(e) => e.stopPropagation()}>
            <div className="welcome-auth-header">
              <h2>{showRegister ? 'Create Account' : 'Welcome to SkyBook AI'}</h2>
              <button onClick={closeAuth} className="welcome-auth-close">&times;</button>
            </div>

            {!showRegister && (
              <div className="welcome-auth-tabs">
                <button className={`welcome-auth-tab ${authTab === 'login' ? 'active' : ''}`} onClick={() => switchAuthTab('login')}>Login</button>
                <button className={`welcome-auth-tab ${authTab === 'guest' ? 'active' : ''}`} onClick={() => switchAuthTab('guest')}>Guest</button>
              </div>
            )}

            {authError && <p className="welcome-auth-error">{authError}</p>}

            {authTab === 'login' && !showRegister && (
              <form className="welcome-auth-form" onSubmit={handleLogin}>
                <input type="email" placeholder="Email" name="login-email" required />
                <input type="password" placeholder="Password" name="login-password" required />
                <button type="submit" className="welcome-auth-submit">Login</button>
                <p className="welcome-auth-switch">
                  Don&apos;t have an account?{' '}
                  <button type="button" onClick={() => { setShowRegister(true); setAuthError(''); }} className="welcome-auth-link">Register here</button>
                </p>
              </form>
            )}

            {showRegister && (
              <form className="welcome-auth-form" onSubmit={handleRegister}>
                <input type="text" placeholder="Full Name" name="reg-name" required />
                <input type="email" placeholder="Email" name="reg-email" required />
                <input type="tel" placeholder="Phone (optional)" name="reg-phone" />
                <input type="password" placeholder="Password (min 6 chars)" name="reg-password" required minLength={6} />
                <button type="submit" className="welcome-auth-submit">Create Account</button>
                <p className="welcome-auth-switch">
                  Already have an account?{' '}
                  <button type="button" onClick={() => { setShowRegister(false); setAuthError(''); }} className="welcome-auth-link">Back to Login</button>
                </p>
              </form>
            )}

            {authTab === 'guest' && !showRegister && (
              <form className="welcome-auth-form" onSubmit={handleGuest}>
                <input type="text" placeholder="Your Name" name="guest-name" required />
                <input type="tel" placeholder="Phone (optional)" name="guest-phone" />
                <button type="submit" className="welcome-auth-submit">Continue as Guest</button>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
