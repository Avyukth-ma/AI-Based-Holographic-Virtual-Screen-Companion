import React, { useEffect, useRef } from 'react';
import { Camera, CameraOff, Eye, Hand } from 'lucide-react';

// MediaPipe Hand Connection Skeleton pairs
const HAND_CONNECTIONS = [
  // Thumb
  [0, 1], [1, 2], [2, 3], [3, 4],
  // Index
  [0, 5], [5, 6], [6, 7], [7, 8],
  // Middle
  [0, 9], [9, 10], [10, 11], [11, 12],
  // Ring
  [0, 13], [13, 14], [14, 15], [15, 16],
  // Pinky
  [0, 17], [17, 18], [18, 19], [19, 20],
  // Palm Base
  [5, 9], [9, 13], [13, 17],
];

const GESTURE_EMOJIS = {
  open_palm: '✋ Open Palm (PAUSE)',
  victory: '✌️ Victory',
  thumbs_up: '👍 Thumbs Up',
  pointing_up: '☝️ Pointing',
  fist: '✊ Fist',
};

/**
 * VideoPreview renders the live webcam stream along with a real-time
 * canvas overlay for YOLOv8 presence detection and MediaPipe hand/face tracking.
 */
export function VideoPreview({ stream, isCameraActive, perceptionData }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);

  // Bind WebRTC stream to video element
  useEffect(() => {
    if (videoRef.current) {
      if (stream && isCameraActive) {
        videoRef.current.srcObject = stream;
      } else {
        videoRef.current.srcObject = null;
      }
    }
  }, [stream, isCameraActive]);

  // Render perception overlay (bounding boxes, hand skeletons, gesture tags)
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !isCameraActive) return;

    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    // Clear previous drawings
    ctx.clearRect(0, 0, width, height);

    if (!perceptionData) return;

    // Helper: Map normalized coords [0, 1] to mirrored canvas coords (since webcam is mirrored horizontally)
    const mapX = (normX) => (1 - normX) * width;
    const mapY = (normY) => normY * height;

    // 1. Draw YOLOv8 Person Bounding Boxes
    if (perceptionData.persons && perceptionData.persons.length > 0) {
      // Find primary person (highest confidence)
      const primaryPerson = perceptionData.persons.reduce((prev, current) => 
        (prev.confidence > current.confidence) ? prev : current
      );

      // Draw Total Person Count at the top right
      ctx.save();
      const countLabel = `Total Persons: ${perceptionData.persons.length}`;
      ctx.font = '700 14px Outfit, sans-serif';
      const countWidth = ctx.measureText(countLabel).width;
      ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
      ctx.fillRect(width - countWidth - 30, 10, countWidth + 20, 30);
      ctx.fillStyle = '#00f2fe';
      ctx.fillText(countLabel, width - countWidth - 20, 31);

      const [x1, y1, x2, y2] = primaryPerson.bbox;
      const left = mapX(x2);
      const top = mapY(y1);
      const boxWidth = (x2 - x1) * width;
      const boxHeight = (y2 - y1) * height;

      // Glowing cyan box for primary person
      ctx.strokeStyle = '#00f2fe';
      ctx.lineWidth = 2;
      ctx.shadowColor = 'rgba(0, 242, 254, 0.6)';
      ctx.shadowBlur = 8;
      ctx.strokeRect(left, top, boxWidth, boxHeight);

      // Label pill
      const label = `Primary: ${(primaryPerson.confidence * 100).toFixed(0)}%`;
      ctx.font = '600 11px Outfit, sans-serif';
      const textWidth = ctx.measureText(label).width;

      ctx.fillStyle = 'rgba(0, 242, 254, 0.85)';
      ctx.fillRect(left, top - 18 > 0 ? top - 18 : top, textWidth + 10, 18);

      ctx.fillStyle = '#07090e';
      ctx.fillText(label, left + 5, top - 18 > 0 ? top - 5 : top + 13);
      ctx.restore();
    }

    // 2. Draw MediaPipe Face Bounding Boxes
    if (perceptionData.faces && perceptionData.faces.length > 0) {
      perceptionData.faces.forEach((face) => {
        const [x1, y1, x2, y2] = face.bbox;
        const left = mapX(x2);
        const top = mapY(y1);
        const boxWidth = (x2 - x1) * width;
        const boxHeight = (y2 - y1) * height;

        ctx.save();
        ctx.strokeStyle = '#c084fc';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 4]);
        ctx.shadowColor = 'rgba(192, 132, 252, 0.6)';
        ctx.shadowBlur = 6;
        ctx.strokeRect(left, top, boxWidth, boxHeight);
        ctx.restore();
      });
    }

    // 3. Draw MediaPipe Hand Skeleton & Landmarks
    if (perceptionData.hands && perceptionData.hands.length > 0) {
      perceptionData.hands.forEach((hand) => {
        const lms = hand.landmarks;
        if (!lms || lms.length < 21) return;

        // Draw bone connections
        ctx.save();
        ctx.strokeStyle = 'rgba(16, 185, 129, 0.8)';
        ctx.lineWidth = 2;
        ctx.shadowColor = 'rgba(16, 185, 129, 0.6)';
        ctx.shadowBlur = 4;

        HAND_CONNECTIONS.forEach(([i, j]) => {
          const pt1 = lms[i];
          const pt2 = lms[j];
          ctx.beginPath();
          ctx.moveTo(mapX(pt1[0]), mapY(pt1[1]));
          ctx.lineTo(mapX(pt2[0]), mapY(pt2[1]));
          ctx.stroke();
        });

        // Draw joint points
        lms.forEach((lm, idx) => {
          const px = mapX(lm[0]);
          const py = mapY(lm[1]);

          ctx.beginPath();
          ctx.arc(px, py, idx % 4 === 0 ? 4 : 2.5, 0, 2 * Math.PI);
          ctx.fillStyle = idx === 4 || idx === 8 || idx === 12 || idx === 16 || idx === 20 ? '#fbbf24' : '#10b981';
          ctx.fill();
        });

        // Draw Recognized Gesture Badge
        if (hand.gesture && hand.gesture !== 'unknown') {
          const wrist = lms[0];
          const badgeX = mapX(wrist[0]);
          const badgeY = Math.max(20, mapY(wrist[1]) - 15);

          const badgeText = GESTURE_EMOJIS[hand.gesture] || hand.gesture.toUpperCase();
          ctx.font = '700 11px Outfit, sans-serif';
          const textMetrics = ctx.measureText(badgeText);
          const badgeW = textMetrics.width + 16;
          const badgeH = 22;

          ctx.fillStyle = hand.gesture === 'open_palm' ? 'rgba(244, 63, 94, 0.9)' : 'rgba(16, 185, 129, 0.9)';
          ctx.beginPath();
          ctx.roundRect(badgeX - badgeW / 2, badgeY - badgeH, badgeW, badgeH, 6);
          ctx.fill();

          ctx.fillStyle = '#ffffff';
          ctx.fillText(badgeText, badgeX - badgeW / 2 + 8, badgeY - 6);
        }
        ctx.restore();
      });
    }
  }, [perceptionData, isCameraActive]);

  const activeGesture = perceptionData?.hands?.find((h) => h.gesture && h.gesture !== 'unknown')?.gesture;

  return (
    <div className="video-card">
      <div className="video-header">
        <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <Eye size={16} /> Perception Feed
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {perceptionData?.inference_time_ms ? (
            <span className="metric-pill" style={{ color: 'var(--accent-cyan)' }}>
              {perceptionData.inference_time_ms}ms
            </span>
          ) : null}
          <span className="metric-pill">
            {isCameraActive ? 'LIVE' : 'PAUSED'}
          </span>
        </div>
      </div>

      <div className="video-frame-container">
        {isCameraActive ? (
          <>
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="video-element"
            />
            <canvas
              ref={canvasRef}
              width={640}
              height={480}
              className="video-overlay-canvas"
            />
            <div className="video-overlay-badge">
              <span className="dot" />
              <span>
                {perceptionData?.user_present ? 'User Detected' : 'Scanning...'}
              </span>
            </div>

            {activeGesture && (
              <div
                className="gesture-alert-pill"
                style={{
                  position: 'absolute',
                  bottom: '12px',
                  left: '50%',
                  transform: 'translateX(-50%)',
                  background: activeGesture === 'open_palm' ? 'rgba(244, 63, 94, 0.9)' : 'rgba(16, 185, 129, 0.9)',
                  padding: '0.35rem 0.8rem',
                  borderRadius: '9999px',
                  fontSize: '0.75rem',
                  fontWeight: '700',
                  color: '#fff',
                  boxShadow: '0 4px 15px rgba(0,0,0,0.5)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  zIndex: 10,
                }}
              >
                <Hand size={14} />
                <span>{GESTURE_EMOJIS[activeGesture] || activeGesture}</span>
              </div>
            )}
          </>
        ) : (
          <div className="video-placeholder">
            <CameraOff size={36} />
            <p>Camera is disabled</p>
          </div>
        )}
      </div>
    </div>
  );
}
