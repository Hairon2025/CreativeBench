# CreativeBench 分阶段代码阅读指南

不要从 README 开始逐文件硬啃。建议按下面顺序，每阶段先看测试，再看领域模型和实现，最后运行对应命令。

## 阶段 1：项目配置与数据 Schema

- `src/creativebench/config.py`：环境变量和默认值；
- `src/creativebench/models.py`：标签枚举、PromptRecord、跨字段规则；
- `data/taxonomy.json`：标签定义；
- `tests/test_models.py`：Schema 边界。

需要掌握：为什么枚举标签、为什么禁止 `normal` 与风险标签共存、为什么人工审核记录需要审计字段。

## 阶段 2：导入与确定性清洗

- `src/creativebench/ingestion/readers.py`；
- `src/creativebench/ingestion/cleaning.py`；
- `src/creativebench/ingestion/pipeline.py`；
- `tests/test_ingestion.py`。

需要掌握：输入格式统一、清洗可追溯、无效数据处理和幂等输出。

## 阶段 3：三层去重

- `src/creativebench/deduplication/fingerprint.py`；
- `src/creativebench/deduplication/embeddings.py`；
- `src/creativebench/deduplication/pipeline.py`；
- `tests/test_deduplication.py`。

需要掌握：SHA-256、SimHash、Embedding 分别解决什么重复；阈值如何选择；为什么去重 Embedding 不使用检索指令。

## 阶段 4：关系数据库

- `src/creativebench/database/models.py`；
- `src/creativebench/database/repository.py`；
- `src/creativebench/database/session.py`；
- `tests/test_database.py`。

需要掌握：事务、外键、唯一约束、upsert、重复关系和 Prompt 状态机。

## 阶段 5：知识库构建

- `src/creativebench/knowledge/builder.py`；
- `src/creativebench/knowledge/store.py`；
- `src/creativebench/knowledge/models.py`；
- `tests/test_knowledge.py`。

需要掌握：为什么标签规则和审核样例分成两类文档、为什么不继续切块、BGE query instruction、Qdrant payload 和过滤检索。

## 阶段 6：LangChain RAG

- `src/creativebench/rag/chain.py`；
- `src/creativebench/rag/models.py`；
- `tests/test_rag.py`。

需要掌握：一次 Embedding、五路检索、RunnableParallel、候选标签与最终分类的区别、如何防止检索文本变成可执行指令。

## 阶段 7：GLM 结构化分类

- `src/creativebench/classification/model.py`；
- `src/creativebench/classification/models.py`；
- `src/creativebench/classification/service.py`；
- `tests/test_classification.py`。

需要掌握：OpenAI 兼容接口、JSON mode 与 Pydantic 的区别、可重试和不可重试错误、为什么重试模型时不重复 RAG。

## 阶段 8：人工审核

- `src/creativebench/database/classification_repository.py`；
- `src/creativebench/review/cli.py`；
- `tests/test_review.py`。

需要掌握：低置信度分流、安全信号强制审核、模型原始结果与人工最终结果分开保存、状态不可重复提交。

## 阶段 9：审核回流

- `src/creativebench/knowledge/feedback.py`；
- `src/creativebench/review/models.py`；
- `src/creativebench/knowledge/store.py` 的 `upsert`；
- `docs/knowledge-feedback.md`。

需要掌握：为什么高置信度模型预测也不能直接回流、确定性 ID 如何保证幂等、如何避免知识污染和错误自增强。

## 阶段 10：离线评测

- `src/creativebench/evaluation/models.py`；
- `src/creativebench/evaluation/metrics.py`；
- `src/creativebench/evaluation/runner.py`；
- `tests/test_evaluation.py`。

需要掌握：多标签 precision/recall/F1、完全匹配率、相同金标准下比较 Zero-shot/Few-shot/RAG、为什么没有真实运行不能把指标写进简历。

## 阶段 11：Red Team 安全

- `src/creativebench/security/scanner.py`；
- `src/creativebench/security/benchmark.py`；
- `data/evaluation/security_cases.jsonl`；
- `tests/test_security.py`。

需要掌握：注入、指令覆盖和角色越狱的区别；规则扫描的高精度定位；规则未命中为什么不代表安全。

## 阶段 12：API、界面与部署

- `src/creativebench/api/app.py`；
- `src/creativebench/api/runtime.py`；
- `src/creativebench/ui/client.py`；
- `ui/streamlit_app.py`；
- `Dockerfile` 与 `docker-compose.yml`；
- `tests/test_api.py`。

需要掌握：依赖注入、延迟加载、HTTP 状态码、UI 与业务解耦、无 API Key 降级、容器数据与密钥管理。
