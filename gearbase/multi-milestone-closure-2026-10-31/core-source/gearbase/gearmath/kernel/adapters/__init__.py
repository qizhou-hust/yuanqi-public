"""可选求解器适配器。核心路径不 import 本子包；缺少第三方依赖时抛 AdapterUnavailable，不影响其余功能。"""


class AdapterUnavailable(ImportError):
    """可选依赖未安装。"""
