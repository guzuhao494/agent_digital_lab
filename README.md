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

## OpenClaw 接入说明

当前 MVP 所有专业 agent 都通过 `OpenClawRuntime` 适配层执行。默认模式为 `local`，用于无外部服务时保持闭环可运行。后续接入真实 OpenClaw SDK 或服务时，可在 `backend/rockburst_lab/openclaw_adapter.py` 中扩展 `sdk` 分支，并通过环境变量启用：

```bash
export OPENCLAW_MODE=sdk
export OPENCLAW_API_KEY=your_key
export OPENCLAW_BASE_URL=https://your-openclaw-endpoint
```
