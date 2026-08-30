import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import gsap from 'gsap'

/**
 * Procedural bullet-style CCTV camera (no external GLTF/GLB asset exists in
 * this project — checked frontend/public and frontend/src; none found), built
 * from grouped primitive meshes so every physical component can be driven
 * independently. A single GSAP timeline (paused, built once) choreographs
 * the disassembly; pointerenter plays it forward, pointerleave reverses it —
 * GSAP timelines interpolate from wherever they currently are, so rapid
 * enter/exit is handled natively without any manual snapping logic.
 */

const METAL = { color: '#3a3a40', metalness: 0.8, roughness: 0.32 }
const METAL_DARK = { color: '#242428', metalness: 0.65, roughness: 0.45 }
const LENS_GLASS = { color: '#05070c', metalness: 0.9, roughness: 0.05 }
const PCB_GREEN = { color: '#0f4a2e', metalness: 0.1, roughness: 0.8 }
const CHIP_BLACK = { color: '#141416', metalness: 0.3, roughness: 0.6 }
const SILVER = { color: '#dcdee1', metalness: 0.9, roughness: 0.2 }
const IR_RED = { color: '#3a1212', emissive: '#a01d1d', emissiveIntensity: 0.6, metalness: 0.4, roughness: 0.5 }
/** Base 3/4-angle pose for the rig, before the tiny idle sine-wave wobble is added on top each frame. */
const BASE_ROTATION: [number, number, number] = [-0.14, 1.25, 0]

export interface CCTVHandle {
  play: () => void
  reverse: () => void
  toggle: () => void
}

function Screw({ position }: { position: [number, number, number] }) {
  return (
    <mesh position={position} castShadow>
      <cylinderGeometry args={[0.045, 0.045, 0.07, 6]} />
      <meshStandardMaterial {...SILVER} />
    </mesh>
  )
}

function IRLed({ angle, radius }: { angle: number; radius: number }) {
  const x = Math.cos(angle) * radius
  const y = Math.sin(angle) * radius
  return (
    <mesh position={[x, y, 0]} rotation={[Math.PI / 2, 0, 0]}>
      <cylinderGeometry args={[0.038, 0.038, 0.05, 8]} />
      <meshStandardMaterial {...IR_RED} />
    </mesh>
  )
}

function CCTVModel({
  compact,
  onReady,
}: {
  compact: boolean
  onReady: (refs: Record<string, THREE.Object3D | null>) => void
}) {
  const idleGroup = useRef<THREE.Group>(null)
  const assembly = useRef<THREE.Group>(null)
  const housingFront = useRef<THREE.Group>(null)
  const housingRear = useRef<THREE.Group>(null)
  const lens = useRef<THREE.Group>(null)
  const irArray = useRef<THREE.Group>(null)
  const imageSensor = useRef<THREE.Group>(null)
  const processorBoard = useRef<THREE.Group>(null)
  const storageModule = useRef<THREE.Group>(null)
  const powerModule = useRef<THREE.Group>(null)
  const networkModule = useRef<THREE.Group>(null)
  const connectors = useRef<THREE.Group>(null)
  const recLed = useRef<THREE.Mesh>(null)

  const irAngles = useMemo(() => Array.from({ length: 10 }, (_, i) => (i / 10) * Math.PI * 2), [])
  const screwPositions = useMemo<[number, number, number][]>(
    () => [
      [0.52, 0, 0.98],
      [-0.52, 0, 0.98],
      [0, 0.52, 0.98],
      [0, -0.52, 0.98],
      [0.5, 0.15, -0.95],
      [-0.5, -0.15, -0.95],
    ],
    [],
  )

  useEffect(() => {
    onReady({
      idleGroup: idleGroup.current,
      assembly: assembly.current,
      housingFront: housingFront.current,
      housingRear: housingRear.current,
      lens: lens.current,
      irArray: irArray.current,
      imageSensor: imageSensor.current,
      processorBoard: processorBoard.current,
      storageModule: storageModule.current,
      powerModule: powerModule.current,
      networkModule: networkModule.current,
      connectors: connectors.current,
    })
  }, [])

  useFrame((state) => {
    const t = state.clock.elapsedTime
    if (idleGroup.current) {
      idleGroup.current.rotation.y = BASE_ROTATION[1] + Math.sin(t * 0.15) * 0.045
      idleGroup.current.rotation.x = BASE_ROTATION[0] + Math.sin(t * 0.11) * 0.02
    }
    if (lens.current) {
      const breathe = 1 + Math.sin(t * 0.8) * 0.015
      lens.current.scale.set(breathe, breathe, 1)
    }
    if (recLed.current) {
      const mat = recLed.current.material as THREE.MeshStandardMaterial
      mat.emissiveIntensity = 0.6 + Math.sin(t * 3.2) * 0.4
    }
  })

  const scale = compact ? 0.72 : 1

  return (
    <group ref={idleGroup} scale={scale} rotation={BASE_ROTATION}>
      {/* Mount bracket — fixed, does not explode */}
      <group position={[0, -0.95, -0.3]}>
        <mesh castShadow>
          <boxGeometry args={[0.18, 0.5, 0.18]} />
          <meshStandardMaterial {...METAL_DARK} />
        </mesh>
        <mesh position={[0, -0.32, 0.05]}>
          <boxGeometry args={[0.4, 0.08, 0.4]} />
          <meshStandardMaterial {...METAL_DARK} />
        </mesh>
        <mesh position={[0, 0.22, 0.28]}>
          <boxGeometry args={[0.16, 0.16, 0.5]} />
          <meshStandardMaterial {...METAL_DARK} />
        </mesh>
      </group>

      <group ref={assembly}>
        {/* Main housing body (static core tube) */}
        <mesh rotation={[Math.PI / 2, 0, 0]} castShadow receiveShadow>
          <cylinderGeometry args={[0.55, 0.55, 1.7, 28]} />
          <meshStandardMaterial {...METAL} />
        </mesh>
        {/* recording indicator */}
        <mesh ref={recLed} position={[0.35, 0.4, 0.75]}>
          <sphereGeometry args={[0.035, 8, 8]} />
          <meshStandardMaterial color="#3a0a0a" emissive="#ff2020" emissiveIntensity={0.6} />
        </mesh>

        {/* Front housing: cap ring + sun visor */}
        <group ref={housingFront} position={[0, 0, 0]}>
          <mesh position={[0, 0, 1.0]} castShadow>
            <cylinderGeometry args={[0.6, 0.58, 0.22, 28]} />
            <meshStandardMaterial {...METAL} />
          </mesh>
          <mesh position={[0, 0.35, 0.75]} rotation={[0.5, 0, 0]}>
            <cylinderGeometry args={[0.65, 0.65, 0.55, 20, 1, false, Math.PI * 0.15, Math.PI * 0.7]} />
            <meshStandardMaterial {...METAL_DARK} side={THREE.DoubleSide} />
          </mesh>
          {Array.from({ length: 4 }).map((_, i) => (
            <Screw key={i} position={screwPositions[i]} />
          ))}
        </group>

        {/* Rear housing: end cap + cable gland */}
        <group ref={housingRear} position={[0, 0, 0]}>
          <mesh position={[0, 0, -0.95]} castShadow>
            <cylinderGeometry args={[0.57, 0.57, 0.18, 28]} />
            <meshStandardMaterial {...METAL} />
          </mesh>
          <mesh position={[0, -0.15, -1.15]} rotation={[Math.PI / 2, 0, 0]}>
            <cylinderGeometry args={[0.09, 0.1, 0.35, 12]} />
            <meshStandardMaterial {...METAL_DARK} />
          </mesh>
          <Screw position={screwPositions[4]} />
          <Screw position={screwPositions[5]} />
        </group>

        {/* Lens assembly */}
        <group ref={lens} position={[0, 0, 1.05]}>
          <mesh rotation={[Math.PI / 2, 0, 0]} castShadow>
            <cylinderGeometry args={[0.34, 0.38, 0.35, 24]} />
            <meshStandardMaterial {...METAL_DARK} />
          </mesh>
          <mesh position={[0, 0, 0.2]} rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[0.33, 0.025, 8, 24]} />
            <meshStandardMaterial {...SILVER} />
          </mesh>
          <mesh position={[0, 0, 0.22]} rotation={[Math.PI / 2, 0, 0]}>
            <cylinderGeometry args={[0.28, 0.28, 0.05, 24]} />
            <meshStandardMaterial {...LENS_GLASS} />
          </mesh>
        </group>

        {/* IR illumination ring */}
        <group ref={irArray} position={[0, 0, 1.02]}>
          {irAngles.map((a, i) => (
            <IRLed key={i} angle={a} radius={0.45} />
          ))}
        </group>

        {/* Image sensor */}
        <group ref={imageSensor} position={[0, 0, 0.65]}>
          <mesh>
            <boxGeometry args={[0.32, 0.32, 0.04]} />
            <meshStandardMaterial {...PCB_GREEN} />
          </mesh>
          <mesh position={[0, 0, 0.03]}>
            <boxGeometry args={[0.16, 0.16, 0.03]} />
            <meshStandardMaterial {...CHIP_BLACK} />
          </mesh>
        </group>

        {/* Processor board */}
        <group ref={processorBoard} position={[0, 0, -0.1]}>
          <mesh>
            <boxGeometry args={[0.85, 0.55, 0.05]} />
            <meshStandardMaterial {...PCB_GREEN} />
          </mesh>
          <mesh position={[-0.2, 0.08, 0.045]}>
            <boxGeometry args={[0.22, 0.22, 0.05]} />
            <meshStandardMaterial {...CHIP_BLACK} />
          </mesh>
          <mesh position={[0.18, -0.1, 0.045]}>
            <boxGeometry args={[0.16, 0.12, 0.04]} />
            <meshStandardMaterial {...CHIP_BLACK} />
          </mesh>
          <group ref={connectors} position={[0, -0.3, 0]}>
            <mesh rotation={[Math.PI / 2, 0, 0]}>
              <cylinderGeometry args={[0.025, 0.025, 0.28, 8]} />
              <meshStandardMaterial {...SILVER} />
            </mesh>
          </group>
        </group>

        {/* Storage module */}
        <group ref={storageModule} position={[0, 0, -0.3]}>
          <mesh>
            <boxGeometry args={[0.24, 0.16, 0.03]} />
            <meshStandardMaterial {...CHIP_BLACK} />
          </mesh>
          <mesh position={[0, 0, 0.02]}>
            <boxGeometry args={[0.16, 0.09, 0.01]} />
            <meshStandardMaterial {...SILVER} />
          </mesh>
        </group>

        {/* Power module */}
        <group ref={powerModule} position={[0, 0, -0.35]}>
          <mesh rotation={[Math.PI / 2, 0, 0]}>
            <cylinderGeometry args={[0.11, 0.11, 0.32, 16]} />
            <meshStandardMaterial {...METAL_DARK} />
          </mesh>
          <mesh position={[0, 0, 0.17]} rotation={[Math.PI / 2, 0, 0]}>
            <cylinderGeometry args={[0.11, 0.11, 0.02, 16]} />
            <meshStandardMaterial {...SILVER} />
          </mesh>
        </group>

        {/* Network / connector interface */}
        <group ref={networkModule} position={[0, -0.15, -0.85]}>
          <mesh>
            <boxGeometry args={[0.32, 0.2, 0.16]} />
            <meshStandardMaterial {...CHIP_BLACK} />
          </mesh>
          <mesh position={[0, 0, -0.09]}>
            <boxGeometry args={[0.24, 0.14, 0.04]} />
            <meshStandardMaterial {...METAL_DARK} />
          </mesh>
        </group>
      </group>
    </group>
  )
}

function Rig({
  compact,
  onProgress,
  handleRef,
  onTimelineReady,
}: {
  compact: boolean
  onProgress: (p: number) => void
  handleRef: React.MutableRefObject<CCTVHandle | null>
  onTimelineReady?: () => void
}) {
  const timeline = useRef<gsap.core.Timeline | null>(null)
  const refsRef = useRef<Record<string, THREE.Object3D | null>>({})
  const onProgressRef = useRef(onProgress)
  onProgressRef.current = onProgress
  const [ready, setReady] = useState(false)

  function handleReady(refs: Record<string, THREE.Object3D | null>) {
    refsRef.current = refs
    setReady(true)
  }

  useLayoutEffect(() => {
    if (!ready) return
    const r = refsRef.current
    const spread = compact ? 0.55 : 1

    const tl = gsap.timeline({
      paused: true,
      defaults: { ease: 'power2.out', duration: 0.6 },
      onUpdate: () => onProgressRef.current(tl.progress()),
    })

    if (r.assembly) tl.to(r.assembly.rotation, { y: 0.35, duration: 1.4, ease: 'power1.inOut' }, 0)

    if (r.housingFront) tl.to(r.housingFront.position, { z: 0.55 * spread, y: 0.1 * spread }, 0)
    if (r.housingRear) tl.to(r.housingRear.position, { z: -0.5 * spread }, 0.05)

    if (r.lens) tl.to(r.lens.position, { z: 1.35 * spread }, 0.15)
    if (r.irArray) tl.to(r.irArray.position, { z: 1.55 * spread }, 0.22)
    if (r.irArray) tl.to(r.irArray.scale, { x: 1.3, y: 1.3 }, 0.22)

    if (r.imageSensor) tl.to(r.imageSensor.position, { z: 0.55 * spread, y: -0.35 * spread }, 0.32)

    if (r.processorBoard) tl.to(r.processorBoard.position, { z: -1.5 * spread, y: 0.45 * spread }, 0.42)
    if (r.processorBoard) tl.to(r.processorBoard.rotation, { y: -0.15 }, 0.42)

    if (r.storageModule) tl.to(r.storageModule.position, { z: -1.85 * spread, x: 0.85 * spread, y: 0.1 * spread }, 0.52)
    if (r.powerModule) tl.to(r.powerModule.position, { z: -1.95 * spread, x: -0.85 * spread, y: 0.1 * spread }, 0.6)
    if (r.networkModule) tl.to(r.networkModule.position, { z: -2.5 * spread, y: -0.55 * spread }, 0.68)
    if (r.connectors) tl.to(r.connectors.position, { z: -0.55 * spread }, 0.55)
    if (r.connectors) tl.to(r.connectors.scale, { y: 2.4 }, 0.55)

    timeline.current = tl
    handleRef.current = {
      play: () => tl.play(),
      reverse: () => tl.reverse(),
      toggle: () => (tl.progress() < 0.5 ? tl.play() : tl.reverse()),
    }
    onTimelineReady?.()

    return () => {
      tl.kill()
    }
  }, [ready, compact])

  return <CCTVModel compact={compact} onReady={handleReady} />
}

function hasWebGL(): boolean {
  try {
    const canvas = document.createElement('canvas')
    return !!(canvas.getContext('webgl2') || canvas.getContext('webgl'))
  } catch {
    return false
  }
}

export function CCTVScene({
  onProgress,
  handleRef,
  onReady,
}: {
  onProgress: (p: number) => void
  handleRef: React.MutableRefObject<CCTVHandle | null>
  onReady?: () => void
}) {
  const [supported, setSupported] = useState(true)
  const [compact, setCompact] = useState(false)
  const [size, setSize] = useState<{ width: number; height: number } | null>(null)
  const wrapperRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setSupported(hasWebGL())
    setCompact(window.innerWidth < 768)
  }, [])

  // Measure the container synchronously (via layout, not ResizeObserver) and
  // pass explicit dimensions to Canvas — browsers defer ResizeObserver
  // callbacks for backgrounded/hidden tabs, which would otherwise leave the
  // canvas stuck at its default 300x150 size until the tab is foregrounded.
  useLayoutEffect(() => {
    function measure() {
      const rect = wrapperRef.current?.getBoundingClientRect()
      if (rect && rect.width > 0 && rect.height > 0) {
        setSize({ width: rect.width, height: rect.height })
      }
    }
    measure()
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [])

  if (!supported) {
    return (
      <div className="flex h-full w-full items-center justify-center">
        <div className="h-48 w-48 rounded-full border border-white/15 bg-[radial-gradient(circle,rgba(0,0,0,0.3),transparent_70%)]" />
      </div>
    )
  }

  return (
    <div ref={wrapperRef} className="h-full w-full">
      {size && (
        <Canvas
          dpr={[1, 1.8]}
          gl={{ antialias: true, alpha: true, powerPreference: 'low-power' }}
          camera={{ fov: 38, position: [0, 0, 7.2] }}
          resize={{ scroll: false }}
          {...{ size: { ...size, top: 0, left: 0 } }}
        >
          {/* key light — soft white, upper-front-left */}
          <directionalLight position={[3.5, 4, 6]} intensity={3.2} color="#fff4e8" />
          {/* fill light — dim, opposite side, keeps shadows from going pure black */}
          <directionalLight position={[-4, -1, 3]} intensity={0.7} color="#ffe8e0" />
          {/* rim light — behind the subject, separates its silhouette from the red field */}
          <pointLight position={[-2, 2, -4]} intensity={30} color="#ffffff" />
          {/* subtle red environmental bounce, matching the landing backdrop */}
          <pointLight position={[0, -2.5, 2]} intensity={14} color="#ff3b30" />
          <ambientLight intensity={0.32} color="#4a2020" />

          <Rig compact={compact} onProgress={onProgress} handleRef={handleRef} onTimelineReady={onReady} />
        </Canvas>
      )}
    </div>
  )
}
