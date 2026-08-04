# Continuity Contracts 差异审计

## 审计范围

本审计只读取 HOME Framework 当前仓库的 models、schemas、repository loader、compiler、renderer、initializer、doctor、CLI、tests 与 architecture ADR。没有读取或引用外部仓库的代码、prompt、字段实现或文档段落。

## 当前能力

- `models.py` 定义 `core`、`current`、既有 `candidate`、`handoff` 和 workspace manifest。
- `repository.py` 只发现 `sources/core`、`sources/current`、`candidates`、`handoffs` 四类 YAML，并提供聚合诊断。
- `compiler.py` 只选择 active 的 core/current authority；既有 candidate 永不进入编译。
- `renderer.py` 只渲染编译后的 Markdown；它不读取聊天、不做选择、不做记忆晋升。
- `initializer.py` 创建虚构 workspace，默认不写 Git、不覆盖非空目录。
- `doctor.py` 做生命周期、导出、安全和 Git hygiene 的只读诊断。
- CLI 只有 `init`、`validate`、`build`、`doctor`；没有 inspect 或 continuity contract 专用接口。
- JSON Schemas 由 Pydantic models 生成并通过 schema-drift 检查。

## 差异与 seam

连续交互所需的 persona autonomy、window state、lifeline、memory candidate、recall decision 和 maintenance channel 不属于现有 authority 文档，也不应伪装成 core/current。它们将放在可选的 `continuity/` 目录，由独立的 `ContinuityContract` 联合模型加载。

现有默认工作流保持不变：没有 `continuity/` 时，既有 workspace 的验证、编译、输出与 document count 不改变；只有 handoff 明确列出 `continuity_ids` 时，允许的连续性锚点才进入输出。MemoryCandidate 和 RecallDecision 始终只可 inspect，不能进入 handoff。

## 独立实现声明

本功能是基于 HOME 现有模型、Pydantic、YAML loader 和 Markdown renderer 的 clean-room independent implementation。没有复制、改写或导入任何第三方仓库的代码、prompt、字段组合、实现细节或受限文档文本。所有协议语义由 HOME 的 local-first、human-reviewed、model-agnostic 约束重新定义。
