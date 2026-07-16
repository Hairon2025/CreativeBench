# Prompt 分层去重

第 5 步在清洗后的标准文本上执行三层去重。

## 检测顺序

```text
SHA-256 完全重复
        ↓ 未命中
SimHash 近似文本重复
        ↓ 未命中
Embedding 语义重复
```

顺序由低成本到高成本排列。第一条记录作为代表记录，后续重复项只写入重复关系报告，不直接删除原始输入。

## 1. 完全重复

对清洗后的完整文本计算 SHA-256。Hash 相同表示文本完全一致。

优点是速度快、结果稳定；缺点是无法识别一个标点或词语发生变化的文本。

## 2. 近似文本重复

先移除空白和标点，再提取中文字符 3-gram，最后计算 64 位 SimHash。两个指纹之间使用汉明距离比较，默认距离不超过 8 判为近似重复。

该层适合识别标点变化、少量增删字和局部格式差异。阈值越大，召回越高，误判风险也越高。

## 3. 语义重复

使用 Embedding 将 Prompt 转为向量，再通过余弦相似度判断语义是否接近。默认模型为 `BAAI/bge-small-zh-v1.5`，当前演示阈值为 0.80。

0.80 来自当前小样本校准：目标改写对得分 0.8098，样例中的非重复对均低于 0.60。该数字不是通用阈值，语义命中只进入疑似重复报告，不自动删除；后续必须使用金标准集评估 Precision、Recall 后重新确定。

语义模型属于可选依赖：

```bash
pip install -e ".[semantic]"
```

不传 `--semantic` 时只执行 SHA-256 和 SimHash，不加载模型。

## 运行

```bash
creativebench-import \
  data/examples/raw_prompts_with_duplicates.csv \
  --output data/processed/dedup_input.jsonl

creativebench-deduplicate data/processed/dedup_input.jsonl

creativebench-deduplicate \
  data/processed/dedup_input.jsonl \
  --semantic
```

输出分为：

- `deduplicated_prompts.jsonl`：保留下来的代表记录；
- `duplicate_report.jsonl`：重复记录、代表记录、命中方式和分数。

## 当前复杂度

MVP 为了便于理解和验证，使用代表记录之间的顺序比较，最坏时间复杂度为 O(n²)。正式处理大规模数据时，完全重复可使用 Hash 索引，SimHash 可使用分桶，Embedding 应使用向量索引召回候选集。
