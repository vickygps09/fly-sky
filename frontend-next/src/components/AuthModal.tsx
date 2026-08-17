'use client';

import { useState } from 'react';
import type { User } from '@/types';
import { login, register, guestLogin } from '@/lib/api';

interface AuthModalProps {
  onClose: () => void;
  onAuth: (user: User) => void;
  initialTab?: 'login' | 'register' | 'guest';
}

export default function AuthModal({ onClose, onAuth, initialTab = 'login' }: AuthModalProps) {
  // 'register' is not a tab — it's a sub-view triggered from the login CTA
  const [tab, setTab] = useState<'login' | 'guest'>(initialTab === 'register' ? 'login' : initialTab);
  const [showRegister, setShowRegister] = useState(initialTab === 'register');
  const [error, setError] = useState('');

  const switchTab = (t: 'login' | 'guest') => {
    setTab(t);
    setShowRegister(false);
    setError('');
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
      setError((err as Error).message);
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
      setError((err as Error).message);
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
      setError((err as Error).message);
    }
  };

  return (
    <div className="modal" style={{ display: 'flex' }}>
      <div className="modal-content">
        <div className="modal-header">
          <h2>{showRegister ? 'Create Account' : 'Welcome to SkyBook AI'}</h2>
          <button onClick={onClose} className="modal-close">&times;</button>
        </div>

        {/* Only show tabs when not in register sub-view */}
        {!showRegister && (
          <div className="auth-tabs">
            <button className={`auth-tab ${tab === 'login' ? 'active' : ''}`} onClick={() => switchTab('login')}>Login</button>
            <button className={`auth-tab ${tab === 'guest' ? 'active' : ''}`} onClick={() => switchTab('guest')}>Guest</button>
          </div>
        )}

        {error && <p style={{ color: 'var(--danger)', fontSize: '13px', marginBottom: '10px' }}>{error}</p>}

        {/* Login form with Register CTA */}
        {tab === 'login' && !showRegister && (
          <form className="auth-form" onSubmit={handleLogin} style={{ display: 'flex' }}>
            <input type="email" placeholder="Email" name="login-email" required />
            <input type="password" placeholder="Password" name="login-password" required />
            <button type="submit" className="btn-primary full-width">Login</button>
            <p style={{ textAlign: 'center', fontSize: '13px', color: 'var(--text-muted)', marginTop: '8px' }}>
              Don&apos;t have an account?{' '}
              <button
                type="button"
                onClick={() => { setShowRegister(true); setError(''); }}
                style={{ background: 'none', border: 'none', color: 'var(--primary)', fontWeight: 600, cursor: 'pointer', fontSize: '13px', padding: 0 }}
              >
                Register here
              </button>
            </p>
          </form>
        )}

        {/* Register sub-view (not a tab) */}
        {showRegister && (
          <form className="auth-form" onSubmit={handleRegister} style={{ display: 'flex' }}>
            <input type="text" placeholder="Full Name" name="reg-name" required />
            <input type="email" placeholder="Email" name="reg-email" required />
            <input type="tel" placeholder="Phone (optional)" name="reg-phone" />
            <input type="password" placeholder="Password (min 6 chars)" name="reg-password" required minLength={6} />
            <button type="submit" className="btn-primary full-width">Create Account</button>
            <p style={{ textAlign: 'center', fontSize: '13px', color: 'var(--text-muted)', marginTop: '8px' }}>
              Already have an account?{' '}
              <button
                type="button"
                onClick={() => { setShowRegister(false); setError(''); }}
                style={{ background: 'none', border: 'none', color: 'var(--primary)', fontWeight: 600, cursor: 'pointer', fontSize: '13px', padding: 0 }}
              >
                Back to Login
              </button>
            </p>
          </form>
        )}

        {/* Guest form */}
        {tab === 'guest' && !showRegister && (
          <form className="auth-form" onSubmit={handleGuest} style={{ display: 'flex' }}>
            <input type="text" placeholder="Your Name" name="guest-name" required />
            <input type="tel" placeholder="Phone (optional)" name="guest-phone" />
            <button type="submit" className="btn-primary full-width">Continue as Guest</button>
          </form>
        )}
      </div>
    </div>
  );
}
