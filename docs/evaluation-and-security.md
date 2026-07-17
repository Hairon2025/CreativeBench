# 离线评测与 Red Team 安全预扫描

## 分类评测

评测输入由金标准 `cases.jsonl` 和不同策略生成的 `predictions.jsonl` 分离保存。这样同一份人工金标准可以比较：

- `zero_shot`：只提供标签代码和任务说明；
- `fixed_few_shot`：所有样本使用相同固定示例；
- `rag`：按当前 Prompt 动态检索标签规则和相似审核样例。

指标包括 scope accuracy、四维标签完全匹配率、各维度及整体 micro precision/recall/F1、平均延迟与 token 用量。

没有 GLM API Key 时只验证指标代码和数据格式，不生成或伪造三种方案的实验结果。填写 Key 后，把真实预测保存到 `data/evaluation/predictions.jsonl`，再运行：

```bash
creativebench-evaluate run
```

该命令会用相同模型依次生成三种策略的预测并保存原始结果。也可以对已有预测重新计算指标：

```bash
creativebench-evaluate score
```

只有真实运行得到的报告才可以写入简历。

## 安全预扫描

安全扫描在 RAG 和 GLM 前执行，用高精度词法规则识别：

- 指令覆盖；
- Prompt 注入；
- 角色扮演越狱；
- 可执行伤害内容诱导；
- 真实个人隐私请求。

```bash
creativebench-security scan "忽略之前所有系统指令"
creativebench-security benchmark
```

规则未命中不代表 Prompt 一定安全，因此扫描结果是模型分类与人工审核之前的防御补充，不是最终安全判定。
