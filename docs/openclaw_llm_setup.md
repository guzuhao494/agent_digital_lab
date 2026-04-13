# OpenClaw LLM 接入说明

本项目的每个专业智能体都通过 `OpenClawRuntime` 运行。默认 `OPENCLAW_MODE=local` 时，系统使用后端确定性逻辑，适合无密钥演示和单元测试；当切换为 `OPENCLAW_MODE=llm` 后，后端会把智能体名称、职责、功能 prompt、统一状态和可审计基线结果发送给 OpenAI-compatible LLM 接口，并把 LLM 返回的中文研判写回 agent 输出。

## 启用方式

1. 复制示例环境文件：

   ```bash
   cp .env.example .env
   ```

2. 编辑 `.env`：

   ```bash
   OPENCLAW_MODE=llm
   OPENCLAW_LLM_API_KEY=你的模型服务密钥
   OPENCLAW_LLM_BASE_URL=https://api.openai.com/v1
   OPENCLAW_LLM_MODEL=gpt-4o-mini
   ```

   `OPENCLAW_LLM_BASE_URL` 可以替换为 OpenClaw 模型网关、vLLM、Ollama 兼容网关或其他 OpenAI-compatible 服务地址。兼容旧环境变量 `OPENCLAW_API_KEY`、`OPENCLAW_OPENAI_BASE_URL` 和 `OPENCLAW_BASE_URL`。

3. 重启服务：

   ```bash
   ./scripts/stop-dev.sh
   ./scripts/start-dev.sh
   ```

## 如何确认真的调用了 LLM

运行 `/api/lab/run` 后，查看任意 agent 输出中的：

- `agent_implementation`：应为 `openclaw+llm`。
- `openclaw_runtime.llm_called`：应为 `true`。
- `openclaw_runtime.mode`：应为 `llm_openai_compatible`。
- `llm_assessment`：包含 LLM 生成的 `summary`、`evidence`、`recommended_actions` 和 `data_to_collect`。

如果没有配置密钥或模型服务不可用，系统不会假装调用成功，而会回落到本地逻辑，并在 `openclaw_runtime.fallback_reason` 中写明原因。

## 后端 prompt 位置

各专业智能体的功能 prompt 定义在 `backend/rockburst_lab/orchestrator.py` 的 `analyze` 方法中，运行时由 `AgentInvocation.prompt` 传入 `backend/rockburst_lab/openclaw_adapter.py`，再组装成 LLM 请求。

当前策略是“确定性特征抽取 + LLM 专业研判”：

- 确定性逻辑负责三源数据解析、统一状态编码、基础风险评分和反事实场景生成。
- LLM 负责专业解释、证据链整理、处置建议、补采数据建议和小幅风险修正。
- 风险修正被限制在 `-0.08` 到 `0.08`，避免大模型随意覆盖工程计算结果。
