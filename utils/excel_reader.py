import math
import pandas as pd


def read_excel(file_path: str, sheet_name=0) -> list[dict]:
    """读取 Excel 测试用例，返回 [{列名: 值}, ...]，NaN 统一转为 None"""
    df = pd.read_excel(file_path, sheet_name=sheet_name)
    cases = df.to_dict(orient="records")
    for case in cases:
        for k, v in case.items():
            if isinstance(v, float) and math.isnan(v):
                case[k] = None
    print("cases",cases)
    return cases


if __name__ == "__main__":
    read_excel("../test_cases.xlsx")