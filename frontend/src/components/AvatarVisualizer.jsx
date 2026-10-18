import React from 'react';

/**
 * AvatarVisualizer renders the dynamic holographic AI avatar synthesized 
 * by the Pillow (PIL) backend engine.
 */
export function AvatarVisualizer({ status = 'idle', audioLevel = 0, avatarFrame = null }) {
  const scale = 1 + (audioLevel || 0) * 0.15;

  return (
    <div className={`avatar-container ${status}`}>
      {avatarFrame ? (
        <div 
          className="hologram-wrapper"
          style={{
            transform: `scale(${scale})`,
            transition: 'transform 0.15s ease-out',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            filter: status === 'speaking' ? 'drop-shadow(0 0 15px rgba(255,180,0,0.6))' : 
                    status === 'thinking' ? 'drop-shadow(0 0 15px rgba(180,0,255,0.6))' : 
                    'drop-shadow(0 0 15px rgba(0,255,255,0.4))'
          }}
        >
          <img 
            src={`data:image/png;base64,${avatarFrame}`} 
            alt="AI Hologram Avatar"
            className="hologram-img"
            style={{
              width: '220px',
              height: '220px',
              objectFit: 'contain',
              animation: 'hologramFloat 4s ease-in-out infinite'
            }}
          />
        </div>
      ) : (
        <>
          <div
            className="orb-ring orb-ring-1"
            style={{ transform: `scale(${scale * 0.95})` }}
          />
          <div
            className="orb-ring orb-ring-2"
            style={{ transform: `scale(${scale * 1.05})` }}
          />
          <div
            className="orb-ring orb-ring-3"
            style={{ transform: `scale(${scale * 1.15})` }}
          />
          <div
            className="orb-core"
            style={{ transform: `scale(${scale})` }}
          />
        </>
      )}
    </div>
  );
}
