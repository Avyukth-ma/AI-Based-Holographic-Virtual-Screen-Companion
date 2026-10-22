import { useEffect, useRef } from 'react';

/**
 * Custom hook to periodically capture compressed video frames from a MediaStream
 * and transmit them over WebSocket for real-time computer vision processing.
 */
export function useFrameExtractor({
  stream,
  isCameraActive,
  isConnected,
  onSendFrame,
  onFrameReady,
  fps = 6,
  width = 360,
  height = 270,
  quality = 0.50,
}) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const intervalRef = useRef(null);
  const isSendingRef = useRef(false);

  useEffect(() => {
    // Only capture when camera is active, connected to backend, and stream is available
    if (!isCameraActive || !isConnected || !stream) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      return;
    }

    // Create offscreen video element to read stream tracks
    if (!videoRef.current) {
      const video = document.createElement('video');
      video.muted = true;
      video.playsInline = true;
      video.autoplay = true;
      videoRef.current = video;
    }

    // Create offscreen canvas for resizing and JPEG compression
    if (!canvasRef.current) {
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      canvasRef.current = canvas;
    }

    const video = videoRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d', { willReadFrequently: false });

    video.srcObject = stream;
    video.play().catch((err) => console.warn('[FrameExtractor] video play failed:', err));

    const intervalMs = Math.round(1000 / fps);

    intervalRef.current = setInterval(() => {
      if (
        !video ||
        video.readyState < 2 || // HAVE_CURRENT_DATA
        video.videoWidth === 0 ||
        video.videoHeight === 0 ||
        isSendingRef.current
      ) {
        return;
      }

      try {
        isSendingRef.current = true;
        // Draw scaled frame to canvas
        ctx.drawImage(video, 0, 0, width, height);

        // Convert to JPEG data URL
        const dataUrl = canvas.toDataURL('image/jpeg', quality);

        // Transmit frame
        const frameHandler = onFrameReady || onSendFrame;
        if (frameHandler) {
          frameHandler(dataUrl);
        }
      } catch (err) {
        console.error('[FrameExtractor] Capture error:', err);
      } finally {
        isSendingRef.current = false;
      }
    }, intervalMs);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      if (video) {
        video.srcObject = null;
      }
    };
  }, [stream, isCameraActive, isConnected, onSendFrame, onFrameReady, fps, width, height, quality]);
}
