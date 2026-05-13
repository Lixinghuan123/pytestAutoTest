import pytest
import allure
from utils.context import GlobalContext


def pytest_addoption(parser):
    """添加命令行参数"""
    parser.addoption(
        "--db-env", 
        action="store", 
        default="test", 
        help="数据库环境: dev/test/prod (默认: test)"
    )


@pytest.fixture(scope="session")
def db_env(request):
    """获取命令行指定的数据库环境"""
    return request.config.getoption("--db-env")


@pytest.fixture(scope="session")
def global_ctx():
    """全局变量上下文，整个测试会话共享。在此配置初始变量。"""
    ctx = GlobalContext()
    ctx.set("base_url", "https://www.info-sandbox.top")  # 基础URL，相对路径会自动拼接
    return ctx


@pytest.fixture(scope="session")
def http_client(global_ctx):
    """HTTP 客户端，绑定全局上下文"""
    from utils.http_client import HttpClient
    return HttpClient(global_ctx)


@pytest.fixture(scope="session")
def db_client(global_ctx, db_env):
    """数据库客户端，整个测试会话共享一个连接"""
    from utils.db_client import DbClient
    db = DbClient(global_ctx, env=db_env)
    yield db
    db.close_all()


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
    
    # 获取数据库环境
    db_env = config.getoption("--db-env", "test")
    
    env_file = os.path.join(allure_dir, "environment.properties")
    with open(env_file, "w", encoding="utf-8") as f:
        f.write("Framework=pytest+allure+requests\n")
        f.write(f"DB_ENV={db_env}\n")
