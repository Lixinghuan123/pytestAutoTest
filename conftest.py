import pytest
import allure
from utils.context import GlobalContext


@pytest.fixture(scope="session")
def global_ctx():
    """全局变量上下文，整个测试会话共享。在此配置初始变量。"""
    ctx = GlobalContext()
    # ---------- 按需配置 ----------
    # ctx.set("base_url", "https://m-passport.shop-sandbox.com")   # 基础URL，相对路径会自动拼接
    # ctx.set("loginName", "limiaomiao")
    ctx.set("base_url", "https://www.info-sandbox.top")  # 基础URL，相对路径会自动拼接
    # ctx.set("accountNumber", "13122761139")
    # ctx.set("password", "81cc14daccf9488de432d62fe239b925908154856b57d37aa5cba31f06643799")          # 登录密码等初始变量
    # -----------------------------
    return ctx


@pytest.fixture(scope="session")
def http_client(global_ctx):
    """HTTP 客户端，绑定全局上下文"""
    from utils.http_client import HttpClient
    return HttpClient(global_ctx)


def pytest_collection_modifyitems(items):
    """确保测试按 Excel 中的顺序（ID）执行"""
    def sort_key(item):
        if hasattr(item, "callspec"):
            case = item.callspec.params.get("case", {})
            return case.get("ID", 9999) or 9999
        return 9999
    items.sort(key=sort_key)


def pytest_configure(config):
    allure_dir = config.getoption("--alluredir", default="allure-results")
    import os
    os.makedirs(allure_dir, exist_ok=True)
    env_file = os.path.join(allure_dir, "environment.properties")
    with open(env_file, "w", encoding="utf-8") as f:
        f.write("Framework=pytest+allure+requests\n")
