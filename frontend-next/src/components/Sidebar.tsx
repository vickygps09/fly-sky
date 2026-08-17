'use client';

interface SidebarProps {
  hidden: boolean;
  onNewChat: () => void;
  onQuickMessage: (msg: string) => void;
}

const QUICK_ACTIONS = [
  { icon: '✈️', label: 'Book Flight', msg: 'Book a flight' },
  { icon: '�', label: 'My Bookings', msg: 'Show my bookings' },
  { icon: '�📊', label: 'Flight Status', msg: 'Check flight status' },
  { icon: '🎫', label: 'Cancel Booking', msg: 'Cancel my booking' },
  { icon: '✅', label: 'Web Check-in', msg: 'Web check-in' },
  { icon: '💰', label: 'Refund Status', msg: 'Where is my refund?' },
  { icon: '🧳', label: 'Baggage Info', msg: 'Baggage information' },
  { icon: '👤', label: 'Human Agent', msg: 'Talk to a human agent' },
];

const CAPABILITIES = [
  '✈️ One-way & Round-trip',
  '💺 Seat Selection',
  '📊 Fare Comparison',
  '🧳 Baggage Info',
  '🎫 Booking & Cancellation',
  '✅ Web Check-in',
  '📥 Boarding Pass',
  '💰 Refund Status',
  '🤖 AI Assistant',
  '👤 Human Transfer',
];

export default function Sidebar({ hidden, onNewChat, onQuickMessage }: SidebarProps) {
  return (
    <aside className={`sidebar ${hidden ? 'hidden' : ''}`}>
      <button onClick={onNewChat} className="btn-new-chat">+ New Chat</button>
      <div className="sidebar-section">
        <h3>Quick Actions</h3>
        {QUICK_ACTIONS.map((action) => (
          <button
            key={action.label}
            onClick={() => onQuickMessage(action.msg)}
            className="sidebar-action"
          >
            {action.icon} {action.label}
          </button>
        ))}
      </div>
      <div className="sidebar-section">
        <h3>Capabilities</h3>
        {CAPABILITIES.map((cap) => (
          <div key={cap} className="capability">{cap}</div>
        ))}
      </div>
    </aside>
  );
}
