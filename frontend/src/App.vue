<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import Plotly from 'plotly.js-dist-min';
import TunnelScene from './components/TunnelScene.vue';
import { runLab as requestLab } from './api';

const result = ref(null);
const loading = ref(true);
const error = ref('');
const scenarioCurveChart = ref(null);
const scenarioBarChart = ref(null);
const scatterChart = ref(null);

const closedLoop = computed(() => result.value?.closed_loop_output ?? {});
const snapshot = computed(() => result.value?.state_snapshot ?? {});
const state = computed(() => result.value?.state ?? {});
const agents = computed(() => result.value?.agents ?? {});
const stateVector = computed(() => state.value?.state_vector_ordered ?? []);
const scenarios = computed(() => agents.value.experiment_agent?.experiment_scenarios ?? agents.value.simulation?.branches ?? []);
const bestScenario = computed(() => agents.value.experiment_agent?.best_scenario ?? {});
const agentSummaries = computed(() => [
  {
    title: '微震感知智能体',
    score: agents.value.microseismic_agent?.preliminary_risk_score,
    lines: [
      `活跃度 ${formatScore(agents.value.microseismic_agent?.microseismic_activity)}`,
      `聚集区 ${formatPoint(agents.value.microseismic_agent?.cluster_center)}`,
    ],
  },
  {
    title: '掘进工况智能体',
    score: agents.value.tbm_agent?.disturbance_intensity,
    lines: [
      agents.value.tbm_agent?.condition_label,
      agents.value.tbm_agent?.coupling_hint,
    ],
  },
  {
    title: '地质认知智能体',
    score: agents.value.geology_agent?.score,
    lines: [
      agents.value.geology_agent?.current_geology_summary,
      (agents.value.geology_agent?.structural_risk_tags ?? []).join(' / '),
    ],
  },
  {
    title: '机理匹配智能体',
    score: agents.value.mechanism_agent?.score,
    lines: [
      agents.value.mechanism_agent?.dominant_mechanism,
      agents.value.mechanism_agent?.dominant_path,
    ],
  },
].filter((item) => item.lines.some(Boolean)));
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

function formatScore(value) {
  return Number.isFinite(value) ? value.toFixed(3) : '--';
}

function formatPoint(point) {
  if (!point) return '--';
  return `(${point.x?.toFixed?.(1) ?? point.x}, ${point.y?.toFixed?.(1) ?? point.y}, ${point.z?.toFixed?.(1) ?? point.z})`;
}

function percent(value) {
  return `${Math.round((value ?? 0) * 100)}%`;
}

function plotLayout(title, extra = {}) {
  return {
    title: { text: title, font: { size: 15, color: '#101418' } },
    margin: { l: 46, r: 24, t: 48, b: 48 },
    paper_bgcolor: '#ffffff',
    plot_bgcolor: '#ffffff',
    font: { family: 'Inter, system-ui, sans-serif', color: '#263238' },
    xaxis: { gridcolor: '#e6eaed', zerolinecolor: '#cfd7dc' },
    yaxis: { gridcolor: '#e6eaed', zerolinecolor: '#cfd7dc', range: [0, 1] },
    legend: { orientation: 'h', y: -0.28 },
    ...extra,
  };
}

function renderScenarioCurve() {
  if (!scenarioCurveChart.value || !scenarios.value.length) return;
  const palette = ['#101418', '#0f766e', '#59636a', '#b42318', '#d6a400'];
  const traces = scenarios.value.map((scenario, index) => ({
    x: scenario.risk_curve.map((point) => point.window),
    y: scenario.risk_curve.map((point) => point.risk_score),
    type: 'scatter',
    mode: 'lines+markers',
    name: scenario.name.replace('场景 ', ''),
    line: { color: palette[index % palette.length], width: scenario.scenario_key === bestScenario.value.scenario_key ? 4 : 2 },
    marker: { size: 7 },
  }));
  Plotly.react(scenarioCurveChart.value, traces, plotLayout('未来 1h / 3h / 6h 风险曲线'), { displayModeBar: false, responsive: true });
}

function renderScenarioBar() {
  if (!scenarioBarChart.value || !scenarios.value.length) return;
  const trace = {
    x: scenarios.value.map((scenario) => scenario.name.replace('场景 ', '')),
    y: scenarios.value.map((scenario) => scenario.peak_risk),
    type: 'bar',
    marker: {
      color: scenarios.value.map((scenario) => (scenario.scenario_key === bestScenario.value.scenario_key ? '#0f766e' : '#59636a')),
    },
    text: scenarios.value.map((scenario) => scenario.peak_risk.toFixed(3)),
    textposition: 'outside',
  };
  Plotly.react(
    scenarioBarChart.value,
    [trace],
    plotLayout('实验分支峰值风险对比', {
      margin: { l: 44, r: 24, t: 48, b: 84 },
      showlegend: false,
      xaxis: { tickangle: -18, gridcolor: '#ffffff' },
    }),
    { displayModeBar: false, responsive: true },
  );
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
        [0.58, '#d6a400'],
        [1, '#b42318'],
      ],
      opacity: 0.88,
    },
    name: '微震事件',
  };
  Plotly.react(
    scatterChart.value,
    [trace],
    plotLayout('微震点云', {
      scene: {
        xaxis: { title: '桩号 / X', gridcolor: '#dfe6ea' },
        yaxis: { title: '横向 Y', gridcolor: '#dfe6ea' },
        zaxis: { title: '高程 Z', gridcolor: '#dfe6ea' },
        camera: { eye: { x: 1.55, y: 1.25, z: 0.8 } },
      },
      yaxis: undefined,
      xaxis: undefined,
    }),
    { displayModeBar: false, responsive: true },
  );
}

function renderCharts() {
  renderScenarioCurve();
  renderScenarioBar();
  renderScatterChart();
}

function resizeCharts() {
  [scenarioCurveChart.value, scenarioBarChart.value, scatterChart.value].filter(Boolean).forEach((node) => Plotly.Plots.resize(node));
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
          <span>最终风险等级</span>
          <strong>{{ closedLoop.final_risk_level || closedLoop.risk_level }}</strong>
        </div>
        <div>
          <span>风险位置</span>
          <strong>{{ closedLoop.risk_position?.label || closedLoop.risk_interval?.label }}</strong>
        </div>
        <div>
          <span>风险机理</span>
          <strong>{{ closedLoop.risk_mechanism }}</strong>
        </div>
        <div>
          <span>推荐方案</span>
          <strong>{{ closedLoop.recommended_plan?.scenario || closedLoop.best_scenario }}</strong>
        </div>
      </section>

      <section class="lab-panel input-panel">
        <div class="panel-heading">
          <p>面板 1</p>
          <h2>多源输入概览</h2>
        </div>
        <div class="source-grid">
          <article class="source-item">
            <span>微震数据</span>
            <strong>已载入</strong>
            <p>{{ snapshot.microseismic_features?.event_count }} 个事件，窗长 {{ snapshot.microseismic_features?.time_window?.duration_min }} min</p>
          </article>
          <article class="source-item">
            <span>TBM 参数</span>
            <strong>已载入</strong>
            <p>推进 {{ snapshot.tbm_features?.advance_rate }} mm/min，转速 {{ snapshot.tbm_features?.cutterhead_rpm }} rpm</p>
          </article>
          <article class="source-item">
            <span>地质 JSON</span>
            <strong>已载入</strong>
            <p>{{ snapshot.geology_features?.current_geologic_body_type }}，{{ snapshot.geology_features?.structural_risk_tags?.join(' / ') }}</p>
          </article>
          <article class="source-item">
            <span>掌子面里程</span>
            <strong>K{{ snapshot.chainage }}</strong>
            <p>{{ snapshot.timestamp }}，覆盖度 {{ percent(snapshot.risk_context?.data_coverage) }}</p>
          </article>
        </div>
      </section>

      <section class="lab-panel state-mechanism-panel">
        <div class="panel-heading">
          <p>面板 2</p>
          <h2>统一状态与机理识别</h2>
        </div>
        <div class="state-grid">
          <div class="state-card">
            <span>微震状态</span>
            <strong>{{ formatScore(snapshot.risk_context?.microseismic_activity_prior) }}</strong>
            <p>累计能 {{ snapshot.microseismic_features?.cumulative_energy_j }} J，最大能 {{ snapshot.microseismic_features?.max_energy_j }} J</p>
            <p>前方事件 {{ percent(snapshot.microseismic_features?.front_event_ratio) }}，拱顶事件 {{ percent(snapshot.microseismic_features?.distribution_ratios?.arch_top) }}</p>
          </div>
          <div class="state-card">
            <span>TBM 状态</span>
            <strong>{{ formatScore(snapshot.tbm_features?.anomaly_score) }}</strong>
            <p>推力 {{ snapshot.tbm_features?.thrust }} kN，扭矩 {{ snapshot.tbm_features?.torque }} kNm</p>
            <p>贯入度 {{ snapshot.tbm_features?.penetration }} mm/rev，扰动 {{ formatScore(snapshot.tbm_features?.disturbance_index) }}</p>
          </div>
          <div class="state-card">
            <span>地质状态</span>
            <strong>{{ formatScore(snapshot.geology_features?.geologic_complexity_score) }}</strong>
            <p>断层 {{ snapshot.geology_features?.near_fault ? '是' : '否' }}，蚀变带 {{ snapshot.geology_features?.near_alteration_zone ? '是' : '否' }}</p>
            <p>结构面编码 {{ snapshot.geology_features?.structural_attitude_encoding?.length || 0 }} 组</p>
          </div>
        </div>

        <div class="mechanism-grid">
          <article v-for="agent in agentSummaries" :key="agent.title" class="agent-item">
            <div>
              <span>{{ agent.title }}</span>
              <strong>{{ formatScore(agent.score) }}</strong>
            </div>
            <p v-for="line in agent.lines.filter(Boolean)" :key="line">{{ line }}</p>
          </article>
          <article class="mechanism-evidence">
            <span>机理证据链</span>
            <strong>{{ agents.mechanism_agent?.dominant_mechanism }}</strong>
            <p v-for="item in agents.mechanism_agent?.trigger_evidence || []" :key="item">{{ item }}</p>
          </article>
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

      <section class="lab-panel experiment-panel">
        <div class="panel-heading">
          <p>面板 3</p>
          <h2>数字实验分支</h2>
        </div>
        <div class="scenario-grid">
          <article v-for="scenario in scenarios" :key="scenario.scenario_key" class="scenario-card" :class="{ selected: scenario.scenario_key === bestScenario.scenario_key }">
            <span>{{ scenario.name }}</span>
            <strong>{{ scenario.peak_risk.toFixed(3) }}</strong>
            <p>{{ scenario.high_risk_interval.label }}，{{ scenario.expected_dominant_mechanism }}</p>
            <p>{{ scenario.suggested_action }}</p>
          </article>
        </div>
        <div class="chart-grid">
          <div ref="scenarioBarChart" class="plot"></div>
          <div ref="scenarioCurveChart" class="plot"></div>
        </div>
      </section>

      <section class="lab-panel spatial-panel">
        <div class="panel-heading">
          <p>面板 4</p>
          <h2>空间预警展示</h2>
        </div>
        <div class="spatial-grid">
          <TunnelScene :result="result" />
          <div class="spatial-side">
            <div ref="scatterChart" class="plot scatter-plot"></div>
            <section class="warning-output">
              <span>闭环决策</span>
              <strong>置信度 {{ percent(closedLoop.confidence || closedLoop.plan_confidence) }}</strong>
              <ul>
                <li v-for="item in closedLoop.recommended_plan?.measures || closedLoop.recommended_measures" :key="item">{{ item }}</li>
                <li v-for="item in closedLoop.data_to_collect_next" :key="item">{{ item }}</li>
              </ul>
            </section>
          </div>
        </div>
      </section>
    </main>

    <main v-else class="loading-state">
      <p v-if="loading">正在编排多智能体实验...</p>
      <p v-else>{{ error }}</p>
      <button v-if="error" type="button" class="run-button" @click="loadLab">重试</button>
    </main>
  </div>
</template>
