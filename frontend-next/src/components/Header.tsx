'use client';

import type { User } from '@/types';

interface HeaderProps {
  user: User | null;
  onToggleSidebar: () => void;
  onLoginClick: () => void;
  onLogout: () => void;
  onAdminClick: () => void;
}

export default function Header({
  user,
  onToggleSidebar,
  onLoginClick,
  onLogout,
  onAdminClick,
}: HeaderProps) {
  return (
    <header className="app-header">
      <div className="header-left">
        <button className="sidebar-toggle" onClick={onToggleSidebar}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>
        <div className="logo">✈️ SkyBook AI</div>
        <span className="badge">Powered by LangGraph</span>
      </div>
      <div className="header-right">
        {user && (
          <div className="user-info" style={{ display: 'flex' }}>
            <span>👋 {user.name}</span>
            <button onClick={onLogout} className="btn-link">Logout</button>
          </div>
        )}
        {!user && (
          <button onClick={onLoginClick} className="btn-primary">Login</button>
        )}
        <button onClick={onAdminClick} className="btn-link">Admin</button>
      </div>
    </header>
  );
}
