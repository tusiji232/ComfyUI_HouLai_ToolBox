# 文件路径: your_plugin_path/py/houlai_data_gate.py

class AnyType(str):
    """
    定义一个万能类型，用于欺骗 ComfyUI 的类型检查。
    这样无论是 Image, Mask, Latent 还是 Model 都可以连入。
    """
    def __ne__(self, __value: object) -> bool:
        return False

# 实例化万能类型
ANY_TYPE = AnyType("*")

class HouLai_Data_Gate:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "enable": ("BOOLEAN", {"default": True, "label_on": "True (Pass)", "label_off": "False (Block)"}),
            },
            "optional": {
                # 使用万能类型，并设为 optional，防止未连接时报错
                "data": (ANY_TYPE,),
            }
        }

    # 返回类型也是万能类型，确保可以连接到任何下游节点
    RETURN_TYPES = (ANY_TYPE,)
    RETURN_NAMES = ("data",)
    FUNCTION = "gate_data"
    CATEGORY = "HouLai_ToolBox"

    # 核心逻辑：惰性求值控制
    def check_lazy_status(self, enable, data=None):
        if enable:
            # 如果开关打开，我们需要 'data' 输入，系统会去计算上游节点
            return ["data"]
        else:
            # 如果开关关闭，告诉系统我们不需要任何输入
            # 这样上游节点（如加载图像）根本不会被执行
            return []

    # 执行逻辑：数据传输控制
    def gate_data(self, enable, data=None):
        if enable:
            # 开关打开：原样透传数据
            return (data,)
        else:
            # 开关关闭：返回 None
            # 下游带有 optional 输入（空心点）的节点会将其视为“未连接”
            return (None,)