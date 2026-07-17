# Streamlit Demo 与容器化部署

Streamlit 只通过 HTTP 调用 FastAPI，不直接连接 SQLite、Qdrant 或 GLM。这样 UI 可以替换，核心业务规则仍集中在 API 和领域服务中。

## 本地启动

终端一：

```bash
python -m pip install -e ".[app,demo]"
creativebench-api
```

终端二：

```bash
streamlit run ui/streamlit_app.py
```

- Swagger：`http://localhost:8000/docs`
- Streamlit：`http://localhost:8501`

没有 GLM Key 时，界面仍可演示健康检查、安全扫描、审核队列和统计；点击真实分类会展示 API 返回的未配置提示。

## Docker Compose

```bash
docker compose up --build
```

如需真实分类，在启动前通过本机环境变量注入：

```bash
export CREATIVEBENCH_GLM_API_KEY=你的密钥
docker compose up --build
```

Key 不写入镜像、Compose 文件或 Git。SQLite 与 Qdrant 运行数据使用命名卷持久化。
