import React from 'react';

/**
 * StatusBadge component displays the real-time cognition / connection state.
 * States: 'idle' | 'listening' | 'thinking' | 'speaking' | 'disconnected'
 */
export function StatusBadge({ status = 'idle' }) {
  const statusConfig = {
    idle: { label: 'Companion Ready', className: 'idle' },
    listening: { label: 'Listening...', className: 'listening' },
    thinking: { label: 'Thinking...', className: 'thinking' },
    speaking: { label: 'Speaking...', className: 'speaking' },
    disconnected: { label: 'Disconnected', className: 'disconnected' },
  };

  const current = statusConfig[status] || statusConfig.idle;

  return (
    <div className={`status-badge ${current.className}`}>
      <span className="status-dot" />
      <span>{current.label}</span>
    </div>
  );
}
