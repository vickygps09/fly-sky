'use client';

export default function TypingIndicator() {
  return (
    <div className="typing-indicator">
      <div className="typing-inner">
        <div className="typing-avatar">✈</div>
        <div className="typing-dots">
          <div className="typing-dot" />
          <div className="typing-dot" />
          <div className="typing-dot" />
        </div>
      </div>
    </div>
  );
}
