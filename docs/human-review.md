# 低置信度人工审核闭环

第 10 步将模型分类结果写入数据库，并根据置信度决定自动通过还是进入人工审核队列。本阶段使用 Fake Model 结果验证，不调用真实 GLM。

## 数据流

```text
ClassificationRun
  -> 保存模型原始预测 classification_runs
  -> confidence < threshold?
       -> 否：auto_accepted，Prompt 标记为 labeled
       -> 是：创建 review_tasks，Prompt 标记为 pending_review
            -> 人工确认：human_approved
            -> 人工修改：human_corrected
            -> Prompt 标记为 labeled
```

默认低置信度阈值为 `0.7`。判断条件使用严格小于，因此置信度等于阈值时可以自动通过。

## 为什么保存两份结果

`classification_runs.prediction` 是模型原始输出，审核后不允许覆盖；`review_tasks.final_prediction` 是最终采用的标签。这样可以追溯模型错误，并在后续评估模型准确率、整理难例和回流知识库时比较两者差异。

## 审核命令

列出待审核任务：

```bash
creativebench-review list
```

确认模型结果：

```bash
creativebench-review approve 1 --reviewer reviewer-a --notes "模型判断正确"
```

提交修正后的完整分类 JSON：

```bash
creativebench-review correct 1 \
  --reviewer reviewer-a \
  --prediction corrected-prediction.json
```

修正 JSON 必须先通过 `ClassificationPrediction` 的枚举、置信度和跨字段业务规则校验。
