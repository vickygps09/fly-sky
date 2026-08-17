'use client';

import { useState, useRef, useEffect } from 'react';

interface DatePickerProps {
  value: string;
  onChange: (date: string) => void;
  placeholder?: string;
  minDate?: string;
  alwaysOpen?: boolean;
  onClose?: () => void;
}

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const WEEKDAYS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

export default function DatePicker({ value, onChange, placeholder = 'Select date', minDate, alwaysOpen = false, onClose }: DatePickerProps) {
  const [open, setOpen] = useState(alwaysOpen);
  const [viewDate, setViewDate] = useState(() => {
    if (value) return new Date(value + 'T00:00:00');
    return new Date();
  });
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        if (onClose) onClose();
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [onClose]);

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const minDateObj = minDate ? new Date(minDate + 'T00:00:00') : today;

  const year = viewDate.getFullYear();
  const month = viewDate.getMonth();
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const selectedDate = value ? new Date(value + 'T00:00:00') : null;

  const formatDate = (d: Date) => {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  };

  const handleSelect = (day: number) => {
    const date = new Date(year, month, day);
    if (date < minDateObj) return;
    onChange(formatDate(date));
    setOpen(false);
    if (onClose) onClose();
  };

  const prevMonth = () => setViewDate(new Date(year, month - 1, 1));
  const nextMonth = () => setViewDate(new Date(year, month + 1, 1));

  const displayValue = value
    ? new Date(value + 'T00:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })
    : placeholder;

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block', width: '100%' }}>
      {!alwaysOpen && (
        <button
          type="button"
          onClick={() => setOpen(!open)}
          style={{
            width: '100%',
            padding: '10px 14px',
            borderRadius: '8px',
            border: '1px solid rgba(255,255,255,0.15)',
            background: 'rgba(255,255,255,0.05)',
            color: value ? 'var(--text)' : 'var(--text-muted)',
            fontSize: '14px',
            textAlign: 'left',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <span>📅</span>
          <span>{displayValue}</span>
        </button>
      )}

      {(open || alwaysOpen) && (
        <div style={{
          position: 'absolute',
          bottom: 'calc(100% + 4px)',
          left: 0,
          zIndex: 1000,
          background: 'var(--bg-card, #1a1a2e)',
          borderRadius: '12px',
          border: '1px solid rgba(255,255,255,0.15)',
          padding: '12px',
          boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
          width: '280px',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <button type="button" onClick={prevMonth} style={{ background: 'none', border: 'none', color: 'var(--text)', cursor: 'pointer', fontSize: '18px', padding: '4px 8px' }}>‹</button>
            <span style={{ fontWeight: 600, fontSize: '14px' }}>{MONTHS[month]} {year}</span>
            <button type="button" onClick={nextMonth} style={{ background: 'none', border: 'none', color: 'var(--text)', cursor: 'pointer', fontSize: '18px', padding: '4px 8px' }}>›</button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '2px', marginBottom: '4px' }}>
            {WEEKDAYS.map((d) => (
              <div key={d} style={{ textAlign: 'center', fontSize: '11px', color: 'var(--text-muted)', padding: '4px' }}>{d}</div>
            ))}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '2px' }}>
            {Array.from({ length: firstDay }).map((_, i) => (
              <div key={`empty-${i}`} />
            ))}
            {Array.from({ length: daysInMonth }).map((_, i) => {
              const day = i + 1;
              const date = new Date(year, month, day);
              const isDisabled = date < minDateObj;
              const isSelected = selectedDate && selectedDate.getTime() === date.getTime();
              const isToday = today.getTime() === date.getTime();
              return (
                <button
                  key={day}
                  type="button"
                  disabled={isDisabled}
                  onClick={() => handleSelect(day)}
                  style={{
                    aspectRatio: '1',
                    border: 'none',
                    borderRadius: '6px',
                    cursor: isDisabled ? 'not-allowed' : 'pointer',
                    fontSize: '13px',
                    fontWeight: isSelected ? 700 : 400,
                    background: isSelected ? 'var(--primary)' : isToday ? 'rgba(255,255,255,0.1)' : 'transparent',
                    color: isDisabled ? 'rgba(255,255,255,0.2)' : isSelected ? '#fff' : 'var(--text)',
                    opacity: isDisabled ? 0.4 : 1,
                  }}
                >
                  {day}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
