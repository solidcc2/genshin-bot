from app.llm.routing import ModelRouter


class TestModelRouter:
    def setup_method(self) -> None:
        self.router = ModelRouter()

    def test_default_text_uses_flash(self) -> None:
        model = self.router.select_model("你好")
        assert model == "deepseek-v4-flash"

    def test_keyword_upgrades_to_pro(self) -> None:
        model = self.router.select_model("帮我分析一下这个情况")
        assert model == "deepseek-v4-pro"

    def test_english_keyword_upgrades_to_pro(self) -> None:
        model = self.router.select_model("explain this to me")
        assert model == "deepseek-v4-pro"

    def test_long_text_upgrades_to_pro(self) -> None:
        text = "a" * 250
        model = self.router.select_model(text)
        assert model == "deepseek-v4-pro"

    def test_short_text_stays_flash(self) -> None:
        model = self.router.select_model("今天天气怎么样")
        assert model == "deepseek-v4-flash"

    def test_empty_string_uses_flash(self) -> None:
        model = self.router.select_model("")
        assert model == "deepseek-v4-flash"

    def test_code_keyword_upgrades(self) -> None:
        model = self.router.select_model("写一段Python代码")
        assert model == "deepseek-v4-pro"

    def test_architecture_keyword_upgrades(self) -> None:
        model = self.router.select_model("系统架构设计")
        assert model == "deepseek-v4-pro"

    def test_boundary_at_200_chars(self) -> None:
        text = "x" * 200
        model = self.router.select_model(text)
        assert model == "deepseek-v4-flash", "200 chars should not trigger upgrade"

    def test_boundary_at_201_chars(self) -> None:
        text = "x" * 201
        model = self.router.select_model(text)
        assert model == "deepseek-v4-pro", "201 chars should trigger upgrade"

    def test_custom_threshold(self) -> None:
        router = ModelRouter(upgrade_min_length=50)
        assert router.select_model("x" * 49) == "deepseek-v4-flash"
        assert router.select_model("x" * 51) == "deepseek-v4-pro"
