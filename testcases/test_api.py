import json
import allure
import pytest
from utils.excel_reader import read_excel
from utils.assertion import assert_response
from utils.extractor import ResponseExtractor


EXCEL_PATH = "test_cases.xlsx"


def load_cases():
    """加载 Excel 中的测试用例，确保登录用例优先执行"""
    cases = read_excel(EXCEL_PATH)
    
    # 过滤有效用例
    valid_cases = [c for c in cases if c.get("url") and c.get("method")]
    
    # 将登录用例放在前面
    login_cases = []
    other_cases = []
    
    for case in valid_cases:
        module = case.get("module", "").lower()
        url = case.get("url", "").lower()
        feature = case.get("feature", "").lower()
        
        # 判断是否为登录用例
        if "登录" in module or "login" in url or "登录" in feature:
            login_cases.append(case)
        else:
            other_cases.append(case)
    
    # 按 ID 排序
    # login_cases.sort(key=lambda c: c.get("ID", 9999) or 9999)
    # other_cases.sort(key=lambda c: c.get("ID", 9999) or 9999)
    
    # 登录用例优先
    return login_cases + other_cases


def get_case_id(case):
    """生成测试用例 ID"""
    return f"case_{case.get('ID', 'unknown')}_{case.get('module', 'unknown')}"


@pytest.mark.parametrize("case", load_cases(), ids=get_case_id)
def test_api(case: dict, http_client, global_ctx):
    """单个接口测试用例的执行入口"""
    _set_allure_labels(case)

    url = case.get("url", "")
    method = case.get("method", "GET")
    headers = case.get("headers")
    data = case.get("data")
    expected = case.get("expected")
    expected_field = case.get("expected_field")
    extracted = case.get("extracted")

    # 1. 发送请求
    with allure.step(f"{method} {url}"):
        resp = http_client.send(url=url, method=method, headers=headers, data=data)
        _attach_request(http_client, url, method, headers, data)
        _attach_response(resp)

    # 2. 提取变量（如 token）写入全局上下文
    if extracted:
        with allure.step(f"提取变量: {extracted}"):
            extracted_vars = ResponseExtractor.extract_and_store(resp, extracted, global_ctx)
            for var_name, value in extracted_vars.items():
                allure.attach(str(value), name=f"提取: {var_name}", attachment_type=allure.attachment_type.TEXT)

    # 3. 断言（包含关系）
    if expected_field and expected is not None:
        with allure.step(f"断言: {expected_field} 包含 {expected}"):
            assert_response(resp, expected_field, str(expected))


# ---------- helpers ----------

def _set_allure_labels(case: dict):
    """设置 Allure 标签"""
    module = case.get("module")
    feature = case.get("feature")
    story = case.get("story")
    package = case.get("package", "api_tests")
    
    if module:
        allure.dynamic.tag(module)
    
    if feature:
        allure.dynamic.feature(feature)
    
    if story:
        allure.dynamic.story(story)
    
    # 设置包名（报告中的"包"字段）
    allure.dynamic.label("package", package)
    
    # 设置测试标题
    title = f"[{case.get('ID')}] "
    if module:
        title += f"{module} - "
    if feature:
        title += feature
    allure.dynamic.title(title)


def _attach_request(http_client, url, method, headers, data):
    """附加请求信息到 Allure"""
    full_url = http_client.context.render(url)
    body = http_client._parse(http_client.context.render(data)) if data else None
    
    req_info = {
        "method": method.upper(),
        "url": full_url,
        "headers": http_client._parse(http_client.context.render(headers)) if headers else {},
        "body": body,
    }
    
    allure.attach(
        json.dumps(req_info, ensure_ascii=False, indent=2),
        name="请求详情",
        attachment_type=allure.attachment_type.JSON,
    )


def _attach_response(resp):
    """附加响应信息到 Allure"""
    try:
        body = resp.json()
    except Exception:
        body = resp.text
    
    info = {
        "status_code": resp.status_code,
        "headers": dict(resp.headers),
        "body": body ,
    }
    
    allure.attach(
        json.dumps(info, ensure_ascii=False, indent=2, default=str),
        name="响应详情",
        attachment_type=allure.attachment_type.JSON,
    )
