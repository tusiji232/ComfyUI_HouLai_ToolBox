import base64
import io
import json

import numpy as np
import requests
import torch
from PIL import Image


class GeminiImageGenerationError(Exception):
    """Structured error used to control retry and downstream blocking behavior."""

    def __init__(self, message, retryable=True, response_text=""):
        super().__init__(message)
        self.retryable = retryable
        self.response_text = response_text or ""


class HouLai_Gemini_Image_Gen:
    """
    后来_Gemini图像生成节点
    支持 Gemini Image API 的文生图和图生图，并提供可选的失败重试能力。
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"multiline": True, "default": "Generate a beautiful landscape"}),
                "api_key": ("STRING", {"default": "", "multiline": False}),
                "base_url": (
                    "STRING",
                    {
                        "default": "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-pro-image-preview:generateContent",
                    },
                ),
                "aspect_ratio_mode": (
                    [
                        "auto",
                        "auto_from_image1",
                        "custom",
                        "1:1",
                        "4:3",
                        "3:4",
                        "16:9",
                        "9:16",
                        "21:9",
                        "3:2",
                        "2:3",
                    ],
                    {"default": "auto"},
                ),
                "custom_aspect_ratio": ("STRING", {"default": "1:1", "multiline": False}),
                "image_size": (["1K", "2K", "4K"], {"default": "2K"}),
                "response_modalities": (["IMAGE", "TEXT+IMAGE"], {"default": "IMAGE"}),
                "enable_retry": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "开启:失败自动重试并阻断失败分支",
                        "label_off": "关闭:单次失败后返回占位图",
                    },
                ),
                "retry_count": ("INT", {"default": 2, "min": 0, "max": 10, "step": 1}),
            },
            "optional": {
                "image1": ("IMAGE",),
                "image2": ("IMAGE",),
                "image3": ("IMAGE",),
                "image4": ("IMAGE",),
                "image5": ("IMAGE",),
                "image6": ("IMAGE",),
                "image7": ("IMAGE",),
                "image8": ("IMAGE",),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("image", "response_text", "info")
    FUNCTION = "generate_image"
    CATEGORY = "后来工具箱/Gemini"

    def __init__(self):
        self.timeout = 600

    def tensor_to_pil(self, tensor):
        """将 ComfyUI tensor 转换为 PIL Image。"""
        if tensor is None:
            return None
        image_np = tensor[0].cpu().numpy()
        image_np = np.clip(image_np * 255, 0, 255).astype(np.uint8)
        return Image.fromarray(image_np)

    def pil_to_tensor(self, pil_image):
        """将 PIL Image 转换为 ComfyUI tensor。"""
        image_np = np.array(pil_image).astype(np.float32) / 255.0
        return torch.from_numpy(image_np)[None,]

    def image_to_base64(self, image_tensor):
        """将输入图像转为 Base64。"""
        if image_tensor is None:
            return None

        pil_image = self.tensor_to_pil(image_tensor)
        buffered = io.BytesIO()
        pil_image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    def calculate_aspect_ratio(self, image_tensor):
        """根据输入图像推断宽高比。"""
        if image_tensor is None:
            return "1:1"

        height = image_tensor.shape[1]
        width = image_tensor.shape[2]

        def gcd(a, b):
            while b:
                a, b = b, a % b
            return a

        divisor = gcd(width, height)
        ratio_w = width // divisor
        ratio_h = height // divisor

        if ratio_w > 21 or ratio_h > 21:
            ratio = width / height
            common_ratios = {
                1.0: "1:1",
                1.33: "4:3",
                0.75: "3:4",
                1.78: "16:9",
                0.56: "9:16",
                2.33: "21:9",
                1.5: "3:2",
                0.67: "2:3",
            }
            closest = min(common_ratios.keys(), key=lambda item: abs(item - ratio))
            return common_ratios[closest]

        return f"{ratio_w}:{ratio_h}"

    def _get_blank_tensor(self):
        blank_image = Image.new("RGB", (1024, 1024), color="white")
        return self.pil_to_tensor(blank_image)

    def _build_full_url(self, base_url, api_key):
        separator = "&" if "?" in base_url else "?"
        return f"{base_url}{separator}key={api_key}"

    def _make_execution_blocker(self, message):
        try:
            from comfy_execution.graph import ExecutionBlocker

            return ExecutionBlocker(message)
        except Exception:
            print("[Gemini] 未找到 ExecutionBlocker，阻断失败时将回退到占位图输出。")
            return None

    def _build_legacy_failure_result(self, error_message, response_text=""):
        return (self._get_blank_tensor(), response_text, error_message)

    def _build_blocked_failure_result(self, error_message):
        image_blocker = self._make_execution_blocker(error_message)
        text_blocker = self._make_execution_blocker(error_message)
        if image_blocker is None or text_blocker is None:
            return self._build_legacy_failure_result(error_message)
        return (image_blocker, text_blocker, error_message)

    @staticmethod
    def _is_retryable_status(status_code):
        return status_code in {408, 409, 425, 429} or 500 <= int(status_code) <= 599

    @staticmethod
    def _canonical_aspect_ratio_mode(aspect_ratio_mode):
        mode = str(aspect_ratio_mode or "").strip()
        aliases = {
            "自动": "auto",
            "跟随图1": "auto_from_image1",
            "自定义": "custom",
        }
        return aliases.get(mode, mode)

    @staticmethod
    def _canonical_response_modalities(response_modalities):
        value = str(response_modalities or "").strip()
        aliases = {
            "仅图片": "IMAGE",
            "文本+图片": "TEXT+IMAGE",
        }
        return aliases.get(value, value)

    def _resolve_aspect_ratio(self, aspect_ratio_mode, custom_aspect_ratio, image1):
        aspect_ratio_mode = self._canonical_aspect_ratio_mode(aspect_ratio_mode)
        if aspect_ratio_mode == "auto":
            print("[Gemini] 使用自动宽高比模式，由 API 自行决定。")
            return None

        if aspect_ratio_mode == "auto_from_image1":
            if image1 is not None:
                aspect_ratio = self.calculate_aspect_ratio(image1)
                print(f"[Gemini] 已从 image1 自动检测宽高比: {aspect_ratio}")
                return aspect_ratio
            print("[Gemini] image1 为空，自动回退到 1:1。")
            return "1:1"

        if aspect_ratio_mode == "custom":
            return custom_aspect_ratio

        return aspect_ratio_mode

    def _build_request_parts(self, prompt, input_images):
        parts = [{"text": prompt}]
        for index, image_tensor in enumerate(input_images, start=1):
            base64_data = self.image_to_base64(image_tensor)
            parts.append(
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": base64_data,
                    }
                }
            )
            print(f"[Gemini] 已附加参考图 {index}")
        return parts

    def _parse_generated_content(self, result):
        response_text_parts = []
        generated_images = []

        if "candidates" not in result:
            return "", generated_images

        for candidate_index, candidate in enumerate(result["candidates"]):
            parts = candidate.get("content", {}).get("parts", [])
            for part_index, part in enumerate(parts):
                print(f"[Gemini] 处理 candidate[{candidate_index}].parts[{part_index}] -> {list(part.keys())}")

                if "text" in part:
                    response_text_parts.append(str(part["text"]))

                inline_data = part.get("inlineData") or part.get("inline_data")
                if inline_data and "data" in inline_data:
                    try:
                        image_bytes = base64.b64decode(inline_data["data"])
                        pil_image = Image.open(io.BytesIO(image_bytes))
                        generated_images.append(self.pil_to_tensor(pil_image))
                        print("[Gemini] 成功解析返回图片。")
                    except Exception as exc:
                        print(f"[Gemini] 解析返回图片失败: {exc}")

        return "\n".join(item for item in response_text_parts if item).strip(), generated_images

    def _build_success_info(self, aspect_ratio, image_size, input_count, output_count, attempt_count):
        aspect_ratio_display = "auto(API 自动)" if aspect_ratio is None else aspect_ratio
        info_lines = [
            "Gemini 图像生成成功",
            f"宽高比: {aspect_ratio_display}",
            f"图片尺寸: {image_size}",
            f"输入图片数: {input_count}",
            f"生成图片数: {output_count}",
            f"请求尝试次数: {attempt_count}",
        ]
        if attempt_count > 1:
            info_lines.append(f"失败重试次数: {attempt_count - 1}")
        return "\n".join(info_lines)

    def _raise_http_failure(self, response):
        error_message = f"API 错误: {response.status_code}\n{response.text}"
        raise GeminiImageGenerationError(
            error_message,
            retryable=self._is_retryable_status(response.status_code),
        )

    def _generate_image_once(
        self,
        prompt,
        api_key,
        base_url,
        aspect_ratio_mode,
        custom_aspect_ratio,
        image_size,
        response_modalities,
        image1=None,
        image2=None,
        image3=None,
        image4=None,
        image5=None,
        image6=None,
        image7=None,
        image8=None,
    ):
        all_images = [image1, image2, image3, image4, image5, image6, image7, image8]
        input_images = [image for image in all_images if image is not None]
        aspect_ratio = self._resolve_aspect_ratio(aspect_ratio_mode, custom_aspect_ratio, image1)
        parts = self._build_request_parts(prompt, input_images)

        normalized_modalities = self._canonical_response_modalities(response_modalities)
        modalities = ["IMAGE"] if normalized_modalities == "IMAGE" else ["TEXT", "IMAGE"]
        image_config = {"imageSize": image_size}
        if aspect_ratio is not None:
            image_config["aspectRatio"] = aspect_ratio

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": parts,
                }
            ],
            "generationConfig": {
                "responseModalities": modalities,
                "imageConfig": image_config,
            },
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        full_url = self._build_full_url(base_url, api_key)
        aspect_ratio_display = "auto(API 自动)" if aspect_ratio is None else aspect_ratio
        print("[Gemini] 正在调用 API...")
        print(
            f"[Gemini] 参数: 宽高比={aspect_ratio_display}, 图片尺寸={image_size}, 输入图片数={len(input_images)}"
        )

        try:
            response = requests.post(
                full_url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout as exc:
            raise GeminiImageGenerationError(f"请求超时: {exc}", retryable=True) from exc
        except requests.exceptions.RequestException as exc:
            raise GeminiImageGenerationError(f"请求失败: {exc}", retryable=True) from exc

        if response.status_code != 200:
            self._raise_http_failure(response)

        try:
            result = response.json()
        except ValueError as exc:
            raise GeminiImageGenerationError(f"响应解析失败: {exc}", retryable=True) from exc

        print("[Gemini] API 调用成功，开始解析响应。")
        response_text, generated_images = self._parse_generated_content(result)

        if not generated_images:
            error_message = (
                "API 返回成功，但未解析到可用图片。\n"
                f"响应顶层字段: {list(result.keys())}"
            )
            print(error_message)
            print("[Gemini] 完整响应如下:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            raise GeminiImageGenerationError(
                error_message,
                retryable=True,
                response_text=response_text,
            )

        combined_tensor = torch.cat(generated_images, dim=0)
        info = self._build_success_info(
            aspect_ratio=aspect_ratio,
            image_size=image_size,
            input_count=len(input_images),
            output_count=len(generated_images),
            attempt_count=1,
        )
        return combined_tensor, response_text, info

    def _update_success_info_attempts(self, info, attempt_count):
        lines = [line for line in str(info).splitlines() if line.strip()]
        filtered_lines = [
            line
            for line in lines
            if not line.startswith("请求尝试次数:") and not line.startswith("失败重试次数:")
        ]
        filtered_lines.append(f"请求尝试次数: {attempt_count}")
        if attempt_count > 1:
            filtered_lines.append(f"失败重试次数: {attempt_count - 1}")
        return "\n".join(filtered_lines)

    def _format_retry_failure_message(self, last_error_message, attempt_count, retry_count, retryable):
        lines = [
            "Gemini 图像生成失败",
            f"失败重试已结束: 共尝试 {attempt_count} 次（最大重试 {retry_count} 次）",
        ]
        if not retryable:
            lines.append("检测到不可重试错误，已提前停止继续重试。")
        lines.append(f"最后一次错误: {last_error_message}")
        return "\n".join(lines)

    def generate_image(
        self,
        prompt,
        api_key,
        base_url,
        aspect_ratio_mode,
        custom_aspect_ratio,
        image_size,
        response_modalities,
        enable_retry=False,
        retry_count=2,
        image1=None,
        image2=None,
        image3=None,
        image4=None,
        image5=None,
        image6=None,
        image7=None,
        image8=None,
    ):
        retry_enabled = bool(enable_retry)
        retry_limit = max(0, int(retry_count))

        if not api_key.strip():
            error_message = "API Key 不能为空，请填写有效的 Gemini API Key。"
            print(error_message)
            if retry_enabled:
                return self._build_blocked_failure_result(error_message)
            return self._build_legacy_failure_result(error_message)

        total_attempts = 1 + retry_limit if retry_enabled else 1
        last_error_message = ""
        last_response_text = ""
        last_retryable = True

        for attempt_index in range(1, total_attempts + 1):
            try:
                image_output, response_text, info = self._generate_image_once(
                    prompt=prompt,
                    api_key=api_key,
                    base_url=base_url,
                    aspect_ratio_mode=aspect_ratio_mode,
                    custom_aspect_ratio=custom_aspect_ratio,
                    image_size=image_size,
                    response_modalities=response_modalities,
                    image1=image1,
                    image2=image2,
                    image3=image3,
                    image4=image4,
                    image5=image5,
                    image6=image6,
                    image7=image7,
                    image8=image8,
                )
                if attempt_index > 1:
                    info = self._update_success_info_attempts(info, attempt_index)
                return image_output, response_text, info
            except GeminiImageGenerationError as exc:
                last_error_message = str(exc)
                last_response_text = exc.response_text
                last_retryable = exc.retryable
                print(f"[Gemini] 第 {attempt_index}/{total_attempts} 次尝试失败: {last_error_message}")

                should_retry = retry_enabled and exc.retryable and attempt_index < total_attempts
                if should_retry:
                    print("[Gemini] 将继续进行失败重试。")
                    continue
                break
            except Exception as exc:
                last_error_message = f"生成图片时发生未预期错误: {exc}"
                last_response_text = ""
                last_retryable = True
                print(last_error_message)
                import traceback

                traceback.print_exc()

                should_retry = retry_enabled and attempt_index < total_attempts
                if should_retry:
                    print("[Gemini] 未预期错误将继续尝试重试。")
                    continue
                break

        if retry_enabled:
            failure_message = self._format_retry_failure_message(
                last_error_message or "未知错误",
                attempt_count=attempt_index,
                retry_count=retry_limit,
                retryable=last_retryable,
            )
            print(failure_message)
            return self._build_blocked_failure_result(failure_message)

        print(last_error_message)
        return self._build_legacy_failure_result(last_error_message or "生成图片失败。", last_response_text)


NODE_CLASS_MAPPINGS = {
    "HouLai_Gemini_Image_Gen": HouLai_Gemini_Image_Gen,
}


NODE_DISPLAY_NAME_MAPPINGS = {
    "HouLai_Gemini_Image_Gen": "后来_Gemini图像生成 (Gemini Image)",
}
