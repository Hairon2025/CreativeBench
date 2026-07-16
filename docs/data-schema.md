# Prompt 数据规范 v1

本文档定义 CreativeBench 第一版 Prompt 数据结构和标注规则。当前阶段只约定数据，不涉及数据库、Embedding、RAG 或模型调用。

## 1. 设计目标

- 同时支持人工标注和后续 GLM 自动分类；
- 支持一个 Prompt 对应多个文体、意图、角色及风险标签；
- 保留标签来源、置信度和分类理由，便于人工审核；
- 标签使用稳定的英文代码，展示时使用中文名称；
- 让数据可以直接转换为后续的 Pydantic 模型和数据库模型。

## 2. 单条数据示例

```json
{
  "schema_version": "1.0",
  "id": "cbp-0001",
  "prompt_text": "请续写下面的悬疑故事：午夜十二点，已经停用十年的电话突然响了。",
  "language": "zh-CN",
  "scope": "creative_writing",
  "source": {
    "type": "synthetic",
    "reference": null
  },
  "labels": {
    "genres": ["suspense"],
    "intents": ["story_continuation"],
    "roles": ["no_explicit_role"],
    "risks": ["normal"]
  },
  "annotation": {
    "status": "approved",
    "source": "human",
    "confidence": 1.0,
    "rationale": "包含明确的悬疑情境，并要求延续已有故事。",
    "annotator": "demo-human-01"
  },
  "created_at": "2026-07-16T00:00:00+08:00"
}
```

## 3. 字段说明

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `schema_version` | string | 是 | 数据规范版本，当前固定为 `1.0` |
| `id` | string | 是 | Prompt 唯一标识，第一版格式为 `cbp-0001` |
| `prompt_text` | string | 是 | 清洗后的 Prompt 正文 |
| `language` | string | 是 | 语言代码，当前示例为 `zh-CN` |
| `scope` | enum | 是 | `creative_writing`、`risk_test` 或 `out_of_scope` |
| `source.type` | enum | 是 | 数据来源类型 |
| `source.reference` | string/null | 是 | 原始链接、内部编号或来源备注；合成数据为 null |
| `labels.genres` | string[] | 是 | 文体标签；安全测试或越界样本可以为空 |
| `labels.intents` | string[] | 是 | 创作意图标签；安全测试或越界样本可以为空 |
| `labels.roles` | string[] | 是 | 角色方式标签，至少一个 |
| `labels.risks` | string[] | 是 | 安全风险标签，至少一个 |
| `annotation.status` | enum | 是 | `pending`、`approved` 或 `rejected` |
| `annotation.source` | enum | 是 | 标签由人工、模型或导入数据产生 |
| `annotation.confidence` | number/null | 是 | 0 到 1；人工确认样本使用 1.0，待审核可为空 |
| `annotation.rationale` | string | 是 | 标签判断依据 |
| `annotation.annotator` | string/null | 是 | 标注人或模型版本标识 |
| `created_at` | datetime | 是 | ISO 8601 时间 |

### source.type 可选值

- `synthetic`：为项目人工构造的演示数据；
- `public_web`：来源明确且允许使用的公开网页数据；
- `internal`：内部业务数据，不应提交到公开仓库；
- `manual`：人工录入但未记录外部来源的数据。

## 4. 标签维度

标签的机器可读定义保存在 `data/taxonomy.json`。

### genres：文体

描述 Prompt 期望生成内容的题材或文体。允许多标签，例如一个案件发生在未来太空站中，可以同时标记为 `suspense` 和 `sci_fi`。

### intents：创作意图

描述用户希望模型执行的创作动作。允许多标签，例如“按照鲁迅风格续写”同时属于 `story_continuation` 和 `style_imitation`。

### roles：角色方式

描述 Prompt 是否设置了用户、模型或多个角色。它与角色设定意图不同：

- `character_design` 表示“请帮我设计角色”；
- `model_role` 表示“请你扮演某个角色与我互动”。

### risks：安全风险

与创作标签正交，用于标记 Prompt 是否包含注入、越狱或敏感诱导。一个高风险 Prompt 仍然可以拥有正常的文体和创作意图标签。

## 5. 核心标注规则

1. 每个标签数组内部不能重复。
2. `normal` 只能单独出现，不能与其他风险标签共存。
3. 没有明确角色扮演要求时使用 `no_explicit_role`。
4. `creative_writing` 样本应至少包含一个文体和一个创作意图。
5. `risk_test` 或 `out_of_scope` 样本不得为了填满字段而虚构文体和意图，允许使用空数组。
6. 标签应根据用户明确表达的需求判断，不推测未出现的题材。
7. 人工确认的样本使用 `approved + human + confidence=1.0`。
8. 模型预测结果在人工确认前使用 `pending + model`。
9. 无法确定的边界样本进入人工审核，不强行给出高置信度。

## 6. 文件职责

```text
data/
├── taxonomy.json                 # 标签代码、中文名称和边界定义
├── schemas/
│   └── prompt.schema.json        # 单条 Prompt 的 JSON Schema
└── examples/
    └── prompts.jsonl             # 人工构造并审核的演示样本
```

- JSON Schema 负责检查字段和基本类型；
- taxonomy 负责检查标签值是否合法；
- JSONL 每行保存一条完整数据，适合流式处理和批量导入。

## 7. 当前边界

- 当前样例仅用于验证数据设计，不是正式训练集或评测集；
- 当前没有实现自动校验脚本，第三步建立 Python 工程后再实现；
- 标签体系是 v1，后续根据边界样本调整时必须更新版本和变更记录。
