import torch
import numpy as np
import cv2

class HouLai_Recolor_Batch_V3:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                "mask": ("MASK",),
                "hex_color_1": ("STRING", {"default": "#c9d7ed"}),
                "hex_color_2": ("STRING", {"default": "#ffcccc"}),
                "hex_color_3": ("STRING", {"default": "#d1ffcc"}),
                "hex_color_4": ("STRING", {"default": "#fdfd96"}),
                "conserve_brightness": ("BOOLEAN", {"default": True}),
                "clamp_highlights": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "apply_batch_recolor"
    CATEGORY = "✨后来工具箱"

    def apply_batch_recolor(self, image, mask, hex_color_1, hex_color_2, hex_color_3, hex_color_4, conserve_brightness, clamp_highlights):
        # 收集所有输入的颜色
        hex_list = [hex_color_1, hex_color_2, hex_color_3, hex_color_4]
        
        # 获取输入图片的 Batch 信息 (目前仅取 Batch 中的第一张作为基础图，以防逻辑冲突)
        # 如果你输入的是多张图，逻辑会按第一张图进行批量改色
        base_img = image[0].cpu().numpy()
        base_mask = mask[0].cpu().numpy()

        # 尺寸对齐 Mask 和 Image
        if base_mask.shape != base_img.shape[:2]:
            base_mask = cv2.resize(base_mask, (base_img.shape[1], base_img.shape[0]), interpolation=cv2.INTER_LINEAR)

        output_batch = []

        for hex_str in hex_list:
            if not hex_str or len(hex_str) < 4: continue # 跳过空输入
            
            # 1. 颜色处理
            hex_str = hex_str.lstrip('#')
            target_rgb = np.array([int(hex_str[i:i+2], 16) for i in (0, 2, 4)]) / 255.0
            target_rgb_img = (target_rgb.reshape(1, 1, 3) * 255).astype(np.uint8)
            target_lab = cv2.cvtColor(target_rgb_img, cv2.COLOR_RGB2LAB)[0][0].astype(np.float32)

            # 2. 转换原图到 LAB
            img_uint8 = (base_img * 255).astype(np.uint8)
            lab = cv2.cvtColor(img_uint8, cv2.COLOR_RGB2LAB).astype(np.float32)
            l, a, b = cv2.split(lab)

            # 3. 明度保留算法
            if conserve_brightness:
                mask_bool = base_mask > 0.5
                if np.any(mask_bool):
                    current_l_mean = np.mean(l[mask_bool])
                    l_shift = target_lab[0] - current_l_mean
                    # 动态补偿亮度分布
                    l[mask_bool] = np.clip(l[mask_bool] + l_shift * 0.4, 0, 255)

            # 4. 颜色混合与高光保护
            mask_3d = base_mask * (1.0 - (l / 255.0) * (1.0 - clamp_highlights))
            
            new_a = a * (1 - mask_3d) + target_lab[1] * mask_3d
            new_b = b * (1 - mask_3d) + target_lab[2] * mask_3d

            # 5. 合并并转回 RGB
            merged_lab = cv2.merge([l, new_a, new_b]).astype(np.uint8)
            res_rgb = cv2.cvtColor(merged_lab, cv2.COLOR_LAB2RGB)
            output_batch.append(res_rgb.astype(np.float32) / 255.0)

        # 将列表转换为 ComfyUI 识别的 Image Batch Tensor
        return (torch.from_numpy(np.array(output_batch)),)

# 注册代码
NODE_CLASS_MAPPINGS = {"HouLai_Recolor_Batch_V3": HouLai_Recolor_Batch_V3}
NODE_DISPLAY_NAME_MAPPINGS = {"HouLai_Recolor_Batch_V3": "🎨 后来_批量质感改色 V3"}