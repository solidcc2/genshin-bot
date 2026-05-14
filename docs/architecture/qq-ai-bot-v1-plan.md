# QQ AI 机器人 v1 选型与架构规划（个人 QQ / NapCat / OneBot / Python 核心）

## 摘要

- v1 目标是先做稳定可用的自用原型，不做复杂 agent，只完成 QQ 接入、原神常用功能、基础模型对话、提醒任务、可扩展插件能力。
- QQ 接入采用个人 QQ + NapCat + OneBot v11，这条路线属于和云崽同类的个人号接入方向，但工程组织不采用云崽式“QQ 框架即核心”，而是 QQ 仅作 adapter，核心能力独立于 QQ 协议端。
- 核心工程采用 Python 自研核心 + 适配层，不深绑 LangChain、Koishi、AstrBot、NoneBot 等框架。
- 原神能力分层接入：Enka.Network 负责公开面板与角色展示；genshin.py + 米游社/HoYoLAB cookies 负责账号类能力；静态资料本地化快照。
- 智能能力 v1 仅采用普通路由 + 单步工具调用；但从架构上预留 Tool Registry、Agent Orchestrator、ExecutionStateStore，未来可扩展到 LangGraph/LangChain 或自研工作流。

## QQ 接入选型结论

- v1 实际方案
  - 个人 QQ
  - NapCat 作为协议端
  - OneBot v11 作为统一消息协议
  - Python 核心服务通过反向 WebSocket 或 HTTP 对接 OneBot 事件
- 这不是官方 QQ Bot 路线
  - 不走 QQ 开放平台官方机器人 API
  - 不依赖官方沙箱、审核、发布流程作为第一版前提
- 与云崽的关系
  - 接入路线相似：都属于个人 QQ 接入，底层都依赖非官方协议或客户端改造生态
  - 架构组织不同：云崽更偏“围绕机器人框架本体长插件”；本方案是“QQ 只是消息入口，业务核心独立”
- 采用该方案的原因
  - 自用原型阶段门槛低，能更自然地进入群聊、私聊场景
  - 和官方机器人相比，交互更接近日常 QQ 使用方式
  - 可先验证原神功能和产品形态，再决定是否补官方线路
- 已知限制
  - 非官方接入，存在封号、失效、升级破坏、登录环境限制、长期维护波动
  - 不适合作为面向陌生用户公开运营的合规基础
  - 因此必须在架构上保留 `QQOfficialAdapter` 的替换位

## 关键选型

- 工程形态
  - 不采用“大而全机器人框架作为主骨架”
  - 采用自研核心 + 外部协议端
  - 不让 NapCat、OneBot 结构渗透到业务层
- 原神能力
  - 公开数据：Enka.Network
  - 账号数据：genshin.py
  - 静态资料：本地 JSON/SQLite 快照
  - 用户绑定：仅支持用户手工提供自己的 cookies
- 模型策略
  - 默认主模型：DeepSeek-V4-Flash
  - 复杂请求升级：DeepSeek-V4-Pro
  - 可选 provider 预留：OpenAI GPT-5 mini / GPT-5
  - v1 不做多模型自动规划，不做复杂推理编排
- 智能扩展策略
  - v1 不引入 LangChain 运行时依赖
  - 仅预留 Orchestrator、Tool Registry、ExecutionStateStore
  - 后续若需要多步骤推理，优先考虑 LangGraph 作为状态化编排实现
- 数据层
  - SQLite：配置、绑定关系、提醒任务、插件配置、审计
  - Redis：消息去重、会话缓存、Enka TTL 缓存、限流
- 调度层
  - APScheduler
  - 长任务与复杂异步队列不纳入 v1

## 架构规划

- `adapters/`
  - `qq_personal_onebot/`
    - 接 NapCat 的 OneBot v11 事件
    - 负责消息收发、事件标准化、发送回执
  - `qq_official/`
    - 预留官方 QQ 机器人映射层
    - v1 只定义接口，不做完整落地
- `core/`
  - `event_model`
    - 统一消息事件，不暴露 OneBot 原始结构
  - `router`
    - 负责命令、原神查询、闲聊请求分流
  - `session`
    - 会话上下文与短期记忆
  - `permission`
    - 用户级开关、频控、敏感功能控制
- `plugins/`
  - `genshin/`
    - 原神资料、面板、签到、便笺、战绩
  - `common/`
    - 帮助、提醒、设置、健康检查
  - 插件只依赖统一上下文，不依赖 QQ 协议对象
- `providers/`
  - `llm/`
  - `genshin/`
  - `storage/`
- `future/agent_boundary/`
  - `ToolRegistry`
  - `AgentOrchestrator`
  - `ExecutionStateStore`
  - v1 只保留抽象和默认空实现
- `api/`
  - 本地调试、健康检查接口
  - 不要求 v1 有完整管理后台

## 需要明确的公共接口

- `NormalizedEvent`
  - 字段至少包含：
    - `platform`
    - `adapter`
    - `scene`
    - `chat_id`
    - `user_id`
    - `message_id`
    - `text`
    - `mentions`
    - `attachments`
    - `reply_to`
    - `timestamp`
- `PluginContext`
  - 包含：
    - 标准化事件
    - 会话对象
    - provider 访问入口
    - 配置
    - 回复方法
- `BotPlugin`
  - `match(event) -> bool`
  - `handle(ctx) -> PluginResult`
  - `help() -> PluginHelp`
- `ModelProvider`
  - `generate(messages, config) -> ModelResponse`
  - `estimate_cost(usage) -> CostInfo`
- `Tool`
  - `name`
  - `schema`
  - `execute(input, ctx) -> ToolResult`
- `AgentOrchestrator`
  - `supports(task_type) -> bool`
  - `run(task, ctx) -> OrchestratorResult`
  - v1 默认实现：`DirectExecutionOrchestrator`
- `GenshinProvider`
  - `get_static_entity()`
  - `get_public_profile()`
  - `get_notes()`
  - `daily_checkin()`
  - `get_chronicle_summary()`

## v1 功能范围

- 必做
  - QQ 私聊、群聊接收与回复
  - 帮助与基础配置
  - 原神静态资料查询
  - UID 公开面板摘要
  - 米游社绑定后的实时便笺、签到、战绩摘要
  - 定时提醒
  - 基础模型闲聊
  - 日志、缓存、限流、错误处理
- 明确不做
  - 多步骤 agent 规划
  - 浏览器自动化
  - Web 搜索编排
  - 知识库复杂检索链
  - 完整 Web 管理后台
- 仅预留
  - `ToolRegistry`
  - `AgentOrchestrator`
  - `ExecutionStateStore`
  - `WebSearchTool`
  - `BrowserTool`
  - `QQOfficialAdapter`

## 后续智能扩展预留方案

- 扩展原则
  - 消息适配层不变
  - 插件入口不变
  - 工具接口不变
  - 只替换编排器实现
- 扩展路径
  - 先把原神、提醒、查询整理成标准 `Tool`
  - 再增加 `WebSearchTool`、`PageFetchTool`、`SummarizeTool`
  - 然后让 `AgentOrchestrator` 仅接管复杂请求
  - 如果任务变成状态化、多轮、多工具协作，再把 orchestrator 实现替换为 LangGraph 或自研状态机
- v1 必须避免
  - 把业务逻辑写死在 OneBot handler 内
  - 把原神功能直接写成 prompt
  - 把工具执行与模型调用耦合

## 测试与验收

- 接入测试
  - NapCat + OneBot 私聊消息可正常触发插件和普通聊天
  - 群聊消息在规则范围内可触发响应
  - 重复投递不会重复执行
- 原神测试
  - 静态资料查询不依赖外部 API
  - Enka 查询按 `ttl` 缓存
  - 未绑定 cookies 的账号类功能明确失败
  - 已绑定 cookies 的便笺、签到、战绩摘要正常
- 模型测试
  - 普通问答默认走主模型
  - 高复杂请求可按规则切升级模型
  - 记录 token、耗时、估算成本
- 架构验收
  - 业务层不依赖 OneBot 原始对象
  - plugin/provider 可被 mock
  - `QQPersonalAdapter` 与未来 `QQOfficialAdapter` 可共享同一插件层
  - `ToolRegistry`、`AgentOrchestrator` 接口已存在，但默认不承载复杂逻辑

## 假设与默认值

- 默认使用场景：纯自用
- 默认接入顺序：个人 QQ 先落地，官方 QQ 后补
- 默认个人号实现：NapCat + OneBot v11
- 默认语言栈：Python + FastAPI + APScheduler + SQLite + Redis
- 默认模型：DeepSeek-V4-Flash 主用，DeepSeek-V4-Pro 升级
- 默认智能形态：简单路由 + 单步工具调用
- 默认未来扩展：优先保留 LangGraph、LangChain 可接入性，但 v1 不引入其运行时依赖

## 参考依据

- QQ 官方、社区接入与沙箱、群聊触发
  - https://docs.picoclaw.io/zh-Hans/docs/channels/qq/
  - https://doc.ppagent.cn/config/source/qq.html
  - https://cloud.tencent.com/developer/article/2626045
- 个人号协议端
  - https://github.com/NapNeko/NapCatQQ
  - https://llonebot.com/en-US/
- 原神社区能力
  - https://github.com/EnkaNetwork/API-docs/blob/master/api.md
  - https://github.com/seriaati/genshin.py
  - https://seria.is-a.dev/genshin.py/hoyolab/
- 模型价格
  - https://api-docs.deepseek.com/quick_start/pricing
  - https://openai.com/index/introducing-gpt-5-for-developers/
  - https://ai.google.dev/gemini-api/docs/pricing?hl=zh-cn
  - https://platform.claude.com/docs/en/about-claude/pricing
