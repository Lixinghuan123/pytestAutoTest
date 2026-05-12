import json
import os
import uuid
import subprocess
import webbrowser
import http.server
import socketserver
import platform

CATEGORIES_CONFIG = [
    {"name": "接口断言失败", "matchedStatuses": ["failed"],
     "messageRegex": ".*断言.*|.*assert.*|.*期望.*|.*expected.*"},
    {"name": "接口返回错误", "matchedStatuses": ["failed"],
     "messageRegex": ".*status_code.*|.*StatusCode.*|.*4\\d{2}.*|.*5\\d{2}.*"},
    {"name": "连接/超时错误", "matchedStatuses": ["broken"],
     "messageRegex": ".*timeout.*|.*connection.*|.*refused.*"},
    {"name": "测试代码缺陷", "matchedStatuses": ["broken"]},
    {"name": "跳过的用例", "matchedStatuses": ["skipped"]},
]

ALLURE_BIN = r"D:\ruanjian\allure\allure-2.41.0\bin\allure.bat"
PORT = 8888


def build_behaviors_from_cases(report_dir: str):
    """从测试用例 JSON 中提取 epic/feature/story 标签，构造 behaviors.json"""
    cases_dir = os.path.join(report_dir, "data", "test-cases")
    if not os.path.isdir(cases_dir):
        return

    # feature -> story -> [cases]
    tree: dict[str, dict[str, list[dict]]] = {}
    all_uids = []

    for fname in os.listdir(cases_dir):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(cases_dir, fname), encoding="utf-8") as f:
            case = json.load(f)
        labels = case.get("labels", [])
        epic = ""
        feature = ""
        story = ""
        for lbl in labels:
            if lbl["name"] == "epic":
                epic = lbl["value"]
            elif lbl["name"] == "feature":
                feature = lbl["value"]
            elif lbl["name"] == "story":
                story = lbl["value"]

        # 跳过 pytest 自动生成的 package 标签（testcases.test_api 这种）
        # 取我们自己在 _set_allure_labels 里设的 "api_tests"

        # 归类：epic > feature > story
        if not epic:
            epic = "默认"
        if not feature:
            feature = "默认"
        if not story:
            story = "默认"

        node = {"name": case["name"], "uid": case["uid"],
                "parentUid": "", "status": case.get("status", "unknown"),
                "time": case.get("time", {}), "flaky": False,
                "newFailed": False, "newPassed": False, "newBroken": False,
                "retriesCount": 0, "retriesStatusChange": False,
                "parameters": case.get("parameters", []),
                "tags": []}
        all_uids.append(case["uid"])

        tree.setdefault(epic, {}).setdefault(feature, {}).setdefault(story, []).append(node)

    def make_uid(name: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_OID, name))

    children = []
    for epic_name, features in tree.items():
        epic_uid = make_uid(f"behavior-epic-{epic_name}")
        feature_nodes = []
        for feature_name, stories in features.items():
            feature_uid = make_uid(f"behavior-feature-{epic_name}-{feature_name}")
            story_nodes = []
            for story_name, cases in stories.items():
                story_uid = make_uid(f"behavior-story-{epic_name}-{feature_name}-{story_name}")
                for c in cases:
                    c["parentUid"] = story_uid
                story_nodes.append({
                    "uid": story_uid,
                    "name": story_name,
                    "children": cases,
                    "parentUid": feature_uid,
                })
            feature_nodes.append({
                "uid": feature_uid,
                "name": feature_name,
                "children": story_nodes,
                "parentUid": epic_uid,
            })
        children.append({
            "uid": epic_uid,
            "name": epic_name,
            "children": feature_nodes,
        })

    behaviors = {
        "uid": make_uid("behaviors-root"),
        "name": "behaviors",
        "children": children,
    }
    with open(os.path.join(report_dir, "data", "behaviors.json"), "w", encoding="utf-8") as f:
        json.dump(behaviors, f, ensure_ascii=False)
    print(f"  已生成 behaviors.json (共 {len(all_uids)} 个用例)")


def build_packages_from_cases(report_dir: str):
    """从测试用例 JSON 中提取 package 标签，构造 packages.json"""
    cases_dir = os.path.join(report_dir, "data", "test-cases")
    if not os.path.isdir(cases_dir):
        return

    # package -> [cases]
    tree: dict[str, list[dict]] = {}
    all_uids = []

    for fname in os.listdir(cases_dir):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(cases_dir, fname), encoding="utf-8") as f:
            case = json.load(f)
        labels = case.get("labels", [])
        pkg = "默认包"
        for lbl in labels:
            if lbl["name"] == "package":
                val = lbl["value"]
                # 跳过 pytest 自动生成的模块路径包名
                if "." in val and val not in ("api_tests",):
                    continue
                pkg = val

        node = {"name": case["name"], "uid": case["uid"],
                "parentUid": "", "status": case.get("status", "unknown"),
                "time": case.get("time", {}), "flaky": False,
                "newFailed": False, "newPassed": False, "newBroken": False,
                "retriesCount": 0, "retriesStatusChange": False,
                "parameters": case.get("parameters", []),
                "tags": []}
        all_uids.append(case["uid"])
        tree.setdefault(pkg, []).append(node)

    def make_uid(name: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_OID, name))

    children = []
    for pkg_name, cases in tree.items():
        pkg_uid = make_uid(f"package-{pkg_name}")
        for c in cases:
            c["parentUid"] = pkg_uid
        children.append({
            "uid": pkg_uid,
            "name": pkg_name,
            "children": cases,
        })

    packages = {
        "uid": make_uid("packages-root"),
        "name": "packages",
        "children": children,
    }
    with open(os.path.join(report_dir, "data", "packages.json"), "w", encoding="utf-8") as f:
        json.dump(packages, f, ensure_ascii=False)
    print(f"  已生成 packages.json (共 {len(all_uids)} 个用例)")


def main():
    try:
        # 1. 运行 pytest
        print("运行pytest测试...")
        subprocess.run(["uv", "run", "pytest", "-v", "--clean-alluredir"], check=True)

        # 2. 写入 categories 配置（--clean-alluredir 已清空目录，在此之后写入）
        print("\n写入 categories 配置...")
        with open("allure-results/categories.json", "w", encoding="utf-8") as f:
            json.dump(CATEGORIES_CONFIG, f, ensure_ascii=False, indent=2)

        # 3. 生成 Allure 报告
        print("\n生成Allure报告...")
        subprocess.run([
            ALLURE_BIN, "generate", "allure-results",
            "-o", "allure-report", "--clean", "--lang", "zh"
        ], check=True)

        # 4. 修复：allure generate 可能未生成 behaviors.json / packages.json
        print("\n修复缺失的行为/包数据文件...")
        report_dir = os.path.abspath("allure-report")
        build_behaviors_from_cases(report_dir)
        build_packages_from_cases(report_dir)

        # 5. 用 Python HTTP 服务器托管报告（避免 file:// 协议 404）
        print("\n启动报告服务器...")
        Handler = http.server.SimpleHTTPRequestHandler

        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            os.chdir(report_dir)
            url = f"http://localhost:{PORT}"
            print(f"报告地址: {url}")
            webbrowser.open(url)
            print("按 Ctrl+C 停止服务器...")
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print()

    except subprocess.CalledProcessError as e:
        print(f"执行失败: {e}")


if __name__ == "__main__":
    main()
