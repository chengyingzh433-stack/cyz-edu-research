# 工作流与工作台：该装哪个，还需要准备什么

只想在 Codex 里推进研究，安装 `cyz-edu-research` 就可以，不必安装工作台。想用独立窗口管理材料、草稿、历史版本和研究任务，再使用 `cyz-research-workbench`。工作台沿用同一套研究规则，不另建一套工作流。

## 两个仓库各自负责什么

| 项目 | 负责的内容 | 是否依赖另一个项目 | 当前状态 |
| --- | --- | --- | --- |
| [CYZ 教育研究工作流](https://github.com/chengyingzh433-stack/cyz-edu-research) | S0–S8 研究规则、项目模板、证据要求、检查脚本 | 不依赖工作台，可直接在 Codex 中使用 | 0.3.0 已公开发布 |
| [CYZ 研究工作台](https://github.com/chengyingzh433-stack/cyz-research-workbench) | Windows 界面、材料管理、草稿版本、Codex 任务接入、MinerU 解析入口 | 当前 0.1.0 开发版固定使用工作流 0.3.0 | 源码公开；Windows x64 安装测试版已预发布，尚未签名 |

两个仓库及其发布附件均公开下载，不需要 GitHub 凭据。要桌面程序，下载 [工作台安装版的 `.exe`](https://github.com/chengyingzh433-stack/cyz-research-workbench/releases/tag/v0.1.0-preview.1)；只要 Skill，下载工作流的 ZIP。不要把工作流 ZIP 当成桌面安装程序。

## 安装后有哪些东西，哪些需要另备

| 内容 | 只安装工作流 Skill | 使用工作台 Windows 安装版 |
| --- | --- | --- |
| 主工作流 `cyz-edu-research` | 从 [0.3.0 发布页](https://github.com/chengyingzh433-stack/cyz-edu-research/releases/tag/0.3.0) 安装 | 安装包自带 0.3.0，安装时自动复制到 Codex 技能目录 |
| Codex 与登录 | 使用者自行准备 | 仍需本机 Codex CLI 可用且已登录，安装包不包含账号 |
| Node、pnpm | Skill 本身不要求 | 使用安装版不需要另装；从源码运行工作台时需要 |
| Python | 运行工作流检查、初始化等脚本时需要 Python 3.11 或更新版本 | 工作台自带 Python 3.14.7 用于初始化项目；不会给系统安装 `py` 命令，单独在 Codex 中跑脚本仍须确认解释器路径 |
| `humanizer-zh`、`humanizer` | 不在主 ZIP 中；分别用于中文、英文语言处理 | 同样不随安装包提供。需要对应环节时另行安装和核验 |
| MinerU Desk 与模型 | 选择本地 MinerU 解析路线时另备 | 工作台的本地 PDF 解析依赖本机 MinerU Desk 和模型，不随包下载 |

工作流的本地 MinerU 路线还需要兼容的 `mineru` 接入 Skill；工作台通过自身适配器调用 MinerU Desk，并使用主工作流中的导出脚本。不要把“工作台能够打开”“主 Skill 已安装”“PDF 可以解析”和“语言检查通过”当成同一件事。具体依赖、许可限制与检查方法见 [agent 安装指南](agent-install.md#4-语言依赖与-030-兼容处理)。

工作台目前验证过的本地解析环境是 MinerU Desk 0.3.1、MinerU 3.4.5、CPU、Pipeline 模型。没有准备好 MinerU 时，仍可使用本地草稿和版本管理，但不能据此声称工作台 PDF 解析已就绪。

## Skill 装在哪里，更新时会发生什么

工作台安装版使用 `CODEX_HOME/skills/cyz-edu-research`；未设置 `CODEX_HOME` 时，使用当前用户的 `.codex/skills/cyz-edu-research`。程序可以安装到别的盘，Skill 仍放在 Codex 读取的位置。安装与运行应使用同一个 Codex 主目录。

已有文件与固定发布包一致时直接复用；有不同内容则保留并提示，不自动覆盖。每次开始研究，工作台还会查询 Codex 是否识别并启用了主 Skill，并显式指定使用它。复制成功不代表当前 Codex 会话已经加载成功。

两个项目各自发布版本，版本号不需要相同。当前对应关系是 **工作台 0.1.0 → 工作流 0.3.0**。工作台不会自动跟随工作流仓库的 `main` 或“最新版本”；以后升级工作流，需要先更新工作台中的固定版本与校验值并重新验证，不能只替换 Skill 文件就认定兼容。

卸载工作台不会主动删除外部研究项目或 Codex Skill。研究项目请放在独立文件夹，不要放进程序安装目录。两个源码仓库都不应存放个人论文、项目缓存、登录信息或模型文件。

## 从哪里开始

只用工作流：读 [安装与使用指南](agent-install.md)，安装后在 Codex 中输入：

```text
$cyz-edu-research
我想做教育研究，目前还没有选题。请先了解我的学科、已有资料和时间条件，每次只问一个关键问题。
```

使用工作台安装包：从 [预发布页面](https://github.com/chengyingzh433-stack/cyz-research-workbench/releases/tag/v0.1.0-preview.1) 下载，按 [Windows 安装说明](https://github.com/chengyingzh433-stack/cyz-research-workbench/blob/main/docs/windows-install.md) 安装，从桌面书本图标打开，选择一个独立的项目文件夹。

让 agent 从源码部署工作台：先读 [工作台 README](https://github.com/chengyingzh433-stack/cyz-research-workbench) 和 [Codex 部署指南](https://github.com/chengyingzh433-stack/cyz-research-workbench/blob/main/docs/codex-deploy.md)。检查环境、运行 `setup.ps1`、确认 Codex 发现主 Skill，再分别报告语言依赖和 PDF 解析状态。不要自动覆盖本地修改、下载模型或发起付费研究任务。
