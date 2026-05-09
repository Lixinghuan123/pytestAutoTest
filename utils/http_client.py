import json
import requests


class HttpClient:
    """HTTP 请求客户端，发送前通过 GlobalContext 渲染模板变量"""

    def __init__(self, context):
        self.context = context
        self.session = requests.Session()

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
            kwargs["json"] = body if isinstance(body, (dict, list)) else body
        elif method == "GET":
            kwargs["params"] = body

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
