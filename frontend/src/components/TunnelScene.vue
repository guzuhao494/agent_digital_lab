<script setup>
import { onMounted, onUnmounted, ref, watch } from 'vue';
import * as THREE from 'three';

const props = defineProps({
  result: {
    type: Object,
    required: true,
  },
});

const canvasRef = ref(null);
let renderer;
let scene;
let camera;
let animationFrame = 0;
let riskGroup;
let microGroup;
let structureGroup;
const tunnelLength = 10;

function mapChainage(chainage, interval) {
  const start = interval.chainage_start - 60;
  const end = interval.chainage_end + 60;
  return ((chainage - start) / (end - start) - 0.5) * tunnelLength;
}

function buildScene() {
  const canvas = canvasRef.value;
  scene = new THREE.Scene();
  scene.background = new THREE.Color('#f7f8fb');
  camera = new THREE.PerspectiveCamera(42, canvas.clientWidth / canvas.clientHeight, 0.1, 100);
  camera.position.set(4.8, 4.2, 6.2);
  camera.lookAt(0, 0, 0);

  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(canvas.clientWidth, canvas.clientHeight, false);

  const ambient = new THREE.AmbientLight('#ffffff', 1.8);
  const key = new THREE.DirectionalLight('#ffffff', 2.6);
  key.position.set(3, 5, 4);
  scene.add(ambient, key);

  const tunnel = new THREE.Mesh(
    new THREE.CylinderGeometry(2.05, 2.05, tunnelLength, 80, 1, true),
    new THREE.MeshStandardMaterial({
      color: '#dfe6e8',
      metalness: 0.08,
      roughness: 0.74,
      transparent: true,
      opacity: 0.56,
      side: THREE.DoubleSide,
    }),
  );
  tunnel.rotation.z = Math.PI / 2;
  scene.add(tunnel);

  const axis = new THREE.Mesh(
    new THREE.BoxGeometry(tunnelLength, 0.03, 0.03),
    new THREE.MeshStandardMaterial({ color: '#59636a' }),
  );
  scene.add(axis);

  riskGroup = new THREE.Group();
  microGroup = new THREE.Group();
  structureGroup = new THREE.Group();
  scene.add(riskGroup, microGroup, structureGroup);
  updateSceneObjects();
  animate();
}

function clearGroup(group) {
  while (group.children.length) {
    const child = group.children.pop();
    child.geometry?.dispose();
    child.material?.dispose();
  }
}

function updateSceneObjects() {
  if (!riskGroup || !microGroup || !structureGroup || !props.result) return;
  clearGroup(riskGroup);
  clearGroup(microGroup);
  clearGroup(structureGroup);

  const output = props.result.closed_loop_output;
  const interval = output.risk_interval;
  const riskCenter = (interval.chainage_start + interval.chainage_end) / 2;
  const riskX = mapChainage(riskCenter, interval);
  const riskColor = output.risk_level === '严重' || output.risk_level === '高' ? '#b42318' : '#d6a400';

  for (let index = 0; index < 4; index += 1) {
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(2.18 + index * 0.035, 0.035, 12, 96),
      new THREE.MeshStandardMaterial({ color: riskColor, emissive: riskColor, emissiveIntensity: 0.16 }),
    );
    ring.rotation.y = Math.PI / 2;
    ring.position.x = riskX + (index - 1.5) * 0.34;
    ring.userData.phase = index * 0.55;
    riskGroup.add(ring);
  }

  const events = props.result.state.microseismic.events;
  const material = new THREE.MeshStandardMaterial({ color: '#0f766e', emissive: '#0f766e', emissiveIntensity: 0.18 });
  const hotMaterial = new THREE.MeshStandardMaterial({ color: '#b42318', emissive: '#b42318', emissiveIntensity: 0.2 });
  events.forEach((event) => {
    const sphere = new THREE.Mesh(
      new THREE.SphereGeometry(Math.max(0.045, Math.log10(event.energy) * 0.018), 16, 16),
      event.energy > 50000 ? hotMaterial : material,
    );
    sphere.position.set(
      mapChainage(event.x, interval),
      event.y / 22,
      (event.z + 276) / 18,
    );
    microGroup.add(sphere);
  });

  const structures = props.result.state_snapshot?.geology_features?.active_structures || [];
  structures.forEach((structure) => {
    const center = (structure.chainage_start + structure.chainage_end) / 2;
    const width = Math.max(0.25, (structure.chainage_end - structure.chainage_start) / 55);
    const structureMaterial = new THREE.MeshStandardMaterial({
      color: structure.type === 'fault' ? '#b42318' : '#d6a400',
      emissive: structure.type === 'fault' ? '#b42318' : '#d6a400',
      emissiveIntensity: 0.08,
      transparent: true,
      opacity: 0.62,
      side: THREE.DoubleSide,
    });
    const plane = new THREE.Mesh(new THREE.BoxGeometry(width, 4.2, 0.045), structureMaterial);
    plane.position.x = mapChainage(center, interval);
    plane.rotation.z = THREE.MathUtils.degToRad(90 - (structure.dip || 65));
    plane.userData.phase = structure.risk_weight || 0.3;
    structureGroup.add(plane);
  });
}

function animate() {
  animationFrame = requestAnimationFrame(animate);
  const time = performance.now() * 0.001;
  riskGroup.children.forEach((ring) => {
    const pulse = 1 + Math.sin(time * 2.4 + ring.userData.phase) * 0.025;
    ring.scale.setScalar(pulse);
  });
  structureGroup.children.forEach((plane) => {
    plane.material.opacity = 0.54 + Math.sin(time * 1.8 + plane.userData.phase) * 0.08;
  });
  microGroup.rotation.x = Math.sin(time * 0.45) * 0.04;
  renderer.render(scene, camera);
}

function resize() {
  if (!renderer || !camera || !canvasRef.value) return;
  const canvas = canvasRef.value;
  camera.aspect = canvas.clientWidth / canvas.clientHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(canvas.clientWidth, canvas.clientHeight, false);
}

watch(() => props.result, updateSceneObjects, { deep: true });
onMounted(() => {
  buildScene();
  window.addEventListener('resize', resize);
});
onUnmounted(() => {
  cancelAnimationFrame(animationFrame);
  window.removeEventListener('resize', resize);
  renderer?.dispose();
});
</script>

<template>
  <section class="tunnel-panel panel">
    <div class="panel-heading">
      <p>数字实验室核心层</p>
      <h2>隧道风险场景</h2>
    </div>
    <canvas ref="canvasRef" class="tunnel-canvas" aria-label="三维隧道风险场景"></canvas>
  </section>
</template>
