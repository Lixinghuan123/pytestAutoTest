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
