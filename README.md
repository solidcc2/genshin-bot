# QQ AI 机器人

当前仓库已完成 `CP1`，即项目的运行时基础骨架。

## CP1 已包含内容

- 统一应用启动入口
- `JSON 配置文件 + 环境变量` 配置加载
- 结构化日志初始化
- 基于 ASGI 的最小 HTTP 健康检查接口
- 最小自动化测试基线

## CP1 暂不包含内容

- QQ 接入适配器
- 事件模型与路由分发
- 原神相关 Provider
- 大模型 Provider
- 定时任务与提醒能力

## 启动方式

```bash
source .venv/bin/activate
python -m app --config configs/dev.json
```

启动后可访问：

```text
http://127.0.0.1:8000/healthz
```

## 运行测试

```bash
source .venv/bin/activate
pytest
```
