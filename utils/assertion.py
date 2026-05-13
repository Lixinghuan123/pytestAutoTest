import re


def assert_response(response, expected_field: str, expected_value: str):
    """从响应 JSON 中提取字段值并断言期望值包含在实际值中。

    支持点号分隔的嵌套字段，如 data.token 表示 response["data"]["token"]。
    断言逻辑：期望值是否包含在实际值中（支持字符串、列表、字典）
    """
    try:
        resp_json = response.json()
    except Exception:
        resp_json = {"_raw": response.text}

    actual = _extract_field(resp_json, expected_field)
    expected = str(expected_value)  # 期望值转为字符串进行包含判断

    # 包含关系断言
    assert _contains(actual, expected), (
        f"断言失败: {expected_field} 实际值={actual!r}，期望包含={expected!r}"
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


def _coerce_type(actual, expected: str):
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


def assert_sql(actual_rows: list[dict], expected_str: str):
    """断言SQL查询结果是否符合期望。
    
    期望格式：key=value, key2=value2
    用逗号分隔多个字段，等号左边是列名，右边是期望值。
    断言逻辑：检查第一行数据是否匹配所有字段。
    """
    if not actual_rows:
        assert False, "SQL查询结果为空"
    
    # 解析期望字符串
    expected_dict = {}
    for pair in expected_str.split(","):
        pair = pair.strip()
        if "=" in pair:
            key, value = pair.split("=", 1)
            expected_dict[key.strip()] = value.strip()
    
    # 获取第一行数据进行断言
    actual = actual_rows[0]
    
    # 逐字段断言
    for key, expected in expected_dict.items():
        if key not in actual:
            assert False, f"字段 {key} 不存在于查询结果中"
        
        actual_value = actual[key]
        expected_value = _coerce_type(actual_value, expected)
        
        assert str(actual_value) == str(expected_value), (
            f"SQL断言失败: {key} 实际值={actual_value!r}，期望值={expected_value!r}"
        )
