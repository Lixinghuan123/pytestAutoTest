import json
from utils.excel_reader import read_excel
from utils.http_client import HttpClient
from utils.context import GlobalContext


def main():
    print("=== 接口自动化测试框架 ===")
    
    # 1. 初始化全局上下文
    ctx = GlobalContext()
    print("ctx:",ctx)
    ctx.set("base_url", "https://www.info-sandbox.top")
    ctx.set("accountNumber", "13122761139")
    ctx.set("password", "b7e3f6b21b1e5f755036eeb2f110f88841c9e684c0ee125038dfe35fd6646887")
    print("ctx2:", ctx)
    
    # 2. 创建 HTTP 客户端
    http_client = HttpClient(ctx)
    
    # 3. 读取测试用例
    print("\n[步骤1] 读取测试用例...")
    cases = read_excel("test_cases.xlsx")
    print(f"共读取到 {len(cases)} 条测试用例")
    print(f"cases类型{type(cases)}")
    
    # 4. 查找登录相关的测试用例
    print("\n[步骤2] 查找登录测试用例...")
    login_cases = [c for c in cases if c.get("module") == "登录"]

    
    if not login_cases:
        print("未找到登录测试用例，尝试按关键字搜索...")
        login_cases = [c for c in cases if "login" in str(c.get("url", "")).lower() or "登录" in str(c.get("feature", ""))]

    if not login_cases:
        print("错误：未找到登录测试用例")
        return
    print(f"login_cases类型{type(login_cases)},login_cases[0]类型{type(login_cases[0])}")
    login_case = login_cases[0]
    print(f"找到登录用例: ID={login_case.get('ID')}, URL={login_case.get('url')}")
    
    # 5. 发起登录请求
    print("\n[步骤3] 发起登录请求...")
    url = login_case.get("url", "")
    method = login_case.get("method", "POST")
    headers = login_case.get("headers")
    data = login_case.get("data")
    data = json.loads(data)
    
    print(f"请求方式: {method}")
    print(f"请求URL: {url}")
    print(f"请求头: {headers}")
    print(f"请求体: {data}")
    
    try:
        response = http_client.send(url=url, method=method, headers=headers, data=data)
        print(f"\n响应状态码: {response.status_code}")
        
        try:
            resp_json = response.json()
            print(f"响应体: {json.dumps(resp_json, ensure_ascii=False, indent=2)}")
        except:
            print(f"响应体: {response.text}")
        
        # 6. 提取 token
        print("\n[步骤4] 提取 token...")
        extracted_expr = login_case.get("extracted")
        
        if extracted_expr:
            token = _extract_token(response, extracted_expr)
            if token:
                ctx.set("token", token)
                print(f"✅ 成功提取 token: {token[:20]}...")
                print(f"已存入全局上下文")
            else:
                print("❌ 未能从响应中提取 token")
        else:
            print("⚠️ 测试用例中未配置 extracted 字段，尝试自动提取...")
            token = _auto_extract_token(response)
            if token:
                ctx.set("token", token)
                print(f"✅ 自动提取 token: {token[:20]}...")
            else:
                print("❌ 未能自动提取 token")
        
        print("\n[完成] 登录流程执行完毕")
        print(f"当前全局上下文变量: {list(ctx._vars.keys())}")
        
    except Exception as e:
        print(f"❌ 请求失败: {str(e)}")


def _extract_token(response, extract_expr):
    """从响应中提取 token，支持点号分隔的路径"""
    try:
        resp_json = response.json()
    except:
        return None
    
    if ":" in extract_expr:
        field_path, _ = extract_expr.split(":", 1)
    else:
        field_path = extract_expr
    
    parts = field_path.split(".")
    current = resp_json
    for part in parts:
        part = part.strip()
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _auto_extract_token(response):
    """自动从响应中提取 token"""
    try:
        resp_json = response.json()
        # 常见的 token 字段名
        token_fields = ["token", "access_token", "accessToken", "Authorization", "auth_token"]
        
        for field in token_fields:
            if field in resp_json:
                return resp_json[field]
            # 检查嵌套结构
            if "data" in resp_json and field in resp_json["data"]:
                return resp_json["data"][field]
            if "result" in resp_json and field in resp_json["result"]:
                return resp_json["result"][field]
    except:
        pass
    return None


if __name__ == "__main__":
    main()