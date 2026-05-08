import torch
import numpy as np

# --- 类名修改为 Image_Switch ---
class HouLai_8_Way_Image_Switch:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                # 范围 1 到 8
                "select_source": ("INT", {"default": 1, "min": 1, "max": 8, "step": 1}),
            },
            "optional": {
                # 惰性求值标记
                "image_1": ("IMAGE", {"lazy": True}),
                "image_2": ("IMAGE", {"lazy": True}),
                "image_3": ("IMAGE", {"lazy": True}),
                "image_4": ("IMAGE", {"lazy": True}),
                "image_5": ("IMAGE", {"lazy": True}),
                "image_6": ("IMAGE", {"lazy": True}),
                "image_7": ("IMAGE", {"lazy": True}),
                "image_8": ("IMAGE", {"lazy": True}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("selected_image",)
    FUNCTION = "switch_data"
    CATEGORY = "HouLai_ToolBox/Logic"

    def check_lazy_status(self, select_source, **kwargs):
        needed_inputs = []
        try:
            idx = int(select_source)
        except:
            idx = 1
        if idx < 1: idx = 1
        if idx > 8: idx = 8
        needed_inputs.append(f"image_{idx}")
        return needed_inputs

    def switch_data(self, select_source, 
                    image_1=None, image_2=None, image_3=None, image_4=None,
                    image_5=None, image_6=None, image_7=None, image_8=None):
        
        final_image = torch.zeros((1, 512, 512, 3), dtype=torch.float32, device="cpu")
        try:
            idx = int(select_source) - 1
        except:
            idx = 0
        if idx < 0: idx = 0
        if idx > 7: idx = 7

        print(f"🔀 [8路图片分流] 正在计算通道: {idx + 1}")

        image_list = [image_1, image_2, image_3, image_4, image_5, image_6, image_7, image_8]
        selected_img_data = image_list[idx]

        if selected_img_data is not None:
            final_image = selected_img_data

        return (final_image,)