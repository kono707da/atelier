const pages = [
  ["projects", "项目中心", "项目", "PJ"],
  ["overview", "项目概览", "制作", "OV"],
  ["story-canvas", "剧本画布", "制作", "SC"],
  ["scene-editor", "场景编辑", "制作", "SE"],
  ["shot-inspector", "分镜检查器", "制作", "SH"],
  ["materials", "素材库", "素材", "MT"],
  ["material-detail", "素材详情", "素材", "MD"],
  ["characters", "人物库", "素材", "CH"],
  ["character-database", "角色查询", "工具", "CD"],
  ["character-matrix", "人物替换矩阵", "制作", "MX"],
  ["workflows", "工作流库", "工作流", "WF"],
  ["workflow-canvas", "工作流画布", "工作流", "WC"],
  ["batch", "批量配置", "生产", "BG"],
  ["tasks", "任务中心", "生产", "TK"],
  ["review", "项目审片图库", "生产", "RV"],
  ["assembly", "最终作品装配", "成片", "AS"],
  ["library", "全局图库", "图库", "LB"],
  ["image-detail", "图片详情", "图库", "ID"],
  ["export", "导出中心", "成片", "EX"],
  ["settings", "设置与 ComfyUI", "系统", "ST"],
];

const navGroups = [
  ["项目", ["projects"]],
  ["项目制作", ["overview", "story-canvas", "workflows", "batch"]],
  ["生产与成片", ["tasks", "review", "assembly", "export"]],
  ["全局资源", ["characters", "materials", "library", "settings"]],
  ["工具", ["character-database"]],
];

const pageMeta = Object.fromEntries(pages.map((p) => [p[0], p]));
const params = new URLSearchParams(location.search);
const current = pageMeta[params.get("page")] ? params.get("page") : "projects";

const colors = [
  ["#cbd6ff", "#f3dae9", "#c6e9e5"],
  ["#d5d0fa", "#f2dfc8", "#c4e6ec"],
  ["#bfe1ec", "#e6d7f7", "#f3d6d9"],
  ["#d7e4c7", "#cddcf6", "#ead5ed"],
  ["#f1d5c5", "#c9d6f7", "#c6e8df"],
  ["#c8e7e1", "#ead6f4", "#f2ddb9"],
  ["#d0daf4", "#d8edf0", "#eed2df"],
  ["#e2d0f1", "#c8e2f0", "#f0ddca"],
];

function thumb(label, index = 0, cls = "") {
  const c = colors[index % colors.length];
  return `<div class="thumb ${cls}" style="--c1:${c[0]};--c2:${c[1]};--c3:${c[2]}"><span class="thumb-label">${label}</span></div>`;
}

function chip(text, color = "") {
  return `<span class="chip ${color}">${text}</span>`;
}

function status(text, color = "") {
  return `<span class="status ${color}"><i class="dot"></i>${text}</span>`;
}

function progress(value, color = "") {
  return `<div class="progress ${color}"><i style="width:${value}%"></i></div>`;
}

function button(text, cls = "") {
  return `<button class="btn ${cls}">${text}</button>`;
}

function pageHeader(title, subtitle, actions = "") {
  return `<div class="page-header">
    <div><h1 class="page-title">${title}</h1><p class="page-subtitle">${subtitle}</p></div>
    <div class="header-actions">${actions}</div>
  </div>`;
}

function panel(title, subtitle, body, actions = "", extra = "") {
  return `<section class="panel ${extra}">
    <div class="panel-header">
      <div><div class="panel-title">${title}</div>${subtitle ? `<div class="panel-sub">${subtitle}</div>` : ""}</div>
      <div class="panel-header-actions">${actions}</div>
    </div>
    <div class="panel-body">${body}</div>
  </section>`;
}

function metric(title, value, note, delta = "") {
  return `<div class="metric-card">
    <div class="metric-top"><span>${title}</span>${delta ? `<span class="delta">${delta}</span>` : ""}</div>
    <div class="metric-value">${value}</div>
    <div class="metric-note">${note}</div>
  </div>`;
}

function shell(content) {
  const meta = pageMeta[current];
  const nav = navGroups.map(([title, keys]) => {
    const items = keys.map((key) => {
      const p = pageMeta[key];
      const activeAliases = {
        materials: ["materials", "material-detail"],
        workflows: ["workflows", "workflow-canvas"],
        characters: ["characters", "character-matrix"],
        review: ["review", "shot-inspector", "scene-editor"],
        library: ["library", "image-detail"],
      };
      const isActive = (activeAliases[key] || [key]).includes(current);
      return `<button class="nav-item ${isActive ? "active" : ""}" data-page="${key}">
        <span class="nav-icon">${p[3]}</span><span>${p[1]}</span>
      </button>`;
    }).join("");
    return `<div class="nav-section">${title}</div>${items}`;
  }).join("");

  return `<div class="app-shell">
    <aside class="sidebar">
      <div class="brand"><span class="brand-mark">A</span><span class="brand-name">Atelier</span><span class="brand-tag">DESIGN</span></div>
      <div class="nav-scroll">${nav}</div>
      <div class="sidebar-bottom">
        <div class="health pending"><span class="health-dot"></span><span>ComfyUI 尚未检测</span><span style="margin-left:auto;color:#9aa2b2">—</span></div>
      </div>
    </aside>
    <main class="workspace">
      <header class="topbar">
        <div class="breadcrumb"><span>Atelier</span><span class="chevron">›</span><span>${meta[2]}</span><span class="chevron">›</span><strong>${meta[1]}</strong></div>
        <div class="topbar-spacer"></div>
        <div class="environment-pill loading" id="environment-pill"><span class="environment-dot"></span><span>正在连接数据库</span></div>
        <div class="save-state"><span class="save-check">✓</span>所有更改已保存</div>
        <button class="icon-button">⌘</button>
        <button class="icon-button">?</button>
        <span class="avatar">K</span>
      </header>
      <div class="page">${content}</div>
    </main>
  </div>`;
}

function projectsPage() {
  const projectData = [
    ["海边度假篇", "4 个章节 · 3 个启用分支", "200 页 · 1,284 张图片", 68, "进行中"],
    ["礼服剧场", "3 个章节 · 2 个启用分支", "148 页 · 862 张图片", 44, "制作中"],
    ["夏日角色集", "1 个章节 · 无分支", "36 页 · 219 张图片", 92, "审片中"],
    ["室内光影研究", "素材实验项目", "64 页 · 406 张图片", 100, "已完成"],
  ];
  const cards = projectData.map((p, i) => `<div class="project-card">
    ${thumb(`PROJECT 0${i + 1}`, i)}
    <div>
      <div style="display:flex;align-items:center;gap:7px">${status(p[4], i === 3 ? "green" : i === 2 ? "orange" : "blue")}</div>
      <div class="project-title">${p[0]}</div>
      <div class="project-meta">${p[1]}<br>${p[2]}</div>
      <div class="project-tags">${chip(i % 2 ? "短裤分支" : "裙装分支", "purple")}${chip("Illustrious", "blue")}${chip("1920×1280")}</div>
      <div class="project-progress">${progress(p[3])}</div>
    </div>
  </div>`).join("");
  return `<div class="page-scroll">
    ${pageHeader("项目中心", "从剧本积木到最终成片，所有制作进度都集中在这里。", button("导入项目") + '<button class="btn primary" data-api-action="open-project-modal">新建项目</button>')}
    <div class="grid cols-4">
      ${metric("活跃项目", "4", "过去 30 天", "+1")}
      ${metric("待跑分镜", "326", "跨 3 个项目")}
      ${metric("运行中任务", "18", "当前队列约 42 分钟")}
      ${metric("图库索引", "1,024,836", "全部图片已建立索引", "100%")}
    </div>
    <div class="section-line"><h3>最近项目</h3><span>按最后编辑时间排序</span><div class="spacer"></div><div class="search wide">⌕&nbsp;&nbsp;搜索项目、标签或分支</div><button class="btn small">筛选</button></div>
    <div class="grid cols-2">${cards}</div>
  </div>`;
}

function overviewPage() {
  const activity = [
    ["BG", "批次 #B-0287 已完成", "生成 48 张图片 · 12 分钟前", "green"],
    ["SC", "短裤分支新增 6 个分镜页", "剧本画布 · 38 分钟前", "blue"],
    ["RV", "P042 采用了 2 张图片", "审片图库 · 1 小时前", "purple"],
    ["WF", "工作流更新为 v12", "角色替换工作流 · 2 小时前", "orange"],
  ].map((a) => `<div class="mini-list-item"><span class="mini-list-icon">${a[0]}</span><div class="mini-list-text">${a[1]}<div class="mini-list-sub">${a[2]}</div></div><span style="margin-left:auto">${status("已记录", a[3])}</span></div>`).join("");
  return `<div class="page-scroll">
    ${pageHeader("海边度假篇", "项目代号 AT-2026-071 · 最后编辑于今天 16:42", button("项目设置") + button("打开剧本画布", "primary"))}
    <div class="grid cols-4">
      ${metric("剧本页", "200", "4 个章节 · 9 个场景")}
      ${metric("启用分支", "3", "裙装、短裤、夜间")}
      ${metric("图片实例", "1,284", "其中 236 张已采用")}
      ${metric("成片进度", "68%", "136 / 200 页已有采用图")}
    </div>
    <div class="split-2" style="height:calc(100% - 190px);margin-top:14px">
      <div class="split-left grid" style="grid-template-rows:1fr 0.9fr">
        ${panel("制作进度", "按阶段统计", `<div class="grid cols-3">
          <div class="metric-card"><div class="metric-top">剧本编排</div><div class="metric-value">200</div><div class="metric-note">页面已编译</div><div style="margin-top:10px">${progress(100, "green")}</div></div>
          <div class="metric-card"><div class="metric-top">跑图完成</div><div class="metric-value">172</div><div class="metric-note">28 页待生成</div><div style="margin-top:10px">${progress(86)}</div></div>
          <div class="metric-card"><div class="metric-top">审片完成</div><div class="metric-value">136</div><div class="metric-note">64 页待采用</div><div style="margin-top:10px">${progress(68)}</div></div>
        </div>`)}
        ${panel("分支版本", "每个分支可独立生成与成片", `<div class="grid cols-3">
          <div class="setting-card"><div style="display:flex;justify-content:space-between">${status("启用", "green")}${chip("A")}</div><div class="setting-title" style="margin-top:10px">裙装主线</div><div class="setting-desc">200 页 · 默认人物规格</div></div>
          <div class="setting-card"><div style="display:flex;justify-content:space-between">${status("启用", "green")}${chip("B")}</div><div class="setting-title" style="margin-top:10px">短裤分支</div><div class="setting-desc">62 页覆盖 · 138 页继承</div></div>
          <div class="setting-card"><div style="display:flex;justify-content:space-between">${status("部分启用", "orange")}${chip("C")}</div><div class="setting-title" style="margin-top:10px">夜间场景</div><div class="setting-desc">34 页 · 光线与工作流覆盖</div></div>
        </div>`)}
      </div>
      <div class="split-right">${panel("最近活动", "项目内所有修改均可追踪", `<div class="mini-list">${activity}</div>`, button("查看全部", "small"))}</div>
    </div>
  </div>`;
}

function storyCanvasPage() {
  const palette = [
    ["章节", "blue"], ["大场景", "green"], ["小场景", "cyan"], ["转场", "orange"],
    ["单页镜头", "purple"], ["场景包 · 8 页", "blue"], ["条件分支", "orange"],
  ].map((p) => `<div class="palette-item"><span class="palette-swatch ${p[1]}"></span>${p[0]}<span style="margin-left:auto;color:#b1b7c2">⋮⋮</span></div>`).join("");
  return `<div class="page-scroll">
    ${pageHeader("剧本画布", "海边度假篇 / 剧本版本 v18 · 200 页 · 3 个启用分支", button("版本历史") + button("编译跑图列表", "primary"))}
    <div class="three-pane" style="height:calc(100% - 79px)">
      <section class="panel"><div class="panel-header"><div><div class="panel-title">积木与场景包</div><div class="panel-sub">拖入画布创建结构</div></div></div><div class="search" style="margin:10px">⌕ 搜索素材</div><div class="palette-list">${palette}</div></section>
      <section class="panel" style="overflow:hidden">
        <div class="toolbar"><span class="tool active">主线</span><span class="tool">裙装 A</span><span class="tool">短裤 B</span><span class="tool">夜间 C</span><span class="spacer"></span><span class="tool">−</span><span class="tool">82%</span><span class="tool">＋</span><span class="tool">自动整理</span></div>
        <div class="canvas">
          <div class="story-stage">
            <div class="story-spine"></div>
            <div class="story-block chapter" style="left:0;top:109px"><div class="block-kicker">CHAPTER 01</div><div class="block-title">抵达与开场</div><div class="block-meta">3 个场景 · 18 页</div></div>
            <div class="story-block" style="left:142px;top:104px"><div class="block-kicker">大场景 01</div><div class="block-title">公共沙滩区</div><div class="block-meta">2 个小场景 · 38 页</div><div class="block-footer">${chip("已编译", "green")}${chip("38 页")}</div></div>
            <div class="story-block active" style="left:339px;top:104px"><div class="block-kicker">大场景 02</div><div class="block-title">浅水区</div><div class="block-meta">3 个小场景 · 42 页</div><div class="block-footer">${chip("2 个分支", "orange")}${chip("42 页")}</div></div>
            <div class="story-block" style="left:536px;top:104px"><div class="block-kicker">转场</div><div class="block-title">回到度假屋</div><div class="block-meta">转场包 · 4 页</div><div class="block-footer">${chip("场景包", "purple")}</div></div>
            <div class="story-block" style="left:733px;top:104px"><div class="block-kicker">大场景 03</div><div class="block-title">室内夜景</div><div class="block-meta">4 个小场景 · 64 页</div><div class="block-footer">${chip("夜间 C", "blue")}${chip("64 页")}</div></div>
            <div class="branch-path" style="left:428px;top:218px;width:92px;transform:rotate(55deg)"></div>
            <div class="branch-path" style="left:479px;top:292px;width:118px"></div>
            <div class="branch-label" style="left:454px;top:253px">服装分支</div>
            <div class="story-block" style="left:598px;top:246px;border-color:#efc08a"><div class="block-kicker">BRANCH B</div><div class="block-title">短裤版本</div><div class="block-meta">覆盖人物变体与 6 个分镜页</div><div class="block-footer">${status("启用", "green")}${chip("62 页")}</div></div>
            <div class="branch-path" style="left:775px;top:302px;width:76px;transform:rotate(-54deg)"></div>
            <div class="foot-status"><span>画布已自动整理 · 19 个结构块</span><span>缩略导航 ◫</span></div>
          </div>
        </div>
      </section>
      <section class="panel inspector">
        <div class="panel-header"><div><div class="panel-title">浅水区</div><div class="panel-sub">大场景 02 · 当前选中</div></div>${status("2 个分支", "orange")}</div>
        <div class="inspector-section"><div class="form-group"><label class="label">场景名称</label><div class="field">浅水区</div></div><div class="form-row"><div><label class="label">页面</label><div class="field">P042–P083</div></div><div><label class="label">小场景</label><div class="field">3 个</div></div></div></div>
        <div class="inspector-section"><label class="label">继承的场景素材</label><div style="display:flex;flex-wrap:wrap;gap:5px">${chip("海面环境", "blue")}${chip("日间自然光", "green")}${chip("水中构图包", "purple")}</div></div>
        <div class="inspector-section"><label class="label">分支</label><div class="mini-list"><div class="mini-list-item"><span class="mini-list-icon">A</span><div class="mini-list-text">裙装主线<div class="mini-list-sub">默认继承</div></div>${status("启用", "green")}</div><div class="mini-list-item"><span class="mini-list-icon">B</span><div class="mini-list-text">短裤版本<div class="mini-list-sub">62 页覆盖</div></div>${status("启用", "green")}</div></div></div>
      </section>
    </div>
  </div>`;
}

function sceneEditorPage() {
  const shots = [
    ["P042", "进入浅水区", "中景 · 双人 · 日间", "已采用", "green"],
    ["P043", "水面互动", "半身 · 正面 · 自然光", "已采用", "green"],
    ["P044", "靠近镜头", "胸腰景 · 侧面", "待审片", "orange"],
    ["P045", "分支入口", "人物形象将在此分叉", "2 个分支", "purple"],
    ["P046", "裙装分支镜头", "继承主线构图", "待跑图", "blue"],
    ["P047", "短裤分支镜头", "覆盖人物变体", "待跑图", "blue"],
    ["P048", "重新汇合", "两分支共用后续页面", "已编译", "green"],
  ];
  const rows = shots.map((s, i) => `<div class="shot-row ${i === 3 ? "selected" : ""}">
    <span class="shot-no">${i + 1}</span><span class="mini-thumb"></span><div><div class="shot-title">${s[0]} · ${s[1]}</div><div class="shot-desc">${s[2]}</div></div><span>${status(s[3], s[4])}</span><span style="color:#9aa2b2;font-size:9px">⋮⋮ 拖动</span>
  </div>`).join("");
  return `<div class="page-scroll">
    ${pageHeader("场景编辑 · 浅水区", "聚焦编辑大场景内部结构，分支仍与主剧本同步。", button("返回剧本画布") + button("保存场景包", "primary"))}
    <div class="three-pane" style="grid-template-columns:210px minmax(0,1fr) 276px;height:calc(100% - 79px)">
      ${panel("场景结构", "42 页", `<div class="mini-list">
        <div class="mini-list-item"><span class="mini-list-icon">01</span><div class="mini-list-text">进入水边<div class="mini-list-sub">P042–P048 · 7 页</div></div></div>
        <div class="mini-list-item" style="background:var(--blue-soft)"><span class="mini-list-icon">02</span><div class="mini-list-text">浅水互动<div class="mini-list-sub">P049–P063 · 15 页</div></div></div>
        <div class="mini-list-item"><span class="mini-list-icon">03</span><div class="mini-list-text">场景收束<div class="mini-list-sub">P064–P083 · 20 页</div></div></div>
      </div>`)}
      <section class="panel" style="overflow:hidden"><div class="toolbar"><span class="tool active">列表</span><span class="tool">缩略时间线</span><span class="spacer"></span><span class="tool">＋ 单页</span><span class="tool">＋ 分支</span><span class="tool">自动编号</span></div><div class="shot-list">${rows}</div></section>
      <section class="panel inspector"><div class="panel-header"><div><div class="panel-title">分支入口</div><div class="panel-sub">P045 · 条件分支</div></div>${status("启用", "green")}</div>
        <div class="inspector-section"><label class="label">分支维度</label><div class="field">人物形象变体</div></div>
        <div class="inspector-section"><label class="label">分支 A</label><div class="field">裙装 · 继承默认人物</div><div style="height:8px"></div><label class="label">分支 B</label><div class="field">短裤 · 覆盖角色变体</div></div>
        <div class="inspector-section"><label class="label">汇合位置</label><div class="field">P048 · 重新汇合</div><div class="empty-note" style="margin-top:10px">两个分支都会进入跑图列表，并分别形成可独立审片与成片的版本。</div></div>
      </section>
    </div>
  </div>`;
}

function shotInspectorPage() {
  return `<div class="page-scroll">
    ${pageHeader("分镜检查器 · P044", "海边度假篇 / 浅水区 / 水面互动", button("上一页") + button("下一页") + button("生成此页", "primary"))}
    <div class="three-pane wide-left" style="height:calc(100% - 79px)">
      <section class="panel inspector">
        <div class="panel-header"><div><div class="panel-title">页面素材</div><div class="panel-sub">拖入、替换或调整顺序</div></div></div>
        <div class="inspector-section"><label class="label">构图与视角</label><div style="display:flex;flex-wrap:wrap;gap:5px">${chip("胸腰景", "blue")}${chip("正面")}${chip("轻微俯视")}</div></div>
        <div class="inspector-section"><label class="label">人物与互动</label><div style="display:flex;flex-wrap:wrap;gap:5px">${chip("双人", "purple")}${chip("靠近镜头")}${chip("人物位置已定义", "green")}</div></div>
        <div class="inspector-section"><label class="label">环境与光线</label><div style="display:flex;flex-wrap:wrap;gap:5px">${chip("浅水区", "cyan")}${chip("水面反光")}${chip("日间自然光", "orange")}</div></div>
        <div class="inspector-section"><label class="label">提示词片段</label><div class="field textarea">quality preset · character slot · composition pack · scene pack · lighting preset</div></div>
      </section>
      <section class="panel" style="overflow:hidden">
        <div class="toolbar"><span class="tool active">页面预览</span><span class="tool">实例 6</span><span class="spacer"></span><span class="tool">适应窗口</span><span class="tool">100%</span></div>
        <div style="height:calc(100% - 49px);padding:14px;background:#f8f9fc">${thumb("P044 · LAYOUT PREVIEW", 2, "hero-image")}</div>
      </section>
      <section class="panel inspector">
        <div class="panel-header"><div><div class="panel-title">运行配置</div><div class="panel-sub">此页最终注入值</div></div>${status("可运行", "green")}</div>
        <div class="inspector-section"><div class="form-group"><label class="label">人物变体</label><div class="field">角色 A · 裙装 · 胸腰景</div></div><div class="form-group"><label class="label">工作流</label><div class="field">角色替换工作流 · v12</div></div></div>
        <div class="inspector-section"><label class="label">语义插槽</label><div class="kv"><span>角色提示词</span><strong>已绑定</strong></div><div class="kv"><span>角色 LoRA</span><strong>character_a.safetensors</strong></div><div class="kv"><span>LoRA 权重</span><strong>0.82</strong></div><div class="kv"><span>分辨率</span><strong>832 × 1216</strong></div><div class="kv"><span>候选数量</span><strong>6</strong></div></div>
        <div class="inspector-section">${button("打开工作流画布", "soft")}</div>
      </section>
    </div>
  </div>`;
}

function materialsPage() {
  const names = [
    ["胸腰景正面", "构图", "适合人物主体与轻量互动", "blue"],
    ["侧面双人构图", "构图", "明确前后关系与朝向", "blue"],
    ["放松微笑", "表情", "柔和视线与轻松表情", "green"],
    ["紧张回避", "表情", "垂落视线与轻微回避", "green"],
    ["浅水环境包", "场景包", "包含 12 张有序镜头", "purple"],
    ["室内夜间光线", "光线", "暖色侧光与低对比背景", "orange"],
    ["进入场景转场", "转场包", "4 张连续空间转换镜头", "cyan"],
    ["角色近景提示词", "提示词", "可绑定人物规格插槽", "purple"],
    ["竖向高图参数", "生成参数", "832 × 1216 · 默认采样", "orange"],
    ["水面互动镜头", "单页模板", "人物、环境、构图复合模板", "cyan"],
    ["远景环境镜头", "单页模板", "大留白与环境建立", "blue"],
    ["最终收束场景", "场景包", "8 张有序镜头", "purple"],
  ];
  const cards = names.map((n, i) => `<div class="material-card">${thumb(n[1], i)}<div class="material-card-body"><div style="display:flex;justify-content:space-between;gap:6px"><span class="material-name">${n[0]}</span>${chip(n[1], n[3])}</div><div class="material-desc">${n[2]}</div><div class="material-footer">${status(i % 4 === 0 ? "项目素材" : "已验证", i % 4 === 0 ? "orange" : "green")}<span style="margin-left:auto;color:#a2a9b7;font-size:8px">引用 ${i * 7 + 12}</span></div></div></div>`).join("");
  return `<div class="page-scroll">
    ${pageHeader("素材库", "管理可复用的分镜素材、单页模板、场景包和转场包。", button("导入素材") + button("新建素材", "primary"))}
    <div class="library-toolbar"><div class="search wide">⌕&nbsp;&nbsp;搜索名称、标签或描述</div><div class="tabs"><span class="tab active">全部</span><span class="tab">构图</span><span class="tab">表情</span><span class="tab">场景</span><span class="tab">光线</span><span class="tab">提示词</span><span class="tab">复合模板</span></div><div style="margin-left:auto">${button("筛选", "small")}</div></div>
    <div class="material-grid">${cards}</div>
  </div>`;
}

function materialDetailPage() {
  return `<div class="page-scroll">
    ${pageHeader("素材详情 · 浅水环境包", "复合模板 / 场景包 · 版本 6", button("复制为新素材") + button("保存修改", "primary"))}
    <div class="split-2" style="height:calc(100% - 79px)">
      <div class="split-left grid" style="grid-template-rows:220px minmax(0,1fr)">
        <section class="panel"><div class="panel-body" style="display:grid;grid-template-columns:250px minmax(0,1fr);gap:16px;height:100%">${thumb("SCENE PACK · 12 SHOTS", 5)}<div><div style="display:flex;gap:6px">${chip("场景包", "purple")}${status("已验证", "green")}${chip("12 页")}</div><h2 style="font-size:18px;margin:12px 0 7px">浅水环境包</h2><p style="margin:0;color:var(--muted);font-size:10px;line-height:1.65">包含从进入浅水区到场景收束的 12 张有序镜头。拖入剧本画布后自动展开，可逐页覆盖人物和构图。</p><div style="margin-top:15px">${button("在画布中预览", "soft")}</div></div></div></section>
        ${panel("模板页面", "拖动调整模板内部页序", `<div class="shot-list" style="padding:0">
          ${[1,2,3,4,5].map((i) => `<div class="shot-row"><span class="shot-no">${i}</span><span class="mini-thumb"></span><div><div class="shot-title">镜头 ${String(i).padStart(2,"0")} · ${["建立环境","进入水面","人物靠近","水面互动","场景收束"][i-1]}</div><div class="shot-desc">${["远景","全身","中景","胸腰景","半身"][i-1]} · 默认继承浅水环境与日间光线</div></div>${status("已验证","green")}<span style="color:#a4aab7;font-size:9px">⋮⋮</span></div>`).join("")}
        </div>`, button("展开全部 12 页", "small"))}
      </div>
      <div class="split-right">
        ${panel("素材属性", "修改后创建新版本", `<div class="form-group"><label class="label">名称</label><div class="field">浅水环境包</div></div><div class="form-group"><label class="label">说明</label><div class="field textarea">适合浅水区域的场景建立、人物互动与收束镜头。</div></div><div class="form-group"><label class="label">默认环境素材</label><div style="display:flex;flex-wrap:wrap;gap:5px">${chip("浅水区","cyan")}${chip("水面反光")}${chip("水波")}${chip("日间自然光","orange")}</div></div><div class="form-row"><div><label class="label">页面数</label><div class="field">12</div></div><div><label class="label">引用方式</label><div class="field">复制后独立</div></div></div><div class="empty-note">当前被 6 个项目、14 个场景引用。修改会创建版本 7，不影响已存在的画布页面。</div>`)}
      </div>
    </div>
  </div>`;
}

function charactersPage() {
  const chars = [
    ["角色 A", "主角", "3 个形象变体 · 5 个规格", "全部规格完整"],
    ["角色 B", "主要人物", "2 个形象变体 · 4 个规格", "缺少 1 项"],
    ["角色 C", "次要人物", "1 个形象变体 · 3 个规格", "全部规格完整"],
    ["角色 D", "客串人物", "1 个形象变体 · 2 个规格", "未绑定 LoRA"],
  ];
  const cards = chars.map((c, i) => `<div class="character-card">${thumb(c[0], i)}<div><div style="display:flex;align-items:center;justify-content:space-between">${chip(c[1], i === 0 ? "purple" : "blue")}${status(c[3], i === 1 ? "orange" : "green")}</div><div class="project-title">${c[0]}</div><div class="project-meta">${c[2]}<br>引用 ${42 + i * 17} 个分镜页</div><div class="spec-list"><div class="spec ready">全身 ✓</div><div class="spec ready">半身 ✓</div><div class="spec ${i === 1 ? "" : "ready"}">特写 ${i === 1 ? "!" : "✓"}</div></div><div style="margin-top:10px">${button("编辑人物", "small soft")}</div></div></div>`).join("");
  return `<div class="page-scroll">
    ${pageHeader("人物库", "为项目角色维护形象变体、景别规格和可选工作流参数。", button("从项目复制") + button("新建人物", "primary"))}
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:13px"><div class="tabs"><span class="tab active">项目人物</span><span class="tab">全局人物模板</span></div><div class="search wide">⌕ 搜索人物或形象变体</div><div style="margin-left:auto">${button("打开替换矩阵", "soft")}</div></div>
    <div class="grid cols-2">${cards}</div>
  </div>`;
}

function characterDatabasePage() {
  return `<div class="page-scroll">
    ${pageHeader("角色查询", "从全局角色库检索角色、作品系列与标签信息。", "")}
    <section class="panel character-database-panel">
      <div class="panel-header">
        <div><div class="panel-title">搜索角色</div><div class="panel-sub">输入关键词或选择作品系列进行筛选</div></div>
      </div>
      <div class="panel-body">
        <form class="character-database-search" id="character-database-search-form">
          <input class="modal-input" id="character-database-q" name="q" type="text" placeholder="搜索角色名 / 触发词 / 标签" autocomplete="off" />
          <select class="modal-input" id="character-database-copyright" name="copyright"><option value="">全部作品系列</option></select>
          <select class="modal-input" id="character-database-sort" name="sort">
            <option value="count_desc">标签数从多到少</option>
            <option value="count_asc">标签数从少到多</option>
            <option value="character_asc">角色名 A→Z</option>
            <option value="character_desc">角色名 Z→A</option>
          </select>
          <button class="btn primary" type="submit">搜索</button>
        </form>
        <div class="character-database-meta" id="character-database-meta"></div>
        <div class="character-database-results" id="character-database-results"></div>
      </div>
    </section>
  </div>`;
}

function characterMatrixPage() {
  const rows = [
    ["角色 A · 裙装", "已填写", "已填写", "已填写", "已填写"],
    ["角色 A · 短裤", "已填写", "已填写", "已填写", "已填写"],
    ["角色 B · 默认", "已填写", "已填写", "缺少提示词", "已填写"],
    ["角色 C · 默认", "已填写", "已填写", "已填写", "未使用"],
  ];
  return `<div class="page-scroll">
    ${pageHeader("人物替换矩阵", "角色 × 形象变体 × 景别规格；生成前统一检查提示词与可选 LoRA。", button("批量粘贴") + button("检查缺失项") + button("保存矩阵", "primary"))}
    <div class="grid cols-4" style="margin-bottom:13px">${metric("项目角色","4","共 7 个形象变体")}${metric("规格单元","28","26 项已完成")}${metric("LoRA 绑定","18","10 项不需要")}${metric("准备度","93%","2 项需要处理")}</div>
    <div class="matrix">
      <div class="matrix-row"><div class="matrix-cell matrix-head">角色与形象变体</div><div class="matrix-cell matrix-head">全身</div><div class="matrix-cell matrix-head">半身</div><div class="matrix-cell matrix-head">特写</div><div class="matrix-cell matrix-head">自定义近景</div></div>
      ${rows.map((r, ri) => `<div class="matrix-row"><div class="matrix-cell"><strong style="font-size:10px">${r[0]}</strong><span style="color:#8e96a6;font-size:8px">${ri < 2 ? "character_a.safetensors · 0.82" : ri === 2 ? "character_b.safetensors · 0.74" : "仅提示词"}</span></div>${r.slice(1).map((v, ci) => `<div class="matrix-cell" style="${v.includes("缺少") ? "background:#fff9ef" : ""}"><div>${status(v, v.includes("缺少") ? "orange" : v === "未使用" ? "" : "green")}</div><span style="color:#8c94a5;font-size:8px">${v.includes("缺少") ? "点击补全" : ci === 0 ? "186 字符 · LoRA 已绑定" : "142 字符 · 继承默认"}</span></div>`).join("")}</div>`).join("")}
    </div>
    <div class="grid cols-2" style="margin-top:13px">
      ${panel("缺失项", "提交批次前必须解决", `<div class="mini-list"><div class="mini-list-item"><span class="mini-list-icon" style="color:#c17b2b;background:var(--orange-soft)">!</span><div class="mini-list-text">角色 B · 特写<div class="mini-list-sub">缺少角色提示词</div></div>${button("补全","small")}</div><div class="mini-list-item"><span class="mini-list-icon" style="color:#c17b2b;background:var(--orange-soft)">!</span><div class="mini-list-text">短裤分支 · P078<div class="mini-list-sub">工作流未绑定“角色 LoRA”插槽</div></div>${button("定位","small")}</div></div>`)}
      ${panel("批量规则", "变体值通过工作流语义插槽注入", `<div class="kv"><span>提示词注入</span><strong>角色提示词插槽</strong></div><div class="kv"><span>LoRA 名称</span><strong>角色 LoRA 插槽</strong></div><div class="kv"><span>LoRA 权重</span><strong>LoRA 权重插槽</strong></div><div class="kv"><span>基础模型</span><strong>使用项目默认</strong></div>`)}
    </div>
  </div>`;
}

function workflowMini(index) {
  return `<div class="wf-mini">
    <span class="wf-mini-node" style="left:14px;top:18px"></span>
    <span class="wf-mini-node" style="left:87px;top:${index % 2 ? 48 : 18}px"></span>
    <span class="wf-mini-node" style="left:160px;top:32px"></span>
    <span class="wf-mini-node" style="left:233px;top:${index % 3 ? 16 : 52}px"></span>
  </div>`;
}

function workflowsPage() {
  const wfs = [
    ["角色替换工作流", "v12", "26 节点 · 8 个语义插槽", "默认工作流"],
    ["高分辨率竖图", "v7", "31 节点 · 6 个语义插槽", "项目工作流"],
    ["快速构图测试", "v4", "14 节点 · 5 个语义插槽", "全局模板"],
    ["夜间光线增强", "v9", "34 节点 · 9 个语义插槽", "分支工作流"],
    ["双人物构图", "v6", "29 节点 · 11 个语义插槽", "项目工作流"],
    ["细节重绘流程", "v3", "21 节点 · 4 个语义插槽", "全局模板"],
  ];
  const cards = wfs.map((w, i) => `<div class="wf-card">${workflowMini(i)}<div style="display:flex;justify-content:space-between;align-items:center"><div class="material-name">${w[0]}</div>${chip(w[1], "blue")}</div><div class="material-desc">${w[2]}</div><div class="material-footer">${status(w[3], i === 0 ? "green" : i === 3 ? "purple" : "")}<span style="margin-left:auto;color:#a0a8b6;font-size:8px">今天 ${14 + i}:20</span></div></div>`).join("");
  return `<div class="page-scroll">
    ${pageHeader("工作流库", "管理 ComfyUI 工作流、版本、项目副本和语义插槽。", button("从图片提取") + button("导入 JSON") + button("新建工作流", "primary"))}
    <div class="library-toolbar"><div class="search wide">⌕ 搜索工作流、节点或插槽</div><div class="tabs"><span class="tab active">全部</span><span class="tab">项目</span><span class="tab">全局模板</span><span class="tab">最近使用</span></div><div style="margin-left:auto">${status("节点定义已同步","green")}</div></div>
    <div class="grid cols-3">${cards}</div>
  </div>`;
}

function workflowCanvasPage() {
  return `<div class="page-scroll">
    ${pageHeader("工作流画布 · 角色替换工作流", "版本 v12 · ComfyUI 节点已同步 · 节点位置由拓扑自动整理", button("导出 JSON") + button("保存新版本", "primary"))}
    <div class="three-pane" style="grid-template-columns:206px minmax(0,1fr) 274px;height:calc(100% - 79px)">
      <section class="panel"><div class="panel-header"><div><div class="panel-title">节点库</div><div class="panel-sub">标准节点与已安装自定义节点</div></div></div><div class="search" style="margin:10px">⌕ 搜索节点</div><div class="palette-list">
        <div class="palette-title">常用</div>
        ${[["模型加载","blue"],["LoRA 加载","purple"],["文本编码","green"],["KSampler","orange"],["空潜空间","cyan"],["VAE 解码","blue"],["保存图片","green"]].map((p)=>`<div class="palette-item"><span class="palette-swatch ${p[1]}"></span>${p[0]}<span style="margin-left:auto;color:#aab1bf">＋</span></div>`).join("")}
        <div class="palette-title">自定义节点 · 47</div>
        <div class="palette-item"><span class="palette-swatch purple"></span>Impact Pack<span style="margin-left:auto">${chip("12")}</span></div>
        <div class="palette-item"><span class="palette-swatch cyan"></span>IPAdapter Plus<span style="margin-left:auto">${chip("9")}</span></div>
      </div></section>
      <section class="panel" style="overflow:hidden"><div class="toolbar"><span class="tool">撤销</span><span class="tool">重做</span><span class="tool active">从左到右</span><span class="tool">聚焦路径</span><span class="spacer"></span><span class="tool">−</span><span class="tool">74%</span><span class="tool">＋</span><span class="tool">自动整理</span></div>
        <div class="canvas"><div class="workflow-stage">
          <div class="wf-lane" style="left:0"><span class="wf-lane-title">01 · 输入与模型</span></div>
          <div class="wf-lane" style="left:232px"><span class="wf-lane-title">02 · 人物与条件</span></div>
          <div class="wf-lane" style="left:464px"><span class="wf-lane-title">03 · 采样</span></div>
          <div class="wf-lane" style="left:696px"><span class="wf-lane-title">04 · 输出</span></div>
          <svg class="wf-connections" viewBox="0 0 900 560" preserveAspectRatio="none">
            <path d="M 184 143 C 215 143, 218 116, 244 116"></path>
            <path class="green" d="M 184 278 C 224 278, 205 222, 244 222"></path>
            <path d="M 416 144 C 448 144, 445 191, 476 191"></path>
            <path class="green" d="M 416 267 C 451 267, 448 232, 476 232"></path>
            <path class="orange" d="M 648 210 C 679 210, 681 168, 708 168"></path>
            <path d="M 648 246 C 679 246, 681 314, 708 314"></path>
          </svg>
          <div class="node-card" style="left:14px;top:68px"><div class="node-head"><i class="node-type"></i>Checkpoint Loader</div><div class="node-body"><div class="node-field"><span class="node-field-name">模型</span><span class="node-value">illustrious_v12.safetensors</span></div><div class="node-field"><span class="node-field-name">VAE</span><span class="node-value">自动</span></div></div><i class="node-port out" style="top:70px"></i></div>
          <div class="node-card" style="left:14px;top:214px"><div class="node-head"><i class="node-type green"></i>正向提示词</div><div class="node-body"><div class="slot-badge">◇ 正向提示词插槽</div><div class="node-field"><span class="node-field-name">文本</span><span class="node-value">由分镜页编译注入</span></div></div><i class="node-port out" style="top:63px"></i></div>
          <div class="node-card selected" style="left:246px;top:72px"><div class="node-head"><i class="node-type purple"></i>角色 LoRA</div><div class="node-body"><div class="node-field"><span class="node-field-name">名称</span><span class="slot-badge">◇ 角色 LoRA</span></div><div class="node-field"><span class="node-field-name">权重</span><span class="slot-badge">◇ LoRA 权重</span></div><div class="node-field"><span class="node-field-name">模型</span><span class="node-value">来自上游</span></div></div><i class="node-port in" style="top:67px"></i><i class="node-port out" style="top:72px"></i></div>
          <div class="node-card" style="left:246px;top:224px"><div class="node-head"><i class="node-type green"></i>CLIP Text Encode</div><div class="node-body"><div class="node-field"><span class="node-field-name">文本</span><span class="node-value">角色 + 场景 + 构图</span></div><div class="node-field"><span class="node-field-name">CLIP</span><span class="node-value">来自角色 LoRA</span></div></div><i class="node-port in" style="top:54px"></i><i class="node-port out" style="top:58px"></i></div>
          <div class="node-card" style="left:478px;top:144px"><div class="node-head"><i class="node-type orange"></i>KSampler</div><div class="node-body"><div class="node-field"><span class="node-field-name">种子</span><span class="slot-badge">◇ 种子</span></div><div class="node-field"><span class="node-field-name">步数</span><span class="node-value">28</span></div><div class="node-field"><span class="node-field-name">CFG</span><span class="node-value">5.5</span></div><div class="node-field"><span class="node-field-name">采样器</span><span class="node-value">euler_ancestral</span></div></div><i class="node-port in" style="top:65px"></i><i class="node-port in" style="top:105px"></i><i class="node-port out" style="top:90px"></i></div>
          <div class="node-card" style="left:710px;top:108px"><div class="node-head"><i class="node-type green"></i>Save Image</div><div class="node-body"><div class="node-field"><span class="node-field-name">前缀</span><span class="slot-badge">◇ 输出前缀</span></div><div class="node-field"><span class="node-field-name">格式</span><span class="node-value">PNG</span></div></div><i class="node-port in" style="top:61px"></i></div>
          <div class="node-card" style="left:710px;top:263px"><div class="node-head"><i class="node-type cyan"></i>Metadata Writer</div><div class="node-body"><div class="node-field"><span class="node-field-name">项目</span><span class="node-value">自动注入</span></div><div class="node-field"><span class="node-field-name">分镜页</span><span class="node-value">自动注入</span></div></div><i class="node-port in" style="top:52px"></i></div>
        </div></div>
      </section>
      <section class="panel inspector"><div class="panel-header"><div><div class="panel-title">角色 LoRA</div><div class="panel-sub">LoraLoader · 节点 12</div></div>${status("有效","green")}</div>
        <div class="inspector-section"><label class="label">节点位置</label><div class="field">第 2 列 · 人物与条件</div><div class="empty-note" style="margin-top:8px">节点不能自由拖动。使用“前移、后移、换列”调整拓扑位置。</div></div>
        <div class="inspector-section"><label class="label">LoRA 名称</label><div class="field">◇ 角色 LoRA</div><div style="height:8px"></div><label class="label">模型权重</label><div class="field">◇ LoRA 权重</div></div>
        <div class="inspector-section"><label class="label">语义插槽来源</label><div class="mini-list-item"><span class="mini-list-icon">CH</span><div class="mini-list-text">项目人物矩阵<div class="mini-list-sub">角色 × 变体 × 规格</div></div></div></div>
        <div class="inspector-section" style="display:flex;gap:7px">${button("前移","small")}${button("后移","small")}${button("换列","small soft")}</div>
      </section>
    </div>
  </div>`;
}

function batchPage() {
  const tree = [
    ["01", "开场章节", "18 页", true],
    ["02", "公共沙滩区", "38 页", true],
    ["03", "浅水区 · 裙装", "42 页", true],
    ["03B", "浅水区 · 短裤", "42 页", true],
    ["04", "室内夜景", "64 页", false],
  ].map((t) => `<div class="mini-list-item" style="${t[3] ? "background:var(--blue-soft)" : ""}"><span class="mini-list-icon">${t[3] ? "✓" : ""}</span><div class="mini-list-text">${t[1]}<div class="mini-list-sub">${t[2]}</div></div>${status(t[3] ? "已选择" : "未选择", t[3] ? "blue" : "")}</div>`).join("");
  return `<div class="page-scroll">
    ${pageHeader("批量配置", "从已编译的跑图列表选择页面、分支和每页生成实例数。", button("保存为预设") + button("提交 140 个任务", "primary"))}
    <div class="grid cols-4" style="margin-bottom:13px">${metric("选择页面","140","跨 4 个场景")}${metric("每页实例","6","允许逐页覆盖")}${metric("预计图片","840","约 14.8 GB")}${metric("预计耗时","2h 36m","基于最近速度")}</div>
    <div class="split-2" style="height:calc(100% - 188px)">
      <div class="split-left grid cols-2">
        ${panel("生成范围", "按章节、场景和分支选择", `<div class="mini-list">${tree}</div>`)}
        ${panel("生成策略", "项目默认可被单页覆盖", `<div class="form-row"><div><label class="label">每页实例数</label><div class="field">6</div></div><div><label class="label">并发提交</label><div class="field">1</div></div></div><div class="form-group"><label class="label">种子策略</label><div class="field">每个实例随机种子</div></div><div class="form-group"><label class="label">跳过规则</label><div class="field">已采用 2 张及以上的页面</div></div><div class="form-group"><label class="label">失败策略</label><div class="field">自动重试 1 次，之后暂停该页</div></div>`)}
      </div>
      <div class="split-right">
        ${panel("提交前检查", "3 类校验全部通过", `<div class="mini-list"><div class="mini-list-item"><span class="mini-list-icon" style="color:#168f6c;background:var(--green-soft)">✓</span><div class="mini-list-text">工作流与节点<div class="mini-list-sub">v12 · 26 节点 · 节点定义有效</div></div></div><div class="mini-list-item"><span class="mini-list-icon" style="color:#168f6c;background:var(--green-soft)">✓</span><div class="mini-list-text">人物语义插槽<div class="mini-list-sub">所有所需提示词与 LoRA 已绑定</div></div></div><div class="mini-list-item"><span class="mini-list-icon" style="color:#168f6c;background:var(--green-soft)">✓</span><div class="mini-list-text">ComfyUI 连接<div class="mini-list-sub">192.168.3.5:8188 · 12 ms</div></div></div></div><div class="empty-note" style="margin-top:12px">提交只创建 Atelier 任务队列。系统会逐项注入语义插槽，再发送至 ComfyUI。</div>`, button("查看 140 条运行项","small"))}
      </div>
    </div>
  </div>`;
}

function tasksPage() {
  const tasks = [
    ["#B-0288", "海边度假篇 · 短裤分支", "运行中", "P076–P082", "38 / 42", 72, "blue"],
    ["#B-0287", "海边度假篇 · 裙装主线", "已完成", "P042–P075", "204 / 204", 100, "green"],
    ["#B-0286", "礼服剧场 · 主线", "排队中", "P001–P060", "0 / 360", 0, "orange"],
    ["#B-0285", "夏日角色集 · 默认", "部分失败", "P020–P036", "94 / 102", 92, "red"],
    ["#B-0284", "室内光影研究", "已暂停", "P001–P064", "156 / 384", 41, ""],
    ["#B-0283", "礼服剧场 · 分支 B", "已完成", "P061–P112", "312 / 312", 100, "green"],
  ];
  return `<div class="page-scroll">
    ${pageHeader("任务中心", "管理排队、运行、失败和完成的 ComfyUI 生成任务。", button("暂停队列") + button("新建批次", "primary"))}
    <div class="grid cols-4" style="margin-bottom:13px">${metric("运行中","18","当前节点 KSampler")}${metric("排队","402","预计 2 小时 51 分")}${metric("今日完成","1,248","成功率 98.7%","+12%")}${metric("失败待处理","8","集中在 2 个页面")}</div>
    <section class="panel" style="height:calc(100% - 188px);overflow:hidden"><div class="panel-header"><div><div class="panel-title">生成批次</div><div class="panel-sub">实时进度通过服务端事件更新</div></div><div class="panel-header-actions"><div class="search wide">⌕ 搜索批次或项目</div><div class="tabs"><span class="tab active">全部</span><span class="tab">运行中</span><span class="tab">失败</span></div></div></div>
      <table class="table"><thead><tr><th>批次</th><th>项目与分支</th><th>状态</th><th>页面范围</th><th>图片</th><th style="width:210px">进度</th><th>操作</th></tr></thead><tbody>${tasks.map((t) => `<tr><td class="task-name">${t[0]}</td><td>${t[1]}</td><td>${status(t[2],t[6])}</td><td>${t[3]}</td><td>${t[4]}</td><td>${progress(t[5],t[5]===100?"green":"")}<div style="margin-top:4px;color:#9aa1b0">${t[5]}%</div></td><td><button class="btn small">${t[2]==="部分失败"?"重试失败项":"查看"}</button></td></tr>`).join("")}</tbody></table>
    </section>
  </div>`;
}

function reviewPage() {
  const pageList = [42,43,44,45,46,47,48,49].map((n, i) => `<div class="review-page ${i === 2 ? "active" : ""}"><span class="shot-no">${n}</span><div><strong>P${String(n).padStart(3,"0")}</strong><div style="margin-top:3px;color:#8d95a5">${i === 2 ? "2 张已采用" : i < 2 ? "审片完成" : "待审片 · 6 张"}</div></div></div>`).join("");
  const candidates = Array.from({length:6},(_,i)=>`<div class="candidate ${i===1||i===4?"adopted":""}"><span class="candidate-index">0${i+1}</span>${i===1||i===4?'<span class="candidate-check">✓</span>':""}${thumb(`SEED ${582941+i*137}`,i+2)}<div class="candidate-meta"><span>${i===1||i===4?"已采用":"候选"}</span><span>${832}×${1216}</span></div></div>`).join("");
  return `<div class="page-scroll">
    ${pageHeader("项目审片图库", "海边度假篇 / 裙装主线 · 按分镜页审核候选，可同时采用多张。", button("只看待审片") + button("生成更多", "primary"))}
    <div class="review-layout" style="height:calc(100% - 79px)">
      <section class="panel" style="overflow:hidden"><div class="panel-header"><div><div class="panel-title">分镜页</div><div class="panel-sub">136 / 200 已完成</div></div></div><div class="review-page-list">${pageList}</div></section>
      <section class="panel" style="overflow:hidden"><div class="toolbar"><span class="tool active">P044 · 水面互动</span><span class="tool">6 个实例</span><span class="spacer"></span><span class="tool">对比</span><span class="tool">按种子</span><span class="tool">信息</span></div><div class="candidate-grid">${candidates}</div></section>
      <section class="panel" style="overflow:hidden"><div class="panel-header"><div><div class="panel-title">本页采用</div><div class="panel-sub">2 张 · 拖动调整页内顺序</div></div>${status("已保存","green")}</div><div class="adopt-list"><div class="adopt-item"><span class="drag-handle">⋮⋮</span><span class="adopt-thumb"></span><div><strong style="font-size:9px">P044-A</strong><div class="mini-list-sub">实例 02 · seed 583078</div></div></div><div class="adopt-item"><span class="drag-handle">⋮⋮</span><span class="adopt-thumb"></span><div><strong style="font-size:9px">P044-B</strong><div class="mini-list-sub">实例 05 · seed 583489</div></div></div><div class="empty-note">采用多张后，它们会按照这里的顺序进入最终作品装配页。</div><div style="margin-top:12px">${button("标记本页完成","primary")}</div></div></section>
    </div>
  </div>`;
}

function assemblyPage() {
  const groups = [
    ["P042",1],["P043",1],["P044",2],["P045",1],["P046",2],["P047",1],
  ];
  const content = groups.map((g, gi) => `<div class="sequence-group ${g[1]===2?"wide":""}"><div class="sequence-group-title"><span>${g[0]} · ${g[1]} 张采用</span><span>⋮⋮</span></div><div class="sequence-images">${Array.from({length:g[1]},(_,i)=>`<div class="sequence-image"><span class="sequence-order">${String(groups.slice(0,gi).reduce((s,x)=>s+x[1],0)+i+1).padStart(3,"0")}</span>${thumb(`${g[0]}-${String.fromCharCode(65+i)}`,gi+i)}</div>`).join("")}</div></div>`).join("");
  return `<div class="page-scroll">
    ${pageHeader("最终作品装配", "裙装成片 v3 · 236 张图片 · 默认按分镜页与页内采用顺序展开", button("恢复默认顺序") + button("创建新版本") + button("保存排序", "primary"))}
    <div class="grid cols-4" style="margin-bottom:12px">${metric("最终图片","236","来自 184 个分镜页")}${metric("多图页面","38","每页 2–4 张采用")}${metric("跨页调整","12","均保留来源追踪")}${metric("成片版本","3","裙装、短裤、发布")}</div>
    <section class="panel assembly"><div class="toolbar"><div class="tabs"><span class="tab active">裙装成片 v3</span><span class="tab">短裤成片 v2</span><span class="tab">发布版 v1</span></div><span class="spacer"></span><span class="tool">紧凑视图</span><span class="tool active">图片视图</span><span class="tool">来源信息</span><span class="tool">−</span><span class="tool">72%</span><span class="tool">＋</span></div><div class="sequence-strip">${content}</div></section>
  </div>`;
}

function libraryPage() {
  const items = Array.from({length:28},(_,i)=>`<div class="library-item">${thumb(`AT-${String(1024836-i).padStart(7,"0")}`,i)}<div class="library-footer">${i%5===0?"已采用 · ":"候选 · "}海边度假篇 · P${String(42+i).padStart(3,"0")}</div></div>`).join("");
  return `<div class="page-scroll">
    ${pageHeader("全局图库", "1,024,836 张图片已建立索引 · 列表仅加载可视区域缩略图。", button("索引状态") + button("批量操作"))}
    <div class="library-toolbar"><div class="search wide" style="min-width:360px">⌕&nbsp;&nbsp;搜索项目、提示词、模型、种子或标签</div><div class="tabs"><span class="tab active">全部</span><span class="tab">已采用</span><span class="tab">候选</span><span class="tab">淘汰</span></div><button class="btn small">项目</button><button class="btn small">工作流</button><button class="btn small">时间</button><div style="margin-left:auto;color:#8a93a4;font-size:9px">游标批次 100 · 虚拟网格</div></div>
    <div class="library-grid">${items}</div>
  </div>`;
}

function imageDetailPage() {
  return `<div class="page-scroll">
    ${pageHeader("图片详情 · AT-1024812", "项目图片 / 海边度假篇 / P044 / 实例 02", button("上一张") + button("下一张") + button("设为采用", "primary"))}
    <div class="detail-layout" style="height:calc(100% - 79px)">
      <section class="panel" style="padding:13px">${thumb("ORIGINAL · 832 × 1216",3,"hero-image")}<div class="hero-tools">${button("适应窗口","small")}${button("100%","small")}${button("对比","small")}${button("下载原图","small")}</div></section>
      <section class="panel" style="overflow:hidden"><div class="panel-header"><div><div class="panel-title">图片信息</div><div class="panel-sub">完整来源与生成快照</div></div>${status("已采用","green")}</div><div class="meta-list">
        <div class="meta-row"><span class="meta-key">来源分镜</span><span class="meta-value">P044 · 水面互动</span></div>
        <div class="meta-row"><span class="meta-key">分支路径</span><span class="meta-value">裙装主线 / 浅水区</span></div>
        <div class="meta-row"><span class="meta-key">工作流</span><span class="meta-value">角色替换工作流 v12</span></div>
        <div class="meta-row"><span class="meta-key">人物规格</span><span class="meta-value">角色 A · 裙装 · 胸腰景</span></div>
        <div class="meta-row"><span class="meta-key">模型</span><span class="meta-value">illustrious_v12.safetensors</span></div>
        <div class="meta-row"><span class="meta-key">角色 LoRA</span><span class="meta-value">character_a.safetensors · 0.82</span></div>
        <div class="meta-row"><span class="meta-key">种子</span><span class="meta-value">583078</span></div>
        <div class="meta-row"><span class="meta-key">参数</span><span class="meta-value">28 steps · CFG 5.5 · euler_ancestral</span></div>
        <div class="meta-row"><span class="meta-key">文件</span><span class="meta-value">832 × 1216 · PNG · 2.18 MB</span></div>
        <div class="meta-row"><span class="meta-key">内容哈希</span><span class="meta-value">9fa2d4b8…7c11</span></div>
        <div class="form-group" style="margin-top:12px"><label class="label">最终提示词快照</label><div class="field textarea">quality preset, character slot values, composition pack, scene pack, lighting preset…</div></div>
      </div></section>
    </div>
  </div>`;
}

function exportPage() {
  const exports = [
    ["裙装成片 v3","236 张 · PNG · 保留元数据","准备就绪","green"],
    ["短裤成片 v2","214 张 · PNG · 保留元数据","准备就绪","green"],
    ["发布版 v1","180 张 · JPEG · 移除工作流元数据","需要更新","orange"],
  ];
  return `<div class="page-scroll">
    ${pageHeader("导出中心", "从最终作品版本生成编号文件、清单和可复用导出记录。", button("管理预设") + button("新建导出", "primary"))}
    <div class="split-2" style="height:calc(100% - 79px)">
      <div class="split-left grid" style="grid-template-rows:auto 1fr">
        ${panel("最终版本", "选择一个已装配的版本", `<div class="mini-list">${exports.map((e,i)=>`<div class="export-card"><span class="export-icon">0${i+1}</span><div><div class="setting-title">${e[0]}</div><div class="setting-desc">${e[1]}</div></div>${status(e[2],e[3])}</div>`).join("")}</div>`)}
        ${panel("最近导出", "导出不会改变采用状态或原文件", `<table class="table"><thead><tr><th>导出记录</th><th>版本</th><th>格式</th><th>状态</th><th>时间</th></tr></thead><tbody><tr><td class="task-name">EX-0084</td><td>裙装成片 v2</td><td>PNG + JSON</td><td>${status("已完成","green")}</td><td>昨天 23:18</td></tr><tr><td class="task-name">EX-0083</td><td>短裤成片 v1</td><td>JPEG</td><td>${status("已完成","green")}</td><td>昨天 21:42</td></tr><tr><td class="task-name">EX-0082</td><td>发布版草稿</td><td>JPEG + CSV</td><td>${status("已取消","")}</td><td>7 月 25 日</td></tr></tbody></table>`)}
      </div>
      <div class="split-right">${panel("导出配置", "裙装成片 v3", `<div class="form-group"><label class="label">导出预设</label><div class="field">原始 PNG · 保留元数据</div></div><div class="form-group"><label class="label">目标目录</label><div class="field">D:\\Atelier Exports\\海边度假篇\\裙装-v3</div></div><div class="form-row"><div><label class="label">文件名</label><div class="field">001, 002, 003…</div></div><div><label class="label">格式</label><div class="field">PNG</div></div></div><div class="kv"><span>复制工作流元数据</span><strong>是</strong></div><div class="kv"><span>生成 JSON 清单</span><strong>是</strong></div><div class="kv"><span>生成 CSV 清单</span><strong>否</strong></div><div class="kv"><span>冲突处理</span><strong>创建新目录</strong></div><div style="margin-top:15px">${button("开始导出 236 张","primary")}</div><div class="empty-note" style="margin-top:10px">每张导出图片仍保留来源分镜页、原图片 ID 和最终顺序。</div>`)}
      </div>
    </div>
  </div>`;
}

function settingsPage() {
  return `<div class="page-scroll">
    ${pageHeader("设置", "管理生产数据、测试数据和运行环境。", '<button class="btn soft" data-api-action="verify-isolation">验证数据库隔离</button>' + button("保存设置", "primary"))}
    <section class="panel database-settings">
      <div class="panel-header">
        <div><div class="panel-title">数据库环境</div><div class="panel-sub">两套数据库使用不同物理文件；普通启动始终默认进入生产库。</div></div>
        <div id="database-safety-status">${status("正在检查","orange")}</div>
      </div>
      <div class="database-guide">
        <span class="database-guide-icon">i</span>
        <div><strong>你平时只使用生产数据库。</strong><br>测试数据库供开发验证和自动化测试使用，测试进程会锁定到测试库，无法切换到生产库。</div>
      </div>
      <div class="database-grid">
        <article class="database-card production" id="database-production">
          <div class="database-card-top">
            <span class="database-symbol">P</span>
            <div><div class="database-name">生产数据库</div><div class="database-purpose">你的真实项目、素材索引和作品数据</div></div>
            <span class="status blue database-state">等待连接</span>
          </div>
          <div class="database-path">正在读取数据库路径…</div>
          <div class="database-facts">
            <div><span>存储格式</span><strong class="database-journal">SQLite WAL</strong></div>
            <div><span>当前大小</span><strong class="database-size">—</strong></div>
            <div><span>测试记录</span><strong class="database-events">—</strong></div>
          </div>
          <button class="btn primary database-action" data-api-action="activate-database" data-environment="production">使用生产数据库</button>
        </article>
        <article class="database-card test" id="database-test">
          <div class="database-card-top">
            <span class="database-symbol">T</span>
            <div><div class="database-name">测试数据库</div><div class="database-purpose">开发检查、自动化测试和可清空的演示数据</div></div>
            <span class="status orange database-state">等待连接</span>
          </div>
          <div class="database-path">正在读取数据库路径…</div>
          <div class="database-facts">
            <div><span>存储格式</span><strong class="database-journal">SQLite WAL</strong></div>
            <div><span>当前大小</span><strong class="database-size">—</strong></div>
            <div><span>测试记录</span><strong class="database-events">—</strong></div>
          </div>
          <button class="btn soft database-action" data-api-action="activate-database" data-environment="test">切换到测试数据库</button>
        </article>
      </div>
      <div class="database-result" id="database-result">尚未执行隔离验证。</div>
    </section>
    <div class="grid cols-3">
      <div class="setting-card"><div style="display:flex;justify-content:space-between">${status("尚未检测","orange")}${chip("默认实例","blue")}</div><div class="setting-title" style="margin-top:12px">ComfyUI 主实例</div><div class="setting-desc">运行生成任务并提供节点定义。</div><div class="setting-value">192.168.3.5:8188</div><div class="kv"><span>延迟</span><strong>连接后读取</strong></div><div class="kv"><span>GPU</span><strong>连接后读取</strong></div><div class="kv"><span>节点</span><strong>连接后读取</strong></div></div>
      <div class="setting-card"><div style="display:flex;justify-content:space-between">${status("已隔离","green")}${chip("双数据库")}</div><div class="setting-title" style="margin-top:12px">数据安全策略</div><div class="setting-desc">生产数据与测试写入使用不同数据库文件。</div><div class="setting-value">Production + Test</div><div class="kv"><span>普通启动</span><strong>生产数据库</strong></div><div class="kv"><span>测试启动</span><strong>锁定测试数据库</strong></div><div class="kv"><span>跨库写入</span><strong>禁止</strong></div></div>
      <div class="setting-card"><div style="display:flex;justify-content:space-between">${status("未配置","orange")}${chip("双层缩略图")}</div><div class="setting-title" style="margin-top:12px">图库缓存</div><div class="setting-desc">256px 列表缩略图与 640px 快速预览。</div><div class="setting-value">尚未设置缓存目录</div><div class="kv"><span>缓存占用</span><strong>0 KB</strong></div><div class="kv"><span>待生成</span><strong>0</strong></div><div class="kv"><span>浏览器策略</span><strong>长缓存 + ETag</strong></div></div>
    </div>
    <div class="grid cols-2" style="margin-top:14px">
      ${panel("应用与单端口启动", "正式环境由 FastAPI 托管前端", `<div class="form-row"><div><label class="label">监听地址</label><div class="field">0.0.0.0</div></div><div><label class="label">应用端口</label><div class="field">8110</div></div></div><div class="kv"><span>前端与 API</span><strong>同一端口</strong></div><div class="kv"><span>健康接口</span><strong>/api/health</strong></div><div class="kv"><span>启动脚本</span><strong>start.bat</strong></div><div class="empty-note" style="margin-top:10px">启动时只终止能够通过项目绝对路径和启动标识确认的 Atelier 旧进程。其他程序占用端口时停止启动。</div>`)}
      ${panel("性能与索引", "百万级图片模式已启用", `<div class="kv"><span>列表分页</span><strong>游标 · 每批 100</strong></div><div class="kv"><span>前端网格</span><strong>二维虚拟化</strong></div><div class="kv"><span>原图加载</span><strong>仅详情页</strong></div><div class="kv"><span>提示词搜索</span><strong>SQLite FTS5</strong></div><div class="kv"><span>重复检测</span><strong>SHA-256 + pHash</strong></div><div style="margin-top:13px;display:flex;gap:8px">${button("重建缺失缩略图","small")}${button("检查索引","small")}${button("清理软删除","small danger-soft")}</div>`)}
    </div>
  </div>`;
}

const renderers = {
  projects: projectsPage,
  overview: overviewPage,
  "story-canvas": storyCanvasPage,
  "scene-editor": sceneEditorPage,
  "shot-inspector": shotInspectorPage,
  materials: materialsPage,
  "material-detail": materialDetailPage,
  characters: charactersPage,
  "character-database": characterDatabasePage,
  "character-matrix": characterMatrixPage,
  workflows: workflowsPage,
  "workflow-canvas": workflowCanvasPage,
  batch: batchPage,
  tasks: tasksPage,
  review: reviewPage,
  assembly: assemblyPage,
  library: libraryPage,
  "image-detail": imageDetailPage,
  export: exportPage,
  settings: settingsPage,
};

document.getElementById("app").innerHTML = shell(renderers[current]());
document.querySelectorAll("[data-page]").forEach((element) => {
  element.addEventListener("click", () => {
    navigateTo(element.dataset.page);
  });
});

function navigateTo(page) {
  const nextParams = new URLSearchParams();
  nextParams.set("page", page);
  const projectId = new URLSearchParams(location.search).get("project");
  if (projectId) nextParams.set("project", projectId);
  location.search = `?${nextParams.toString()}`;
}

function showToast(message) {
  let toast = document.querySelector(".demo-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.className = "demo-toast";
    toast.innerHTML = '<span class="demo-toast-check">✓</span><span class="demo-toast-text"></span>';
    document.body.appendChild(toast);
  }
  toast.querySelector(".demo-toast-text").textContent = message;
  toast.classList.remove("show");
  window.clearTimeout(showToast.timer);
  requestAnimationFrame(() => toast.classList.add("show"));
  showToast.timer = window.setTimeout(() => toast.classList.remove("show"), 2200);
}

const buttonRoutes = new Map([
  ["打开剧本画布", "story-canvas"],
  ["返回剧本画布", "story-canvas"],
  ["打开工作流画布", "workflow-canvas"],
  ["打开替换矩阵", "character-matrix"],
  ["新建批次", "batch"],
  ["提交 140 个任务", "tasks"],
  ["生成更多", "batch"],
  ["新建导出", "export"],
]);

document.querySelectorAll(".project-card").forEach((card) => {
  card.tabIndex = 0;
  card.setAttribute("role", "button");
  card.addEventListener("click", () => navigateTo("overview"));
  card.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") navigateTo("overview");
  });
});

document.querySelectorAll(".tabs").forEach((tabs) => {
  tabs.addEventListener("click", (event) => {
    const tab = event.target.closest(".tab");
    if (!tab) return;
    tabs.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
    tab.classList.add("active");
    showToast(`已切换到「${tab.textContent.trim()}」`);
  });
});

document.querySelectorAll(".toolbar").forEach((toolbar) => {
  toolbar.addEventListener("click", (event) => {
    const tool = event.target.closest(".tool");
    if (!tool || ["−", "＋"].includes(tool.textContent.trim())) return;
    const tools = [...toolbar.querySelectorAll(".tool")];
    const text = tool.textContent.trim();
    if (["主线", "裙装 A", "短裤 B", "夜间 C", "紧凑视图", "图片视图", "来源信息"].includes(text)) {
      tools.forEach((item) => {
        if (["主线", "裙装 A", "短裤 B", "夜间 C"].includes(text) ===
            ["主线", "裙装 A", "短裤 B", "夜间 C"].includes(item.textContent.trim())) {
          item.classList.remove("active");
        }
      });
      tool.classList.add("active");
    }
    showToast(`「${text}」视图已更新`);
  });
});

document.querySelectorAll(".palette-item").forEach((item) => {
  item.tabIndex = 0;
  item.addEventListener("click", () => {
    const name = item.textContent.replace("⋮⋮", "").trim();
    showToast(`已将「${name}」加入画布待放置区`);
  });
});

document.querySelectorAll(".story-block").forEach((block) => {
  block.tabIndex = 0;
  block.addEventListener("click", () => {
    document.querySelectorAll(".story-block").forEach((item) => item.classList.remove("active"));
    block.classList.add("active");
    const title = block.querySelector(".block-title")?.textContent.trim() || "结构块";
    const inspector = document.querySelector(".three-pane > .inspector");
    if (inspector) {
      const inspectorTitle = inspector.querySelector(".panel-title");
      const inspectorSub = inspector.querySelector(".panel-sub");
      if (inspectorTitle) inspectorTitle.textContent = title;
      if (inspectorSub) inspectorSub.textContent = `${block.querySelector(".block-kicker")?.textContent.trim() || "结构块"} · 当前选中`;
    }
    showToast(`已选中「${title}」`);
  });
});

document.querySelectorAll(".node-card").forEach((node) => {
  node.tabIndex = 0;
  node.addEventListener("click", () => {
    document.querySelectorAll(".node-card").forEach((item) => item.classList.remove("selected"));
    node.classList.add("selected");
    showToast(`已选中节点「${node.querySelector(".node-head")?.textContent.trim() || "未命名节点"}」`);
  });
});

document.querySelectorAll(".review-page").forEach((page) => {
  page.tabIndex = 0;
  page.addEventListener("click", () => {
    document.querySelectorAll(".review-page").forEach((item) => item.classList.remove("active"));
    page.classList.add("active");
    showToast(`已打开 ${page.querySelector("strong")?.textContent.trim() || "分镜页"}`);
  });
});

document.querySelectorAll(".candidate").forEach((candidate) => {
  candidate.tabIndex = 0;
  candidate.addEventListener("click", () => {
    const adopted = candidate.classList.toggle("adopted");
    let check = candidate.querySelector(".candidate-check");
    if (adopted && !check) {
      check = document.createElement("span");
      check.className = "candidate-check";
      check.textContent = "✓";
      candidate.appendChild(check);
    } else if (!adopted && check) {
      check.remove();
    }
    const state = candidate.querySelector(".candidate-meta span");
    if (state) state.textContent = adopted ? "已采用" : "候选";
    const adoptedCount = document.querySelectorAll(".candidate.adopted").length;
    const summary = document.querySelector(".review-layout > section:last-child .panel-sub");
    if (summary) summary.textContent = `${adoptedCount} 张 · 拖动调整页内顺序`;
    showToast(adopted ? "已采用该图片实例" : "已取消采用该图片实例");
  });
});

function renumberSequence() {
  let order = 1;
  document.querySelectorAll(".sequence-strip .sequence-image").forEach((image) => {
    const label = image.querySelector(".sequence-order");
    if (label) label.textContent = String(order++).padStart(3, "0");
  });
}

let draggedSequence = null;
document.querySelectorAll(".sequence-group").forEach((group) => {
  group.draggable = true;
  group.tabIndex = 0;
  group.addEventListener("dragstart", () => {
    draggedSequence = group;
    group.classList.add("dragging");
  });
  group.addEventListener("dragend", () => {
    group.classList.remove("dragging");
    draggedSequence = null;
  });
  group.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
    event.preventDefault();
    const strip = group.parentElement;
    if (event.key === "ArrowLeft" && group.previousElementSibling) {
      strip.insertBefore(group, group.previousElementSibling);
    }
    if (event.key === "ArrowRight" && group.nextElementSibling) {
      strip.insertBefore(group.nextElementSibling, group);
    }
    renumberSequence();
    group.focus();
    showToast("成片顺序已调整，来源页关系保持不变");
  });
});

const sequenceStrip = document.querySelector(".sequence-strip");
if (sequenceStrip) {
  sequenceStrip.addEventListener("dragover", (event) => {
    event.preventDefault();
    if (!draggedSequence) return;
    const target = event.target.closest(".sequence-group");
    if (!target || target === draggedSequence) return;
    const box = target.getBoundingClientRect();
    const after = event.clientX > box.left + box.width / 2;
    sequenceStrip.insertBefore(draggedSequence, after ? target.nextSibling : target);
  });
  sequenceStrip.addEventListener("drop", (event) => {
    event.preventDefault();
    renumberSequence();
    showToast("成片顺序已调整，来源页关系保持不变");
  });
}

document.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (
    !button ||
    button.type === "submit" ||
    button.closest("[data-page]") ||
    button.closest(".atelier-modal-backdrop") ||
    button.dataset.apiAction
  ) return;
  const label = button.textContent.trim();
  const route = buttonRoutes.get(label);
  if (route) {
    navigateTo(route);
    return;
  }
  showToast(`「${label}」操作已在演示状态中完成`);
});
