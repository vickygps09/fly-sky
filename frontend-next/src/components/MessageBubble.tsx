'use client';

import { useState, useEffect, useRef } from 'react';
import type { ChatMessage } from '@/types';
import type { ResponseMetadata, BoardingPass } from '@/types';
import { formatMessage, formatIntentLabel } from '@/lib/api';
import FlightCard from './FlightCard';

interface MessageBubbleProps {
  message: ChatMessage;
  onFlightSelect: (flightId: string, number: number) => void;
  onBoardingPass: (bp: BoardingPass) => void;
  onStreamComplete?: (msgId: string) => void;
}

export default function MessageBubble({
  message,
  onFlightSelect,
  onBoardingPass,
  onStreamComplete,
}: MessageBubbleProps) {
  const handleContentClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement;
    if (target.tagName === 'A') {
      const href = (target as HTMLAnchorElement).getAttribute('href') || '';
      if (href.includes('boarding-pass') && metadata?.boarding_pass) {
        e.preventDefault();
        onBoardingPass(metadata.boarding_pass);
      }
    }
  };
  const avatar = message.role === 'user' ? 'U' : '✈';
  const metadata = (message.metadata || null) as ResponseMetadata | null;

  const hasFlightCards = metadata?.flight_cards && metadata.flight_cards.length > 0;
  const hasBoardingPass = !!metadata?.boarding_pass;
  const hasEscalation = !!message.escalated;
  const hasIntent = !!message.intent;

  // Typewriter streaming state
  const isStreaming = message.role === 'bot' && message.streaming;
  const words = (message.content || '').split(' ');
  const [wordIndex, setWordIndex] = useState(isStreaming ? 0 : words.length);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!isStreaming) return;

    const speed = Math.max(15, Math.min(40, 800 / words.length));
    intervalRef.current = setInterval(() => {
      setWordIndex((prev) => {
        if (prev >= words.length) {
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
          return prev;
        }
        return prev + 1;
      });
    }, speed);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Notify parent when streaming completes — separate useEffect to avoid
  // calling parent setState during our own state updater (React error).
  useEffect(() => {
    if (isStreaming && wordIndex >= words.length && onStreamComplete) {
      onStreamComplete(message.id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wordIndex]);

  const displayedText = words.slice(0, wordIndex).join(' ');
  const html = formatMessage(displayedText);
  const streamDone = wordIndex >= words.length;

  const renderExtras = () => (
    <>
      {streamDone && hasFlightCards && (
        <div className="flight-cards-container">
          {metadata!.flight_cards!.map((flight, i) => (
            <FlightCard
              key={flight.id}
              flight={flight}
              number={i + 1}
              onSelect={onFlightSelect}
            />
          ))}
        </div>
      )}
      {streamDone && hasBoardingPass && (
        <button
          className="btn-primary"
          style={{ marginTop: '12px' }}
          onClick={() => onBoardingPass(metadata!.boarding_pass!)}
        >
          📥 View Boarding Pass
        </button>
      )}
      {streamDone && hasEscalation && (
        <div className="escalation-banner">
          <span className="escalation-icon">🤝</span>
          <div className="escalation-text">
            <strong>Transferred to Human Agent</strong>
            <span>A support representative will assist you shortly.</span>
          </div>
        </div>
      )}
    </>
  );

  if (hasFlightCards || hasBoardingPass) {
    return (
      <div className={`message ${message.role}`}>
        <div className="message-inner">
          <div className="message-avatar">{avatar}</div>
          <div className="message-content-wrap">
            <div
              className={`message-content ${isStreaming && !streamDone ? 'typewriter-cursor' : ''}`}
              onClick={handleContentClick}
              dangerouslySetInnerHTML={{ __html: html }}
            />
            {renderExtras()}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`message ${message.role}`}>
      <div className="message-inner">
        <div className="message-avatar">{avatar}</div>
        <div className="message-content-wrap">
          <div
            className={`message-content ${isStreaming && !streamDone ? 'typewriter-cursor' : ''}`}
            dangerouslySetInnerHTML={{ __html: html }}
          />
          {streamDone && hasEscalation && (
            <div className="escalation-banner">
              <span className="escalation-icon">🤝</span>
              <div className="escalation-text">
                <strong>Transferred to Human Agent</strong>
                <span>A support representative will assist you shortly.</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
