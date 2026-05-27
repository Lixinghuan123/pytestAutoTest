import json
import requests
import urllib.parse


class HttpClient:
    """HTTP 请求客户端，发送前通过 GlobalContext 渲染模板变量"""

    def __init__(self, context):
        self.context = context
        self.session = requests.Session()
        # 添加默认请求头，与浏览器/Jmeter行为保持一致
        # self.session.headers.update({
        #     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        #     "Accept": "application/json, text/plain, */*",
        #     "Accept-Encoding": "gzip, deflate, br",
        #     "Connection": "keep-alive"
        # })

    def send(self, url: str, method: str, headers: str | dict | None = None,
             data: str | dict | None = None) -> requests.Response:
        method = str(method).upper().strip() if method else "GET"

        url = self._build_url(self.context.render(url))
        if headers and not isinstance(headers, float):
            headers = self._parse(self.context.render(headers))
        else:
            headers = {}
        body = self._parse(self.context.render(data)) if data else None

        kwargs = {"headers": headers, "timeout": 30}
        if method in ("POST", "PUT", "PATCH"):
            kwargs["json"] = body if isinstance(body, (dict, list)) else json.dumps(body)
        elif method == "GET":
            # 处理 GET 请求参数，确保 URL 编码正确
            kwargs["params"] = self._encode_get_params(body)

     

        response = self.session.request(method, url, **kwargs)
        return response

    def _build_url(self, url: str) -> str:
        """如果 URL 以 / 开头，自动拼接 base_url"""
        if url.startswith("/"):
            base = self.context.get("base_url", "")
            if base:
                return base.rstrip("/") + url
            raise ValueError(
                f"URL '{url}' 是相对路径，请在全局上下文中设置 base_url。"
                f" 示例: global_ctx.set('base_url', 'https://api.example.com')"
            )
        return url

    def _encode_get_params(self, params) -> dict:
        """处理 GET 请求参数
        
        问题场景：当参数值包含空格（如日期时间 "2026-05-23 00:00:00"）时，
        需要正确处理。这里不进行手动 URL 编码，让 requests 库自动处理，
        确保编码方式符合标准。
        
        Args:
            params: 请求参数（可能是 dict 或 JSON 字符串）
            
        Returns:
            dict: 处理后的参数字典
        """
        if not params:
            return {}
        
        # 如果是字符串，尝试解析为 JSON
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except json.JSONDecodeError:
                # 如果不是有效的 JSON，记录警告并返回空字典
                print(f"【警告】GET 参数不是有效 JSON: {params}")
                return {}
        
        # 如果不是字典，返回空字典
        if not isinstance(params, dict):
            print(f"【警告】GET 参数不是字典类型: {type(params).__name__}")
            return {}
        
        # 将所有值转为字符串（requests 库会自动进行 URL 编码）
        processed_params = {}
        for key, value in params.items():
            if value is None:
                processed_params[key] = None
            else:
                str_value = str(value)
                processed_params[key] = str_value
                
        # 打印处理后的参数
        print(f"【GET参数】{json.dumps(processed_params, ensure_ascii=False)}")
        
        return processed_params

    @staticmethod
    def _parse(text):
        if isinstance(text, (dict, list)):
            return text
        if isinstance(text, str):
            try:
                return json.loads(text)
            except (json.JSONDecodeError, TypeError):
                return text
        return text
