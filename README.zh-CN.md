# Context Rollover Guard

简体中文 · [English](README.md)

**给 Codex 长任务准备一本交接笔记。** Context Rollover Guard（简称 CRG）是社区开发的 Python 工具，也可以作为 Codex 技能使用。它能检查已保存的恢复状态、验证交接文件，并避免在结果不明确时重复执行操作。

想象你和别人一起搭一个很大的乐高模型。换人接着搭时，新人需要知道：原来的要求是什么、已经搭好了哪些、还有什么需要检查。CRG 提供的就是这类交接工具。它**不会让 Codex 拥有无限记忆**，安装后也**不会自动把对话搬到新任务里**。

## 现在可以做什么？

| 你的需求 | 目前能做到什么 |
|---|---|
| 不连接账号，先试一试 | 使用临时目录和模拟数据运行离线演示 |
| 检查项目中的 CRG 设置 | 只读检查配置和恢复状态 |
| 接着已有的交接记录工作 | 先验证归档，再在同一工作区的新任务中继续 |
| 查看用量 | 主动导入受支持的数字记录，见[用量指南](docs/quickstart.md) |
| 自动保护 Desktop 的所有对话 | 目前不支持；需要另外配置并验证集成 |

**运行要求：** Python 3.11 或更新版本。离线 CI 已覆盖 Linux、macOS 上的 Python 3.11–3.13。原生 Windows 暂不支持，WSL 也未经过独立验收。这是 CRG 的支持范围，不代表 Codex 本身的平台要求。CRG 不是 OpenAI 官方产品。

## 从这里开始：安全地试一次

在 GitHub 页面点击 **Code → Download ZIP**，解压后打开文件夹。如果你已经会用 Git，也可以运行：

```sh
git clone https://github.com/FeidaWang/Context-Rollover-Guard.git
cd Context-Rollover-Guard
```

### 使用 Codex Desktop 的朋友

1. 在 Codex Desktop 中，把下载并解压的仓库文件夹打开为本地项目。
2. 在该文件夹中新建任务，粘贴：

   ```text
   阅读 README.zh-CN.md，确认有 Python 3.11 或更新版本，然后运行
   python3 scripts/demo_offline.py，用简单的话解释结果。
   不要安装 hooks，也不要启用实时集成。
   ```

3. 在命令输出中寻找 `result: PASS`。它表示四个离线检查通过：创建默认关闭的配置、读取配置、检查工作区，以及只预览 hook 配置而不安装。

Python 演示本身不调用模型或 API，也不需要登录 Codex。但让 Codex 帮你执行命令，仍会使用正常的 Codex 对话额度。如果缺少 Python，请从 [Python 官方下载页](https://www.python.org/downloads/)安装 3.11 或更新版本后重试。

### 使用终端或 Codex CLI 的朋友

终端就是输入命令的应用。在下载的仓库文件夹中打开终端，依次运行：

```sh
python3 --version
python3 scripts/demo_offline.py
python3 dist/context-rollover-guard/scripts/self_test.py
```

第一条应显示 3.11 或更新版本。演示应显示 `PASS`，自检应成功结束。这些命令不会把 CRG 安装进 Codex；甚至还没安装 Codex CLI 也能运行。Codex 本身的安装请参考[官方入门指南](https://developers.openai.com/codex/quickstart)。

## 可选：让 Codex 使用这个技能

**技能（skill）**就是 Codex 可以阅读的一小份操作说明和工具。可安装的完整目录是 [`dist/context-rollover-guard`](dist/context-rollover-guard)，其中已经包含 Python 运行程序。

在 Codex 中告诉技能安装器：

```text
使用 skill-installer 安装下面这个地址中的技能：
https://github.com/FeidaWang/Context-Rollover-Guard/tree/main/dist/context-rollover-guard
如果已经安装过，先停下来告诉我位置，不要覆盖已有副本。
```

确认安装器建议的位置后再接受安装。然后在客户端的技能选择器中选择 `context-rollover-guard`。Codex CLI 可以输入 `/skills` 或 `$context-rollover-guard`。如果找不到，重启 Codex 后再检查。另见 [OpenAI 技能说明](https://developers.openai.com/codex/skills)及本项目的[手动安装和卸载指南](docs/CONTRIBUTOR-QUICKSTART.md)。

第一次可以这样说：

```text
使用 context-rollover-guard 技能运行离线自检。
告诉我哪些检查通过了，哪些能力还没有验证。
```

安装技能只会增加说明和脚本，不会安装 hooks、启动后台监控或开启自动恢复。**Hook** 是“发生某个事件时运行代码”的另外一层集成；初学者体验演示不需要它。

## 检查你自己的项目

在本仓库文件夹中运行下面的命令。把 `/absolute/path/to/your-project` 换成你项目文件夹的真实完整路径；路径含空格时保留双引号。

```sh
python3 dist/context-rollover-guard/scripts/crg.pyz doctor --workspace "/absolute/path/to/your-project" --format human
```

`doctor` 只检查 CRG 配置，不会启用保护。看到 `UNKNOWN`，表示证据还不够，不能理解成保护已经开启。如果需要初始配置，`init` 会创建默认关闭的 `crg.toml`，已有文件则不会覆盖：

```sh
python3 dist/context-rollover-guard/scripts/crg.pyz init --workspace "/absolute/path/to/your-project"
```

**工作区（workspace）**就是项目文件夹。**交接记录（handoff）**是保存下来、供后续继续工作的资料包。如果经授权的集成已经生成交接记录，请在**同一工作区创建新任务**，提供 `handoff.md` 的准确路径，让 CRG 先验证归档再继续。结果确认之前，保留原任务和恢复文件。前面的演示不会替你的真实对话生成交接记录。

## 几个容易误会的地方

- CRG 默认关闭。只把 `enabled` 改成开启，不代表集成已经生效。目前没有经过认证、可以拦截提示词的公共 hook 适配器。
- 如果无法确定消息是否已经被接受，CRG 会先停下来核查，不直接重发。这有助于降低重复操作的风险，但不是“绝对只执行一次”的保证。
- Codex 自己负责压缩上下文。CRG 不能扩大上下文窗口，也不能保证所有客户端都能无损恢复。
- 上下文空间、token 用量、账号额度是不同的东西。CRG 不会自动读取所有聊天或实时账号余额。预测功能仍属实验性质；没有证据时会显示未知。
- 恢复归档可能保存完整提示词和回答，请保存在私有位置。文件权限不等于加密。默认不会上传数据，公开测试数据均为模拟数据。
- 通过原安装器卸载技能，或只移除自己记录下来的手动安装副本。保留尚未处理完的恢复文件。另行安装的 hooks 需要按[安装凭据回滚](docs/CONTRIBUTOR-QUICKSTART.md)。

## 想参与开发？

运行程序只依赖 Python 标准库。下面的命令可复现离线测试，并重新构建仓库中的分发文件：

```sh
python3 scripts/verify_offline.py --clean
python3 scripts/build_release.py
python3 scripts/build_release.py --verify
```

测试器会在临时源码副本中运行。本地 Python 网络防护不等于操作系统沙箱；托管 CI 会另外验证操作系统级网络隔离。离线测试通过，不代表真实 Codex 会话已通过兼容性认证。详见 [CI 验证记录](docs/ci-acceptance.md)与[支持范围](docs/COMPATIBILITY.md)。

- [贡献者入门](docs/CONTRIBUTOR-QUICKSTART.md) · [适合首次贡献的任务](docs/GOOD-FIRST-ISSUES.md)
- [恢复细节](dist/context-rollover-guard/references/recovery.md) · [Desktop 使用边界](dist/context-rollover-guard/references/desktop.md)
- [用量分析指南](docs/quickstart.md) · [隐私说明](docs/privacy.md) · [架构说明](docs/architecture/native-cooperative.md)
- [贡献须知](CONTRIBUTING.md) · [安全问题报告](SECURITY.md)

本项目采用 [Apache License 2.0](LICENSE) 许可证。
