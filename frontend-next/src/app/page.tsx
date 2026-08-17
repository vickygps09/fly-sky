'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import type { ChatMessage, User, FlightInfo, BoardingPass, BookingResult, ResponseMetadata } from '@/types';
import { newSession, sendMessage } from '@/lib/api';
import WelcomeOverlay from '@/components/WelcomeOverlay';
import Header from '@/components/Header';
import Sidebar from '@/components/Sidebar';
import MessageBubble from '@/components/MessageBubble';
import TypingIndicator from '@/components/TypingIndicator';
import QuickReplies from '@/components/QuickReplies';
import AuthModal from '@/components/AuthModal';
import PaymentModal from '@/components/PaymentModal';
import BookingModal from '@/components/BookingModal';
import BoardingPassModal from '@/components/BoardingPassModal';
import CSATWidget from '@/components/CSATWidget';
import DatePicker from '@/components/DatePicker';

const WELCOME_MESSAGES = [
  { icon: '🔍', title: 'Search Flights', desc: 'Book a flight' },
  { icon: '📊', title: 'Flight Status', desc: 'Check SB101 status' },
  { icon: '✅', title: 'Web Check-in', desc: 'Web check-in' },
  { icon: '🧳', title: 'Baggage Info', desc: 'Baggage information' },
];

export default function HomePage() {
  const [showWelcome, setShowWelcome] = useState(true);
  const [user, setUser] = useState<User | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [sidebarHidden, setSidebarHidden] = useState(false);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [authTab, setAuthTab] = useState<'login' | 'register' | 'guest'>('login');
  const [bookingFlight, setBookingFlight] = useState<FlightInfo | null>(null);
  const [passengerCount, setPassengerCount] = useState(1);
  const [paymentData, setPaymentData] = useState<BookingResult | null>(null);
  const [boardingPass, setBoardingPass] = useState<BoardingPass | null>(null);
  const [currentQuickReplies, setCurrentQuickReplies] = useState<string[]>([]);
  const [showCSAT, setShowCSAT] = useState(false);
  const [csatIntent, setCSATIntent] = useState<string | undefined>(undefined);
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [pickedDate, setPickedDate] = useState('');
  const pendingPaymentRef = useRef<BookingResult | null>(null);

  const sessionIdRef = useRef<string>('');
  const pendingMetaRef = useRef<{ msgId: string; meta: ResponseMetadata | null } | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const processingRef = useRef(false);

  useEffect(() => {
    newSession().then((id) => {
      sessionIdRef.current = id;
    });
  }, []);

  const scrollToBottom = useCallback(() => {
    setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, 50);
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping, scrollToBottom]);

  // Auto-focus input after bot finishes responding
  useEffect(() => {
    if (!isTyping && !showWelcome && !showAuthModal && !bookingFlight && !paymentData && !boardingPass && !showDatePicker) {
      inputRef.current?.focus();
    }
  }, [isTyping, showWelcome, showAuthModal, bookingFlight, paymentData, boardingPass, showDatePicker]);

  const handleSend = useCallback(async (text: string) => {
    if (!text.trim() || processingRef.current) return;
    processingRef.current = true;
    setInputValue('');

    // Handle Pay now / Cancel quick replies for pending payment
    const trimmed = text.trim();
    if (trimmed === 'Pay now' && pendingPaymentRef.current) {
      setPaymentData(pendingPaymentRef.current);
      processingRef.current = false;
      return;
    }
    if (trimmed === 'Cancel' && pendingPaymentRef.current) {
      pendingPaymentRef.current = null;
      setCurrentQuickReplies([]);
      processingRef.current = false;
      return;
    }

    // Internal sync messages (starting with __) should not be shown in chat
    const isInternalSync = trimmed.startsWith('__');

    if (!isInternalSync) {
      const userMsg: ChatMessage = {
        id: `msg_${Date.now()}_user`,
        role: 'user',
        content: trimmed,
      };
      setMessages((prev) => [...prev, userMsg]);
      setIsTyping(true);
      setCurrentQuickReplies([]);
    }

    try {
      const resp = await sendMessage(sessionIdRef.current, trimmed, user?.user_id || null);

      if (!isInternalSync) {
        const botMsgId = `msg_${Date.now()}_bot`;
        const meta = (resp.metadata || null) as ResponseMetadata | null;
        pendingMetaRef.current = { msgId: botMsgId, meta };
        const botMsg: ChatMessage = {
          id: botMsgId,
          role: 'bot',
          content: resp.reply || '',
          metadata: resp.metadata,
          escalated: resp.escalated,
          intent: resp.intent,
          streaming: true,
        };
        setMessages((prev) => [...prev, botMsg]);
        setIsTyping(false);
      }
    } catch {
      if (!isInternalSync) {
        const errorMsg: ChatMessage = {
          id: `msg_${Date.now()}_error`,
          role: 'bot',
          content: '⚠️ Sorry, I encountered an error. Please try again.',
        };
        setMessages((prev) => [...prev, errorMsg]);
        setIsTyping(false);
      }
    } finally {
      processingRef.current = false;
    }
  }, [user]);

  const handleStreamComplete = useCallback((msgId: string) => {
    setMessages((prev) =>
      prev.map((m) => (m.id === msgId ? { ...m, streaming: false } : m))
    );
    // Re-focus input after streaming completes
    setTimeout(() => inputRef.current?.focus(), 0);
    const pending = pendingMetaRef.current;
    if (pending && pending.msgId === msgId) {
      const meta = pending.meta;
      if (meta?.quick_replies && meta.quick_replies.length > 0) {
        setCurrentQuickReplies(meta.quick_replies);
      } else {
        setCurrentQuickReplies([]);
      }
      if (meta?.boarding_pass) {
        setBoardingPass(meta.boarding_pass);
      }
      if (meta?.show_booking_form && meta?.flight_info) {
        setBookingFlight(meta.flight_info);
        setPassengerCount(meta.passenger_count || 1);
      }
      if (meta?.booking_result) {
        pendingPaymentRef.current = meta.booking_result;
      }
      if (meta?.show_date_picker) {
        setShowDatePicker(true);
      }
      const csatIntents = ['check_in', 'cancel_booking', 'refund', 'book_flight'];
      if (meta?.intent && csatIntents.includes(meta.intent)) {
        setCSATIntent(meta.intent);
        setShowCSAT(true);
      }
      pendingMetaRef.current = null;
    }
  }, []);

  const handleFlightSelect = useCallback((_flightId: string, number: number) => {
    // In the original app, selecting a flight sends the flight number as a message
    // The backend then responds with metadata.show_booking_form to trigger the booking modal
    handleSend(String(number));
  }, [handleSend]);

  const handleBookingComplete = useCallback((result: BookingResult) => {
    setBookingFlight(null);
    // Store as pending payment and show confirmation in chat with Pay now / Cancel
    pendingPaymentRef.current = result;

    const depTime = new Date(result.departure_time).toLocaleString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false,
    });

    const reply = (
      `🎫 **Booking Created Successfully!**\n\n` +
      `PNR: **${result.pnr}**\n` +
      `Flight: ${result.flight_number} — ${result.departure_city} → ${result.arrival_city}\n` +
      `Date: ${depTime}\n` +
      `Passenger: ${result.passenger_name}\n` +
      `Passengers: ${result.passengers}\n` +
      `Email: ${result.contact_email}\n` +
      `Phone: ${result.contact_phone}\n` +
      (result.travel_insurance ? `Travel Insurance: ✅ Included\n` : '') +
      (result.extra_baggage_kg > 0 ? `Extra Baggage: +${result.extra_baggage_kg} kg\n` : '') +
      `Total Amount: **₹${result.total_amount.toLocaleString()}**\n\n` +
      `💳 Click **Pay now** below to proceed to the payment gateway.`
    );

    const botMsg: ChatMessage = {
      id: `msg_${Date.now()}_booking`,
      role: 'bot',
      content: reply,
      metadata: { quick_replies: ['Pay now', 'Cancel'], booking_pnr: result.pnr } as ResponseMetadata,
    };
    setMessages((prev) => [...prev, botMsg]);
    setCurrentQuickReplies(['Pay now', 'Cancel']);
  }, []);

  const handlePaymentSuccess = useCallback(() => {
    const p = pendingPaymentRef.current;
    setPaymentData(null);
    pendingPaymentRef.current = null;

    if (p) {
      const successReply = (
        `✅ **Payment Successful! Booking Confirmed**\n\n` +
        `PNR: **${p.pnr}**\n` +
        `Amount Paid: **₹${p.total_amount.toLocaleString()}**\n` +
        `Status: Confirmed ✅\n\n` +
        `📧 A confirmation email has been sent to **${p.contact_email}**.\n` +
        `🎫 You can check-in online 24 hours before departure.\n\n` +
        `Is there anything else I can help you with?`
      );
      const botMsg: ChatMessage = {
        id: `msg_${Date.now()}_paysuccess`,
        role: 'bot',
        content: successReply,
        metadata: { quick_replies: ['Web check-in', 'Check flight status', 'Book another flight'], booking_pnr: p.pnr } as ResponseMetadata,
      };
      setMessages((prev) => [...prev, botMsg]);
      setCurrentQuickReplies(['Web check-in', 'Check flight status', 'Book another flight']);

      // Send internal sync message to update flow_step
      handleSend('__payment_completed__');
    }
  }, [handleSend]);

  const handleNewChat = useCallback(() => {
    setMessages([]);
    setCurrentQuickReplies([]);
    newSession().then((id) => {
      sessionIdRef.current = id;
    });
    inputRef.current?.focus();
  }, []);

  const handleAuth = useCallback((u: User) => {
    setUser(u);
    setShowAuthModal(false);
    setShowWelcome(false);
    // Store user and token in localStorage
    if (typeof window !== 'undefined') {
      localStorage.setItem('skybook_user', JSON.stringify(u));
      if (u.access_token) {
        localStorage.setItem('skybook_token', u.access_token);
      }
    }
    // Start a new session
    newSession().then((id) => {
      sessionIdRef.current = id;
    });
    inputRef.current?.focus();
  }, []);

  const handleLogout = useCallback(() => {
    setUser(null);
    pendingPaymentRef.current = null;
    if (typeof window !== 'undefined') {
      localStorage.removeItem('skybook_user');
      localStorage.removeItem('skybook_token');
    }
    setShowWelcome(true);
    setMessages([]);
    setCurrentQuickReplies([]);
  }, []);

  const handleGuest = useCallback(() => {
    setShowWelcome(false);
    setShowAuthModal(true);
    setAuthTab('guest');
  }, []);

  const handleLoginClick = useCallback(() => {
    setShowAuthModal(true);
    setAuthTab('login');
  }, []);

  const handleAdminClick = useCallback(() => {
    if (typeof window !== 'undefined') {
      window.location.href = '/admin';
    }
  }, []);

  // Load user from localStorage on mount
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('skybook_user');
      if (stored) {
        try {
          const u = JSON.parse(stored) as User;
          setUser(u);
          setShowWelcome(false);
          newSession().then((id) => {
            sessionIdRef.current = id;
          });
        } catch {
          // ignore
        }
      }
    }
  }, []);

  const handleKeyPress = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend(inputValue);
    }
  }, [inputValue, handleSend]);

  const showWelcomeScreen = messages.length === 0 && !isTyping;

  return (
    <>
      {showWelcome && (
        <WelcomeOverlay onLogin={handleLoginClick} onGuest={handleGuest} onAuth={handleAuth} />
      )}

      {/* Background image for chat — matches welcome page */}
      <img className="chat-bg-img" src="/img/home-bg.png" alt="" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
      <div className="chat-bg-overlay" />

      {showAuthModal && (
        <AuthModal
          onClose={() => setShowAuthModal(false)}
          onAuth={handleAuth}
          initialTab={authTab}
        />
      )}

      {bookingFlight && (
        <BookingModal
          flightInfo={bookingFlight}
          passengerCount={passengerCount}
          user={user}
          sessionId={sessionIdRef.current}
          onClose={() => setBookingFlight(null)}
          onBookingComplete={handleBookingComplete}
        />
      )}

      {paymentData && (
        <PaymentModal
          payment={paymentData}
          onClose={() => setPaymentData(null)}
          onSuccess={handlePaymentSuccess}
        />
      )}

      {boardingPass && (
        <BoardingPassModal
          boardingPass={boardingPass}
          onClose={() => setBoardingPass(null)}
        />
      )}

      {!showWelcome && (
      <Header
        user={user}
        onToggleSidebar={() => setSidebarHidden(!sidebarHidden)}
        onLoginClick={handleLoginClick}
        onLogout={handleLogout}
        onAdminClick={handleAdminClick}
      />
      )}

      {!showWelcome && (
      <div className="chat-container">
        <Sidebar
          hidden={sidebarHidden}
          onNewChat={handleNewChat}
          onQuickMessage={handleSend}
        />

        <div className="chat-main">
          <div className="messages">
            {showWelcomeScreen ? (
              <div className="welcome-screen">
                <div className="welcome-icon">✈️</div>
                <h1>Welcome to SkyBook AI</h1>
                <p>Your intelligent airline reservation assistant</p>
                <div className="welcome-features">
                  {WELCOME_MESSAGES.map((feat) => (
                    <div
                      key={feat.title}
                      className="feature-card"
                      onClick={() => handleSend(feat.desc)}
                    >
                      <span className="feature-icon">{feat.icon}</span>
                      <span>{feat.title}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg) => (
                <MessageBubble
                  key={msg.id}
                  message={msg}
                  onFlightSelect={handleFlightSelect}
                  onBoardingPass={setBoardingPass}
                  onStreamComplete={handleStreamComplete}
                />
              ))
            )}
            {showCSAT && !isTyping && messages.length > 0 && (
              <CSATWidget sessionId={sessionIdRef.current} intent={csatIntent} />
            )}
            {isTyping && <TypingIndicator />}
            <div ref={messagesEndRef} />
          </div>

          {currentQuickReplies.length > 0 && !isTyping && (
            <QuickReplies replies={currentQuickReplies} onReply={handleSend} />
          )}

          <div className="input-area">
            <div className="input-inner">
              <div className="input-wrapper" style={{ position: 'relative' }}>
                {showDatePicker && (
                  <div style={{ position: 'absolute', bottom: 'calc(100% + 4px)', left: 0, zIndex: 1000, width: '280px' }}>
                    <DatePicker
                      value={pickedDate}
                      alwaysOpen={true}
                      onClose={() => setShowDatePicker(false)}
                      onChange={(d) => {
                        setPickedDate(d);
                        setShowDatePicker(false);
                        const formatted = new Date(d + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
                        setInputValue((prev) => prev ? `${prev} ${formatted}` : formatted);
                        inputRef.current?.focus();
                      }}
                      placeholder="Pick a travel date"
                    />
                  </div>
                )}
                <button
                  type="button"
                  onClick={() => setShowDatePicker(!showDatePicker)}
                  disabled={isTyping}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: showDatePicker ? 'var(--primary)' : 'var(--text-muted)',
                    cursor: 'pointer',
                    fontSize: '18px',
                    padding: '0 4px',
                    display: 'flex',
                    alignItems: 'center',
                  }}
                  title="Pick a date"
                >
                  📅
                </button>
                <input
                  ref={inputRef}
                  type="text"
                  className="message-input"
                  placeholder="Ask about flights, bookings, check-in..."
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyPress={handleKeyPress}
                  disabled={isTyping}
                />
                <button
                  className="send-btn"
                  onClick={() => handleSend(inputValue)}
                  disabled={!inputValue.trim() || isTyping}
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="22" y1="2" x2="11" y2="13" />
                    <polygon points="22 2 15 22 11 13 2 9 22 2" />
                  </svg>
                </button>
              </div>
              <div className="disclaimer">
                SkyBook AI may produce inaccurate info. Verify flight details before booking.
              </div>
            </div>
          </div>
        </div>
      </div>
      )}
    </>
  );
}
