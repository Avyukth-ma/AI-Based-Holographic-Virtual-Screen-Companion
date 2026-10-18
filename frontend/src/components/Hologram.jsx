import React, { useRef, useMemo, useEffect } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import * as THREE from 'three';

function HologramModel({ state, gazeRef, volumeRef }) {
  const group = useRef();
  const headRef = useRef();

  const getEmissiveColor = (s) => {
    switch (s) {
      case 'idle': return '#06b6d4'; // Cyan
      case 'thinking': return '#a855f7'; // Purple
      case 'speaking': return '#f59e0b'; // Gold
      case 'sleep': return '#374151'; // Dim Grey
      case 'error': return '#ef4444'; // Red
      case 'affirmation': return '#10b981'; // Emerald Green
      default: return '#06b6d4';
    }
  };

  const sharedMaterial = useMemo(() => new THREE.MeshStandardMaterial({
    transparent: true,
    opacity: 0.9,
    roughness: 0.25,
    metalness: 0.1,
    wireframe: false,
    color: '#000000',
    emissive: new THREE.Color(getEmissiveColor(state)),
    emissiveIntensity: 0.5
  }), []);

  const materialRef = useRef(sharedMaterial);

  useEffect(() => {
    if (materialRef.current) {
      materialRef.current.emissive.set(getEmissiveColor(state));
    }
  }, [state]);

  useEffect(() => {
    return () => {
      sharedMaterial.dispose();
    };
  }, [sharedMaterial]);

  useFrame((_, delta) => {
    if (headRef.current && gazeRef && gazeRef.current) {
      // Lerp the Y rotation (looking left/right)
      headRef.current.rotation.y = THREE.MathUtils.lerp(headRef.current.rotation.y, -gazeRef.current.x * 0.8, 0.1);
      // Lerp the X rotation (looking up/down)
      headRef.current.rotation.x = THREE.MathUtils.lerp(headRef.current.rotation.x, -gazeRef.current.y * 0.5, 0.1);
    }

    if (materialRef.current) {
      if (state === 'speaking') {
        const liveVolume = (volumeRef && typeof volumeRef.current === 'number') ? volumeRef.current : 0;
        const targetIntensity = 0.4 + (liveVolume * 1.5);
        materialRef.current.emissiveIntensity = THREE.MathUtils.lerp(
          materialRef.current.emissiveIntensity,
          targetIntensity,
          0.15
        );
      } else {
        materialRef.current.emissiveIntensity = THREE.MathUtils.lerp(
          materialRef.current.emissiveIntensity,
          0.5,
          0.15
        );
      }
    }
  });

  return (
    <group ref={group} position={[0, -0.65, 0]}>
      {/* Head */}
      <mesh ref={headRef} position={[0, 0.4, 0]} material={materialRef.current}>
        <sphereGeometry args={[0.35, 32, 32]} />
      </mesh>
      
      {/* Neck */}
      <mesh position={[0, -0.05, 0]} material={materialRef.current}>
        <cylinderGeometry args={[0.14, 0.16, 0.35, 32]} />
      </mesh>
      
      {/* Shoulders / Chest */}
      <mesh position={[0, -0.55, 0]} material={materialRef.current}>
        <cylinderGeometry args={[0.55, 0.75, 0.7, 32]} />
      </mesh>
    </group>
  );
}

export function Hologram({ state, gazeRef, volumeRef }) {
  return (
    <div
      className="hologram-container"
      style={{
        width: '100%',
        height: '300px',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        margin: '1rem 0',
        position: 'relative',
      }}
    >
      <Canvas camera={{ position: [0, 0.2, 1.8], fov: 45 }}>
        <ambientLight intensity={0.4} />
        <directionalLight position={[0, 2, 2]} intensity={0.6} />
        <pointLight position={[0, -1, 1]} intensity={2.0} color="#ffffff" />
        
        <HologramModel state={state} gazeRef={gazeRef} volumeRef={volumeRef} />
        
        <OrbitControls enableZoom={false} enablePan={false} enableRotate={false} />
      </Canvas>
    </div>
  );
}
