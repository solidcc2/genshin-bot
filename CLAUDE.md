# CLAUDE.md

本文件为 Claude Code 在操作此仓库时提供上下文指引。

## 常用命令

> **重要：** 所有 Python 命令都必须在虚拟环境中运行。先执行 `source .venv/bin/activate`，或使用 `.venv/bin/` 前缀（如 `.venv/bin/pytest`）。

```bash
# 激活虚拟环境
source .venv/bin/activate

# 安装依赖（dev 包含 pytest、httpx）
pip install -e ".[dev]"

# 运行全部测试
pytest

# 运行单个测试
pytest tests/test_config.py::test_loads_config_file_and_env_override -v

# 启动应用（HTTP 服务）
python -m app --config configs/dev.json

# 启动应用 + CLI 交互模式
python -m app --config configs/dev.json --cli

# 非交互式冒烟测试（干净退出、无异常告警）
printf "/help\n/echo hello\n/notes\n/sign\n/stats\n/hoyounbind\n/quit\n" | python -m app --config configs/dev.json --cli 2>&1

# 健康检查（需先启动应用）
curl http://127.0.0.1:8000/healthz
```

## 项目结构

```
app/                  # 应用包
├── __main__.py       # 入口：调用 bootstrap.main()
├── bootstrap.py      # Application 类、build_application()、async_main()
├── config.py         # ConfigLoader — 配置加载链：默认值 → JSON 文件 → 环境变量
├── event_model.py    # NormalizedEvent、Scene、ReplyTarget、MessageSender Protocol
├── plugin.py         # BotPlugin ABC、PluginContext、PluginResult、PluginRegistry
├── router.py         # Router — 按序 match → handle 分发
├── plugins/          # 内置最小插件
│   ├── echo.py       #   EchoPlugin — 回显
│   ├── ping.py       #   PingPlugin — 连通性检查
│   └── help.py       #   HelpPlugin — 命令列表
├── adapters/         # 消息接入适配器
│   └── __init__.py   #   CLIAdapter、CLIMessageSender
├── runtime.py        # AppContext、RuntimeState、ServiceRegistry
├── http.py           # HealthService — FastAPI 应用 + uvicorn runner
├── logging.py        # JSON 结构化日志输出到 stdout
└── errors.py         # BootstrapError 异常层次
tests/                # pytest 测试
configs/              # JSON 配置文件
docs/                 # 架构文档
```

## 架构与约定

### 当前阶段

- **CP1** — 运行时基础骨架（启动入口、配置、日志、健康检查）
- **CP2** — 统一事件模型与插件执行主线（NormalizedEvent、BotPlugin、Router）
- CLI adapter 作为开发期工具，`--cli` 参数启动

### 提交命名约定

`CP`（Checkpoint）前缀仅用于既定的 checkpoint 计划提交。插入的优化、修复、重构等非计划内变更**不应**使用 `CP` 编号，直接用自然语言描述即可。

### 消息通道架构

```
消息来源 → NormalizedEvent → Router.dispatch()
                                ├─ 命中 /cmd → Plugin.handle()
                                └─ 无匹配 (None) → 预留 LLM 兜底
```

接入无关：`NormalizedEvent` 和 `MessageSender` Protocol 保证所有 adapter 可共享同一套插件。
当前支持的接入：HTTP（健康检查）、CLI（`--cli`）。未来可扩展：QQ/OneBot、Webhook 等。

### 插件开发约定

- **指令格式**：插件以 `/cmd` 作为规范匹配形式（`/help`、`/ping`、`/echo`），Router 依赖 `match()` 多态，不感知 `/` 前缀
- **注册顺序即优先级**：先注册的插件先匹配，首个命中即执行
- **确定性回复**：插件应处理确定的、可测试的逻辑；开放性对话留给 LLM 兜底
- **插件上下文**：PluginContext 包含 event、sender、config、logger，不依赖任何 adapter 细节

### 配置系统

三层合并策略：默认值 → JSON 配置文件 → 环境变量（`APP_*` 前缀）。校验后转为冻结 dataclass（`AppConfig`、`HTTPConfig`）。

### 错误层次

- `BootstrapError` — 所有启动失败的基类
  - `ConfigError` — 配置加载/校验失败
  - `ServiceRegistrationError` — 重复注册服务
  - `ApplicationStateError` — 生命周期使用不当
  - `HealthServiceError` — HTTP 服务启动失败
  - `PluginError` — 插件 match/handle 异常
  - `RouterError` — 路由分发异常

## 测试说明

- 使用 `pytest`，异步测试通过 `@pytest.mark.anyio` 标记
- 共享测试工具在 `tests/conftest.py`（`make_event`、`FakeSender`）
- `FakeServerRunner` 替代 uvicorn，健康检查通过 `httpx.ASGITransport` 在 ASGI 层面测试
