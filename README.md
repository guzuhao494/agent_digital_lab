# rockburst-agent-lab

智能体数字实验室的最小可运行闭环 MVP。系统读取微震、TBM 掘进参数和地质 JSON 三类数据，构建统一的岩爆孕育状态向量，编排多个专业智能体完成风险分析、机理匹配、反事实推演和闭环预警输出。

## MVP 范围

- 多源输入层：微震事件 CSV、TBM 参数 CSV、地质 JSON。
- 统一状态构建层：把时空微震、掘进工况和地质构造编码为统一状态向量。
- 多智能体协同层：微震感知、掘进工况、地质认知、机理匹配、推演实验、预警决策、反馈校正。
- 数字实验室核心层：自动生成多组反事实控制场景，并比较未来时窗岩爆风险。
- 闭环输出层：风险等级、危险区段、主导机理路径、处置建议、置信度和补采数据建议。

## WSL 运行

后端：

```bash
cd /mnt/c/Users/17196/Desktop/智能体数字实验室/agent_digital_lab
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python backend/app.py
```

前端：

```bash
cd /mnt/c/Users/17196/Desktop/智能体数字实验室/agent_digital_lab/frontend
export PATH="$HOME/.local/node/bin:$PATH"
npm install
npm run dev
```

浏览器打开 `http://localhost:5173`。

## 数据接入

- `GET /api/health`：服务健康检查。
- `GET /api/lab/run`：读取默认样例数据并运行闭环实验。
- `POST /api/lab/run`：可传入 `microseismic_path`、`tbm_path`、`geology_path` 覆盖默认数据路径。
- `POST /api/lab/run`：也支持 `multipart/form-data` 上传，字段名为 `microseismic_file`、`tbm_file`、`geology_file`。微震和 TBM 支持 `.csv` / `.xlsx`，地质结构支持 `.json`。

前端“多源输入概览”面板提供三类文件上传入口。未上传时系统使用 `backend/sample_data` 中的样例数据；上传任意一类文件时，该类数据覆盖样例数据，其余数据继续使用样例数据。

## OpenClaw 接入说明

当前 MVP 所有专业 agent 都通过 `OpenClawRuntime` 适配层执行。默认模式为 `local`，用于无外部服务时保持闭环可运行；配置 `OPENCLAW_MODE=llm` 后，后端会把每个智能体的功能 prompt、统一状态和可审计基线结果发送给 OpenAI-compatible LLM 接口，agent 输出会包含 `llm_assessment`、`openclaw_runtime.llm_called=true` 和 `agent_implementation=openclaw+llm`。详细配置见 `docs/openclaw_llm_setup.md`。

```bash
cp .env.example .env
# 修改 .env 中的 OPENCLAW_MODE、OPENCLAW_LLM_API_KEY、OPENCLAW_LLM_BASE_URL、OPENCLAW_LLM_MODEL
./scripts/stop-dev.sh
./scripts/start-dev.sh
```
