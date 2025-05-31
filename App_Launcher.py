import sys
import os
import subprocess
import signal
from RAG_flow import get_connection_pool

def cleanup():
    pool = get_connection_pool()
    if pool:
        pool.close()
    print("✅ 连接池已安全关闭")


def signal_handler(sig, frame):
    print("\n🛑 用户中断 (Ctrl+C)，正在清理资源...")
    cleanup()
    sys.exit(0)


def main():
    try:
        project_dir = r"D:\Python\PyCharm_Workspace\QA-App"
        os.chdir(project_dir)

        app_path = os.path.join(project_dir, "Neuclear_QA_App.py")
        absolute_app_path = os.path.abspath(app_path)

        if not os.path.exists(absolute_app_path):
            raise FileNotFoundError(f"找不到指定的文件: {absolute_app_path}")

        # 使用 Popen 启动 Streamlit 应用
        proc = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", absolute_app_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        # 实时输出日志
        while True:
            line = proc.stdout.readline()
            if not line and proc.poll() is not None:
                break
            print(line.strip())

        proc.wait()

    except KeyboardInterrupt:
        signal_handler(None, None)
    except Exception as e:
        print(f"\n❌ 发生严重错误: {e}")
        cleanup()
        sys.exit(1)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    main()
