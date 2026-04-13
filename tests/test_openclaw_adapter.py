from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from rockburst_lab.openclaw_adapter import AgentInvocation, OpenClawRuntime  # noqa: E402


class OpenClawAdapterTest(unittest.TestCase):
    def test_nuwa_mode_calls_openai_compatible_gateway_and_merges_assessment(self) -> None:
        requests = []

        def fake_http_post(url, headers, payload, timeout):
            requests.append((url, headers, payload, timeout))
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"summary":"微震能量与构造扰动耦合增强",'
                                '"evidence":["事件向掌子面前方集中","推力扰动同步抬升"],'
                                '"risk_adjustment":0.04,'
                                '"confidence":0.81,'
                                '"recommended_actions":["降低推进速度并复核支护"],'
                                '"data_to_collect":["掌子面前方超前地质预报"],'
                                '"notes":["样本量仍偏小"]}'
                            )
                        }
                    }
                ]
            }

        runtime = OpenClawRuntime(
            mode="nuwa",
            env={
                "NUWA_API_KEY": "test-key",
                "NUWA_BASE_URL": "https://api.nuwaflux.com/v1",
                "NUWA_MODEL": "test-model",
            },
            http_post=fake_http_post,
        )
        invocation = AgentInvocation(
            name="微震感知智能体",
            role="微震时空聚集与能量演化分析",
            prompt="请输出中文岩爆风险研判。",
            observation={"state_snapshot": {"chainage": 1200.0}},
        )

        result = runtime.invoke(invocation, lambda: {"score": 0.5, "level": "关注", "findings": ["基线研判"]})

        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0][0], "https://api.nuwaflux.com/v1/chat/completions")
        self.assertEqual(requests[0][2]["model"], "test-model")
        self.assertEqual(result["agent_implementation"], "openclaw+llm")
        self.assertTrue(result["openclaw_runtime"]["llm_called"])
        self.assertEqual(result["openclaw_runtime"]["mode"], "nuwa_llm_gateway")
        self.assertEqual(result["score"], 0.54)
        self.assertEqual(result["llm_assessment"]["confidence"], 0.81)
        self.assertIn("LLM 研判：微震能量与构造扰动耦合增强", result["findings"])

    def test_nuwa_mode_without_key_reports_local_fallback(self) -> None:
        runtime = OpenClawRuntime(mode="nuwa", env={})
        invocation = AgentInvocation(
            name="掘进工况智能体",
            role="TBM 参数异常与扰动强度分析",
            prompt="请输出中文工况研判。",
            observation={},
        )

        result = runtime.invoke(invocation, lambda: {"score": 0.42, "level": "关注"})

        self.assertEqual(result["agent_implementation"], "openclaw")
        self.assertFalse(result["openclaw_runtime"]["llm_called"])
        self.assertIn("NUWA_API_KEY", result["openclaw_runtime"]["fallback_reason"])


if __name__ == "__main__":
    unittest.main()
