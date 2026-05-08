import base64
import io
import requests
import time
import uuid

import numpy as np
import torch
from PIL import Image


class NanoBananaScheduler:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "middleware_url": ("STRING", {"default": "http://127.0.0.1:8001"}),
                "api_key": ("STRING", {"default": "", "multiline": False}),
                "dispatch_token": ("STRING", {"default": "", "multiline": False}),
                "api_base_url": ("STRING", {"default": "https://api.example.com", "multiline": False}),
                "provider": (
                    ["openai_images", "gpt_chat_completions", "gemini_native", "auto"],
                    {"default": "openai_images"},
                ),
                "prompt": ("STRING", {"multiline": True, "default": "one cat\ntwo dogs", "dynamicPrompts": True}),
                "mode": (["text2img", "img2img"], {"default": "text2img"}),
                "model": (
                    ["nano-banana-2", "nano-banana-2-2k", "nano-banana-2-4k", "gpt-image-2"],
                    {"default": "nano-banana-2"},
                ),
                "custom_model": ("STRING", {"default": "", "multiline": False}),
                "aspect_ratio": (
                    ["auto", "16:9", "4:3", "4:5", "3:2", "1:1", "2:3", "3:4", "5:4", "9:16", "21:9", "custom"],
                    {"default": "auto"},
                ),
                "custom_aspect_ratio": ("STRING", {"default": "", "multiline": False}),
                "image_size": (["1K", "2K", "4K"], {"default": "2K"}),
                "quality": (["auto", "high", "medium", "low"], {"default": "auto"}),
                "size": (["auto", "1024x1024", "1536x1024", "1024x1536"], {"default": "auto"}),
                "background": (["auto", "transparent", "opaque"], {"default": "auto"}),
                "output_format": (["png", "jpeg", "webp"], {"default": "png"}),
                "moderation": (["auto", "low"], {"default": "auto"}),
                "response_format": (["b64_json", "url"], {"default": "b64_json"}),
                "n": ("INT", {"default": 1, "min": 1, "max": 4}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 2147483647}),
                "clear_chats": ("BOOLEAN", {"default": True}),
                "image_download_timeout": ("INT", {"default": 600, "min": 60, "max": 1200, "step": 10}),
                "conversation_key": ("STRING", {"default": "", "multiline": False}),
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

    RETURN_TYPES = ()
    RETURN_NAMES = ()
    OUTPUT_NODE = True
    FUNCTION = "process"
    CATEGORY = "NanoBanana"

    def _build_request_options(
        self,
        quality,
        size,
        background,
        output_format,
        moderation,
        response_format,
        n,
        clear_chats,
        image_download_timeout,
        conversation_key,
    ):
        request_options = {
            "quality": quality,
            "size": size,
            "background": background,
            "output_format": output_format,
            "moderation": moderation,
            "response_format": response_format,
            "n": n,
            "clear_chats": clear_chats,
            "image_download_timeout": image_download_timeout,
        }
        clean_conversation_key = (conversation_key or "").strip()
        if clean_conversation_key:
            request_options["conversation_key"] = clean_conversation_key
        return request_options

    def process(
        self,
        middleware_url,
        api_key,
        dispatch_token,
        api_base_url,
        provider,
        prompt,
        mode,
        model,
        custom_model,
        aspect_ratio,
        custom_aspect_ratio,
        image_size,
        quality,
        size,
        background,
        output_format,
        moderation,
        response_format,
        n,
        seed,
        clear_chats,
        image_download_timeout,
        conversation_key,
        **kwargs,
    ):
        final_model = custom_model.strip() if custom_model and custom_model.strip() else model
        final_aspect_ratio = custom_aspect_ratio.strip() if aspect_ratio == "custom" and custom_aspect_ratio.strip() else aspect_ratio

        collected_images = []
        for index in range(1, 9):
            key = f"image{index}"
            if key in kwargs and kwargs[key] is not None:
                img_tensor = kwargs[key][0]
                img_np = 255.0 * img_tensor.cpu().numpy()
                img_pil = Image.fromarray(np.clip(img_np, 0, 255).astype(np.uint8))
                buffered = io.BytesIO()
                img_pil.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
                collected_images.append(f"data:image/png;base64,{img_str}")

        prompt_list = [item.strip() for item in prompt.split("\n") if item.strip()]
        if not prompt_list:
            prompt_list = [""]

        print(f"[NanoBanana] Preparing to dispatch {len(prompt_list)} task(s)")

        batch_id = f"NB_{time.time_ns()}_{uuid.uuid4().hex[:6]}"
        manifest_items = []

        for idx, prompt_text in enumerate(prompt_list):
            task_conversation_key = (conversation_key or "").strip()
            if task_conversation_key and len(prompt_list) > 1:
                task_conversation_key = f"{task_conversation_key}:{idx}"

            request_options = self._build_request_options(
                quality=quality,
                size=size,
                background=background,
                output_format=output_format,
                moderation=moderation,
                response_format=response_format,
                n=n,
                clear_chats=clear_chats,
                image_download_timeout=image_download_timeout,
                conversation_key=task_conversation_key,
            )
            request_options["gpt_request"] = final_model.strip().lower().startswith("gpt")

            manifest_items.append(
                {
                    "tid": f"{batch_id}_T{idx}",
                    "prompt": prompt_text,
                    "image_uris": collected_images,
                    "api_key": api_key,
                    "api_base_url": api_base_url,
                    "provider": provider,
                    "mode": mode,
                    "model": final_model,
                    "aspect_ratio": final_aspect_ratio,
                    "image_size": image_size,
                    "seed": seed + idx if seed > 0 else 0,
                    "request_options": request_options,
                    "slot": {"image_index": idx, "prompt_index": idx, "copy_index": 0},
                }
            )

        payload = {
            "batch_id": batch_id,
            "frontend": {"order_id": batch_id, "callback_url": ""},
            "nanobana_config": {},
            "manifest": manifest_items,
        }

        ui_msg = ""
        try:
            url = f"{middleware_url.rstrip('/')}/api/v1/dispatch"
            headers = {"Content-Type": "application/json"}
            token = (dispatch_token or "").strip()
            if token:
                headers["X-Dispatch-Token"] = token

            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=30,
                proxies={"http": None, "https": None},
            )

            if response.status_code == 200:
                print(f"[NanoBanana] Dispatch succeeded. Batch ID: {batch_id}")
                ui_msg = (
                    f"Dispatched {len(prompt_list)} task(s) to middleware.\n"
                    f"Provider: {provider}\n"
                    f"Batch ID: {batch_id}\n"
                    "Results will be written under archive."
                )
            else:
                print(f"[NanoBanana] Dispatch failed: {response.status_code}")
                ui_msg = f"Dispatch failed: {response.text}"
        except Exception as exc:
            print(f"[NanoBanana] Connection error: {exc}")
            ui_msg = f"Unable to reach middleware: {exc}"

        return {"ui": {"text": ui_msg}}


class HouLai_Nanobanan:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"multiline": True}),
                "mode": (["text2img", "img2img"], {"default": "text2img"}),
                "api_key": ("STRING", {"default": "", "multiline": False}),
                "api_base_url": ("STRING", {"default": "https://api.example.com", "multiline": False}),
                "model": ("STRING", {"default": "nano-banana-2", "multiline": False}),
                "aspect_ratio": (
                    ["auto", "16:9", "4:3", "4:5", "3:2", "1:1", "2:3", "3:4", "5:4", "9:16", "21:9", "custom"],
                    {"default": "auto"},
                ),
                "custom_aspect_ratio": ("STRING", {"default": "", "multiline": False}),
                "image_size": (["1K", "2K", "4K"], {"default": "2K"}),
                "response_format": (["url", "b64_json"], {"default": "url"}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 2147483647}),
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
                "image9": ("IMAGE",),
                "image10": ("IMAGE",),
                "image11": ("IMAGE",),
                "image12": ("IMAGE",),
                "image13": ("IMAGE",),
                "image14": ("IMAGE",),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("image", "response", "image_url")
    FUNCTION = "generate_image"
    CATEGORY = "HouLai/NanoBanana"

    def __init__(self):
        self.timeout = 600

    def _blank_tensor(self):
        blank_image = Image.new("RGB", (1024, 1024), color="white")
        blank_np = np.array(blank_image).astype(np.float32) / 255.0
        return torch.from_numpy(blank_np)[None,]

    def _tensor_to_pil(self, tensor):
        img_np = tensor[0].cpu().numpy()
        img_np = np.clip(img_np * 255.0, 0, 255).astype(np.uint8)
        return Image.fromarray(img_np)

    def _pil_to_tensor(self, pil_image):
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")
        img_np = np.array(pil_image).astype(np.float32) / 255.0
        return torch.from_numpy(img_np)[None,]

    def _effective_ratio(self, aspect_ratio, custom_aspect_ratio):
        if aspect_ratio == "custom":
            return custom_aspect_ratio.strip() or "auto"
        return aspect_ratio

    def generate_image(
        self,
        prompt,
        mode,
        api_key,
        api_base_url,
        model,
        aspect_ratio,
        custom_aspect_ratio,
        image_size,
        response_format,
        seed,
        **kwargs,
    ):
        if not api_key.strip():
            return (self._blank_tensor(), "API key is required", "")

        base = (api_base_url or "").strip().rstrip("/")
        if not base:
            base = "https://api.example.com"
        final_ratio = self._effective_ratio(aspect_ratio, custom_aspect_ratio)

        try:
            headers = {"Authorization": f"Bearer {api_key}"}

            if mode == "text2img":
                req_headers = dict(headers)
                req_headers["Content-Type"] = "application/json"

                payload = {
                    "prompt": prompt,
                    "model": model,
                    "aspect_ratio": final_ratio,
                    "response_format": response_format,
                    "image_size": image_size,
                }
                if seed > 0:
                    payload["seed"] = seed

                response = requests.post(
                    f"{base}/v1/images/generations",
                    headers=req_headers,
                    json=payload,
                    timeout=self.timeout,
                )
                image_count = 0
            else:
                images = []
                for index in range(1, 15):
                    key = f"image{index}"
                    if kwargs.get(key) is not None:
                        images.append(kwargs[key])

                files = []
                for idx, img in enumerate(images):
                    pil_img = self._tensor_to_pil(img)
                    buffered = io.BytesIO()
                    pil_img.save(buffered, format="PNG")
                    buffered.seek(0)
                    files.append(("image", (f"image_{idx}.png", buffered, "image/png")))

                data = {
                    "prompt": prompt,
                    "model": model,
                    "aspect_ratio": final_ratio,
                    "response_format": response_format,
                    "image_size": image_size,
                }
                if seed > 0:
                    data["seed"] = str(seed)

                response = requests.post(
                    f"{base}/v1/images/edits",
                    headers=headers,
                    data=data,
                    files=files,
                    timeout=self.timeout,
                )
                image_count = len(images)

            if response.status_code != 200:
                return (self._blank_tensor(), f"API Error: {response.status_code} - {response.text}", "")

            result = response.json()
            data_items = result.get("data")
            if not data_items:
                return (self._blank_tensor(), "No image data in response", "")
            if not isinstance(data_items, list):
                data_items = [data_items]

            tensors = []
            image_urls = []
            response_info = f"Generated {len(data_items)} images using {model}\n"
            response_info += f"Image size: {image_size}\n"
            response_info += f"Aspect ratio: {final_ratio}\n"
            if mode == "img2img":
                response_info += f"Input images: {image_count}\n"
            if seed > 0:
                response_info += f"Seed: {seed}\n"

            for index, item in enumerate(data_items):
                if isinstance(item, dict) and item.get("b64_json"):
                    image_data = base64.b64decode(item["b64_json"])
                    gen_image = Image.open(io.BytesIO(image_data))
                    tensors.append(self._pil_to_tensor(gen_image))
                    response_info += f"Image {index + 1}: Base64 data\n"
                elif isinstance(item, dict) and item.get("url"):
                    image_url = item["url"]
                    image_urls.append(image_url)
                    response_info += f"Image {index + 1}: {image_url}\n"
                    try:
                        img_response = requests.get(image_url, timeout=self.timeout)
                        img_response.raise_for_status()
                        gen_image = Image.open(io.BytesIO(img_response.content))
                        tensors.append(self._pil_to_tensor(gen_image))
                    except Exception as download_error:
                        print(f"[HouLai_Nanobanan] download error: {download_error}")

            if not tensors:
                return (self._blank_tensor(), "Failed to process any images", "")

            combined_tensor = torch.cat(tensors, dim=0)
            first_url = image_urls[0] if image_urls else ""
            return (combined_tensor, response_info, first_url)

        except Exception as exc:
            return (self._blank_tensor(), f"Error in image generation: {exc}", "")
