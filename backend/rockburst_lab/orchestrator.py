from __future__ import annotations

import csv
import json
import math
import statistics
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable

from .openclaw_adapter import AgentInvocation, OpenClawRuntime


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        return default if value is None or value == "" else float(value)
    except (TypeError, ValueError):
        return default


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def normalize(value: float, low: float, high: float) -> float:
    return 0.0 if high <= low else clamp((value - low) / (high - low))


def mean(values: Iterable[float]) -> float:
    data = list(values)
    return statistics.fmean(data) if data else 0.0


def stdev(values: Iterable[float]) -> float:
    data = list(values)
    return statistics.pstdev(data) if len(data) > 1 else 0.0


def risk_level(score: float) -> str:
    if score >= 0.78:
        return "严重"
    if score >= 0.58:
        return "高"
    if score >= 0.34:
        return "关注"
    return "低"


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


@dataclass
class DomainAgent:
    name: str
    role: str
    runtime: OpenClawRuntime

    def invoke(self, state: dict[str, Any], logic: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
        return self.runtime.invoke(
            AgentInvocation(
                name=self.name,
                role=self.role,
                prompt=f"Analyze rockburst risk as {self.role}.",
                observation=state,
            ),
            lambda: logic(state),
        )


class MicroseismicSensingAgent(DomainAgent):
    def analyze(self, state: dict[str, Any]) -> dict[str, Any]:
        return self.invoke(state, self._logic)

    def _logic(self, state: dict[str, Any]) -> dict[str, Any]:
        vector = state["state_vector"]
        score = clamp(
            0.36 * vector["microseismic_energy_index"]
            + 0.26 * vector["microseismic_cluster_index"]
            + 0.22 * vector["microseismic_energy_acceleration"]
            + 0.16 * vector["microseismic_mechanism_index"]
        )
        findings = [
            f"近窗事件数 {state['microseismic']['recent_event_count']}，累计能量 {state['microseismic']['recent_energy_sum']:.2e} J",
            f"空间聚集指数 {vector['microseismic_cluster_index']:.2f}，能量加速指数 {vector['microseismic_energy_acceleration']:.2f}",
        ]
        if vector["microseismic_mechanism_index"] > 0.55:
            findings.append("剪切和张拉破裂信号并存，提示局部应力重分配增强")
        return {
            "score": round(score, 3),
            "level": risk_level(score),
            "findings": findings,
            "signals": {
                "energy_index": vector["microseismic_energy_index"],
                "cluster_index": vector["microseismic_cluster_index"],
                "mechanism_index": vector["microseismic_mechanism_index"],
            },
        }


class TbmConditionAgent(DomainAgent):
    def analyze(self, state: dict[str, Any]) -> dict[str, Any]:
        return self.invoke(state, self._logic)

    def _logic(self, state: dict[str, Any]) -> dict[str, Any]:
        vector = state["state_vector"]
        score = clamp(
            0.38 * vector["tbm_disturbance_index"]
            + 0.24 * vector["tbm_thrust_anomaly"]
            + 0.24 * vector["tbm_torque_anomaly"]
            + 0.14 * vector["tbm_advance_pressure_index"]
        )
        return {
            "score": round(score, 3),
            "level": risk_level(score),
            "findings": [
                f"当前桩号 K{state['chainage']:.1f}，推进速度 {state['tbm']['latest']['advance_rate']:.2f} mm/min",
                f"推力异常 {vector['tbm_thrust_anomaly']:.2f}，扭矩异常 {vector['tbm_torque_anomaly']:.2f}，扰动指数 {vector['tbm_disturbance_index']:.2f}",
            ],
            "signals": {
                "disturbance_index": vector["tbm_disturbance_index"],
                "advance_pressure_index": vector["tbm_advance_pressure_index"],
            },
        }


class GeologyCognitionAgent(DomainAgent):
    def analyze(self, state: dict[str, Any]) -> dict[str, Any]:
        return self.invoke(state, self._logic)

    def _logic(self, state: dict[str, Any]) -> dict[str, Any]:
        vector = state["state_vector"]
        active = state["geology"]["active_structures"]
        score = clamp(
            0.42 * vector["geology_structure_index"]
            + 0.34 * vector["geology_stress_index"]
            + 0.24 * vector["geology_brittleness_index"]
        )
        sources = [f"{item['type']} K{item['chainage_start']:.0f}-K{item['chainage_end']:.0f}" for item in active]
        if not sources:
            sources = ["当前窗未命中显著构造，但仍保留高地应力背景权重"]
        return {
            "score": round(score, 3),
            "level": risk_level(score),
            "findings": [
                f"构造风险源：{'；'.join(sources)}",
                f"最大主应力 {state['geology']['in_situ_stress_mpa']:.1f} MPa，岩性脆性指数 {vector['geology_brittleness_index']:.2f}",
            ],
            "signals": {
                "structure_index": vector["geology_structure_index"],
                "stress_index": vector["geology_stress_index"],
            },
        }


class MechanismMatchingAgent(DomainAgent):
    def analyze(self, state: dict[str, Any]) -> dict[str, Any]:
        return self.invoke(state, self._logic)

    def _logic(self, state: dict[str, Any]) -> dict[str, Any]:
        vector = state["state_vector"]
        candidates = [
            (
                "高地应力蓄能 -> 构造面锁固 -> 微震聚集 -> 动态卸荷触发",
                0.30 * vector["geology_stress_index"]
                + 0.26 * vector["geology_structure_index"]
                + 0.25 * vector["microseismic_cluster_index"]
                + 0.19 * vector["tbm_disturbance_index"],
            ),
            (
                "掘进扰动增强 -> 围岩损伤扩展 -> 能量快速释放",
                0.36 * vector["tbm_disturbance_index"]
                + 0.30 * vector["microseismic_energy_acceleration"]
                + 0.20 * vector["microseismic_energy_index"]
                + 0.14 * vector["geology_brittleness_index"],
            ),
            (
                "结构面切割 -> 局部块体失稳 -> 剪切破裂占优",
                0.44 * vector["geology_structure_index"]
                + 0.24 * vector["microseismic_mechanism_index"]
                + 0.20 * vector["geology_brittleness_index"]
                + 0.12 * vector["tbm_torque_anomaly"],
            ),
        ]
        path, score = max(candidates, key=lambda item: item[1])
        nodes = state["geology"].get("mechanism_graph", {}).get("nodes", [])
        matched_nodes = [node["id"] for node in nodes if node.get("trigger_threshold", 0) <= score + 0.1][:4]
        return {
            "score": round(clamp(score), 3),
            "level": risk_level(score),
            "dominant_path": path,
            "matched_nodes": matched_nodes,
            "findings": [
                f"主导机理路径：{path}",
                f"机理匹配强度 {score:.2f}，匹配节点 {', '.join(matched_nodes) if matched_nodes else '待补充'}",
            ],
        }


class SimulationExperimentAgent(DomainAgent):
    def analyze(self, state: dict[str, Any]) -> dict[str, Any]:
        return self.invoke(state, self._logic)

    def _logic(self, state: dict[str, Any]) -> dict[str, Any]:
        vector = state["state_vector"]
        base_score = clamp(
            0.30 * vector["microseismic_energy_index"]
            + 0.22 * vector["microseismic_cluster_index"]
            + 0.20 * vector["tbm_disturbance_index"]
            + 0.18 * vector["geology_structure_index"]
            + 0.10 * vector["geology_stress_index"]
        )
        scenarios = [
            ("keep_current", "保持当前掘进参数", 1.00, "维持当前推进和支护参数"),
            ("reduce_advance_rate", "降低推进速度", 0.82, "推进速度下调 20%，同步观察微震能量斜率"),
            ("strengthen_support", "调整支护参数", 0.78, "提高锚喷支护响应等级并缩短滞后距离"),
            ("ignore_structure", "弱化结构面影响假设", 0.90, "用于评估构造认知不确定性的反事实分支"),
            ("combined_control", "降速并加强支护", 0.66, "推进速度下调 20%，支护参数同步增强"),
        ]
        branches = []
        acceleration = vector["microseismic_energy_acceleration"]
        structure_memory = 0.05 * vector["geology_structure_index"]
        for key, name, multiplier, action in scenarios:
            curve = []
            for step in range(1, 7):
                drift = 0.035 * step * acceleration + structure_memory
                tbm_relief = 0.018 * step if key in {"reduce_advance_rate", "combined_control"} else 0.0
                support_relief = 0.014 * step if key in {"strengthen_support", "combined_control"} else 0.0
                score = clamp(base_score * multiplier + drift - tbm_relief - support_relief)
                curve.append({"window": f"T+{step * 30}min", "risk_score": round(score, 3), "level": risk_level(score)})
            branches.append(
                {
                    "scenario_key": key,
                    "name": name,
                    "control_action": action,
                    "risk_curve": curve,
                    "peak_risk": round(max(point["risk_score"] for point in curve), 3),
                }
            )
        best = min(branches, key=lambda branch: branch["peak_risk"])
        return {
            "score": round(base_score, 3),
            "level": risk_level(base_score),
            "branches": branches,
            "best_scenario": best,
            "findings": [
                f"共生成 {len(branches)} 组反事实实验分支",
                f"未来 3 小时最低峰值风险来自：{best['name']}，峰值 {best['peak_risk']:.2f}",
            ],
        }


class WarningDecisionAgent(DomainAgent):
    def analyze(self, state: dict[str, Any]) -> dict[str, Any]:
        return self.invoke(state, self._logic)

    def _logic(self, state: dict[str, Any]) -> dict[str, Any]:
        agents = state["agent_outputs"]
        score = clamp(
            0.27 * agents["microseismic"]["score"]
            + 0.18 * agents["tbm"]["score"]
            + 0.21 * agents["geology"]["score"]
            + 0.20 * agents["mechanism"]["score"]
            + 0.14 * agents["simulation"]["best_scenario"]["peak_risk"]
        )
        chainage = state["chainage"]
        best = agents["simulation"]["best_scenario"]
        measures = [
            best["control_action"],
            "对 K{:.0f}-K{:.0f} 区段提高微震采样与人工巡检频次".format(chainage - 40, chainage + 90),
        ]
        if risk_level(score) in {"高", "严重"}:
            measures.append("执行短进尺、弱扰动掘进，并复核掌子面前方构造")
        confidence = clamp(0.52 + 0.14 * len(state["geology"]["active_structures"]) + 0.18 * state["data_quality"]["coverage"])
        return {
            "risk_score": round(score, 3),
            "risk_level": risk_level(score),
            "risk_interval": {
                "chainage_start": round(chainage - 40, 1),
                "chainage_end": round(chainage + 90, 1),
                "label": "K{:.0f}-K{:.0f}".format(chainage - 40, chainage + 90),
            },
            "dominant_mechanism_path": agents["mechanism"]["dominant_path"],
            "recommended_measures": measures,
            "plan_confidence": round(confidence, 3),
            "best_scenario": best["name"],
        }


class FeedbackCorrectionAgent(DomainAgent):
    def analyze(self, state: dict[str, Any]) -> dict[str, Any]:
        return self.invoke(state, self._logic)

    def _logic(self, state: dict[str, Any]) -> dict[str, Any]:
        vector = state["state_vector"]
        follow_up = []
        if state["microseismic"]["recent_event_count"] < 12:
            follow_up.append("补采高频微震事件，重点覆盖掌子面前方 150 m")
        if vector["geology_structure_index"] > 0.45:
            follow_up.append("补充超前地质预报或钻孔成像，校正结构面连续性")
        if vector["tbm_disturbance_index"] > 0.45:
            follow_up.append("同步采集刀盘振动、推进油缸压力和出渣粒径")
        if not follow_up:
            follow_up.append("保持微震、TBM 与地质编录三源同步更新")
        return {
            "parameter_updates": {
                "mechanism_weight_delta": round(0.08 * vector["geology_structure_index"], 3),
                "tbm_disturbance_weight_delta": round(0.06 * vector["tbm_disturbance_index"], 3),
                "microseismic_energy_weight_delta": round(0.07 * vector["microseismic_energy_acceleration"], 3),
            },
            "data_to_collect_next": follow_up,
            "findings": ["根据后续真实监测结果回写 agent 权重和机理路径置信度"],
        }


class RockburstLabOrchestrator:
    def __init__(
        self,
        default_microseismic_path: Path,
        default_tbm_path: Path,
        default_geology_path: Path,
        runtime: OpenClawRuntime | None = None,
    ) -> None:
        self.default_microseismic_path = default_microseismic_path
        self.default_tbm_path = default_tbm_path
        self.default_geology_path = default_geology_path
        self.runtime = runtime or OpenClawRuntime()
        self.microseismic_agent = MicroseismicSensingAgent("微震感知智能体", "微震时空聚集与能量演化分析", self.runtime)
        self.tbm_agent = TbmConditionAgent("掘进工况智能体", "TBM 参数异常与扰动强度分析", self.runtime)
        self.geology_agent = GeologyCognitionAgent("地质认知智能体", "断层、蚀变带和结构面风险解释", self.runtime)
        self.mechanism_agent = MechanismMatchingAgent("机理匹配智能体", "当前状态与机理图谱节点路径匹配", self.runtime)
        self.simulation_agent = SimulationExperimentAgent("推演实验智能体", "数字实验室反事实情景推演", self.runtime)
        self.decision_agent = WarningDecisionAgent("预警决策智能体", "风险等级、危险区段和处置方案输出", self.runtime)
        self.feedback_agent = FeedbackCorrectionAgent("反馈校正智能体", "监测反馈下的参数和机理权重修正", self.runtime)

    def run(
        self,
        microseismic_path: str | Path | None = None,
        tbm_path: str | Path | None = None,
        geology_path: str | Path | None = None,
    ) -> dict[str, Any]:
        micro_path = Path(microseismic_path) if microseismic_path else self.default_microseismic_path
        tbm_path_obj = Path(tbm_path) if tbm_path else self.default_tbm_path
        geology_path_obj = Path(geology_path) if geology_path else self.default_geology_path

        microseismic = self._load_microseismic(micro_path)
        tbm = self._load_tbm(tbm_path_obj)
        geology = self._load_geology(geology_path_obj)
        state = self._build_state(microseismic, tbm, geology)

        micro_result = self.microseismic_agent.analyze(state)
        tbm_result = self.tbm_agent.analyze(state)
        geology_result = self.geology_agent.analyze(state)
        mechanism_result = self.mechanism_agent.analyze(state)
        simulation_result = self.simulation_agent.analyze(state)

        state["agent_outputs"] = {
            "microseismic": micro_result,
            "tbm": tbm_result,
            "geology": geology_result,
            "mechanism": mechanism_result,
            "simulation": simulation_result,
        }
        decision_result = self.decision_agent.analyze(state)
        feedback_result = self.feedback_agent.analyze(state)

        return {
            "lab_name": "rockburst-agent-lab",
            "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "inputs": {
                "microseismic": str(micro_path),
                "tbm": str(tbm_path_obj),
                "geology": str(geology_path_obj),
            },
            "state": state,
            "agents": state["agent_outputs"] | {
                "decision": decision_result,
                "feedback": feedback_result,
            },
            "closed_loop_output": {
                **decision_result,
                "data_to_collect_next": feedback_result["data_to_collect_next"],
                "parameter_updates": feedback_result["parameter_updates"],
            },
        }

    def _load_microseismic(self, path: Path) -> list[dict[str, Any]]:
        events = []
        for row in read_csv(path):
            events.append(
                {
                    "timestamp": row["timestamp"],
                    "time": parse_time(row["timestamp"]),
                    "x": parse_float(row.get("x")),
                    "y": parse_float(row.get("y")),
                    "z": parse_float(row.get("z")),
                    "energy": parse_float(row.get("energy_j")),
                    "magnitude": parse_float(row.get("magnitude")),
                    "mechanism": row.get("mechanism", "unknown"),
                }
            )
        return sorted(events, key=lambda item: item["time"])

    def _load_tbm(self, path: Path) -> list[dict[str, Any]]:
        records = []
        for row in read_csv(path):
            records.append(
                {
                    "timestamp": row["timestamp"],
                    "time": parse_time(row["timestamp"]),
                    "chainage": parse_float(row.get("chainage_m")),
                    "thrust": parse_float(row.get("thrust_kn")),
                    "torque": parse_float(row.get("torque_knm")),
                    "advance_rate": parse_float(row.get("advance_rate_mm_min")),
                    "rpm": parse_float(row.get("rpm")),
                    "penetration": parse_float(row.get("penetration_mm_rev")),
                    "support_pressure": parse_float(row.get("support_pressure_mpa")),
                }
            )
        return sorted(records, key=lambda item: item["time"])

    def _load_geology(self, path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _build_state(
        self,
        microseismic: list[dict[str, Any]],
        tbm: list[dict[str, Any]],
        geology: dict[str, Any],
    ) -> dict[str, Any]:
        latest_tbm = tbm[-1]
        chainage = latest_tbm["chainage"]
        recent_micro = microseismic[-12:] if len(microseismic) >= 12 else microseismic
        recent_energy = [event["energy"] for event in recent_micro]
        first_half = recent_energy[: max(1, len(recent_energy) // 2)]
        second_half = recent_energy[max(1, len(recent_energy) // 2) :]
        energy_sum = sum(recent_energy)
        acceleration = normalize(mean(second_half) - mean(first_half), 0, 18000)

        thrust_values = [record["thrust"] for record in tbm]
        torque_values = [record["torque"] for record in tbm]
        latest_thrust_anomaly = self._z_anomaly(latest_tbm["thrust"], thrust_values)
        latest_torque_anomaly = self._z_anomaly(latest_tbm["torque"], torque_values)
        advance_pressure_index = clamp(
            0.58 * normalize(latest_tbm["advance_rate"], 35, 72)
            + 0.42 * normalize(latest_tbm["support_pressure"], 1.8, 3.2)
        )
        disturbance = clamp(0.38 * latest_thrust_anomaly + 0.34 * latest_torque_anomaly + 0.28 * advance_pressure_index)

        stress_mpa = parse_float(geology.get("in_situ_stress", {}).get("max_principal_mpa"))
        brittleness = parse_float(geology.get("rock_mass", {}).get("brittleness_index"))
        active_structures = self._active_structures(geology, chainage)
        structure_index = clamp(
            sum(parse_float(item.get("risk_weight"), 0.35) * parse_float(item.get("confidence"), 0.75) for item in active_structures)
        )
        vector = {
            "microseismic_event_density": normalize(len(recent_micro), 2, 14),
            "microseismic_energy_index": normalize(math.log10(energy_sum + 1), 4.4, 6.4),
            "microseismic_cluster_index": self._micro_cluster_index(recent_micro),
            "microseismic_energy_acceleration": acceleration,
            "microseismic_mechanism_index": self._micro_mechanism_index(recent_micro),
            "tbm_disturbance_index": disturbance,
            "tbm_thrust_anomaly": latest_thrust_anomaly,
            "tbm_torque_anomaly": latest_torque_anomaly,
            "tbm_advance_pressure_index": advance_pressure_index,
            "geology_structure_index": structure_index,
            "geology_stress_index": normalize(stress_mpa, 35, 70),
            "geology_brittleness_index": normalize(brittleness, 0.45, 0.90),
        }
        return {
            "chainage": chainage,
            "state_vector": {key: round(value, 4) for key, value in vector.items()},
            "state_vector_ordered": [{"name": name, "value": round(value, 3)} for name, value in vector.items()],
            "microseismic": {
                "recent_event_count": len(recent_micro),
                "recent_energy_sum": energy_sum,
                "events": [{key: value for key, value in event.items() if key != "time"} for event in microseismic],
            },
            "tbm": {
                "latest": {key: value for key, value in latest_tbm.items() if key != "time"},
                "series": [{key: value for key, value in record.items() if key != "time"} for record in tbm],
            },
            "geology": {
                "in_situ_stress_mpa": stress_mpa,
                "active_structures": active_structures,
                "mechanism_graph": geology.get("mechanism_graph", {}),
            },
            "data_quality": {
                "coverage": round(
                    clamp(
                        0.34 * min(1.0, len(microseismic) / 18)
                        + 0.33 * min(1.0, len(tbm) / 14)
                        + 0.33 * (1.0 if geology else 0.0)
                    ),
                    3,
                ),
            },
        }

    def _active_structures(self, geology: dict[str, Any], chainage: float) -> list[dict[str, Any]]:
        active = []
        for item in geology.get("structures", []):
            start = parse_float(item.get("chainage_start"))
            end = parse_float(item.get("chainage_end"))
            influence = parse_float(item.get("influence_radius_m"), 40)
            if start - influence <= chainage <= end + influence:
                active.append(
                    {
                        "type": item.get("type", "structure"),
                        "chainage_start": start,
                        "chainage_end": end,
                        "confidence": parse_float(item.get("confidence"), 0.7),
                        "risk_weight": parse_float(item.get("risk_weight"), 0.35),
                        "description": item.get("description", ""),
                    }
                )
        return active

    def _micro_cluster_index(self, events: list[dict[str, Any]]) -> float:
        if len(events) < 2:
            return 0.0
        distances = []
        for idx, event in enumerate(events):
            for other in events[idx + 1 :]:
                distances.append(
                    math.sqrt(
                        (event["x"] - other["x"]) ** 2
                        + (event["y"] - other["y"]) ** 2
                        + (event["z"] - other["z"]) ** 2
                    )
                )
        return clamp(1 - mean(distances) / 130)

    def _micro_mechanism_index(self, events: list[dict[str, Any]]) -> float:
        if not events:
            return 0.0
        risky = sum(1 for event in events if event["mechanism"] in {"shear", "tensile", "mixed"})
        mixed_bonus = 0.12 if any(event["mechanism"] == "mixed" for event in events) else 0.0
        return clamp(risky / len(events) + mixed_bonus)

    def _z_anomaly(self, latest: float, values: list[float]) -> float:
        sigma = stdev(values)
        if sigma <= 1e-9:
            return 0.0
        return clamp(abs(latest - mean(values)) / (3.0 * sigma))
