# GLM 结构化分类层

第 9 步在现有 RAG 链之后增加 GLM 分类与 Pydantic 校验，但暂不填写 API Key，也不发送真实模型请求。

## 调用边界

```text
用户 Prompt
  -> RAG 检索（只执行一次）
  -> GLM 生成 JSON
  -> Pydantic 解析和业务规则校验
       -> 成功：返回 ClassificationRun
       -> 可重试错误：只重试 GLM + 解析，最多 3 次
       -> 用尽次数：抛出 ClassificationError
```

RAG 不放在重试循环中，因为标签定义和相似样例在同一次分类任务内不会变化。这样可以减少重复 Embedding 与向量检索，并保持每次模型重试使用相同上下文。

## 为什么仍需 Pydantic 校验

GLM 的 JSON 模式只约束输出是合法 JSON，不能完整保证业务规则。例如：

- `normal` 不能与 `prompt_injection` 同时出现；
- 创意写作必须至少有一个文体和创作意图；
- 安全测试不能只输出 `normal`；
- 标签必须来自项目枚举，置信度必须在 0 到 1 之间。

因此模型输出必须经过 `ClassificationPrediction` 二次校验，不能直接写入数据库。

## 当前离线验证范围

- Fake Model 第一次返回非法文本、第二次返回合法 JSON；
- 验证模型调用两次时 RAG 只调用一次；
- 验证连续解析失败会转换为统一的业务异常；
- 验证 API Key 为空时，在创建客户端前明确失败；
- 不进行任何真实 GLM 网络请求。

## 最后联调时再执行

在本地 `.env` 中填写：

```dotenv
CREATIVEBENCH_GLM_API_KEY=你的本地密钥
```

然后再运行：

```bash
creativebench-classify "请续写一个发生在火星殖民地的悬疑故事"
```

当前默认模型为 `glm-4-flash-250414`，模型名和兼容接口地址都可以通过环境变量替换。
