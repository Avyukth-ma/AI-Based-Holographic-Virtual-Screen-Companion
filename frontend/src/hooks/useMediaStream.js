import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * Custom hook to manage WebRTC MediaStream (Camera only).
 */
export function useMediaStream() {
  const [stream, setStream] = useState(null);
  const [isCameraActive, setIsCameraActive] = useState(false);
  const [permissionError, setPermissionError] = useState(null);
  const [hasPermissions, setHasPermissions] = useState(false);

  const streamRef = useRef(null);

  // Initialize media devices with user permissions
  const startMedia = useCallback(async (video = true) => {
    try {
      setPermissionError(null);

      // Stop any existing stream before creating a new one
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }

      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: video
          ? {
              width: { ideal: 640 },
              height: { ideal: 480 },
              facingMode: 'user',
            }
          : false,
        audio: false, // Voice input removed as per user request
      });

      streamRef.current = mediaStream;
      setStream(mediaStream);
      setIsCameraActive(video && mediaStream.getVideoTracks().some((t) => t.enabled));
      setHasPermissions(true);

      return mediaStream;
    } catch (err) {
      console.error('Error accessing media devices:', err);
      setPermissionError(err.message || 'Media permission denied');
      setHasPermissions(false);
      return null;
    }
  }, []);

  // Stop all media tracks
  const stopMedia = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    setStream(null);
    setIsCameraActive(false);
  }, []);

  // Toggle Camera Track
  const toggleCamera = useCallback(async () => {
    if (!streamRef.current) {
      return await startMedia(true);
    }
    const videoTracks = streamRef.current.getVideoTracks();
    if (videoTracks.length === 0) {
      // Need to re-request with video track enabled
      return await startMedia(true);
    }
    const nextState = !videoTracks[0].enabled;
    videoTracks.forEach((track) => {
      track.enabled = nextState;
    });
    setIsCameraActive(nextState);
  }, [startMedia]);

  // Cleanup tracks on unmount
  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  return {
    stream,
    isCameraActive,
    permissionError,
    hasPermissions,
    startMedia,
    stopMedia,
    toggleCamera,
  };
}
