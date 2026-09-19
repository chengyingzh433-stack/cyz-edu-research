# CYZ 教育研究工作流

在 Codex 里用中文说明你现在有什么：一个教学困惑、几篇论文、研究方案，或还没有选题。`cyz-edu-research` 会据此引导选题、文献阅读、证据综合、研究设计和论文写作，并把进度留在项目文件夹里。

当前发布版本为 **0.3.0**，以 Skill 安装。独立桌面工作台仍在开发，这个仓库不提供桌面安装程序。仓库为私有，下载需要相应 GitHub 访问权限。

- [功能介绍、下载安装和第一条使用指令](https://github.com/chengyingzh433-stack/cyz-edu-research/releases/tag/0.3.0)
- [交给 agent 安装与检查](docs/agent-install.md)
- [安装、升级和回滚](docs/install-upgrade-rollback.md)
- [完整工作流规则](skills/cyz-edu-research/SKILL.md)
- [验证记录](docs/acceptance/workflow-acceptance.md)

安装后可以在 Codex 中输入：

```text
$cyz-edu-research
我想做教育研究，目前没有选题。请结合我的学科、资料和时间条件，带我找一个能继续核查的方向。
```

主 ZIP 不包含 humanizer-zh、humanizer、MinerU Desk 或本地模型。0.3.0 语言检查还需要显式传入补充依赖锁文件，步骤见 [agent 指南](docs/agent-install.md#4-语言依赖与-030-兼容处理)。重要文献、数字和研究结论仍需人工核查。
