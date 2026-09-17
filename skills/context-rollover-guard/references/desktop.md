# Codex Desktop 使用与测试

在输入框输入 `$context-rollover-guard`，选择该 skill，并附上需求。

## 第一次测试

`使用 $context-rollover-guard 运行离线自测，告诉我是否通过。`

自测运行打包的真实 CLI，以合成事件检查预测、压缩后基线重置及状态持久化。不消耗模型测试额度，不修改项目 Hooks。通过不代表 Desktop 自动切换已经实现。

## 检查当前项目

`使用 $context-rollover-guard 检查当前项目的配置、Hooks 和交接状态。`

调用 `python3 <skill>/scripts/crg.pyz config --workspace <项目绝对路径>`。
读取项目 crg.toml、.codex 下实际 Hook 配置，以及 .crg-state/workspaces 下已有 state.json。使用状态中真实 session_id 调用 `status --workspace <项目> --session <ID> --state-root <状态根目录>`。没有记录时报告尚未绑定，不创建虚构会话。不要把 doctor 的缺失缓存当成现场探测结果。

该 skill 不假设任何特定机器、项目或 Hook 已经安装。请始终读取目标项目的现场配置与状态；没有记录时报告尚未绑定，不创建虚构会话。默认交接目录可为项目内 `.codex/context-archive`，但它必须保持私有并排除在版本控制之外。全局安装这个 skill 不会将 Hooks 扩散到其他项目。

## 真正的交接续做

当项目 Hook 提示已经保存交接且阻止旧任务提交时，在同一项目手动新建任务，发送：

`使用 $context-rollover-guard 读取 /绝对路径/.codex/context-archive/crg_…/handoff.md，继续其中保存的用户请求。`

使用提示中给出的真实路径。保留旧任务，直至新任务已接手。自测无需刻意填满上下文。若需要在其他项目部署 Hooks，应另行明确部署范围并检查该版本运行时支持；skill 安装不等同于 Hook 部署。
