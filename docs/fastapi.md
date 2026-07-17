# FastAPI 应用层

FastAPI 使用应用工厂创建，启动时只初始化数据库，不创建 GLM 客户端、不加载 BGE 模型。真实分类请求到达后才延迟创建模型客户端和 Embedding Provider。

## 接口

- `GET /health`：服务状态、模型配置状态；
- `POST /api/v1/security/scan`：离线安全预扫描；
- `POST /api/v1/classifications`：RAG + GLM 分类，可选持久化；
- `GET /api/v1/reviews`：待审核队列；
- `POST /api/v1/reviews/{task_id}`：确认或修正；
- `GET /api/v1/stats`：数据、分类和审核统计。

当没有 API Key 时，除分类接口返回 `503` 外，健康检查、安全扫描、审核和统计均可正常使用。

如果安全预扫描命中风险，即使模型置信度高于阈值，持久化结果也会强制进入人工审核，避免把模型置信度当作安全放行依据。

```bash
python -m pip install -e ".[app]"
creativebench-api
```

启动后访问 `http://localhost:8000/docs` 查看 Swagger。
