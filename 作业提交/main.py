"""
CareerAI · 求职助手 —— 期末作品主程序
包含6个功能模块：
  1. JD职位解析器      — 正则+AI提取结构化职位信息
  2. 个人简历解析器      — 正则提取姓名/电话/邮箱/学校/公司/技能
  3. AI职位匹配追问系统 — 对比JD vs 简历缺口生成精准追问
  4. JD对标简历生成器    — 根据JD要求重组简历+自我介绍
  5. AI模拟面试官       — 4阶段结构化面试（支持多种人格）
  6. 多模型API网关      — 限流/用量/余额/模型路由

运行方式: python main.py
"""

import sys
import os
from pathlib import Path

# 将当前目录加入模块搜索路径
sys.path.insert(0, str(Path(__file__).parent))

# 导入6个模块
import module1_jd_parser
import module2_resume_parser
import module3_info_enquiry
import module4_resume_generator
import module5_ai_interviewer
import module6_api_gateway


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def show_banner():
    print("""
╔══════════════════════════════════════════════════════╗
║              CareerAI · 求职助手                      ║
║        2025-2026学年 《计算思维之问题求解》 期末作品     ║
╚══════════════════════════════════════════════════════╝
""")


def show_menu():
    print("=" * 55)
    print("  功能模块菜单")
    print("=" * 55)
    print("  1. JD职位解析器")
    print("      └─ 正则提取+AI结构化解析招聘JD")
    print("  2. 个人简历解析器")
    print("      └─ 正则提取姓名/电话/邮箱/学校/公司/技能")
    print("  3. AI职位匹配追问系统")
    print("      └─ 对比JD与简历缺口，生成精准追问问题")
    print("  4. JD对标简历生成器")
    print("      └─ 根据JD要求重组简历 + 生成自我介绍")
    print("  5. AI模拟面试官")
    print("      └─ 4阶段结构化面试（支持4种面试官人格）")
    print("  6. 多模型API网关")
    print("      └─ 限流保护 / 用量统计 / 余额守护 / 模型路由")
    print("  0. 退出程序")
    print("=" * 55)


def main():
    modules = {
        "1": ("JD职位解析器", module1_jd_parser),
        "2": ("个人简历解析器", module2_resume_parser),
        "3": ("AI职位匹配追问系统", module3_info_enquiry),
        "4": ("JD对标简历生成器", module4_resume_generator),
        "5": ("AI模拟面试官", module5_ai_interviewer),
        "6": ("多模型API网关", module6_api_gateway),
    }

    while True:
        clear_screen()
        show_banner()
        show_menu()
        choice = input("\n请选择功能模块（0-6）: ").strip()

        if choice == "0":
            print("\n感谢使用 CareerAI · 求职助手！")
            print("期末作品提交完成。")
            break

        if choice in modules:
            name, mod = modules[choice]
            clear_screen()
            print(f"\n正在启动【{name}】...")
            print("-" * 55)
            try:
                mod.run()
            except Exception as e:
                print(f"\n[错误] 模块运行异常: {e}")
            print("\n" + "-" * 55)
            input("\n按 Enter 键返回主菜单...")
        else:
            print("\n无效选项，请输入0-6之间的数字。")
            input("按 Enter 键继续...")


if __name__ == "__main__":
    main()
