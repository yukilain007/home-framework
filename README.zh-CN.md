# HOME Framework

让 AI 延续你的工作，而不是每次重新认识你。

[English](README.md) | 简体中文

你有没有遇到过：

- 换一个 AI 对话窗口，它突然“不认识你”？
- 昨天已经解释过的项目背景，今天又要重新讲一遍？
- 在 ChatGPT、Claude、本地模型之间切换，每次都像从零开始？
- 想让 AI 更了解你的习惯，却不想把所有私人信息交出去？
- AI 看起来“知道很多”，但你不知道它依据了哪些信息？

AI 很会回答问题。

但在新的窗口、模型或工具里，它通常不知道你之前已经确认过什么。

HOME Framework 解决的是 AI 协作中的“上下文延续（context continuity）”问题。

无论你使用 ChatGPT、Claude、本地模型，还是 AI Agent，HOME 都帮助 AI 在用户允许的范围内继续理解：

- 正在做什么；
- 当前目标是什么；
- 哪些信息已经确认；
- 哪些信息不应该共享。

它不是让 AI 获取你的全部过去，而是让 AI 获得此刻应该知道的部分。

## 换一个窗口，不换一个你

假设你正在长期使用 AI 完成一个项目。

第一次，你告诉 AI：

- 项目背景；
- 工作方式；
- 当前状态；
- 已确认方案。

之后，你换了一个新的 AI 窗口。

传统方式通常是：

- 重新复制背景；
- 重新解释需求；
- 重新纠正 AI；
- 再等它慢慢进入状态。

HOME 的方式是：

```text
你的上下文
  ↓
HOME Workspace
  ↓
生成当前任务需要的 Context Handoff
  ↓
新的 AI 继续工作
```

这不是让 AI 拿到你的全部过去，而是让它拿到当前任务需要、并且经过你允许的那一部分上下文。

## 上下文延续，不等于 AI 记忆

很多 AI 产品关注的是：

> 让 AI 记住用户。

HOME 关注的是另一个问题：

当用户：

- 换窗口；
- 换模型；
- 换工具；
- 进入新的工作阶段；

如何让 AI 获得正确背景。

真正重要的是，AI 当前使用的信息是否：

- 准确；
- 被确认；
- 适合当前任务；
- 没有泄露不必要的信息。

上下文延续不是 AI 记忆。它不是让模型自动保存你的状态，也不是把聊天历史全部塞进下一次对话。它更像一次有边界的工作交接：用户决定哪些内容可以延续，哪些内容需要保持私密，哪些内容只适合当前任务。

## HOME 是什么

HOME 不是 AI 模型，也不是简单的聊天记录存储。

HOME 不是 AI Memory。它不让模型自己决定什么应该长期保留，也不把聊天历史自动变成“记忆”。

HOME 是用户控制的 AI context infrastructure，也就是用户控制的 AI 上下文基础设施。

它管理：

- 哪些信息可以延续；
- 哪些信息只属于当前任务；
- 哪些信息需要保持私密；
- 哪些信息经过确认后可以成为稳定上下文。

换句话说，HOME 不是替你保存所有过去，而是帮你准备“这一次 AI 真正需要知道什么”。

## 为什么需要用户控制

AI 可以帮助整理信息。

但 AI 不应该单方面决定什么代表用户长期状态。

如果上下文完全交给模型自动管理，用户很难知道：

- 哪些信息被带进了下一次对话；
- 哪些信息已经过期却仍在影响回答；
- 哪些只是模型推测，而不是用户确认过的事实；
- 哪些私人内容其实不该被共享给某个工具或某次任务。

HOME 把这部分控制权放回用户手里。它要求重要信息经过人工确认，要求候选信息保持隔离，也要求 context handoff 可以被检查和重建。

这对 AI Agent、知识系统、长期项目助手和多模型工作流尤其重要：系统越复杂，越需要明确“AI 此刻到底依据了什么”。

## 工作方式

```text
你的信息
  ↓
HOME Workspace
  ↓
core / current / candidate
  ↓
Context Handoff
  ↓
AI
```

`core` 是稳定、已确认的信息，例如项目原则、已确认的偏好、较长期有效的背景。它不是模型自动保存的个人记忆，而是经过审阅后当前仍适合复用的上下文。

`current` 是当前阶段有效的信息，例如最近正在做什么、某个任务的阶段、短期有效的项目状态。

`candidate` 是等待确认的信息。它可以被记录和检查，但不会把候选信息编译进上下文，也不会自动成为事实。

`Context Handoff` 是最终给 AI 的上下文交接文件。它只包含被选择、被允许、适合当前目的的信息。

## 场景说明

一个用户可能同时使用：

- ChatGPT 写作；
- Claude 分析资料；
- 本地模型处理私人内容。

HOME 不替换这些 AI，也不要求用户只使用一个工具。

它负责帮助不同 AI 获取合适的上下文：写作工具只需要文章背景，资料分析工具只需要项目材料，本地模型可以处理你选择保留在本地的敏感内容。不同工具拿到不同范围的信息，但这些信息来自同一套由用户控制、可以审阅的上下文结构。

如果你在开发 AI Agent、个人知识系统、团队知识库或长期项目助手，HOME 可以作为 context handoff 的底层约束：它不替你选择模型，而是帮助你控制模型拿到的背景。

## HOME 不是什么

HOME 不是自动上传全部聊天记录的工具。

HOME 不是让 AI 自己决定什么应该长期保留。

HOME 不是替代 ChatGPT、Claude 或本地模型的模型层。

HOME 也不是面向普通消费者的一站式聊天应用。它更像是给认真使用 AI 的人准备的上下文工作台：透明、可审计、由用户控制。

## 隐私理念

HOME 的设计是 local-first。用户拥有自己的数据，并决定哪些内容进入上下文。

默认原则是：

- 明确授权：重要信息进入稳定上下文前需要人工确认；
- 最小必要上下文：只给 AI 当前任务需要的内容；
- 人工确认变化：重要状态变化不应由模型自动推断；
- 候选隔离：未批准的候选信息可以等待审阅，但不能当作事实调用；
- 可验证输出：生成的 handoff 可以被用户查看、复核和重建。

HOME 不承诺绝对安全或永久保存。它提供的是更清晰的边界、更少的误用机会，以及更容易审计的上下文流动方式。

## Quickstart

这是中文 Quickstart，面向开发者，但尽量保持易读。所有带 `--as-of` 的示例都使用固定日期，是为了让构建结果和诊断结果可复现；实际使用时可以换成你要审查的上下文日期。

HOME Framework 需要 Python 3.11 或更新版本。当前已发布的 alpha 包可以这样安装：

```bash
python -m pip install home-framework==0.1.0a4
```

查看 CLI：

```bash
home --help
```

创建一个示例工作区：

```bash
home init example-home --name example-home
```

验证刚创建的示例工作区：

```bash
home validate example-home
```

按固定日期构建上下文：

```bash
home build example-home \
  --handoff project.execution \
  --as-of 2026-07-20
```

检查生命周期、导出、敏感信息和 Git 状态：

```bash
home doctor example-home --as-of 2026-07-20
home doctor example-home --as-of 2026-07-20 --strict
```

这些命令来自当前 CLI help：

- `home --help`
- `home init --help`
- `home validate --help`
- `home build --help`
- `home doctor --help`

## 当前状态

HOME Framework 仍处于 alpha prerelease 阶段。

`home-framework 0.1.0a4` 已通过 GitHub Actions OIDC Trusted Publishing 发布到 PyPI。

接口、schema 和命令输出仍可能变化。请不要把当前 alpha 版本当作稳定协议使用。

## Developer Documentation

更技术化的开发者文档在这里：

- [English README](README.md)
- [Architecture](docs/architecture.md)
- [Privacy model](docs/privacy-model.md)
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)

## License

Apache-2.0。详见 [LICENSE](LICENSE)。
