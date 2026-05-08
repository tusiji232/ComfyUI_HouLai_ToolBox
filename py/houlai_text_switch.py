import torch

class HouLai_8_Way_Text_Switch:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                # 范围 1 到 8，控制选择哪一路
                "select_source": ("INT", {"default": 1, "min": 1, "max": 8, "step": 1}),
            },
            "optional": {
                # --- 关键：lazy=True 实现惰性求值，forceInput=True 强制要求连线 ---
                # 如果你想允许不连线（支持手动输入文本框），可以去掉 forceInput=True
                # 这里为了严谨，我们先设为允许手动输入（去掉forceInput）
                "text_1": ("STRING", {"multiline": True, "lazy": True}),
                "text_2": ("STRING", {"multiline": True, "lazy": True}),
                "text_3": ("STRING", {"multiline": True, "lazy": True}),
                "text_4": ("STRING", {"multiline": True, "lazy": True}),
                "text_5": ("STRING", {"multiline": True, "lazy": True}),
                "text_6": ("STRING", {"multiline": True, "lazy": True}),
                "text_7": ("STRING", {"multiline": True, "lazy": True}),
                "text_8": ("STRING", {"multiline": True, "lazy": True}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("selected_text",)
    FUNCTION = "switch_text"
    CATEGORY = "HouLai_ToolBox/Logic"

    # --- 惰性求值逻辑 (和图片版一模一样) ---
    def check_lazy_status(self, select_source, **kwargs):
        needed_inputs = []
        try:
            idx = int(select_source)
        except:
            idx = 1
        
        if idx < 1: idx = 1
        if idx > 8: idx = 8

        # 告诉 ComfyUI：我只需要这一路的文本
        needed_inputs.append(f"text_{idx}")
        
        return needed_inputs

    def switch_text(self, select_source, 
                    text_1="", text_2="", text_3="", text_4="",
                    text_5="", text_6="", text_7="", text_8=""):
        
        # 1. 默认空值
        final_text = ""

        # 2. 索引计算
        try:
            idx = int(select_source) - 1
        except:
            idx = 0
            
        if idx < 0: idx = 0
        if idx > 7: idx = 7

        print(f"🔀 [8路文本分流] 正在使用文本通道: {idx + 1}")

        # 3. 数据提取
        text_list = [text_1, text_2, text_3, text_4, text_5, text_6, text_7, text_8]
        
        # 此时，只有被选中的 text 才有值（或者是默认空字符串），其他的可能没被计算
        selected_text_data = text_list[idx]

        if selected_text_data is not None:
            final_text = selected_text_data

        return (final_text,)