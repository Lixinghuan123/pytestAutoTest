import re

from jsonpath_ng import parse


class ResponseExtractor:
    """响应提取器工具类，支持从 JSON 响应中提取多个字段
    
    Excel 配置格式（extracted 列）：
        token:$.token, userId:$.data.userId, role:$.data.role
        
    格式说明：
        - 多个提取规则用英文逗号分隔
        - 每个规则格式：存储名:JSONPath表达式
        - JSONPath 语法参考：https://goessner.net/articles/JsonPath/
    """

    @staticmethod
    def extract(response, extract_expr: str) -> dict:
        """从响应中提取多个字段，返回映射字典
        
        Args:
            response: requests.Response 对象
            extract_expr: 提取表达式字符串，如 "token:$.token, userId:$.data.userId"
            
        Returns:
            dict: {存储名: 提取值, ...}
        """
        result = {}
        
        if not extract_expr or not isinstance(extract_expr, str):
            return result
        
        try:
            resp_json = response.json()
        except Exception:
            return result
        
        # 按逗号分割多个提取规则
        rules = [r.strip() for r in extract_expr.split(",") if r.strip()]
        
        for rule in rules:
            # 解析每个规则：存储名:JSONPath表达式
            if ":" in rule:
                var_name, jsonpath_expr = rule.split(":", 1)
                var_name = var_name.strip()
                jsonpath_expr = jsonpath_expr.strip()
                
                if var_name and jsonpath_expr:
                    value = ResponseExtractor._extract_by_jsonpath(resp_json, jsonpath_expr)
                    if value is not None:
                        result[var_name] = value
        
        return result

    @staticmethod
    def _extract_by_jsonpath(data: dict, jsonpath_expr: str):
        """使用 JSONPath 从字典中提取值"""
        try:
            jsonpath_expr = jsonpath_expr.strip()
            # 支持简写：如果不以 $ 开头，自动补充
            if not jsonpath_expr.startswith("$"):
                jsonpath_expr = "$." + jsonpath_expr
            
            path = parse(jsonpath_expr)
            matches = [match.value for match in path.find(data)]
            
            if matches:
                # 如果只有一个匹配，返回单个值；否则返回列表
                return matches[0] if len(matches) == 1 else matches
            return None
        except Exception:
            # JSONPath 解析失败，尝试点号分隔的简单路径
            return ResponseExtractor._extract_by_dot_path(data, jsonpath_expr)

    @staticmethod
    def _extract_by_dot_path(data: dict, field_path: str):
        """使用点号分隔路径提取值（兼容旧格式）"""
        try:
            # 去除可能的 $. 前缀
            field_path = re.sub(r"^\$\.?", "", field_path)
            
            parts = field_path.split(".")
            current = data
            
            for part in parts:
                part = part.strip()
                if isinstance(current, dict):
                    current = current.get(part)
                elif isinstance(current, list):
                    # 支持数组索引，如 data.items[0].id
                    if part.isdigit():
                        idx = int(part)
                        current = current[idx] if idx < len(current) else None
                    else:
                        return None
                else:
                    return None
            
            return current
        except Exception:
            return None

    @staticmethod
    def extract_and_store(response, extract_expr: str, context) -> dict:
        """提取字段并存储到全局上下文
        
        Args:
            response: requests.Response 对象
            extract_expr: 提取表达式字符串
            context: GlobalContext 对象
            
        Returns:
            dict: 成功提取的变量映射
        """
        extracted = ResponseExtractor.extract(response, extract_expr)
        
        for var_name, value in extracted.items():
            context.set(var_name, value)
        
        return extracted
