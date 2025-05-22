# launcher.py
import sys
import os
from RAG_flow import get_connection_pool

def cleanup():
    pool = get_connection_pool()
    if pool:
        pool.close()
    print("✅ 连接池已安全关闭")


def main():
    try:
        # 设置项目根目录（请根据实际情况修改）
        project_dir = r"D:\Python\PyCharm_Workspace\QA-App"

        # 切换到项目目录，确保能找到 .py 文件
        os.chdir(project_dir)

        # 构建完整的脚本路径并转为绝对路径
        app_path = os.path.join(project_dir, "Neuclear_QA_App.py")
        absolute_app_path = os.path.abspath(app_path)

        print(f"当前工作目录: {os.getcwd()}")
        print(f"目标文件是否存在？ {os.path.exists(absolute_app_path)}")
        print(f"目标文件路径: {absolute_app_path}")

        if not os.path.exists(absolute_app_path):
            raise FileNotFoundError(f"找不到指定的文件: {absolute_app_path}")

        import sys
        import subprocess

        subprocess.run([sys.executable, "-m", "streamlit", "run", absolute_app_path])

    except KeyboardInterrupt:
        print("\n🛑 用户中断 (Ctrl+C)，正在清理资源...")
        cleanup()
        sys.exit(0)

    except Exception as e:
        print(f"\n❌ 发生严重错误: {e}")
        cleanup()
        sys.exit(1)


if __name__ == "__main__":
    main()
