# ComfyUI_HouLai_ToolBox/py/image_nodes.py
# 图像处理节点

import torch
import numpy as np
from PIL import Image
import comfy.utils

class HouLaiImageProcessor:
    """图像处理基础节点"""
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
            },
            "optional": {
                "width": ("INT", {"default": 512, "min": 64, "max": 4096, "step": 64}),
                "height": ("INT", {"default": 512, "min": 64, "max": 4096, "step": 64}),
            }
        }
    
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "process_image"
    CATEGORY = "后来工具箱/图像处理"
    
    def process_image(self, image, width=512, height=512):
        # 简单的图像处理示例
        return (image,)


# 节点注册映射
NODE_CLASS_MAPPINGS = {
    "HouLaiImageProcessor": HouLaiImageProcessor,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "HouLaiImageProcessor": "后来_图像处理器",
}
