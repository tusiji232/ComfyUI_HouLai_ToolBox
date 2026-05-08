#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import tkinter as tk
from PIL import Image, ImageTk
from tkinter import filedialog, messagebox, ttk

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import comfy_api_upload_router as api_router


DEFAULT_WORKFLOW_NAME = "\u4e00\u53e5\u8bddP\u56fe\uff08\u652f\u63011~10\u56fe\uff093.4.json"
DEFAULT_WORKFLOW = Path.home() / "Downloads" / DEFAULT_WORKFLOW_NAME
DEFAULT_SERVER = "http://127.0.0.1:8000"
DEFAULT_OUT_DIR = Path.home() / "Downloads" / "api_visual_results"
DEFAULT_INPUT_DIR = Path.home() / "Pictures"

EMPTY_SLOT = "[\u7a7a]"
RESIZE_MODE_OPTIONS = ["\u5173\u95ed", "\u6309\u50cf\u7d20\u6570\u91cf(\u767e\u4e07)", "\u6309\u6700\u957f\u8fb9", "\u6309\u6700\u77ed\u8fb9"]
RESAMPLE_OPTIONS = ["lanczos", "bicubic", "bilinear"]
ALIGN_OPTIONS = [1, 2, 4, 8, 16, 32, 64]
EMPTY_OUTPUT_MODE_OPTIONS = ["\u7a7a\u503c", "\u963b\u65ad"]

CLASS_ROUTER = "HouLai_10_Slot_Image_Router"
CLASS_SWITCH = "HouLai_8_Way_Image_Switch"
CLASS_PRIMITIVE_INT = "PrimitiveInt"
CLASS_TEXTBOX = "LayerUtility: TextBox"
EDIT_CLASS_KEYWORD = "nano_banana2_edit"


@dataclass
class WorkflowBindings:
    router_id: Optional[str] = None
    switch_id: Optional[str] = None
    route_value_id: Optional[str] = None
    select_value_id: Optional[str] = None
    apikey_textbox_id: Optional[str] = None
    prompt_textbox_id: Optional[str] = None


def load_workflow_json(path: Path) -> Dict[str, Any]:
    data = api_router.load_json(path)
    if not isinstance(data, dict):
        raise ValueError("Workflow JSON 必须是对象格式。")
    return data


def detect_bindings(prompt: Dict[str, Any]) -> WorkflowBindings:
    b = WorkflowBindings()

    for node_id, node in prompt.items():
        class_type = node.get("class_type")
        if class_type == CLASS_ROUTER and b.router_id is None:
            b.router_id = str(node_id)
        elif class_type == CLASS_SWITCH and b.switch_id is None:
            b.switch_id = str(node_id)

    if b.router_id:
        route_input = prompt[b.router_id].get("inputs", {}).get("route_n")
        if isinstance(route_input, list) and route_input:
            b.route_value_id = str(route_input[0])

    if b.switch_id:
        select_input = prompt[b.switch_id].get("inputs", {}).get("select_source")
        if isinstance(select_input, list) and select_input:
            b.select_value_id = str(select_input[0])

    for node in prompt.values():
        class_type = str(node.get("class_type", ""))
        if EDIT_CLASS_KEYWORD not in class_type.lower():
            continue
        inputs = node.get("inputs", {})
        apikey_ref = inputs.get("apikey")
        prompt_ref = inputs.get("prompt")
        if isinstance(apikey_ref, list) and apikey_ref:
            b.apikey_textbox_id = str(apikey_ref[0])
        if isinstance(prompt_ref, list) and prompt_ref:
            b.prompt_textbox_id = str(prompt_ref[0])

    textboxes = [str(nid) for nid, n in prompt.items() if n.get("class_type") == CLASS_TEXTBOX]
    if b.apikey_textbox_id is None and textboxes:
        for nid in textboxes:
            text_value = str(prompt[nid].get("inputs", {}).get("text", ""))
            if text_value.strip().startswith("sk-"):
                b.apikey_textbox_id = nid
                break
        if b.apikey_textbox_id is None:
            b.apikey_textbox_id = textboxes[0]

    if b.prompt_textbox_id is None and textboxes:
        for nid in textboxes:
            if nid != b.apikey_textbox_id:
                b.prompt_textbox_id = nid
                break
        if b.prompt_textbox_id is None:
            b.prompt_textbox_id = textboxes[0]

    return b


def _extract_int_value(prompt: Dict[str, Any], node_id: Optional[str], key: str, fallback: int) -> int:
    if not node_id or node_id not in prompt:
        return fallback
    inputs = prompt[node_id].get("inputs", {})
    try:
        return int(inputs.get(key, fallback))
    except Exception:
        return fallback


def read_defaults_from_workflow(prompt: Dict[str, Any], b: WorkflowBindings) -> Dict[str, Any]:
    defaults: Dict[str, Any] = {}

    defaults["apikey"] = ""
    defaults["prompt_text"] = ""
    defaults["route_n"] = 1
    defaults["select_source"] = 1
    defaults["resize_mode"] = RESIZE_MODE_OPTIONS[0]
    defaults["resize_value"] = 1
    defaults["resample"] = "lanczos"
    defaults["max_side_limit"] = 1536
    defaults["align_to_multiple"] = 1
    defaults["empty_output_mode"] = "空值"
    defaults["slots"] = [""] * 10

    if b.apikey_textbox_id and b.apikey_textbox_id in prompt:
        defaults["apikey"] = str(prompt[b.apikey_textbox_id].get("inputs", {}).get("text", ""))
    if b.prompt_textbox_id and b.prompt_textbox_id in prompt:
        defaults["prompt_text"] = str(prompt[b.prompt_textbox_id].get("inputs", {}).get("text", ""))

    if b.route_value_id and b.route_value_id in prompt:
        defaults["route_n"] = _extract_int_value(prompt, b.route_value_id, "value", defaults["route_n"])
    elif b.router_id and b.router_id in prompt:
        defaults["route_n"] = _extract_int_value(prompt, b.router_id, "route_n", defaults["route_n"])

    if b.select_value_id and b.select_value_id in prompt:
        defaults["select_source"] = _extract_int_value(prompt, b.select_value_id, "value", defaults["select_source"])

    if b.router_id and b.router_id in prompt:
        inputs = prompt[b.router_id].get("inputs", {})
        defaults["resize_mode"] = api_router.normalize_resize_mode_value(str(inputs.get("resize_mode", defaults["resize_mode"])))
        defaults["resize_value"] = int(inputs.get("resize_value", defaults["resize_value"]))
        defaults["resample"] = str(inputs.get("resample_method", defaults["resample"]))
        defaults["max_side_limit"] = int(inputs.get("max_side_limit", defaults["max_side_limit"]))
        defaults["align_to_multiple"] = int(inputs.get("align_to_multiple", defaults["align_to_multiple"]))
        defaults["empty_output_mode"] = api_router.normalize_empty_output_mode_value(
            str(inputs.get("empty_output_mode", defaults["empty_output_mode"]))
        )

        for i in range(1, 11):
            token = str(inputs.get(f"image_{i}", EMPTY_SLOT))
            if token and token != EMPTY_SLOT:
                p = Path(token)
                if p.exists():
                    defaults["slots"][i - 1] = str(p)
                else:
                    candidate = DEFAULT_INPUT_DIR / token
                    defaults["slots"][i - 1] = str(candidate) if candidate.exists() else token

    return defaults


def apply_values_to_prompt(
    prompt: Dict[str, Any],
    b: WorkflowBindings,
    apikey: str,
    prompt_text: str,
    route_n: int,
    select_source: int,
    resize_mode: str,
    resize_value: int,
    resample_method: str,
    max_side_limit: int,
    align_to_multiple: int,
    empty_output_mode: str,
    slot_map: Dict[int, str],
) -> None:
    route_n = max(0, min(10, int(route_n)))
    select_source = max(1, min(8, int(select_source)))

    if b.apikey_textbox_id and b.apikey_textbox_id in prompt:
        prompt[b.apikey_textbox_id].setdefault("inputs", {})["text"] = apikey
    if b.prompt_textbox_id and b.prompt_textbox_id in prompt:
        prompt[b.prompt_textbox_id].setdefault("inputs", {})["text"] = prompt_text

    if b.route_value_id and b.route_value_id in prompt and prompt[b.route_value_id].get("class_type") == CLASS_PRIMITIVE_INT:
        prompt[b.route_value_id].setdefault("inputs", {})["value"] = route_n

    if b.select_value_id and b.select_value_id in prompt and prompt[b.select_value_id].get("class_type") == CLASS_PRIMITIVE_INT:
        prompt[b.select_value_id].setdefault("inputs", {})["value"] = select_source

    if b.router_id and b.router_id in prompt:
        router_inputs = prompt[b.router_id].setdefault("inputs", {})
        router_inputs["route_n"] = route_n
        router_inputs["resize_mode"] = api_router.normalize_resize_mode_value(resize_mode)
        router_inputs["resize_value"] = int(resize_value)
        router_inputs["resample_method"] = resample_method
        router_inputs["max_side_limit"] = int(max_side_limit)
        router_inputs["align_to_multiple"] = int(align_to_multiple)
        router_inputs["empty_output_mode"] = api_router.normalize_empty_output_mode_value(empty_output_mode)
        for i in range(1, 11):
            router_inputs[f"image_{i}"] = slot_map.get(i, EMPTY_SLOT)


def download_images_with_paths(server_url: str, history_entry: Dict[str, Any], out_dir: Path, prompt_id: str) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: List[Path] = []
    outputs = history_entry.get("outputs", {})
    for node_id, node_output in outputs.items():
        images = node_output.get("images", [])
        for idx, image_info in enumerate(images, start=1):
            params = {
                "filename": image_info.get("filename", ""),
                "subfolder": image_info.get("subfolder", ""),
                "type": image_info.get("type", "output"),
            }
            if not params["filename"]:
                continue
            response = requests.get(f"{server_url}/view", params=params, timeout=30)
            response.raise_for_status()
            file_name = Path(params["filename"]).name
            save_path = out_dir / f"{prompt_id}_{node_id}_{idx}_{file_name}"
            save_path.write_bytes(response.content)
            saved.append(save_path)
    return saved


class VisualUploaderApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("一句话P图 API 可视化上传器")
        self.geometry("1380x900")
        self.minsize(1200, 780)

        self._running = False
        self._buttons: List[ttk.Button] = []
        self._preview_image_ref = None

        self.server_var = tk.StringVar(value=DEFAULT_SERVER)
        self.workflow_var = tk.StringVar(value=str(DEFAULT_WORKFLOW))
        self.output_var = tk.StringVar(value=str(DEFAULT_OUT_DIR))
        self.apikey_var = tk.StringVar(value="")
        self.route_var = tk.IntVar(value=2)
        self.select_var = tk.IntVar(value=2)
        self.resize_mode_var = tk.StringVar(value=RESIZE_MODE_OPTIONS[1])
        self.resize_value_var = tk.IntVar(value=2)
        self.resample_var = tk.StringVar(value="lanczos")
        self.max_side_var = tk.IntVar(value=1536)
        self.align_var = tk.IntVar(value=1)
        self.empty_output_mode_var = tk.StringVar(value="空值")
        self.timeout_var = tk.IntVar(value=300)
        self.prompt_text_widget: Optional[tk.Text] = None
        self.slot_vars = [tk.StringVar(value="") for _ in range(10)]

        self._build_ui()
        self.after(120, self._load_defaults_from_workflow)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=10)
        root.pack(fill=tk.BOTH, expand=True)

        paned = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(paned)
        right = ttk.Frame(paned)
        paned.add(left, weight=4)
        paned.add(right, weight=2)

        base = ttk.LabelFrame(left, text="基础配置", padding=10)
        base.pack(fill=tk.X)
        self._path_row(base, 0, "ComfyUI 地址", self.server_var, self._check_server, "检测")
        self._path_row(base, 1, "工作流 JSON", self.workflow_var, self._browse_workflow, "选择")
        self._path_row(base, 2, "输出目录", self.output_var, self._browse_output, "选择")
        base.grid_columnconfigure(1, weight=1)

        config = ttk.LabelFrame(left, text="工作流参数", padding=10)
        config.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(config, text="API Key").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(config, textvariable=self.apikey_var, show="*", width=80).grid(row=0, column=1, columnspan=5, sticky="ew", pady=4)

        ttk.Label(config, text="一句话 Prompt").grid(row=1, column=0, sticky="nw", padx=(0, 8), pady=4)
        self.prompt_text_widget = tk.Text(config, height=3, wrap=tk.WORD)
        self.prompt_text_widget.grid(row=1, column=1, columnspan=5, sticky="ew", pady=4)

        ttk.Label(config, text="route_n").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Spinbox(config, from_=0, to=10, textvariable=self.route_var, width=8).grid(row=2, column=1, sticky="w", pady=4)

        ttk.Label(config, text="预览来源(1=img2img 2=text2img)").grid(row=2, column=2, sticky="w", padx=(16, 8), pady=4)
        ttk.Spinbox(config, from_=1, to=8, textvariable=self.select_var, width=8).grid(row=2, column=3, sticky="w", pady=4)

        ttk.Label(config, text="缩放模式").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Combobox(config, textvariable=self.resize_mode_var, values=RESIZE_MODE_OPTIONS, state="readonly", width=18).grid(
            row=3, column=1, sticky="w", pady=4
        )
        ttk.Label(config, text="像素数量/边长").grid(row=3, column=2, sticky="w", padx=(16, 8), pady=4)
        ttk.Spinbox(config, from_=1, to=200, textvariable=self.resize_value_var, width=8).grid(row=3, column=3, sticky="w", pady=4)

        ttk.Label(config, text="缩放算法").grid(row=4, column=0, sticky="w", pady=4)
        ttk.Combobox(config, textvariable=self.resample_var, values=RESAMPLE_OPTIONS, state="readonly", width=12).grid(
            row=4, column=1, sticky="w", pady=4
        )
        ttk.Label(config, text="最大边长").grid(row=4, column=2, sticky="w", padx=(16, 8), pady=4)
        ttk.Spinbox(config, from_=64, to=32768, textvariable=self.max_side_var, width=8).grid(row=4, column=3, sticky="w", pady=4)
        ttk.Label(config, text="对齐倍数").grid(row=4, column=4, sticky="w", padx=(16, 8), pady=4)
        ttk.Combobox(config, textvariable=self.align_var, values=ALIGN_OPTIONS, state="readonly", width=8).grid(row=4, column=5, sticky="w", pady=4)

        ttk.Label(config, text="空槽输出策略").grid(row=5, column=0, sticky="w", pady=4)
        ttk.Combobox(
            config,
            textvariable=self.empty_output_mode_var,
            values=EMPTY_OUTPUT_MODE_OPTIONS,
            state="readonly",
            width=10,
        ).grid(row=5, column=1, sticky="w", pady=4)

        ttk.Label(config, text="超时秒数").grid(row=5, column=2, sticky="w", padx=(16, 8), pady=4)
        ttk.Spinbox(config, from_=30, to=1800, textvariable=self.timeout_var, width=8).grid(row=5, column=3, sticky="w", pady=4)
        config.grid_columnconfigure(1, weight=1)
        config.grid_columnconfigure(5, weight=1)

        slots = ttk.LabelFrame(left, text="10 路图像上传（支持本地文件 / data-uri / b64:...）", padding=10)
        slots.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        for i in range(10):
            row = i
            ttk.Label(slots, text=f"image_{i + 1}").grid(row=row, column=0, sticky="w", pady=3)
            ttk.Entry(slots, textvariable=self.slot_vars[i], width=90).grid(row=row, column=1, sticky="ew", padx=(8, 8), pady=3)
            ttk.Button(slots, text="选择", width=7, command=lambda idx=i: self._choose_slot(idx)).grid(row=row, column=2, sticky="w", pady=3)
            ttk.Button(slots, text="清空", width=7, command=lambda idx=i: self.slot_vars[idx].set("")).grid(row=row, column=3, sticky="w", padx=(6, 0), pady=3)
        slots.grid_columnconfigure(1, weight=1)

        actions = ttk.Frame(left)
        actions.pack(fill=tk.X, pady=(10, 0))
        btn_sync = ttk.Button(actions, text="读取工作流默认值", command=self._load_defaults_from_workflow)
        btn_dry = ttk.Button(actions, text="仅生成 Payload", command=lambda: self._start_job(True))
        btn_submit = ttk.Button(actions, text="提交并接收结果", command=lambda: self._start_job(False))
        btn_open = ttk.Button(actions, text="打开输出目录", command=self._open_output_dir)
        btn_clear = ttk.Button(actions, text="清空全部图片", command=self._clear_slots)
        btn_sync.pack(side=tk.LEFT, padx=(0, 8))
        btn_dry.pack(side=tk.LEFT, padx=(0, 8))
        btn_submit.pack(side=tk.LEFT, padx=(0, 8))
        btn_open.pack(side=tk.LEFT, padx=(0, 8))
        btn_clear.pack(side=tk.LEFT)
        self._buttons.extend([btn_sync, btn_dry, btn_submit, btn_clear])

        result = ttk.LabelFrame(right, text="结果预览", padding=10)
        result.pack(fill=tk.BOTH, expand=True)
        self.preview_label = ttk.Label(result, text="\u6682\u65e0\u56fe\u50cf", anchor="center")
        self.preview_label.pack(fill=tk.BOTH, expand=True)
        self.result_info = tk.StringVar(value="\u672a\u8fd0\u884c")
        ttk.Label(result, textvariable=self.result_info, justify=tk.LEFT).pack(fill=tk.X, pady=(8, 0))

        logs = ttk.LabelFrame(right, text="运行日志", padding=10)
        logs.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self.log_text = tk.Text(logs, height=14, wrap=tk.WORD)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(logs, orient=tk.VERTICAL, command=self.log_text.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=scroll.set, state=tk.DISABLED)

        self._log("\u7a0b\u5e8f\u5df2\u5c31\u7eea\uff0c\u53ef\u76f4\u63a5\u63d0\u4ea4\u6d4b\u8bd5\u3002")

    def _path_row(self, parent: ttk.LabelFrame, row: int, label: str, variable: tk.StringVar, cmd, btn_text: str) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Button(parent, text=btn_text, width=8, command=cmd).grid(row=row, column=2, sticky="w", padx=(8, 0), pady=4)

    def _choose_slot(self, idx: int) -> None:
        path = filedialog.askopenfilename(
            title=f"\u9009\u62e9 image_{idx + 1}",
            filetypes=[
                ("Image files", "*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.gif;*.tif;*.tiff;*.avif"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.slot_vars[idx].set(path)

    def _browse_workflow(self) -> None:
        path = filedialog.askopenfilename(title="\u9009\u62e9\u5de5\u4f5c\u6d41 JSON", filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if path:
            self.workflow_var.set(path)
            self._load_defaults_from_workflow()

    def _browse_output(self) -> None:
        path = filedialog.askdirectory(title="\u9009\u62e9\u8f93\u51fa\u76ee\u5f55")
        if path:
            self.output_var.set(path)

    def _open_output_dir(self) -> None:
        out_dir = Path(self.output_var.get().strip())
        out_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(str(out_dir))

    def _clear_slots(self) -> None:
        for var in self.slot_vars:
            var.set("")
        self._log("\u5df2\u6e05\u7a7a image_1~image_10")

    def _set_running(self, running: bool) -> None:
        self._running = running
        state = tk.DISABLED if running else tk.NORMAL
        for btn in self._buttons:
            btn.configure(state=state)

    def _append_log(self, text: str) -> None:
        t = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{t}] {text}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _log(self, text: str) -> None:
        self.after(0, lambda: self._append_log(text))

    def _check_server(self) -> None:
        server = api_router.normalize_server_url(self.server_var.get().strip())
        try:
            api_router.ensure_server_reachable(server)
        except Exception as exc:
            self._log(f"\u8fde\u63a5\u5931\u8d25: {exc}")
            messagebox.showerror("\u8fde\u63a5\u5931\u8d25", str(exc))
            return
        self._log(f"\u8fde\u63a5\u6210\u529f: {server}")
        messagebox.showinfo("\u8fde\u63a5\u6210\u529f", server)

    def _load_defaults_from_workflow(self) -> None:
        try:
            path = Path(self.workflow_var.get().strip())
            data = load_workflow_json(path)
            if not api_router.is_api_prompt_format(data):
                self._log("\u68c0\u6d4b\u5230 UI \u5de5\u4f5c\u6d41\uff0c\u754c\u9762\u9ed8\u8ba4\u503c\u4ec5\u8f7d\u5165\u4e00\u90e8\u5206\u3002")
                object_info = api_router.fetch_object_info(api_router.normalize_server_url(self.server_var.get().strip()))
                data = api_router.convert_ui_workflow_to_prompt(data, object_info)

            b = detect_bindings(data)
            defaults = read_defaults_from_workflow(data, b)

            self.apikey_var.set(defaults["apikey"])
            if self.prompt_text_widget is not None:
                self.prompt_text_widget.delete("1.0", tk.END)
                self.prompt_text_widget.insert("1.0", defaults["prompt_text"])
            self.route_var.set(int(defaults["route_n"]))
            self.select_var.set(int(defaults["select_source"]))
            self.resize_mode_var.set(str(defaults["resize_mode"]))
            self.resize_value_var.set(int(defaults["resize_value"]))
            self.resample_var.set(str(defaults["resample"]))
            self.max_side_var.set(int(defaults["max_side_limit"]))
            self.align_var.set(int(defaults["align_to_multiple"]))
            self.empty_output_mode_var.set(str(defaults["empty_output_mode"]))
            for i, value in enumerate(defaults["slots"]):
                self.slot_vars[i].set(value)

            self._log(
                "\u5de5\u4f5c\u6d41\u9ed8\u8ba4\u503c\u5df2\u52a0\u8f7d "
                f"(router={b.router_id}, apikey_box={b.apikey_textbox_id}, prompt_box={b.prompt_textbox_id})"
            )
        except Exception as exc:
            self._log(f"\u8bfb\u53d6\u5de5\u4f5c\u6d41\u5931\u8d25: {exc}")

    def _collect_slot_map(self) -> Dict[int, str]:
        slot_map: Dict[int, str] = {}
        for i, var in enumerate(self.slot_vars, start=1):
            raw = var.get().strip()
            if not raw:
                continue
            slot_map[i] = api_router.parse_slot_value(raw)
        return slot_map

    def _start_job(self, dry_run: bool) -> None:
        if self._running:
            return
        workflow_path = Path(self.workflow_var.get().strip())
        if not workflow_path.exists():
            messagebox.showerror("\u53c2\u6570\u9519\u8bef", f"\u5de5\u4f5c\u6d41\u6587\u4ef6\u4e0d\u5b58\u5728:\n{workflow_path}")
            return
        try:
            slot_map = self._collect_slot_map()
        except Exception as exc:
            messagebox.showerror("\u53c2\u6570\u9519\u8bef", str(exc))
            return

        prompt_text = ""
        if self.prompt_text_widget is not None:
            prompt_text = self.prompt_text_widget.get("1.0", tk.END).strip()

        payload = {
            "dry_run": dry_run,
            "workflow_path": workflow_path,
            "server": self.server_var.get().strip(),
            "out_dir": Path(self.output_var.get().strip()),
            "apikey": self.apikey_var.get().strip(),
            "prompt_text": prompt_text,
            "route_n": int(self.route_var.get()),
            "select_source": int(self.select_var.get()),
            "resize_mode": self.resize_mode_var.get().strip(),
            "resize_value": int(self.resize_value_var.get()),
            "resample_method": self.resample_var.get().strip(),
            "max_side_limit": int(self.max_side_var.get()),
            "align_to_multiple": int(self.align_var.get()),
            "empty_output_mode": self.empty_output_mode_var.get().strip(),
            "timeout": int(self.timeout_var.get()),
            "slot_map": slot_map,
        }

        self._set_running(True)
        self._log(f"\u5f00\u59cb\u4efb\u52a1: dry_run={dry_run}, \u56fe\u50cf\u69fd\u4f4d={len(slot_map)}")
        worker = threading.Thread(target=self._run_job, args=(payload,), daemon=True)
        worker.start()

    def _set_preview(self, image_path: Optional[Path], text: str) -> None:
        if image_path is None or not image_path.exists():
            self.preview_label.configure(image="", text="\u6682\u65e0\u56fe\u50cf")
            self._preview_image_ref = None
            self.result_info.set(text)
            return

        with Image.open(image_path) as im:
            preview = im.convert("RGB")
            preview.thumbnail((520, 520))
        photo = ImageTk.PhotoImage(preview)
        self.preview_label.configure(image=photo, text="")
        self._preview_image_ref = photo
        self.result_info.set(text)

    def _run_job(self, payload: Dict[str, Any]) -> None:
        try:
            server = api_router.normalize_server_url(payload["server"])
            out_dir: Path = payload["out_dir"]
            out_dir.mkdir(parents=True, exist_ok=True)

            data = load_workflow_json(payload["workflow_path"])
            if api_router.is_api_prompt_format(data):
                prompt = data
            else:
                object_info = api_router.fetch_object_info(server)
                prompt = api_router.convert_ui_workflow_to_prompt(data, object_info)

            b = detect_bindings(prompt)
            if b.router_id is None:
                raise ValueError(f"\u5de5\u4f5c\u6d41\u4e2d\u672a\u627e\u5230 {CLASS_ROUTER} \u8282\u70b9")

            apply_values_to_prompt(
                prompt=prompt,
                b=b,
                apikey=payload["apikey"],
                prompt_text=payload["prompt_text"],
                route_n=payload["route_n"],
                select_source=payload["select_source"],
                resize_mode=payload["resize_mode"],
                resize_value=payload["resize_value"],
                resample_method=payload["resample_method"],
                max_side_limit=payload["max_side_limit"],
                align_to_multiple=payload["align_to_multiple"],
                empty_output_mode=payload["empty_output_mode"],
                slot_map=payload["slot_map"],
            )

            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            payload_file = out_dir / f"payload_{stamp}.json"
            payload_file.write_text(json.dumps(prompt, ensure_ascii=False, indent=2), encoding="utf-8")
            self._log(f"Payload \u5df2\u751f\u6210: {payload_file}")

            if payload["dry_run"]:
                self.after(0, lambda: self._set_preview(None, f"dry-run \u5b8c\u6210\n{payload_file}"))
                self._log("dry-run \u7ed3\u675f")
                return

            api_router.ensure_server_reachable(server)
            prompt_id = api_router.submit_prompt(server, prompt)
            self._log(f"\u5df2\u63d0\u4ea4 prompt_id: {prompt_id}")

            history_entry = api_router.wait_for_history(
                server_url=server,
                prompt_id=prompt_id,
                timeout_seconds=payload["timeout"],
                poll_interval=1.0,
            )
            history_file = out_dir / f"history_{prompt_id}.json"
            history_file.write_text(json.dumps(history_entry, ensure_ascii=False, indent=2), encoding="utf-8")
            self._log(f"History \u5df2\u4fdd\u5b58: {history_file}")

            images = download_images_with_paths(server, history_entry, out_dir, prompt_id)
            self._log(f"\u4e0b\u8f7d\u56fe\u50cf {len(images)} \u5f20")
            preview_path = images[0] if images else None
            info = f"prompt_id: {prompt_id}\n\u4e0b\u8f7d: {len(images)}\n\u76ee\u5f55: {out_dir}"
            self.after(0, lambda: self._set_preview(preview_path, info))
            self.after(0, lambda: messagebox.showinfo("\u5b8c\u6210", info))
        except Exception as exc:
            self._log(f"\u4efb\u52a1\u5931\u8d25: {exc}")
            self.after(0, lambda: messagebox.showerror("\u4efb\u52a1\u5931\u8d25", str(exc)))
        finally:
            self.after(0, lambda: self._set_running(False))


def main() -> int:
    app = VisualUploaderApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
