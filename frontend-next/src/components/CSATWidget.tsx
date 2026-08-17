'use client';

import { useState } from 'react';
import { submitCSAT } from '@/lib/api';

interface CSATWidgetProps {
  sessionId: string;
  intent?: string;
}

export default function CSATWidget({ sessionId, intent }: CSATWidgetProps) {
  const [rating, setRating] = useState(0);
  const [hover, setHover] = useState(0);
  const [submitted, setSubmitted] = useState(false);
  const [showFeedback, setShowFeedback] = useState(false);
  const [feedback, setFeedback] = useState('');

  const handleRate = (star: number) => {
    setRating(star);
    setShowFeedback(true);
  };

  const handleSubmit = () => {
    submitCSAT(sessionId, rating, feedback || undefined, intent);
    setSubmitted(true);
  };

  if (submitted) {
    return (
      <div style={{
        padding: '12px 16px',
        background: 'rgba(34, 197, 94, 0.1)',
        borderRadius: '8px',
        margin: '8px 0',
        fontSize: '13px',
        color: '#22c55e',
        textAlign: 'center',
      }}>
        ✅ Thank you for your feedback!
      </div>
    );
  }

  return (
    <div style={{
      padding: '12px 16px',
      background: 'rgba(255, 255, 255, 0.05)',
      borderRadius: '8px',
      margin: '8px 0',
      border: '1px solid rgba(255, 255, 255, 0.1)',
    }}>
      <div style={{ fontSize: '13px', marginBottom: '8px', color: 'var(--text-muted)' }}>
        How was your experience?
      </div>
      <div style={{ display: 'flex', gap: '4px', marginBottom: showFeedback ? '8px' : '0' }}>
        {[1, 2, 3, 4, 5].map((star) => (
          <button
            key={star}
            onClick={() => handleRate(star)}
            onMouseEnter={() => setHover(star)}
            onMouseLeave={() => setHover(0)}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              fontSize: '24px',
              color: (hover || rating) >= star ? '#eab308' : 'rgba(255,255,255,0.2)',
              padding: '0 2px',
              transition: 'color 0.15s',
            }}
          >
            ★
          </button>
        ))}
      </div>
      {showFeedback && (
        <>
          <input
            type="text"
            placeholder="Optional feedback..."
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            style={{
              width: '100%',
              padding: '6px 10px',
              borderRadius: '6px',
              border: '1px solid rgba(255,255,255,0.1)',
              background: 'rgba(255,255,255,0.05)',
              color: 'var(--text)',
              fontSize: '13px',
              marginBottom: '8px',
            }}
          />
          <button
            onClick={handleSubmit}
            style={{
              padding: '6px 16px',
              borderRadius: '6px',
              border: 'none',
              background: 'var(--primary)',
              color: '#fff',
              cursor: 'pointer',
              fontSize: '13px',
              fontWeight: 600,
            }}
          >
            Submit Rating
          </button>
        </>
      )}
    </div>
  );
}
