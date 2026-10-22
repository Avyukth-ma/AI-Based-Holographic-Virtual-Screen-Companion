import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Bot, Wifi, WifiOff, Volume2, Activity, Mic } from 'lucide-react';
import { useMediaStream } from './hooks/useMediaStream';
import { useWebSocket } from './hooks/useWebSocket';
import { usePushToTalk } from './hooks/usePushToTalk';
import { useFrameExtractor } from './hooks/useFrameExtractor';
import { VideoPreview } from './components/VideoPreview';
import { Hologram } from './components/Hologram';
import { MediaControls } from './components/MediaControls';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

function StatusBadge({ status }) {
  const getStatusConfig = () => {
    switch (status) {
      case 'listening':
        return { label: 'Listening', className: 'status-badge listening' };
      case 'thinking':
        return { label: 'Thinking...', className: 'status-badge thinking' };
      case 'speaking':
        return { label: 'Speaking', className: 'status-badge speaking' };
      case 'error':
        return { label: 'Error / Timeout', className: 'status-badge error' };
      case 'idle':
      default:
        return { label: 'Standby / Ready', className: 'status-badge idle' };
    }
  };

  const config = getStatusConfig();
  return <div className={config.className}>{config.label}</div>;
}

export default function App() {
  const [logs, setLogs] = useState([]);
  const [companionState, setCompanionState] = useState('idle');
  const [subtitle, setSubtitle] = useState('Welcome! Click "Enable Camera" to begin.');
  const [perceptionData, setPerceptionData] = useState(null);
  const [sentenceChunks, setSentenceChunks] = useState([]);
  const [activeSpeakingIndex, setActiveSpeakingIndex] = useState(-1);

  const audioPlayerRef = useRef(new Audio());
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const volumeRef = useRef(0); // Stores live volume 0.0 to 1.0
  const sourceNodeRef = useRef(null);
  const audioQueueRef = useRef([]); // Queue of { audio, text, is_final }
  const isAudioPlayingRef = useRef(false);
  const lastGestureLogRef = useRef({ gesture: null, timestamp: 0 });
  const targetGazeRef = useRef({ x: 0, y: 0 });

  // Intercept and swallow OS media keys (like 4-finger touchpad taps)
  useEffect(() => {
    if ('mediaSession' in navigator) {
      const noop = () => { /* Suppress OS Media Play/Pause events */ };
      navigator.mediaSession.setActionHandler('play', noop);
      navigator.mediaSession.setActionHandler('pause', noop);
      navigator.mediaSession.setActionHandler('stop', noop);
      navigator.mediaSession.setActionHandler('seekbackward', noop);
      navigator.mediaSession.setActionHandler('seekforward', noop);
      navigator.mediaSession.setActionHandler('previoustrack', noop);
      navigator.mediaSession.setActionHandler('nexttrack', noop);
    }
  }, []);

  // Initialize Web Audio API Analyser for dynamic emissive visual pulsing
  const initAudioAnalyzer = useCallback(() => {
    try {
      if (!audioContextRef.current) {
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        if (!AudioContextClass) return;
        audioContextRef.current = new AudioContextClass();
      }

      if (audioContextRef.current.state === 'suspended') {
        audioContextRef.current.resume();
      }

      if (!analyserRef.current && audioContextRef.current) {
        const analyser = audioContextRef.current.createAnalyser();
        analyser.fftSize = 256;
        analyser.smoothingTimeConstant = 0.8;
        analyserRef.current = analyser;
      }

      if (!sourceNodeRef.current && audioPlayerRef.current && audioContextRef.current && analyserRef.current) {
        const source = audioContextRef.current.createMediaElementSource(audioPlayerRef.current);
        source.connect(analyserRef.current);
        analyserRef.current.connect(audioContextRef.current.destination);
        sourceNodeRef.current = source;
      }
    } catch (err) {
      console.warn('[AudioAnalyzer] Initialization error:', err);
    }
  }, []);

  // Seamless queue-based audio playback for sentence-streaming without pauses or clipping
  const playNextAudioChunk = useCallback(() => {
    if (audioQueueRef.current.length === 0) {
      isAudioPlayingRef.current = false;
      setCompanionState('idle');
      volumeRef.current = 0;
      setActiveSpeakingIndex(-1);
      return;
    }

    const nextItem = audioQueueRef.current.shift();
    isAudioPlayingRef.current = true;
    setCompanionState('speaking');
    
    if (nextItem.chunk_index !== undefined) {
      setActiveSpeakingIndex(nextItem.chunk_index);
    }

    if (nextItem.audio && audioPlayerRef.current) {
      initAudioAnalyzer();
      if (audioContextRef.current && audioContextRef.current.state === 'suspended') {
        audioContextRef.current.resume();
      }

      audioPlayerRef.current.src = `data:audio/mp3;base64,${nextItem.audio}`;
      audioPlayerRef.current
        .play()
        .then(() => {
          audioPlayerRef.current.onended = () => {
            playNextAudioChunk();
          };
        })
        .catch((err) => {
          console.warn('[AudioPlayer] Error playing audio chunk:', err);
          playNextAudioChunk();
        });
    } else {
      playNextAudioChunk();
    }
  }, [initAudioAnalyzer]);

  // Listen for user gestures to unlock/resume AudioContext per browser autoplay policies
  useEffect(() => {
    const handleResumeAudio = () => {
      if (audioContextRef.current && audioContextRef.current.state === 'suspended') {
        audioContextRef.current.resume();
      }
    };
    window.addEventListener('click', handleResumeAudio);
    window.addEventListener('keydown', handleResumeAudio);
    return () => {
      window.removeEventListener('click', handleResumeAudio);
      window.removeEventListener('keydown', handleResumeAudio);
    };
  }, []);

  // Continuous animation frame loop to read analyser data and compute normalized volume
  useEffect(() => {
    let animationFrameId;
    const dataArray = new Uint8Array(128);

    const updateVolume = () => {
      if (analyserRef.current) {
        analyserRef.current.getByteFrequencyData(dataArray);
        let sumSquares = 0;
        for (let i = 0; i < dataArray.length; i++) {
          sumSquares += dataArray[i] * dataArray[i];
        }
        const rms = Math.sqrt(sumSquares / dataArray.length);
        // Normalize between 0.0 and 1.0 (voice RMS typically reaches 60-120)
        const normalized = Math.min(1.0, Math.max(0.0, rms / 100.0));
        volumeRef.current = normalized;
      }
      animationFrameId = requestAnimationFrame(updateVolume);
    };

    animationFrameId = requestAnimationFrame(updateVolume);
    return () => {
      if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
      }
    };
  }, []);

  // 1. WebRTC Camera Stream Hook (No Mic)
  const {
    stream,
    isCameraActive,
    permissionError,
    hasPermissions,
    startMedia,
    toggleCamera,
  } = useMediaStream();

  // 2. WebSocket Real-Time Channel Hook
  const {
    isConnected,
    latency,
    connect,
    sendMessage,
    addMessageListener,
  } = useWebSocket();

  const lastLogRef = useRef('');

  // Helper to append timestamped event logs
  const addLog = useCallback((message, type = 'system') => {
    lastLogRef.current = message;
    const timeStr = new Date().toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
    setLogs((prev) => {
      // Event Log Guard: skip adding duplicate consecutive interrupt logs
      if (message === 'AI output interrupted.' && prev.length > 0 && prev[0].message === 'AI output interrupted.') {
        return prev;
      }
      return [{ time: timeStr, message, type }, ...prev.slice(0, 49)];
    });
  }, []);

  // Stop audio playback and annihilate playback buffer + queued sentence chunks
  const stopAudioPlayback = useCallback(() => {
    audioQueueRef.current = [];
    isAudioPlayingRef.current = false;
    setActiveSpeakingIndex(-1);
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
      audioPlayerRef.current.currentTime = 0;
      audioPlayerRef.current.removeAttribute('src'); 
      audioPlayerRef.current.load();
    }
    volumeRef.current = 0;
    setCompanionState('idle');
  }, []);

  const {
    isListening,
    transcript,
    startListening,
    stopListening,
    setTranscript,
  } = usePushToTalk();

  // Watch for PTT transcript to send when listening stops
  useEffect(() => {
    if (!isListening && transcript.trim() && isConnected) {
      addLog(`You (Voice): "${transcript}"`, 'system');
      setSubtitle(`You (Voice): "${transcript}"`);
      setSentenceChunks([]);
      setCompanionState('thinking');
      sendMessage('text_message', { text: transcript.trim() });
      setTranscript('');
    }
  }, [isListening, transcript, isConnected, sendMessage, addLog, setTranscript]);


  // 3. WebCam Frame Extraction Hook (10 FPS)
  useFrameExtractor({
    stream,
    isCameraActive,
    isConnected,
    fps: 6,
    onFrameReady: (frameBase64) => {
      sendMessage('video_frame', {
        data: frameBase64,
        timestamp: Date.now(),
      });
    },
  });

  // WebSocket Message Dispatcher
  useEffect(() => {
    const unsubscribe = addMessageListener((message) => {
      const { type, payload } = message;

      if (type === 'server_ready') {
        addLog('Server Ready: Connected to AI Perception & Cognition Engine', 'success');
      } else if (type === 'perception_result') {
        setPerceptionData(payload);

        // Check if hand gesture was recognized
        if (payload.hands && payload.hands.length > 0) {
          const activeHand = payload.hands[0];
          const now = Date.now();
          const last = lastGestureLogRef.current;

          // Immediate priority interrupt: cut off audio if open palm is displayed while speaking
          if (activeHand.gesture === 'open_palm') {
            if (isAudioPlayingRef.current || audioQueueRef.current.length > 0) {
              stopAudioPlayback();
              setCompanionState('idle');
              setSubtitle('✋ AI paused. I am waiting for you.');
              setSentenceChunks([]);
              sendMessage('interrupt_request', {});
              if (now - last.timestamp > 1500) {
                addLog('✋ Gesture Detected: Open Palm (Speech Interrupted)', 'error');
                lastGestureLogRef.current = { gesture: activeHand.gesture, timestamp: now };
              }
            }
          }

          if (last.gesture !== activeHand.gesture || now - last.timestamp > 3000) {
            lastGestureLogRef.current = { gesture: activeHand.gesture, timestamp: now };

            if (activeHand.gesture === 'open_palm') {
              addLog('✋ Gesture Detected: Open Palm (Pause Triggered)', 'error');
              stopAudioPlayback();
              setCompanionState('idle');
              setSubtitle('✋ AI paused. I am waiting for you.');
              setSentenceChunks([]);
              sendMessage('interrupt_request', {});
            } else if (activeHand.gesture === 'victory') {
              addLog('✌️ Gesture Detected: Victory / Peace', 'success');
            } else if (activeHand.gesture === 'thumbs_up') {
              addLog('👍 Gesture Detected: Thumbs Up', 'success');
            } else if (activeHand.gesture === 'pointing_up') {
              addLog('☝️ Gesture Detected: Pointing Up (Scanning...)', 'system');
            } else if (activeHand.gesture === 'fist') {
              addLog('✊ Gesture Detected: Fist (Standby)', 'system');
            }
          }
        }
      } else if (type === 'ai_audio_response') {
        const { text, accumulated_text, audio, is_final, chunk_index } = payload;
        
        if (text) {
          if (chunk_index === 0) {
            setSentenceChunks([{ index: chunk_index, text }]);
            setSubtitle('');
            const textSnippet = text.length > 50 ? text.slice(0, 47) + '...' : text;
            addLog(`AI Companion: "${textSnippet}"`, 'success');
          } else {
            setSentenceChunks(prev => {
              if (prev.find(c => c.index === chunk_index)) return prev;
              return [...prev, { index: chunk_index, text }];
            });
          }
        }

        if (audio) {
          audioQueueRef.current.push({ audio, text, is_final, chunk_index });
          if (!isAudioPlayingRef.current) {
            playNextAudioChunk();
          }
        } else if (is_final && !isAudioPlayingRef.current) {
          setCompanionState('idle');
          volumeRef.current = 0;
          setActiveSpeakingIndex(-1);
        }
      } else if (type === 'ai_interrupted') {
        stopAudioPlayback();
        setCompanionState('idle');
        volumeRef.current = 0;
        setActiveSpeakingIndex(-1);
        setSubtitle((prev) => {
          if (!prev || prev.includes('[Interrupted]')) return prev;
          return `${prev} [Interrupted]`;
        });
        if (lastLogRef.current !== 'AI output interrupted.') {
          addLog('AI output interrupted.', 'error');
        }
      } else if (type === 'state_change') {
        if (payload.state) {
          setCompanionState(payload.state);
        }
      } else if (type === 'ai_state') {
        if (payload.state) {
          setCompanionState(payload.state);
        }
      } else if (type === 'status_ack') {
        addLog('Device status synced with backend', 'system');
      } else if (type === 'gaze') {
        targetGazeRef.current = { x: message.x, y: message.y };
      }
    });

    return () => unsubscribe();
  }, [addMessageListener, addLog, stopAudioPlayback, playNextAudioChunk]);

  // Sync camera toggle with backend
  useEffect(() => {
    if (isConnected) {
      sendMessage('client_status', {
        camera: isCameraActive,
        mic: false,
      });
    }
  }, [isCameraActive, isConnected, sendMessage]);

  // Auto-Scroll to Active Spoken Chunk
  useEffect(() => {
    if (activeSpeakingIndex >= 0) {
      const activeEl = document.getElementById(`chunk-${activeSpeakingIndex}`);
      if (activeEl) {
        activeEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    }
  }, [activeSpeakingIndex, sentenceChunks]);

  // Handler to start session by requesting user permissions
  const handleStartSession = async () => {
    initAudioAnalyzer();
    addLog('Requesting webcam access...', 'system');
    const media = await startMedia(true);
    if (media) {
      addLog('Camera permissions granted!', 'success');
      setSubtitle("I'm watching. Type a message or show gestures to interact.");
      setCompanionState('idle');
    } else {
      addLog('Camera permissions were denied or unavailable.', 'error');
    }
  };

  return (
    <div className="app-container">
      {/* Header Bar */}
      <header className="app-header">
        <div className="logo-area">
          <div className="logo-icon">
            <Bot size={24} />
          </div>
          <div className="logo-text">
            <h1>Multimodal AI Companion</h1>
            <span>Real-Time Perception & Cognition</span>
          </div>
        </div>

        <div className="header-status-area">
          <div className="metric-pill">
            {isConnected ? <Wifi size={14} color="var(--accent-emerald)" /> : <WifiOff size={14} color="var(--accent-rose)" />}
            <span>{isConnected ? `WS Connected ${latency ? `(${latency}ms)` : ''}` : 'WS Offline'}</span>
          </div>
          <StatusBadge status={companionState} />
        </div>
      </header>

      {/* Main Companion Workspace */}
      <main className="main-stage">
        {/* Center Stage: AI Visualizer & Dialogue */}
        <section className="visualizer-stage">
          <div className="stage-top-meta" style={{ display: 'flex', gap: '0.6rem', alignItems: 'center' }}>
            <span className="metric-pill" style={{ textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Cognition & Voice Unit
            </span>
            <span className="metric-pill" style={{ color: 'var(--accent-cyan, #06b6d4)', borderColor: 'rgba(6,182,212,0.3)' }}>
              Cognition: Active
            </span>
            <span className="metric-pill" style={{ color: 'var(--accent-emerald, #10b981)', borderColor: 'rgba(16,185,129,0.3)' }}>
              Neural State: Online
            </span>
            {companionState === 'speaking' && (
              <span className="metric-pill" style={{ color: 'var(--accent-amber)', borderColor: 'rgba(245,158,11,0.4)' }}>
                <Volume2 size={12} /> AI Speaking...
              </span>
            )}
          </div>

          <Hologram state={companionState} gazeRef={targetGazeRef} volumeRef={volumeRef} />

          <div className="dialogue-box">
            <div 
              className={`dialogue-text ${companionState !== 'idle' ? 'active' : ''}`}
              style={{
                maxHeight: '260px',
                overflowY: 'auto',
                padding: '1rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.75rem',
                scrollbarWidth: 'thin',
                scrollbarColor: 'rgba(255,255,255,0.2) transparent'
              }}
            >
              {permissionError ? `⚠️ Permission Error: ${permissionError}` : (
                <>
                  {subtitle && (
                    <div id="subtitle-box">
                      <ReactMarkdown 
                          remarkPlugins={[remarkGfm, remarkMath]} 
                          rehypePlugins={[rehypeKatex]}
                      >
                          {subtitle}
                      </ReactMarkdown>
                    </div>
                  )}
                  {sentenceChunks.length > 0 && sentenceChunks.map((chunk) => (
                    <div
                      key={chunk.index}
                      id={`chunk-${chunk.index}`}
                      style={{
                        marginRight: '0.25rem',
                        transition: 'color 0.3s ease, text-shadow 0.2s ease',
                        color: activeSpeakingIndex === -1 ? '#fff' :
                               chunk.index === activeSpeakingIndex ? '#fff' :
                               chunk.index < activeSpeakingIndex ? 'rgba(255,255,255,0.6)' :
                               'rgba(255,255,255,0.3)',
                        textShadow: (activeSpeakingIndex !== -1 && chunk.index === activeSpeakingIndex) 
                                    ? '0 0 10px rgba(255,255,255,0.8)' : 'none',
                      }}
                    >
                      <ReactMarkdown 
                          remarkPlugins={[remarkGfm, remarkMath]} 
                          rehypePlugins={[rehypeKatex]}
                          components={{ p: React.Fragment }}
                      >
                          {chunk.text + ' '}
                      </ReactMarkdown>
                    </div>
                  ))}
                </>
              )}
            </div>
          </div>

          <MediaControls
            hasPermissions={hasPermissions}
            isCameraActive={isCameraActive}
            isConnected={isConnected}
            onStartSession={handleStartSession}
            onToggleCamera={toggleCamera}
            onReconnect={connect}
          />


          {/* Text input chat */}
          {isConnected && (
            <div style={{ display: 'flex', gap: '0.5rem', width: '100%', marginTop: '0.75rem' }}>
              <button
                onMouseDown={() => {
                  initAudioAnalyzer();
                  startListening();
                }}
                onMouseUp={stopListening}
                onMouseLeave={stopListening}
                onTouchStart={() => {
                  initAudioAnalyzer();
                  startListening();
                }}
                onTouchEnd={stopListening}
                title="Hold to Speak"
                style={{
                  padding: '0.5rem 1rem',
                  borderRadius: '8px',
                  border: 'none',
                  background: isListening ? 'var(--accent-rose, #f43f5e)' : 'rgba(255,255,255,0.1)',
                  color: '#fff',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  transition: 'background 0.2s',
                  boxShadow: isListening ? '0 0 10px var(--accent-rose)' : 'none'
                }}
              >
                <Mic size={18} />
                {isListening ? 'Listening...' : 'Hold'}
              </button>
              <form
                style={{ display: 'flex', gap: '0.5rem', flex: 1 }}
              onSubmit={(e) => {
                e.preventDefault();
                initAudioAnalyzer();
                const input = e.target.elements.textInput;
                const text = input.value.trim();
                if (!text) return;
                addLog(`You: "${text}"`, 'system');
                setSubtitle(`You: "${text}"`);
                setSentenceChunks([]);
                setCompanionState('thinking');
                sendMessage('text_message', { text });
                input.value = '';
              }}
            >
              <input
                name="textInput"
                type="text"
                placeholder="Type a message and press Enter..."
                style={{
                  flex: 1,
                  padding: '0.5rem 0.85rem',
                  borderRadius: '8px',
                  border: '1px solid rgba(255,255,255,0.15)',
                  background: 'rgba(255,255,255,0.07)',
                  color: '#fff',
                  fontSize: '0.85rem',
                  outline: 'none',
                }}
              />
              <button
                type="submit"
                style={{
                  padding: '0.5rem 1rem',
                  borderRadius: '8px',
                  border: 'none',
                  background: 'var(--accent-emerald, #10b981)',
                  color: '#fff',
                  fontWeight: 600,
                  cursor: 'pointer',
                  fontSize: '0.85rem',
                }}
              >
                Send
              </button>
              </form>
            </div>
          )}
        </section>

        {/* Side Panel: Perception Feed & Terminal Logs */}
        <aside className="side-panel">
          <VideoPreview
            stream={stream}
            isCameraActive={isCameraActive}
            perceptionData={perceptionData}
          />

          <div className="terminal-card">
            <div className="terminal-header">
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <Activity size={14} /> Real-Time Event Log
              </span>
              <span className="metric-pill" style={{ fontSize: '0.65rem' }}>
                {logs.length} events
              </span>
            </div>
            <div className="terminal-logs">
              {logs.length === 0 ? (
                <div className="log-entry">
                  <span className="log-time">--:--:--</span>
                  <span className="log-msg">Waiting for events...</span>
                </div>
              ) : (
                logs.map((log, index) => {
                  const cleanMessage = typeof log.message === 'string'
                    ? log.message.replace(/^AI Companion\s*\([^)]*\):/, 'AI Companion:')
                    : log.message;
                  return (
                    <div key={index} className="log-entry">
                      <span className="log-time">[{log.time}]</span>
                      <span className={`log-msg ${log.type}`}>{cleanMessage}</span>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </aside>
      </main>
    </div>
  );
}
