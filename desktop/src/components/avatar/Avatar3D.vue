<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import type { AssistantState } from '../../services/backend'

const props = defineProps<{
  state: AssistantState
  assistantName: string
}>()

const host = ref<HTMLDivElement>()
const loading = ref(true)
const failed = ref(false)
let renderer: THREE.WebGLRenderer | undefined
let camera: THREE.PerspectiveCamera | undefined
let scene: THREE.Scene | undefined
let avatar: THREE.Group | undefined
let frame = 0
let observer: ResizeObserver | undefined
let elapsed = 0
let currentState: AssistantState = props.state

watch(() => props.state, (value) => {
  currentState = value
})

function disposeMaterial(material: THREE.Material): void {
  for (const value of Object.values(material)) {
    if (value instanceof THREE.Texture) value.dispose()
  }
  material.dispose()
}

function fitAvatar(model: THREE.Group): void {
  const bounds = new THREE.Box3().setFromObject(model)
  const size = bounds.getSize(new THREE.Vector3())
  const center = bounds.getCenter(new THREE.Vector3())
  const upperBodyHeight = Math.max(size.y * 0.43, 0.001)
  const upperBodyCenterY = bounds.max.y - upperBodyHeight / 2
  const scale = 2.12 / upperBodyHeight
  model.scale.setScalar(scale)
  model.position.set(-center.x * scale, -upperBodyCenterY * scale - 0.08, -center.z * scale)
}

function resize(): void {
  if (!host.value || !renderer || !camera) return
  const width = Math.max(host.value.clientWidth, 1)
  const height = Math.max(host.value.clientHeight, 1)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(width, height, false)
  camera.aspect = width / height
  camera.updateProjectionMatrix()
}

function animate(): void {
  frame = requestAnimationFrame(animate)
  elapsed += 1 / 60
  if (avatar) {
    let speed = 1
    let amplitude = 0.018
    let turn = 0.025
    if (currentState === 'listening') {
      speed = 1.6
      amplitude = 0.026
      avatar.rotation.x = THREE.MathUtils.lerp(avatar.rotation.x, -0.035, 0.08)
    } else if (currentState === 'processing' || currentState === 'transcribing') {
      speed = 2
      amplitude = 0.02
      turn = 0.09
      avatar.rotation.x = THREE.MathUtils.lerp(avatar.rotation.x, 0.025, 0.06)
    } else if (currentState === 'speaking') {
      speed = 3.2
      amplitude = 0.035
      turn = 0.045
      avatar.rotation.x = THREE.MathUtils.lerp(avatar.rotation.x, -0.012, 0.1)
    } else {
      avatar.rotation.x = THREE.MathUtils.lerp(avatar.rotation.x, 0, 0.06)
    }
    avatar.position.y = Math.sin(elapsed * speed) * amplitude
    avatar.rotation.y = Math.sin(elapsed * speed * 0.55) * turn
    avatar.rotation.z = Math.sin(elapsed * speed * 0.35) * 0.008
  }
  renderer?.render(scene!, camera!)
}

onMounted(() => {
  if (!host.value) return
  scene = new THREE.Scene()
  camera = new THREE.PerspectiveCamera(32, 1, 0.01, 100)
  camera.position.set(0, 0.05, 4.35)
  camera.lookAt(0, 0, 0)

  renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true })
  renderer.setClearColor(0x000000, 0)
  renderer.outputColorSpace = THREE.SRGBColorSpace
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  host.value.appendChild(renderer.domElement)

  scene.add(new THREE.HemisphereLight(0xdce7ff, 0x22253b, 2.4))
  const keyLight = new THREE.DirectionalLight(0xffffff, 2.6)
  keyLight.position.set(2.5, 3.5, 4)
  scene.add(keyLight)

  new GLTFLoader().load(
    `/models/assistant.glb?v=${Date.now()}`,
    (gltf) => {
      fitAvatar(gltf.scene)
      avatar = new THREE.Group()
      avatar.add(gltf.scene)
      scene?.add(avatar)
      loading.value = false
      animate()
    },
    undefined,
    () => {
      loading.value = false
      failed.value = true
    }
  )

  observer = new ResizeObserver(resize)
  observer.observe(host.value)
  resize()
})

onBeforeUnmount(() => {
  cancelAnimationFrame(frame)
  observer?.disconnect()
  avatar?.traverse((object) => {
    if (!(object instanceof THREE.Mesh)) return
    object.geometry.dispose()
    const materials = Array.isArray(object.material) ? object.material : [object.material]
    materials.forEach(disposeMaterial)
  })
  renderer?.dispose()
  renderer?.domElement.remove()
})
</script>

<template>
  <div ref="host" class="avatar-3d" :class="state" :aria-label="`Avatar de ${assistantName}`">
    <div v-if="loading || failed" class="orb-container" aria-hidden="true">
      <div class="orb"><div class="orb-core"></div></div>
    </div>
  </div>
</template>

<style scoped>
.avatar-3d {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: transparent;
  transition: filter .2s ease;
}
.avatar-3d :deep(canvas) { display: block; width: 100%; height: 100%; }
.orb-container {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  pointer-events: none;
}
.orb {
  --orb-color: #9c91ff;
  --orb-speed: 3.2s;
  position: relative;
  width: clamp(100px, 38%, 170px);
  aspect-ratio: 1;
  border: 2px solid var(--orb-color);
  border-radius: 50%;
  box-shadow: 0 0 28px color-mix(in srgb, var(--orb-color) 45%, transparent), inset 0 0 28px color-mix(in srgb, var(--orb-color) 25%, transparent);
  animation: orb-breathe var(--orb-speed) ease-in-out infinite;
}
.orb::before, .orb::after { content: ''; position: absolute; border-radius: 50%; }
.orb::before {
  inset: -12px;
  border: 2px solid transparent;
  border-top-color: var(--orb-color);
  border-bottom-color: var(--orb-color);
  animation: orb-spin 7s linear infinite;
}
.orb::after { inset: 15%; background: radial-gradient(circle, var(--orb-color), transparent 70%); opacity: .45; }
.orb-core { position: absolute; inset: 35%; border-radius: 50%; background: #eef0ff; box-shadow: 0 0 24px var(--orb-color); }
.listening .orb { --orb-color: #52e0a1; --orb-speed: 1.5s; }
.processing .orb, .transcribing .orb { --orb-color: #b493ff; --orb-speed: 1s; }
.processing .orb::before, .transcribing .orb::before { animation-duration: 1.3s; }
.speaking .orb { --orb-color: #58c7ff; --orb-speed: .65s; }
.disconnected .orb, .dormant .orb { --orb-color: #8c92a9; opacity: .6; }
@keyframes orb-breathe { 0%, 100% { transform: scale(.94); } 50% { transform: scale(1.06); } }
@keyframes orb-spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .orb, .orb::before { animation: none; } }
.avatar-3d.listening { filter: drop-shadow(0 0 18px #52e0a142); }
.avatar-3d.processing,
.avatar-3d.transcribing { filter: drop-shadow(0 0 18px #7658d64d); }
.avatar-3d.speaking { filter: drop-shadow(0 0 20px #3999d65c); }
</style>
