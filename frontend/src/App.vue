<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import Plotly from 'plotly.js-dist-min';
import TunnelScene from './components/TunnelScene.vue';
import { runLab as requestLab } from './api';

const result = ref(null);
const loading = ref(true);
const error = ref('');
const scenarioChart = ref(null);
const scatterChart = ref(null);
const tbmChart = ref(null);

const closedLoop = computed(() => result.value?.closed_loop_output ?? {});
const state = computed(() => result.value?.state ?? {});
const agents = computed(() => result.value?.agents ?? {});
const stateVector = computed(() => state.value?.state_vector_ordered ?? []);
const agentList = computed(() => [
  agents.value.microseismic,
  agents.value.tbm,
  agents.value.geology,
  agents.value.mechanism,
  agents.value.simulation,
].filter(Boolean));
const levelClass = computed(() => {
  const level = closedLoop.value.risk_level || '低';
  return {
    'level-critical': level === '严重',
    'level-high': level === '高',
    'level-watch': level === '关注',
    'level-low': level === '低',
  };
});

async function loadLab() {
  loading.value = true;
  error.value = '';
  try {
    result.value = await requestLab();
    await nextTick();
    renderCharts();
  } catch (err) {
    error.value = err instanceof Error ? err.message : '实验编排失败';
  } finally {
    loading.value = false;
  }
}

function plotLayout(title, extra = {}) {
  return {
    title: { text: title, font: { size: 15, color: '#101418' } },
    margin: { l: 48, r: 24, t: 46, b: 48 },
    paper_bgcolor: '#ffffff',
    plot_bgcolor: '#ffffff',
    font: { family: 'Inter, system-ui, sans-serif', color: '#263238' },
    xaxis: { gridcolor: '#e6eaed', zerolinecolor: '#cfd7dc' },
    yaxis: { gridcolor: '#e6eaed', zerolinecolor: '#cfd7dc', range: [0, 1] },
    legend: { orientation: 'h', y: -0.28 },
    ...extra,
  };
}

function renderScenarioChart() {
  if (!scenarioChart.value || !agents.value.simulation) return;
  const palette = ['#101418', '#0f766e', '#b42318', '#59636a', '#d6a400'];
  const traces = agents.value.simulation.branches.map((branch, index) => ({
    x: branch.risk_curve.map((point) => point.window),
    y: branch.risk_curve.map((point) => point.risk_score),
    type: 'scatter',
    mode: 'lines+markers',
    name: branch.name,
    line: { color: palette[index % palette.length], width: branch.scenario_key === 'combined_control' ? 4 : 2 },
    marker: { size: 7 },
  }));
  Plotly.react(scenarioChart.value, traces, plotLayout('反事实风险曲线'), { displayModeBar: false, responsive: true });
}

function renderScatterChart() {
  if (!scatterChart.value || !state.value.microseismic) return;
  const events = state.value.microseismic.events;
  const trace = {
    x: events.map((event) => event.x),
    y: events.map((event) => event.y),
    z: events.map((event) => event.z),
    text: events.map((event) => `${event.timestamp}<br>能量 ${event.energy} J<br>${event.mechanism}`),
    mode: 'markers',
    type: 'scatter3d',
    marker: {
      size: events.map((event) => Math.max(4, Math.log10(event.energy) * 2)),
      color: events.map((event) => event.energy),
      colorscale: [
        [0, '#0f766e'],
        [0.55, '#d6a400'],
        [1, '#b42318'],
      ],
      opacity: 0.88,
    },
    name: '微震事件',
  };
  Plotly.react(
    scatterChart.value,
    [trace],
    plotLayout('微震空间散点', {
      scene: {
        xaxis: { title: 'X / 桩号', gridcolor: '#dfe6ea' },
        yaxis: { title: 'Y', gridcolor: '#dfe6ea' },
        zaxis: { title: 'Z', gridcolor: '#dfe6ea' },
        camera: { eye: { x: 1.55, y: 1.25, z: 0.8 } },
      },
      yaxis: undefined,
      xaxis: undefined,
    }),
    { displayModeBar: false, responsive: true },
  );
}

function renderTbmChart() {
  if (!tbmChart.value || !state.value.tbm) return;
  const series = state.value.tbm.series;
  const microEvents = state.value.microseismic.events;
  const traces = [
    {
      x: series.map((item) => item.timestamp),
      y: series.map((item) => item.thrust),
      type: 'scatter',
      mode: 'lines',
      name: '推力 kN',
      line: { color: '#0f766e', width: 3 },
    },
    {
      x: series.map((item) => item.timestamp),
      y: series.map((item) => item.torque),
      type: 'scatter',
      mode: 'lines',
      name: '扭矩 kNm',
      yaxis: 'y2',
      line: { color: '#59636a', width: 3 },
    },
    {
      x: microEvents.map((item) => item.timestamp),
      y: microEvents.map((item) => item.energy),
      type: 'bar',
      name: '微震能量 J',
      yaxis: 'y3',
      marker: { color: '#d6a400', opacity: 0.42 },
    },
  ];
  Plotly.react(
    tbmChart.value,
    traces,
    plotLayout('TBM 与微震能量时序', {
      yaxis: { title: '推力', gridcolor: '#e6eaed' },
      yaxis2: { title: '扭矩', overlaying: 'y', side: 'right', showgrid: false },
      yaxis3: { title: '能量', overlaying: 'y', side: 'right', position: 0.93, showgrid: false },
      legend: { orientation: 'h', y: -0.25 },
    }),
    { displayModeBar: false, responsive: true },
  );
}

function renderCharts() {
  renderScenarioChart();
  renderScatterChart();
  renderTbmChart();
}

function resizeCharts() {
  [scenarioChart.value, scatterChart.value, tbmChart.value].filter(Boolean).forEach((node) => Plotly.Plots.resize(node));
}

watch(result, () => nextTick(renderCharts));
onMounted(() => {
  loadLab();
  window.addEventListener('resize', resizeCharts);
});
onUnmounted(() => window.removeEventListener('resize', resizeCharts));
</script>

<template>
  <div class="shell">
    <header class="topbar">
      <div>
        <p class="system-name">rockburst-agent-lab</p>
        <h1>智能体数字实验室</h1>
      </div>
      <button type="button" class="run-button" :disabled="loading" @click="loadLab">
        {{ loading ? '推演中' : '重新推演' }}
      </button>
    </header>

    <main v-if="result" class="workspace">
      <section class="decision-strip" aria-label="闭环输出">
        <div class="risk-block" :class="levelClass">
          <span>风险等级</span>
          <strong>{{ closedLoop.risk_level }}</strong>
        </div>
        <div>
          <span>风险区段</span>
          <strong>{{ closedLoop.risk_interval.label }}</strong>
        </div>
        <div>
          <span>方案置信度</span>
          <strong>{{ Math.round(closedLoop.plan_confidence * 100) }}%</strong>
        </div>
        <div>
          <span>最优策略</span>
          <strong>{{ closedLoop.best_scenario }}</strong>
        </div>
      </section>

      <section class="primary-grid">
        <TunnelScene :result="result" />

        <section class="panel decision-panel">
          <div class="panel-heading">
            <p>闭环预警</p>
            <h2>{{ closedLoop.risk_score }} 综合风险</h2>
          </div>
          <dl class="mechanism">
            <dt>主导机理路径</dt>
            <dd>{{ closedLoop.dominant_mechanism_path }}</dd>
          </dl>
          <div class="recommendation">
            <h3>处置建议</h3>
            <ul>
              <li v-for="item in closedLoop.recommended_measures" :key="item">{{ item }}</li>
            </ul>
          </div>
          <div class="recommendation">
            <h3>后续补采</h3>
            <ul>
              <li v-for="item in closedLoop.data_to_collect_next" :key="item">{{ item }}</li>
            </ul>
          </div>
        </section>
      </section>

      <section class="chart-grid" aria-label="实验图表">
        <section class="panel chart-panel">
          <div ref="scenarioChart" class="plot"></div>
        </section>
        <section class="panel chart-panel">
          <div ref="scatterChart" class="plot"></div>
        </section>
        <section class="panel chart-panel wide">
          <div ref="tbmChart" class="plot plot-wide"></div>
        </section>
      </section>

      <section class="state-panel panel">
        <div class="panel-heading">
          <p>统一状态构建层</p>
          <h2>岩爆孕育状态向量</h2>
        </div>
        <div class="vector-list">
          <div v-for="item in stateVector" :key="item.name" class="vector-row">
            <span>{{ item.name }}</span>
            <div class="vector-track">
              <i :style="{ width: `${Math.round(item.value * 100)}%` }"></i>
            </div>
            <strong>{{ item.value.toFixed(3) }}</strong>
          </div>
        </div>
      </section>

      <section class="agent-grid" aria-label="专业智能体">
        <article v-for="agent in agentList" :key="agent.agent" class="agent-item">
          <div>
            <span>{{ agent.agent }}</span>
            <strong>{{ agent.level }}</strong>
          </div>
          <p v-for="finding in agent.findings" :key="finding">{{ finding }}</p>
        </article>
      </section>
    </main>

    <main v-else class="loading-state">
      <p v-if="loading">正在编排多智能体实验...</p>
      <p v-else>{{ error }}</p>
      <button v-if="error" type="button" class="run-button" @click="loadLab">重试</button>
    </main>
  </div>
</template>
