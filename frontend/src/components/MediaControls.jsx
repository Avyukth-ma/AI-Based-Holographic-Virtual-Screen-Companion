import React from 'react';
import { Camera, CameraOff, RefreshCw, Power } from 'lucide-react';

export function MediaControls({
  hasPermissions,
  isCameraActive,
  isConnected,
  onStartSession,
  onToggleCamera,
  onReconnect,
}) {
  return (
    <div className="media-controls-wrapper">
      {!hasPermissions ? (
        <button
          id="btn-start-session"
          className="btn-primary"
          onClick={onStartSession}
          disabled={!isConnected}
        >
          <Power size={18} />
          <span>Enable Camera</span>
        </button>
      ) : (
        <div className="controls-button-row">
          <button
            id="btn-toggle-camera"
            className={`btn-control ${isCameraActive ? 'active' : 'inactive'}`}
            onClick={onToggleCamera}
            title={isCameraActive ? 'Disable Camera' : 'Enable Camera'}
          >
            {isCameraActive ? <Camera size={20} /> : <CameraOff size={20} />}
            <span>{isCameraActive ? 'Camera ON' : 'Camera OFF'}</span>
          </button>

          {!isConnected && (
            <button
              id="btn-reconnect"
              className="btn-control warning"
              onClick={onReconnect}
              title="Reconnect WebSocket"
            >
              <RefreshCw size={20} />
              <span>Reconnect</span>
            </button>
          )}
        </div>
      )}
    </div>
  );
}
