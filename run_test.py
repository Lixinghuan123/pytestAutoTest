import os
import subprocess
import platform


def main():
    try:
        # 1. 运行pytest测试
        print("运行pytest测试...")
        subprocess.run(["uv", "run", "pytest", "-v","--clean-alluredir"], check=True)
        
        # 2. 生成Allure报告
        print("\n生成Allure报告...")
        subprocess.run([
            r"D:\ruanjian\allure\allure-2.41.0\bin\allure.bat", 
            "generate", "allure-results", "-o", "allure-report", "--clean", "--lang", "zh"
        ], check=True)
        
        # 3. 在浏览器中打开报告（使用allure open启动本地服务器）
        print("\n打开报告...")
        subprocess.run([
            r"D:\ruanjian\allure\allure-2.41.0\bin\allure.bat", 
            "open", "allure-report"
        ])
        
        print("完成!")
    
    except subprocess.CalledProcessError as e:
        print(f"执行失败: {e}")


if __name__ == "__main__":
    main()