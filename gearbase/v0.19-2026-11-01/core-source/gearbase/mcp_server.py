"""MCP 服务器启动脚本（stdio）：python3 -I mcp_server.py [--state-dir 目录]

-I（隔离模式）下当前目录不在 sys.path，所以这里显式加入本脚本所在目录（包根）；零第三方依赖。
不给 --state-dir（也无环境变量 GEARBASE_STATE_DIR）则设计状态只在进程内存里。
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from gearmath.tools.ai_tools import serve  # noqa: E402

if __name__ == "__main__":
    argv = sys.argv[1:]
    sd = argv[argv.index("--state-dir") + 1] if "--state-dir" in argv and argv.index("--state-dir") + 1 < len(argv) else None
    serve(state_dir=sd)
