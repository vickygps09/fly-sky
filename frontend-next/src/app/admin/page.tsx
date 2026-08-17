'use client';

import { useState, useEffect, useCallback, Fragment } from 'react';

// Types
interface AdminDashboardData {
  total_bookings: number;
  total_revenue: number;
  total_cancellations: number;
  total_refunds: number;
  active_flights: number;
  total_users: number;
  booking_trends: Array<{ date: string; bookings: number }>;
  popular_routes: Array<{ route: string; bookings: number }>;
}

interface AdminFlight {
  id: string;
  flight_number: string;
  airline_name: string;
  route: string;
  departure_time: string;
  status: string;
  is_active: boolean;
}

interface PaxValidation {
  field: string;
  valid: boolean;
  message: string;
}

interface AdminPassenger {
  id?: string;
  full_name: string;
  age: number | null;
  gender: string | null;
  seat_number: string | null;
  meal_preference: string;
  is_primary: boolean;
  passport_number: string | null;
  all_valid: boolean;
  validations: PaxValidation[];
}

interface ContactValidation {
  field: string;
  valid: boolean;
  message: string;
}

interface AdminBooking {
  id: string;
  pnr: string;
  flight_number: string;
  route: string;
  passenger_count: number;
  total_amount: number;
  booking_status: string;
  all_valid: boolean;
  created_at: string;
  passengers: AdminPassenger[];
  contact_validations: ContactValidation[];
  travel_insurance: boolean;
  extra_baggage_kg: number;
}

interface AdminRefund {
  id: string;
  booking_pnr: string;
  refund_amount: number;
  refund_status: string;
  reason: string | null;
  created_at: string;
}

interface AdminUser {
  name: string;
  email: string;
  phone: string | null;
  role: string;
  is_guest: boolean;
  is_verified: boolean;
  created_at: string;
}

interface AdminChat {
  session_id: string;
  message_count: number;
  is_escalated: boolean;
  summary: string | null;
  created_at: string;
}

interface AdminAIResponse {
  intent: string | null;
  content: string;
  created_at: string;
}

interface AdminAirport {
  id: string;
  code: string;
  name: string;
  city: string;
  country: string;
  timezone: string;
  terminals: number;
}

interface AdminPromotion {
  id: string;
  title: string;
  description: string | null;
  discount_type: string;
  discount_value: number;
  promo_code: string;
  valid_from: string | null;
  valid_until: string | null;
  is_active: boolean;
  max_uses: number;
  used_count: number;
}

interface AdminCoupon {
  id: string;
  code: string;
  discount_type: string;
  discount_value: number;
  min_booking_amount: number;
  max_discount_amount: number | null;
  valid_from: string | null;
  valid_until: string | null;
  is_active: boolean;
  max_uses: number;
  used_count: number;
}

interface AdminCSAT {
  total_ratings: number;
  average_rating: number;
  distribution: Record<number, number>;
  recent: Array<{ id: string; session_id: string; rating: number; feedback: string | null; intent: string | null; created_at: string }>;
}

interface SystemHealth {
  status: string;
  app: string;
  version: string;
  uptime_seconds: number;
  dependencies: {
    database: string;
    llm_provider: string;
  };
  system: {
    python_version: string;
    platform: string;
    cpu_percent: number;
    memory_total_mb: number;
    memory_used_mb: number;
    memory_percent: number;
  };
}

interface SystemMetrics {
  bookings: { total: number; confirmed: number; pending: number; cancelled: number };
  flights: { active: number };
  users: { total: number };
  conversations: { total: number };
  revenue: { total: number };
  csat: { average: number; count: number };
  uptime_seconds: number;
}

interface AIMetrics {
  intent_recognition: {
    accuracy: number; macro_precision: number; macro_recall: number; macro_f1: number;
    per_class: Record<string, any>; total: number; correct: number;
    results: Array<{ message: string; expected: string; predicted: string; pass: boolean }>;
  };
  entity_extraction: {
    accuracy: number; macro_precision: number; macro_recall: number; macro_f1: number;
    per_field: Record<string, any>; total: number; correct: number;
    results: Array<{ message: string; expected: any; predicted: any; pass: boolean }>;
  };
  rag_retrieval: { accuracy: number; avg_confidence: number; total: number; correct: number; method_counts: Record<string, number> };
  route_extraction: { accuracy: number; total: number; correct: number };
  hallucination: { total_tested: number; hallucinations_detected: number; hallucination_rate: number; details: Array<{ query: string; matched: string; confidence: number }> };
}

interface APIStats {
  uptime_seconds: number;
  api: {
    total_requests: number; total_success: number; total_failure: number; availability: number;
    per_endpoint: Record<string, { total: number; success: number; failure: number; errors: Array<any> }>;
  };
  llm: { total: number; success: number; failure: number; timeouts: number };
  rag_retrieval: { total: number; success: number; failure: number };
}

interface AdminReports {
  total_bookings?: number;
  by_status?: Record<string, number>;
  by_cabin_class?: Record<string, number>;
  revenue_by_cabin?: Record<string, number>;
  total_cancelled?: number;
  total_refunded?: number;
  pending_refunds?: number;
  cancellation_reasons?: Array<{ reason: string; count: number }>;
  total_revenue?: number;
  monthly_revenue?: Array<{ month: string; revenue: number }>;
}

type TabName = 'overview' | 'flights' | 'bookings' | 'refunds' | 'users' | 'chat' | 'ai' | 'airports' | 'promotions' | 'coupons' | 'csat' | 'reports' | 'monitoring';

const NAV_ITEMS: { tab: TabName; icon: string; label: string }[] = [
  { tab: 'overview', icon: '📊', label: 'Overview' },
  { tab: 'flights', icon: '🛫', label: 'Flights' },
  { tab: 'airports', icon: '🏢', label: 'Airports' },
  { tab: 'bookings', icon: '🎫', label: 'Bookings' },
  { tab: 'refunds', icon: '💰', label: 'Refunds' },
  { tab: 'promotions', icon: '🎁', label: 'Promotions' },
  { tab: 'coupons', icon: '🏷️', label: 'Coupons' },
  { tab: 'users', icon: '👥', label: 'Users' },
  { tab: 'chat', icon: '💬', label: 'Chat History' },
  { tab: 'ai', icon: '🤖', label: 'AI Responses' },
  { tab: 'csat', icon: '⭐', label: 'CSAT' },
  { tab: 'reports', icon: '📈', label: 'Reports' },
  { tab: 'monitoring', icon: '🖥️', label: 'System Monitor' },
];

function statusBadge(status: string): string {
  const map: Record<string, string> = {
    confirmed: 'success', success: 'success', completed: 'success', arrived: 'success',
    pending: 'warning', processing: 'warning', scheduled: 'warning', boarding: 'warning',
    cancelled: 'danger', rejected: 'danger', failed: 'danger',
    departed: 'info', delayed: 'warning', refunded: 'info',
  };
  return map[status] || 'default';
}

const MEAL_LABELS: Record<string, string> = {
  veg: '🥗 Veg', non_veg: '🍗 Non-Veg', jain: '🌱 Jain', none: 'No Meal',
};

export default function AdminPage() {
  const [adminToken, setAdminToken] = useState<string | null>(null);
  const [showDashboard, setShowDashboard] = useState(false);
  const [loginError, setLoginError] = useState('');
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [email, setEmail] = useState('admin@skybook.ai');
  const [password, setPassword] = useState('admin123');
  const [activeTab, setActiveTab] = useState<TabName>('overview');

  // Data states
  const [dashboardData, setDashboardData] = useState<AdminDashboardData | null>(null);
  const [flights, setFlights] = useState<AdminFlight[]>([]);
  const [bookings, setBookings] = useState<AdminBooking[]>([]);
  const [refunds, setRefunds] = useState<AdminRefund[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [chatHistory, setChatHistory] = useState<AdminChat[]>([]);
  const [aiResponses, setAIResponses] = useState<AdminAIResponse[]>([]);
  const [expandedBooking, setExpandedBooking] = useState<string | null>(null);
  const [airports, setAirports] = useState<AdminAirport[]>([]);
  const [promotions, setPromotions] = useState<AdminPromotion[]>([]);
  const [coupons, setCoupons] = useState<AdminCoupon[]>([]);
  const [csatData, setCSATData] = useState<AdminCSAT | null>(null);
  const [reportData, setReportData] = useState<AdminReports | null>(null);
  const [reportSubTab, setReportSubTab] = useState<'booking' | 'cancellation' | 'revenue'>('booking');
  const [healthData, setHealthData] = useState<SystemHealth | null>(null);
  const [metricsData, setMetricsData] = useState<SystemMetrics | null>(null);
  const [aiMetrics, setAIMetrics] = useState<AIMetrics | null>(null);
  const [apiStats, setApiStats] = useState<APIStats | null>(null);
  const [aiLoading, setAILoading] = useState(false);

  // Modal/form state
  const [showModal, setShowModal] = useState(false);
  const [modalTitle, setModalTitle] = useState('');
  const [modalContent, setModalContent] = useState<React.ReactNode>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  const api = useCallback(async (path: string) => {
    const resp = await fetch(path, { headers: { Authorization: `Bearer ${adminToken}` } });
    if (resp.status === 401) {
      handleLogout();
      throw new Error('Unauthorized');
    }
    if (!resp.ok) {
      const text = await resp.text().catch(() => '');
      console.error(`Admin API error ${resp.status} for ${path}:`, text);
      throw new Error(`API error ${resp.status}`);
    }
    return resp.json();
  }, [adminToken]);

  const apiPut = useCallback(async (path: string) => {
    const resp = await fetch(path, { method: 'PUT', headers: { Authorization: `Bearer ${adminToken}` } });
    if (!resp.ok) {
      const text = await resp.text().catch(() => '');
      console.error(`Admin PUT error ${resp.status} for ${path}:`, text);
      throw new Error(`API error ${resp.status}`);
    }
    return resp.json();
  }, [adminToken]);

  const apiPost = useCallback(async (path: string, body: any) => {
    const resp = await fetch(path, {
      method: 'POST',
      headers: { Authorization: `Bearer ${adminToken}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      const text = await resp.text().catch(() => '');
      console.error(`Admin POST error ${resp.status} for ${path}:`, text);
      throw new Error(`API error ${resp.status}: ${text}`);
    }
    return resp.json();
  }, [adminToken]);

  const apiDelete = useCallback(async (path: string) => {
    const resp = await fetch(path, { method: 'DELETE', headers: { Authorization: `Bearer ${adminToken}` } });
    if (!resp.ok) {
      const text = await resp.text().catch(() => '');
      console.error(`Admin DELETE error ${resp.status} for ${path}:`, text);
      throw new Error(`API error ${resp.status}`);
    }
    return resp.json();
  }, [adminToken]);

  function showActionMsg(msg: string) {
    setActionMsg(msg);
    setTimeout(() => setActionMsg(null), 5000);
  }

  function openModal(title: string, content: React.ReactNode) {
    setModalTitle(title);
    setModalContent(content);
    setShowModal(true);
  }

  function closeModal() {
    setShowModal(false);
    setModalContent(null);
    setModalTitle('');
  }

  async function cancelFlightWithCascade(id: string, flightNumber: string) {
    if (!confirm(`Cancel flight ${flightNumber}? ALL active bookings for this flight will be cancelled and refunded.`)) return;
    try {
      const result = await apiDelete(`/api/admin/flights/${id}`);
      showActionMsg(`✈️ ${result.message || 'Flight cancelled'}`);
      api('/api/admin/flights').then((data: AdminFlight[]) => setFlights(data)).catch(() => {});
    } catch (err: any) {
      showActionMsg(`❌ Failed to cancel flight: ${err.message}`);
    }
  }

  async function cancelBooking(bookingId: string, pnr: string) {
    const reason = prompt(`Cancel booking ${pnr}? Enter reason (optional):`);
    if (reason === null) return;
    try {
      await apiPut(`/api/admin/bookings/${bookingId}/status?status=cancelled${reason ? `&reason=${encodeURIComponent(reason)}` : ''}`);
      showActionMsg(`🎫 Booking ${pnr} cancelled. Refund initiated.`);
      api('/api/admin/bookings').then((data: AdminBooking[]) => setBookings(data)).catch(() => {});
    } catch (err: any) {
      showActionMsg(`❌ Failed to cancel booking: ${err.message}`);
    }
  }

  async function changeBookingStatus(bookingId: string, status: string) {
    try {
      await apiPut(`/api/admin/bookings/${bookingId}/status?status=${status}`);
      showActionMsg(`🎫 Booking status changed to ${status}`);
      api('/api/admin/bookings').then((data: AdminBooking[]) => setBookings(data)).catch(() => {});
    } catch (err: any) {
      showActionMsg(`❌ Failed to update booking: ${err.message}`);
    }
  }

  function openAddFlightModal() {
    openModal('Add New Flight', (
      <FlightForm
        airports={airports}
        onSubmit={async (data) => {
          try {
            await apiPost('/api/admin/flights', data);
            showActionMsg('✈️ Flight created successfully');
            closeModal();
            api('/api/admin/flights').then((d: AdminFlight[]) => setFlights(d)).catch(() => {});
          } catch (err: any) {
            showActionMsg(`❌ Failed to create flight: ${err.message}`);
          }
        }}
        onCancel={closeModal}
      />
    ));
  }

  function openEditPassengerModal(bookingId: string, p: AdminPassenger) {
    openModal(`Edit Passenger: ${p.full_name}`, (
      <PassengerEditForm
        passenger={p}
        onSubmit={async (data) => {
          const params = new URLSearchParams();
          if (data.full_name) params.set('full_name', data.full_name);
          if (data.age) params.set('age', String(data.age));
          if (data.gender) params.set('gender', data.gender);
          if (data.seat_number !== undefined) params.set('seat_number', data.seat_number);
          if (data.meal_preference) params.set('meal_preference', data.meal_preference);
          try {
            await apiPut(`/api/admin/bookings/${bookingId}/passenger/${p.id || ''}?${params.toString()}`);
            showActionMsg('👤 Passenger updated successfully');
            closeModal();
            api('/api/admin/bookings').then((d: AdminBooking[]) => setBookings(d)).catch(() => {});
          } catch (err: any) {
            showActionMsg(`❌ Failed to update passenger: ${err.message}`);
          }
        }}
        onCancel={closeModal}
      />
    ));
  }

  function openAddAirportModal() {
    openModal('Add New Airport', (
      <AirportForm
        onSubmit={async (data) => {
          try {
            await apiPost('/api/admin/airports', data);
            showActionMsg('🏢 Airport created successfully');
            closeModal();
            api('/api/admin/airports').then((d: AdminAirport[]) => setAirports(d)).catch(() => {});
          } catch (err: any) {
            showActionMsg(`❌ Failed to create airport: ${err.message}`);
          }
        }}
        onCancel={closeModal}
      />
    ));
  }

  function openAddPromotionModal() {
    openModal('Add New Promotion', (
      <PromotionForm
        onSubmit={async (data) => {
          try {
            await apiPost('/api/admin/promotions', data);
            showActionMsg('🎁 Promotion created successfully');
            closeModal();
            api('/api/admin/promotions').then((d: AdminPromotion[]) => setPromotions(d)).catch(() => {});
          } catch (err: any) {
            showActionMsg(`❌ Failed to create promotion: ${err.message}`);
          }
        }}
        onCancel={closeModal}
      />
    ));
  }

  function openAddCouponModal() {
    openModal('Add New Coupon', (
      <CouponForm
        onSubmit={async (data) => {
          try {
            await apiPost('/api/admin/coupons', data);
            showActionMsg('🏷️ Coupon created successfully');
            closeModal();
            api('/api/admin/coupons').then((d: AdminCoupon[]) => setCoupons(d)).catch(() => {});
          } catch (err: any) {
            showActionMsg(`❌ Failed to create coupon: ${err.message}`);
          }
        }}
        onCancel={closeModal}
      />
    ));
  }

  function handleLogout() {
    setAdminToken(null);
    setShowDashboard(false);
    if (typeof window !== 'undefined') {
      localStorage.removeItem('admin_token');
    }
  }

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoginError('');
    try {
      const resp = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = await resp.json();
      if (data.access_token) {
        setAdminToken(data.access_token);
        if (typeof window !== 'undefined') {
          localStorage.setItem('admin_token', data.access_token);
        }
        setShowDashboard(true);
      } else {
        setLoginError(data.detail || 'Login failed');
      }
    } catch {
      setLoginError('Connection error');
    }
  }

  // Load token on mount
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('admin_token');
      if (token) {
        setAdminToken(token);
        // Verify token
        fetch('/api/admin/dashboard', { headers: { Authorization: `Bearer ${token}` } })
          .then((r) => {
            if (r.ok) {
              setShowDashboard(true);
            } else {
              localStorage.removeItem('admin_token');
              setAdminToken(null);
            }
          })
          .catch(() => {
            localStorage.removeItem('admin_token');
            setAdminToken(null);
          });
      }
    }
  }, []);

  // Load data when tab changes
  useEffect(() => {
    if (!showDashboard || !adminToken) return;

    setIsLoading(true);
    setLoadError(null);

    const loadPath = (path: string) => api(path).then((data) => {
      setIsLoading(false);
      return data;
    }).catch((err) => {
      setLoadError(err.message || 'Failed to load data');
      setIsLoading(false);
      return null;
    });

    if (activeTab === 'overview') {
      loadPath('/api/admin/dashboard').then((data) => { if (data) setDashboardData(data as AdminDashboardData); });
    } else if (activeTab === 'flights') {
      loadPath('/api/admin/flights').then((data) => { if (data) setFlights(data as AdminFlight[]); });
    } else if (activeTab === 'bookings') {
      loadPath('/api/admin/bookings').then((data) => { if (data) setBookings(data as AdminBooking[]); });
    } else if (activeTab === 'refunds') {
      loadPath('/api/admin/refunds').then((data) => { if (data) setRefunds(data as AdminRefund[]); });
    } else if (activeTab === 'users') {
      loadPath('/api/admin/users').then((data) => { if (data) setUsers(data as AdminUser[]); });
    } else if (activeTab === 'chat') {
      loadPath('/api/admin/chat-history').then((data) => { if (data) setChatHistory(data as AdminChat[]); });
    } else if (activeTab === 'ai') {
      loadPath('/api/admin/ai-responses').then((data) => { if (data) setAIResponses(data as AdminAIResponse[]); });
    } else if (activeTab === 'airports') {
      loadPath('/api/admin/airports').then((data) => { if (data) setAirports(data as AdminAirport[]); });
    } else if (activeTab === 'promotions') {
      loadPath('/api/admin/promotions').then((data) => { if (data) setPromotions(data as AdminPromotion[]); });
    } else if (activeTab === 'coupons') {
      loadPath('/api/admin/coupons').then((data) => { if (data) setCoupons(data as AdminCoupon[]); });
    } else if (activeTab === 'csat') {
      loadPath('/api/admin/csat').then((data) => { if (data) setCSATData(data as AdminCSAT); });
    } else if (activeTab === 'reports') {
      const subPath = reportSubTab === 'booking' ? 'booking-summary' : reportSubTab === 'cancellation' ? 'cancellation' : 'revenue';
      loadPath(`/api/admin/reports/${subPath}`).then((data) => { if (data) setReportData(data as AdminReports); });
    } else if (activeTab === 'monitoring') {
      loadPath('/api/health/detailed').then((data) => { if (data) setHealthData(data as SystemHealth); });
      loadPath('/api/metrics').then((data) => { if (data) setMetricsData(data as SystemMetrics); });
      loadPath('/api/admin/api-stats').then((data) => { if (data) setApiStats(data as APIStats); });
    }
  }, [activeTab, reportSubTab, showDashboard, adminToken, api]);

  async function toggleFlightStatus(id: string, current: string) {
    const statuses = ['scheduled', 'boarding', 'departed', 'arrived', 'delayed', 'cancelled'];
    const idx = statuses.indexOf(current);
    const next = statuses[(idx + 1) % statuses.length];
    await apiPut(`/api/admin/flights/${id}/status?status=${next}`);
    api('/api/admin/flights').then((data: AdminFlight[]) => setFlights(data)).catch(() => {});
  }

  async function deactivateFlight(id: string) {
    if (!confirm('Deactivate this flight?')) return;
    await apiDelete(`/api/admin/flights/${id}`);
    api('/api/admin/flights').then((data: AdminFlight[]) => setFlights(data)).catch(() => {});
  }

  async function updateRefund(id: string, status: string) {
    await apiPut(`/api/admin/refunds/${id}/status?status=${status}`);
    api('/api/admin/refunds').then((data: AdminRefund[]) => setRefunds(data)).catch(() => {});
  }

  // Login gate
  if (!showDashboard) {
    return (
      <div className="admin-body">
        <div className="admin-login-gate">
          <div className="admin-login-card">
            <div className="admin-login-logo">✈️ SkyBook AI</div>
            <h2>Admin Portal</h2>
            <p>Sign in with your admin credentials to access the dashboard.</p>
            <form onSubmit={handleLogin}>
              <input
                type="email"
                placeholder="Admin email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
              <input
                type="password"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
              <button type="submit" className="admin-btn-primary">Login</button>
              <div className="admin-error-msg">{loginError}</div>
            </form>
            <a href="/" className="admin-back-link">← Back to Chat</a>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="admin-body">
      <div className="admin-dashboard">
        {/* Sidebar */}
        <aside className="admin-sidebar">
          <div className="admin-sidebar-logo">✈️ SkyBook AI</div>
          <nav className="admin-sidebar-nav">
            {NAV_ITEMS.map((item) => (
              <div
                key={item.tab}
                className={`admin-nav-item ${activeTab === item.tab ? 'active' : ''}`}
                onClick={() => setActiveTab(item.tab)}
              >
                {item.icon} {item.label}
              </div>
            ))}
          </nav>
          <div className="admin-sidebar-footer">
            <a href="/" className="admin-back-link">← Back to Chat</a>
            <button onClick={handleLogout} className="admin-btn-link">Logout</button>
          </div>
        </aside>

        {/* Main Content */}
        <main className="admin-main-content">
          {loadError && (
            <div className="admin-error-banner" style={{
              background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.4)',
              borderRadius: '8px', padding: '12px 16px', marginBottom: '16px',
              color: '#fca5a5', fontSize: '0.9rem',
            }}>
              ⚠️ Error loading data: {loadError}. <button onClick={() => setActiveTab(activeTab)} style={{ background: 'none', border: 'none', color: '#fca5a5', textDecoration: 'underline', cursor: 'pointer' }}>Retry</button>
            </div>
          )}
          {isLoading && (
            <div style={{ color: 'rgba(255,255,255,0.5)', padding: '8px 0', fontSize: '0.9rem' }}>Loading...</div>
          )}
          {/* Overview Tab */}
          {activeTab === 'overview' && (
            <div className="admin-tab-content active">
              <h1>📊 Dashboard Overview</h1>
              {dashboardData ? (
                <>
                  <div className="admin-stats-grid">
                    {[
                      { icon: '🎫', value: dashboardData.total_bookings, label: 'Total Bookings' },
                      { icon: '💰', value: `₹${dashboardData.total_revenue.toLocaleString()}`, label: 'Total Revenue' },
                      { icon: '❌', value: dashboardData.total_cancellations, label: 'Cancellations' },
                      { icon: '↩️', value: `₹${dashboardData.total_refunds.toLocaleString()}`, label: 'Total Refunds' },
                      { icon: '🛫', value: dashboardData.active_flights, label: 'Active Flights' },
                      { icon: '👥', value: dashboardData.total_users, label: 'Total Users' },
                    ].map((s) => (
                      <div key={s.label} className="admin-stat-card">
                        <div className="stat-icon">{s.icon}</div>
                        <div className="stat-value">{s.value}</div>
                        <div className="stat-label">{s.label}</div>
                      </div>
                    ))}
                  </div>
                  <div className="admin-charts-row">
                    <div className="admin-card">
                      <h3>📈 Booking Trends (7 days)</h3>
                      <div className="admin-bar-chart">
                        {(dashboardData.booking_trends || []).map((t, i) => {
                          const maxBookings = Math.max(...(dashboardData.booking_trends || []).map((x) => x.bookings), 1);
                          const h = (t.bookings / maxBookings) * 100;
                          const d = new Date(t.date);
                          const label = `${d.getMonth() + 1}/${d.getDate()}`;
                          return (
                            <div key={i} className="admin-bar-item">
                              <div className="admin-bar" style={{ height: `${h}%` }} />
                              <div className="admin-bar-label">{label}</div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                    <div className="admin-card">
                      <h3>🔥 Popular Routes</h3>
                      {(dashboardData.popular_routes || []).length > 0 ? (
                        (dashboardData.popular_routes || []).map((r, i) => (
                          <div key={i} className="admin-route-item">
                            <span className="admin-route-name">{r.route}</span>
                            <span className="admin-route-count">{r.bookings} bookings</span>
                          </div>
                        ))
                      ) : (
                        <p style={{ color: '#999' }}>No data yet</p>
                      )}
                    </div>
                  </div>
                </>
              ) : (
                <p style={{ color: 'rgba(255,255,255,0.5)' }}>Loading...</p>
              )}
            </div>
          )}

          {/* Flights Tab */}
          {activeTab === 'flights' && (
            <div className="admin-tab-content active">
              <div className="admin-tab-header">
                <h1>🛫 Flight Management</h1>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button className="admin-btn-primary" style={{ padding: '8px 16px', fontSize: '0.85rem' }} onClick={() => openAddFlightModal()}>+ Add Flight</button>
                  <button className="admin-btn-secondary" onClick={() => api('/api/admin/flights').then((data: AdminFlight[]) => setFlights(data))}>Refresh</button>
                </div>
              </div>
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead><tr><th>Flight</th><th>Airline</th><th>Route</th><th>Departure</th><th>Status</th><th>Active</th><th>Actions</th></tr></thead>
                  <tbody>
                    {flights.length === 0 ? (
                      <tr><td colSpan={7} style={{ textAlign: 'center', color: '#999', padding: '24px' }}>No flights found</td></tr>
                    ) : flights.slice(0, 50).map((f) => (
                      <tr key={f.id}>
                        <td><strong>{f.flight_number}</strong></td>
                        <td>{f.airline_name}</td>
                        <td>{f.route}</td>
                        <td>{f.departure_time ? new Date(f.departure_time).toLocaleString() : '-'}</td>
                        <td><span className={`admin-badge admin-badge-${statusBadge(f.status)}`}>{f.status}</span></td>
                        <td>{f.is_active ? '✅' : '❌'}</td>
                        <td>
                          <button className="admin-btn-sm" onClick={() => toggleFlightStatus(f.id, f.status)}>Cycle Status</button>
                          <button className="admin-btn-sm" onClick={() => cancelFlightWithCascade(f.id, f.flight_number)} style={{ color: '#ef4444', marginLeft: '4px' }}>Cancel Flight</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Bookings Tab */}
          {activeTab === 'bookings' && (
            <div className="admin-tab-content active">
              <div className="admin-tab-header">
                <h1>🎫 All Bookings</h1>
                <button className="admin-btn-secondary" onClick={() => api('/api/admin/bookings').then((data: AdminBooking[]) => setBookings(data))}>Refresh</button>
              </div>
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead><tr><th>PNR</th><th>Flight</th><th>Route</th><th>Passengers</th><th>Amount</th><th>Status</th><th>Validations</th><th>Created</th><th>Details</th></tr></thead>
                  <tbody>
                    {bookings.length === 0 ? (
                      <tr><td colSpan={9} style={{ textAlign: 'center', color: '#999', padding: '24px' }}>No bookings found</td></tr>
                    ) : bookings.map((b) => (
                      <Fragment key={b.id}>
                        <tr
                          className="admin-booking-row"
                          onClick={() => setExpandedBooking(expandedBooking === b.id ? null : b.id)}
                        >
                          <td><strong>{b.pnr}</strong></td>
                          <td>{b.flight_number}</td>
                          <td>{b.route}</td>
                          <td>{b.passenger_count}</td>
                          <td>₹{b.total_amount.toLocaleString()}</td>
                          <td><span className={`admin-badge admin-badge-${statusBadge(b.booking_status)}`}>{b.booking_status}</span></td>
                          <td>{b.all_valid
                            ? <span className="admin-badge admin-badge-success">✅ All Valid</span>
                            : <span className="admin-badge admin-badge-warning">⚠️ Incomplete</span>}</td>
                          <td>{b.created_at ? new Date(b.created_at).toLocaleDateString() : '-'}</td>
                          <td><button className="admin-btn-sm" onClick={(e) => { e.stopPropagation(); setExpandedBooking(expandedBooking === b.id ? null : b.id); }}>Expand ▾</button></td>
                        </tr>
                        {expandedBooking === b.id && (
                          <tr className="admin-booking-detail-row">
                            <td colSpan={9}>
                              <div className="admin-booking-detail-content">
                                <div className="admin-detail-section">
                                  <h4>� Booking Actions</h4>
                                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                                    {b.booking_status !== 'cancelled' && b.booking_status !== 'completed' && (
                                      <button className="admin-btn-sm" style={{ color: '#ef4444', borderColor: 'rgba(239,68,68,0.3)' }} onClick={() => cancelBooking(b.id, b.pnr)}>Cancel Booking</button>
                                    )}
                                    {b.booking_status === 'pending' && (
                                      <button className="admin-btn-sm" style={{ color: '#4ade80', borderColor: 'rgba(74,222,128,0.3)' }} onClick={() => changeBookingStatus(b.id, 'confirmed')}>Confirm Booking</button>
                                    )}
                                    {b.booking_status === 'cancelled' && (
                                      <button className="admin-btn-sm" style={{ color: '#a5b4fc' }} onClick={() => changeBookingStatus(b.id, 'confirmed')}>Reactivate Booking</button>
                                    )}
                                    {b.booking_status === 'confirmed' && (
                                      <button className="admin-btn-sm" style={{ color: '#fbbf24', borderColor: 'rgba(251,191,36,0.3)' }} onClick={() => changeBookingStatus(b.id, 'modified')}>Mark Modified</button>
                                    )}
                                  </div>
                                </div>
                                <div className="admin-detail-section">
                                  <h4>�� Contact Details</h4>
                                  <div className="admin-detail-contact">
                                    {(b.contact_validations || []).map((v, i) => (
                                      <span key={i} className={`admin-badge admin-badge-${v.valid ? 'success' : 'danger'}`} title={v.message}>
                                        {v.valid ? '✅' : '❌'} {v.field}: {v.message}
                                      </span>
                                    ))}
                                  </div>
                                </div>
                                <div className="admin-detail-section">
                                  <h4>🧳 Add-ons</h4>
                                  <div>
                                    {b.travel_insurance && <span className="admin-badge admin-badge-info" style={{ marginRight: '6px' }}>🛡️ Insurance</span>}
                                    {b.extra_baggage_kg > 0 && <span className="admin-badge admin-badge-info">🧳 +{b.extra_baggage_kg}kg Baggage</span>}
                                    {!b.travel_insurance && b.extra_baggage_kg === 0 && <span style={{ color: 'rgba(255,255,255,0.3)', fontSize: '0.8rem' }}>None</span>}
                                  </div>
                                </div>
                                <div className="admin-detail-section">
                                  <h4>👤 Passenger Details & Validations</h4>
                                  <div className="admin-pax-list">
                                    {(b.passengers || []).map((p, i) => (
                                      <div key={i} className="admin-pax-detail-card">
                                        <div className="admin-pax-detail-header">
                                          <span className="admin-pax-num">{i + 1}</span>
                                          <strong>{p.full_name}</strong>
                                          {p.is_primary && <span className="admin-badge admin-badge-info">Primary</span>}
                                          <button className="admin-btn-sm" style={{ marginLeft: 'auto', fontSize: '0.75rem' }} onClick={() => openEditPassengerModal(b.id, p)}>Edit</button>
                                        </div>
                                        <div className="admin-pax-detail-grid">
                                          <div><span className="admin-pax-label">Age</span><span className="admin-pax-value">{p.age || '-'}</span></div>
                                          <div><span className="admin-pax-label">Gender</span><span className="admin-pax-value">{p.gender || '-'}</span></div>
                                          <div><span className="admin-pax-label">Seat</span><span className="admin-pax-value">{p.seat_number || '-'}</span></div>
                                          <div><span className="admin-pax-label">Meal</span><span className="admin-pax-value">{MEAL_LABELS[p.meal_preference] || p.meal_preference || '-'}</span></div>
                                          <div><span className="admin-pax-label">Passport</span><span className="admin-pax-value">{p.passport_number || '-'}</span></div>
                                        </div>
                                        <div className="admin-pax-validations">
                                          {(p.validations || []).map((v, j) => {
                                            const cls = v.valid ? 'success' : (v.field === 'passport' ? 'default' : 'danger');
                                            const icon = v.valid ? '✅' : (v.field === 'passport' ? '➖' : '❌');
                                            return <span key={j} className={`admin-badge admin-badge-${cls}`} title={v.message}>{icon} {v.field}</span>;
                                          })}
                                        </div>
                                      </div>
                                    ))}
                                    {(!b.passengers || b.passengers.length === 0) && <p style={{ color: 'rgba(255,255,255,0.3)' }}>No passenger data</p>}
                                  </div>
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Refunds Tab */}
          {activeTab === 'refunds' && (
            <div className="admin-tab-content active">
              <div className="admin-tab-header">
                <h1>💰 Refund Management</h1>
                <button className="admin-btn-secondary" onClick={() => api('/api/admin/refunds').then((data: AdminRefund[]) => setRefunds(data))}>Refresh</button>
              </div>
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead><tr><th>PNR</th><th>Amount</th><th>Status</th><th>Reason</th><th>Created</th><th>Actions</th></tr></thead>
                  <tbody>
                    {refunds.length === 0 ? (
                      <tr><td colSpan={6} style={{ textAlign: 'center', color: '#999', padding: '24px' }}>No refunds yet</td></tr>
                    ) : refunds.map((r) => (
                      <tr key={r.id}>
                        <td><strong>{r.booking_pnr}</strong></td>
                        <td>₹{r.refund_amount.toLocaleString()}</td>
                        <td><span className={`admin-badge admin-badge-${statusBadge(r.refund_status)}`}>{r.refund_status}</span></td>
                        <td>{r.reason || '-'}</td>
                        <td>{r.created_at ? new Date(r.created_at).toLocaleDateString() : '-'}</td>
                        <td>
                          {(r.refund_status === 'pending' || r.refund_status === 'processing') ? (
                            <>
                              <button className="admin-btn-sm" onClick={() => updateRefund(r.id, 'completed')}>Mark Completed</button>
                              <button className="admin-btn-sm" onClick={() => updateRefund(r.id, 'rejected')} style={{ color: '#ef4444', marginLeft: '4px' }}>Reject</button>
                            </>
                          ) : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Users Tab */}
          {activeTab === 'users' && (
            <div className="admin-tab-content active">
              <div className="admin-tab-header">
                <h1>👥 User Management</h1>
                <button className="admin-btn-secondary" onClick={() => api('/api/admin/users').then((data: AdminUser[]) => setUsers(data))}>Refresh</button>
              </div>
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead><tr><th>Name</th><th>Email</th><th>Phone</th><th>Role</th><th>Guest</th><th>Verified</th><th>Joined</th></tr></thead>
                  <tbody>
                    {users.length === 0 ? (
                      <tr><td colSpan={7} style={{ textAlign: 'center', color: '#999', padding: '24px' }}>No users found</td></tr>
                    ) : users.map((u, i) => (
                      <tr key={i}>
                        <td>{u.name}</td>
                        <td>{u.email}</td>
                        <td>{u.phone || '-'}</td>
                        <td><span className={`admin-badge admin-badge-${u.role === 'admin' ? 'info' : 'default'}`}>{u.role}</span></td>
                        <td>{u.is_guest ? '✅' : '❌'}</td>
                        <td>{u.is_verified ? '✅' : '❌'}</td>
                        <td>{u.created_at ? new Date(u.created_at).toLocaleDateString() : '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Chat History Tab */}
          {activeTab === 'chat' && (
            <div className="admin-tab-content active">
              <div className="admin-tab-header">
                <h1>💬 Chat History</h1>
                <button className="admin-btn-secondary" onClick={() => api('/api/admin/chat-history').then((data: AdminChat[]) => setChatHistory(data))}>Refresh</button>
              </div>
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead><tr><th>Session</th><th>Messages</th><th>Escalated</th><th>Summary</th><th>Created</th></tr></thead>
                  <tbody>
                    {chatHistory.length === 0 ? (
                      <tr><td colSpan={5} style={{ textAlign: 'center', color: '#999', padding: '24px' }}>No conversations yet</td></tr>
                    ) : chatHistory.map((c, i) => (
                      <tr key={i}>
                        <td><code>{c.session_id.substring(0, 12)}...</code></td>
                        <td>{c.message_count}</td>
                        <td>{c.is_escalated ? <span className="admin-badge admin-badge-warning">Escalated</span> : <span className="admin-badge admin-badge-success">Normal</span>}</td>
                        <td>{c.summary || '-'}</td>
                        <td>{c.created_at ? new Date(c.created_at).toLocaleString() : '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* AI Responses Tab */}
          {activeTab === 'ai' && (
            <div className="admin-tab-content active">
              <div className="admin-tab-header">
                <h1>🤖 AI Response Log</h1>
                <button className="admin-btn-secondary" onClick={() => api('/api/admin/ai-responses').then((data: AdminAIResponse[]) => setAIResponses(data))}>Refresh</button>
              </div>
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead><tr><th>Intent</th><th>Response</th><th>Time</th></tr></thead>
                  <tbody>
                    {aiResponses.length === 0 ? (
                      <tr><td colSpan={3} style={{ textAlign: 'center', color: '#999', padding: '24px' }}>No AI responses yet</td></tr>
                    ) : aiResponses.map((r, i) => (
                      <tr key={i}>
                        <td><span className="admin-badge admin-badge-info">{r.intent || 'unknown'}</span></td>
                        <td style={{ maxWidth: '500px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.content}</td>
                        <td>{r.created_at ? new Date(r.created_at).toLocaleString() : '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Airports Tab */}
          {activeTab === 'airports' && (
            <div className="admin-tab-content active">
              <div className="admin-tab-header">
                <h1>🏢 Airport Management</h1>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button className="admin-btn-primary" style={{ padding: '8px 16px', fontSize: '0.85rem' }} onClick={() => openAddAirportModal()}>+ Add Airport</button>
                  <button className="admin-btn-secondary" onClick={() => api('/api/admin/airports').then((data: AdminAirport[]) => setAirports(data))}>Refresh</button>
                </div>
              </div>
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead><tr><th>Code</th><th>Name</th><th>City</th><th>Country</th><th>Timezone</th><th>Terminals</th><th>Actions</th></tr></thead>
                  <tbody>
                    {airports.length === 0 ? (
                      <tr><td colSpan={7} style={{ textAlign: 'center', color: '#999', padding: '24px' }}>No airports</td></tr>
                    ) : airports.map((a) => (
                      <tr key={a.id}>
                        <td><strong>{a.code}</strong></td>
                        <td>{a.name}</td>
                        <td>{a.city}</td>
                        <td>{a.country}</td>
                        <td>{a.timezone}</td>
                        <td>{a.terminals}</td>
                        <td>
                          <button className="admin-btn-sm" style={{ color: '#ef4444' }} onClick={async () => { if (confirm(`Delete airport ${a.code}?`)) { try { await apiDelete(`/api/admin/airports/${a.id}`); showActionMsg('Airport deleted'); api('/api/admin/airports').then((d: AdminAirport[]) => setAirports(d)); } catch (err: any) { showActionMsg(`❌ ${err.message}`); } } }}>Delete</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Promotions Tab */}
          {activeTab === 'promotions' && (
            <div className="admin-tab-content active">
              <div className="admin-tab-header">
                <h1>🎁 Promotions</h1>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button className="admin-btn-primary" style={{ padding: '8px 16px', fontSize: '0.85rem' }} onClick={() => openAddPromotionModal()}>+ Add Promotion</button>
                  <button className="admin-btn-secondary" onClick={() => api('/api/admin/promotions').then((data: AdminPromotion[]) => setPromotions(data))}>Refresh</button>
                </div>
              </div>
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead><tr><th>Code</th><th>Title</th><th>Discount</th><th>Valid</th><th>Uses</th><th>Active</th><th>Actions</th></tr></thead>
                  <tbody>
                    {promotions.length === 0 ? (
                      <tr><td colSpan={7} style={{ textAlign: 'center', color: '#999', padding: '24px' }}>No promotions yet</td></tr>
                    ) : promotions.map((p) => (
                      <tr key={p.id}>
                        <td><strong>{p.promo_code}</strong></td>
                        <td>{p.title}</td>
                        <td>{p.discount_type === 'percentage' ? `${p.discount_value}%` : `₹${p.discount_value}`}</td>
                        <td>{p.valid_from ? new Date(p.valid_from).toLocaleDateString() : '-'} → {p.valid_until ? new Date(p.valid_until).toLocaleDateString() : '∞'}</td>
                        <td>{p.used_count}/{p.max_uses}</td>
                        <td>{p.is_active ? <span className="admin-badge admin-badge-success">Active</span> : <span className="admin-badge admin-badge-danger">Inactive</span>}</td>
                        <td>
                          <button className="admin-btn-sm" onClick={async () => { await apiPut(`/api/admin/promotions/${p.id}/toggle`); api('/api/admin/promotions').then((data: AdminPromotion[]) => setPromotions(data)); }}>Toggle</button>
                          <button className="admin-btn-sm" style={{ color: '#ef4444', marginLeft: '4px' }} onClick={async () => { if (confirm('Delete this promotion?')) { await apiDelete(`/api/admin/promotions/${p.id}`); api('/api/admin/promotions').then((data: AdminPromotion[]) => setPromotions(data)); } }}>Delete</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Coupons Tab */}
          {activeTab === 'coupons' && (
            <div className="admin-tab-content active">
              <div className="admin-tab-header">
                <h1>🏷️ Coupons</h1>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button className="admin-btn-primary" style={{ padding: '8px 16px', fontSize: '0.85rem' }} onClick={() => openAddCouponModal()}>+ Add Coupon</button>
                  <button className="admin-btn-secondary" onClick={() => api('/api/admin/coupons').then((data: AdminCoupon[]) => setCoupons(data))}>Refresh</button>
                </div>
              </div>
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead><tr><th>Code</th><th>Discount</th><th>Min Amount</th><th>Max Discount</th><th>Valid</th><th>Uses</th><th>Active</th><th>Actions</th></tr></thead>
                  <tbody>
                    {coupons.length === 0 ? (
                      <tr><td colSpan={8} style={{ textAlign: 'center', color: '#999', padding: '24px' }}>No coupons yet</td></tr>
                    ) : coupons.map((c) => (
                      <tr key={c.id}>
                        <td><strong>{c.code}</strong></td>
                        <td>{c.discount_type === 'percentage' ? `${c.discount_value}%` : `₹${c.discount_value}`}</td>
                        <td>₹{c.min_booking_amount.toLocaleString()}</td>
                        <td>{c.max_discount_amount ? `₹${c.max_discount_amount.toLocaleString()}` : '∞'}</td>
                        <td>{c.valid_from ? new Date(c.valid_from).toLocaleDateString() : '-'} → {c.valid_until ? new Date(c.valid_until).toLocaleDateString() : '∞'}</td>
                        <td>{c.used_count}/{c.max_uses}</td>
                        <td>{c.is_active ? <span className="admin-badge admin-badge-success">Active</span> : <span className="admin-badge admin-badge-danger">Inactive</span>}</td>
                        <td>
                          <button className="admin-btn-sm" onClick={async () => { await apiPut(`/api/admin/coupons/${c.id}/toggle`); api('/api/admin/coupons').then((data: AdminCoupon[]) => setCoupons(data)); }}>Toggle</button>
                          <button className="admin-btn-sm" style={{ color: '#ef4444', marginLeft: '4px' }} onClick={async () => { if (confirm('Delete this coupon?')) { await apiDelete(`/api/admin/coupons/${c.id}`); api('/api/admin/coupons').then((data: AdminCoupon[]) => setCoupons(data)); } }}>Delete</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* CSAT Tab */}
          {activeTab === 'csat' && (
            <div className="admin-tab-content active">
              <div className="admin-tab-header">
                <h1>⭐ Customer Satisfaction</h1>
                <button className="admin-btn-secondary" onClick={() => api('/api/admin/csat').then((data: AdminCSAT) => setCSATData(data))}>Refresh</button>
              </div>
              {csatData ? (
                <>
                  <div className="admin-stats-grid">
                    <div className="admin-stat-card">
                      <div className="stat-icon">⭐</div>
                      <div className="stat-value">{csatData.average_rating}/5</div>
                      <div className="stat-label">Average Rating</div>
                    </div>
                    <div className="admin-stat-card">
                      <div className="stat-icon">📊</div>
                      <div className="stat-value">{csatData.total_ratings}</div>
                      <div className="stat-label">Total Ratings</div>
                    </div>
                  </div>
                  <div className="admin-card" style={{ marginTop: '16px' }}>
                    <h3>Rating Distribution</h3>
                    <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-end', height: '120px', padding: '16px 0' }}>
                      {[5, 4, 3, 2, 1].map((star) => {
                        const count = csatData.distribution[star] || 0;
                        const max = Math.max(...Object.values(csatData.distribution), 1);
                        const h = (count / max) * 100;
                        return (
                          <div key={star} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 1 }}>
                            <div style={{ fontSize: '12px', marginBottom: '4px' }}>{count}</div>
                            <div style={{ width: '40px', height: `${h}%`, background: star >= 4 ? '#22c55e' : star === 3 ? '#eab308' : '#ef4444', borderRadius: '4px 4px 0 0', minHeight: '2px' }} />
                            <div style={{ fontSize: '14px', marginTop: '4px' }}>{'⭐'.repeat(star)}</div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                  <div className="admin-table-wrap" style={{ marginTop: '16px' }}>
                    <table className="admin-table">
                      <thead><tr><th>Rating</th><th>Feedback</th><th>Intent</th><th>Session</th><th>Date</th></tr></thead>
                      <tbody>
                        {(csatData.recent || []).length === 0 ? (
                          <tr><td colSpan={5} style={{ textAlign: 'center', color: '#999', padding: '24px' }}>No ratings yet</td></tr>
                        ) : csatData.recent.map((r) => (
                          <tr key={r.id}>
                            <td>{'⭐'.repeat(r.rating)}</td>
                            <td>{r.feedback || '-'}</td>
                            <td><span className="admin-badge admin-badge-info">{r.intent || '-'}</span></td>
                            <td><code>{r.session_id.substring(0, 12)}...</code></td>
                            <td>{r.created_at ? new Date(r.created_at).toLocaleString() : '-'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : (
                <p style={{ color: 'rgba(255,255,255,0.5)' }}>Loading...</p>
              )}
            </div>
          )}

          {/* Reports Tab */}
          {activeTab === 'reports' && (
            <div className="admin-tab-content active">
              <div className="admin-tab-header">
                <h1>📈 Reports & Analytics</h1>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button className={`admin-btn-sm ${reportSubTab === 'booking' ? 'admin-btn-primary' : ''}`} onClick={() => setReportSubTab('booking')}>Booking Summary</button>
                  <button className={`admin-btn-sm ${reportSubTab === 'cancellation' ? 'admin-btn-primary' : ''}`} onClick={() => setReportSubTab('cancellation')}>Cancellations</button>
                  <button className={`admin-btn-sm ${reportSubTab === 'revenue' ? 'admin-btn-primary' : ''}`} onClick={() => setReportSubTab('revenue')}>Revenue</button>
                </div>
              </div>
              {reportData ? (
                <div className="admin-card">
                  {reportSubTab === 'booking' && reportData.by_status && (
                    <>
                      <h3>Booking Summary</h3>
                      <p style={{ fontSize: '24px', fontWeight: 700, margin: '12px 0' }}>Total: {reportData.total_bookings || 0}</p>
                      <h4>By Status</h4>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', margin: '12px 0' }}>
                        {Object.entries(reportData.by_status).map(([k, v]) => (
                          <span key={k} className={`admin-badge admin-badge-${statusBadge(k)}`}>{k}: {v}</span>
                        ))}
                      </div>
                      <h4>By Cabin Class</h4>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', margin: '12px 0' }}>
                        {Object.entries(reportData.by_cabin_class || {}).map(([k, v]) => (
                          <span key={k} className="admin-badge admin-badge-info">{k}: {v}</span>
                        ))}
                      </div>
                      <h4>Revenue by Cabin</h4>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', margin: '12px 0' }}>
                        {Object.entries(reportData.revenue_by_cabin || {}).map(([k, v]) => (
                          <span key={k} className="admin-badge admin-badge-success">{k}: ₹{(v as number).toLocaleString()}</span>
                        ))}
                      </div>
                    </>
                  )}
                  {reportSubTab === 'cancellation' && (
                    <>
                      <h3>Cancellation Report</h3>
                      <div className="admin-stats-grid" style={{ marginTop: '12px' }}>
                        <div className="admin-stat-card"><div className="stat-icon">❌</div><div className="stat-value">{reportData.total_cancelled || 0}</div><div className="stat-label">Cancelled</div></div>
                        <div className="admin-stat-card"><div className="stat-icon">↩️</div><div className="stat-value">₹{(reportData.total_refunded || 0).toLocaleString()}</div><div className="stat-label">Refunded</div></div>
                        <div className="admin-stat-card"><div className="stat-icon">⏳</div><div className="stat-value">{reportData.pending_refunds || 0}</div><div className="stat-label">Pending Refunds</div></div>
                      </div>
                      <h4 style={{ marginTop: '16px' }}>Cancellation Reasons</h4>
                      <div className="admin-table-wrap" style={{ marginTop: '8px' }}>
                        <table className="admin-table">
                          <thead><tr><th>Reason</th><th>Count</th></tr></thead>
                          <tbody>
                            {(reportData.cancellation_reasons || []).map((r, i) => (
                              <tr key={i}><td>{r.reason}</td><td>{r.count}</td></tr>
                            ))}
                            {(!reportData.cancellation_reasons || reportData.cancellation_reasons.length === 0) && (
                              <tr><td colSpan={2} style={{ textAlign: 'center', color: '#999', padding: '16px' }}>No data</td></tr>
                            )}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )}
                  {reportSubTab === 'revenue' && (
                    <>
                      <h3>Revenue Report</h3>
                      <p style={{ fontSize: '28px', fontWeight: 700, margin: '12px 0' }}>Total: ₹{(reportData.total_revenue || 0).toLocaleString()}</p>
                      <h4>Monthly Revenue (6 months)</h4>
                      <div className="admin-bar-chart" style={{ marginTop: '8px' }}>
                        {(reportData.monthly_revenue || []).map((m, i) => {
                          const maxRev = Math.max(...(reportData.monthly_revenue || []).map((x) => x.revenue), 1);
                          const h = (m.revenue / maxRev) * 100;
                          return (
                            <div key={i} className="admin-bar-item">
                              <div className="admin-bar" style={{ height: `${h}%` }} />
                              <div className="admin-bar-label">{m.month}</div>
                            </div>
                          );
                        })}
                      </div>
                      <div className="admin-table-wrap" style={{ marginTop: '16px' }}>
                        <table className="admin-table">
                          <thead><tr><th>Month</th><th>Revenue</th></tr></thead>
                          <tbody>
                            {(reportData.monthly_revenue || []).map((m, i) => (
                              <tr key={i}><td>{m.month}</td><td>₹{m.revenue.toLocaleString()}</td></tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )}
                </div>
              ) : (
                <p style={{ color: 'rgba(255,255,255,0.5)' }}>Loading...</p>
              )}
            </div>
          )}

          {/* System Monitor Tab */}
          {activeTab === 'monitoring' && (
            <div className="admin-tab-content active">
              <div className="admin-tab-header">
                <h1>🖥️ System Monitor</h1>
                <button className="admin-btn-secondary" onClick={() => {
                  api('/api/health/detailed').then((data) => { if (data) setHealthData(data as SystemHealth); });
                  api('/api/metrics').then((data) => { if (data) setMetricsData(data as SystemMetrics); });
                }}>Refresh</button>
              </div>

              {/* Health Status */}
              {healthData ? (
                <>
                  <div className="admin-stats-grid">
                    <div className="admin-stat-card">
                      <div className="stat-icon">{healthData.status === 'healthy' ? '✅' : '⚠️'}</div>
                      <div className="stat-value" style={{ fontSize: '1.2rem', textTransform: 'capitalize' }}>{healthData.status}</div>
                      <div className="stat-label">System Status</div>
                    </div>
                    <div className="admin-stat-card">
                      <div className="stat-icon">⏱️</div>
                      <div className="stat-value">{Math.floor(healthData.uptime_seconds / 3600)}h {Math.floor((healthData.uptime_seconds % 3600) / 60)}m</div>
                      <div className="stat-label">Uptime</div>
                    </div>
                    <div className="admin-stat-card">
                      <div className="stat-icon">🐍</div>
                      <div className="stat-value" style={{ fontSize: '1.1rem' }}>Python {healthData.system.python_version}</div>
                      <div className="stat-label">Runtime</div>
                    </div>
                    <div className="admin-stat-card">
                      <div className="stat-icon">📦</div>
                      <div className="stat-value" style={{ fontSize: '1.1rem' }}>{healthData.version}</div>
                      <div className="stat-label">App Version</div>
                    </div>
                  </div>

                  <div className="admin-charts-row">
                    {/* CPU & Memory */}
                    <div className="admin-card">
                      <h3>💻 System Resources</h3>
                      <div style={{ marginTop: '16px' }}>
                        <div style={{ marginBottom: '16px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                            <span style={{ color: 'rgba(255,255,255,0.7)', fontSize: '0.9rem' }}>CPU Usage</span>
                            <span style={{ color: healthData.system.cpu_percent > 80 ? '#fca5a5' : '#86efac', fontWeight: 600 }}>{healthData.system.cpu_percent.toFixed(1)}%</span>
                          </div>
                          <div style={{ background: 'rgba(255,255,255,0.1)', borderRadius: '8px', height: '10px', overflow: 'hidden' }}>
                            <div style={{ width: `${healthData.system.cpu_percent}%`, height: '100%', background: healthData.system.cpu_percent > 80 ? '#ef4444' : healthData.system.cpu_percent > 60 ? '#f59e0b' : '#22c55e', borderRadius: '8px', transition: 'width 0.3s' }} />
                          </div>
                        </div>
                        <div style={{ marginBottom: '16px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                            <span style={{ color: 'rgba(255,255,255,0.7)', fontSize: '0.9rem' }}>Memory Usage</span>
                            <span style={{ color: healthData.system.memory_percent > 80 ? '#fca5a5' : '#86efac', fontWeight: 600 }}>{healthData.system.memory_percent.toFixed(1)}%</span>
                          </div>
                          <div style={{ background: 'rgba(255,255,255,0.1)', borderRadius: '8px', height: '10px', overflow: 'hidden' }}>
                            <div style={{ width: `${healthData.system.memory_percent}%`, height: '100%', background: healthData.system.memory_percent > 80 ? '#ef4444' : healthData.system.memory_percent > 60 ? '#f59e0b' : '#22c55e', borderRadius: '8px', transition: 'width 0.3s' }} />
                          </div>
                          <div style={{ color: 'rgba(255,255,255,0.5)', fontSize: '0.8rem', marginTop: '4px' }}>
                            {healthData.system.memory_used_mb.toFixed(0)} MB / {healthData.system.memory_total_mb.toFixed(0)} MB
                          </div>
                        </div>
                        <div style={{ color: 'rgba(255,255,255,0.5)', fontSize: '0.8rem' }}>
                          Platform: {healthData.system.platform}
                        </div>
                      </div>
                    </div>

                    {/* Dependencies */}
                    <div className="admin-card">
                      <h3>🔌 Service Dependencies</h3>
                      <div style={{ marginTop: '16px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 0', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                          <span style={{ color: 'rgba(255,255,255,0.8)' }}>Database</span>
                          <span className={`admin-badge admin-badge-${healthData.dependencies.database === 'connected' ? 'success' : 'danger'}`}>
                            {healthData.dependencies.database}
                          </span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 0', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                          <span style={{ color: 'rgba(255,255,255,0.8)' }}>LLM Provider</span>
                          <span className="admin-badge admin-badge-info">{healthData.dependencies.llm_provider}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                <p style={{ color: 'rgba(255,255,255,0.5)' }}>Loading health data...</p>
              )}

              {/* Application Metrics */}
              {metricsData ? (
                <div className="admin-card" style={{ marginTop: '16px' }}>
                  <h3>📊 Application Metrics</h3>
                  <div className="admin-stats-grid" style={{ marginTop: '16px' }}>
                    <div className="admin-stat-card"><div className="stat-icon">🎫</div><div className="stat-value">{metricsData.bookings.total}</div><div className="stat-label">Total Bookings</div></div>
                    <div className="admin-stat-card"><div className="stat-icon">✅</div><div className="stat-value">{metricsData.bookings.confirmed}</div><div className="stat-label">Confirmed</div></div>
                    <div className="admin-stat-card"><div className="stat-icon">⏳</div><div className="stat-value">{metricsData.bookings.pending}</div><div className="stat-label">Pending</div></div>
                    <div className="admin-stat-card"><div className="stat-icon">❌</div><div className="stat-value">{metricsData.bookings.cancelled}</div><div className="stat-label">Cancelled</div></div>
                    <div className="admin-stat-card"><div className="stat-icon">🛫</div><div className="stat-value">{metricsData.flights.active}</div><div className="stat-label">Active Flights</div></div>
                    <div className="admin-stat-card"><div className="stat-icon">👥</div><div className="stat-value">{metricsData.users.total}</div><div className="stat-label">Users</div></div>
                    <div className="admin-stat-card"><div className="stat-icon">💬</div><div className="stat-value">{metricsData.conversations.total}</div><div className="stat-label">Conversations</div></div>
                    <div className="admin-stat-card"><div className="stat-icon">💰</div><div className="stat-value">₹{metricsData.revenue.total.toLocaleString()}</div><div className="stat-label">Revenue</div></div>
                    <div className="admin-stat-card"><div className="stat-icon">⭐</div><div className="stat-value">{metricsData.csat.average.toFixed(2)}</div><div className="stat-label">CSAT Avg ({metricsData.csat.count} ratings)</div></div>
                  </div>
                </div>
              ) : (
                healthData && <p style={{ color: 'rgba(255,255,255,0.5)', marginTop: '16px' }}>Loading metrics...</p>
              )}

              {/* API Availability & Failures */}
              {apiStats ? (
                <div className="admin-card" style={{ marginTop: '16px' }}>
                  <h3>🔌 API Availability & Failures</h3>
                  <div className="admin-stats-grid" style={{ marginTop: '16px' }}>
                    <div className="admin-stat-card">
                      <div className="stat-icon">{apiStats.api.availability >= 99 ? '✅' : apiStats.api.availability >= 90 ? '⚠️' : '❌'}</div>
                      <div className="stat-value">{apiStats.api.availability.toFixed(2)}%</div>
                      <div className="stat-label">API Availability</div>
                    </div>
                    <div className="admin-stat-card"><div className="stat-icon">📡</div><div className="stat-value">{apiStats.api.total_requests}</div><div className="stat-label">Total Requests</div></div>
                    <div className="admin-stat-card"><div className="stat-icon">✅</div><div className="stat-value">{apiStats.api.total_success}</div><div className="stat-label">Successful</div></div>
                    <div className="admin-stat-card"><div className="stat-icon">❌</div><div className="stat-value" style={{ color: apiStats.api.total_failure > 0 ? '#fca5a5' : undefined }}>{apiStats.api.total_failure}</div><div className="stat-label">Failed</div></div>
                    <div className="admin-stat-card"><div className="stat-icon">🤖</div><div className="stat-value">{apiStats.llm.total}</div><div className="stat-label">LLM Calls ({apiStats.llm.success} ok, {apiStats.llm.failure} fail, {apiStats.llm.timeouts} timeout)</div></div>
                    <div className="admin-stat-card"><div className="stat-icon">🔍</div><div className="stat-value">{apiStats.rag_retrieval.total}</div><div className="stat-label">RAG Retrievals ({apiStats.rag_retrieval.success} ok, {apiStats.rag_retrieval.failure} fail)</div></div>
                  </div>

                  {/* Per-endpoint breakdown */}
                  {Object.keys(apiStats.api.per_endpoint).length > 0 && (
                    <div className="admin-table-wrap" style={{ marginTop: '16px' }}>
                      <h4 style={{ marginBottom: '8px' }}>Per-Endpoint Breakdown</h4>
                      <table className="admin-table">
                        <thead><tr><th>Endpoint</th><th>Total</th><th>Success</th><th>Failed</th><th>Availability</th></tr></thead>
                        <tbody>
                          {Object.entries(apiStats.api.per_endpoint)
                            .sort(([, a], [, b]) => b.total - a.total)
                            .slice(0, 15)
                            .map(([path, s]) => (
                              <tr key={path}>
                                <td style={{ fontSize: '0.85rem' }}>{path}</td>
                                <td>{s.total}</td>
                                <td>{s.success}</td>
                                <td style={{ color: s.failure > 0 ? '#fca5a5' : undefined }}>{s.failure}</td>
                                <td>{s.total > 0 ? (s.success / s.total * 100).toFixed(1) : 100}%</td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {/* Recent errors */}
                  {Object.entries(apiStats.api.per_endpoint).some(([, s]) => s.errors && s.errors.length > 0) && (
                    <div style={{ marginTop: '16px' }}>
                      <h4 style={{ marginBottom: '8px' }}>Recent Errors</h4>
                      <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
                        {Object.entries(apiStats.api.per_endpoint)
                          .filter(([, s]) => s.errors && s.errors.length > 0)
                          .flatMap(([path, s]) => (s.errors || []).map((e, i) => (
                            <div key={`${path}-${i}`} style={{ fontSize: '0.8rem', padding: '4px 0', color: '#fca5a5' }}>
                              <span style={{ color: '#fca5a5' }}>❌ {e.status}</span> — {path} — {e.time}
                            </div>
                          )))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                healthData && <p style={{ color: 'rgba(255,255,255,0.5)', marginTop: '16px' }}>Loading API stats...</p>
              )}

              {/* AI Evaluation Metrics */}
              <div className="admin-card" style={{ marginTop: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <h3>🧠 AI Evaluation Metrics</h3>
                  <button
                    className="admin-btn-primary"
                    style={{ padding: '8px 16px', fontSize: '0.85rem' }}
                    disabled={aiLoading}
                    onClick={() => {
                      setAILoading(true);
                      api('/api/admin/ai-metrics').then((data) => {
                        setAIMetrics(data as AIMetrics);
                        setAILoading(false);
                      }).catch(() => setAILoading(false));
                    }}
                  >
                    {aiLoading ? 'Running Evaluation...' : aiMetrics ? 'Re-run Evaluation' : 'Run Evaluation'}
                  </button>
                </div>

                {aiLoading && <p style={{ color: 'rgba(255,255,255,0.5)', marginTop: '12px' }}>Running test suite against {29} intent cases, {11} entity cases, {28} RAG cases, and {10} hallucination probes...</p>}

                {aiMetrics && (
                  <>
                    {/* Summary scores */}
                    <div className="admin-stats-grid" style={{ marginTop: '16px' }}>
                      <div className="admin-stat-card">
                        <div className="stat-icon">🎯</div>
                        <div className="stat-value">{(aiMetrics.intent_recognition.accuracy * 100).toFixed(1)}%</div>
                        <div className="stat-label">Intent Accuracy ({aiMetrics.intent_recognition.correct}/{aiMetrics.intent_recognition.total})</div>
                      </div>
                      <div className="admin-stat-card">
                        <div className="stat-icon">📊</div>
                        <div className="stat-value">{(aiMetrics.intent_recognition.macro_f1 * 100).toFixed(1)}%</div>
                        <div className="stat-label">Intent Macro F1</div>
                      </div>
                      <div className="admin-stat-card">
                        <div className="stat-icon">🏷️</div>
                        <div className="stat-value">{(aiMetrics.entity_extraction.accuracy * 100).toFixed(1)}%</div>
                        <div className="stat-label">Entity Accuracy ({aiMetrics.entity_extraction.correct}/{aiMetrics.entity_extraction.total})</div>
                      </div>
                      <div className="admin-stat-card">
                        <div className="stat-icon">📐</div>
                        <div className="stat-value">{(aiMetrics.entity_extraction.macro_f1 * 100).toFixed(1)}%</div>
                        <div className="stat-label">Entity Macro F1</div>
                      </div>
                      <div className="admin-stat-card">
                        <div className="stat-icon">🔍</div>
                        <div className="stat-value">{(aiMetrics.rag_retrieval.accuracy * 100).toFixed(1)}%</div>
                        <div className="stat-label">RAG Retrieval Accuracy ({aiMetrics.rag_retrieval.correct}/{aiMetrics.rag_retrieval.total})</div>
                      </div>
                      <div className="admin-stat-card">
                        <div className="stat-icon">🛣️</div>
                        <div className="stat-value">{(aiMetrics.route_extraction.accuracy * 100).toFixed(1)}%</div>
                        <div className="stat-label">Route Extraction ({aiMetrics.route_extraction.correct}/{aiMetrics.route_extraction.total})</div>
                      </div>
                      <div className="admin-stat-card">
                        <div className="stat-icon">{aiMetrics.hallucination.hallucinations_detected === 0 ? '🛡️' : '⚠️'}</div>
                        <div className="stat-value" style={{ color: aiMetrics.hallucination.hallucinations_detected > 0 ? '#fca5a5' : '#86efac' }}>{aiMetrics.hallucination.hallucinations_detected}</div>
                        <div className="stat-label">Hallucinations ({aiMetrics.hallucination.total_tested} tested)</div>
                      </div>
                      <div className="admin-stat-card">
                        <div className="stat-icon">📈</div>
                        <div className="stat-value">{(aiMetrics.rag_retrieval.avg_confidence * 100).toFixed(1)}%</div>
                        <div className="stat-label">Avg RAG Confidence</div>
                      </div>
                    </div>

                    {/* Precision / Recall / F1 breakdown */}
                    <div className="admin-charts-row" style={{ marginTop: '16px' }}>
                      <div className="admin-card">
                        <h4>Intent Recognition — Per Class</h4>
                        <div className="admin-table-wrap" style={{ marginTop: '8px' }}>
                          <table className="admin-table">
                            <thead><tr><th>Intent</th><th>Precision</th><th>Recall</th><th>F1</th><th>TP</th><th>FP</th><th>FN</th></tr></thead>
                            <tbody>
                              {Object.entries(aiMetrics.intent_recognition.per_class).map(([cls, m]: [string, any]) => (
                                <tr key={cls}>
                                  <td>{cls}</td>
                                  <td>{(m.precision * 100).toFixed(1)}%</td>
                                  <td>{(m.recall * 100).toFixed(1)}%</td>
                                  <td>{(m.f1 * 100).toFixed(1)}%</td>
                                  <td>{m.tp}</td><td>{m.fp}</td><td>{m.fn}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                      <div className="admin-card">
                        <h4>Entity Extraction — Per Field</h4>
                        <div className="admin-table-wrap" style={{ marginTop: '8px' }}>
                          <table className="admin-table">
                            <thead><tr><th>Field</th><th>Precision</th><th>Recall</th><th>F1</th><th>TP</th><th>FP</th><th>FN</th></tr></thead>
                            <tbody>
                              {Object.entries(aiMetrics.entity_extraction.per_field).map(([field, m]: [string, any]) => (
                                <tr key={field}>
                                  <td>{field}</td>
                                  <td>{(m.precision * 100).toFixed(1)}%</td>
                                  <td>{(m.recall * 100).toFixed(1)}%</td>
                                  <td>{(m.f1 * 100).toFixed(1)}%</td>
                                  <td>{m.tp}</td><td>{m.fp}</td><td>{m.fn}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </div>

                    {/* Hallucination Details */}
                    <div style={{ marginTop: '16px' }}>
                      <h4>🛡️ Hallucination Detection</h4>
                      {aiMetrics.hallucination.hallucinations_detected === 0 ? (
                        <p style={{ color: '#86efac', marginTop: '8px' }}>✅ No hallucinations detected — RAG correctly rejected all {aiMetrics.hallucination.total_tested} unknown city queries.</p>
                      ) : (
                        <div className="admin-table-wrap" style={{ marginTop: '8px' }}>
                          <table className="admin-table">
                            <thead><tr><th>Query</th><th>Falsely Matched To</th><th>Confidence</th></tr></thead>
                            <tbody>
                              {aiMetrics.hallucination.details.map((d, i) => (
                                <tr key={i}><td>{d.query}</td><td style={{ color: '#fca5a5' }}>{d.matched}</td><td>{(d.confidence * 100).toFixed(1)}%</td></tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>

                    {/* RAG Retrieval Methods */}
                    <div style={{ marginTop: '16px' }}>
                      <h4>🔍 RAG Retrieval Methods</h4>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '8px' }}>
                        {Object.entries(aiMetrics.rag_retrieval.method_counts || {}).map(([method, count]) => (
                          <span key={method} className="admin-badge admin-badge-info">{method}: {count}</span>
                        ))}
                      </div>
                    </div>

                    {/* Failed Test Cases */}
                    {aiMetrics.intent_recognition.results.some((r) => !r.pass) && (
                      <div style={{ marginTop: '16px' }}>
                        <h4 style={{ color: '#fca5a5' }}>❌ Failed Intent Tests</h4>
                        <div className="admin-table-wrap" style={{ marginTop: '8px' }}>
                          <table className="admin-table">
                            <thead><tr><th>Message</th><th>Expected</th><th>Predicted</th></tr></thead>
                            <tbody>
                              {aiMetrics.intent_recognition.results.filter((r) => !r.pass).map((r, i) => (
                                <tr key={i}><td>{r.message}</td><td>{r.expected}</td><td style={{ color: '#fca5a5' }}>{r.predicted}</td></tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                    {aiMetrics.entity_extraction.results.some((r) => !r.pass) && (
                      <div style={{ marginTop: '16px' }}>
                        <h4 style={{ color: '#fca5a5' }}>❌ Failed Entity Tests</h4>
                        <div className="admin-table-wrap" style={{ marginTop: '8px' }}>
                          <table className="admin-table">
                            <thead><tr><th>Message</th><th>Expected</th><th>Predicted</th></tr></thead>
                            <tbody>
                              {aiMetrics.entity_extraction.results.filter((r) => !r.pass).map((r, i) => (
                                <tr key={i}><td>{r.message}</td><td>{JSON.stringify(r.expected)}</td><td style={{ color: '#fca5a5' }}>{JSON.stringify(r.predicted)}</td></tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          )}

          {/* Action Message */}
          {actionMsg && (
            <div className="admin-action-msg" style={{
              position: 'sticky', bottom: '16px', background: 'rgba(99,102,241,0.2)', border: '1px solid rgba(99,102,241,0.4)',
              borderRadius: '8px', padding: '12px 16px', marginTop: '16px', color: '#a5b4fc', fontSize: '0.9rem', zIndex: 10,
            }}>
              {actionMsg}
            </div>
          )}
        </main>
      </div>

      {/* Modal */}
      {showModal && (
        <div className="admin-modal-overlay" style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
        }} onClick={closeModal}>
          <div className="admin-modal" style={{
            background: 'rgba(30,27,60,0.95)', border: '1px solid rgba(255,255,255,0.15)',
            borderRadius: '16px', padding: '32px', maxWidth: '600px', width: '90%',
            maxHeight: '85vh', overflowY: 'auto', boxShadow: '0 16px 48px rgba(0,0,0,0.4)',
          }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
              <h2 style={{ fontSize: '1.3rem', color: '#fff' }}>{modalTitle}</h2>
              <button className="admin-btn-sm" onClick={closeModal}>✕</button>
            </div>
            {modalContent}
          </div>
        </div>
      )}
    </div>
  );
}


// ── Form Components ──────────────────────────────────────────────────────────

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '10px 14px', border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: '8px', fontSize: '0.9rem', background: 'rgba(255,255,255,0.05)',
  color: '#fff', outline: 'none',
};
const labelStyle: React.CSSProperties = {
  display: 'block', fontSize: '0.8rem', color: 'rgba(255,255,255,0.6)',
  marginBottom: '4px', marginTop: '12px',
};
const formRowStyle: React.CSSProperties = { display: 'flex', gap: '12px' };

function FlightForm({ airports, onSubmit, onCancel }: {
  airports: AdminAirport[];
  onSubmit: (data: any) => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState({
    flight_number: '', airline_name: 'SkyBook Airlines', airline_code: 'SB',
    departure_airport_code: '', arrival_airport_code: '',
    departure_time: '', arrival_time: '', duration_minutes: 120,
    aircraft: 'Boeing 737', total_seats: 180,
    price_economy: 3500, price_premium_economy: 5000, price_business: 8000, price_first: 12000,
    cabin_baggage_kg: 7, checked_baggage_kg: 15, seat_rows: 30, seat_cols: 6,
  });

  const set = (k: string, v: any) => setForm({ ...form, [k]: v });

  return (
    <form onSubmit={(e) => { e.preventDefault(); onSubmit(form); }}>
      <div style={formRowStyle}>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Flight Number *</label>
          <input style={inputStyle} value={form.flight_number} onChange={(e) => set('flight_number', e.target.value)} required placeholder="SB999" />
        </div>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Airline Name</label>
          <input style={inputStyle} value={form.airline_name} onChange={(e) => set('airline_name', e.target.value)} />
        </div>
      </div>
      <div style={formRowStyle}>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Departure Airport *</label>
          <select style={inputStyle} value={form.departure_airport_code} onChange={(e) => set('departure_airport_code', e.target.value)} required>
            <option value="">Select...</option>
            {airports.map((a) => <option key={a.id} value={a.code}>{a.code} — {a.city}</option>)}
          </select>
        </div>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Arrival Airport *</label>
          <select style={inputStyle} value={form.arrival_airport_code} onChange={(e) => set('arrival_airport_code', e.target.value)} required>
            <option value="">Select...</option>
            {airports.map((a) => <option key={a.id} value={a.code}>{a.code} — {a.city}</option>)}
          </select>
        </div>
      </div>
      <div style={formRowStyle}>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Departure Time *</label>
          <input style={inputStyle} type="datetime-local" value={form.departure_time} onChange={(e) => set('departure_time', e.target.value)} required />
        </div>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Arrival Time *</label>
          <input style={inputStyle} type="datetime-local" value={form.arrival_time} onChange={(e) => set('arrival_time', e.target.value)} required />
        </div>
      </div>
      <div style={formRowStyle}>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Duration (min)</label>
          <input style={inputStyle} type="number" value={form.duration_minutes} onChange={(e) => set('duration_minutes', +e.target.value)} />
        </div>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Aircraft</label>
          <input style={inputStyle} value={form.aircraft} onChange={(e) => set('aircraft', e.target.value)} />
        </div>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Total Seats</label>
          <input style={inputStyle} type="number" value={form.total_seats} onChange={(e) => set('total_seats', +e.target.value)} />
        </div>
      </div>
      <div style={formRowStyle}>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Price Economy (₹)</label>
          <input style={inputStyle} type="number" value={form.price_economy} onChange={(e) => set('price_economy', +e.target.value)} />
        </div>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Price Premium Econ (₹)</label>
          <input style={inputStyle} type="number" value={form.price_premium_economy} onChange={(e) => set('price_premium_economy', +e.target.value)} />
        </div>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Price Business (₹)</label>
          <input style={inputStyle} type="number" value={form.price_business} onChange={(e) => set('price_business', +e.target.value)} />
        </div>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Price First (₹)</label>
          <input style={inputStyle} type="number" value={form.price_first} onChange={(e) => set('price_first', +e.target.value)} />
        </div>
      </div>
      <div style={formRowStyle}>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Seat Rows</label>
          <input style={inputStyle} type="number" value={form.seat_rows} onChange={(e) => set('seat_rows', +e.target.value)} />
        </div>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Seat Cols</label>
          <input style={inputStyle} type="number" value={form.seat_cols} onChange={(e) => set('seat_cols', +e.target.value)} />
        </div>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Cabin Baggage (kg)</label>
          <input style={inputStyle} type="number" value={form.cabin_baggage_kg} onChange={(e) => set('cabin_baggage_kg', +e.target.value)} />
        </div>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Checked Baggage (kg)</label>
          <input style={inputStyle} type="number" value={form.checked_baggage_kg} onChange={(e) => set('checked_baggage_kg', +e.target.value)} />
        </div>
      </div>
      <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
        <button type="submit" className="admin-btn-primary" style={{ padding: '10px 24px' }}>Create Flight</button>
        <button type="button" className="admin-btn-secondary" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}

function PassengerEditForm({ passenger, onSubmit, onCancel }: {
  passenger: AdminPassenger;
  onSubmit: (data: any) => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState({
    full_name: passenger.full_name,
    age: passenger.age || '',
    gender: passenger.gender || '',
    seat_number: passenger.seat_number || '',
    meal_preference: passenger.meal_preference || 'none',
  });

  const set = (k: string, v: any) => setForm({ ...form, [k]: v });

  return (
    <form onSubmit={(e) => { e.preventDefault(); onSubmit(form); }}>
      <label style={labelStyle}>Full Name</label>
      <input style={inputStyle} value={form.full_name} onChange={(e) => set('full_name', e.target.value)} />
      <div style={formRowStyle}>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Age</label>
          <input style={inputStyle} type="number" value={form.age} onChange={(e) => set('age', +e.target.value)} />
        </div>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Gender</label>
          <select style={inputStyle} value={form.gender} onChange={(e) => set('gender', e.target.value)}>
            <option value="">Select...</option>
            <option value="male">Male</option>
            <option value="female">Female</option>
            <option value="other">Other</option>
          </select>
        </div>
      </div>
      <div style={formRowStyle}>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Seat Number</label>
          <input style={inputStyle} value={form.seat_number} onChange={(e) => set('seat_number', e.target.value)} placeholder="e.g. 12A" />
        </div>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Meal Preference</label>
          <select style={inputStyle} value={form.meal_preference} onChange={(e) => set('meal_preference', e.target.value)}>
            <option value="none">No Meal</option>
            <option value="veg">Veg</option>
            <option value="non_veg">Non-Veg</option>
            <option value="jain">Jain</option>
          </select>
        </div>
      </div>
      <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
        <button type="submit" className="admin-btn-primary" style={{ padding: '10px 24px' }}>Save Changes</button>
        <button type="button" className="admin-btn-secondary" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}

function AirportForm({ onSubmit, onCancel }: {
  onSubmit: (data: any) => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState({
    code: '', name: '', city: '', country: 'India', timezone: 'Asia/Kolkata', terminals: 2,
  });

  const set = (k: string, v: any) => setForm({ ...form, [k]: v });

  return (
    <form onSubmit={(e) => { e.preventDefault(); onSubmit(form); }}>
      <div style={formRowStyle}>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Airport Code * (3 letters)</label>
          <input style={inputStyle} value={form.code} onChange={(e) => set('code', e.target.value.toUpperCase())} maxLength={3} required placeholder="BLR" />
        </div>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Terminals</label>
          <input style={inputStyle} type="number" value={form.terminals} onChange={(e) => set('terminals', +e.target.value)} />
        </div>
      </div>
      <label style={labelStyle}>Airport Name *</label>
      <input style={inputStyle} value={form.name} onChange={(e) => set('name', e.target.value)} required placeholder="Kempegowda International Airport" />
      <div style={formRowStyle}>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>City *</label>
          <input style={inputStyle} value={form.city} onChange={(e) => set('city', e.target.value)} required placeholder="Bangalore" />
        </div>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Country</label>
          <input style={inputStyle} value={form.country} onChange={(e) => set('country', e.target.value)} />
        </div>
      </div>
      <label style={labelStyle}>Timezone</label>
      <input style={inputStyle} value={form.timezone} onChange={(e) => set('timezone', e.target.value)} placeholder="Asia/Kolkata" />
      <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
        <button type="submit" className="admin-btn-primary" style={{ padding: '10px 24px' }}>Create Airport</button>
        <button type="button" className="admin-btn-secondary" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}

function PromotionForm({ onSubmit, onCancel }: {
  onSubmit: (data: any) => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState({
    title: '', description: '', discount_type: 'percentage', discount_value: 10,
    promo_code: '', valid_from: '', valid_until: '', max_uses: 100,
  });

  const set = (k: string, v: any) => setForm({ ...form, [k]: v });

  return (
    <form onSubmit={(e) => { e.preventDefault(); onSubmit(form); }}>
      <label style={labelStyle}>Title *</label>
      <input style={inputStyle} value={form.title} onChange={(e) => set('title', e.target.value)} required placeholder="Summer Sale" />
      <label style={labelStyle}>Description</label>
      <input style={inputStyle} value={form.description} onChange={(e) => set('description', e.target.value)} placeholder="10% off summer flights" />
      <div style={formRowStyle}>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Promo Code *</label>
          <input style={inputStyle} value={form.promo_code} onChange={(e) => set('promo_code', e.target.value.toUpperCase())} required placeholder="SUMMER10" />
        </div>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Discount Type</label>
          <select style={inputStyle} value={form.discount_type} onChange={(e) => set('discount_type', e.target.value)}>
            <option value="percentage">Percentage</option>
            <option value="fixed">Fixed Amount</option>
          </select>
        </div>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Discount Value</label>
          <input style={inputStyle} type="number" value={form.discount_value} onChange={(e) => set('discount_value', +e.target.value)} />
        </div>
      </div>
      <div style={formRowStyle}>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Valid From</label>
          <input style={inputStyle} type="date" value={form.valid_from} onChange={(e) => set('valid_from', e.target.value)} />
        </div>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Valid Until</label>
          <input style={inputStyle} type="date" value={form.valid_until} onChange={(e) => set('valid_until', e.target.value)} />
        </div>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Max Uses</label>
          <input style={inputStyle} type="number" value={form.max_uses} onChange={(e) => set('max_uses', +e.target.value)} />
        </div>
      </div>
      <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
        <button type="submit" className="admin-btn-primary" style={{ padding: '10px 24px' }}>Create Promotion</button>
        <button type="button" className="admin-btn-secondary" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}

function CouponForm({ onSubmit, onCancel }: {
  onSubmit: (data: any) => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState({
    code: '', discount_type: 'percentage', discount_value: 10,
    min_booking_amount: 1000, max_discount_amount: 500,
    valid_from: '', valid_until: '', max_uses: 100,
  });

  const set = (k: string, v: any) => setForm({ ...form, [k]: v });

  return (
    <form onSubmit={(e) => { e.preventDefault(); onSubmit(form); }}>
      <div style={formRowStyle}>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Coupon Code *</label>
          <input style={inputStyle} value={form.code} onChange={(e) => set('code', e.target.value.toUpperCase())} required placeholder="FLY500" />
        </div>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Discount Type</label>
          <select style={inputStyle} value={form.discount_type} onChange={(e) => set('discount_type', e.target.value)}>
            <option value="percentage">Percentage</option>
            <option value="fixed">Fixed Amount</option>
          </select>
        </div>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Discount Value</label>
          <input style={inputStyle} type="number" value={form.discount_value} onChange={(e) => set('discount_value', +e.target.value)} />
        </div>
      </div>
      <div style={formRowStyle}>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Min Booking Amount (₹)</label>
          <input style={inputStyle} type="number" value={form.min_booking_amount} onChange={(e) => set('min_booking_amount', +e.target.value)} />
        </div>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Max Discount (₹)</label>
          <input style={inputStyle} type="number" value={form.max_discount_amount} onChange={(e) => set('max_discount_amount', +e.target.value)} />
        </div>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Max Uses</label>
          <input style={inputStyle} type="number" value={form.max_uses} onChange={(e) => set('max_uses', +e.target.value)} />
        </div>
      </div>
      <div style={formRowStyle}>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Valid From</label>
          <input style={inputStyle} type="date" value={form.valid_from} onChange={(e) => set('valid_from', e.target.value)} />
        </div>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>Valid Until</label>
          <input style={inputStyle} type="date" value={form.valid_until} onChange={(e) => set('valid_until', e.target.value)} />
        </div>
      </div>
      <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
        <button type="submit" className="admin-btn-primary" style={{ padding: '10px 24px' }}>Create Coupon</button>
        <button type="button" className="admin-btn-secondary" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}
