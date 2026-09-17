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
python3 scripts/build_release.py
python3 scripts/build_release.py --verify
```

根目录运行时只使用 Python 标准库；可选的 `pip` 打包配置位于 [`pyproject.toml`](pyproject.toml)。本地日志、交接、测试工作区和机器特定证据已刻意排除在 Git 之外。

## 安全模型

CRG 将未知结果视为恢复工作，而不是重试授权。除非已获授权的拥有方集成推进一笔已正向验证的事务，否则恢复操作保持只读。对“提示词可能已被接受、但结果暂不可见”的情况，这一点尤其重要。

操作细节请参阅随 skill 发布的参考资料：[`desktop.md`](dist/context-rollover-guard/references/desktop.md) 与 [`recovery.md`](dist/context-rollover-guard/references/recovery.md)。

## 许可证

本项目采用 [Apache License 2.0](LICENSE)。

## 贡献与安全问题

提交变更前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。报告敏感问题前请阅读 [SECURITY.md](SECURITY.md)；当前尚无已验证的私密报告渠道。

## 安全配置

新检出的仓库默认禁用（`enabled = false`、`mode = "auto"`），提示词与压缩阻断均须显式开启。安装 skill 不会安装 hooks。守护功能需要显式启用及单独配置、验证的集成；`enabled` 本身不代表已激活。

机器专用运行时路径放在 `$CODEX_HOME/context-rollover.toml`（默认 `~/.codex/context-rollover.toml`）的 `[context_rollover]` / `codex_binary` 中。未指定时探测通过 PATH 查找 `codex`。仓库配置覆盖用户配置，CLI 覆盖最后生效。

运行 `python3.13 -m crg config --workspace .` 查看有效值及各字段的 `sources`（`default`、`user`、`repo`、`cli`）。命令只读 CRG 设置，不读取 Codex 凭据、不探测或安装运行时。`--codex PATH` 仅覆盖本次查看的路径。要求 Python 3.11+，请使用本机对应解释器。

运行 `python3.13 scripts/verify_offline.py --clean` 可将当前未忽略的源码复制到临时干净 Git 检出，隔离 HOME/CODEX_HOME，先构建最终制品，再执行单元测试、CLI 集成测试及导出的 skill ZIP、PYZ 和 wheel 校验。本地审计模式拒绝所覆盖的 Python 网络操作及真实运行时启动，但不等于操作系统沙箱；托管 CI 另行强制并验证操作系统网络隔离。CI 配置覆盖 Linux/macOS 的 Python 3.11–3.13；使用 `--clean` 时构建发生在临时检出中，不修改工作区产物；运行 `python3 scripts/build_release.py` 可统一更新工作区发布产物。

## 运行时路径与诊断

对于尚无 `crg.toml` 的工作区，`python3.13 -m crg init --workspace /项目路径` 只创建默认禁用的配置，拒绝覆盖已有文件。`python3.13 -m crg doctor --workspace /项目路径` 默认输出 JSON，加上 `--format human` 可显示简明文本。普通诊断只读；没有新证据时，hooks 信任、遥测可用性和已启用会话的实际激活状态保持未知。

缓存及回执目录默认位于配置的 state root 下，不再依赖源码检出目录。已有证据需要显式配置路径，仍可使用 `doctor --evidence PATH`。修改现有集成前请阅读 [CRG-0103 路径、状态语义与迁移说明](docs/implementation/CRG-0103-RESULTS.md)。`doctor --probe` 会显式调用隔离运行时探测，不属于安装或普通查看操作。

安装及对应卸载/回退步骤见[贡献者快速指南](docs/CONTRIBUTOR-QUICKSTART.md)。保留未确认的恢复日志；移除 skill 不等于卸载独立配置的 hooks。


### M4 离线实验

新增 `statistical-audit`、`resolve-model` 和供测试适配器使用的重置事务引擎，详见 [M4 契约说明](docs/metrics/EXPERIMENTAL-M4.md)。这些实现不会启用高级策略或实际兑换重置额度。[CRG-0301～0401 验收报告](docs/implementation/CRG-0301-0401-RESULTS.md) 区分了已通过的离线测试与尚缺的真实数据、运行时及 Windows/附件证据；整批任务尚未满足上线验收条件。

执行与恢复提供本地去重、提交前持久化意图，以及接受状态不明时不盲目重发的保证，不承诺分布式恰好一次交付。归档策略、配置支持与恢复限制见[执行配置与信任语义](docs/architecture/execution-semantics.md)。

## 复现离线演示（v0.1.0 已实现）

在仓库目录使用 Python 3.11+：

```sh
python3 scripts/demo_offline.py
```

演示在独立临时工作目录中调用发布的 CLI，使用空 HOME/CODEX_HOME，PATH 中没有 Codex。
它创建默认禁用的项目配置，读取配置和诊断结果，并确认 Hook 安装预览不写入 Hook 文件。
不调用模型。预览中的 dispatcher 仅为占位示例，不安装或激活集成。
最终 `result: PASS` 表示四项离线检查成功，不代表真实运行时兼容性。

## 连续性策略与控制模式

CRG 默认禁用。显式启用后，`native_cooperative` 允许原生连续执行并保存受支持的快照；
`observe` 不执行 Hook 写入或拦截；`manual_recovery` 由用户决定交接；
`guarded_owned_rollover` 需要明确授权且已验证的自有集成。
原生压缩由运行时负责；CRG 保存恢复内容，并在操作是否已接受不明时核对证据，不盲目重发。

MODE_A 是保守回退；MODE_B 需要已验证的无损 Stop 数据、可信 Hook 执行及提示词拦截；
MODE_C 还要求拥有活动传输通道，并验证新任务、工作区、接受状态与归档行为。
设置策略或模式并不能证明这些能力。当前没有通过拦截认证的公开 Hook 适配器。
全局安装 skill 不等于全局安装 Hook。详见[策略说明](docs/architecture/native-cooperative.md)。

私密恢复归档可能包含原始提示词和答案；文件权限不等于加密。公开夹具是合成数据，默认不上传任何内容。
卸载时保留未确认的恢复日志；按[快速指南](docs/CONTRIBUTOR-QUICKSTART.md)只移除安装回执所拥有的 Hook 条目。

当前[托管验收证据](docs/ci-acceptance.md)仅适用于离线测试。真实跨仓库 fork、原生能力激活及 Windows 支持仍未验证。
可从[范围明确的贡献任务](docs/GOOD-FIRST-ISSUES.md)开始参与。

### 规范化分析与本地预测

[本地分析指南](docs/quickstart.md)提供有界规范化导入、自然周统计、预览确认后的数值导出与任务执行前的基线预测。没有已验证的官方适配器时，账户活动保持不支持；不会猜测原生会话日志结构。参见[离线证据](docs/evaluations/summary.md)、[预测限制](docs/evaluations/forecast-quality.md)和[隐私边界](docs/privacy.md)。[合成数据集](docs/data-card.md)不含贡献者日志。原生 Windows 仍不支持；重置适配器保持默认禁用、实验性质。
