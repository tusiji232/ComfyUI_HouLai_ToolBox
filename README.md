# ComfyUI_HouLai_ToolBox

<div align="center">

**后来工具箱 - ComfyUI 多功能节点集合**

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![ComfyUI](https://img.shields.io/badge/ComfyUI-Compatible-green.svg)](https://github.com/comfyanonymous/ComfyUI)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)

</div>

## New Node: HouLai 10-Slot Image Router

- Node name: `后来_10路可空图像上传路由 (10-Slot Router)`
- Class key: `HouLai_10_Slot_Image_Router`
- Category: `HouLai_ToolBox/Logic`

### What it does

- Provides 10 upload slots on the left (`image_1` to `image_10`), each can be `[空]`.
- Provides 10 image outputs on the right, mapped by index.
- Uses `route_n` (`0~10`) to pass only the first `N` slots.
- Empty/unselected slots are blocked (not forwarded), so downstream flow is not forced.
- API direct input is supported on `image_1~image_10`:
  - input filename/path under ComfyUI `input`
  - `data:image/...;base64,...`
  - plain base64 string
  - bytes/bytearray/list[0..255] (programmatic invocation)

### Resize options

- `resize_mode`
  - `关闭`
  - `按像素数量(百万)` (`resize_value=1` means `1,000,000` pixels)
  - `按最长边`
  - `按最短边`
- `resample_method`
  - `lanczos`
  - `bicubic`
  - `bilinear`
- `max_side_limit`: max edge safety clamp after resize.
- `align_to_multiple`: edge alignment (1/2/4/8/16/32/64).
- `empty_output_mode`
  - `空值`（兼容型，未放行/空槽输出 `None`，适合可选输入节点）
  - `阻断`（严格型，使用 `ExecutionBlocker` 阻断分支）

### Routing examples

- `route_n=0`: all 10 outputs blocked.
- `route_n=2`: only slots 1 and 2 are eligible to pass.
- `route_n=9`: slots 1~9 are eligible; empty slots among them stay blocked.

## New Node: HouLai Reroute

- Node name: `后来_转接点 (Reroute)`
- Class key: `HouLai_Reroute`
- Category: `HouLai_ToolBox/Logic`

### What it does

- Single input to single output pass-through.
- Uses wildcard socket type (`ANY`), so it can relay `IMAGE/TEXT/LATENT/MODEL/...`.
- No transform, no copy, no side effect. It only helps line routing and graph readability.

## 可视化测试工具（脚本）

- `scripts/comfy_visual_uploader_yjhpt.py`
  - 针对 `一句话P图（支持1~10图）3.4.json` 的可视化上传与结果接收工具。
  - 支持 10 路图像选择、`route_n`、一句话提示词、API Key、缩放参数设置。
  - 提交后自动拉取结果并在界面预览。
- 启动方式：`scripts/run_visual_uploader_yjhpt.ps1`

## 📖 简介

ComfyUI_HouLai_ToolBox 是一个功能丰富的 ComfyUI 自定义节点集合，提供了从基础工具到高级 AI 功能的完整解决方案。

## ✨ 功能特性

### 🎨 图像处理节点
- **批量质感改色 V3** - 高级批量图像重新着色工具
- **8路图片分流器** - 智能图像路由和分发系统
- **图像处理工具** - 多种图像操作和转换功能

### 📝 文本处理节点
- **随机提示词抽取** - 批量随机提示词生成器
- **8路文本分流器** - 灵活的文本路由系统
- **文本处理工具** - 文本操作和格式化功能

### 🤖 AI 智能节点
- **通用LLM配置** - 支持多种 LLM 服务（豆包、GPT-4o、DeepSeek 等）
- **电商技能路由** - 基于 YAML 技能库的智能提示词生成
- **多模态支持** - 图像+文本混合输入处理

### 🔧 实用工具节点
- **万能数据闸门** - 通用数据流控制节点
- **全能云端绘图** - 云端 API 绘图集成
- **超级 API 工具** - 强大的 API 调用功能

### 🚀 云端调度节点
- **NanoBanana云端调度器** - 批量任务调度，支持多图参考、批量提示词、Fire-and-Forget 异步处理

##  安装

### 方法一：Git 克隆（推荐）

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/tusiji232/ComfyUI_HouLai_ToolBox.git
cd ComfyUI_HouLai_ToolBox
pip install -r requirements.txt
```

### 方法二：手动下载

1. 下载本仓库的 ZIP 文件
2. 解压到 `ComfyUI/custom_nodes/` 目录
3. 安装依赖：
```bash
pip install -r requirements.txt
```

## 🚀 快速开始

### 基础节点使用

1. 启动 ComfyUI
2. 在节点菜单中找到 `后来工具箱` 分类
3. 拖拽所需节点到工作区
4. 连接节点并配置参数

### LLM 节点使用示例

#### 1. 配置 LLM 连接

```
添加节点: 🤖 后来_通用LLM配置
配置参数:
  - base_url: https://ark.cn-beijing.volces.com/api/v3
  - api_key: 你的API密钥
  - model_name: ep-xxx...
  - system_prompt: 你是一个专业的电商视觉内容生成助手
```

#### 2. 使用电商技能路由

```
添加节点: 🛒 后来_电商技能路由
连接: LLM配置 → 电商技能路由
配置:
  - 技能选择: beauty - 美妆产品
  - 输出模式: 分批输出
  - 批次数量: 4
  - 可选输入: 图片、产品名称、卖点等
```

## 📂 项目结构

```
ComfyUI_HouLai_ToolBox/
├── __init__.py              # 节点注册入口
├── requirements.txt         # Python 依赖
├── README.md               # 项目文档
├── LICENSE                 # 开源协议
├── py/                     # Python 节点实现
│   ├── __init__.py
│   ├── houlai_llm_agent.py      # LLM 智能节点
│   ├── houlai_super_api.py      # 云端 API 节点
│   ├── houlai_data_gate.py      # 数据闸门节点
│   ├── houlai_switch.py         # 图片分流器
│   ├── houlai_text_switch.py    # 文本分流器
│   ├── recolor_node.py          # 改色节点
│   ├── prompt_nodes.py          # 提示词节点
│   ├── image_nodes.py           # 图像处理节点
│   ├── nanobana_node.py         # NanoBanana 调度节点
│   └── utils.py                 # 工具函数
├── js/                     # JavaScript 前端
│   └── houlai_menu.js          # 菜单扩展
├── skills/                 # LLM 技能库
│   ├── beauty.yaml             # 美妆技能
│   └── digital.yaml            # 数码技能
└── examples/               # 示例工作流
    └── demo_prompt.json
```

## 🎯 节点列表

| 节点名称 | 功能描述 | 分类 |
|---------|---------|------|
| ✨ 后来_随机提示词抽取 | 批量随机提示词生成 | 文本处理 |
| 🔀 后来_8路图片分流器 | 图像智能路由分发 | 图像处理 |
| 🔀 后来_8路文本分流器 | 文本智能路由分发 | 文本处理 |
| 🎨 后来_批量质感改色 V3 | 批量图像重新着色 | 图像处理 |
| 🛑 后来_万能数据闸门 | 通用数据流控制 | 工具 |
| ☁️ 后来_全能云端绘图 | 云端 API 绘图 | AI 生成 |
| 🤖 后来_通用LLM配置 | LLM 服务配置 | AI 智能 |
| 🛒 后来_电商技能路由 | 智能提示词生成 | AI 智能 |
| 🚀 后来_NanoBanana云端调度器 | 批量任务异步调度 | 云端调度 |
| 🔁 后来_转接点 | 万能类型数据转接（单进单出） | 逻辑 |

## 🔧 依赖要求

- Python >= 3.8
- ComfyUI (最新版本)
- openai >= 1.0.0
- PyYAML >= 6.0
- Pillow >= 9.0.0
- requests >= 2.28.0

## 📝 技能库扩展

### 添加自定义技能

在 `skills/` 目录下创建 YAML 文件：

```yaml
# skills/custom.yaml
my_skill:
  name: "我的自定义技能"
  description: "技能描述"
  template: |
    根据以下信息生成 {batch_count} 条提示词：
    {selling_points}
    
    要求：
    1. 每条提示词独立成行
    2. 适配 Flux 模型
    3. 包含产品特点
```

### 技能模板变量

- `{platform}` - 平台名称
- `{selling_points}` - 产品信息上下文
- `{batch_count}` - 批次数量

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📄 开源协议

本项目采用 MIT 协议开源 - 详见 [LICENSE](LICENSE) 文件

## 🙏 致谢

- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) - 强大的 Stable Diffusion GUI
- 所有贡献者和用户的支持

## 📮 联系方式

- Issues: [GitHub Issues](https://github.com/tusiji232/ComfyUI_HouLai_ToolBox/issues)
- Discussions: [GitHub Discussions](https://github.com/tusiji232/ComfyUI_HouLai_ToolBox/discussions)

---

<div align="center">

**如果这个项目对你有帮助，请给个 ⭐ Star 支持一下！**

</div>
