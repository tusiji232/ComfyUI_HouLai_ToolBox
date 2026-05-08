import { app } from "../../scripts/app.js";

const EXTENSION_NAME = "ComfyUI_HouLai_ToolBox.WidgetI18N";

const NODE_LOCALIZERS = {
  HouLai_10_Slot_Image_Router: {
    labels: {
      route_n: "路由数量",
      resize_mode: "缩放模式",
      resize_value: "像素数量",
      resample_method: "缩放算法",
      max_side_limit: "最大边长限制",
      align_to_multiple: "尺寸对齐倍数",
      empty_output_mode: "空槽输出策略",
    },
    dynamicLabel(widget) {
      if (/^image_\d+$/.test(widget.name)) {
        const index = widget.name.split("_")[1];
        return `图像${index}`;
      }
      return null;
    },
  },
  HouLai_Gemini_Image_Gen: {
    labels: {
      prompt: "提示词",
      api_key: "API 密钥",
      base_url: "接口地址",
      aspect_ratio_mode: "宽高比模式",
      custom_aspect_ratio: "自定义宽高比",
      image_size: "图像尺寸",
      response_modalities: "返回模态",
      enable_retry: "失败重试",
      retry_count: "失败重试次数",
    },
    legacyValueMaps: {
      aspect_ratio_mode: {
        自动: "auto",
        跟随图1: "auto_from_image1",
        自定义: "custom",
      },
      response_modalities: {
        仅图片: "IMAGE",
        "文本+图片": "TEXT+IMAGE",
      },
    },
  },
};

function normalizeLegacyWidgetValue(widget, legacyValueMap) {
  if (!widget || !legacyValueMap || typeof widget.value !== "string") return;
  const normalizedValue = legacyValueMap[widget.value];
  if (normalizedValue && normalizedValue !== widget.value) {
    widget.value = normalizedValue;
  }
}

function localizeNodeWidgets(node) {
  const nodeKey = node?.comfyClass || node?.type;
  const config = NODE_LOCALIZERS[nodeKey];
  if (!config || !node?.widgets?.length) return;

  for (const widget of node.widgets) {
    if (!widget?.name) continue;

    const legacyValueMap = config.legacyValueMaps?.[widget.name];
    if (legacyValueMap) {
      normalizeLegacyWidgetValue(widget, legacyValueMap);

      const originalBeforeQueued = widget.beforeQueued;
      widget.beforeQueued = function () {
        normalizeLegacyWidgetValue(widget, legacyValueMap);
        return originalBeforeQueued?.apply(this, arguments);
      };
    }

    if (config.labels?.[widget.name]) {
      widget.label = config.labels[widget.name];
      continue;
    }

    const dynamicLabel = config.dynamicLabel?.(widget);
    if (dynamicLabel) {
      widget.label = dynamicLabel;
    }
  }

  node.setDirtyCanvas?.(true, true);
}

app.registerExtension({
  name: EXTENSION_NAME,

  beforeRegisterNodeDef(nodeType, nodeData) {
    if (!nodeData?.name || !NODE_LOCALIZERS[nodeData.name]) return;

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const result = onNodeCreated?.apply(this, arguments);
      localizeNodeWidgets(this);
      return result;
    };

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      const result = onConfigure?.apply(this, arguments);
      localizeNodeWidgets(this);
      return result;
    };
  },

  loadedGraphNode(node) {
    localizeNodeWidgets(node);
  },

  nodeCreated(node) {
    localizeNodeWidgets(node);
  },
});
