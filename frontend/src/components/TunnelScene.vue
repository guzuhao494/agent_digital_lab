<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
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
let supportGroup;
let staticGroup;
const tunnelLength = 10;

function mapChainage(chainage, interval) {
  const safeInterval = interval || { chainage_start: chainage - 50, chainage_end: chainage + 80 };
  const start = safeInterval.chainage_start - 60;
  const end = safeInterval.chainage_end + 60;
  return ((chainage - start) / (end - start) - 0.5) * tunnelLength;
}

const output = computed(() => props.result.closed_loop_output || {});
const riskInterval = computed(() => output.value.risk_interval || output.value.risk_position || {});
const bestScenario = computed(() => props.result.agents?.experiment_agent?.best_scenario || {});
const activeStructures = computed(() => props.result.state_snapshot?.geology_features?.active_structures || []);
const highEnergyEvents = computed(() => {
  const events = props.result.state?.microseismic?.events || [];
  return [...events].sort((a, b) => b.energy - a.energy).slice(0, 3);
});
const riskTone = computed(() => {
  const level = output.value.risk_level || output.value.final_risk_level;
  if (level === '严重' || level === '高') return '高风险';
  if (level === '关注') return '关注';
  return '低风险';
});

function buildScene() {
  const canvas = canvasRef.value;
  scene = new THREE.Scene();
  scene.background = new THREE.Color('#eef3f4');
  scene.fog = new THREE.Fog('#eef3f4', 9, 18);
  camera = new THREE.PerspectiveCamera(40, canvas.clientWidth / canvas.clientHeight, 0.1, 100);
  camera.position.set(5.6, 4.4, 6.8);
  camera.lookAt(0, 0, 0);

  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(canvas.clientWidth, canvas.clientHeight, false);

  const ambient = new THREE.AmbientLight('#ffffff', 1.55);
  const key = new THREE.DirectionalLight('#ffffff', 2.4);
  key.position.set(3, 5, 4);
  const rim = new THREE.DirectionalLight('#bfe3df', 1.2);
  rim.position.set(-4, 2, -4);
  scene.add(ambient, key, rim);

  staticGroup = new THREE.Group();
  scene.add(staticGroup);

  const grid = new THREE.GridHelper(12, 12, '#b8c6ca', '#d6dee1');
  grid.position.y = -2.24;
  staticGroup.add(grid);

  const tunnel = new THREE.Mesh(
    new THREE.CylinderGeometry(2.05, 2.05, tunnelLength, 80, 1, true),
    new THREE.MeshStandardMaterial({
      color: '#cfdadd',
      metalness: 0.08,
      roughness: 0.74,
      transparent: true,
      opacity: 0.48,
      side: THREE.DoubleSide,
    }),
  );
  tunnel.rotation.z = Math.PI / 2;
  staticGroup.add(tunnel);

  const liningMaterial = new THREE.MeshStandardMaterial({ color: '#728089', roughness: 0.62 });
  for (let index = 0; index <= 10; index += 1) {
    const ring = new THREE.Mesh(new THREE.TorusGeometry(2.07, 0.018, 8, 72), liningMaterial);
    ring.rotation.y = Math.PI / 2;
    ring.position.x = -tunnelLength / 2 + index;
    staticGroup.add(ring);
  }

  const axis = new THREE.Mesh(
    new THREE.BoxGeometry(tunnelLength, 0.025, 0.025),
    new THREE.MeshStandardMaterial({ color: '#3f4a50' }),
  );
  staticGroup.add(axis);

  riskGroup = new THREE.Group();
  microGroup = new THREE.Group();
  structureGroup = new THREE.Group();
  supportGroup = new THREE.Group();
  scene.add(riskGroup, microGroup, structureGroup, supportGroup);
  updateSceneObjects();
  animate();
}

function disposeObject(child) {
  child.geometry?.dispose();
  if (Array.isArray(child.material)) {
    child.material.forEach((material) => material.dispose?.());
  } else {
    child.material?.dispose();
  }
}

function clearGroup(group) {
  while (group.children.length) {
    const child = group.children.pop();
    disposeObject(child);
  }
}

function updateSceneObjects() {
  if (!riskGroup || !microGroup || !structureGroup || !supportGroup || !props.result) return;
  clearGroup(riskGroup);
  clearGroup(microGroup);
  clearGroup(structureGroup);
  clearGroup(supportGroup);

  const output = props.result.closed_loop_output;
  const interval = output.risk_interval;
  const riskCenter = (interval.chainage_start + interval.chainage_end) / 2;
  const riskX = mapChainage(riskCenter, interval);
  const riskColor = output.risk_level === '严重' || output.risk_level === '高' ? '#b42318' : '#d6a400';
  const riskWidth = Math.max(0.8, (interval.chainage_end - interval.chainage_start) / 32);

  const riskVolume = new THREE.Mesh(
    new THREE.CylinderGeometry(2.12, 2.12, riskWidth, 64, 1, true),
    new THREE.MeshStandardMaterial({
      color: riskColor,
      emissive: riskColor,
      emissiveIntensity: 0.08,
      transparent: true,
      opacity: 0.18,
      side: THREE.DoubleSide,
    }),
  );
  riskVolume.rotation.z = Math.PI / 2;
  riskVolume.position.x = riskX;
  riskVolume.userData.phase = 0.2;
  riskGroup.add(riskVolume);

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

  const supportStart = interval.chainage_start - 12;
  const supportEnd = interval.chainage_start + 42;
  const supportCenter = mapChainage((supportStart + supportEnd) / 2, interval);
  const support = new THREE.Mesh(
    new THREE.BoxGeometry(Math.max(0.7, (supportEnd - supportStart) / 45), 0.1, 4.45),
    new THREE.MeshStandardMaterial({
      color: '#0f766e',
      emissive: '#0f766e',
      emissiveIntensity: 0.12,
      transparent: true,
      opacity: 0.38,
    }),
  );
  support.position.set(supportCenter, -2.18, 0);
  support.userData.phase = 0.6;
  supportGroup.add(support);

  const face = new THREE.Mesh(
    new THREE.CylinderGeometry(2.03, 2.03, 0.08, 64),
    new THREE.MeshStandardMaterial({ color: '#263238', transparent: true, opacity: 0.34 }),
  );
  face.rotation.z = Math.PI / 2;
  face.position.x = mapChainage(props.result.state_snapshot.chainage, interval);
  supportGroup.add(face);

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
    if (event.energy > 50000) {
      const halo = new THREE.Mesh(
        new THREE.SphereGeometry(Math.max(0.11, Math.log10(event.energy) * 0.034), 20, 20),
        new THREE.MeshBasicMaterial({ color: '#b42318', transparent: true, opacity: 0.16 }),
      );
      halo.position.copy(sphere.position);
      halo.userData.phase = Math.log10(event.energy);
      microGroup.add(halo);
    }
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
  supportGroup.children.forEach((item) => {
    if (item.material?.opacity && Number.isFinite(item.userData.phase)) {
      item.material.opacity = 0.28 + Math.sin(time * 1.5 + item.userData.phase) * 0.05;
    }
  });
  structureGroup.children.forEach((plane) => {
    plane.material.opacity = 0.54 + Math.sin(time * 1.8 + plane.userData.phase) * 0.08;
  });
  microGroup.children.forEach((item) => {
    if (item.material?.opacity && item.userData.phase) {
      item.material.opacity = 0.12 + Math.sin(time * 2.2 + item.userData.phase) * 0.04;
    }
  });
  microGroup.rotation.x = Math.sin(time * 0.42) * 0.035;
  staticGroup.rotation.x = Math.sin(time * 0.18) * 0.008;
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
    <div class="tunnel-stage">
      <canvas ref="canvasRef" class="tunnel-canvas" aria-label="三维隧道风险场景"></canvas>
      <div class="scene-overlay">
        <div>
          <span>风险区段</span>
          <strong>{{ riskInterval.label }}</strong>
        </div>
        <div>
          <span>场景判别</span>
          <strong>{{ riskTone }}</strong>
        </div>
        <div>
          <span>最优分支</span>
          <strong>{{ bestScenario.name || '待推演' }}</strong>
        </div>
      </div>
      <div class="scene-legend">
        <span><i class="legend-risk"></i>风险热区</span>
        <span><i class="legend-support"></i>推荐处置区</span>
        <span><i class="legend-micro"></i>微震点云</span>
        <span><i class="legend-structure"></i>地质构造</span>
      </div>
    </div>
    <div class="scene-data">
      <article>
        <span>高能微震</span>
        <strong>{{ highEnergyEvents.length }} 个</strong>
        <p v-for="event in highEnergyEvents" :key="event.timestamp">K{{ Math.round(event.x) }}，{{ Number(event.energy).toExponential(2) }} J，{{ event.mechanism }}</p>
      </article>
      <article>
        <span>命中构造</span>
        <strong>{{ activeStructures.length }} 组</strong>
        <p v-for="item in activeStructures" :key="`${item.type}-${item.chainage_start}`">{{ item.type }} K{{ Math.round(item.chainage_start) }}-K{{ Math.round(item.chainage_end) }}，倾角 {{ item.dip }}°</p>
      </article>
    </div>
  </section>
</template>
