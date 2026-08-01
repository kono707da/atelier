"""Seed a full small-scene + shot-page + character + material dataset for the
§8.2 front-end simulated click test. Targets a TEST-environment backend only.
Idempotent-ish: reuses existing named project if present.
"""
from __future__ import annotations

import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8113"
PROJ_NAME = "分镜点击测试项目"


def post(path: str, body: dict) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        BASE + path, data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def put(path: str, body: dict) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        BASE + path, data=data, method="PUT",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get(path: str) -> dict:
    req = urllib.request.Request(BASE + path, method="GET")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def delete(path: str) -> None:
    req = urllib.request.Request(BASE + path, method="DELETE")
    with urllib.request.urlopen(req, timeout=10) as resp:
        resp.read()


def main() -> int:
    # 1. project (delete existing then recreate, for idempotent re-runs)
    projects = get("/api/projects?limit=50").get("items", [])
    proj = next((p for p in projects if p["name"] == PROJ_NAME), None)
    if proj:
        delete(f"/api/projects/{proj['id']}/permanent")
    proj = post("/api/projects", {"name": PROJ_NAME})["project"]
    pid = proj["id"]

    # 2. chapter -> large_scene -> small_scene
    ch = post(f"/api/projects/{pid}/chapters", {"name": "第一章"})["chapter"]
    ls = post(f"/api/chapters/{ch['id']}/large-scenes", {"name": "大场景A"})["large_scene"]
    ss = post(f"/api/large-scenes/{ls['id']}/small-scenes", {"name": "小场景A"})["small_scene"]

    # 3. shot page P01 (empty prompt for the test)
    sp = post(f"/api/small-scenes/{ss['id']}/pages",
              {"name": "P01", "description": "点击测试首页"})["page"]

    # 4. character + variant
    char = post("/api/characters", {"name": "女主角"})["character"]
    var = post(f"/api/characters/{char['id']}/variants", {"name": "带外套"})["variant"]

    # 5. specs (custom labels) + fill spec values for the variant
    existing_specs = get("/api/specs")["items"]
    def get_or_create_spec(label: str) -> dict:
        match = next((s for s in existing_specs
                      if s.get("custom_label") == label), None)
        if match:
            return match
        return post("/api/specs", {"spec_type": "custom", "custom_label": label})["spec"]
    spec_half = get_or_create_spec("正面半身")
    spec_full = get_or_create_spec("正面全身")
    spec_back = get_or_create_spec("背面全身")

    def fill_spec_value(variant_id: str, spec_id: str, prompt: str) -> dict:
        values = get(f"/api/character-variants/{variant_id}/spec-values")["items"]
        sv = next((v for v in values if v["spec_id"] == spec_id), None)
        if not sv:
            print(f"!! spec value not found for variant {variant_id} spec {spec_id}", file=sys.stderr)
            sys.exit(1)
        sv_id = sv["id"]
        req = urllib.request.Request(
            BASE + f"/api/character-spec-values/{sv_id}",
            data=json.dumps({"prompt": prompt}).encode("utf-8"),
            method="PATCH",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    fill_spec_value(var["id"], spec_half["id"],
                    "<lora:girl_v1:0.8>, 1girl, silver hair, red eyes,\n"
                    "--outfit\nwinter coat, scarf\n\n"
                    "--quality\nmasterpiece, best quality")
    # spec_full and spec_back left EMPTY to verify only filled specs show
    fill_spec_value(var["id"], spec_full["id"], "")
    fill_spec_value(var["id"], spec_back["id"], "")

    # 6. materials + material pages (4 types: scene/composition/expression/lighting)
    types_pages = {
        "scene": ("场景素材", "室内卧室", "bedroom, night, window moonlight"),
        "composition": ("构图素材", "三分构图", "rule of thirds, full body"),
        "expression": ("表情素材", "微笑", "smile, blush"),
        "lighting": ("光线素材", "柔光", "soft light, warm tone"),
    }
    material_ids = []
    for mtype, (mname, pname, pprompt) in types_pages.items():
        mat = post("/api/materials", {
            "name": mname,
            "material_type": mtype,
            "content": pprompt,
        })["material"]
        material_ids.append(mat["id"])
        post(f"/api/materials/{mat['id']}/pages",
             {"name": pname, "prompt_text": pprompt, "negative_prompt": f"no {mtype}"})

    # 7. link materials to small scene + map each to P01
    post(f"/api/small-scenes/{ss['id']}/resources", {"material_id": material_ids[0]})  # scene
    post(f"/api/small-scenes/{ss['id']}/resources", {"material_id": material_ids[1]})  # composition
    post(f"/api/small-scenes/{ss['id']}/resources", {"material_id": material_ids[2]})  # expression
    post(f"/api/small-scenes/{ss['id']}/resources", {"material_id": material_ids[3]})  # lighting

    # map each material's first page to the shot page by type
    for mid, mtype in zip(material_ids, ["scene", "composition", "expression", "lighting"]):
        pages = get(f"/api/materials/{mid}/pages")["pages"]
        put(f"/api/small-scene-pages/{sp['id']}/mappings/{mtype}",
            {"material_page_id": pages[0]["id"]})

    out = {
        "project": pid,
        "chapter": ch["id"],
        "large_scene": ls["id"],
        "small_scene": ss["id"],
        "shot_page": sp["id"],
        "character": char["id"],
        "variant": var["id"],
        "spec_half": spec_half["id"],
        "spec_full": spec_full["id"],
        "spec_back": spec_back["id"],
        "materials": {t: mid for mid, t in zip(material_ids, ["scene", "composition", "expression", "lighting"])},
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
