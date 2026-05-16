from __future__ import annotations


_UPGRADE_KEYWORDS = frozenset({
    "分析", "比较", "对比", "总结", "归纳", "解释", "推导",
    "代码", "编程", "函数", "算法", "调试", "bug", "错误",
    "优化", "重构", "设计", "架构", "方案", "规划",
    "analyze", "compare", "contrast", "summarize", "explain",
    "code", "program", "function", "algorithm", "debug",
    "optimize", "refactor", "architecture", "design pattern",
})


class ModelRouter:
    def __init__(
        self,
        default_model: str = "deepseek-v4-flash",
        upgrade_model: str = "deepseek-v4-pro",
        upgrade_min_length: int = 200,
        upgrade_keywords: frozenset[str] | None = None,
    ) -> None:
        self._default = default_model
        self._upgrade = upgrade_model
        self._min_length = upgrade_min_length
        self._keywords = upgrade_keywords or _UPGRADE_KEYWORDS

    def select_model(self, text: str) -> str:
        if len(text) > self._min_length:
            return self._upgrade
        text_lower = text.lower()
        if any(kw in text_lower for kw in self._keywords):
            return self._upgrade
        return self._default
