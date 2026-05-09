import pandas as pd


def read_excel(file_path, sheet_name=0):
    """
    读取 Excel 测试用例
    :param file_path: Excel 文件路径
    :param sheet_name: 工作表名或索引（默认第1个）
    :return: 测试用例列表（每条用例是字典）
    """
    df = pd.read_excel(file_path, sheet_name=sheet_name)

    # 把 DataFrame 转成 [{}, {}, {}] 格式（适合接口自动化）
    case_list = df.to_dict(orient="records")

    return case_list


# 测试一下（你运行这个文件就能看到效果）
if __name__ == '__main__':
    cases = read_excel("test_cases.xlsx")  # 你的Excel文件名
    for case in cases:
        print(case)