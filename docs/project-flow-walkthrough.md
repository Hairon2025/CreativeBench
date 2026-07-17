# CreativeBench 项目全流程与代码理解手册

这份文档用于从整体上理解 CreativeBench，而不是逐行解释代码。建议先建立完整的数据流认识，再按照每个阶段给出的顺序阅读源码和测试。

## 1. 项目到底解决什么问题

原始业务是收集和标注创意写作 Prompt。随着数据量增长，单纯依赖人工会出现：

- 数据格式不一致、存在无效内容和重复 Prompt；
- 文体、创作意图、角色方式和安全风险的标签边界不清晰；
- 已经审核过的历史样本没有被复用；
- 模型分类结果缺少结构校验、审核和追溯；
- Prompt 注入、指令覆盖和角色越狱等风险缺少统一测试；
- 无法客观比较 Zero-shot、固定 Few-shot 和 RAG 的效果。

CreativeBench 将它工程化为一套 Prompt 资产管理和智能标注系统：

1. 导入、清洗和去重 Prompt；
2. 将标签规范和人工审核样例构建为知识库；
3. 通过 RAG 找到相关标签规则和相似样例；
4. 调用 GLM 输出结构化分类；
5. 使用 Pydantic 校验模型输出；
6. 将低置信度或高风险结果转人工审核；
7. 将人工确认结果回流知识库；
8. 使用离线评测和 Red Team 用例持续验证；
9. 通过 FastAPI 和 Streamlit 对外提供 Demo。

## 2. 完整运行流程

```text
CSV / JSONL 原始 Prompt
          │
          ▼
读取与字段统一
          │
          ▼
确定性清洗、长度校验、隐私处理
          │
          ▼
SHA-256 精确去重
          │
          ▼
SimHash 近似文本去重
          │
          ▼
BGE Embedding 语义去重
          │
          ▼
SQLite 保存 Prompt、导入信息和重复关系
          │
          ├───────────────────────────────┐
          │                               │
          ▼                               ▼
标签规范 taxonomy                  人工审核金标准样例
          │                               │
          └───────────┬───────────────────┘
                      ▼
              构建知识文档
                      │
                      ▼
             BGE Embedding + Qdrant
                      │
新 Prompt ──► 安全规则预扫描
                      │
                      ▼
          一次 Query Embedding
                      │
                      ▼
      四类标签规则 + 相似样例并行检索
                      │
                      ▼
             LangChain 组装上下文
                      │
                      ▼
                GLM 输出 JSON
                      │
                      ▼
             Pydantic 结构与业务校验
                      │
        ┌─────────────┴─────────────┐
        │                           │
高置信度且无安全信号        低置信度或命中安全规则
        │                           │
        ▼                           ▼
    自动通过                  创建人工审核任务
                                    │
                         ┌──────────┴──────────┐
                         │                     │
                    人工确认              人工修正
                         │                     │
                         └──────────┬──────────┘
                                    ▼
                            最终结果回流知识库
```

旁路能力：

- 离线评测：比较 Zero-shot、固定 Few-shot、RAG；
- Red Team：回归测试注入、越狱、敏感诱导和隐私请求；
- FastAPI：对外提供分类、审核、安全和统计接口；
- Streamlit：提供面试演示界面；
- Docker Compose：统一启动 API 和 UI。

## 3. 阶段一：标签体系和数据 Schema

### 目的

先确定“系统处理的数据长什么样”和“标签有哪些”，避免后续代码各自使用不同字段。

### 输入与输出

- 输入：业务中的创意写作 Prompt 和人工分类经验；
- 输出：标签枚举、PromptRecord、JSON Schema、taxonomy。

### 核心代码

建议按下面顺序阅读：

1. `data/taxonomy.json`
2. `src/creativebench/models.py`
3. `data/schemas/prompt.schema.json`
4. `tests/test_models.py`
5. `docs/data-schema.md`

### 重点理解

- `scope` 为什么要区分 `creative_writing`、`risk_test` 和 `out_of_scope`；
- 为什么文体、意图、角色和风险都是多标签；
- 为什么 `normal` 不能与其他风险标签同时出现；
- 为什么创意写作至少需要一个文体和一个意图；
- 为什么人工确认样本要求记录审核人和判断依据。

### 面试可能追问

- 标签体系是怎么设计出来的？
- 多标签和单标签分类有什么区别？
- 标签之间存在冲突时如何校验？

## 4. 阶段二：数据导入和清洗

### 目的

将来源不同、字段不同的 CSV 和 JSONL 统一转换为内部结构。

### 流程

```text
读取原始记录
  -> 字段映射
  -> 文本标准化
  -> 空白和控制字符处理
  -> 长度校验
  -> 生成导入元数据
  -> 输出统一 JSONL
```

### 核心代码

1. `src/creativebench/ingestion/models.py`
2. `src/creativebench/ingestion/readers.py`
3. `src/creativebench/ingestion/cleaning.py`
4. `src/creativebench/ingestion/pipeline.py`
5. `src/creativebench/ingestion/cli.py`
6. `tests/test_ingestion.py`
7. `docs/ingestion.md`

### 重点理解

- Reader、Cleaner、Pipeline 为什么分开；
- 为什么保存 `original_length`、`cleaned_length` 和清洗操作；
- 为什么清洗规则必须是确定性的；
- 同一份输入重复导入时，如何保证结果可复现。

### 运行

```bash
creativebench-import data/examples/raw_prompts.csv
```

## 5. 阶段三：三层去重

### 目的

识别完全相同、轻微修改和语义相似的 Prompt，减少重复标注和知识库污染。

### 三层策略

| 层级 | 技术 | 解决的问题 |
|---|---|---|
| 第一层 | SHA-256 | 文本完全一致 |
| 第二层 | SimHash | 标点、空格、少量词语变化 |
| 第三层 | BGE Embedding | 表达不同但语义高度相似 |

### 核心代码

1. `src/creativebench/deduplication/models.py`
2. `src/creativebench/deduplication/fingerprint.py`
3. `src/creativebench/deduplication/embeddings.py`
4. `src/creativebench/deduplication/pipeline.py`
5. `tests/test_deduplication.py`
6. `docs/deduplication.md`

### 重点理解

- 为什么不能只使用 Embedding 去重；
- SimHash 的汉明距离代表什么；
- 语义相似度阈值过高和过低分别有什么问题；
- 为什么去重场景不添加 BGE Query Instruction；
- 为什么要保存代表样本和重复样本之间的关系。

### 运行

```bash
creativebench-deduplicate data/processed/imported_prompts.jsonl --semantic
```

## 6. 阶段四：数据库持久化

### 目的

将 Prompt、导入信息、重复关系、模型分类和人工审核统一保存，形成可追溯的数据状态。

### 主要数据表

- `prompts`：Prompt 主数据；
- `prompt_ingestions`：导入和清洗信息；
- `duplicate_matches`：重复关系；
- `classification_runs`：模型原始分类；
- `review_tasks`：人工审核任务和最终结果。

### 核心代码

1. `src/creativebench/database/models.py`
2. `src/creativebench/database/session.py`
3. `src/creativebench/database/repository.py`
4. `src/creativebench/database/classification_repository.py`
5. `tests/test_database.py`
6. `tests/test_review.py`
7. `docs/database.md`

### Prompt 状态变化

```text
ready_for_labeling
  -> duplicate
  -> labeled
  -> pending_review
  -> labeled
```

状态并不是严格单向。例如重新执行去重时，原来被判定为重复的记录可能恢复为待标注；但已经进入审核或已经完成标注的状态不能被去重任务随意覆盖。

### 重点理解

- 为什么仓储层负责事务内的数据操作；
- 为什么模型原始结果不能被人工修改覆盖；
- 外键、唯一约束和 CheckConstraint 分别解决什么问题；
- 为什么已完成审核不能重复提交。

## 7. 阶段五：知识库构建

### 目的

将稳定的标签规范和动态的人工审核样例转换为可检索知识。

### 两种知识文档

#### label_definition

包含标签代码、定义、适用条件、排除条件和易混淆标签。

#### approved_example

包含 Prompt 原文、人工确认标签和判断依据，用作动态 Few-shot。

### 核心代码

1. `src/creativebench/knowledge/models.py`
2. `src/creativebench/knowledge/builder.py`
3. `src/creativebench/knowledge/store.py`
4. `src/creativebench/knowledge/cli.py`
5. `tests/test_knowledge.py`
6. `docs/knowledge-base.md`

### 重点理解

- 为什么标签定义和样例要使用不同文档类型；
- 为什么一条标签规则或一条样例就是一个完整 Chunk；
- Qdrant Payload 中为什么要保存业务元数据；
- 为什么 Query 添加 BGE 检索指令，而文档入库时不添加；
- 为什么 Qdrant Point ID 要由业务文档 ID 确定性生成。

### 运行

```bash
creativebench-knowledge build
creativebench-knowledge search "请续写一个火星殖民地故事"
```

## 8. 阶段六：LangChain RAG 分类链

### 目的

针对每个新 Prompt，动态检索最相关的标签规则和人工样例，并组装成 GLM 分类上下文。

### 检索流程

```text
Prompt
  -> 只计算一次 Query Embedding
  -> genres 标签检索
  -> intents 标签检索
  -> roles 标签检索
  -> risks 标签检索
  -> approved examples 检索
  -> 合并为 RetrievalBundle
  -> 生成 ChatPromptValue
```

五路检索使用 LangChain `RunnableParallel` 编排，但共享同一份 Query Vector。

### 核心代码

1. `src/creativebench/rag/models.py`
2. `src/creativebench/rag/chain.py`
3. `src/creativebench/rag/cli.py`
4. `tests/test_rag.py`
5. `docs/langchain-rag.md`

### 重点理解

- RAG 返回的是标签候选，不是最终标签；
- 为什么不同标签维度分开检索；
- 为什么只计算一次 Query Embedding；
- 检索分数为什么不能直接当模型置信度；
- Prompt 中如何声明检索文本和用户文本都是数据，不能作为系统指令执行。

### 运行

```bash
creativebench-rag "请续写一个火星殖民地故事"
```

## 9. 阶段七：GLM 结构化分类

### 目的

调用 GLM，将 RAG 上下文转换成经过严格验证的多标签分类结果。

### 流程

```text
ChatPromptValue
  -> GLM OpenAI 兼容接口
  -> JSON Mode
  -> PydanticOutputParser
  -> ClassificationPrediction
  -> 跨字段业务校验
```

### 核心代码

1. `src/creativebench/classification/model.py`
2. `src/creativebench/classification/models.py`
3. `src/creativebench/classification/generation.py`
4. `src/creativebench/classification/service.py`
5. `src/creativebench/classification/cli.py`
6. `tests/test_classification.py`
7. `docs/glm-classification.md`

### 重试边界

```text
RAG 检索一次
  -> 模型生成
  -> 解析失败
  -> 只重试模型生成和解析
  -> 不重复 RAG
```

这样可以保持每次重试使用相同上下文，也避免重复计算 Embedding 和向量检索。

### 重点理解

- JSON Mode 和 Pydantic 校验有什么区别；
- 为什么认证失败和错误请求不应该盲目重试；
- 为什么 LangChain 自带重试被关闭，由应用层统一控制；
- API Key 为什么使用 `SecretStr`；
- 缺少 Key 时为什么要在创建客户端前终止。

## 10. 阶段八：安全预扫描与人工审核

### 目的

在模型调用和自动放行之外增加防御层，避免单纯依赖模型置信度。

### 安全预扫描

核心代码：

1. `src/creativebench/security/models.py`
2. `src/creativebench/security/scanner.py`
3. `src/creativebench/security/benchmark.py`
4. `data/evaluation/security_cases.jsonl`
5. `tests/test_security.py`

识别类型：

- Prompt Injection；
- Instruction Override；
- Roleplay Jailbreak；
- Sensitive Inducement；
- Privacy Request。

规则扫描采用高精度词法匹配，未命中不代表 Prompt 一定安全，因此它是预警机制，不是最终安全判定。

### 审核分流

```text
模型结果
  -> confidence < 0.7？
  -> 安全扫描是否命中？
  -> 任一条件成立：创建 review_task
  -> 否则：自动标记 labeled
```

核心代码：

1. `src/creativebench/database/classification_repository.py`
2. `src/creativebench/review/cli.py`
3. `tests/test_review.py`
4. `docs/human-review.md`

### 重点理解

- 为什么高置信度安全风险也要强制审核；
- 模型置信度为什么不等于真实准确率；
- 人工确认和人工修正如何区分；
- 为什么保留模型原始结果和人工最终结果两份数据。

## 11. 阶段九：审核结果回流

### 目的

将人工确认或修正后的样本作为新的 RAG Few-shot，形成数据闭环。

### 回流准入

允许：

- `human_approved`
- `human_corrected`

禁止：

- `auto_accepted`
- `review_pending`
- 缺少审核人或最终标签的数据

### 核心代码

1. `src/creativebench/review/models.py`
2. `src/creativebench/knowledge/feedback.py`
3. `src/creativebench/knowledge/store.py` 中的 `upsert`
4. `src/creativebench/database/classification_repository.py` 中的导出方法
5. `docs/knowledge-feedback.md`

### 重点理解

- 为什么高置信度模型结果也不能直接回流；
- 错误样本回流为什么会造成知识污染和错误自增强；
- `review-example:{task_id}` 如何保证幂等；
- 全量重建知识库时，如何避免动态审核样本丢失。

## 12. 阶段十：离线评测

### 目的

使用同一份金标准，比较不同 Prompt 策略，而不是凭主观感受选方案。

### 三种策略

#### Zero-shot

只提供任务描述和标签范围。

#### Fixed Few-shot

所有 Prompt 都使用相同的固定人工样例。

#### RAG

每个 Prompt 动态检索相关标签规则和相似样例。

### 指标

- Scope Accuracy；
- Exact Match；
- 各标签维度 Precision、Recall、F1；
- 整体 Micro Precision、Recall、F1；
- 平均响应时间；
- Prompt Token 和 Completion Token。

### 核心代码

1. `src/creativebench/evaluation/models.py`
2. `src/creativebench/evaluation/io.py`
3. `src/creativebench/evaluation/metrics.py`
4. `src/creativebench/evaluation/runner.py`
5. `src/creativebench/evaluation/live.py`
6. `src/creativebench/evaluation/cli.py`
7. `data/evaluation/cases.jsonl`
8. `tests/test_evaluation.py`
9. `docs/evaluation-and-security.md`

### 重点理解

- 多标签任务为什么只看 Accuracy 不够；
- Exact Match 为什么比 Micro F1 更严格；
- 三种策略为什么必须使用相同模型和相同测试集；
- 为什么没有真实 API 运行结果时不能编造简历指标；
- 为什么评测集不能参与 Few-shot 或知识库构建。

### 运行

```bash
creativebench-evaluate run
creativebench-evaluate score
```

当前未填写 GLM Key，`run` 会在模型请求前停止。

## 13. 阶段十一：FastAPI 应用层

### 目的

将分类、审核、安全扫描和统计能力组织为稳定 HTTP 接口。

### API

- `GET /health`
- `POST /api/v1/security/scan`
- `POST /api/v1/classifications`
- `GET /api/v1/reviews`
- `POST /api/v1/reviews/{task_id}`
- `GET /api/v1/stats`

### 核心代码

1. `src/creativebench/api/schemas.py`
2. `src/creativebench/api/runtime.py`
3. `src/creativebench/api/app.py`
4. `src/creativebench/api/cli.py`
5. `tests/test_api.py`
6. `docs/fastapi.md`

### 重点理解

- 为什么使用 Application Factory；
- 为什么 GLM 客户端和 BGE 模型延迟加载；
- 为什么没有 API Key 时服务仍然可以启动；
- 400、409、502、503 分别适合哪些错误；
- 测试中如何注入 Fake Classifier，避免真实网络请求。

## 14. 阶段十二：Streamlit 与部署

### 目的

提供可以在面试中直接操作的演示界面，并让环境能够统一启动。

### 核心代码

1. `src/creativebench/ui/client.py`
2. `ui/streamlit_app.py`
3. `tests/test_ui_client.py`
4. `Dockerfile`
5. `docker-compose.yml`
6. `.dockerignore`
7. `docs/deployment.md`

### 重点理解

- Streamlit 为什么只调用 FastAPI，不直接操作数据库；
- API 与 UI 解耦后有什么好处；
- Docker 镜像为什么不包含 API Key；
- SQLite 和 Qdrant 数据如何通过 Volume 持久化；
- 无 Key 时 Demo 哪些功能仍然可以展示。

### 运行

```bash
creativebench-api
streamlit run ui/streamlit_app.py
```

或者：

```bash
docker compose up --build
```

## 15. 建议的实际学习顺序

不要一次看完所有代码。建议拆成六轮：

### 第一轮：数据基础

阅读阶段 1、2、3，自己运行导入和去重命令。

完成标准：

- 能解释内部数据格式；
- 能解释三层去重的边界；
- 能看懂清洗和去重测试。

### 第二轮：存储与知识库

阅读阶段 4、5，查看 SQLite 表和 Qdrant 文档。

完成标准：

- 能说清数据库五张核心表；
- 能解释标签文档和样例文档的区别；
- 能手动执行知识库检索。

### 第三轮：RAG 与模型分类

阅读阶段 6、7，先运行 `creativebench-rag` 查看最终模型消息，再看 Fake Model 测试。

完成标准：

- 能画出五路检索；
- 能解释为什么 Query Embedding 只算一次；
- 能解释结构化输出和重试边界。

### 第四轮：审核闭环

阅读阶段 8、9。

完成标准：

- 能解释低置信度分流；
- 能解释安全信号强制审核；
- 能解释为什么只回流人工审核结果。

### 第五轮：评测和安全

阅读阶段 10，以及安全扫描相关代码。

完成标准：

- 能手算一组 Precision、Recall、F1；
- 能区分 Prompt Injection、Instruction Override 和 Roleplay Jailbreak；
- 能说明规则基准满分不代表真实泛化能力。

### 第六轮：应用交付

阅读阶段 11、12，启动 API 和 Streamlit。

完成标准：

- 能通过 Swagger 调接口；
- 能说明无 Key 降级；
- 能解释 Docker 中 API、UI 和数据卷的关系。

## 16. 面试口述前需要准备的内容

理解代码后，再将项目整理为 3 分钟和 8 分钟两个版本。正式话术至少要覆盖：

1. 业务背景：为什么要把人工 Prompt 标注工程化；
2. 个人职责：数据处理、知识库、RAG、分类、审核、评测分别做了什么；
3. 核心链路：Prompt 如何从导入一直走到人工审核和知识回流；
4. 技术亮点：三层去重、五路 RAG、结构化校验、审核闭环；
5. 安全设计：注入防护、强制审核、知识污染控制；
6. 评测方案：如何公平比较 Zero-shot、Few-shot 和 RAG；
7. 工程设计：事务、状态机、幂等、延迟加载、依赖注入；
8. 真实边界：哪些来源于实际数据标注工作，哪些是个人工程化重构；
9. 实验结果：只使用真实 GLM 调用后得到的数据；
10. 复盘改进：如果数据量和调用量扩大，如何迁移到 PostgreSQL、独立 Qdrant、任务队列和异步批处理。

不要急着背话术。建议每完成一轮代码阅读，先尝试不看文档讲一遍“输入、处理、输出、异常情况”，再进入下一轮。全部理解后，再基于真实掌握程度整理最终口述稿。
