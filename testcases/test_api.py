import json
import allure
import pytest
from utils.excel_reader import read_excel
from utils.assertion import assert_response, assert_sql
from utils.extractor import ResponseExtractor


EXCEL_PATH = "test_cases.xlsx"


def load_cases():
    """加载 Excel 中的测试用例，确保登录用例优先执行+多行sql与对应expected_sql已经处理过；问题"""
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
def test_api(case: dict, http_client, global_ctx, db_client, db_client_factory):
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

    # 4. 执行SQL并断言（支持多数据库、多SQL）
    sql_list = case.get("sql", [])
    expected_sql_list = case.get("expected_sql", [])
    db_name = case.get("db_name", "default")  # 从Excel获取数据库名称
    
    # 确保 sql_list 是列表格式
    if isinstance(sql_list, str):
        sql_list = [sql_list]
    
    if sql_list:
        try:
            # 根据 db_name 获取对应的数据库客户端
            if db_name == "default":
                current_db = db_client
            else:
                current_db = db_client_factory(db_name)
            
            # 存储所有SQL执行结果
            all_results = []
            
            # 执行每条SQL
            for idx, sql in enumerate(sql_list):
                if not sql.strip():
                    continue
                
                # 先渲染SQL模板变量，这里的渲染1、allure中查看 2、传递给数据库执行
                rendered_sql = current_db.render_sql(sql)
                
                with allure.step(f"执行SQL[{idx+1}] [{db_name}]: {sql[:100]}..."):
                    # 传递渲染后的SQL，避免重复渲染
                    rows = current_db.execute_raw(rendered_sql)
                    all_results.append(rows)
                    
                    allure.attach(sql, name=f"SQL[{idx+1}] 原始SQL（含模板变量）", 
                                  attachment_type=allure.attachment_type.TEXT)
                    allure.attach(rendered_sql, name=f"SQL[{idx+1}] 渲染后SQL（实际执行）", 
                                  attachment_type=allure.attachment_type.TEXT)
                    allure.attach(json.dumps(rows, ensure_ascii=False, indent=2, default=str),
                                 name=f"SQL[{idx+1}] 执行结果", 
                                 attachment_type=allure.attachment_type.JSON)
            
            # 执行断言
            if expected_sql_list:
                # 确保 expected_sql_list 是列表格式
                if isinstance(expected_sql_list, str):
                    expected_sql_list = [expected_sql_list]
                
                with allure.step(f"SQL断言: {expected_sql_list}"):
                    assert_sql(all_results, expected_sql_list)
        except Exception as e:
            # 确保即使失败也能记录SQL信息
            for idx, sql in enumerate(sql_list):
                if sql and sql.strip():
                    allure.attach(sql, name=f"失败的SQL[{idx+1}]原始SQL", 
                                  attachment_type=allure.attachment_type.TEXT)
                    try:
                        rendered = current_db.render_sql(sql)
                        allure.attach(rendered, name=f"失败的SQL[{idx+1}]渲染后SQL", 
                                      attachment_type=allure.attachment_type.TEXT)
                    except:
                        pass
            if 'all_results' in locals():
                for idx, rows in enumerate(all_results):
                    allure.attach(json.dumps(rows, ensure_ascii=False, indent=2, default=str),
                                 name=f"失败时的SQL[{idx+1}]结果", 
                                 attachment_type=allure.attachment_type.JSON)
            raise


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
    # 这里还要渲染一遍是因为有些url是有动态参数的，例：/api/user/{{uid}}
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
