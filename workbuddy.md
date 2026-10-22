# WorkBuddy 开发对话导出（麦分精算师）

> 本文件记录使用腾讯 WorkBuddy 开发「麦分精算师」的完整过程，用于核验是否符合
> 麦当劳程序员创意开发大赛 WorkBuddy 专项奖励条件（真实使用 WorkBuddy 智能体开发）。

## 开发对话摘要

### 1. 需求澄清
- 用户确认参与 1024「麦当劳程序员创意开发大赛」，目标为**进榜拿周边（Star>0）**，已有 GitHub、MCP Token 待申请。
- 明确要求：由 WorkBuddy 生成创意并选择**差异化赛道**。

### 2. 调研（WorkBuddy 联网检索 + 官方仓库读取）
- 检索并核实官方规则：报名 / 排名截止 2026-10-25 23:59，定榜 2026-10-26 00:00，按 GitHub 公开 Star 排名。
- 读取官方活动仓库 README / activityGuidelines / CONTEST_DECLARATION（原文逐字复用，不可改动）。
- 读取麦当劳 MCP Server 仓库，获取**完整 30+ 工具清单**，按使用热度划分红海 / 蓝海赛道。
- 结论：点餐 / 省钱 / 派对为红海；积分 / 商城 / 抽奖 / 营养为蓝海。

### 3. 创意生成与选型
WorkBuddy 给出 3 个差异化创意并分析稳健度：
1. **麦分精算师（积分理财）** — 蓝海、永远有数据、纯只读最安全 → **推荐并采用**
2. 麦麦抽奖体检师 — 最新工具蓝海但依赖活动在跑
3. 麦麦营养热量预算师 — 营养工具蓝海但已有少量同类

用户确认方向 1。

### 4. 工程实现（WorkBuddy 生成代码 + 验证）
- 生成 `scripts/mcd_points_advisor.py`：纯标准库实现 MCP Streamable HTTP 客户端 + 积分贪心匹配分析。
- 内置 `--offline` 离线演示模式（无 Token 也能跑通，便于评审 / 拉 Star）。
- 严格遵循只读红线：仅调用 `query-my-account` / `mall-points-products` / `mall-product-detail`，不触碰任何写接口。
- **真实接口验证**：使用用户提供的麦当劳 MCP Token 跑通实时模式，成功读取真实积分账户（可用 / 累计 / 已过期 / 本月将过期）与商城商品，并正确过滤纯现金商品、生成兑换建议，证明 Skill 对官方接口完全可用。
- 修正点：官方工具返回体为「字段说明 + `## Original Response` + JSON」混排，且字段名为 `availablePoint` / `currentMouthExpirePoint` 等；已更新解析器精准提取。

### 5. 必交文件产出
WorkBuddy 一次性生成全部参赛文件：
- `README.md`（门面 + 使用示例）、`CONTEST_DECLARATION.md`（官方原文）、`MCP_INTEGRATION.md`、`mcp-config.example.json`（环境变量占位符脱敏）、`SKILL.md`、本 `workbuddy.md`、`.gitignore`。

### 6. 提交指引（待用户执行）
- 仓库设为 Public，创建时间符合要求；
- 按官方 Issue 模板提交（标题与正文间勿换行、地址不用 Markdown）；
- 本 `workbuddy.md` 随仓库提交以参与专项积分奖励。

## 验证结论
- ✅ 真实使用腾讯 WorkBuddy 完成调研、选型、编码、自测、文档全流程。
- ✅ 真实使用麦当劳官方 MCP 只读能力（实时模式需用户 Token）。
- ✅ 符合 WorkBuddy 专项奖励的提交条件。
