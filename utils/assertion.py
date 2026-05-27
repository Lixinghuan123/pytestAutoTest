import re
import json
from typing import Any, Dict, List, Union


def assert_response(response, expected_field: str, expected_value: str):
    """从响应 JSON 中提取字段值并断言期望值。

    支持多种格式：
    
    1. **单字段断言**（包含关系）:
       - expected_field: "data.token"
       - expected_value: "abc123"
       断言逻辑：期望值是否包含在实际值中
    
    2. **多字段断言**（逗号或分号分隔）:
       - expected_field: "data.status, data.code"
       - expected_value: "success, 200"
       断言逻辑：按顺序一一对应，每个字段进行包含判断
    
    3. **带操作符的断言**（支持多种比较）:
       - expected_field: "data.status=success, data.code=200, data.count>10"
       - expected_value: "" 或任意值（此时忽略）
       格式: field_path operator value
       支持的操作符: =, !=, >, >=, <, <=, contains
    
    支持点号分隔的嵌套字段，如 data.token 表示 response["data"]["token"]。
    """
    try:
        resp_json = response.json()
    except Exception:
        resp_json = {"_raw": response.text}

    # 尝试解析为带操作符的断言格式
    if "=" in expected_field or ">" in expected_field or "<" in expected_field or "contains" in expected_field:
        _assert_response_with_operators(resp_json, expected_field)
        return

    # 处理多字段断言（逗号或分号分隔）
    fields = []
    values = []
    
    # 支持逗号和分号分隔
    if "," in expected_field:
        fields = [f.strip() for f in expected_field.split(",") if f.strip()]
    elif ";" in expected_field:
        fields = [f.strip() for f in expected_field.split(";") if f.strip()]
    else:
        fields = [expected_field]
    
    if expected_value:
        if "," in expected_value:
            values = [v.strip() for v in expected_value.split(",") if v.strip()]
        elif ";" in expected_value:
            values = [v.strip() for v in expected_value.split(";") if v.strip()]
        else:
            values = [expected_value]
    
    # 一一对应断言
    for i, field in enumerate(fields):
        # 如果没有对应的期望值，则使用第一个期望值或跳过
        if i < len(values):
            expected = str(values[i])
        elif values:
            expected = str(values[0])
        else:
            continue
        
        actual = _extract_field(resp_json, field)
        
        assert _contains(actual, expected), (
            f"断言失败: {field} 实际值={actual!r}，期望包含={expected!r}"
        )


def _assert_response_with_operators(resp_json: dict, expected_str: str):
    """使用操作符进行响应断言"""
    # 支持的运算符（按优先级排序）
    operators = [
        ("!=", "!="),
        (">=", ">="),
        ("<=", "<="),
        (">", ">"),
        ("<", "<"),
        (" contains ", "contains"),
        ("=", "="),
    ]
    
    # 智能拆分条件（处理括号内的逗号）
    conditions = _split_conditions(expected_str)
    
    for condition in conditions:
        condition = condition.strip()
        if not condition:
            continue
        
        matched = False
        for op_str, op_name in operators:
            if op_str in condition:
                parts = condition.split(op_str, 1)
                field_path = parts[0].strip()
                expected_value = parts[1].strip()
                
                actual_value = _extract_field(resp_json, field_path)
                expected = _parse_value(expected_value)
                
                assert _compare(actual_value, op_name, expected), (
                    f"响应断言失败: {field_path} 实际值={actual_value!r}，期望{op_name}{expected!r}"
                )
                matched = True
                break
        
        if not matched:
            # 默认视为等于
            if "=" in condition:
                field_path, expected_value = condition.split("=", 1)
                actual_value = _extract_field(resp_json, field_path.strip())
                expected = _parse_value(expected_value.strip())
                assert str(actual_value) == str(expected), (
                    f"响应断言失败: {field_path.strip()} 实际值={actual_value!r}，期望={expected!r}"
                )


def _contains(actual, expected: str) -> bool:
    """判断期望值是否包含在实际值中"""
    if actual is None:
        return False
    
    # 将实际值转为字符串进行包含判断
    actual_str = str(actual)
    return expected in actual_str


def _extract_field(data: dict, field_path: str):
    """按点号路径从嵌套字典中提取值，如 data.token"""
    parts = field_path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _coerce_type(actual: Any, expected: str) -> Any:
    """根据实际值类型，将期望字符串转为对应类型再比较"""
    if actual is None:
        return expected
    if isinstance(actual, bool):
        return expected.lower() in ("true", "1", "yes")
    if isinstance(actual, int):
        try:
            return int(expected)
        except ValueError:
            return expected
    if isinstance(actual, float):
        try:
            return float(expected)
        except ValueError:
            return expected
    return expected


def _split_conditions(expected_str: str) -> list[str]:
    """智能拆分条件字符串，正确处理 JSON 数组中的逗号"""
    conditions = []
    current = ""
    bracket_count = 0
    brace_count = 0
    
    for char in expected_str:
        if char == "[":
            bracket_count += 1
            current += char
        elif char == "]":
            bracket_count -= 1
            current += char
        elif char == "{":
            brace_count += 1
            current += char
        elif char == "}":
            brace_count -= 1
            current += char
        elif char == "," and bracket_count == 0 and brace_count == 0:
            # 只有不在括号内的逗号才作为分隔符
            conditions.append(current.strip())
            current = ""
        else:
            current += char
    
    if current.strip():
        conditions.append(current.strip())
    
    return conditions


def _parse_expected(expected_str: str) -> List[Dict[str, Any]]:
    """解析期望字符串，支持多种格式：
    
    1. 简单格式："key=value, key2>value2, key3 contains value3"
    2. JSON数组格式：[{"key1": "value1"}, {"key1": "value2"}] - 多行全量对比
    3. 特殊断言："count=5", "count>10", "total(column)=100", "total(column)>=100"
    
    返回解析后的断言列表，每个元素包含:
    - type: "field" | "count" | "total"
    - key: 字段名或统计类型
    - operator: 比较运算符
    - value: 期望值
    """
    if not expected_str:
        return []
    
    expected_str = str(expected_str).strip()
    
    # 尝试解析为 JSON 数组（多行全量对比）
    if expected_str.startswith("[") and expected_str.endswith("]"):
        try:
            parsed = json.loads(expected_str)
            if isinstance(parsed, list):
                return [{"type": "rows", "value": parsed}]
        except json.JSONDecodeError:
            pass
    
    # 解析为多个断言条件（智能拆分，处理JSON数组中的逗号）
    assertions = []
    
    # 支持的运算符（按优先级排序）
    operators = [
        ("!=", "!="),
        (">=", ">="),
        ("<=", "<="),
        (">", ">"),
        ("<", "<"),
        (" contains ", "contains"),
        (" in ", "in"),
        (" between ", "between"),
        ("=", "="),
    ]
    
    for condition in _split_conditions(expected_str):
        condition = condition.strip()
        if not condition:
            continue
        
        matched = False
        for op_str, op_name in operators:
            if op_str in condition:
                parts = condition.split(op_str, 1)
                key = parts[0].strip()
                value = parts[1].strip()
                
                # 处理 count 和 total 特殊断言
                if key.startswith("count"):
                    assertions.append({
                        "type": "count",
                        "operator": op_name,
                        "value": _parse_value(value)
                    })
                elif key.startswith("total(") and key.endswith(")"):
                    col_name = key[6:-1].strip()
                    assertions.append({
                        "type": "total",
                        "key": col_name,
                        "operator": op_name,
                        "value": _parse_value(value)
                    })
                else:
                    assertions.append({
                        "type": "field",
                        "key": key,
                        "operator": op_name,
                        "value": _parse_value(value)
                    })
                matched = True
                break
        
        if not matched:
            # 默认视为等于
            if "=" in condition:
                key, value = condition.split("=", 1)
                assertions.append({
                    "type": "field",
                    "key": key.strip(),
                    "operator": "=",
                    "value": _parse_value(value.strip())
                })
    
    return assertions


def _parse_value(value_str: str) -> Any:
    """解析值字符串，尝试转为正确类型"""
    value_str = value_str.strip()
    
    # 尝试解析为数字
    try:
        if "." in value_str:
            return float(value_str)
        else:
            return int(value_str)
    except ValueError:
        pass
    
    # 尝试解析为布尔值
    if value_str.lower() == "true":
        return True
    if value_str.lower() == "false":
        return False
    
    # 尝试解析为 JSON（用于 in 和 between 操作符）
    if value_str.startswith("[") and value_str.endswith("]"):
        try:
            return json.loads(value_str)
        except json.JSONDecodeError:
            pass
    
    # 返回字符串
    return value_str


def _compare(actual: Any, operator: str, expected: Any) -> bool:
    """执行比较操作"""
    # 将 expected 转换为与 actual 相同的类型，保持 actual 不变
    expected_converted = _coerce_type(actual, str(expected))
    
    if operator == "=":
        return str(actual) == str(expected_converted)
    elif operator == "!=":
        return str(actual) != str(expected_converted)
    elif operator == ">":
        return float(actual) > float(expected_converted)
    elif operator == ">=":
        return float(actual) >= float(expected_converted)
    elif operator == "<":
        return float(actual) < float(expected_converted)
    elif operator == "<=":
        return float(actual) <= float(expected_converted)
    elif operator == "contains":
        return str(expected_converted) in str(actual)
    elif operator == "in":
        if not isinstance(expected_converted, list):
            return False
        return str(actual) in [str(v) for v in expected_converted]
    elif operator == "between":
        if not isinstance(expected_converted, list) or len(expected_converted) != 2:
            return False
        return float(expected_converted[0]) <= float(actual) <= float(expected_converted[1])
    
    return False


def assert_sql(actual_rows: List[Dict[str, Any]], expected_str: Union[str, List[str]]):
    """断言SQL查询结果是否符合期望。
    
    支持的断言格式：
    
    1. **字段断言**（默认检查第一行）:
       - `key=value` - 等于
       - `key!=value` - 不等于
       - `key>value`, `key>=value`, `key<value`, `key<=value` - 数值比较
       - `key contains value` - 包含
       - `key in [value1, value2]` - 属于列表
       - `key between [min, max]` - 在范围内
    
    2. **行数断言**:
       - `count=5` - 返回5行
       - `count>10` - 返回多于10行
       - `count>=0` - 返回至少0行
    
    3. **总和断言**:
       - `total(column)=100` - 某列总和为100
       - `total(amount)>=500` - amount列总和大于等于500
    
    4. **多行全量对比**:
       - `[{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]` - JSON数组格式，逐行对比
    
    5. **组合断言**:
       - `count=2, status=active, total(amount)>100`
    
    参数:
        actual_rows: SQL查询结果（字典列表）
        expected_str: 期望断言字符串或字符串列表（多条SQL对应多条断言）
    """
    # 如果是列表，说明是多条SQL的断言
    if isinstance(expected_str, list):
        for i, expected in enumerate(expected_str):
            if expected:
                _assert_single_sql(actual_rows[i], expected, f"SQL[{i+1}]")
        return
    
    _assert_single_sql(actual_rows, expected_str)


def _assert_single_sql(actual_rows: List[Dict[str, Any]], expected_str: str, prefix: str = ""):
    """断言单条SQL查询结果"""
    assertions = _parse_expected(expected_str)
    
    if not assertions:
        return
    
    # 添加前缀
    def add_prefix(msg: str) -> str:
        return f"{prefix}: {msg}" if prefix else msg
    
    for assert_item in assertions:
        assert_type = assert_item["type"]
        
        if assert_type == "rows":
            # 多行全量对比
            expected_rows = assert_item["value"]
            assert len(actual_rows) == len(expected_rows), (
                add_prefix(f"行数不匹配: 实际{len(actual_rows)}行，期望{len(expected_rows)}行")
            )
            
            for i, (actual, expected) in enumerate(zip(actual_rows, expected_rows)):
                for key, expected_value in expected.items():
                    assert key in actual, (
                        add_prefix(f"第{i+1}行字段 {key} 不存在")
                    )
                    actual_value = actual[key]
                    assert str(actual_value) == str(expected_value), (
                        add_prefix(f"第{i+1}行 {key} 不匹配: 实际={actual_value!r}, 期望={expected_value!r}")
                    )
        
        elif assert_type == "count":
            # 行数断言
            actual_count = len(actual_rows)
            operator = assert_item["operator"]
            expected_count = assert_item["value"]
            
            assert _compare(actual_count, operator, expected_count), (
                add_prefix(f"行数断言失败: 实际{actual_count}行，期望{operator}{expected_count}")
            )
        
        elif assert_type == "total":
            # 总和断言
            col_name = assert_item["key"]
            operator = assert_item["operator"]
            expected_total = assert_item["value"]
            
            actual_total = sum(row.get(col_name, 0) or 0 for row in actual_rows)
            
            assert _compare(actual_total, operator, expected_total), (
                add_prefix(f"总和断言失败: {col_name}列总和={actual_total}，期望{operator}{expected_total}")
            )
        
        elif assert_type == "field":
            # 字段断言（检查第一行）
            key = assert_item["key"]
            operator = assert_item["operator"]
            expected_value = assert_item["value"]
            
            if not actual_rows:
                assert False, add_prefix("SQL查询结果为空")
            
            actual = actual_rows[0]
            assert key in actual, add_prefix(f"字段 {key} 不存在于查询结果中")
            
            actual_value = actual[key]
            
            assert _compare(actual_value, operator, expected_value), (
                add_prefix(f"字段断言失败: {key} 实际值={actual_value!r}，期望{operator}{expected_value!r}")
            )
