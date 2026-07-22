# HOME Framework

HOME Framework 是一个 local-first 的 Python 工具包，用来验证经过人工审阅的权威文件，并生成确定性的、面向特定用途的上下文交接文档。

> 当前版本：`0.1.0a4`
>
> 这是 alpha 预发布版本，已发布到 PyPI。文件格式和命令输出在稳定版之前仍可能变化。

HOME Framework 不是自动记忆系统。它不会证明 AI 具有连续意识，不会推断同意，不会读取聊天历史，也不会把工作区内容发送给第三方服务。

[English README](README.md)

## 核心概念

- **权威文件**：由人审阅和控制的 YAML 文件，是构建上下文的唯一输入。
- **核心文档**：稳定、长期有效的指导信息。
- **当前文档**：带有效期的近期上下文。
- **候选内容**：未批准的提议；会被验证，但不会把候选记忆编译进上下文。
- **交接文件**：为某个具体目的选择 ID、范围和允许的敏感级别。
- **导出文件**：可重复生成的 Markdown 投影，不应手工维护。

## 安装

HOME Framework 需要 Python 3.11 或更新版本。

安装已发布的 alpha 包：

```bash
python -m pip install home-framework==0.1.0a4
```

如果要参与开发，可以从本地仓库安装：

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

## 中文 Quickstart

创建一个不初始化 Git、也不创建远程仓库的示例工作区：

```bash
home init example-home --name example-home
```

生成的工作区包含两个公开的虚构权威文档和一个交接文件，因此可以立即验证和构建。对一个已经有效的工作区重复执行 `home init` 是安全的，不会覆盖文件；非空且未知的目录会被拒绝。

验证仓库自带的虚构示例：

```bash
home validate examples/fictional-assistant
```

按固定日期构建上下文：

```bash
home build examples/fictional-assistant \
  --handoff project.execution \
  --as-of 2026-07-20
```

默认输出位置是：

```text
examples/fictional-assistant/exports/project.execution.md
```

在相同权威文件、交接文件和上下文日期下重复构建，会得到相同指纹。真实生成时间只是展示信息，不参与指纹计算。

检查生命周期、导出、敏感信息和 Git 卫生状态：

```bash
home doctor examples/fictional-assistant --as-of 2026-07-20
home doctor examples/fictional-assistant --as-of 2026-07-20 --strict
```

不传 `--as-of` 时，build 和 doctor 会使用本地日期。测试和可复现自动化应始终显式传入日期。

## 工作区结构

```text
home.yaml           版本化工作区清单
sources/core/       稳定权威文档
sources/current/    有有效期的当前权威文档
candidates/         不会进入编译上下文的候选内容
handoffs/           已审阅的选择声明
exports/            可删除、可重建的 Markdown 导出
```

`home.yaml` 保持很小：

```yaml
kind: workspace
schema_version: "1.0"
name: example-home
framework:
  minimum_version: 0.1.0a4
defaults:
  export_directory: exports
```

导出目录必须是安全的相对路径。绝对路径、`..`、符号链接逃逸和指向工作区外部的自定义输出路径都会被拒绝。

## 隐私边界

- CLI 只读取操作者显式提供的工作区路径。
- 未选择上下文时，默认不选择任何内容。
- 交接文件默认只允许 `public` 内容；`private` 必须显式列出。
- `secret` 内容不能导出，即使绕过验证也不允许。
- 候选内容永远不会进入编译上下文。
- 本仓库只包含虚构示例数据。
- 生成的 `exports/*.md` 默认被 Git 忽略，可以删除后重建。

## 开发检查

```bash
python scripts/check.py
pre-commit run --all-files
```

`scripts/check.py` 会运行测试、schema drift 检查、Ruff、mypy、虚构示例验证、重复构建指纹检查和敏感信息扫描。

## 当前限制

- 只处理本地文件，没有数据库或云同步。
- 一次 build 只选择一个交接文件和一个上下文日期。
- 不会自动批准候选内容，也不会自动修改权威文件。
- Markdown 是当前唯一的渲染格式。
- `1.0` 是当前唯一接受的 schema 协议版本。

## 许可证

Apache-2.0。详见 [LICENSE](LICENSE)。
