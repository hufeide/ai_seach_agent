# AI Search Agent: LangGraph + SearXNG + Crawl4AI + vLLM + BGE DB

这是一个联网搜索智能体项目骨架，已按你的要求做了 4 个改动：

1. 去掉 Ollama，改用 vLLM 部署的 OpenAI-compatible API。
2. 联网代理默认使用：
   ```bash
   export http_proxy="socks5://192.168.1.159:10808"
   export https_proxy="socks5://192.168.1.159:10808"
   ```
3. 向量检索使用自部署 BGE 数据库 / 检索服务，通过 HTTP adapter 接入。
4. 项目已整理为可打包文件夹结构。

## 目录结构

```text
ai-search-agent-vllm-bge/
├── README.md
├── pyproject.toml
├── docker-compose.yml
├── .env.example
├── searxng/
│   └── settings.yml
├── scripts/
│   └── run_api.sh
├── examples/
│   └── curl_search.sh
└── src/
    └── ai_search_agent/
        ├── __init__.py
        ├── api.py
        ├── bge_db.py
        ├── config.py
        ├── crawler.py
        ├── graph.py
        ├── http_client.py
        ├── llm.py
        ├── searxng.py
        └── text.py
```

## 架构

```text
User Question
  ↓
LangGraph: plan_queries
  ↓
SearXNG: search web
  ↓
Crawl4AI: crawl pages
  ↓
BGE DB: upsert crawled chunks + vector search
  ↓
LLM: select evidence
  ↓
LLM: answer with citations
```

## 1. 准备 Python 环境

```bash
cd ai-search-agent-vllm-bge
python -m venv .venv
source .venv/bin/activate
pip install -e .
crawl4ai-setup
```

如果 Crawl4AI / Playwright 安装浏览器失败，可以手动执行：

```bash
python -m playwright install chromium
```

## 2. 启动 SearXNG

```bash
docker compose up -d searxng
```

`searxng/settings.yml` 已启用 JSON：

```yaml
search:
  formats:
    - html
    - json
```

## 3. 准备 vLLM

这个项目默认调用：

```text
VLLM_BASE_URL=http://127.0.0.1:8000/v1
VLLM_MODEL=qwen2.5-7b-instruct
```

示例 vLLM 启动命令：

```bash
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-7B-Instruct \
  --served-model-name qwen2.5-7b-instruct \
  --host 0.0.0.0 \
  --port 8000
```

也可以换成 Llama：

```bash
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3.1-8B-Instruct \
  --served-model-name llama3.1-8b-instruct \
  --host 0.0.0.0 \
  --port 8000
```

对应修改 `.env`：

```bash
VLLM_MODEL=llama3.1-8b-instruct
```

## 4. 配置代理和服务地址

```bash
cp .env.example .env
```

默认代理已经写入 `.env.example` 和 `scripts/run_api.sh`：

```bash
HTTP_PROXY=socks5://192.168.1.159:10808
HTTPS_PROXY=socks5://192.168.1.159:10808
```

如果 vLLM、SearXNG、BGE DB 在本机或内网，建议保持：

```bash
NO_PROXY=localhost,127.0.0.1,::1,192.168.0.0/16,10.0.0.0/8
```

## 5. BGE 数据库接口约定

项目默认假设你的自部署 BGE 数据库 / 检索服务提供两个 HTTP 接口。

### 5.1 Upsert

请求：

```http
POST {BGE_DB_BASE_URL}{BGE_DB_UPSERT_PATH}
```

默认：

```text
POST http://127.0.0.1:9000/upsert
```

Payload：

```json
{
  "collection": "web_search",
  "documents": [
    {
      "id": "doc_id",
      "text": "chunk text",
      "metadata": {
        "title": "page title",
        "url": "https://example.com",
        "chunk_index": 1,
        "source": "web"
      }
    }
  ]
}
```

### 5.2 Search

请求：

```http
POST {BGE_DB_BASE_URL}{BGE_DB_SEARCH_PATH}
```

默认：

```text
POST http://127.0.0.1:9000/search
```

Payload：

```json
{
  "collection": "web_search",
  "query": "用户问题",
  "top_k": 8,
  "filters": {}
}
```

返回支持两种格式。

格式 1：

```json
{
  "results": [
    {
      "id": "doc_id",
      "text": "matched chunk",
      "score": 0.87,
      "metadata": {
        "title": "page title",
        "url": "https://example.com"
      }
    }
  ]
}
```

格式 2：

```json
[
  {
    "id": "doc_id",
    "text": "matched chunk",
    "score": 0.87,
    "metadata": {
      "title": "page title",
      "url": "https://example.com"
    }
  }
]
```

如果你的 BGE DB 接口不是这个格式，只需要改：

```text
src/ai_search_agent/bge_db.py
```

或者在 `.env` 里修改：

```bash
BGE_DB_BASE_URL=http://your-bge-db:9000
BGE_DB_UPSERT_PATH=/your/upsert/path
BGE_DB_SEARCH_PATH=/your/search/path
```

调试时可以临时关闭 BGE DB：

```bash
BGE_DB_ENABLED=false
```

关闭后 Agent 会直接使用 Crawl4AI 抓到的网页正文作为证据候选。

## 6. 启动 API

```bash
./scripts/run_api.sh
```

API 默认启动在：

```text
http://127.0.0.1:18000
```

健康检查：

```bash
curl http://127.0.0.1:18000/health
```

搜索测试：

```bash
./examples/curl_search.sh
```

或：

```bash
curl -X POST "http://127.0.0.1:18000/search-agent" \
  -H "Content-Type: application/json" \
  -d '{"question":"最近 LangGraph 的 StateGraph 主要怎么用？","mode":"deep"}'
```

## 7. 关键环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `VLLM_BASE_URL` | `http://127.0.0.1:8000/v1` | vLLM OpenAI-compatible API 地址 |
| `VLLM_API_KEY` | `EMPTY` | vLLM 默认可用假 key |
| `VLLM_MODEL` | `qwen2.5-7b-instruct` | vLLM served model name |
| `SEARXNG_URL` | `http://127.0.0.1:8080/search` | SearXNG 搜索接口 |
| `HTTP_PROXY` | `socks5://192.168.1.159:10808` | HTTP 代理 |
| `HTTPS_PROXY` | `socks5://192.168.1.159:10808` | HTTPS 代理 |
| `BGE_DB_BASE_URL` | `http://127.0.0.1:9000` | 自部署 BGE DB 地址 |
| `BGE_DB_COLLECTION` | `web_search` | 向量集合名 |
| `BGE_DB_TOP_K` | `8` | BGE 检索 top_k |
| `MAX_SEARCH_RESULTS` | `10` | SearXNG 搜索结果数 |
| `MAX_CRAWL_PAGES` | `6` | Crawl4AI 抓取网页数 |
| `MAX_ITERATIONS` | `2` | deep 模式最大搜索轮数 |

## 8. 主流程代码位置

LangGraph 主流程在：

```text
src/ai_search_agent/graph.py
```

节点：

```text
plan_queries
search
crawl
bge_upsert_and_search
select_evidence
answer
```

## 9. 常见问题

### SearXNG 返回 403

通常是 JSON API 没启用。确认：

```yaml
search:
  formats:
    - html
    - json
```

### vLLM 返回模型不存在

确认 `VLLM_MODEL` 和 vLLM 启动时的 `--served-model-name` 一致。

### vLLM JSON 模式不稳定

`llm.py` 已经做了 JSON fallback，会从模型输出中提取第一个 JSON object。若你的模型模板不支持 OpenAI `response_format`，可以在 `llm.py` 里把 `json_mode=True` 时的 `response_format` 删除。

### BGE DB 接口不匹配

改 `src/ai_search_agent/bge_db.py` 的 `upsert_pages()` 和 `search()` 即可。

## 10. 生产化建议

- 给 SearXNG、BGE DB、vLLM 加鉴权。
- 加 URL 级缓存，避免重复抓取网页。
- 给 Crawl4AI 加站点黑名单和速率限制。
- 对搜索结果做来源可信度评分。
- 对新闻、价格、政策类问题强制加入时间约束。

## Web UI：搜索、查看数据源、点击抓取网页正文

本项目已内置一个无需前端构建工具的网页 UI。

启动 API 后访问：

```bash
http://127.0.0.1:8001/
```

页面能力：

1. **智能搜索**：调用 `/search-agent`，完成 query 规划、SearXNG 搜索、Crawl4AI 抓取、BGE DB 检索和 vLLM 生成答案。
2. **只找数据源**：调用 `/search-sources`，只通过 SearXNG 返回搜索结果，不走 LLM。
3. **点击查看网页内容**：点击任意数据源卡片后，调用 `/fetch-page`，使用 Crawl4AI 抓取该 URL 的正文并展示在右侧。

新增接口：

```text
GET  /
POST /search-sources
POST /fetch-page
```

`/search-sources` 请求示例：

```bash
curl -X POST http://127.0.0.1:8001/search-sources \
  -H "Content-Type: application/json" \
  -d '{"query":"LangGraph StateGraph"}'
```

`/fetch-page` 请求示例：

```bash
curl -X POST http://127.0.0.1:8001/fetch-page \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","title":"example"}'
```


cd /home/aixz/data/hxf/bigmodel/ai_code/ai-search-agent-vllm-bge
source .venv/bin/activate
sudo ./scripts/setup_privoxy.sh 10808
bash scripts/run_api.sh