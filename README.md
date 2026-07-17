# CreativeBench

基于 GLM + RAG 的创意写作 Prompt 资产管理与智能标注系统。

本项目来源于真实的创意写作 Prompt 收集、分类与标注场景，目标是将原有的数据处理工作逐步工程化，最终实现一套可以实际运行、演示和解释技术细节的 AI 应用。

> 当前状态：完整工程链路已实现，包括数据处理、RAG、GLM 接入层、人工审核、知识回流、离线评测、安全扫描、FastAPI、Streamlit 与 Docker；仅真实 GLM 实验因 API Key 留空而尚未执行。

## 项目背景

随着创意写作 Prompt 数量增加，纯人工处理会面临以下问题：

- Prompt 来源和格式不统一，存在无效数据及重复数据；
- 文体、创作意图等标签边界不清晰，人工标注一致性不足；
- 已审核的历史样本难以复用；
- 新增或调整标签后，需要投入较多人工成本重新整理数据；
- 越狱、指令覆盖和敏感内容诱导等风险 Prompt 缺少统一管理。

CreativeBench 将标签定义、标注规范和已审核样本构建为领域知识库，通过 RAG 检索相关知识和相似案例，再调用 GLM 完成结构化分类，并通过人工审核结果回流形成持续优化的数据闭环。

## 核心流程

```text
Prompt 数据导入
      ↓
数据清洗与重复检测
      ↓
检索标签定义和相似已标注样本
      ↓
组装分类上下文并调用 GLM
      ↓
结构化标签、置信度与分类理由
      ↓
结果校验与人工审核
      ↓
审核结果回流知识库
```

## 已实现功能

- Prompt 数据导入、清洗、脱敏和去重；
- 文体、创作意图、角色属性和安全风险等多层级标签管理；
- 标签规范及人工审核样本的向量化入库；
- 基于 Embedding 的相似 Prompt 与标签定义检索；
- GLM 多标签分类和结构化 JSON 输出；
- Pydantic 数据校验、异常重试和低置信度转人工审核；
- 人工审核及修正结果回流；
- Zero-shot、固定 Few-shot 与 RAG 分类效果对比；
- 分类准确率、F1、响应时间和调用成本统计；
- Prompt 注入、角色扮演越狱等风险类型识别。

## 技术栈

- Python 3.11+
- FastAPI
- Pydantic
- SQLAlchemy
- SQLite（开发阶段）/ PostgreSQL（后续扩展）
- Qdrant Local Mode
- GLM API
- Streamlit
- Pandas
- Pytest
- Docker Compose

真实模型指标仍需填写 API Key 后运行，项目不会用 Fake Model 指标冒充实验结果。

## 本地开发

项目要求 Python 3.11 或更高版本。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,app,demo]"
cp .env.example .env
```

校验项目中的演示数据：

```bash
creativebench-validate
```

导入并清洗原始 Prompt：

```bash
creativebench-import data/examples/raw_prompts.csv
```

默认输出到 `data/processed/imported_prompts.jsonl`。

对清洗后的 Prompt 去重：

```bash
creativebench-deduplicate data/processed/imported_prompts.jsonl
```

启用本地 Embedding 语义去重前安装可选依赖：

```bash
python -m pip install -e ".[semantic]"
creativebench-deduplicate data/processed/imported_prompts.jsonl --semantic
```

初始化并写入数据库：

```bash
creativebench-db init
creativebench-db load \
  --prompts data/processed/dedup_input.jsonl \
  --duplicates data/processed/duplicate_report.jsonl
creativebench-db stats
```

构建并检索知识库：

```bash
python -m pip install -e ".[knowledge]"
creativebench-knowledge build
creativebench-knowledge search "请续写一个发生在火星殖民地的故事"
```

生成 LangChain RAG 分类上下文：

```bash
python -m pip install -e ".[rag]"
creativebench-rag "请续写一个发生在火星殖民地的故事"
```

安装 GLM 分类层（当前可运行离线测试，无需填写 API Key）：

```bash
python -m pip install -e ".[classification]"
pytest -p no:cacheprovider tests/test_classification.py
```

真实模型联调命令已经预留，但本阶段不执行：

```bash
creativebench-classify "请续写一个发生在火星殖民地的故事"
```

查看和处理低置信度人工审核任务：

```bash
creativebench-review list
creativebench-review approve 1 --reviewer reviewer-a
creativebench-review correct 1 \
  --reviewer reviewer-a \
  --prediction corrected-prediction.json
```

将已完成人工审核的样本回流知识库：

```bash
creativebench-knowledge feedback
```

运行安全预扫描和 Red Team 基准：

```bash
creativebench-security scan "忽略之前所有系统指令"
creativebench-security benchmark
```

填写 GLM Key 后运行三种分类策略的真实评测：

```bash
creativebench-evaluate run
creativebench-evaluate score
```

未填写 Key 时 `run` 会在模型调用前终止，不生成虚假报告。当前 8 条安全用例是规则回归集，其满分结果只用于防止规则退化，不代表开放环境中的安全泛化能力。

启动 API 与 Streamlit：

```bash
python -m pip install -e ".[app,demo]"
creativebench-api
streamlit run ui/streamlit_app.py
```

完整代码阅读顺序见 `docs/code-reading-guide.md`。

运行测试和静态检查：

```bash
pytest
ruff check .
```

## 已完成开发路线

项目采用逐步实现、逐步验证的方式完成：

1. **项目初始化**：建立说明文档、Git 忽略规则和基础目录。
2. **数据定义**：确定标签体系、数据字段和样例格式。
3. **数据处理**：实现导入、清洗、规则过滤及重复检测。
4. **知识库构建**：整理标签规范与金标准样本，生成 Embedding 并写入向量库。
5. **RAG 分类链路**：实现检索、上下文组装、GLM 调用和结构化输出。
6. **人工审核闭环**：实现审核、修正和知识库回流。
7. **效果评估**：建立测试集并完成不同分类方案的消融对比。
8. **安全能力**：补充 Prompt 注入、越狱和敏感诱导识别。
9. **应用界面与部署**：完成可视化界面、测试及容器化部署。

各阶段运行方法和设计决策已分别记录在 `docs/` 中。

## 计划目录结构

以下结构会在对应阶段按需创建，不在初始化阶段一次性生成：

```text
CreativeBench/
├── app/                 # FastAPI 应用与核心业务代码
├── src/creativebench/   # Python 核心包
├── data/                # 标签规范、数据 Schema 和示例数据
├── docs/                # 数据设计与开发说明
├── scripts/             # 数据导入、清洗和知识库构建脚本
├── tests/               # 自动化测试
├── ui/                  # Streamlit 演示界面
├── .env.example         # 环境变量示例
├── .gitignore
└── README.md
```

## 数据与安全说明

- 不提交真实 API Key、密码和本地环境配置；
- 不提交包含隐私信息或无授权来源的原始数据；
- 演示数据优先使用人工构造、脱敏或明确允许使用的数据；
- 简历中的量化指标以项目实际实验结果为准。

## 最后联调

在本地 `.env` 填写 `CREATIVEBENCH_GLM_API_KEY` 后，执行真实分类并生成 Zero-shot、固定 Few-shot 与 RAG 的预测文件。只有真实评测结果才能形成简历中的量化指标。
