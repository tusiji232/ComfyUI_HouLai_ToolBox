#!/usr/bin/env python3
"""
Submit base64 images to HouLai_10_Slot_Image_Router in a ComfyUI workflow.

Usage example:
  python scripts/comfy_api_upload_router.py ^
    --workflow "%USERPROFILE%\\Downloads\\test_workflow.json" ^
    --slot 1 "%USERPROFILE%\\Pictures\\example_1.jpg" ^
    --slot 2 "%USERPROFILE%\\Pictures\\example_2.jpg" ^
    --route-n 2
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

ROUTER_CLASS = "HouLai_10_Slot_Image_Router"
DEFAULT_SERVER = "http://127.0.0.1:8188"
DEFAULT_TIMEOUT_SECONDS = 300
EMPTY_SLOT_VALUE = "[空]"
DEFAULT_EMPTY_OUTPUT_MODE = "空值"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload images to ComfyUI HouLai 10-slot router via API."
    )
    parser.add_argument(
        "--workflow",
        required=True,
        help="Path to workflow JSON (UI workflow format or API prompt format).",
    )
    parser.add_argument(
        "--server",
        default=DEFAULT_SERVER,
        help=f"ComfyUI server base URL. Default: {DEFAULT_SERVER}",
    )
    parser.add_argument(
        "--router-node-id",
        type=int,
        default=None,
        help=f"Optional router node id. If omitted, first '{ROUTER_CLASS}' node is used.",
    )
    parser.add_argument(
        "--slot",
        action="append",
        nargs=2,
        metavar=("INDEX", "VALUE"),
        default=[],
        help=(
            "Set slot image payload, repeatable. "
            "INDEX=1..10, VALUE can be local file path, data URI, or b64:<base64>."
        ),
    )
    parser.add_argument(
        "--route-n",
        type=int,
        default=None,
        help="Route first N slots (0..10). Default: max provided slot index.",
    )
    parser.add_argument(
        "--resize-mode",
        choices=[
            "off",
            "pixel_count_1m",
            "longest_side",
            "shortest_side",
            "关闭",
            "按像素数量(百万)",
            "按最长边",
            "按最短边",
        ],
        default=None,
        help="Resize mode override for router.",
    )
    parser.add_argument(
        "--resize-value",
        type=int,
        default=None,
        help="Resize value override.",
    )
    parser.add_argument(
        "--resample-method",
        choices=["lanczos", "bicubic", "bilinear"],
        default=None,
        help="Resample method override.",
    )
    parser.add_argument(
        "--max-side-limit",
        type=int,
        default=None,
        help="Max side limit override.",
    )
    parser.add_argument(
        "--align-to-multiple",
        type=int,
        default=None,
        help="Align-to-multiple override.",
    )
    parser.add_argument(
        "--empty-output-mode",
        choices=["none", "blocker", "空值", "阻断"],
        default="none",
        help="How empty/unrouted slots are emitted by router.",
    )
    parser.add_argument(
        "--keep-existing-images",
        action="store_true",
        help="Do not clear image_1..image_10 before applying --slot values.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only generate payload file, do not call ComfyUI.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Wait timeout in seconds. Default: {DEFAULT_TIMEOUT_SECONDS}",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
        help="Polling interval in seconds. Default: 1.0",
    )
    parser.add_argument(
        "--out-dir",
        default="api_upload_results",
        help="Output directory for generated payload and downloaded images.",
    )
    return parser.parse_args()


def normalize_server_url(url: str) -> str:
    return url.rstrip("/")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def is_api_prompt_format(data: Any) -> bool:
    if not isinstance(data, dict) or not data:
        return False
    if "nodes" in data and isinstance(data.get("nodes"), list):
        return False
    for value in data.values():
        if not isinstance(value, dict):
            return False
        if "class_type" not in value:
            return False
    return True


def build_link_lookup(links: List[Any]) -> Dict[int, Tuple[int, int, int, int, str]]:
    lookup: Dict[int, Tuple[int, int, int, int, str]] = {}
    for entry in links:
        if not isinstance(entry, list) or len(entry) < 6:
            continue
        link_id = int(entry[0])
        src_node = int(entry[1])
        src_slot = int(entry[2])
        dst_node = int(entry[3])
        dst_slot = int(entry[4])
        link_type = str(entry[5])
        lookup[link_id] = (src_node, src_slot, dst_node, dst_slot, link_type)
    return lookup


def fetch_object_info(server_url: str) -> Optional[Dict[str, Any]]:
    url = f"{server_url}/object_info"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            return data
    except Exception:
        return None
    return None


def ensure_server_reachable(server_url: str) -> None:
    probe_paths = ["/system_stats", "/object_info", "/"]
    last_error: Optional[Exception] = None
    for path in probe_paths:
        try:
            response = requests.get(f"{server_url}{path}", timeout=5)
            if response.status_code < 500:
                return
        except requests.RequestException as exc:
            last_error = exc

    detail = f" ({last_error})" if last_error else ""
    raise RuntimeError(
        "Cannot connect to ComfyUI API at "
        f"{server_url}{detail}. Start ComfyUI first, then verify URL and port."
    )


def fallback_widget_order(node_type: str) -> List[str]:
    if node_type == ROUTER_CLASS:
        return [
            "route_n",
            "resize_mode",
            "resize_value",
            "resample_method",
            "max_side_limit",
            "align_to_multiple",
            "image_1",
            "image_2",
            "image_3",
            "image_4",
            "image_5",
            "image_6",
            "image_7",
            "image_8",
            "image_9",
            "image_10",
        ]
    return []


def get_widget_input_order(node_type: str, object_info: Optional[Dict[str, Any]]) -> List[str]:
    if object_info and node_type in object_info:
        node_info = object_info.get(node_type, {})
        input_info = node_info.get("input", {})
        names: List[str] = []
        for section in ("required", "optional"):
            section_info = input_info.get(section, {})
            if isinstance(section_info, dict):
                names.extend(section_info.keys())
        if names:
            return names
    return fallback_widget_order(node_type)


def convert_ui_workflow_to_prompt(
    workflow: Dict[str, Any],
    object_info: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    prompt: Dict[str, Any] = {}
    links_lookup = build_link_lookup(workflow.get("links", []))

    for node in workflow.get("nodes", []):
        node_id = str(node["id"])
        node_type = node["type"]
        node_inputs: Dict[str, Any] = {}

        widget_names = get_widget_input_order(node_type, object_info)
        widget_values = node.get("widgets_values", []) or []

        for input_name, input_value in zip(widget_names, widget_values):
            node_inputs[input_name] = input_value

        for input_entry in node.get("inputs", []) or []:
            link_id = input_entry.get("link")
            if link_id is None:
                continue
            link = links_lookup.get(int(link_id))
            if not link:
                continue
            src_node, src_slot, _, _, _ = link
            node_inputs[input_entry["name"]] = [str(src_node), int(src_slot)]

        prompt[node_id] = {
            "class_type": node_type,
            "inputs": node_inputs,
        }

    return prompt


def find_router_node_id(prompt: Dict[str, Any], preferred_id: Optional[int]) -> str:
    if preferred_id is not None:
        node_id = str(preferred_id)
        node_data = prompt.get(node_id)
        if not node_data:
            raise ValueError(f"Router node id {preferred_id} not found in prompt.")
        if node_data.get("class_type") != ROUTER_CLASS:
            raise ValueError(
                f"Node id {preferred_id} is '{node_data.get('class_type')}', not '{ROUTER_CLASS}'."
            )
        return node_id

    for node_id, node_data in prompt.items():
        if node_data.get("class_type") == ROUTER_CLASS:
            return node_id
    raise ValueError(f"No '{ROUTER_CLASS}' node found in workflow.")


def encode_file_to_data_uri(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{payload}"


def parse_slot_value(raw_value: str) -> str:
    raw_value = raw_value.strip()
    if raw_value.startswith("data:"):
        return raw_value
    if raw_value.startswith("b64:"):
        return raw_value[4:]

    file_path = Path(raw_value)
    if not file_path.exists():
        raise FileNotFoundError(f"Slot file not found: {raw_value}")
    return encode_file_to_data_uri(file_path)


def parse_slots(slot_args: List[List[str]]) -> Dict[str, str]:
    slot_map: Dict[str, str] = {}
    for pair in slot_args:
        if len(pair) != 2:
            continue
        index_raw, value_raw = pair
        index = int(index_raw)
        if not (1 <= index <= 10):
            raise ValueError(f"Slot index must be 1..10, got: {index}")
        slot_map[f"image_{index}"] = parse_slot_value(value_raw)
    return slot_map


def apply_router_overrides(
    prompt: Dict[str, Any],
    router_node_id: str,
    slot_map: Dict[str, str],
    route_n: Optional[int],
    resize_mode: Optional[str],
    resize_value: Optional[int],
    resample_method: Optional[str],
    max_side_limit: Optional[int],
    align_to_multiple: Optional[int],
    empty_output_mode: Optional[str],
    keep_existing_images: bool,
) -> None:
    router = prompt[router_node_id]
    inputs = router.setdefault("inputs", {})

    if not keep_existing_images:
        for i in range(1, 11):
            inputs[f"image_{i}"] = EMPTY_SLOT_VALUE

    for key, value in slot_map.items():
        inputs[key] = value

    if route_n is None:
        max_slot = 0
        for key in slot_map:
            max_slot = max(max_slot, int(key.split("_")[1]))
        route_n = max_slot if max_slot > 0 else int(inputs.get("route_n", 0) or 0)
    route_n = max(0, min(10, int(route_n)))
    inputs["route_n"] = route_n

    if resize_mode is not None:
        inputs["resize_mode"] = normalize_resize_mode_value(resize_mode)
    if resize_value is not None:
        inputs["resize_value"] = int(resize_value)
    if resample_method is not None:
        inputs["resample_method"] = resample_method
    if max_side_limit is not None:
        inputs["max_side_limit"] = int(max_side_limit)
    if align_to_multiple is not None:
        inputs["align_to_multiple"] = int(align_to_multiple)
    if empty_output_mode is not None:
        inputs["empty_output_mode"] = normalize_empty_output_mode_value(empty_output_mode)


def normalize_resize_mode_value(mode: str) -> str:
    aliases = {
        "off": "关闭",
        "关闭": "关闭",
        "pixel_count_1m": "按像素数量(百万)",
        "megapixel_1m": "按像素数量(百万)",
        "megapixel_10m": "按像素数量(百万)",
        "按像素数量": "按像素数量(百万)",
        "按像素数量(百万)": "按像素数量(百万)",
        "longest_side": "按最长边",
        "按最长边": "按最长边",
        "shortest_side": "按最短边",
        "按最短边": "按最短边",
    }
    return aliases.get(str(mode).strip(), "关闭")


def normalize_empty_output_mode_value(mode: str) -> str:
    aliases = {
        "none": "空值",
        "空值": "空值",
        "blocker": "阻断",
        "阻断": "阻断",
    }
    return aliases.get(str(mode).strip(), DEFAULT_EMPTY_OUTPUT_MODE)


def submit_prompt(server_url: str, prompt: Dict[str, Any]) -> str:
    url = f"{server_url}/prompt"
    payload = {
        "prompt": prompt,
        "client_id": str(uuid.uuid4()),
    }
    try:
        response = requests.post(url, json=payload, timeout=30)
    except requests.RequestException as exc:
        raise RuntimeError(f"Failed to call {url}: {exc}") from exc
    if response.status_code >= 400:
        detail = response.text.strip()
        raise RuntimeError(
            f"ComfyUI /prompt returned HTTP {response.status_code}. "
            f"Response: {detail[:1200]}"
        )
    data = response.json()
    if "error" in data:
        raise RuntimeError(f"ComfyUI prompt error: {data['error']}")
    prompt_id = data.get("prompt_id")
    if not prompt_id:
        raise RuntimeError(f"Missing prompt_id in response: {data}")
    return str(prompt_id)


def wait_for_history(
    server_url: str,
    prompt_id: str,
    timeout_seconds: int,
    poll_interval: float,
) -> Dict[str, Any]:
    history_url = f"{server_url}/history/{prompt_id}"
    start = time.time()
    while True:
        try:
            response = requests.get(history_url, timeout=30)
        except requests.RequestException as exc:
            raise RuntimeError(f"Failed to call {history_url}: {exc}") from exc
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and prompt_id in data:
            return data[prompt_id]
        if time.time() - start > timeout_seconds:
            raise TimeoutError(
                f"Timed out waiting for prompt_id={prompt_id} after {timeout_seconds}s."
            )
        time.sleep(max(0.1, poll_interval))


def download_history_images(server_url: str, history_entry: Dict[str, Any], out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    outputs = history_entry.get("outputs", {})
    for node_id, node_output in outputs.items():
        images = node_output.get("images", [])
        for index, image_info in enumerate(images, start=1):
            params = {
                "filename": image_info.get("filename", ""),
                "subfolder": image_info.get("subfolder", ""),
                "type": image_info.get("type", "output"),
            }
            if not params["filename"]:
                continue
            try:
                response = requests.get(f"{server_url}/view", params=params, timeout=30)
            except requests.RequestException as exc:
                raise RuntimeError(f"Failed to download image from {server_url}/view: {exc}") from exc
            response.raise_for_status()
            save_name = f"{node_id}_{index}_{Path(params['filename']).name}"
            (out_dir / save_name).write_bytes(response.content)
            count += 1
    return count


def main() -> int:
    args = parse_args()
    server_url = normalize_server_url(args.server)

    workflow_path = Path(args.workflow)
    if not workflow_path.exists():
        raise FileNotFoundError(f"Workflow file not found: {workflow_path}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    raw = load_json(workflow_path)

    if not args.dry_run:
        ensure_server_reachable(server_url)

    object_info = None if args.dry_run else fetch_object_info(server_url)

    if is_api_prompt_format(raw):
        prompt = raw
    else:
        if not isinstance(raw, dict) or not isinstance(raw.get("nodes"), list):
            raise ValueError("Unsupported workflow JSON format.")
        prompt = convert_ui_workflow_to_prompt(raw, object_info)

    router_node_id = find_router_node_id(prompt, args.router_node_id)
    slot_map = parse_slots(args.slot)

    apply_router_overrides(
        prompt=prompt,
        router_node_id=router_node_id,
        slot_map=slot_map,
        route_n=args.route_n,
        resize_mode=args.resize_mode,
        resize_value=args.resize_value,
        resample_method=args.resample_method,
        max_side_limit=args.max_side_limit,
        align_to_multiple=args.align_to_multiple,
        empty_output_mode=args.empty_output_mode,
        keep_existing_images=args.keep_existing_images,
    )

    payload_file = out_dir / "payload_prompt.json"
    payload_file.write_text(json.dumps(prompt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] Prompt payload saved: {payload_file}")
    print(f"[ok] Router node id: {router_node_id}")
    print(f"[ok] Slot count set: {len(slot_map)}")

    if args.dry_run:
        print("[dry-run] Not submitting to ComfyUI.")
        return 0

    if object_info is None:
        print("[warn] Could not fetch /object_info. Conversion may be incomplete for complex workflows.")

    prompt_id = submit_prompt(server_url, prompt)
    print(f"[ok] Submitted prompt_id: {prompt_id}")

    history_entry = wait_for_history(
        server_url=server_url,
        prompt_id=prompt_id,
        timeout_seconds=args.timeout,
        poll_interval=args.poll_interval,
    )
    history_file = out_dir / f"history_{prompt_id}.json"
    history_file.write_text(json.dumps(history_entry, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] History saved: {history_file}")

    image_count = download_history_images(server_url, history_entry, out_dir)
    print(f"[ok] Downloaded images: {image_count}")
    print(f"[ok] Output directory: {out_dir.resolve()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[error] {exc}")
        raise SystemExit(1)
