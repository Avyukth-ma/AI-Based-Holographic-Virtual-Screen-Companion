import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Custom hook to manage WebSocket connection with FastAPI backend.
 * Features auto-reconnect, latency ping/pong, and message event listeners.
 */
export function useWebSocket(url = null) {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  const [latency, setLatency] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState('disconnected'); // disconnected, connecting, connected

  const wsRef = useRef(null);
  const pingIntervalRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);
  const listenersRef = useRef(new Set());

  // Determine target WebSocket URL
  const getWsUrl = useCallback(() => {
    if (url) return url;
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // Fallback to localhost:8000 if running directly on vite port 5173
    const host = window.location.port === '5173' ? 'localhost:8000' : window.location.host;
    return `${protocol}//${host}/ws/companion`;
  }, [url]);

  const connect = useCallback(() => {
    try {
      if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
        return;
      }

      setConnectionStatus('connecting');
      const wsUrl = getWsUrl();
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        setConnectionStatus('connected');
        reconnectAttemptsRef.current = 0;
        console.log('[WebSocket] Connected to', wsUrl);

        // Start ping interval (every 3 seconds for responsive latency measurement)
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping', payload: { timestamp: Date.now() } }));
          }
        }, 3000);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'pong' && data.payload?.client_timestamp) {
            const rawRtt = Date.now() - data.payload.client_timestamp;
            // Ignore stale pings from before a reconnect (>10s)
            if (rawRtt >= 0 && rawRtt < 10000) {
              setLatency(rawRtt);
            }
          } else {
            setLastMessage(data);
            listenersRef.current.forEach((listener) => listener(data));
          }
        } catch (e) {
          console.warn('[WebSocket] Received non-JSON message:', event.data);
        }
      };

      ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error);
      };

      ws.onclose = () => {
        setIsConnected(false);
        setConnectionStatus('disconnected');

        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);

        // Attempt reconnect with exponential backoff (max 30s)
        const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
        console.log(`[WebSocket] Connection closed. Reconnecting in ${delay}ms... (Attempt ${reconnectAttemptsRef.current + 1})`);
        
        if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectAttemptsRef.current += 1;
          connect();
        }, delay);
      };
    } catch (err) {
      console.error('[WebSocket] Failed to connect:', err);
      setConnectionStatus('disconnected');
    }
  }, [getWsUrl]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
    setConnectionStatus('disconnected');
  }, []);

  const sendMessage = useCallback((type, payload = {}) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, payload }));
      return true;
    }
    console.warn('[WebSocket] Cannot send message, socket not open');
    return false;
  }, []);

  const sendBinary = useCallback((data) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(data);
      return true;
    }
    return false;
  }, []);

  const addMessageListener = useCallback((listener) => {
    listenersRef.current.add(listener);
    return () => listenersRef.current.delete(listener);
  }, []);

  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    isConnected,
    connectionStatus,
    lastMessage,
    latency,
    connect,
    disconnect,
    sendMessage,
    sendBinary,
    addMessageListener,
  };
}
