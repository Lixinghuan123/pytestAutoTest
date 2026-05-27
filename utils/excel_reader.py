import math
import json
import pandas as pd


def _parse_multiple_sql(sql_str: str) -> list[str]:
    """解析 SQL 字符串，支持 JSON 数组或分号分隔格式"""
    if not sql_str or pd.isna(sql_str):
        return []
    
    sql_str = str(sql_str).strip()
    
    # 尝试解析为 JSON 数组
    if sql_str.startswith("[") and sql_str.endswith("]"):
        try:
            parsed = json.loads(sql_str)
            if isinstance(parsed, list):
                return [str(s).strip() for s in parsed if s]
        except json.JSONDecodeError:
            pass
    
    # 尝试按分号分隔
    if ";" in sql_str:
        return [s.strip() for s in sql_str.split(";") if s.strip()]
    
    # 返回单条 SQL
    return [sql_str]


def read_excel(file_path: str, sheet_name=0) -> list[dict]:
    """读取 Excel 测试用例，返回 [{列名: 值}, ...]，NaN 统一转为 None
    
    扩展功能：
    - sql 字段支持 JSON 数组格式如 ["SELECT * FROM a", "SELECT * FROM b"]
    - sql 字段支持分号分隔格式如 "SELECT * FROM a; SELECT * FROM b"
    - expected_sql 字段同样支持上述格式
    """
    df = pd.read_excel(file_path, sheet_name=sheet_name)
    cases = df.to_dict(orient="records")
    
    for case in cases:
        for k, v in case.items():
            # 处理 NaN
            if isinstance(v, float) and math.isnan(v):
                case[k] = None
            
            # 处理 sql 和 expected_sql 字段，解析为列表
            if k in ("sql", "expected_sql") and v:
                case[k] = _parse_multiple_sql(v)
    
    print("cases", cases)
    return cases


if __name__ == "__main__":
    read_excel("../test_cases.xlsx")