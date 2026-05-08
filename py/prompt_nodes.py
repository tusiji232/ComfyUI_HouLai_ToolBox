import random
import re

class HouLaiRandomPrompts:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "text": ("STRING", {"multiline": True, "default": "", "placeholder": "在此粘贴您的提示词库..."}), 
                "extract_count": ("INT", {"default": 9, "min": 1, "max": 100, "step": 1, "display": "number"}), 
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}), 
                "filter_mode": (["No Change (不处理)", 
                                 "Trim & Remove Empty (去空行空格)", 
                                 "Remove Index (去序号 1. ->)",
                                 "Shuffle Only (仅打乱全量输出)"],), 
            },
        }

    RETURN_TYPES = ("STRING", "STRING",) 
    RETURN_NAMES = ("list_output", "combo_text_output",) 
    OUTPUT_IS_LIST = (True, False,)
    FUNCTION = "process_prompts"
    CATEGORY = "后来/Prompt"

    def process_prompts(self, text, extract_count, seed, filter_mode):
        if not text:
             return ([""], "")
             
        lines = text.split('\n')
        
        cleaned_lines = []
        for line in lines:
            if filter_mode == "No Change (不处理)":
                cleaned_lines.append(line)
            else:
                temp_line = line.strip()
                if "Remove Index" in filter_mode:
                    temp_line = re.sub(r'^\d+[\.\、\s]*', '', temp_line)
                if temp_line:
                    cleaned_lines.append(temp_line)

        if not cleaned_lines:
            return ([""], "") 

        random.seed(seed)
        
        if filter_mode == "Shuffle Only (仅打乱全量输出)":
            selected_lines = list(cleaned_lines)
            random.shuffle(selected_lines)
        else:
            if len(cleaned_lines) < extract_count:
                selected_lines = []
                while len(selected_lines) < extract_count:
                    selected_lines.extend(cleaned_lines)
                selected_lines = selected_lines[:extract_count]
                random.shuffle(selected_lines)
            else:
                selected_lines = random.sample(cleaned_lines, extract_count)

        combo_text = "\n".join(selected_lines)

        return (selected_lines, combo_text)