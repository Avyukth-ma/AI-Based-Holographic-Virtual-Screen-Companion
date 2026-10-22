import React, { useRef, useMemo } from 'react';
import { Canvas, useFrame, useLoader } from '@react-three/fiber';
import * as THREE from 'three';

// Futuristic JARVIS Holographic Particle Cloud
function JarvisTelemetryParticles({ count = 90, state }) {
  const pointsRef = useRef();

  const particleColor = useMemo(() => {
    switch (state) {
      case 'speaking': return new THREE.Color('#38bdf8'); // High-Energy Stark Cyan/Blue
      case 'thinking': return new THREE.Color('#f59e0b'); // Processing Gold/Amber
      case 'affirmation': return new THREE.Color('#10b981'); // Systems Nominal Green
      case 'sleep': return new THREE.Color('#475569'); // Standby Slate
      case 'error': return new THREE.Color('#ef4444'); // System Alert Crimson
      default: return new THREE.Color('#00f2fe'); // Iconic Holographic Arc Cyan
    }
  }, [state]);

  const [positions, speeds] = useMemo(() => {
    const pos = new Float32Array(count * 3);
    const spd = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      const theta = Math.random() * Math.PI * 2;
      const radius = 0.9 + Math.random() * 0.9;
      pos[i * 3] = Math.cos(theta) * radius;
      pos[i * 3 + 1] = Math.sin(theta) * radius;
      pos[i * 3 + 2] = (Math.random() - 0.5) * 0.7;
      spd[i] = 0.4 + Math.random() * 0.9;
    }
    return [pos, spd];
  }, [count]);

  useFrame((stateObj, delta) => {
    if (!pointsRef.current) return;
    const time = stateObj.clock.getElapsedTime();
    const posArr = pointsRef.current.geometry.attributes.position.array;
    const speedMult = state === 'speaking' ? 2.2 : state === 'thinking' ? 1.6 : 1.0;

    for (let i = 0; i < count; i++) {
      const curX = posArr[i * 3];
      const curY = posArr[i * 3 + 1];
      const angle = delta * speeds[i] * 0.5 * speedMult;
      // Orbit circularly around Arc Reactor core
      posArr[i * 3] = curX * Math.cos(angle) - curY * Math.sin(angle);
      posArr[i * 3 + 1] = curX * Math.sin(angle) + curY * Math.cos(angle);
      posArr[i * 3 + 2] += Math.sin(time + i) * 0.002;
    }
    pointsRef.current.geometry.attributes.position.needsUpdate = true;
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={count}
          array={positions}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.038}
        color={particleColor}
        transparent
        opacity={state === 'sleep' ? 0.2 : 0.85}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}

// Interactive JARVIS Arc Reactor & Holographic Telemetry HUD
function JarvisCoreAvatar({ state, gazeRef, volumeRef }) {
  const groupRef = useRef();
  const outerRingRef = useRef();
  const midRingRef = useRef();
  const innerCoreRef = useRef();

  // Load high-resolution JARVIS Arc Reactor HUD texture
  const texture = useLoader(THREE.TextureLoader, '/jarvis_core.png');
  texture.generateMipmaps = true;
  texture.minFilter = THREE.LinearMipmapLinearFilter;

  // Plane geometry
  const coreGeom = useMemo(() => new THREE.PlaneGeometry(2.5, 2.5), []);

  // Telemetry state accent color
  const stateColor = useMemo(() => {
    switch (state) {
      case 'speaking': return '#38bdf8'; // Vibrant Stark Blue
      case 'thinking': return '#f59e0b'; // Calculation Amber
      case 'affirmation': return '#10b981'; // Systems Verified Green
      case 'sleep': return '#334155'; // Standby Grey
      case 'error': return '#ef4444'; // Red Alert
      default: return '#00f2fe'; // Mark-VII Arc Cyan
    }
  }, [state]);

  useFrame((stateObj, delta) => {
    if (!groupRef.current) return;

    const time = stateObj.clock.getElapsedTime();
    const liveVolume = (volumeRef && typeof volumeRef.current === 'number') ? volumeRef.current : 0;

    // 1. Gaze & Telemetry Parallax Tracking (JARVIS HUD tilts toward user face)
    let gazeX = 0;
    let gazeY = 0;
    if (gazeRef && gazeRef.current) {
      gazeX = typeof gazeRef.current.x === 'number' ? gazeRef.current.x : 0;
      gazeY = typeof gazeRef.current.y === 'number' ? gazeRef.current.y : 0;
    }

    const isSleeping = state === 'sleep';
    const breathRate = isSleeping ? 1.0 : 2.0;
    const idleBreath = Math.sin(time * breathRate) * (isSleeping ? 0.005 : 0.018);

    // Dynamic 3D Gimbal Rotation
    const targetRotY = gazeX * 0.32;
    const targetRotX = -gazeY * 0.22;
    groupRef.current.rotation.y = THREE.MathUtils.lerp(groupRef.current.rotation.y, targetRotY, 0.08);
    groupRef.current.rotation.x = THREE.MathUtils.lerp(groupRef.current.rotation.x, targetRotX, 0.08);

    // Parallax Shift
    const targetPosX = gazeX * 0.1;
    const targetPosY = -gazeY * 0.06;
    groupRef.current.position.x = THREE.MathUtils.lerp(groupRef.current.position.x, targetPosX, 0.08);
    groupRef.current.position.y = THREE.MathUtils.lerp(groupRef.current.position.y, targetPosY, 0.08);

    // 2. Multi-Ring Rotational Dynamics & Speech Reactive Wave
    const rotSpeed = state === 'speaking' ? 1.6 : state === 'thinking' ? 2.5 : 0.6;

    if (outerRingRef.current) {
      outerRingRef.current.rotation.z -= delta * 0.4 * rotSpeed;
    }
    if (midRingRef.current) {
      midRingRef.current.rotation.z += delta * 0.7 * rotSpeed;
    }

    // 3. Audio Amplitude Expansion (Arc Reactor core flares and pulses when JARVIS speaks)
    if (innerCoreRef.current) {
      let targetScale = 1.0 + idleBreath;
      if (state === 'speaking') {
        const speechWave = Math.sin(time * 16) * 0.03;
        targetScale = 1.0 + (liveVolume * 0.18) + speechWave;
      }
      innerCoreRef.current.scale.x = THREE.MathUtils.lerp(innerCoreRef.current.scale.x, targetScale, 0.25);
      innerCoreRef.current.scale.y = THREE.MathUtils.lerp(innerCoreRef.current.scale.y, targetScale, 0.25);
    }
  });

  return (
    <group ref={groupRef} position={[0, 0, 0]}>
      {/* Outer Gyroscopic Ring */}
      <mesh ref={outerRingRef} position={[0, 0, -0.04]}>
        <ringGeometry args={[1.35, 1.42, 64]} />
        <meshBasicMaterial
          color={stateColor}
          transparent
          opacity={state === 'sleep' ? 0.1 : 0.4}
          side={THREE.DoubleSide}
          blending={THREE.AdditiveBlending}
        />
      </mesh>

      {/* Mid Segmented Telemetry Ring */}
      <mesh ref={midRingRef} position={[0, 0, -0.02]}>
        <ringGeometry args={[1.05, 1.12, 48]} />
        <meshBasicMaterial
          color={stateColor}
          transparent
          opacity={state === 'sleep' ? 0.15 : 0.55}
          side={THREE.DoubleSide}
          blending={THREE.AdditiveBlending}
        />
      </mesh>

      {/* Central Interactive Arc Reactor Core HUD */}
      <mesh ref={innerCoreRef} geometry={coreGeom} position={[0, 0, 0]}>
        <meshStandardMaterial
          map={texture}
          transparent
          roughness={0.15}
          metalness={0.1}
          emissive={stateColor}
          emissiveIntensity={state === 'speaking' ? 0.6 : state === 'thinking' ? 0.45 : 0.25}
        />
      </mesh>
    </group>
  );
}

export function Hologram({ state = 'idle', gazeRef, volumeRef }) {
  const getLighting = (s) => {
    switch (s) {
      case 'speaking': return { main: '#38bdf8', intensity: 1.5, ambient: 0.95 };
      case 'thinking': return { main: '#f59e0b', intensity: 1.4, ambient: 0.85 };
      case 'affirmation': return { main: '#10b981', intensity: 1.4, ambient: 0.9 };
      case 'sleep': return { main: '#334155', intensity: 0.35, ambient: 0.3 };
      case 'error': return { main: '#ef4444', intensity: 1.3, ambient: 0.8 };
      default: return { main: '#00f2fe', intensity: 1.35, ambient: 0.9 };
    }
  };

  const lights = getLighting(state);

  const filterShadow = useMemo(() => {
    switch (state) {
      case 'speaking': return 'drop-shadow(0 0 30px rgba(56, 189, 248, 0.55))';
      case 'thinking': return 'drop-shadow(0 0 30px rgba(245, 158, 11, 0.5))';
      case 'affirmation': return 'drop-shadow(0 0 30px rgba(16, 185, 129, 0.5))';
      case 'sleep': return 'drop-shadow(0 0 10px rgba(51, 65, 85, 0.3))';
      default: return 'drop-shadow(0 0 28px rgba(0, 242, 254, 0.45))';
    }
  }, [state]);

  return (
    <div
      className="hologram-container"
      style={{
        width: '100%',
        height: '350px',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        margin: '0.4rem 0',
        position: 'relative',
        filter: filterShadow,
        transition: 'filter 0.4s ease',
      }}
    >
      <Canvas camera={{ position: [0, 0, 3.5], fov: 46 }}>
        <ambientLight intensity={lights.ambient} />
        <directionalLight position={[0, 2, 3]} intensity={lights.intensity} />
        <pointLight position={[0, 0, 1.8]} intensity={1.2} color={lights.main} />

        <JarvisTelemetryParticles state={state} count={90} />
        <React.Suspense fallback={null}>
          <JarvisCoreAvatar state={state} gazeRef={gazeRef} volumeRef={volumeRef} />
        </React.Suspense>
      </Canvas>
    </div>
  );
}
