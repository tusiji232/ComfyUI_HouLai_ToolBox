#!/usr/bin/env python3
from __future__ import annotations

import json
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import comfy_api_upload_router as api_router


DEFAULT_WORKFLOW = Path.home() / "Downloads" / "example_api_workflow.json"
DEFAULT_SERVER = "http://127.0.0.1:8000"
DEFAULT_OUTPUT_DIR = Path.home() / "Downloads" / "api_upload_gui_out"

RESIZE_MODE_OPTIONS = ["关闭", "按像素数量(百万)", "按最长边", "按最短边"]
RESAMPLE_METHOD_OPTIONS = ["lanczos", "bicubic", "bilinear"]
ALIGN_OPTIONS = [1, 2, 4, 8, 16, 32, 64]


class ComfyApiUploadGui(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("ComfyUI API 上传测试器（10路图像）")
        self.geometry("1060x860")
        self.minsize(980, 760)

        self._running = False
        self._action_buttons: list[ttk.Button] = []

        self.server_var = tk.StringVar(value=DEFAULT_SERVER)
        self.workflow_var = tk.StringVar(value=str(DEFAULT_WORKFLOW))
        self.output_var = tk.StringVar(value=str(DEFAULT_OUTPUT_DIR))
        self.route_n_var = tk.IntVar(value=2)
        self.resize_mode_var = tk.StringVar(value="按像素数量(百万)")
        self.resize_value_var = tk.IntVar(value=1)
        self.resample_var = tk.StringVar(value="lanczos")
        self.max_side_var = tk.IntVar(value=1536)
        self.align_var = tk.IntVar(value=1)
        self.timeout_var = tk.IntVar(value=300)

        self.slot_vars = [tk.StringVar(value="") for _ in range(10)]
        self._prefill_demo_slots()
        self._build_ui()

    def _prefill_demo_slots(self) -> None:
        demo_1 = Path.home() / "Pictures" / "example_1.jpg"
        demo_2 = Path.home() / "Pictures" / "example_2.jpg"
        if demo_1.exists():
            self.slot_vars[0].set(str(demo_1))
        if demo_2.exists():
            self.slot_vars[1].set(str(demo_2))

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill=tk.BOTH, expand=True)

        top = ttk.LabelFrame(root, text="基础设置", padding=10)
        top.pack(fill=tk.X)

        self._add_path_row(
            parent=top,
            row=0,
            label="ComfyUI 地址",
            variable=self.server_var,
            browse_cmd=None,
            browse_text="检测连接",
            browse_action=self._check_server,
        )
        self._add_path_row(
            parent=top,
            row=1,
            label="工作流 JSON",
            variable=self.workflow_var,
            browse_cmd=self._browse_workflow,
            browse_text="选择文件",
            browse_action=None,
        )
        self._add_path_row(
            parent=top,
            row=2,
            label="输出目录",
            variable=self.output_var,
            browse_cmd=self._browse_output_dir,
            browse_text="选择目录",
            browse_action=None,
        )

        for i in range(3):
            top.grid_columnconfigure(i, weight=1 if i == 1 else 0)

        options = ttk.LabelFrame(root, text="路由与缩放参数", padding=10)
        options.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(options, text="路由数量 route_n").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Spinbox(options, from_=0, to=10, textvariable=self.route_n_var, width=10).grid(
            row=0, column=1, sticky="w", pady=4
        )

        ttk.Label(options, text="缩放模式").grid(row=0, column=2, sticky="w", padx=(16, 8), pady=4)
        ttk.Combobox(
            options,
            textvariable=self.resize_mode_var,
            values=RESIZE_MODE_OPTIONS,
            state="readonly",
            width=20,
        ).grid(row=0, column=3, sticky="w", pady=4)

        ttk.Label(options, text="像素数量/边长值").grid(row=0, column=4, sticky="w", padx=(16, 8), pady=4)
        ttk.Spinbox(options, from_=1, to=200, textvariable=self.resize_value_var, width=10).grid(
            row=0, column=5, sticky="w", pady=4
        )

        ttk.Label(options, text="缩放算法").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Combobox(
            options,
            textvariable=self.resample_var,
            values=RESAMPLE_METHOD_OPTIONS,
            state="readonly",
            width=10,
        ).grid(row=1, column=1, sticky="w", pady=4)

        ttk.Label(options, text="最大边长限制").grid(row=1, column=2, sticky="w", padx=(16, 8), pady=4)
        ttk.Spinbox(options, from_=64, to=32768, textvariable=self.max_side_var, width=10).grid(
            row=1, column=3, sticky="w", pady=4
        )

        ttk.Label(options, text="尺寸对齐倍数").grid(row=1, column=4, sticky="w", padx=(16, 8), pady=4)
        ttk.Combobox(
            options,
            textvariable=self.align_var,
            values=ALIGN_OPTIONS,
            state="readonly",
            width=10,
        ).grid(row=1, column=5, sticky="w", pady=4)

        ttk.Label(options, text="超时秒数").grid(row=1, column=6, sticky="w", padx=(16, 8), pady=4)
        ttk.Spinbox(options, from_=10, to=1800, textvariable=self.timeout_var, width=10).grid(
            row=1, column=7, sticky="w", pady=4
        )

        slots_group = ttk.LabelFrame(root, text="10 路图像输入（可本地路径 / data-uri / b64:...）", padding=10)
        slots_group.pack(fill=tk.X, pady=(10, 0))
        for row in range(10):
            slot_no = row + 1
            ttk.Label(slots_group, text=f"image_{slot_no}").grid(row=row, column=0, sticky="w", pady=3)
            entry = ttk.Entry(slots_group, textvariable=self.slot_vars[row], width=95)
            entry.grid(row=row, column=1, sticky="ew", padx=(8, 8), pady=3)
            ttk.Button(
                slots_group,
                text="选择",
                command=lambda i=row: self._browse_slot(i),
                width=8,
            ).grid(row=row, column=2, sticky="w", pady=3)
        slots_group.grid_columnconfigure(1, weight=1)

        action = ttk.Frame(root)
        action.pack(fill=tk.X, pady=(10, 0))
        btn_submit = ttk.Button(action, text="提交到 ComfyUI", command=lambda: self._start_job(False))
        btn_dry = ttk.Button(action, text="仅生成 Payload", command=lambda: self._start_job(True))
        btn_clear = ttk.Button(action, text="清空 10 槽", command=self._clear_slots)
        btn_open = ttk.Button(action, text="打开输出目录", command=self._open_output_dir)
        btn_submit.pack(side=tk.LEFT, padx=(0, 8))
        btn_dry.pack(side=tk.LEFT, padx=(0, 8))
        btn_clear.pack(side=tk.LEFT, padx=(0, 8))
        btn_open.pack(side=tk.LEFT)
        self._action_buttons.extend([btn_submit, btn_dry, btn_clear])

        log_group = ttk.LabelFrame(root, text="运行日志", padding=10)
        log_group.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self.log_text = tk.Text(log_group, height=16, wrap=tk.WORD)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(log_group, orient=tk.VERTICAL, command=self.log_text.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.configure(state=tk.DISABLED)

        self._log("程序已就绪。可直接点“提交到 ComfyUI”测试。")

    def _add_path_row(
        self,
        parent: ttk.LabelFrame,
        row: int,
        label: str,
        variable: tk.StringVar,
        browse_cmd,
        browse_text: str,
        browse_action,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=4)
        if browse_cmd is not None:
            ttk.Button(parent, text=browse_text, command=browse_cmd, width=10).grid(
                row=row, column=2, sticky="w", padx=(8, 0), pady=4
            )
        elif browse_action is not None:
            ttk.Button(parent, text=browse_text, command=browse_action, width=10).grid(
                row=row, column=2, sticky="w", padx=(8, 0), pady=4
            )

    def _browse_workflow(self) -> None:
        path = filedialog.askopenfilename(
            title="选择工作流 JSON",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
        )
        if path:
            self.workflow_var.set(path)

    def _browse_output_dir(self) -> None:
        path = filedialog.askdirectory(title="选择输出目录")
        if path:
            self.output_var.set(path)

    def _browse_slot(self, idx: int) -> None:
        path = filedialog.askopenfilename(
            title=f"选择 image_{idx + 1}",
            filetypes=[
                ("Image files", "*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.gif;*.tif;*.tiff;*.avif"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.slot_vars[idx].set(path)

    def _clear_slots(self) -> None:
        for var in self.slot_vars:
            var.set("")
        self._log("已清空 image_1~image_10。")

    def _open_output_dir(self) -> None:
        out_dir = Path(self.output_var.get().strip())
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            import os

            os.startfile(str(out_dir))
        except Exception as exc:
            messagebox.showerror("打开目录失败", str(exc))

    def _check_server(self) -> None:
        server_url = self.server_var.get().strip()
        try:
            api_router.ensure_server_reachable(api_router.normalize_server_url(server_url))
        except Exception as exc:
            messagebox.showerror("连接失败", str(exc))
            self._log(f"连接失败: {exc}")
            return
        messagebox.showinfo("连接成功", f"ComfyUI 可访问: {server_url}")
        self._log(f"连接成功: {server_url}")

    def _set_running(self, running: bool) -> None:
        self._running = running
        state = tk.DISABLED if running else tk.NORMAL
        for button in self._action_buttons:
            button.configure(state=state)

    def _collect_slots(self) -> dict[str, str]:
        slot_map: dict[str, str] = {}
        for i, var in enumerate(self.slot_vars, start=1):
            value = var.get().strip()
            if not value:
                continue
            slot_map[f"image_{i}"] = api_router.parse_slot_value(value)
        return slot_map

    def _start_job(self, dry_run: bool) -> None:
        if self._running:
            return

        workflow_path = Path(self.workflow_var.get().strip())
        if not workflow_path.exists():
            messagebox.showerror("参数错误", f"工作流文件不存在:\n{workflow_path}")
            return

        try:
            slot_map = self._collect_slots()
        except Exception as exc:
            messagebox.showerror("参数错误", str(exc))
            return

        if not slot_map:
            if not messagebox.askyesno("确认", "未设置任何槽位图像，仍要继续吗？"):
                return

        params = {
            "dry_run": dry_run,
            "server": self.server_var.get().strip(),
            "workflow_path": workflow_path,
            "output_dir": Path(self.output_var.get().strip()),
            "slot_map": slot_map,
            "route_n": int(self.route_n_var.get()),
            "resize_mode": self.resize_mode_var.get().strip(),
            "resize_value": int(self.resize_value_var.get()),
            "resample_method": self.resample_var.get().strip(),
            "max_side_limit": int(self.max_side_var.get()),
            "align_to_multiple": int(self.align_var.get()),
            "timeout": int(self.timeout_var.get()),
        }

        self._set_running(True)
        self._log(f"开始任务，dry_run={dry_run}，槽位数={len(slot_map)}。")
        worker = threading.Thread(target=self._run_job_worker, args=(params,), daemon=True)
        worker.start()

    def _run_job_worker(self, params: dict) -> None:
        try:
            server_url = api_router.normalize_server_url(params["server"])
            output_dir: Path = params["output_dir"]
            output_dir.mkdir(parents=True, exist_ok=True)

            if not params["dry_run"]:
                api_router.ensure_server_reachable(server_url)
                self._log(f"ComfyUI 已连接: {server_url}")

            raw = api_router.load_json(params["workflow_path"])
            object_info = None if params["dry_run"] else api_router.fetch_object_info(server_url)

            if api_router.is_api_prompt_format(raw):
                prompt = raw
            else:
                prompt = api_router.convert_ui_workflow_to_prompt(raw, object_info)

            router_node_id = api_router.find_router_node_id(prompt, preferred_id=None)
            self._log(f"路由节点 ID: {router_node_id}")

            api_router.apply_router_overrides(
                prompt=prompt,
                router_node_id=router_node_id,
                slot_map=params["slot_map"],
                route_n=params["route_n"],
                resize_mode=params["resize_mode"],
                resize_value=params["resize_value"],
                resample_method=params["resample_method"],
                max_side_limit=params["max_side_limit"],
                align_to_multiple=params["align_to_multiple"],
                empty_output_mode="空值",
                keep_existing_images=False,
            )

            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            payload_file = output_dir / f"payload_prompt_{stamp}.json"
            payload_file.write_text(json.dumps(prompt, ensure_ascii=False, indent=2), encoding="utf-8")
            self._log(f"已生成 Payload: {payload_file}")

            if params["dry_run"]:
                self._log("dry-run 结束。")
                self._run_on_ui_thread(lambda: messagebox.showinfo("完成", "Payload 已生成。"))
                return

            prompt_id = api_router.submit_prompt(server_url, prompt)
            self._log(f"已提交 Prompt: {prompt_id}")

            history_entry = api_router.wait_for_history(
                server_url=server_url,
                prompt_id=prompt_id,
                timeout_seconds=params["timeout"],
                poll_interval=1.0,
            )
            history_file = output_dir / f"history_{prompt_id}.json"
            history_file.write_text(json.dumps(history_entry, ensure_ascii=False, indent=2), encoding="utf-8")
            self._log(f"History 已保存: {history_file}")

            image_count = api_router.download_history_images(server_url, history_entry, output_dir)
            self._log(f"下载结果图数量: {image_count}")
            self._run_on_ui_thread(
                lambda: messagebox.showinfo(
                    "完成",
                    f"任务完成。\nPrompt ID: {prompt_id}\n下载图像: {image_count}\n输出目录:\n{output_dir}",
                )
            )
        except Exception as exc:
            self._log(f"任务失败: {exc}")
            self._run_on_ui_thread(lambda: messagebox.showerror("任务失败", str(exc)))
        finally:
            self._run_on_ui_thread(lambda: self._set_running(False))

    def _run_on_ui_thread(self, callback) -> None:
        self.after(0, callback)

    def _log(self, text: str) -> None:
        self._run_on_ui_thread(lambda: self._append_log(text))

    def _append_log(self, text: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{timestamp}] {text}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)


def main() -> int:
    app = ComfyApiUploadGui()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
