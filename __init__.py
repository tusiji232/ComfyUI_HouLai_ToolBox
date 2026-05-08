# ComfyUI_HouLai_ToolBox main plugin entry

import os
from pathlib import Path

# Plugin root directory
PLUGIN_ROOT = Path(__file__).parent.resolve()

# 1) Unified node imports
from .py.prompt_nodes import HouLaiRandomPrompts
from .py.houlai_switch import HouLai_8_Way_Image_Switch
from .py.houlai_text_switch import HouLai_8_Way_Text_Switch
from .py.recolor_node import HouLai_Recolor_Batch_V3
from .py.houlai_data_gate import HouLai_Data_Gate
from .py.houlai_super_api import HouLaiSuperCloudGen
from .py.houlai_llm_agent import Universal_LLM_Config, Ecommerce_Skill_Router, scan_skills_directory
from .py.nanobana_node import NanoBananaScheduler, HouLai_Nanobanan
from .py.gemini_image_node import HouLai_Gemini_Image_Gen
from .py.houlai_jimeng_seedream5 import HouLai_Jimeng_Seedream5
from .py.houlai_10_slot_image_router import HouLai_10_Slot_Image_Router
from .py.houlai_reroute import HouLai_Reroute
from .py.aliyun_translate import (
    HouLai_Aliyun_Translate,
    build_aliyun_translate_error_payload,
    handle_aliyun_translate_http_payload,
)

# 2) Register API endpoints (compatible with hot-reload)
try:
    import server
    import json
    from aiohttp import web
    from pathlib import Path
    from .py.houlai_llm_agent import scan_skills_directory_v2, SKILLS_DIR

    def is_safe_skill_path(custom_path: str) -> bool:
        """Validate that custom_path stays under allowed plugin directories."""
        if not custom_path or not custom_path.strip():
            return True

        try:
            custom = Path(custom_path.strip()).resolve()
            base = SKILLS_DIR.parent.resolve()
            return str(custom).startswith(str(base))
        except (OSError, ValueError, RuntimeError):
            return False

    if hasattr(server, "PromptServer") and server.PromptServer.instance:
        @server.PromptServer.instance.routes.post("/houlai/refresh_skills")
        async def refresh_skills_api(request):
            """Refresh skills list (v2) with optional custom path."""
            try:
                try:
                    data = await request.json()
                except json.JSONDecodeError:
                    return web.json_response(
                        {"success": False, "error": "Invalid JSON format"},
                        status=400,
                    )

                custom_path = data.get("custom_path", "")
                if custom_path and not is_safe_skill_path(custom_path):
                    print(f"[Security] Rejected unsafe skill directory path: {custom_path}")
                    return web.json_response(
                        {"success": False, "error": "Invalid skill directory path"},
                        status=403,
                    )

                skills, triggers, weights, categories, skill_id_map = scan_skills_directory_v2(
                    force_refresh=True,
                    custom_path=custom_path,
                )

                return web.json_response(
                    {
                        "success": True,
                        "skills": skills,
                        "triggers": triggers,
                        "weights": weights,
                        "categories": categories,
                        "skill_id_map": skill_id_map,
                        "count": len(skills),
                    }
                )

            except Exception as e:
                print(f"[Error] refresh_skills_api: {type(e).__name__}: {e}")
                import traceback

                traceback.print_exc()
                return web.json_response(
                    {"success": False, "error": "Internal server error"},
                    status=500,
                )

        @server.PromptServer.instance.routes.get("/houlai/get_skills")
        async def get_skills_api(request):
            """Get skills list (v2) with optional custom path."""
            try:
                custom_path = request.query.get("custom_path", "")
                if custom_path and not is_safe_skill_path(custom_path):
                    print(f"[Security] Rejected unsafe skill directory path: {custom_path}")
                    return web.json_response(
                        {"success": False, "error": "Invalid skill directory path"},
                        status=403,
                    )

                skills, triggers, weights, categories, skill_id_map = scan_skills_directory_v2(
                    force_refresh=False,
                    custom_path=custom_path,
                )

                return web.json_response(
                    {
                        "success": True,
                        "skills": skills,
                        "triggers": triggers,
                        "weights": weights,
                        "categories": categories,
                        "skill_id_map": skill_id_map,
                        "count": len(skills),
                    }
                )

            except Exception as e:
                print(f"[Error] get_skills_api: {type(e).__name__}: {e}")
                import traceback

                traceback.print_exc()
                return web.json_response(
                    {"success": False, "error": "Internal server error"},
                    status=500,
                )

        @server.PromptServer.instance.routes.post("/houlai/translate/aliyun")
        async def aliyun_translate_api(request):
            """Translate text with Alibaba Cloud TranslateGeneral."""
            try:
                try:
                    data = await request.json()
                except json.JSONDecodeError:
                    return web.json_response(
                        {"success": False, "error": "Invalid JSON format"},
                        status=400,
                    )

                response_payload = handle_aliyun_translate_http_payload(data)
                return web.json_response(response_payload)

            except Exception as e:
                status, payload = build_aliyun_translate_error_payload(e)
                if status == 500 and payload.get("error") == "Internal server error":
                    print(f"[Error] aliyun_translate_api: {type(e).__name__}: {e}")
                    import traceback

                    traceback.print_exc()
                return web.json_response(payload, status=status)

        print("[ComfyUI_HouLai_ToolBox] API endpoints registered with safety checks")
    else:
        print("[ComfyUI_HouLai_ToolBox] Hot-reload mode: API endpoints become active after restart")
except Exception as e:
    print(f"[ComfyUI_HouLai_ToolBox] API endpoint registration skipped: {e}")

# 3) Unified node class mappings
NODE_CLASS_MAPPINGS = {
    "HouLaiRandomPrompts": HouLaiRandomPrompts,
    "HouLai_8_Way_Image_Switch": HouLai_8_Way_Image_Switch,
    "HouLai_8_Way_Text_Switch": HouLai_8_Way_Text_Switch,
    "HouLai_Recolor_Batch_V3": HouLai_Recolor_Batch_V3,
    "HouLai_Data_Gate": HouLai_Data_Gate,
    "HouLaiSuperCloudGen": HouLaiSuperCloudGen,
    "Universal_LLM_Config": Universal_LLM_Config,
    "Ecommerce_Skill_Router": Ecommerce_Skill_Router,
    "NanoBananaScheduler": NanoBananaScheduler,
    "HouLai_Nanobanan": HouLai_Nanobanan,
    "HouLai_Gemini_Image_Gen": HouLai_Gemini_Image_Gen,
    "HouLai_Jimeng_Seedream5": HouLai_Jimeng_Seedream5,
    "HouLai_10_Slot_Image_Router": HouLai_10_Slot_Image_Router,
    "HouLai_Reroute": HouLai_Reroute,
    "HouLai_Aliyun_Translate": HouLai_Aliyun_Translate,
}

# 4) Display names shown in ComfyUI menu
NODE_DISPLAY_NAME_MAPPINGS = {
    "HouLaiRandomPrompts": "后来_随机提示词抽卡 (Random Batch)",
    "HouLai_8_Way_Image_Switch": "后来_8路图像分流器 (Image Switch)",
    "HouLai_8_Way_Text_Switch": "后来_8路文本分流器 (Text Switch)",
    "HouLai_Recolor_Batch_V3": "后来_批量质感改色 V3 (Recolor)",
    "HouLai_Data_Gate": "后来_万能数据闸门 (Data Gate)",
    "HouLaiSuperCloudGen": "后来_全能云端绘图 (Super Cloud Gen)",
    "Universal_LLM_Config": "后来_通用LLM配置 (LLM Config)",
    "Ecommerce_Skill_Router": "后来_电商技能路由 (Skill Router)",
    "NanoBananaScheduler": "后来_NanoBanana云端调度器 (NanoBanana)",
    "HouLai_Nanobanan": "后来_Nanobanan",
    "HouLai_Gemini_Image_Gen": "后来_Gemini图像生成 (Gemini Image)",
    "HouLai_Jimeng_Seedream5": "后来_Jimeng Seedream 5",
    "HouLai_10_Slot_Image_Router": "后来_10路可空图像上传路由 (10-Slot Router)",
    "HouLai_Reroute": "后来_转接点 (Reroute)",
    "HouLai_Aliyun_Translate": "后来_阿里云翻译 (Aliyun Translate)",
}

# 5) Frontend extension path
WEB_DIRECTORY = str(PLUGIN_ROOT / "js")

# 6) Exports
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

print("[ComfyUI_HouLai_ToolBox] Plugin loaded")
print(f"[ComfyUI_HouLai_ToolBox] JS directory: {WEB_DIRECTORY}")
