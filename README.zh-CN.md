# Context Rollover Guard

[English](README.md) · 简体中文

Context Rollover Guard（CRG）是一个开源的 Codex skill 与 Python 运行时，用于在长任务接近上下文切换、或需要恢复已有交接时，以可验证且保守的方式延续工作。

它会保留原始任务、写入可持久化验证的交接信息，并且只有在存在正向证据时才把不确定的操作视为已接受。它不会偷偷重发提示词，也不会声称已经切换了当前 Codex Desktop 的任务。

## 能做什么

- 在 Python 3.11+ 上运行无第三方依赖的独立运行时。
- 检查明确指定项目的配置、Hook 状态与已有恢复日志。
- 在已授权的集成中创建并验证可持久化的交接归档。
- 当运行时支持时，使用 `tokenUsage.last.totalTokens` 判断活动上下文压力；绝不将累计 session 用量冒充活动上下文。
- 操作是否已接受存在歧义时安全停止，而不是重复发送提示词。

## 不做什么

- 导入或运行测试时不会安装全局 Hook 或后台服务。
- 不提供通用 token 遥测；这取决于当前 Codex 运行时与明确的项目集成。
- 不会接管当前打开的 Codex Desktop 任务，也不会自动切换界面。
- 不会因为缺少一次 readback 就重发消息、重置日志或归档旧任务。

## 安装 skill

便携式 skill 位于 [`dist/context-rollover-guard`](dist/context-rollover-guard)。请使用你的 Codex skill 或 plugin 安装流程安装该目录，随后可在任务中通过 `$context-rollover-guard` 调用。

安装前可在本地检查：

```sh
python3 dist/context-rollover-guard/scripts/self_test.py
python3 dist/context-rollover-guard/scripts/crg.pyz --help
```

仓库根目录同时包含 Codex plugin manifest，支持 plugin 的工具可从 `dist/` 发现这个 skill。

## 第一次使用

可以对 Codex 说：

```text
使用 $context-rollover-guard 运行离线自测，并告诉我是否通过。
```

自测使用临时目录中的合成事件；不会消耗模型用量、安装 Hook，也不能证明 Desktop 已支持自动切换。

检查项目时可使用：

```text
使用 $context-rollover-guard 检查当前项目的配置、Hooks 和交接状态。
```

要继续一个已保存交接，请在相同工作区创建新任务，并提供其 `handoff.md` 的准确路径。新任务可靠接手前，请保留源任务。

## 开发

```sh
python3 -m unittest discover -s tests/unit -v
python3 scripts/build_zipapp.py
```

根目录运行时只使用 Python 标准库；可选的 `pip` 打包配置位于 [`pyproject.toml`](pyproject.toml)。本地日志、交接、测试工作区和机器特定证据已刻意排除在 Git 之外。

## 安全模型

CRG 将未知结果视为恢复工作，而不是重试授权。除非已获授权的拥有方集成推进一笔已正向验证的事务，否则恢复操作保持只读。对“提示词可能已被接受、但结果暂不可见”的情况，这一点尤其重要。

操作细节请参阅随 skill 发布的参考资料：[`desktop.md`](dist/context-rollover-guard/references/desktop.md) 与 [`recovery.md`](dist/context-rollover-guard/references/recovery.md)。

## 许可证

本项目采用 [Apache License 2.0](LICENSE)。

## 贡献与安全问题

提交变更前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。安全问题请按 [SECURITY.md](SECURITY.md) 的方式私下报告。
