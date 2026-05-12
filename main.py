import json
import os
import sys
from utils.excel_reader import read_excel
from utils.http_client import HttpClient
from utils.context import GlobalContext
from utils.extractor import ResponseExtractor
from utils.assertion import assert_response


def main():
    print("=== 接口自动化测试框架 ===")
    
    # 初始化 allure 环境
    _init_allure()
    
    # 1. 初始化全局上下文
    ctx = GlobalContext()
    ctx.set("base_url", "https://www.info-sandbox.top")
    
    # 2. 创建 HTTP 客户端
    http_client = HttpClient(ctx)
    
    # 3. 读取测试用例
    print("\n[步骤1] 读取测试用例...")
    all_cases = read_excel("test_cases.xlsx")
    
    # 过滤有效用例（url 和 method 均非空）
    valid_cases = [c for c in all_cases if c.get("url") and c.get("method")]
    print(f"共读取到 {len(all_cases)} 条测试用例，有效用例 {len(valid_cases)} 条")
    
    if not valid_cases:
        print("错误：未找到有效测试用例")
        return
    
    # 4. 按 ID 排序测试用例
    valid_cases.sort(key=lambda c: c.get("ID", 9999) or 9999)
    
    # 5. 查找并执行登录用例（优先执行）
    login_case = _find_login_case(valid_cases)
    
    if login_case:
        print(f"\n[步骤2] 执行登录用例...")
        success = _execute_case(login_case, http_client, ctx)
        
        if not success:
            print("⚠️ 登录失败，继续执行其他用例可能会失败")
        
        # 从列表中移除已执行的登录用例
        valid_cases.remove(login_case)
    else:
        print("\n[步骤2] 未找到登录用例，直接执行其他用例")
    
    # 6. 循环执行剩余测试用例
    print(f"\n[步骤3] 执行剩余 {len(valid_cases)} 条测试用例...")
    
    for idx, case in enumerate(valid_cases, 1):
        print(f"\n--- 用例 {idx}/{len(valid_cases)} ---")
        _execute_case(case, http_client, ctx)
    
    # 7. 输出最终结果
    print("\n[完成] 所有测试用例执行完毕")
    print(f"当前全局上下文变量: {list(ctx._vars.keys())}")
    
    # 8. 生成 allure 报告
    _generate_allure_report()


def _init_allure():
    """初始化 allure 报告目录"""
    allure_dir = "allure-results"
    os.makedirs(allure_dir, exist_ok=True)
    
    # 写入环境信息
    env_file = os.path.join(allure_dir, "environment.properties")
    with open(env_file, "w", encoding="utf-8") as f:
        f.write("Framework=pytest+allure+requests\n")
        f.write("Language=Python\n")


def _find_login_case(cases):
    """查找登录测试用例"""
    # 优先按 module == "登录" 查找
    login_cases = [c for c in cases if c.get("module") == "登录"]
    if login_cases:
        return login_cases[0]
    
    # 其次按关键字搜索
    login_cases = [c for c in cases if "login" in str(c.get("url", "")).lower() or "登录" in str(c.get("feature", ""))]
    if login_cases:
        return login_cases[0]
    
    return None


def _execute_case(case: dict, http_client: HttpClient, ctx: GlobalContext) -> bool:
    """执行单个测试用例"""
    case_id = case.get("ID")
    module = case.get("module", "")
    feature = case.get("feature", "")
    url = case.get("url", "")
    method = case.get("method", "GET")
    headers = case.get("headers")
    data = case.get("data")
    expected = case.get("expected")
    expected_field = case.get("expected_field")
    extracted = case.get("extracted")
    
    print(f"用例ID: {case_id}")
    print(f"模块: {module}, 功能: {feature}")
    print(f"请求: {method} {url}")
    
    # 创建测试结果收集器
    result_collector = _AllureResultCollector(case_id, module, feature)
    
    try:
        # 发送请求（HttpClient 会自动渲染 headers 和 data 中的模板变量）
        response = http_client.send(url=url, method=method, headers=headers, data=data)
        print(f"响应状态码: {response.status_code}")
        
        # 打印响应体（最多显示 500 字符）
        try:
            resp_json = response.json()
            resp_str = json.dumps(resp_json, ensure_ascii=False, indent=2)
            print(f"响应体: {resp_str[:500]}{'...' if len(resp_str) > 500 else ''}")
        except:
            resp_text = response.text
            print(f"响应体: {resp_text[:500]}{'...' if len(resp_text) > 500 else ''}")
        
        # 记录请求和响应信息
        full_url = http_client.context.render(url)
        req_body = http_client._parse(http_client.context.render(data)) if data else None
        req_headers = http_client._parse(http_client.context.render(headers)) if headers else {}
        
        result_collector.add_request(method, full_url, req_headers, req_body)
        result_collector.add_response(response)
        
        # 提取变量（支持多字段提取）
        if extracted:
            print(f"提取变量: {extracted}")
            extracted_vars = ResponseExtractor.extract_and_store(response, extracted, ctx)
            if extracted_vars:
                print("✅ 提取成功:")
                for var_name, value in extracted_vars.items():
                    print(f"  - {var_name}: {str(value)[:30]}{'...' if len(str(value)) > 30 else ''}")
                    result_collector.add_extracted_var(var_name, value)
        
        # 断言（包含关系）
        if expected_field and expected is not None:
            print(f"断言: {expected_field} 包含 {expected}")
            try:
                assert_response(response, expected_field, str(expected))
                print("✅ 断言通过")
                result_collector.add_assertion(expected_field, expected, True, None)
            except AssertionError as e:
                print(f"❌ 断言失败: {e}")
                result_collector.add_assertion(expected_field, expected, False, str(e))
                result_collector.mark_failed(str(e))
        
        result_collector.mark_passed()
        result_collector.write_result()  # 写入测试结果
        return True
        
    except Exception as e:
        print(f"❌ 请求失败: {str(e)}")
        result_collector.mark_failed(str(e))
        result_collector.write_result()  # 写入测试结果
        return False


class _AllureResultCollector:
    """Allure 测试结果收集器，手动生成 Allure 所需的 JSON 格式"""
    
    def __init__(self, case_id, module, feature):
        self.case_id = case_id
        self.module = module
        self.feature = feature
        self.status = "passed"
        self.status_details = {}
        self.steps = []
        self.attachments = []
        self.parameters = []
    
    def add_step(self, name, status="passed", details=None):
        """添加步骤"""
        self.steps.append({
            "name": name,
            "status": status,
            "stage": "finished",
            "details": details
        })
    
    def add_attachment(self, name, content, content_type="text/plain"):
        """添加附件"""
        import base64
        encoded = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        self.attachments.append({
            "name": name,
            "source": encoded,
            "type": content_type
        })
    
    def add_request(self, method, url, headers, body):
        """添加请求信息"""
        request_info = json.dumps({
            "method": method.upper(),
            "url": url,
            "headers": headers,
            "body": body
        }, ensure_ascii=False, indent=2)
        self.add_attachment("请求详情", request_info, "application/json")
        self.add_step(f"{method} {url}")
    
    def add_response(self, response):
        """添加响应信息"""
        try:
            resp_body = response.json()
            formatted_body = json.dumps(resp_body, ensure_ascii=False, indent=2)
        except:
            formatted_body = response.text
        
        response_info = json.dumps({
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": formatted_body
        }, ensure_ascii=False, indent=2, default=str)
        self.add_attachment("响应详情", response_info, "application/json")
    
    def add_extracted_var(self, var_name, value):
        """添加提取的变量"""
        self.add_attachment(f"提取变量: {var_name}", str(value), "text/plain")
        self.add_step(f"提取变量 {var_name}")
    
    def add_assertion(self, field, expected, passed, error_msg):
        """添加断言信息"""
        if passed:
            self.add_step(f"断言: {field} 包含 {expected}", "passed")
        else:
            self.add_step(f"断言: {field} 包含 {expected}", "failed", error_msg)
    
    def mark_passed(self):
        """标记测试通过"""
        self.status = "passed"
    
    def mark_failed(self, error_msg):
        """标记测试失败"""
        self.status = "failed"
        self.status_details = {
            "message": error_msg,
            "trace": error_msg
        }
    
    def write_result(self):
        """将测试结果写入 allure-results 目录"""
        import uuid
        import time
        
        result_uuid = str(uuid.uuid4())
        result_dir = "allure-results"
        os.makedirs(result_dir, exist_ok=True)
        
        # 生成测试结果 JSON
        result = {
            "uuid": result_uuid,
            "historyId": str(uuid.uuid4()),
            "testCaseId": str(self.case_id),
            "testName": f"[{self.case_id}] {self.module} - {self.feature}",
            "fullName": f"testcases.test_api.test_{self.case_id}",
            "className": "testcases.test_api",
            "methodName": f"test_{self.case_id}",
            "status": self.status,
            "statusDetails": self.status_details,
            "stage": "finished",
            "start": int(time.time() * 1000),
            "stop": int(time.time() * 1000),
            "steps": self.steps,
            "attachments": self.attachments,
            "parameters": self.parameters,
            "labels": [
                {"name": "feature", "value": self.feature or self.module},
                {"name": "story", "value": self.module},
                {"name": "severity", "value": "normal"},
                {"name": "testClass", "value": "TestAPI"},
                {"name": "testMethod", "value": f"test_{self.case_id}"}
            ]
        }
        
        # 写入 JSON 文件
        result_file = os.path.join(result_dir, f"{result_uuid}-result.json")
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        # 写入容器文件
        container_file = os.path.join(result_dir, f"{result_uuid}-container.json")
        with open(container_file, "w", encoding="utf-8") as f:
            json.dump({
                "uuid": result_uuid,
                "children": [],
                "before": [],
                "after": []
            }, f, ensure_ascii=False)


def _generate_allure_report():
    """生成 allure 报告"""
    print("\n[生成 allure 报告...]")
    
    # 尝试多种方式查找 allure 命令
    allure_cmd = _find_allure_command()
    
    if not allure_cmd:
        print("❌ 未找到 allure 命令行工具")
        print("请确保已正确安装 allure 并配置环境变量")
        print("\n手动生成报告命令:")
        print("  allure generate allure-results -o allure-report --clean")
        print("  allure serve allure-results")
        return
    
    try:
        import subprocess
        result = subprocess.run(
            [allure_cmd, "generate", "allure-results", "-o", "allure-report", "--clean"],
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode == 0:
            print("✅ Allure 报告生成成功")
            print(f"报告路径: {os.path.abspath('allure-report')}")
            print("\n查看报告方式:")
            print(f"  命令行: allure serve allure-results")
            print(f"  或直接打开: {os.path.abspath('allure-report/index.html')}")
        else:
            print(f"⚠️ Allure 报告生成失败")
            if result.stdout:
                print(f"标准输出: {result.stdout}")
            if result.stderr:
                print(f"错误输出: {result.stderr}")
    except Exception as e:
        print(f"⚠️ 生成 allure 报告时出错: {str(e)}")


def _find_allure_command():
    """查找 allure 命令路径"""
    import subprocess
    
    # 方法1: 直接尝试 allure 命令（已配置 PATH）
    try:
        result = subprocess.run(
            ["allure", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print(f"找到 allure: {result.stdout.strip()}")
            return "allure"
    except FileNotFoundError:
        pass
    
    # 方法2: Windows 尝试 allure.bat
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["allure.bat", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                print(f"找到 allure.bat: {result.stdout.strip()}")
                return "allure.bat"
        except FileNotFoundError:
            pass
    
    # 方法3: 查找常见安装路径
    common_paths = [
        "D:\\ruanjian\\allure\\allure-2.41.0\\bin\\allure.bat",
        "D:\\allure\\bin\\allure.bat",
        "C:\\Program Files\\allure\\bin\\allure.bat",
        "C:\\allure\\bin\\allure.bat",
        "/usr/local/bin/allure",
        "/usr/bin/allure",
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            print(f"在 {path} 找到 allure")
            return path
    
    # 方法4: 从 PATH 环境变量中查找
    path_env = os.environ.get("PATH", "")
    paths = path_env.split(";" if os.name == "nt" else ":")
    
    for path in paths:
        if "allure" in path.lower():
            candidate = os.path.join(path, "allure.bat" if os.name == "nt" else "allure")
            if os.path.exists(candidate):
                print(f"在 PATH 中找到 allure: {candidate}")
                return candidate
    
    return None


if __name__ == "__main__":
    main()