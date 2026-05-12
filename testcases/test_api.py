import json
import allure
import pytest
from utils.excel_reader import read_excel
from utils.assertion import assert_response
from utils.extractor import ResponseExtractor


EXCEL_PATH = "test_cases.xlsx"


def load_cases():
    """加载 Excel 中的全部测试用例，仅保留 url 和 method 均非空的行"""
    cases = read_excel(EXCEL_PATH)
    return [c for c in cases if c.get("url") and c.get("method")]


@allure.feature("接口自动化测试")
@pytest.mark.parametrize("case", load_cases(), ids=lambda c: f"case_{c.get('ID')}")
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

    # 3. 断言
    if expected_field and expected is not None:
        with allure.step(f"断言: {expected_field} == {expected}"):
            assert_response(resp, expected_field, str(expected))


# ---------- helpers ----------

def _set_allure_labels(case: dict):
    story = case.get("story") or case.get("module")
    feature = case.get("feature") or case.get("story")
    if story:
        allure.dynamic.story(story)
    if feature:
        allure.dynamic.feature(feature)
    allure.dynamic.title(f"[{case.get('ID')}] {case.get('module', '')} - {case.get('feature', '')}")


def _attach_request(http_client, url, method, headers, data):
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
    try:
        body = resp.json()
        formatted = json.dumps(body, ensure_ascii=False, indent=2)
    except Exception:
        formatted = resp.text
    info = {
        "status_code": resp.status_code,
        "headers": dict(resp.headers),
        "body": formatted,
    }
    allure.attach(
        json.dumps(info, ensure_ascii=False, indent=2, default=str),
        name="响应详情",
        attachment_type=allure.attachment_type.JSON,
    )
