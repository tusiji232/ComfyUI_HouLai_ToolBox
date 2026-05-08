import base64
import binascii
import io
import math
from pathlib import Path
from typing import Any, List, Optional, Tuple

import comfy.utils
import folder_paths
import numpy as np
import torch
from PIL import Image, ImageOps


class HouLai_10_Slot_Image_Router:
    """10-slot image uploader/router with optional resizing and route gating."""

    SLOT_COUNT = 10
    EMPTY_OPTION = "[空]"
    RESAMPLE_METHODS = ["lanczos", "bicubic", "bilinear"]
    ALIGN_CHOICES = [1, 2, 4, 8, 16, 32, 64]
    EMPTY_OUTPUT_MODES = ["空值", "阻断"]

    @classmethod
    def _list_input_files(cls) -> List[str]:
        input_dir = Path(folder_paths.get_input_directory())
        if not input_dir.exists():
            return [cls.EMPTY_OPTION]

        allowed_ext = {
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".bmp",
            ".gif",
            ".tif",
            ".tiff",
            ".avif",
        }

        files: List[str] = []
        for file_path in input_dir.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in allowed_ext:
                continue
            files.append(file_path.relative_to(input_dir).as_posix())

        files.sort()
        return [cls.EMPTY_OPTION] + files

    @classmethod
    def INPUT_TYPES(cls):
        required = {
            "route_n": ("INT", {"default": 1, "min": 0, "max": 10, "step": 1}),
            "resize_mode": (
                ["关闭", "按像素数量(百万)", "按最长边", "按最短边"],
                {"default": "关闭"},
            ),
            "resize_value": ("INT", {"default": 1, "min": 1, "max": 200, "step": 1}),
            "resample_method": (cls.RESAMPLE_METHODS, {"default": "lanczos"}),
            "max_side_limit": ("INT", {"default": 8192, "min": 64, "max": 32768, "step": 1}),
            "align_to_multiple": (cls.ALIGN_CHOICES, {"default": 1}),
            "empty_output_mode": (cls.EMPTY_OUTPUT_MODES, {"default": "空值"}),
        }

        for i in range(1, cls.SLOT_COUNT + 1):
            required[f"image_{i}"] = (
                "STRING",
                {
                    "default": cls.EMPTY_OPTION,
                    "multiline": False,
                    "image_upload": True,
                },
            )

        return {"required": required}

    RETURN_TYPES = ("IMAGE",) * 10
    RETURN_NAMES = tuple(f"image_{i}" for i in range(1, 11))
    FUNCTION = "process"
    CATEGORY = "HouLai_ToolBox/Logic"

    @staticmethod
    def _canonical_empty_output_mode(empty_output_mode: str) -> str:
        mode = str(empty_output_mode or "").strip()
        aliases = {
            "none": "none",
            "空值": "none",
            "blocker": "blocker",
            "阻断": "blocker",
        }
        return aliases.get(mode, "none")

    @classmethod
    def _blocked_output(cls, empty_output_mode: str):
        mode = cls._canonical_empty_output_mode(empty_output_mode)
        if mode == "none":
            return None

        try:
            from comfy_execution.graph import ExecutionBlocker

            return ExecutionBlocker(None)
        except Exception:
            return None

    @classmethod
    def _pil_to_tensor(cls, image: Image.Image) -> Optional[torch.Tensor]:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image_np = np.asarray(image).astype(np.float32) / 255.0
        if image_np.ndim != 3 or image_np.shape[-1] != 3:
            return None
        return torch.from_numpy(image_np)[None,]

    @classmethod
    def _load_image_from_bytes(cls, image_bytes: bytes) -> Optional[torch.Tensor]:
        try:
            with Image.open(io.BytesIO(image_bytes)) as image:
                return cls._pil_to_tensor(image)
        except Exception:
            return None

    @classmethod
    def _load_image_from_path_token(cls, file_token: str) -> Optional[torch.Tensor]:
        try:
            if hasattr(folder_paths, "exists_annotated_filepath"):
                if not folder_paths.exists_annotated_filepath(file_token):
                    return None
            image_path = folder_paths.get_annotated_filepath(file_token)
            if not image_path:
                return None
            if not Path(image_path).exists():
                return None
            with Image.open(image_path) as image:
                return cls._pil_to_tensor(image)
        except Exception:
            return None

    @staticmethod
    def _decode_base64_bytes(raw: str) -> Optional[bytes]:
        if not isinstance(raw, str):
            return None
        text = raw.strip()
        if not text:
            return None

        payload = text
        lower_text = text.lower()

        if lower_text.startswith("data:image/"):
            if "," not in text:
                return None
            _, payload = text.split(",", 1)
        elif lower_text.startswith("base64:"):
            payload = text.split(":", 1)[1]

        payload = payload.strip().replace("\n", "").replace("\r", "")
        if not payload:
            return None

        missing_padding = len(payload) % 4
        if missing_padding:
            payload = payload + ("=" * (4 - missing_padding))

        try:
            return base64.b64decode(payload, validate=False)
        except (binascii.Error, ValueError):
            try:
                return base64.urlsafe_b64decode(payload)
            except Exception:
                return None

    @classmethod
    def _load_image_tensor(cls, file_token: Any) -> Optional[torch.Tensor]:
        # Empty value handling
        if file_token is None:
            return None

        if isinstance(file_token, str):
            stripped = file_token.strip()
            if not stripped or stripped in {cls.EMPTY_OPTION, "[空]"}:
                return None

        # Direct bytes / bytearray / memoryview
        if isinstance(file_token, (bytes, bytearray, memoryview)):
            return cls._load_image_from_bytes(bytes(file_token))

        # Direct list of byte values (0-255)
        if (
            isinstance(file_token, list)
            and file_token
            and all(isinstance(v, int) and 0 <= v <= 255 for v in file_token)
        ):
            return cls._load_image_from_bytes(bytes(file_token))

        # Dict wrapper support, e.g. {"base64": "..."} or {"bytes": [...]}
        if isinstance(file_token, dict):
            for key in ("base64", "b64", "data", "image", "bytes"):
                if key in file_token:
                    return cls._load_image_tensor(file_token.get(key))
            return None

        # String support:
        # 1) annotated filepath under ComfyUI input
        # 2) data-uri base64 / plain base64 payload
        if isinstance(file_token, str):
            image_from_path = cls._load_image_from_path_token(file_token)
            if image_from_path is not None:
                return image_from_path

            base64_bytes = cls._decode_base64_bytes(file_token)
            if base64_bytes is not None:
                image_from_b64 = cls._load_image_from_bytes(base64_bytes)
                if image_from_b64 is not None:
                    return image_from_b64

        return None

    @staticmethod
    def _canonical_resize_mode(resize_mode: str) -> str:
        mode = str(resize_mode or "").strip()
        aliases = {
            "off": "off",
            "关闭": "off",
            "megapixel_10m": "pixel_1m",
            "megapixel_1m": "pixel_1m",
            "pixel_count_1m": "pixel_1m",
            "按像素数量(百万)": "pixel_1m",
            "按像素数量": "pixel_1m",
            "像素数量": "pixel_1m",
            "longest_side": "longest_side",
            "按最长边": "longest_side",
            "shortest_side": "shortest_side",
            "按最短边": "shortest_side",
        }
        return aliases.get(mode, "off")

    @staticmethod
    def _align_down(value: int, multiple: int) -> int:
        if multiple <= 1:
            return max(1, int(value))
        value = max(1, int(value))
        if value < multiple:
            return value
        return max(1, (value // multiple) * multiple)

    @classmethod
    def _compute_target_size(
        cls,
        width: int,
        height: int,
        resize_mode: str,
        resize_value: int,
        max_side_limit: int,
        align_to_multiple: int,
    ) -> Tuple[int, int]:
        mode = cls._canonical_resize_mode(resize_mode)
        width = max(1, int(width))
        height = max(1, int(height))
        target_width = width
        target_height = height

        if mode == "pixel_1m":
            # 1 means 1,000,000 pixels
            target_pixels = max(1, int(resize_value)) * 1_000_000
            scale = math.sqrt(target_pixels / float(width * height))
            target_width = max(1, int(round(width * scale)))
            target_height = max(1, int(round(height * scale)))
        elif mode == "longest_side":
            longest = max(width, height)
            scale = max(1, int(resize_value)) / float(longest)
            target_width = max(1, int(round(width * scale)))
            target_height = max(1, int(round(height * scale)))
        elif mode == "shortest_side":
            shortest = min(width, height)
            scale = max(1, int(resize_value)) / float(shortest)
            target_width = max(1, int(round(width * scale)))
            target_height = max(1, int(round(height * scale)))

        limit = max(64, int(max_side_limit))
        current_max = max(target_width, target_height)
        if current_max > limit:
            scale = limit / float(current_max)
            target_width = max(1, int(round(target_width * scale)))
            target_height = max(1, int(round(target_height * scale)))

        align = max(1, int(align_to_multiple))
        target_width = cls._align_down(target_width, align)
        target_height = cls._align_down(target_height, align)

        return max(1, target_width), max(1, target_height)

    @classmethod
    def _resize_tensor_if_needed(
        cls,
        image_tensor: torch.Tensor,
        resize_mode: str,
        resize_value: int,
        max_side_limit: int,
        align_to_multiple: int,
        resample_method: str,
    ) -> torch.Tensor:
        _, height, width, _ = image_tensor.shape
        target_width, target_height = cls._compute_target_size(
            width=width,
            height=height,
            resize_mode=resize_mode,
            resize_value=resize_value,
            max_side_limit=max_side_limit,
            align_to_multiple=align_to_multiple,
        )

        if target_width == width and target_height == height:
            return image_tensor

        method = resample_method if resample_method in cls.RESAMPLE_METHODS else "lanczos"
        return comfy.utils.common_upscale(
            image_tensor.movedim(-1, 1),
            target_width,
            target_height,
            method,
            crop="disabled",
        ).movedim(1, -1)

    def process(
        self,
        route_n,
        resize_mode,
        resize_value,
        resample_method,
        max_side_limit,
        align_to_multiple,
        image_1,
        image_2,
        image_3,
        image_4,
        image_5,
        image_6,
        image_7,
        image_8,
        image_9,
        image_10,
        empty_output_mode="空值",
    ):
        route_n = max(0, min(10, int(route_n)))
        image_tokens = [
            image_1,
            image_2,
            image_3,
            image_4,
            image_5,
            image_6,
            image_7,
            image_8,
            image_9,
            image_10,
        ]

        outputs = []
        for idx, file_token in enumerate(image_tokens, start=1):
            if idx > route_n:
                outputs.append(self._blocked_output(empty_output_mode))
                continue

            image_tensor = self._load_image_tensor(file_token)
            if image_tensor is None:
                outputs.append(self._blocked_output(empty_output_mode))
                continue

            image_tensor = self._resize_tensor_if_needed(
                image_tensor=image_tensor,
                resize_mode=resize_mode,
                resize_value=resize_value,
                max_side_limit=max_side_limit,
                align_to_multiple=align_to_multiple,
                resample_method=resample_method,
            )
            outputs.append(image_tensor)

        return tuple(outputs)
