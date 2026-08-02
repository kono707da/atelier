"""从 ComfyUI object_info 生成精简的 widget 名称映射表。

只保留 {node_class: [widget_name1, widget_name2, ...]}
其中 widget_name 是按定义顺序的 widget 参数名（排除可连线输入端口）。
"""
import json
import urllib.request
import os

URL = "http://192.168.3.5:8188/object_info"
OUTPUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "design", "ui-preview", "comfyui-widget-names.json",
)


def fetch_object_info():
    with urllib.request.urlopen(URL, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_widget_names(node_class, definition):
    """从节点定义中提取 widget 名称列表（排除可连线输入端口）。

    object_info 结构：
      {
        "input": {
          "required": {"seed": ["INT", {...}], "image": ["IMAGE", ...]},
          "optional": {...}
        }
    }
    可连线输入的判定：值是 [TYPE] 或 [TYPE, {...}]，TYPE 不是
    内置 widget 类型（INT/FLOAT/STRING/BOOLEAN）且不在枚举列表中。
    实际上 ComfyUI 中 required/optional 的 key 如果对应的 value[0]
    是数组，则该 key 是 widget（下拉选择）；如果是字符串类型名，
    则该 key 是可连线输入端口（除非类型是 INT/FLOAT/STRING/BOOLEAN）。
    """
    if not isinstance(definition, dict):
        return []
    inp = definition.get("input")
    if not isinstance(inp, dict):
        return []
    required = inp.get("required") or {}
    optional = inp.get("optional") or {}
    # 按顺序合并
    ordered = []
    for key, val in (required.items() if isinstance(required, dict) else []):
        ordered.append((key, val))
    for key, val in (optional.items() if isinstance(optional, dict) else []):
        ordered.append((key, val))
    # widget 类型：值为 [TYPE, ...] 或 [[opt1, opt2, ...]]
    widget_names = []
    for key, val in ordered:
        if not isinstance(val, list) or not val:
            continue
        first = val[0]
        # 可连线输入端口类型名（大写字符串）
        # 但 BOOLEAN/INT/FLOAT/STRING 也是可连线输入，同时也是 widget
        # 枚举类型：first 是数组
        is_enum = isinstance(first, list)
        is_builtin_widget = isinstance(first, str) and first in (
            "INT", "FLOAT", "STRING", "BOOLEAN"
        )
        if is_enum or is_builtin_widget:
            widget_names.append(key)
    return widget_names


def main():
    print(f"Fetching object_info from {URL} ...")
    object_info = fetch_object_info()
    print(f"Got {len(object_info)} node classes")

    mapping = {}
    for node_class, definition in object_info.items():
        names = extract_widget_names(node_class, definition)
        if names:
            mapping[node_class] = names

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, separators=(",", ":"))

    print(f"Written {len(mapping)} node widget mappings to {OUTPUT}")
    # 显示前几个示例
    for i, (k, v) in enumerate(sorted(mapping.items())[:5]):
        print(f"  {k}: {v}")
    if "KSampler Adv. (Efficient)" in mapping:
        print(f"  KSampler Adv. (Efficient): {mapping['KSampler Adv. (Efficient)']}")


if __name__ == "__main__":
    main()
