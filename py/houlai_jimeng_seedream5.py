import base64
import io
import json
from typing import List, Tuple

import numpy as np
from PIL import Image
import requests
import torch


class HouLai_Jimeng_Seedream5:
    """
    HouLai Jimeng Seedream 5 image generation node.
    Supports text-to-image and optional reference images via Ark compatible REST API.
    """

    DEFAULT_MODEL = "doubao-seedream-5-0-260128"
    DEFAULT_URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"multiline": True, "default": "A cinematic scene with rich details"}),
                "api_key": ("STRING", {"default": "", "multiline": False}),
                "model": (
                    [
                        "doubao-seedream-5-0-260128",
                        "doubao-seedream-4-5-251128",
                        "doubao-seedream-4-0-250828",
                    ],
                    {"default": "doubao-seedream-5-0-260128"},
                ),
                "api_url": ("STRING", {"default": cls.DEFAULT_URL, "multiline": False}),
                "size": (["1K", "2K", "4K"], {"default": "2K"}),
                "response_format": (["url", "b64_json"], {"default": "url"}),
                "watermark": ("BOOLEAN", {"default": True}),
                "seed": ("INT", {"default": -1, "min": -1, "max": 2147483647}),
                "sequential_image_generation": (["disabled", "auto"], {"default": "disabled"}),
                "max_images": ("INT", {"default": 1, "min": 1, "max": 15}),
                "enable_web_search": ("BOOLEAN", {"default": False}),
                "timeout_seconds": ("INT", {"default": 120, "min": 10, "max": 600}),
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
    RETURN_NAMES = ("image", "info", "image_urls")
    FUNCTION = "generate"
    CATEGORY = "后来工具箱/Jimeng"

    @staticmethod
    def _blank_tensor(width: int = 1024, height: int = 1024):
        blank = Image.new("RGB", (width, height), color="white")
        arr = np.array(blank).astype(np.float32) / 255.0
        return torch.from_numpy(arr)[None,]

    @staticmethod
    def _tensor_to_pil(image_tensor):
        arr = image_tensor[0].cpu().numpy()
        arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
        return Image.fromarray(arr)

    @staticmethod
    def _pil_to_tensor(pil_image):
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")
        arr = np.array(pil_image).astype(np.float32) / 255.0
        return torch.from_numpy(arr)[None,]

    def _tensor_to_data_url(self, image_tensor):
        pil_image = self._tensor_to_pil(image_tensor)
        buffered = io.BytesIO()
        pil_image.save(buffered, format="PNG")
        b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{b64}"

    def _normalize_api_url(self, api_url: str):
        url = (api_url or "").strip()
        if not url:
            return self.DEFAULT_URL
        url = url.rstrip("/")
        if url.endswith("/api/v3"):
            return f"{url}/images/generations"
        if "/images/generations" in url:
            return url
        return url

    def _collect_reference_images(self, *images) -> List[str]:
        refs = []
        for img in images:
            if img is not None:
                refs.append(self._tensor_to_data_url(img))
        return refs

    def _decode_result_images(
        self, items: list, timeout_seconds: int
    ) -> Tuple[List[torch.Tensor], List[str], List[str]]:
        tensors: List[torch.Tensor] = []
        urls: List[str] = []
        warnings: List[str] = []

        for idx, item in enumerate(items):
            if isinstance(item, str) and item.startswith("http"):
                item = {"url": item}

            if not isinstance(item, dict):
                warnings.append(f"Skip invalid item[{idx}] type: {type(item).__name__}")
                continue

            image_url = item.get("url") or item.get("image_url")
            b64_json = item.get("b64_json")

            if image_url:
                urls.append(image_url)
                try:
                    resp = requests.get(image_url, timeout=timeout_seconds)
                    resp.raise_for_status()
                    image = Image.open(io.BytesIO(resp.content))
                    tensors.append(self._pil_to_tensor(image))
                except Exception as e:
                    warnings.append(f"Download failed for item[{idx}]: {e}")
                continue

            if b64_json:
                try:
                    if isinstance(b64_json, str) and b64_json.startswith("data:image"):
                        b64_json = b64_json.split(",", 1)[1]
                    image_bytes = base64.b64decode(b64_json)
                    image = Image.open(io.BytesIO(image_bytes))
                    tensors.append(self._pil_to_tensor(image))
                except Exception as e:
                    warnings.append(f"Base64 decode failed for item[{idx}]: {e}")
                continue

            warnings.append(f"No url/b64_json in item[{idx}]")

        return tensors, urls, warnings

    def generate(
        self,
        prompt,
        api_key,
        model,
        api_url,
        size,
        response_format,
        watermark,
        seed,
        sequential_image_generation,
        max_images,
        enable_web_search,
        timeout_seconds,
        image1=None,
        image2=None,
        image3=None,
        image4=None,
        image5=None,
        image6=None,
        image7=None,
        image8=None,
    ):
        if not (api_key or "").strip():
            return (self._blank_tensor(), "API key is required", "")

        endpoint = self._normalize_api_url(api_url)
        refs = self._collect_reference_images(
            image1, image2, image3, image4, image5, image6, image7, image8
        )

        payload = {
            "model": model or self.DEFAULT_MODEL,
            "prompt": prompt,
            "size": size,
            "response_format": response_format,
            "stream": False,
            "watermark": bool(watermark),
            "sequential_image_generation": sequential_image_generation,
        }
        if seed is not None and int(seed) >= 0:
            payload["seed"] = int(seed)
        if refs:
            payload["image"] = refs[0] if len(refs) == 1 else refs
        if sequential_image_generation == "auto":
            payload["sequential_image_generation_options"] = {"max_images": int(max_images)}
        if enable_web_search:
            payload["tools"] = [{"type": "web_search"}]

        headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=int(timeout_seconds),
            )
        except Exception as e:
            return (self._blank_tensor(), f"Request failed: {e}", "")

        if response.status_code != 200:
            err = f"API Error {response.status_code}: {response.text}"
            return (self._blank_tensor(), err, "")

        try:
            result = response.json()
        except Exception as e:
            return (self._blank_tensor(), f"Invalid JSON response: {e}", "")

        data_items = result.get("data", [])
        if isinstance(data_items, dict):
            data_items = [data_items]
        if not data_items:
            # fallback for non-standard but compatible payloads
            if result.get("url") or result.get("b64_json"):
                data_items = [result]

        tensors, urls, warnings = self._decode_result_images(data_items, int(timeout_seconds))
        if not tensors:
            info = "No image decoded from response."
            if warnings:
                info += "\n" + "\n".join(warnings[:3])
            info += "\nRaw keys: " + ",".join(list(result.keys()))
            return (self._blank_tensor(), info, "\n".join(urls))

        combined = torch.cat(tensors, dim=0)
        info_lines = [
            f"Model: {payload['model']}",
            f"Output images: {len(tensors)}",
            f"Response format: {response_format}",
            f"Reference images: {len(refs)}",
            f"Sequential mode: {sequential_image_generation}",
            f"Web search: {enable_web_search}",
            f"Endpoint: {endpoint}",
        ]
        if warnings:
            info_lines.append("Warnings: " + " | ".join(warnings[:3]))
        info_lines.append("Raw response:")
        info_lines.append(json.dumps(result, ensure_ascii=False))
        return (combined, "\n".join(info_lines), "\n".join(urls))


NODE_CLASS_MAPPINGS = {
    "HouLai_Jimeng_Seedream5": HouLai_Jimeng_Seedream5,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "HouLai_Jimeng_Seedream5": "后来_Jimeng Seedream 5",
}
