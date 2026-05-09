import re
from jinja2 import Environment, BaseLoader


class GlobalContext:
    """全局变量上下文，存储从响应中提取的变量（如 token），支持 Jinja2 模板渲染"""

    def __init__(self):
        self._vars = {}

    def set(self, key, value):
        self._vars[key] = value

    def get(self, key, default=None):
        return self._vars.get(key, default)

    def update(self, mapping: dict):
        self._vars.update(mapping)

    def render(self, text):
        """渲染文本中的模板变量，兼容 ${var} 和 {{ var }} 两种写法"""
        if text is None or not isinstance(text, str):
            return text
        text = re.sub(r'\$\{(\w+)\}', r'{{ \1 }}', text)
        env = Environment(loader=BaseLoader())
        template = env.from_string(text)
        return template.render(**self._vars)

    def __repr__(self):
        return f"GlobalContext({self._vars})"
