(function () {
  const environmentNames = {
    production: "生产数据库",
    test: "测试数据库",
  };

  // API 路径常量：新代码应使用 API.* 而非硬编码字符串，避免 URL 分散。
  // 现有调用逐步迁移，不强制一次性全部替换。
  const API = {
    health: "/api/health",
    developerProgress: "/api/developer/progress",
    databases: {
      settings: "/api/settings/databases",
      verifyIsolation: "/api/settings/databases/verify-isolation",
    },
    projects: "/api/projects",
    project: (id) => `/api/projects/${id}`,
    chapters: (projectId) => `/api/projects/${projectId}/chapters`,
    chapter: (id) => `/api/chapters/${id}`,
    largeScenes: (chapterId) => `/api/chapters/${chapterId}/large-scenes`,
    largeScene: (id) => `/api/large-scenes/${id}`,
    largeSceneMove: (id) => `/api/large-scenes/${id}/move`,
    smallScenes: (largeSceneId) => `/api/large-scenes/${largeSceneId}/small-scenes`,
    smallScene: (id) => `/api/small-scenes/${id}`,
    smallSceneMove: (id) => `/api/small-scenes/${id}/move`,
    smallSceneMaterials: (id) => `/api/small-scenes/${id}/materials`,
    smallSceneResources: (id) => `/api/small-scenes/${id}/resources`,
    smallSceneWorkspace: (id) => `/api/small-scenes/${id}/workspace`,
    smallScenePages: (id) => `/api/small-scenes/${id}/pages`,
    smallScenePagesOrder: (id) => `/api/small-scenes/${id}/pages/order`,
    smallSceneResourceLink: (linkId) => `/api/small-scene-resource-links/${linkId}`,
    shotPages: (smallSceneId) => `/api/small-scenes/${smallSceneId}/shot-pages`,
    shotPage: (id) => `/api/shot-pages/${id}`,
    shotPageMove: (id) => `/api/shot-pages/${id}/move`,
    scenePage: (id) => `/api/small-scene-pages/${id}`,
    scenePageMapping: (pageId, materialType) => `/api/small-scene-pages/${pageId}/mappings/${materialType}`,
    branches: (parentType, parentId) => `/api/${parentType}/${parentId}/branches`,
    branch: (id) => `/api/branches/${id}`,
    materials: "/api/materials",
    material: (id) => `/api/materials/${id}`,
    materialPreview: (id) => `/api/materials/${id}/preview`,
    materialThumbnail: (id) => `/api/materials/${id}/thumbnail`,
    materialPages: (id) => `/api/materials/${id}/pages`,
    materialPagesOrder: (id) => `/api/materials/${id}/pages/order`,
    materialPage: (id) => `/api/material-pages/${id}`,
    materialTags: "/api/material-tags",
    storyTree: (projectId) => `/api/projects/${projectId}/story-tree`,
    characters: "/api/characters",
    character: (id) => `/api/characters/${id}`,
    characterDatabase: {
      status: "/api/character-database/status",
    },
  };

  const emptyStateCopy = {
    projects: ["还没有项目", "生产数据库目前为空。创建第一个项目后，项目进度会显示在这里。", "新建项目"],
    overview: ["还没有项目概览", "先在项目中心创建或打开一个项目。", "返回项目中心"],
    "story-canvas": ["还没有剧本结构", "创建项目后，可以从章节和场景积木开始组织剧本。", "等待项目"],
    "scene-editor": ["还没有场景", "剧本画布中的场景会显示在这里。", "等待剧本"],
    "shot-inspector": ["还没有分镜页", "从剧本画布创建页面后，再配置单张图片内容。", "等待分镜"],
    materials: ["还没有素材", "人物、服装、场景和构图素材会保存在这里。", "添加素材"],
    "material-detail": ["没有可查看的素材", "先进入素材库添加素材。", "返回素材库"],
    characters: ["还没有人物", "创建人物后，可以为其管理多套形象规格。", "新建人物"],
    "character-matrix": ["还没有人物替换任务", "先创建人物、形象规格和分镜页。", "等待人物"],
    workflows: ["还没有工作流", "准备第一次跑图时，再从 ComfyUI 读取或创建工作流。", "连接 ComfyUI"],
    "workflow-canvas": ["还没有打开工作流", "从工作流库选择一个工作流进入画布。", "返回工作流库"],
    batch: ["还没有可生成页面", "项目分镜编译后，才能建立批量跑图任务。", "等待分镜"],
    tasks: ["还没有任务", "提交批量跑图后，运行状态会显示在这里。", "暂无任务"],
    review: ["还没有待审图片", "ComfyUI 生成的图片实例会按分镜页进入这里。", "等待生成"],
    assembly: ["还没有可装配图片", "在审片页采用图片后，才能排列最终作品。", "等待采用"],
    library: ["图库为空", "生产数据库尚未索引任何图片。", "添加图片"],
    "image-detail": ["没有可查看的图片", "先从项目生成或向图库添加图片。", "返回图库"],
    export: ["还没有可导出版本", "完成审片和作品装配后，再创建导出。", "等待成片"],
  };

  const projectScopedPages = new Set([
    "overview",
    "story-canvas",
    "scene-editor",
    "shot-inspector",
    "characters",
    "character-matrix",
    "batch",
    "review",
    "assembly",
    "export",
  ]);

  const neutralPageTitles = {
    "scene-editor": "场景编辑",
    "shot-inspector": "分镜检查器",
  };

  const storyCanvasView = {
    projectId: "",
    x: 0,
    y: 0,
    scale: 1,
    pointerId: null,
    pointerStartX: 0,
    pointerStartY: 0,
    viewStartX: 0,
    viewStartY: 0,
    persistTimer: null,
  };

  const STORY_CANVAS_MIN_SCALE = 0.45;
  const STORY_CANVAS_MAX_SCALE = 1.6;

  function formatBytes(bytes) {
    if (!bytes) return "0 KB";
    const units = ["B", "KB", "MB", "GB"];
    const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    return `${(bytes / 1024 ** index).toFixed(index > 1 ? 2 : 0)} ${units[index]}`;
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (character) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;",
    })[character]);
  }

  function applyProductionEmptyState() {
    const pageKey = new URLSearchParams(window.location.search).get("page") || "projects";
    if (pageKey === "settings") return;
    const copy = emptyStateCopy[pageKey];
    const page = document.querySelector(".page-scroll");
    if (!copy || !page) return;
    [...page.children].forEach((child) => {
      if (!child.classList.contains("page-header")) child.remove();
    });
    const empty = document.createElement("section");
    empty.className = "production-empty-state";
    empty.innerHTML = `
      <span class="production-empty-icon">A</span>
      <h2>${copy[0]}</h2>
      <p>${copy[1]}</p>
      <span class="production-empty-action">${copy[2]}</span>
      <small>当前使用生产数据库 · 未加载任何演示数据</small>
    `;
    page.appendChild(empty);
  }

  function projectEmptyState() {
    return `
      <section class="production-empty-state">
        <span class="production-empty-icon">A</span>
        <h2>还没有项目</h2>
        <p>生产数据库目前为空。输入项目名称，创建你的第一个真实项目。</p>
        <button class="btn primary" data-api-action="open-project-modal">新建项目</button>
        <small>当前使用生产数据库 · 未加载任何演示数据</small>
      </section>
    `;
  }

  function projectCard(project) {
    const createdAt = new Date(project.created_at);
    const dateText = Number.isNaN(createdAt.getTime())
      ? "刚刚创建"
      : createdAt.toLocaleString("zh-CN", {
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
        });
    return `
      <article class="project-card real-project-card" data-project-id="${escapeHtml(project.id)}" role="button" tabindex="0" aria-label="打开项目 ${escapeHtml(project.name)}">
        <div class="real-project-cover"><span>${escapeHtml(project.name.slice(0, 1).toUpperCase())}</span></div>
        <div>
          <span class="status blue">新建</span>
          <div class="project-title">${escapeHtml(project.name)}</div>
          <div class="project-meta">${
            project.chapter_count
              ? `${project.chapter_count} 个章节 · ${project.large_scene_count} 个大场景`
              : "尚未创建章节"
          }<br>创建于 ${escapeHtml(dateText)}</div>
          <div class="project-tags"><span class="chip">生产项目</span></div>
        </div>
      </article>
    `;
  }

  async function renderProductionProjects() {
    const page = document.querySelector(".page-scroll");
    if (!page) return;
    const payload = await request("/api/projects");
    const items = await Promise.all(payload.items.map(async (project) => {
      const chapters = await request(`/api/projects/${project.id}/chapters`);
      const largeSceneCounts = await Promise.all(
        chapters.items.map(async (chapter) => {
          const largeScenes = await request(`/api/chapters/${chapter.id}/large-scenes`);
          return largeScenes.total;
        })
      );
      return {
        ...project,
        chapter_count: chapters.total,
        large_scene_count: largeSceneCounts.reduce((total, count) => total + count, 0),
      };
    }));
    [...page.children].forEach((child) => {
      if (!child.classList.contains("page-header")) child.remove();
    });
    if (!items.length) {
      page.insertAdjacentHTML("beforeend", projectEmptyState());
      return;
    }
    page.insertAdjacentHTML(
      "beforeend",
      `
        <div class="section-line real-project-heading">
          <h3>我的项目</h3>
          <span>${payload.total} 个真实项目</span>
        </div>
        <div class="grid cols-2 real-project-grid">
          ${items.map(projectCard).join("")}
        </div>
      `
    );
  }

  async function resolveCurrentProject() {
    const projects = await request("/api/projects");
    if (!projects.items.length) return null;
    const requestedId = new URLSearchParams(window.location.search).get("project");
    const selected = requestedId
      ? projects.items.find((project) => project.id === requestedId)
      : null;
    const project = selected || projects.items[0];
    if (!requestedId && project) {
      const params = new URLSearchParams(window.location.search);
      params.set("project", project.id);
      window.history.replaceState(null, "", `?${params.toString()}`);
    }
    return project;
  }

  function formatProjectDate(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "未知";
    return date.toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function applyProjectHeader(project, pageKey) {
    if (!project) return;
    document.querySelectorAll(".page-title, .page-subtitle").forEach((element) => {
      element.textContent = element.textContent.replaceAll("海边度假篇", project.name);
    });
    if (projectScopedPages.has(pageKey) && pageKey !== "overview") {
      const title = document.querySelector(".page-title");
      const subtitle = document.querySelector(".page-subtitle");
      const actions = document.querySelector(".page-header .header-actions");
      if (title && neutralPageTitles[pageKey]) title.textContent = neutralPageTitles[pageKey];
      if (subtitle) subtitle.textContent = `项目：${project.name}`;
      if (actions) actions.innerHTML = "";
    }
    document.body.dataset.projectId = project.id;
  }

  async function renderProductionOverview(project) {
    const page = document.querySelector(".page-scroll");
    if (!page) return;
    const header = page.querySelector(".page-header");
    [...page.children].forEach((child) => {
      if (child !== header) child.remove();
    });
    if (!project) {
      page.insertAdjacentHTML("beforeend", projectEmptyState());
      return;
    }
    const title = header.querySelector(".page-title");
    const subtitle = header.querySelector(".page-subtitle");
    if (title) title.textContent = project.name;
    if (subtitle) subtitle.textContent = "项目概览";
    const chapters = await request(`/api/projects/${project.id}/chapters`);
    if (chapters.total) {
      const chapterItems = await Promise.all(
        chapters.items.map(async (chapter) => {
          const largeScenes = await request(`/api/chapters/${chapter.id}/large-scenes`);
          return { ...chapter, large_scene_count: largeScenes.total };
        })
      );
      const largeSceneTotal = chapterItems.reduce(
        (total, chapter) => total + chapter.large_scene_count,
        0
      );
      page.insertAdjacentHTML(
        "beforeend",
        `
          <section class="panel real-overview-chapters">
            <div class="panel-header">
              <div><div class="panel-title">章节</div><div class="panel-sub">${chapters.total} 个章节 · ${largeSceneTotal} 个大场景</div></div>
            </div>
            <div class="overview-chapter-list">
              ${chapterItems.map((chapter) => `
                <div class="overview-chapter-row">
                  <span class="chapter-order">${String(chapter.sort_order).padStart(2, "0")}</span>
                  <strong>${escapeHtml(chapter.name)}</strong>
                  <span class="overview-chapter-count">${chapter.large_scene_count} 个大场景</span>
                </div>
              `).join("")}
            </div>
          </section>
        `
      );
      return;
    }
    page.insertAdjacentHTML(
      "beforeend",
      `
        <section class="production-empty-state project-overview-empty">
          <span class="production-empty-icon">${escapeHtml(project.name.slice(0, 1).toUpperCase())}</span>
          <h2>项目内容为空</h2>
          <p>这里会显示该项目实际产生的章节、分镜、图片和制作状态。</p>
          <small>创建于 ${escapeHtml(formatProjectDate(project.created_at))}</small>
        </section>
      `
    );
  }

  function chapterEmptyState() {
    return `
      <section class="production-empty-state">
        <span class="production-empty-icon">CH</span>
        <h2>还没有章节</h2>
        <p>章节用于组织项目中的场景和分镜。</p>
        <button class="btn primary" data-api-action="open-chapter-modal">新建章节</button>
        <small>当前项目未创建任何章节</small>
      </section>
    `;
  }

  function largeSceneBlock(largeScene) {
    const sceneType = largeScene.scene_type || "content";
    const typeLabel = sceneType === "transition" ? "过渡段" : "内容段";
    return `
      <article
        class="story-block large-scene-block scene-type-${sceneType}"
        data-large-scene-id="${escapeHtml(largeScene.id)}"
        data-chapter-id="${escapeHtml(largeScene.chapter_id)}"
        data-chapter-name="${escapeHtml(largeScene.chapter_name || "")}"
        data-scene-type="${escapeHtml(sceneType)}"
        data-sort-order="${escapeHtml(largeScene.sort_order)}"
        data-inspector-kind="large-scene"
        data-context-menu="large-scene"
        data-name="${escapeHtml(largeScene.name)}"
        draggable="true"
        aria-label="拖动大场景调整顺序或跨章节移动"
      >
        <div class="large-scene-drag-handle" aria-label="拖动大场景调整顺序或跨章节移动" title="拖动以调整顺序"></div>
        <div class="block-kicker">大场景 ${String(largeScene.sort_order).padStart(2, "0")}</div>
        <div class="block-title">${escapeHtml(largeScene.name)}</div>
        <div class="block-meta">尚未添加小场景</div>
        <div class="block-footer">
          <span class="large-scene-type-badge" data-scene-type="${escapeHtml(sceneType)}">${typeLabel}</span>
        </div>
      </article>
    `;
  }

  function chapterBlock(chapter) {
    const largeScenes = chapter.large_scenes || [];
    const addLargeSceneNode = `
      <div class="large-scene-add-card story-add-node">
        <button
          class="btn compact"
          data-api-action="open-large-scene-modal"
          data-chapter-id="${escapeHtml(chapter.id)}"
          data-chapter-name="${escapeHtml(chapter.name)}"
        >＋ 大场景</button>
      </div>
    `;
    return `
      <section class="story-chapter-group" data-chapter-id="${escapeHtml(chapter.id)}">
        <article
          class="story-block chapter real-chapter-block"
          data-context-menu="chapter"
          data-inspector-kind="chapter"
          data-chapter-id="${escapeHtml(chapter.id)}"
          data-name="${escapeHtml(chapter.name)}"
          data-sort-order="${escapeHtml(chapter.sort_order)}"
          data-large-scene-count="${largeScenes.length}"
        >
          <div class="block-kicker">章节 ${String(chapter.sort_order).padStart(2, "0")}</div>
          <div class="block-title">${escapeHtml(chapter.name)}</div>
          <div class="block-meta">${largeScenes.length} 个大场景</div>
        </article>
        <div class="chapter-scene-connector" aria-hidden="true"></div>
        <div
          class="large-scene-track story-scene-track"
          data-drop-zone
          data-chapter-id="${escapeHtml(chapter.id)}"
        >
          ${largeScenes.map((largeScene) => largeSceneBlock({
            ...largeScene,
            chapter_name: chapter.name,
          })).join("")}
          ${addLargeSceneNode}
        </div>
      </section>
    `;
  }

  function storyCanvasPalette(chapterItems) {
    const firstChapter = chapterItems[0] || null;
    return `
      <section class="panel story-palette-panel">
        <div class="panel-header">
          <div>
            <div class="panel-title">积木与场景包</div>
            <div class="panel-sub">点击添加到主线</div>
          </div>
        </div>
        <div class="palette-list">
          <button class="palette-item" type="button" data-api-action="open-chapter-modal">
            <span class="palette-swatch"></span>
            <span>章节</span>
            <span class="palette-item-mark">＋</span>
          </button>
          <button
            class="palette-item"
            id="story-palette-large-scene"
            type="button"
            data-api-action="open-large-scene-modal"
            data-chapter-id="${firstChapter ? escapeHtml(firstChapter.id) : ""}"
            data-chapter-name="${firstChapter ? escapeHtml(firstChapter.name) : ""}"
            ${firstChapter ? "" : "disabled"}
          >
            <span class="palette-swatch green"></span>
            <span>大场景</span>
            <span class="palette-item-mark">＋</span>
          </button>
        </div>
        <div class="story-palette-note">
          节点只沿主线排序，拖动大场景可调整顺序或移动到其他章节。
        </div>
      </section>
    `;
  }

  function storyCanvasInspectorPlaceholder() {
    return `
      <section class="panel inspector story-runtime-inspector" id="story-runtime-inspector">
        <div class="panel-header">
          <div>
            <div class="panel-title">未选择节点</div>
            <div class="panel-sub">在画布中选择章节或大场景</div>
          </div>
        </div>
        <div class="story-inspector-placeholder">
          <span class="story-inspector-placeholder-icon">⌁</span>
          <p>选择一个结构节点后，这里会显示真实信息和可用操作。</p>
        </div>
      </section>
    `;
  }

  function storyCanvasEmptyStage() {
    return `
      <div class="story-canvas-empty-node">
        <span class="story-canvas-empty-icon">CH</span>
        <strong>主线还是空的</strong>
        <p>从左侧添加第一个章节。</p>
        <button class="btn primary" type="button" data-api-action="open-chapter-modal">新建章节</button>
      </div>
    `;
  }

  function storyCanvasWorkspace(chapterItems, chapterTotal, largeSceneTotal) {
    return `
      <div class="three-pane story-canvas-three-pane">
        ${storyCanvasPalette(chapterItems)}
        <section class="panel story-canvas-center-panel">
          <div class="toolbar story-canvas-toolbar">
            <span class="tool active">主线</span>
            <span class="story-toolbar-count">${chapterTotal} 个章节 · ${largeSceneTotal} 个大场景</span>
            <span class="spacer"></span>
            <button class="tool" type="button" data-story-canvas-action="zoom-out" title="缩小画布" aria-label="缩小画布">−</button>
            <button class="tool story-zoom-label" type="button" data-story-canvas-action="zoom-reset" id="story-canvas-zoom-label" title="恢复 100%">100%</button>
            <button class="tool" type="button" data-story-canvas-action="zoom-in" title="放大画布" aria-label="放大画布">＋</button>
            <button class="tool" type="button" data-story-canvas-action="fit">自动整理</button>
          </div>
          <div class="canvas real-story-viewport" id="story-canvas-viewport" aria-label="剧本结构画布">
            <div class="story-canvas-surface" id="story-canvas-surface">
              <div class="real-story-stack story-runtime-stage">
                ${
                  chapterItems.length
                    ? `<div class="story-runtime-spine" aria-hidden="true"></div>${chapterItems.map(chapterBlock).join("")}`
                    : storyCanvasEmptyStage()
                }
              </div>
            </div>
            <div class="story-canvas-hint">拖动空白处移动 · Ctrl/⌘ + 滚轮缩放</div>
          </div>
        </section>
        ${storyCanvasInspectorPlaceholder()}
      </div>
    `;
  }

  function updateStoryCanvasInspector(node) {
    const inspector = document.getElementById("story-runtime-inspector");
    if (!inspector || !node) return;
    const kind = node.dataset.inspectorKind;
    const name = node.dataset.name || "未命名";
    const id = kind === "chapter"
      ? node.dataset.chapterId
      : node.dataset.largeSceneId;
    const order = Number(node.dataset.sortOrder || 0);
    const isChapter = kind === "chapter";
    const chapterId = isChapter ? id : node.dataset.chapterId;
    const chapterName = isChapter ? name : node.dataset.chapterName || "";
    const typeLabel = node.dataset.sceneType === "transition" ? "过渡段" : "内容段";
    inspector.innerHTML = `
      <div class="panel-header">
        <div>
          <div class="panel-title">${escapeHtml(name)}</div>
          <div class="panel-sub">${isChapter ? "章节" : "大场景"} ${String(order).padStart(2, "0")} · 当前选中</div>
        </div>
        <span class="status blue">${isChapter ? "章节" : escapeHtml(typeLabel)}</span>
      </div>
      <div class="inspector-section">
        <div class="form-group">
          <label class="label">名称</label>
          <div class="field">${escapeHtml(name)}</div>
        </div>
        ${
          isChapter
            ? `
              <div class="form-group">
                <label class="label">包含内容</label>
                <div class="field">${Number(node.dataset.largeSceneCount || 0)} 个大场景</div>
              </div>
            `
            : `
              <div class="form-group">
                <label class="label">所属章节</label>
                <div class="field">${escapeHtml(chapterName)}</div>
              </div>
              <div class="form-group">
                <label class="label">场景类型</label>
                <div class="field">${escapeHtml(typeLabel)}</div>
              </div>
            `
        }
      </div>
      <div class="inspector-section story-inspector-actions">
        ${
          isChapter
            ? `
              <button
                class="btn soft"
                type="button"
                data-api-action="open-large-scene-modal"
                data-chapter-id="${escapeHtml(chapterId)}"
                data-chapter-name="${escapeHtml(chapterName)}"
              >添加大场景</button>
            `
            : ""
        }
        <button
          class="btn"
          type="button"
          data-story-inspector-action="rename"
          data-kind="${escapeHtml(kind)}"
          data-id="${escapeHtml(id)}"
          data-name="${escapeHtml(name)}"
        >改名</button>
        <button
          class="btn danger-soft"
          type="button"
          data-story-inspector-action="delete"
          data-kind="${escapeHtml(kind)}"
          data-id="${escapeHtml(id)}"
          data-name="${escapeHtml(name)}"
          data-large-scene-count="${escapeHtml(node.dataset.largeSceneCount || "0")}"
        >删除</button>
      </div>
      <div class="inspector-section story-inspector-tip">也可以右键节点打开快捷菜单。</div>
    `;
    const paletteLargeScene = document.getElementById("story-palette-large-scene");
    if (paletteLargeScene && chapterId) {
      paletteLargeScene.disabled = false;
      paletteLargeScene.dataset.chapterId = chapterId;
      paletteLargeScene.dataset.chapterName = chapterName;
    }
  }

  function storyCanvasStorageKey(projectId) {
    return `atelier:story-canvas-view:v2:${projectId}`;
  }

  function clampStoryCanvasScale(scale) {
    return Math.min(
      STORY_CANVAS_MAX_SCALE,
      Math.max(STORY_CANVAS_MIN_SCALE, Number(scale) || 1)
    );
  }

  function saveStoryCanvasView() {
    if (!storyCanvasView.projectId) return;
    window.clearTimeout(storyCanvasView.persistTimer);
    storyCanvasView.persistTimer = window.setTimeout(() => {
      try {
        window.localStorage.setItem(
          storyCanvasStorageKey(storyCanvasView.projectId),
          JSON.stringify({
            x: Math.round(storyCanvasView.x * 10) / 10,
            y: Math.round(storyCanvasView.y * 10) / 10,
            scale: Math.round(storyCanvasView.scale * 1000) / 1000,
          })
        );
      } catch (error) {
        // View persistence is optional; the canvas remains usable without storage.
      }
    }, 120);
  }

  function restoreStoryCanvasView(projectId) {
    try {
      const saved = JSON.parse(
        window.localStorage.getItem(storyCanvasStorageKey(projectId)) || "null"
      );
      if (
        saved &&
        Number.isFinite(saved.x) &&
        Number.isFinite(saved.y) &&
        Number.isFinite(saved.scale)
      ) {
        storyCanvasView.x = saved.x;
        storyCanvasView.y = saved.y;
        storyCanvasView.scale = clampStoryCanvasScale(saved.scale);
        return true;
      }
    } catch (error) {
      // Ignore invalid or unavailable browser storage.
    }
    return false;
  }

  function applyStoryCanvasView({ persist = true } = {}) {
    const viewport = document.getElementById("story-canvas-viewport");
    const surface = document.getElementById("story-canvas-surface");
    const zoomLabel = document.getElementById("story-canvas-zoom-label");
    if (!viewport || !surface) return;
    surface.style.transform = `translate3d(${storyCanvasView.x}px, ${storyCanvasView.y}px, 0) scale(${storyCanvasView.scale})`;
    viewport.style.setProperty(
      "--story-grid-size",
      `${Math.max(9, 22 * storyCanvasView.scale)}px`
    );
    viewport.style.setProperty(
      "--story-grid-x",
      `${storyCanvasView.x % (22 * storyCanvasView.scale)}px`
    );
    viewport.style.setProperty(
      "--story-grid-y",
      `${storyCanvasView.y % (22 * storyCanvasView.scale)}px`
    );
    if (zoomLabel) zoomLabel.textContent = `${Math.round(storyCanvasView.scale * 100)}%`;
    if (persist) saveStoryCanvasView();
  }

  function setStoryCanvasScale(nextScale, clientX, clientY) {
    const viewport = document.getElementById("story-canvas-viewport");
    if (!viewport) return;
    const rect = viewport.getBoundingClientRect();
    const originX = Number.isFinite(clientX) ? clientX - rect.left : rect.width / 2;
    const originY = Number.isFinite(clientY) ? clientY - rect.top : rect.height / 2;
    const previousScale = storyCanvasView.scale;
    const scale = clampStoryCanvasScale(nextScale);
    const worldX = (originX - storyCanvasView.x) / previousScale;
    const worldY = (originY - storyCanvasView.y) / previousScale;
    storyCanvasView.scale = scale;
    storyCanvasView.x = originX - worldX * scale;
    storyCanvasView.y = originY - worldY * scale;
    applyStoryCanvasView();
  }

  function fitStoryCanvas({ persist = true } = {}) {
    const viewport = document.getElementById("story-canvas-viewport");
    const stack = document.querySelector("#story-canvas-surface .real-story-stack");
    if (!viewport || !stack) return;
    const viewportWidth = viewport.clientWidth;
    const viewportHeight = viewport.clientHeight;
    const contentWidth = stack.offsetWidth;
    const contentHeight = stack.offsetHeight;
    if (!viewportWidth || !viewportHeight || !contentWidth || !contentHeight) return;
    const inset = 44;
    storyCanvasView.scale = clampStoryCanvasScale(
      Math.min(
        1,
        (viewportWidth - inset * 2) / contentWidth,
        (viewportHeight - inset * 2) / contentHeight
      )
    );
    storyCanvasView.x = Math.max(inset, (viewportWidth - contentWidth * storyCanvasView.scale) / 2);
    storyCanvasView.y = Math.max(inset, (viewportHeight - contentHeight * storyCanvasView.scale) / 2);
    applyStoryCanvasView({ persist });
  }

  function bindStoryCanvas(projectId) {
    const viewport = document.getElementById("story-canvas-viewport");
    const toolbar = document.querySelector(".story-canvas-toolbar");
    if (!viewport || !toolbar) return;
    storyCanvasView.projectId = projectId;

    const stopPanning = (event) => {
      if (storyCanvasView.pointerId === null) return;
      if (
        event &&
        viewport.hasPointerCapture?.(storyCanvasView.pointerId)
      ) {
        viewport.releasePointerCapture(storyCanvasView.pointerId);
      }
      storyCanvasView.pointerId = null;
      viewport.classList.remove("is-panning");
      saveStoryCanvasView();
    };

    viewport.addEventListener("pointerdown", (event) => {
      if (event.button !== 0 && event.button !== 1) return;
      if (
        event.target.closest(
          "button, input, select, textarea, a, .large-scene-block, .real-chapter-block"
        )
      ) {
        return;
      }
      event.preventDefault();
      storyCanvasView.pointerId = event.pointerId;
      storyCanvasView.pointerStartX = event.clientX;
      storyCanvasView.pointerStartY = event.clientY;
      storyCanvasView.viewStartX = storyCanvasView.x;
      storyCanvasView.viewStartY = storyCanvasView.y;
      viewport.setPointerCapture?.(event.pointerId);
      viewport.classList.add("is-panning");
    });

    viewport.addEventListener("pointermove", (event) => {
      if (event.pointerId !== storyCanvasView.pointerId) return;
      storyCanvasView.x =
        storyCanvasView.viewStartX + event.clientX - storyCanvasView.pointerStartX;
      storyCanvasView.y =
        storyCanvasView.viewStartY + event.clientY - storyCanvasView.pointerStartY;
      applyStoryCanvasView({ persist: false });
    });

    viewport.addEventListener("pointerup", stopPanning);
    viewport.addEventListener("pointercancel", stopPanning);

    viewport.addEventListener(
      "wheel",
      (event) => {
        event.preventDefault();
        if (event.ctrlKey || event.metaKey) {
          const factor = Math.exp(-event.deltaY * 0.002);
          setStoryCanvasScale(storyCanvasView.scale * factor, event.clientX, event.clientY);
          return;
        }
        storyCanvasView.x -= event.deltaX;
        storyCanvasView.y -= event.deltaY;
        applyStoryCanvasView();
      },
      { passive: false }
    );

    viewport.addEventListener("click", (event) => {
      const selected = event.target.closest(".large-scene-block, .real-chapter-block");
      viewport
        .querySelectorAll(".canvas-node-selected")
        .forEach((node) => node.classList.remove("canvas-node-selected"));
      if (selected) {
        selected.classList.add("canvas-node-selected");
        updateStoryCanvasInspector(selected);
      }
    });

    toolbar.addEventListener("click", (event) => {
      const button = event.target.closest("[data-story-canvas-action]");
      if (!button) return;
      const action = button.dataset.storyCanvasAction;
      if (action === "zoom-in") {
        setStoryCanvasScale(storyCanvasView.scale + 0.1);
      } else if (action === "zoom-out") {
        setStoryCanvasScale(storyCanvasView.scale - 0.1);
      } else if (action === "zoom-reset") {
        setStoryCanvasScale(1);
      } else if (action === "fit") {
        fitStoryCanvas();
      }
    });

    document
      .getElementById("story-runtime-inspector")
      ?.addEventListener("click", async (event) => {
        const button = event.target.closest("[data-story-inspector-action]");
        if (!button) return;
        const kind = button.dataset.kind;
        const id = button.dataset.id;
        const name = button.dataset.name;
        if (button.dataset.storyInspectorAction === "rename") {
          if (kind === "chapter") openRenameModal("chapter", id, name);
          else openLargeSceneEditModal(id, name);
          return;
        }
        if (button.dataset.storyInspectorAction === "delete") {
          if (kind === "chapter") {
            await deleteChapter(
              id,
              name,
              Number(button.dataset.largeSceneCount || 0)
            );
          } else {
            await deleteLargeScene(id, name);
          }
        }
      });

    const restored = restoreStoryCanvasView(projectId);
    window.requestAnimationFrame(() => {
      if (restored) applyStoryCanvasView({ persist: false });
      else {
        const stack = document.querySelector("#story-canvas-surface .real-story-stack");
        const hasChapters = Boolean(stack?.querySelector(".story-chapter-group"));
        if (hasChapters) {
          const viewportHeight = viewport.clientHeight;
          storyCanvasView.scale = 0.82;
          storyCanvasView.x = 32;
          storyCanvasView.y = Math.max(
            24,
            (viewportHeight - stack.offsetHeight * storyCanvasView.scale) / 2
          );
          applyStoryCanvasView({ persist: false });
        } else {
          fitStoryCanvas({ persist: false });
        }
      }
    });
  }

  async function renderProductionStoryCanvas(project) {
    const page = document.querySelector(".page-scroll");
    if (!page || !project) return;
    const header = page.querySelector(".page-header");
    [...page.children].forEach((child) => {
      if (child !== header) child.remove();
    });
    const title = header.querySelector(".page-title");
    const subtitle = header.querySelector(".page-subtitle");
    const actions = header.querySelector(".header-actions");
    if (title) title.textContent = "剧本画布";
    if (subtitle) subtitle.textContent = `项目：${project.name}`;
    if (actions) {
      actions.innerHTML = '<button class="btn primary" data-api-action="open-chapter-modal">新建章节</button>';
    }
    const chapters = await request(`/api/projects/${project.id}/chapters`);
    const chapterItems = await Promise.all(
      chapters.items.map(async (chapter) => {
        const largeScenes = await request(`/api/chapters/${chapter.id}/large-scenes`);
        return { ...chapter, large_scenes: largeScenes.items };
      })
    );
    const largeSceneTotal = chapterItems.reduce(
      (total, chapter) => total + chapter.large_scenes.length,
      0
    );
    page.insertAdjacentHTML(
      "beforeend",
      storyCanvasWorkspace(chapterItems, chapters.total, largeSceneTotal)
    );
    bindStoryCanvas(project.id);
  }

  const storyWorkspaceState = {
    project: null,
    tree: null,
    smallSceneBackendAvailable: true,
    smallSceneWorkspace: null,
  };

  const storyResourceTypeLabels = {
    composition: "构图",
    expression: "表情",
    scene: "场景",
    lighting: "光线",
    prompt: "提示词",
    composite_template: "复合模板",
  };

  async function requestOptional(path) {
    try {
      return await request(path);
    } catch (error) {
      if ([404, 405, 501].includes(error.status)) return null;
      throw error;
    }
  }

  function storyTreeSmallSceneDirectory(smallScene) {
    const pages = Array.isArray(smallScene.pages) ? smallScene.pages : [];
    const resources = Array.isArray(smallScene.resources) ? smallScene.resources : [];
    return `
      <li class="story-tree-branch">
        <button
          class="story-tree-row story-tree-small-scene"
          type="button"
          data-small-scene-id="${escapeHtml(smallScene.id)}"
          data-story-tree-action="open-small-scene"
          title="双击进入小场景画布"
        >
          <span class="story-tree-chevron">⌄</span>
          <span class="story-tree-icon small-scene">SS</span>
          <span class="story-tree-name">${escapeHtml(smallScene.name)}</span>
          <span class="story-tree-count">${pages.length || Number(smallScene.page_count || 0)}</span>
        </button>
        <ul class="story-tree-children">
          <li class="story-tree-branch">
            <div class="story-tree-row story-tree-folder-row">
              <span class="story-tree-chevron">⌄</span>
              <span class="story-tree-icon folder">PG</span>
              <span class="story-tree-name">场景页</span>
              <span class="story-tree-count">${pages.length || Number(smallScene.page_count || 0)}</span>
            </div>
            ${
              pages.length
                ? `<ul class="story-tree-children">${pages.map((page) => `
                    <li>
                      <button
                        class="story-tree-row story-tree-leaf"
                        type="button"
                        data-small-scene-id="${escapeHtml(smallScene.id)}"
                        data-scene-page-id="${escapeHtml(page.id)}"
                        data-story-tree-action="open-small-scene"
                      >
                        <span class="story-tree-spacer"></span>
                        <span class="story-tree-icon page">${String(page.sort_order || 0).padStart(2, "0")}</span>
                        <span class="story-tree-name">${escapeHtml(page.name)}</span>
                      </button>
                    </li>
                  `).join("")}</ul>`
                : ""
            }
          </li>
          <li class="story-tree-branch">
            <div class="story-tree-row story-tree-folder-row">
              <span class="story-tree-chevron">⌄</span>
              <span class="story-tree-icon folder">MT</span>
              <span class="story-tree-name">关联素材</span>
              <span class="story-tree-count">${resources.length || Number(smallScene.resource_count || 0)}</span>
            </div>
            ${
              resources.length
                ? `<ul class="story-tree-children">${resources.map((resource) => `
                    <li class="story-tree-resource">
                      <div class="story-tree-row story-tree-leaf">
                        <span class="story-tree-spacer"></span>
                        <span class="story-tree-icon resource">${escapeHtml((storyResourceTypeLabels[resource.material_type] || "素材").slice(0, 1))}</span>
                        <span class="story-tree-name">${escapeHtml(resource.name)}</span>
                        <span class="story-tree-count">${Array.isArray(resource.pages) ? resource.pages.length : Number(resource.page_count || 0)}</span>
                      </div>
                    </li>
                  `).join("")}</ul>`
                : ""
            }
          </li>
        </ul>
      </li>
    `;
  }

  function storyDirectoryTree(project, chapters, backendAvailable) {
    return `
      <section class="panel story-directory-panel" aria-label="剧本目录">
        <div class="story-directory-heading">
          <div>
            <div class="panel-title">剧本目录</div>
            <div class="panel-sub">章节 / 大场景 / 小场景 / 页面与素材</div>
          </div>
          <button class="story-directory-add" type="button" data-api-action="open-chapter-modal" aria-label="新建章节">＋</button>
        </div>
        <div class="story-directory-scroll">
          <ul class="story-tree">
            <li class="story-tree-branch story-tree-root">
              <div class="story-tree-row story-tree-root-row">
                <span class="story-tree-chevron">⌄</span>
                <span class="story-tree-icon root">A</span>
                <span class="story-tree-name">${escapeHtml(project.name)}</span>
              </div>
              <ul class="story-tree-children">
                ${chapters.map((chapter) => `
                  <li class="story-tree-branch">
                    <button
                      class="story-tree-row story-tree-chapter"
                      type="button"
                      data-story-tree-node="chapter"
                      data-chapter-id="${escapeHtml(chapter.id)}"
                    >
                      <span class="story-tree-chevron">⌄</span>
                      <span class="story-tree-icon chapter">CH</span>
                      <span class="story-tree-name">${escapeHtml(chapter.name)}</span>
                      <span class="story-tree-count">${chapter.large_scenes.length}</span>
                    </button>
                    <ul class="story-tree-children">
                      ${chapter.large_scenes.map((largeScene) => `
                        <li class="story-tree-branch">
                          <button
                            class="story-tree-row story-tree-large-scene"
                            type="button"
                            data-story-tree-node="large-scene"
                            data-large-scene-id="${escapeHtml(largeScene.id)}"
                          >
                            <span class="story-tree-chevron">⌄</span>
                            <span class="story-tree-icon large-scene">LS</span>
                            <span class="story-tree-name">${escapeHtml(largeScene.name)}</span>
                            <span class="story-tree-count">${largeScene.small_scenes.length}</span>
                          </button>
                          <ul class="story-tree-children">
                            ${largeScene.small_scenes.map(storyTreeSmallSceneDirectory).join("")}
                            ${
                              backendAvailable
                                ? `<li><button
                                    class="story-tree-row story-tree-add-row"
                                    type="button"
                                    data-story-small-scene-action="create"
                                    data-large-scene-id="${escapeHtml(largeScene.id)}"
                                    data-large-scene-name="${escapeHtml(largeScene.name)}"
                                  ><span class="story-tree-spacer"></span><span class="story-tree-icon add">＋</span><span class="story-tree-name">添加小场景</span></button></li>`
                                : ""
                            }
                          </ul>
                        </li>
                      `).join("")}
                    </ul>
                  </li>
                `).join("")}
              </ul>
            </li>
          </ul>
          ${
            backendAvailable
              ? ""
              : `<div class="story-directory-backend-note"><span>API</span><p>章节和大场景已载入。小场景、页面与素材映射等待后端接口。</p></div>`
          }
        </div>
      </section>
    `;
  }

  function storySmallSceneCard(smallScene) {
    const pageCount = Array.isArray(smallScene.pages)
      ? smallScene.pages.length
      : Number(smallScene.page_count || 0);
    const resourceCount = Array.isArray(smallScene.resources)
      ? smallScene.resources.length
      : Number(smallScene.resource_count || 0);
    return `
      <button
        class="story-small-scene-card"
        type="button"
        data-small-scene-id="${escapeHtml(smallScene.id)}"
        data-story-tree-action="open-small-scene"
        title="双击进入小场景画布"
      >
        <span class="story-small-scene-kicker">小场景 ${String(smallScene.sort_order || 0).padStart(2, "0")}</span>
        <strong>${escapeHtml(smallScene.name)}</strong>
        <span>${pageCount} 页 · ${resourceCount} 个关联素材</span>
        <small>双击管理页面与素材映射</small>
      </button>
    `;
  }

  function storyLargeSceneWrapper(largeScene, backendAvailable) {
    const typeLabel = largeScene.scene_type === "transition" ? "过渡段" : "内容段";
    return `
      <section
        class="story-large-scene-wrapper scene-type-${escapeHtml(largeScene.scene_type || "content")}"
        data-large-scene-id="${escapeHtml(largeScene.id)}"
      >
        <header
          class="story-wrapper-heading large-scene-block"
          data-context-menu="large-scene"
          data-large-scene-id="${escapeHtml(largeScene.id)}"
          data-chapter-id="${escapeHtml(largeScene.chapter_id)}"
          data-name="${escapeHtml(largeScene.name)}"
          data-sort-order="${escapeHtml(largeScene.sort_order)}"
          data-scene-type="${escapeHtml(largeScene.scene_type || "content")}"
          draggable="false"
        >
          <span class="story-wrapper-index">LS ${String(largeScene.sort_order || 0).padStart(2, "0")}</span>
          <strong>${escapeHtml(largeScene.name)}</strong>
          <span class="large-scene-type-badge" data-scene-type="${escapeHtml(largeScene.scene_type || "content")}">${typeLabel}</span>
        </header>
        <div class="story-small-scene-grid">
          ${largeScene.small_scenes.map(storySmallSceneCard).join("")}
          ${
            backendAvailable
              ? `<button
                  class="story-small-scene-add"
                  type="button"
                  data-story-small-scene-action="create"
                  data-large-scene-id="${escapeHtml(largeScene.id)}"
                  data-large-scene-name="${escapeHtml(largeScene.name)}"
                ><span>＋</span><strong>添加小场景</strong><small>固定加入当前大场景</small></button>`
              : `<div class="story-small-scene-pending"><span>API</span><strong>小场景待接入</strong><small>后端完成后在这里显示和添加</small></div>`
          }
        </div>
      </section>
    `;
  }

  function storyChapterWrapper(chapter, backendAvailable) {
    return `
      <section class="story-chapter-wrapper" data-chapter-id="${escapeHtml(chapter.id)}">
        <header
          class="story-wrapper-heading story-chapter-wrapper-heading real-chapter-block"
          data-context-menu="chapter"
          data-chapter-id="${escapeHtml(chapter.id)}"
          data-name="${escapeHtml(chapter.name)}"
          data-sort-order="${escapeHtml(chapter.sort_order)}"
          data-large-scene-count="${chapter.large_scenes.length}"
        >
          <span class="story-wrapper-index">CH ${String(chapter.sort_order || 0).padStart(2, "0")}</span>
          <strong>${escapeHtml(chapter.name)}</strong>
          <small>${chapter.large_scenes.length} 个大场景</small>
        </header>
        <div class="story-large-scene-grid">
          ${chapter.large_scenes.map((scene) => storyLargeSceneWrapper(scene, backendAvailable)).join("")}
          <button
            class="story-large-scene-add"
            type="button"
            data-api-action="open-large-scene-modal"
            data-chapter-id="${escapeHtml(chapter.id)}"
            data-chapter-name="${escapeHtml(chapter.name)}"
          ><span>＋</span><strong>添加大场景</strong></button>
        </div>
      </section>
    `;
  }

  function storyHierarchyCanvas(project, chapters, backendAvailable) {
    const largeSceneTotal = chapters.reduce((total, chapter) => total + chapter.large_scenes.length, 0);
    const smallSceneTotal = chapters.reduce(
      (total, chapter) => total + chapter.large_scenes.reduce(
        (chapterTotal, scene) => chapterTotal + scene.small_scenes.length,
        0
      ),
      0
    );
    return `
      <section class="panel story-canvas-center-panel story-hierarchy-panel">
        <div class="toolbar story-canvas-toolbar">
          <span class="tool active">项目结构</span>
          <span class="story-toolbar-count">${chapters.length} 个章节 · ${largeSceneTotal} 个大场景 · ${smallSceneTotal} 个小场景</span>
          <span class="spacer"></span>
          <button class="tool" type="button" data-story-canvas-action="zoom-out" title="缩小画布">−</button>
          <button class="tool story-zoom-label" type="button" data-story-canvas-action="zoom-reset" id="story-canvas-zoom-label">100%</button>
          <button class="tool" type="button" data-story-canvas-action="zoom-in" title="放大画布">＋</button>
          <button class="tool" type="button" data-story-canvas-action="fit">适合画布</button>
        </div>
        <div class="canvas real-story-viewport story-hierarchy-viewport" id="story-canvas-viewport">
          <div class="story-canvas-surface" id="story-canvas-surface">
            <div class="real-story-stack story-hierarchy-stage">
              ${
                chapters.length
                  ? `<section class="story-project-wrapper">
                      <header class="story-project-wrapper-heading">
                        <span class="story-project-mark">${escapeHtml(project.name.slice(0, 1).toUpperCase())}</span>
                        <div><small>画布根节点</small><strong>${escapeHtml(project.name)}</strong></div>
                        <span>${chapters.length} 个章节</span>
                      </header>
                      <div class="story-chapter-wrapper-list">
                        ${chapters.map((chapter) => storyChapterWrapper(chapter, backendAvailable)).join("")}
                      </div>
                    </section>`
                  : storyCanvasEmptyStage()
              }
            </div>
          </div>
          <div class="story-canvas-hint">拖动画布空白处移动 · Ctrl/⌘ + 滚轮缩放 · 双击小场景进入</div>
        </div>
      </section>
    `;
  }

  function storyWorkspaceShell(project, chapters, backendAvailable) {
    return `
      <div class="story-workspace-layout">
        ${storyDirectoryTree(project, chapters, backendAvailable)}
        ${storyHierarchyCanvas(project, chapters, backendAvailable)}
      </div>
    `;
  }

  async function loadStoryHierarchy(projectId) {
    const aggregate = await requestOptional(`/api/projects/${projectId}/story-tree`);
    if (aggregate && Array.isArray(aggregate.chapters)) {
      return { chapters: aggregate.chapters, backendAvailable: true };
    }
    const chaptersPayload = await request(`/api/projects/${projectId}/chapters`);
    const chapters = await Promise.all(
      chaptersPayload.items.map(async (chapter) => {
        const largeScenes = await request(`/api/chapters/${chapter.id}/large-scenes`);
        return {
          ...chapter,
          large_scenes: largeScenes.items.map((largeScene) => ({
            ...largeScene,
            small_scenes: [],
          })),
        };
      })
    );
    return { chapters, backendAvailable: false };
  }

  function openSmallSceneRoute(smallSceneId, scenePageId = "") {
    const params = new URLSearchParams(window.location.search);
    params.set("page", "story-canvas");
    params.set("smallScene", smallSceneId);
    if (scenePageId) params.set("scenePage", scenePageId);
    else params.delete("scenePage");
    window.location.search = `?${params.toString()}`;
  }

  function bindStoryHierarchy(projectId) {
    bindStoryCanvas(projectId);
    const workspace = document.querySelector(".story-workspace-layout");
    if (!workspace) return;
    workspace.addEventListener("dblclick", (event) => {
      const target = event.target.closest("[data-small-scene-id]");
      if (!target) return;
      openSmallSceneRoute(target.dataset.smallSceneId, target.dataset.scenePageId || "");
    });
    workspace.addEventListener("click", (event) => {
      const treeNode = event.target.closest("[data-story-tree-node]");
      if (treeNode) {
        const id = treeNode.dataset.chapterId || treeNode.dataset.largeSceneId;
        const canvasNode = !id
          ? null
          : treeNode.dataset.storyTreeNode === "chapter"
            ? document.querySelector(
                `#story-canvas-surface .story-chapter-wrapper[data-chapter-id="${CSS.escape(id)}"]`
              )
            : document.querySelector(
                `#story-canvas-surface .story-large-scene-wrapper[data-large-scene-id="${CSS.escape(id)}"]`
              );
        document
          .querySelectorAll("#story-canvas-surface .story-tree-canvas-focus")
          .forEach((node) => node.classList.remove("story-tree-canvas-focus"));
        canvasNode?.classList.add("story-tree-canvas-focus");
        canvasNode?.scrollIntoView({ block: "center", inline: "center", behavior: "smooth" });
      }
      const smallSceneAction = event.target.closest("[data-story-small-scene-action='create']");
      if (smallSceneAction) {
        openSmallSceneCreateDialog(
          smallSceneAction.dataset.largeSceneId,
          smallSceneAction.dataset.largeSceneName || ""
        );
      }
    });
  }

  function smallSceneBackendState(project, message) {
    return `
      <div class="story-workspace-layout small-scene-backend-layout">
        <section class="panel story-directory-panel">
          <div class="story-directory-heading">
            <div><div class="panel-title">小场景画布</div><div class="panel-sub">${escapeHtml(project.name)}</div></div>
          </div>
          <div class="story-directory-back-link">
            <button class="btn soft" type="button" data-small-scene-workspace-action="back">返回项目结构</button>
          </div>
        </section>
        <section class="panel small-scene-backend-state">
          <span>API</span>
          <h2>小场景后端待开发</h2>
          <p>${escapeHtml(message || "前端画布已经就绪。后端完成工作区接口后，这里会显示场景页、素材页和映射关系。")}</p>
          <button class="btn primary" type="button" data-small-scene-workspace-action="back">返回项目结构</button>
        </section>
      </div>
    `;
  }

  function scenePageMappingSummary(page, workspace) {
    const mappings = (workspace.mappings || []).filter((mapping) => mapping.scene_page_id === page.id);
    if (!mappings.length) return '<span class="scene-page-no-mapping">尚未绑定素材页</span>';
    return mappings.map((mapping) => {
      const resource = (workspace.resources || []).find((item) =>
        (item.pages || []).some((materialPage) => materialPage.id === mapping.material_page_id)
      );
      const materialPage = resource?.pages?.find((item) => item.id === mapping.material_page_id);
      return `<span class="scene-page-mapping-chip type-${escapeHtml(resource?.material_type || "")}">
        ${escapeHtml(storyResourceTypeLabels[resource?.material_type] || "素材")} · ${escapeHtml(materialPage?.name || "未命名页")}
      </span>`;
    }).join("");
  }

  function smallScenePageCard(page, workspace) {
    return `
      <article class="small-scene-page-card" data-scene-page-id="${escapeHtml(page.id)}">
        <header>
          <span>P${String(page.sort_order || 0).padStart(2, "0")}</span>
          <div class="small-scene-page-actions">
            <button type="button" data-small-scene-page-action="move-left" aria-label="前移">←</button>
            <button type="button" data-small-scene-page-action="move-right" aria-label="后移">→</button>
            <button type="button" data-small-scene-page-action="edit">编辑</button>
            <button class="danger" type="button" data-small-scene-page-action="delete">删除</button>
          </div>
        </header>
        <strong>${escapeHtml(page.name)}</strong>
        <p>${escapeHtml(page.description || "尚未填写画面描述")}</p>
        <div class="small-scene-page-mappings">${scenePageMappingSummary(page, workspace)}</div>
      </article>
    `;
  }

  function materialPageMappingButtons(resource, materialPage, workspace) {
    return (workspace.pages || []).map((scenePage) => {
      const selected = (workspace.mappings || []).some(
        (mapping) =>
          mapping.scene_page_id === scenePage.id &&
          mapping.material_page_id === materialPage.id
      );
      return `
        <button
          class="material-page-map-button ${selected ? "selected" : ""}"
          type="button"
          data-material-map-action="toggle"
          data-scene-page-id="${escapeHtml(scenePage.id)}"
          data-material-page-id="${escapeHtml(materialPage.id)}"
          data-material-type="${escapeHtml(resource.material_type)}"
          title="${selected ? "取消绑定" : "绑定到该场景页；同类型已有绑定会被替换"}"
        >P${String(scenePage.sort_order || 0).padStart(2, "0")}</button>
      `;
    }).join("");
  }

  function smallSceneResourceRow(resource, workspace) {
    const pages = Array.isArray(resource.pages) ? resource.pages : [];
    return `
      <section class="small-scene-resource-group type-${escapeHtml(resource.material_type)}">
        <header>
          <span class="small-scene-resource-type">${escapeHtml(storyResourceTypeLabels[resource.material_type] || resource.material_type)}</span>
          <strong>${escapeHtml(resource.name)}</strong>
          <span>${pages.length} 个只读素材页</span>
          <button
            type="button"
            data-small-scene-resource-action="remove"
            data-resource-link-id="${escapeHtml(resource.link_id || resource.id)}"
          >移除关联</button>
        </header>
        <div class="small-scene-material-pages">
          ${pages.map((materialPage) => `
            <article class="small-scene-material-page">
              <div class="small-scene-material-page-index">M${String(materialPage.sort_order || 0).padStart(2, "0")}</div>
              <div class="small-scene-material-page-copy">
                <strong>${escapeHtml(materialPage.name)}</strong>
                <p>${escapeHtml(materialPage.description || "素材页内容由素材库维护")}</p>
              </div>
              <div class="small-scene-material-page-map">
                <span>绑定到场景页</span>
                <div>${materialPageMappingButtons(resource, materialPage, workspace)}</div>
              </div>
            </article>
          `).join("")}
        </div>
      </section>
    `;
  }

  function smallSceneWorkspaceShell(project, workspace) {
    const pages = Array.isArray(workspace.pages) ? workspace.pages : [];
    const resources = Array.isArray(workspace.resources) ? workspace.resources : [];
    return `
      <div class="small-scene-workspace">
        <section class="panel small-scene-directory">
          <div class="story-directory-heading">
            <div><div class="panel-title">${escapeHtml(workspace.small_scene.name)}</div><div class="panel-sub">小场景目录</div></div>
            <button class="story-directory-add" type="button" data-small-scene-page-action="create" aria-label="添加场景页">＋</button>
          </div>
          <div class="small-scene-directory-scroll">
            <button class="small-scene-back-button" type="button" data-small-scene-workspace-action="back">‹ 返回项目结构</button>
            <div class="small-scene-directory-section">
              <strong>场景页</strong>
              ${pages.map((page) => `
                <button
                  type="button"
                  data-scene-page-focus="${escapeHtml(page.id)}"
                ><span>P${String(page.sort_order || 0).padStart(2, "0")}</span>${escapeHtml(page.name)}</button>
              `).join("")}
              ${pages.length ? "" : "<p>还没有场景页</p>"}
            </div>
            <div class="small-scene-directory-section">
              <strong>关联素材</strong>
              ${resources.map((resource) => `
                <div><span>${escapeHtml((storyResourceTypeLabels[resource.material_type] || "素材").slice(0, 1))}</span>${escapeHtml(resource.name)}</div>
              `).join("")}
              ${resources.length ? "" : "<p>还没有关联素材</p>"}
            </div>
          </div>
        </section>
        <section class="panel small-scene-canvas-panel">
          <div class="small-scene-toolbar">
            <div>
              <small>${escapeHtml(project.name)} / ${escapeHtml(workspace.chapter?.name || "")} / ${escapeHtml(workspace.large_scene?.name || "")}</small>
              <strong>${escapeHtml(workspace.small_scene.name)}</strong>
            </div>
            <span class="small-scene-toolbar-rule">同一场景页：每种素材类型最多绑定 1 页</span>
            <button class="btn soft" type="button" data-small-scene-resource-action="attach">关联素材</button>
            <button class="btn primary" type="button" data-small-scene-page-action="create">添加场景页</button>
          </div>
          <div class="small-scene-canvas-scroll">
            <section class="small-scene-pages-section">
              <div class="small-scene-section-heading">
                <div><span>01</span><div><strong>场景页</strong><small>可添加、修改、删除和调整顺序</small></div></div>
                <span>${pages.length} 页</span>
              </div>
              <div class="small-scene-page-strip">
                ${pages.map((page) => smallScenePageCard(page, workspace)).join("")}
                <button class="small-scene-page-add-card" type="button" data-small-scene-page-action="create">
                  <span>＋</span><strong>添加场景页</strong>
                </button>
              </div>
            </section>
            <section class="small-scene-resources-section">
              <div class="small-scene-section-heading">
                <div><span>02</span><div><strong>素材页映射</strong><small>素材页只读；点击 P 编号绑定或替换同类型映射</small></div></div>
                <span>${resources.length} 个素材</span>
              </div>
              ${
                resources.length
                  ? resources.map((resource) => smallSceneResourceRow(resource, workspace)).join("")
                  : `<div class="small-scene-resource-empty"><span>MT</span><strong>还没有关联素材</strong><p>先从素材库选择素材。素材自身的页面在这里保持只读。</p><button class="btn soft" type="button" data-small-scene-resource-action="attach">关联素材</button></div>`
              }
            </section>
          </div>
        </section>
      </div>
    `;
  }

  function openSmallSceneCreateDialog(largeSceneId, largeSceneName) {
    openStoryEditorDialog({
      title: "添加小场景",
      description: `添加到大场景「${largeSceneName || "未命名"}」`,
      nameLabel: "小场景名称",
      nameValue: "",
      descriptionValue: "",
      showDescription: false,
      submitText: "创建小场景",
      onSubmit: async ({ name }) => {
        await request(`/api/large-scenes/${largeSceneId}/small-scenes`, {
          method: "POST",
          body: JSON.stringify({ name }),
        });
        await renderProductionStoryCanvasV3(storyWorkspaceState.project);
      },
    });
  }

  function openStoryEditorDialog({
    title,
    description,
    nameLabel,
    nameValue,
    descriptionValue,
    showDescription,
    submitText,
    onSubmit,
  }) {
    document.getElementById("story-editor-modal")?.remove();
    const modal = document.createElement("div");
    modal.id = "story-editor-modal";
    modal.className = "atelier-modal-backdrop show";
    modal.innerHTML = `
      <section class="atelier-modal size-md" role="dialog" aria-modal="true" aria-labelledby="story-editor-title">
        <div class="atelier-modal-icon scene">SC</div>
        <h2 id="story-editor-title">${escapeHtml(title)}</h2>
        <p>${escapeHtml(description || "")}</p>
        <form id="story-editor-form">
          <label class="label" for="story-editor-name">${escapeHtml(nameLabel)}</label>
          <input id="story-editor-name" class="modal-input" name="name" maxlength="80" value="${escapeHtml(nameValue || "")}" required />
          ${
            showDescription
              ? `<label class="label" for="story-editor-description">画面描述</label>
                 <textarea id="story-editor-description" class="modal-input story-editor-description" name="description" maxlength="2000">${escapeHtml(descriptionValue || "")}</textarea>`
              : ""
          }
          <div class="modal-error" role="alert"></div>
          <div class="modal-actions">
            <button class="btn" type="button" data-story-editor-close>取消</button>
            <button class="btn primary" type="submit">${escapeHtml(submitText)}</button>
          </div>
        </form>
      </section>
    `;
    document.body.appendChild(modal);
    const close = () => modal.remove();
    modal.querySelector("[data-story-editor-close]").addEventListener("click", close);
    modal.addEventListener("click", (event) => {
      if (event.target === modal) close();
    });
    modal.querySelector("form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const submit = form.querySelector("[type='submit']");
      const error = form.querySelector(".modal-error");
      submit.disabled = true;
      try {
        await onSubmit({
          name: form.elements.name.value.trim(),
          description: showDescription ? form.elements.description.value.trim() : "",
        });
        close();
      } catch (requestError) {
        error.textContent = requestError.message;
        submit.disabled = false;
      }
    });
    modal.querySelector("#story-editor-name").focus();
  }

  async function refreshSmallSceneWorkspace() {
    const smallSceneId = new URLSearchParams(window.location.search).get("smallScene");
    if (!smallSceneId || !storyWorkspaceState.project) return;
    await renderSmallSceneWorkspace(storyWorkspaceState.project, smallSceneId);
  }

  function bindSmallSceneWorkspace(project, workspace) {
    const shell = document.querySelector(".small-scene-workspace, .small-scene-backend-layout");
    if (!shell) return;
    shell.addEventListener("click", async (event) => {
      try {
      const back = event.target.closest("[data-small-scene-workspace-action='back']");
      if (back) {
        const params = new URLSearchParams(window.location.search);
        params.delete("smallScene");
        params.delete("scenePage");
        window.location.search = `?${params.toString()}`;
        return;
      }
      const focus = event.target.closest("[data-scene-page-focus]");
      if (focus) {
        document.querySelector(`[data-scene-page-id="${CSS.escape(focus.dataset.scenePageFocus)}"]`)
          ?.scrollIntoView({ behavior: "smooth", inline: "center", block: "center" });
        return;
      }
      const pageAction = event.target.closest("[data-small-scene-page-action]");
      if (pageAction) {
        const action = pageAction.dataset.smallScenePageAction;
        const card = pageAction.closest("[data-scene-page-id]");
        const page = card
          ? (workspace.pages || []).find((item) => item.id === card.dataset.scenePageId)
          : null;
        if (action === "create" || action === "edit") {
          openStoryEditorDialog({
            title: action === "create" ? "添加场景页" : "编辑场景页",
            description: action === "create" ? "新页面会加入当前小场景末尾。" : `正在编辑 P${String(page.sort_order).padStart(2, "0")}`,
            nameLabel: "页面名称",
            nameValue: page?.name || "",
            descriptionValue: page?.description || "",
            showDescription: true,
            submitText: action === "create" ? "创建页面" : "保存修改",
            onSubmit: async (values) => {
              await request(
                action === "create"
                  ? `/api/small-scenes/${workspace.small_scene.id}/pages`
                  : `/api/small-scene-pages/${page.id}`,
                {
                  method: action === "create" ? "POST" : "PATCH",
                  body: JSON.stringify(values),
                }
              );
              await refreshSmallSceneWorkspace();
            },
          });
          return;
        }
        if (action === "delete" && page) {
          const confirmed = await confirmDialog({
            title: "删除场景页",
            message: `确定删除「${page.name}」吗？该页的所有素材映射会一并删除，其余页面会自动连续编号。`,
            confirmText: "删除",
            danger: true,
          });
          if (!confirmed) return;
          await request(`/api/small-scene-pages/${page.id}`, { method: "DELETE" });
          await refreshSmallSceneWorkspace();
          return;
        }
        if (["move-left", "move-right"].includes(action) && page) {
          const ids = (workspace.pages || []).map((item) => item.id);
          const index = ids.indexOf(page.id);
          const target = action === "move-left" ? index - 1 : index + 1;
          if (target < 0 || target >= ids.length) return;
          [ids[index], ids[target]] = [ids[target], ids[index]];
          await request(`/api/small-scenes/${workspace.small_scene.id}/pages/order`, {
            method: "PUT",
            body: JSON.stringify({ page_ids: ids }),
          });
          await refreshSmallSceneWorkspace();
          return;
        }
      }
      const mapAction = event.target.closest("[data-material-map-action='toggle']");
      if (mapAction) {
        const selected = mapAction.classList.contains("selected");
        const url = `/api/small-scene-pages/${mapAction.dataset.scenePageId}/mappings/${mapAction.dataset.materialType}`;
        if (selected) {
          // Per second-round contract 8.5: PUT + null is the canonical unset
          await request(url, {
            method: "PUT",
            body: JSON.stringify({ material_page_id: null }),
          });
        } else {
          await request(url, {
            method: "PUT",
            body: JSON.stringify({
              material_page_id: mapAction.dataset.materialPageId,
            }),
          });
        }
        await refreshSmallSceneWorkspace();
        return;
      }
      const resourceAction = event.target.closest("[data-small-scene-resource-action]");
      if (resourceAction?.dataset.smallSceneResourceAction === "attach") {
        await openSmallSceneMaterialDialog(workspace);
        return;
      }
      if (resourceAction?.dataset.smallSceneResourceAction === "remove") {
        const confirmed = await confirmDialog({
          title: "移除关联素材",
          message: "素材本身不会被删除，但它在当前小场景内的所有页面映射会被移除。",
          confirmText: "移除",
          danger: true,
        });
        if (!confirmed) return;
        await request(`/api/small-scene-resource-links/${resourceAction.dataset.resourceLinkId}`, {
          method: "DELETE",
        });
        await refreshSmallSceneWorkspace();
      }
      } catch (error) {
        if (typeof showToast === "function") showToast(error.message || "操作失败");
      }
    });
  }

  async function openSmallSceneMaterialDialog(workspace) {
    const materials = await request("/api/materials?limit=100&offset=0&sort=name_asc");
    document.getElementById("small-scene-material-modal")?.remove();
    const linkedIds = new Set((workspace.resources || []).map((resource) => resource.material_id || resource.id));
    const choices = materials.items.filter((item) => !linkedIds.has(item.id));
    const modal = document.createElement("div");
    modal.id = "small-scene-material-modal";
    modal.className = "atelier-modal-backdrop show";
    modal.innerHTML = `
      <section class="atelier-modal size-md small-scene-material-dialog" role="dialog" aria-modal="true">
        <div class="atelier-modal-icon scene">MT</div>
        <h2>关联素材</h2>
        <p>素材关联后，其素材页会只读显示在小场景画布中。</p>
        <div class="small-scene-material-choices">
          ${choices.map((item) => `
            <button type="button" data-material-choice-id="${escapeHtml(item.id)}">
              <span>${escapeHtml(storyResourceTypeLabels[item.material_type] || item.material_type)}</span>
              <strong>${escapeHtml(item.name)}</strong>
              <small>${escapeHtml(item.description || "暂无简介")}</small>
            </button>
          `).join("") || "<div class='small-scene-material-choice-empty'>没有可继续关联的素材</div>"}
        </div>
        <div class="modal-actions"><button class="btn" type="button" data-material-choice-close>关闭</button></div>
      </section>
    `;
    document.body.appendChild(modal);
    const close = () => modal.remove();
    modal.querySelector("[data-material-choice-close]").addEventListener("click", close);
    modal.addEventListener("click", async (event) => {
      if (event.target === modal) close();
      const choice = event.target.closest("[data-material-choice-id]");
      if (!choice) return;
      choice.disabled = true;
      try {
        await request(`/api/small-scenes/${workspace.small_scene.id}/resources`, {
          method: "POST",
          body: JSON.stringify({ material_id: choice.dataset.materialChoiceId }),
        });
        close();
        await refreshSmallSceneWorkspace();
      } catch (error) {
        choice.disabled = false;
        if (typeof showToast === "function") showToast(error.message);
      }
    });
  }

  async function renderSmallSceneWorkspace(project, smallSceneId) {
    const page = document.querySelector(".page-scroll");
    if (!page) return;
    const header = page.querySelector(".page-header");
    [...page.children].forEach((child) => {
      if (child !== header) child.remove();
    });
    const title = header.querySelector(".page-title");
    const subtitle = header.querySelector(".page-subtitle");
    const actions = header.querySelector(".header-actions");
    if (title) title.textContent = "小场景画布";
    if (subtitle) subtitle.textContent = `项目：${project.name}`;
    if (actions) actions.innerHTML = "";
    const payload = await requestOptional(`/api/small-scenes/${smallSceneId}/workspace`);
    if (!payload) {
      page.insertAdjacentHTML(
        "beforeend",
        smallSceneBackendState(project, "缺少 GET /api/small-scenes/{id}/workspace 接口。请按后端开发需求书完成后端。")
      );
      bindSmallSceneWorkspace(project, null);
      return;
    }
    storyWorkspaceState.smallSceneWorkspace = payload;
    page.insertAdjacentHTML("beforeend", smallSceneWorkspaceShell(project, payload));
    bindSmallSceneWorkspace(project, payload);
  }

  async function renderProductionStoryCanvasV3(project) {
    const page = document.querySelector(".page-scroll");
    if (!page || !project) return;
    storyWorkspaceState.project = project;
    const smallSceneId = new URLSearchParams(window.location.search).get("smallScene");
    if (smallSceneId) {
      await renderSmallSceneWorkspace(project, smallSceneId);
      return;
    }
    const header = page.querySelector(".page-header");
    [...page.children].forEach((child) => {
      if (child !== header) child.remove();
    });
    const title = header.querySelector(".page-title");
    const subtitle = header.querySelector(".page-subtitle");
    const actions = header.querySelector(".header-actions");
    if (title) title.textContent = "剧本画布";
    if (subtitle) subtitle.textContent = `项目：${project.name}`;
    if (actions) {
      actions.innerHTML = '<button class="btn primary" data-api-action="open-chapter-modal">新建章节</button>';
    }
    const hierarchy = await loadStoryHierarchy(project.id);
    storyWorkspaceState.tree = hierarchy.chapters;
    storyWorkspaceState.smallSceneBackendAvailable = hierarchy.backendAvailable;
    page.insertAdjacentHTML(
      "beforeend",
      storyWorkspaceShell(project, hierarchy.chapters, hierarchy.backendAvailable)
    );
    bindStoryHierarchy(project.id);
  }

  const specTypeLabels = {
    full_body: "全身",
    half_body: "半身",
    close_up: "特写",
    custom: "自定义",
  };

  const specTypeOrder = ["full_body", "half_body", "close_up", "custom"];

  function specLabel(spec) {
    if (spec.spec_type === "custom") {
      return spec.custom_label || "自定义";
    }
    return specTypeLabels[spec.spec_type] || spec.spec_type;
  }

  function characterEmptyState() {
    return `
      <section class="production-empty-state">
        <span class="production-empty-icon">CH</span>
        <h2>还没有人物</h2>
        <p>创建人物后，可以为其管理多套形象变体与景别规格。</p>
        <button class="btn primary" data-api-action="open-character-modal">新建人物</button>
        <small>尚未创建任何人物</small>
      </section>
    `;
  }

  function characterCard(character, stats, specCount) {
    const filled = stats ? stats.spec_filled : 0;
    const total = stats ? stats.spec_total : 0;
    const variantCount = stats ? stats.variant_count : 0;
    const completeness = total > 0 ? `${filled}/${total}` : "0/0";
    return `
      <article
        class="character-block"
        data-character-id="${escapeHtml(character.id)}"
        data-api-action="select-character"
        data-context-menu="character"
        data-name="${escapeHtml(character.name)}"
      >
        <div class="character-block-thumb"></div>
        <div class="character-block-name">${escapeHtml(character.name)}</div>
        <div class="character-block-meta">${variantCount} 个变体 · ${specCount} 个规格</div>
        <div class="character-block-stats">
          <span class="stats-pill ${filled > 0 ? "" : "muted"}">规格 ${completeness}</span>
        </div>
      </article>
    `;
  }

  function variantRow(variant) {
    const isDefault = Number(variant.is_default) === 1;
    return `
      <li
        class="character-variant-row"
        data-variant-id="${escapeHtml(variant.id)}"
        data-context-menu="character-variant"
        data-name="${escapeHtml(variant.name)}"
        data-is-default="${isDefault ? "1" : "0"}"
      >
        <span class="character-variant-name">${escapeHtml(variant.name)}</span>
        ${isDefault ? '<span class="character-variant-default">默认</span>' : ""}
        <span class="character-variant-order">序 ${variant.sort_order}</span>
      </li>
    `;
  }

  function specRow(spec) {
    const isCustom = spec.spec_type === "custom";
    return `
      <li
        class="character-spec-row"
        data-spec-id="${escapeHtml(spec.id)}"
        data-context-menu="project-spec"
        data-name="${escapeHtml(specLabel(spec))}"
        data-spec-type="${escapeHtml(spec.spec_type)}"
      >
        <span class="character-spec-name">${escapeHtml(specLabel(spec))}</span>
        <span class="character-spec-type">${escapeHtml(specTypeLabels[spec.spec_type] || spec.spec_type)}</span>
        <span class="character-spec-order">序 ${spec.sort_order}</span>
      </li>
    `;
  }

  function specValueEditor(value) {
    const label = specLabel(value);
    const weight = value.lora_weight === null || value.lora_weight === undefined
      ? ""
      : String(value.lora_weight);
    const filled = Boolean(
      value.prompt ||
      value.lora_name ||
      value.model_override ||
      value.notes ||
      weight
    );
    return `
      <form
        class="character-spec-editor"
        data-inline-action="save-spec-value"
        data-spec-value-id="${escapeHtml(value.id)}"
      >
        <div class="character-spec-editor-head">
          <div
            class="character-spec-editor-title"
            data-context-menu="project-spec"
            data-spec-id="${escapeHtml(value.spec_id)}"
            data-name="${escapeHtml(label)}"
            data-spec-type="${escapeHtml(value.spec_type)}"
          >
            <strong>${escapeHtml(label)}</strong>
            <span>${escapeHtml(specTypeLabels[value.spec_type] || value.spec_type)}</span>
          </div>
          <span class="spec-fill-state ${filled ? "filled" : ""}">${filled ? "已填写" : "未填写"}</span>
        </div>
        <label class="character-spec-field character-spec-field-wide">
          <span>提示词</span>
          <textarea name="prompt" rows="3" placeholder="输入当前人物、当前变体在这个景别下使用的提示词">${escapeHtml(value.prompt || "")}</textarea>
        </label>
        <div class="character-spec-field-grid">
          <label class="character-spec-field">
            <span>LoRA 文件</span>
            <input name="lora_name" type="text" value="${escapeHtml(value.lora_name || "")}" placeholder="例如：character.safetensors" />
          </label>
          <label class="character-spec-field">
            <span>LoRA 权重</span>
            <input name="lora_weight" type="number" min="0" max="2" step="0.01" value="${escapeHtml(weight)}" placeholder="例如：0.8" />
          </label>
          <label class="character-spec-field character-spec-field-wide">
            <span>模型覆盖</span>
            <input name="model_override" type="text" value="${escapeHtml(value.model_override || "")}" placeholder="留空则使用工作流默认模型" />
          </label>
        </div>
        <label class="character-spec-field character-spec-field-wide">
          <span>备注</span>
          <textarea name="notes" rows="2" placeholder="只供自己查看的使用说明">${escapeHtml(value.notes || "")}</textarea>
        </label>
        <div class="character-spec-editor-actions">
          <span class="spec-save-status" role="status"></span>
          <button class="btn small primary" type="submit">保存此规格</button>
        </div>
      </form>
    `;
  }

  function characterExpandedPanel(character, variants, specs) {
    const defaultVariant = variants.find((v) => Number(v.is_default) === 1) || variants[0];
    const activeVariantId = defaultVariant ? defaultVariant.id : "";
    return `
      <section class="character-expanded" data-character-id="${escapeHtml(character.id)}">
        <div class="variant-tabs-bar">
          <div class="variant-tabs" role="tablist">
            ${variants.map((v) => variantTab(v, v.id === activeVariantId)).join("")}
            <button class="variant-tab-add" type="button" data-api-action="add-variant" data-character-id="${escapeHtml(character.id)}" aria-label="添加变体">+</button>
          </div>
          <form class="character-inline-form variant-tab-form" data-inline-action="create-variant" data-character-id="${escapeHtml(character.id)}" hidden>
            <input class="modal-input" name="name" maxlength="80" autocomplete="off" placeholder="例如：裙装" required />
            <button class="btn small primary" type="submit">创建</button>
            <button class="btn small" type="button" data-api-action="cancel-add-variant">取消</button>
          </form>
        </div>
        <div class="character-expanded-main">
          <div class="character-expanded-head">
            <div>
              <div class="character-expanded-title">规格</div>
              <div class="character-expanded-sub">${specs.length} 个规格 · 全局共享 · 当前变体：${escapeHtml(defaultVariant ? defaultVariant.name : "无")}</div>
            </div>
            <button class="btn small soft" type="button" data-api-action="add-spec" data-project-id="${escapeHtml(character.project_id)}">添加规格</button>
          </div>
          <div
            class="character-spec-editor-list"
            data-variant-spec-values
            data-active-variant-id="${escapeHtml(activeVariantId)}"
          >
            ${activeVariantId
              ? '<div class="character-spec-editor-loading">正在读取规格内容…</div>'
              : '<div class="character-spec-editor-empty">请先创建一个形象变体。</div>'}
          </div>
          <form class="character-inline-form" data-inline-action="create-spec" data-project-id="${escapeHtml(character.project_id)}" hidden>
            <label class="label">类型</label>
            <select class="modal-input" name="spec_type">
              <option value="full_body">全身</option>
              <option value="half_body">半身</option>
              <option value="close_up">特写</option>
              <option value="custom">自定义</option>
            </select>
            <label class="label">自定义标签（仅自定义类型需要）</label>
            <input class="modal-input" name="custom_label" maxlength="80" autocomplete="off" placeholder="例如：近景特写" />
            <button class="btn small primary" type="submit">创建</button>
            <button class="btn small" type="button" data-api-action="cancel-add-spec">取消</button>
          </form>
        </div>
      </section>
    `;
  }

  async function renderVariantSpecValues(variantId, variantName) {
    const modal = document.getElementById("character-detail-modal");
    if (!modal || modal.hidden) return;
    const list = modal.querySelector("[data-variant-spec-values]");
    if (!list) return;
    list.dataset.activeVariantId = variantId;
    list.innerHTML = '<div class="character-spec-editor-loading">正在读取规格内容…</div>';
    try {
      const payload = await request(`/api/character-variants/${variantId}/spec-values`);
      if (list.dataset.activeVariantId !== variantId) return;
      list.innerHTML = payload.total
        ? payload.items.map(specValueEditor).join("")
        : '<div class="character-spec-editor-empty">还没有规格。请先点击右上角“添加规格”。</div>';
      const sub = modal.querySelector(".character-expanded-sub");
      if (sub) {
        sub.textContent = `${payload.total} 个规格 · 全局共享 · 当前变体：${variantName || ""}`;
      }
    } catch (error) {
      if (list.dataset.activeVariantId !== variantId) return;
      list.innerHTML = `
        <div class="character-spec-editor-error">
          <span>规格内容加载失败：${escapeHtml(error.message)}</span>
          <button class="btn small" type="button" data-api-action="retry-spec-values" data-variant-id="${escapeHtml(variantId)}" data-variant-name="${escapeHtml(variantName || "")}">重新加载</button>
        </div>
      `;
    }
  }

  function variantTab(variant, isActive) {
    const isDefault = Number(variant.is_default) === 1;
    return `
      <button
        class="variant-tab${isActive ? " active" : ""}"
        type="button"
        role="tab"
        data-api-action="select-variant"
        data-variant-id="${escapeHtml(variant.id)}"
        data-variant-name="${escapeHtml(variant.name)}"
        data-context-menu="character-variant"
        data-name="${escapeHtml(variant.name)}"
        data-is-default="${isDefault ? "1" : "0"}"
      >
        <span class="variant-tab-name">${escapeHtml(variant.name)}</span>
        ${isDefault ? '<span class="variant-tab-default">默认</span>' : ""}
      </button>
    `;
  }

  async function renderProductionCharacters() {
    const page = document.querySelector(".page-scroll");
    if (!page) return;
    const header = page.querySelector(".page-header");
    [...page.children].forEach((child) => {
      if (child !== header) child.remove();
    });
    const title = header.querySelector(".page-title");
    const subtitle = header.querySelector(".page-subtitle");
    const actions = header.querySelector(".header-actions");
    if (title) title.textContent = "人物库";
    if (subtitle) subtitle.textContent = "管理全局人物、形象变体与景别规格。";
    if (actions) {
      actions.innerHTML = '<button class="btn primary" data-api-action="open-character-modal">新建人物</button>';
    }
    const [charactersPayload, specsPayload] = await Promise.all([
      request(`/api/characters`),
      request(`/api/specs`),
    ]);
    if (!charactersPayload.total) {
      page.insertAdjacentHTML("beforeend", characterEmptyState());
      return;
    }
    page.insertAdjacentHTML(
      "beforeend",
      `
        <section class="panel real-character-panel">
          <div class="panel-header">
            <div>
              <div class="panel-title">全局人物</div>
              <div class="panel-sub">${charactersPayload.total} 个人物 · ${specsPayload.total} 个规格</div>
            </div>
          </div>
          <div class="character-grid">
            ${charactersPayload.items
              .map((character) =>
                characterCard(character, character.stats, specsPayload.total)
              )
              .join("")}
          </div>
        </section>
      `
    );
  }

  const characterDatabaseState = {
    q: "",
    copyright: "",
    sort: "count_desc",
    page: 1,
    pageSize: 50,
    total: 0,
    isLoading: false,
    isReady: false,
    hasMore: true,
    observer: null,
    statusTimer: null,
    copyrightTimer: null,
    copyrightRequestId: 0,
  };

  async function renderCharacterDatabasePage() {
    const page = document.querySelector(".page-scroll");
    if (!page) return;
    characterDatabaseState.isReady = false;
    const form = document.getElementById("character-database-search-form");
    if (form && !form.dataset.bound) {
      form.dataset.bound = "1";
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        const qInput = document.getElementById("character-database-q");
        const copyrightSelect = document.getElementById("character-database-copyright");
        const sortSelect = document.getElementById("character-database-sort");
        characterDatabaseState.q = (qInput && qInput.value || "").trim();
        characterDatabaseState.copyright = (copyrightSelect && copyrightSelect.value || "").trim();
        characterDatabaseState.sort = (sortSelect && sortSelect.value || "count_desc");
        characterDatabaseState.page = 1;
        characterDatabaseState.hasMore = true;
        loadCharacterDatabaseResults(false);
      });
    }
    const copyrightInput = document.getElementById("character-database-copyright");
    if (copyrightInput && !copyrightInput.dataset.bound) {
      copyrightInput.dataset.bound = "1";
      const scheduleSuggestions = () => {
        if (characterDatabaseState.copyrightTimer) {
          clearTimeout(characterDatabaseState.copyrightTimer);
        }
        characterDatabaseState.copyrightTimer = setTimeout(() => {
          loadCharacterDatabaseCopyrights(copyrightInput.value || "");
        }, 180);
      };
      copyrightInput.addEventListener("input", scheduleSuggestions);
      copyrightInput.addEventListener("focus", scheduleSuggestions);
    }
    // Reset results container with table shell + scroll sentinel.
    const resultsEl = document.getElementById("character-database-results");
    if (resultsEl) {
      resultsEl.innerHTML =
        '<div class="character-database-scroll">'
        + '<table class="character-database-table"><thead><tr>'
        + '<th>角色名</th><th>作品系列</th><th>触发词</th><th>核心标签</th><th>标签数</th><th>Danbooru</th>'
        + '</tr></thead><tbody></tbody></table>'
        + '<div class="character-database-sentinel" id="character-database-sentinel"></div>'
        + '</div>';
      setupCharacterDatabaseScrollObserver();
    }
    // Check backend status first; poll if still loading the CSV index.
    try {
      const statusPayload = await request("/api/character-database/status");
      if (statusPayload.state === "ready") {
        characterDatabaseState.isReady = true;
        await loadCharacterDatabaseResults(false);
      } else if (statusPayload.state === "loading") {
        showCharacterDatabaseLoading(statusPayload.progress || 0);
        pollCharacterDatabaseStatus();
      } else if (statusPayload.state === "error") {
        const resultsEl2 = document.getElementById("character-database-results");
        if (resultsEl2)
          resultsEl2.innerHTML = `<div class="character-database-empty">角色库加载失败：${escapeHtml(statusPayload.error || "未知错误")}</div>`;
      }
    } catch (error) {
      const resultsEl3 = document.getElementById("character-database-results");
      if (resultsEl3)
        resultsEl3.innerHTML = `<div class="character-database-empty">无法连接角色库服务：${escapeHtml(error.message)}</div>`;
    }
  }

  function showCharacterDatabaseLoading(progress) {
    const metaEl = document.getElementById("character-database-meta");
    const resultsEl = document.getElementById("character-database-results");
    if (metaEl) {
      const pct = Math.round((progress || 0) * 100);
      metaEl.textContent = `角色库正在建立索引 ${pct}%，请稍候…`;
    }
    if (resultsEl) {
      resultsEl.innerHTML =
        '<div class="character-database-empty">角色库正在建立索引，完成后将自动加载…</div>';
    }
  }

  function pollCharacterDatabaseStatus() {
    if (characterDatabaseState.statusTimer) return;
    characterDatabaseState.statusTimer = setInterval(async () => {
      try {
        const statusPayload = await request("/api/character-database/status");
        if (statusPayload.state === "ready") {
          characterDatabaseState.isReady = true;
          clearInterval(characterDatabaseState.statusTimer);
          characterDatabaseState.statusTimer = null;
          const resultsEl = document.getElementById("character-database-results");
          if (resultsEl) {
            resultsEl.innerHTML =
              '<div class="character-database-scroll">'
              + '<table class="character-database-table"><thead><tr>'
              + '<th>角色名</th><th>作品系列</th><th>触发词</th><th>核心标签</th><th>标签数</th><th>Danbooru</th>'
              + '</tr></thead><tbody></tbody></table>'
              + '<div class="character-database-sentinel" id="character-database-sentinel"></div>'
              + '</div>';
            setupCharacterDatabaseScrollObserver();
          }
          await loadCharacterDatabaseResults(false);
        } else if (statusPayload.state === "loading") {
          showCharacterDatabaseLoading(statusPayload.progress || 0);
        } else if (statusPayload.state === "error") {
          clearInterval(characterDatabaseState.statusTimer);
          characterDatabaseState.statusTimer = null;
          const resultsEl = document.getElementById("character-database-results");
          if (resultsEl)
            resultsEl.innerHTML = `<div class="character-database-empty">角色库加载失败：${escapeHtml(statusPayload.error || "未知错误")}</div>`;
        }
      } catch (error) {
        // keep polling on transient network errors
      }
    }, 2000);
  }

  function setupCharacterDatabaseScrollObserver() {
    if (characterDatabaseState.observer) {
      characterDatabaseState.observer.disconnect();
      characterDatabaseState.observer = null;
    }
    const sentinel = document.getElementById("character-database-sentinel");
    if (!sentinel) return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            if (
              characterDatabaseState.isReady &&
              !characterDatabaseState.isLoading &&
              characterDatabaseState.hasMore
            ) {
              characterDatabaseState.page += 1;
              loadCharacterDatabaseResults(true);
            }
          }
        }
      },
      { root: document.querySelector(".character-database-scroll"), rootMargin: "64px" }
    );
    observer.observe(sentinel);
    characterDatabaseState.observer = observer;
  }

  async function loadCharacterDatabaseCopyrights(query) {
    const list = document.getElementById("character-database-copyright-options");
    if (!list) return;
    const requestId = characterDatabaseState.copyrightRequestId + 1;
    characterDatabaseState.copyrightRequestId = requestId;
    try {
      const params = new URLSearchParams();
      params.set("q", String(query || "").trim());
      params.set("limit", "50");
      const payload = await request(
        `/api/character-database/copyrights?${params.toString()}`
      );
      if (requestId !== characterDatabaseState.copyrightRequestId) return;
      const items = Array.isArray(payload.items)
        ? payload.items
        : Array.isArray(payload)
        ? payload
        : [];
      list.innerHTML = items
        .map((item) => {
          const value =
            typeof item === "string"
              ? item
              : item.value || item.copyright || item.name || "";
          return `<option value="${escapeHtml(value)}"></option>`;
        })
        .join("");
    } catch (error) {
      if (requestId === characterDatabaseState.copyrightRequestId) {
        list.innerHTML = "";
      }
    }
  }

  async function loadCharacterDatabaseResults(append) {
    const resultsEl = document.getElementById("character-database-results");
    const metaEl = document.getElementById("character-database-meta");
    if (!resultsEl) return;
    const tbody = resultsEl.querySelector("tbody");
    if (!append) {
      if (tbody) tbody.innerHTML = "";
      characterDatabaseState.page = 1;
      characterDatabaseState.hasMore = true;
    }
    if (characterDatabaseState.isLoading) return;
    characterDatabaseState.isLoading = true;

    // Show inline loading indicator at the sentinel while fetching.
    const sentinel = document.getElementById("character-database-sentinel");
    if (sentinel) sentinel.innerHTML = '<div class="character-database-loading-more">加载中…</div>';

    const params = new URLSearchParams();
    params.set("q", characterDatabaseState.q);
    if (characterDatabaseState.copyright)
      params.set("copyright", characterDatabaseState.copyright);
    params.set("sort", characterDatabaseState.sort);
    params.set("page", String(characterDatabaseState.page));
    params.set("page_size", String(characterDatabaseState.pageSize));
    try {
      const payload = await request(
        `/api/character-database/search?${params.toString()}`
      );
      const items = Array.isArray(payload.items) ? payload.items : [];
      characterDatabaseState.total = payload.total || 0;
      const loadedCount = (append && tbody ? tbody.children.length : 0) + items.length;
      characterDatabaseState.hasMore = loadedCount < characterDatabaseState.total && items.length > 0;
      if (metaEl) {
        metaEl.textContent = `共 ${characterDatabaseState.total} 个角色 · 已加载 ${loadedCount} 条`;
      }
      if (!append && !items.length) {
        resultsEl.innerHTML = '<div class="character-database-empty">未找到匹配的角色</div>';
        return;
      }
      if (tbody) {
        const rowsHtml = items.map(renderCharacterDatabaseRow).join("");
        tbody.insertAdjacentHTML("beforeend", rowsHtml);
      }
      if (sentinel) {
        sentinel.innerHTML = characterDatabaseState.hasMore
          ? ""
          : (characterDatabaseState.total > 0 ? '<div class="character-database-end">已全部加载</div>' : "");
      }
    } catch (error) {
      if (sentinel) {
        sentinel.innerHTML = `<div class="character-database-loading-error">加载失败：${escapeHtml(error.message)}</div>`;
      } else if (!append) {
        resultsEl.innerHTML = `<div class="character-database-empty">加载失败：${escapeHtml(error.message)}</div>`;
      }
    } finally {
      characterDatabaseState.isLoading = false;
    }
  }

  function renderCharacterDatabaseRow(item) {
    const character = escapeHtml(item.character || item.name || "");
    const copyright = escapeHtml(item.copyright || item.series || "");
    const trigger = escapeHtml(item.trigger || item.trigger_words || "");
    const coreTagsRaw = item.core_tags || item.coreTags || [];
    const coreTags = escapeHtml(
      Array.isArray(coreTagsRaw) ? coreTagsRaw.join(" ") : coreTagsRaw || ""
    );
    const count = escapeHtml(String(item.count ?? item.tag_count ?? ""));
    const danbooruUrl =
      item.danbooru_url ||
      (item.character
        ? `https://danbooru.donmai.us/posts?tags=${encodeURIComponent(item.character)}`
        : "");
    const danbooruLink = danbooruUrl
      ? `<a class="character-database-link" href="${escapeHtml(danbooruUrl)}" target="_blank" rel="noopener noreferrer">查看</a>`
      : "—";
    return `<tr>
      <td class="character-database-name">${character}</td>
      <td>${copyright}</td>
      <td>${trigger}</td>
      <td>${coreTags}</td>
      <td>${count}</td>
      <td>${danbooruLink}</td>
    </tr>`;
  }

  const materialTypes = {
    composition: { label: "构图", code: "CO" },
    expression: { label: "表情", code: "EX" },
    scene: { label: "场景", code: "SC" },
    lighting: { label: "光线", code: "LI" },
    prompt: { label: "提示词", code: "PR" },
    composite_template: { label: "复合模板", code: "TM" },
  };

  const materialListState = {
    q: "",
    materialType: "",
    validationStatus: "",
    tag: "",
    sort: "updated_desc",
    limit: 60,
    offset: 0,
    total: 0,
    items: [],
    loading: false,
    requestId: 0,
    searchTimer: null,
    tagTimer: null,
    tagRequestIds: {},
  };

  const materialDetailState = {
    material: null,
    snapshot: "",
    previewFile: null,
    removePreview: false,
    objectUrl: null,
    dirty: false,
  };

  let materialCreateObjectUrl = null;

  function materialTypeInfo(type) {
    return materialTypes[type] || { label: type || "素材", code: "MT" };
  }

  function materialDate(value, includeTime = false) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "刚刚";
    return date.toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      ...(includeTime ? { hour: "2-digit", minute: "2-digit" } : {}),
    });
  }

  function materialCard(item) {
    const type = materialTypeInfo(item.material_type);
    const tags = Array.isArray(item.tags) ? item.tags : [];
    const visibleTags = tags.slice(0, 3);
    const extraTags = Math.max(0, tags.length - visibleTags.length);
    const image = item.thumbnail_url
      ? `<img src="${escapeHtml(item.thumbnail_url)}" alt="" loading="lazy" decoding="async" />`
      : "";
    return `
      <article
        class="material-card real-material-card"
        data-material-id="${escapeHtml(item.id)}"
        tabindex="0"
        role="button"
        aria-label="打开素材 ${escapeHtml(item.name)}"
      >
        <div class="material-card-preview type-${escapeHtml(item.material_type)}">
          ${image}
          ${image ? "" : `<span class="material-card-preview-code">${escapeHtml(type.code)}</span>`}
          <button
            class="material-card-menu"
            type="button"
            data-api-action="delete-material"
            data-material-id="${escapeHtml(item.id)}"
            data-material-name="${escapeHtml(item.name)}"
            aria-label="删除素材 ${escapeHtml(item.name)}"
            title="删除素材"
          >•••</button>
        </div>
        <div class="material-card-body">
          <div class="material-card-head">
            <span class="material-name">${escapeHtml(item.name)}</span>
            <span class="material-type-badge">${escapeHtml(type.label)}</span>
          </div>
          <div class="material-desc">${escapeHtml(item.description || "暂无简介")}</div>
          <div class="material-card-tags">
            ${visibleTags.map((tag) => `<span class="material-mini-tag">${escapeHtml(tag)}</span>`).join("")}
            ${extraTags ? `<span class="material-mini-tag">+${extraTags}</span>` : ""}
          </div>
          <div class="material-footer">
            <span class="material-validation-badge ${item.validation_status === "verified" ? "verified" : "unverified"}">
              ${item.validation_status === "verified" ? "已验证" : "未验证"}
            </span>
            <span class="material-card-time">${escapeHtml(materialDate(item.updated_at))}</span>
          </div>
        </div>
      </article>
    `;
  }

  function materialBackendMissingState() {
    return `
      <section class="material-list-state backend-missing">
        <span class="material-state-icon">API</span>
        <h2>素材库后端尚未完成</h2>
        <p>前端页面已经准备好。编程 AI 完成素材接口后，这里会自动显示真实素材，不需要重新制作页面。</p>
        <button class="btn soft" type="button" data-api-action="retry-materials">重新连接</button>
      </section>
    `;
  }

  function materialEmptyState(filtered) {
    return `
      <section class="material-list-state">
        <span class="material-state-icon">MT</span>
        <h2>${filtered ? "没有匹配的素材" : "还没有素材"}</h2>
        <p>${
          filtered
            ? "尝试清除搜索词或筛选条件。"
            : "创建第一个可复用素材，保存构图、表情、场景、光线或提示词内容。"
        }</p>
        <button class="btn ${filtered ? "soft" : "primary"}" type="button" data-api-action="${
          filtered ? "clear-material-filters" : "open-material-modal"
        }">${filtered ? "清除筛选" : "新建素材"}</button>
      </section>
    `;
  }

  function materialRequestIsMissing(error) {
    if (!error) return false;
    if (Number(error.status) === 405) return true;
    if (Number(error.status) !== 404) return false;
    const detail = String(error.payload?.detail || error.message || "").trim().toLowerCase();
    return !detail || detail === "not found" || detail === "请求失败（404）";
  }

  function bindMaterialLibraryControls() {
    const runtime = document.querySelector(".material-library-runtime");
    if (!runtime || runtime.dataset.bound) return;
    runtime.dataset.bound = "1";

    const search = document.getElementById("material-search-input");
    const status = document.getElementById("material-status-filter");
    const tag = document.getElementById("material-tag-filter");
    const sort = document.getElementById("material-sort-filter");

    search?.addEventListener("input", () => {
      clearTimeout(materialListState.searchTimer);
      materialListState.searchTimer = setTimeout(() => {
        materialListState.q = search.value.trim();
        loadMaterials(false);
      }, 300);
    });

    status?.addEventListener("change", () => {
      materialListState.validationStatus = status.value;
      loadMaterials(false);
    });

    sort?.addEventListener("change", () => {
      materialListState.sort = sort.value;
      loadMaterials(false);
    });

    const scheduleTagWork = () => {
      clearTimeout(materialListState.tagTimer);
      materialListState.tagTimer = setTimeout(() => {
        materialListState.tag = tag.value.trim();
        loadMaterialTagSuggestions(tag.value, "material-tag-filter-options");
        loadMaterials(false);
      }, 300);
    };
    tag?.addEventListener("input", scheduleTagWork);
    tag?.addEventListener("change", scheduleTagWork);
    tag?.addEventListener("focus", () => {
      loadMaterialTagSuggestions(tag.value, "material-tag-filter-options");
    });

    document.getElementById("material-type-filters")?.addEventListener("click", (event) => {
      const button = event.target.closest("[data-material-type]");
      if (!button) return;
      runtime.querySelectorAll("[data-material-type]").forEach((item) => {
        item.classList.toggle("active", item === button);
      });
      materialListState.materialType = button.dataset.materialType || "";
      loadMaterials(false);
    });
  }

  async function renderMaterialsPage() {
    bindMaterialLibraryControls();
    await loadMaterials(false);
  }

  async function loadMaterials(append) {
    const grid = document.getElementById("material-grid");
    const summary = document.getElementById("material-library-summary");
    const loadMoreWrap = document.getElementById("material-load-more-wrap");
    if (!grid || (append && materialListState.loading)) return;

    materialListState.loading = true;
    const requestId = materialListState.requestId + 1;
    materialListState.requestId = requestId;
    if (!append) {
      materialListState.offset = 0;
      materialListState.items = [];
      grid.innerHTML = '<div class="material-list-loading">正在读取素材库…</div>';
      if (summary) summary.textContent = "";
      if (loadMoreWrap) loadMoreWrap.hidden = true;
    } else {
      const button = loadMoreWrap?.querySelector("button");
      if (button) {
        button.disabled = true;
        button.textContent = "正在加载…";
      }
    }

    const params = new URLSearchParams();
    if (materialListState.q) params.set("q", materialListState.q);
    if (materialListState.materialType) {
      params.set("material_type", materialListState.materialType);
    }
    if (materialListState.validationStatus) {
      params.set("validation_status", materialListState.validationStatus);
    }
    if (materialListState.tag) params.set("tag", materialListState.tag);
    params.set("sort", materialListState.sort);
    params.set("limit", String(materialListState.limit));
    params.set("offset", String(append ? materialListState.items.length : 0));

    try {
      const payload = await request(`/api/materials?${params.toString()}`);
      if (requestId !== materialListState.requestId) return;
      const incoming = Array.isArray(payload.items) ? payload.items : [];
      materialListState.items = append
        ? materialListState.items.concat(incoming)
        : incoming;
      materialListState.total = Number(payload.total || 0);
      materialListState.offset = materialListState.items.length;

      const filtered = Boolean(
        materialListState.q ||
        materialListState.materialType ||
        materialListState.validationStatus ||
        materialListState.tag
      );
      grid.innerHTML = materialListState.items.length
        ? materialListState.items.map(materialCard).join("")
        : materialEmptyState(filtered);
      if (summary) {
        summary.textContent = materialListState.total
          ? `共 ${materialListState.total} 个素材 · 已加载 ${materialListState.items.length} 个`
          : "";
      }
      const hasMore =
        Boolean(payload.has_more) ||
        materialListState.items.length < materialListState.total;
      if (loadMoreWrap) {
        loadMoreWrap.hidden = !hasMore;
        const button = loadMoreWrap.querySelector("button");
        if (button) {
          button.disabled = false;
          button.textContent = "加载更多";
        }
      }
    } catch (error) {
      if (requestId !== materialListState.requestId) return;
      grid.innerHTML = materialRequestIsMissing(error)
        ? materialBackendMissingState()
        : `
          <section class="material-list-state">
            <span class="material-state-icon">!</span>
            <h2>素材库加载失败</h2>
            <p>${escapeHtml(error.message)}</p>
            <button class="btn soft" type="button" data-api-action="retry-materials">重试</button>
          </section>
        `;
      if (summary) summary.textContent = "";
      if (loadMoreWrap) loadMoreWrap.hidden = true;
    } finally {
      if (requestId === materialListState.requestId) {
        materialListState.loading = false;
      }
    }
  }

  async function loadMaterialTagSuggestions(query, datalistId) {
    const list = document.getElementById(datalistId);
    if (!list) return;
    const requestId = (materialListState.tagRequestIds[datalistId] || 0) + 1;
    materialListState.tagRequestIds[datalistId] = requestId;
    const params = new URLSearchParams({
      q: String(query || "").trim(),
      limit: "30",
    });
    try {
      const payload = await request(`/api/material-tags?${params.toString()}`);
      if (requestId !== materialListState.tagRequestIds[datalistId]) return;
      const items = Array.isArray(payload.items) ? payload.items : [];
      list.innerHTML = items.map((item) => {
        const name = typeof item === "string" ? item : item.name || "";
        return `<option value="${escapeHtml(name)}"></option>`;
      }).join("");
    } catch (error) {
      if (requestId === materialListState.tagRequestIds[datalistId]) {
        list.innerHTML = "";
      }
    }
  }

  function resetMaterialFilters() {
    materialListState.q = "";
    materialListState.materialType = "";
    materialListState.validationStatus = "";
    materialListState.tag = "";
    materialListState.sort = "updated_desc";
    const search = document.getElementById("material-search-input");
    const status = document.getElementById("material-status-filter");
    const tag = document.getElementById("material-tag-filter");
    const sort = document.getElementById("material-sort-filter");
    if (search) search.value = "";
    if (status) status.value = "";
    if (tag) tag.value = "";
    if (sort) sort.value = "updated_desc";
    document.querySelectorAll("[data-material-type]").forEach((button) => {
      button.classList.toggle("active", !button.dataset.materialType);
    });
    loadMaterials(false);
  }

  function materialTypeOptions(selected) {
    return Object.entries(materialTypes).map(([value, meta]) => (
      `<option value="${value}" ${value === selected ? "selected" : ""}>${escapeHtml(meta.label)}</option>`
    )).join("");
  }

  function materialTagsEditor(id, tags = []) {
    return `
      <div class="material-tags-editor" id="${escapeHtml(id)}" data-tags="${escapeHtml(JSON.stringify(tags))}">
        <div class="material-tags-list"></div>
        <input
          class="material-tag-editor-input"
          type="text"
          maxlength="40"
          list="${escapeHtml(id)}-options"
          placeholder="输入标签后按回车"
          autocomplete="off"
        />
        <datalist id="${escapeHtml(id)}-options"></datalist>
      </div>
    `;
  }

  function getMaterialEditorTags(editor) {
    if (!editor) return [];
    try {
      const tags = JSON.parse(editor.dataset.tags || "[]");
      return Array.isArray(tags) ? tags : [];
    } catch (error) {
      return [];
    }
  }

  function renderMaterialEditorTags(editor) {
    const list = editor?.querySelector(".material-tags-list");
    if (!list) return;
    list.innerHTML = getMaterialEditorTags(editor).map((tag) => `
      <span class="material-tag-chip">
        <span>${escapeHtml(tag)}</span>
        <button class="material-tag-remove" type="button" data-remove-material-tag="${escapeHtml(tag)}" aria-label="删除标签 ${escapeHtml(tag)}">×</button>
      </span>
    `).join("");
  }

  function addMaterialEditorTag(editor, rawTag) {
    if (!editor) return;
    const tag = String(rawTag || "").trim().replace(/\s+/g, " ");
    if (!tag) return;
    const tags = getMaterialEditorTags(editor);
    if (tags.length >= 30) {
      if (typeof showToast === "function") showToast("每个素材最多 30 个标签");
      return;
    }
    if (tags.some((item) => item.toLocaleLowerCase() === tag.toLocaleLowerCase())) {
      return;
    }
    tags.push(tag);
    editor.dataset.tags = JSON.stringify(tags);
    renderMaterialEditorTags(editor);
    editor.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function removeMaterialEditorTag(editor, tag) {
    const tags = getMaterialEditorTags(editor).filter((item) => item !== tag);
    editor.dataset.tags = JSON.stringify(tags);
    renderMaterialEditorTags(editor);
    editor.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function bindMaterialTagsEditor(editor) {
    if (!editor || editor.dataset.bound) return;
    editor.dataset.bound = "1";
    renderMaterialEditorTags(editor);
    const input = editor.querySelector(".material-tag-editor-input");
    const datalistId = input?.getAttribute("list");
    let suggestionTimer = null;
    input?.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === ",") {
        event.preventDefault();
        addMaterialEditorTag(editor, input.value.replace(/,$/, ""));
        input.value = "";
      } else if (event.key === "Backspace" && !input.value) {
        const tags = getMaterialEditorTags(editor);
        if (tags.length) removeMaterialEditorTag(editor, tags[tags.length - 1]);
      }
    });
    input?.addEventListener("change", () => {
      addMaterialEditorTag(editor, input.value);
      input.value = "";
    });
    input?.addEventListener("input", () => {
      clearTimeout(suggestionTimer);
      suggestionTimer = setTimeout(() => {
        loadMaterialTagSuggestions(input.value, datalistId);
      }, 220);
    });
    editor.addEventListener("click", (event) => {
      const remove = event.target.closest("[data-remove-material-tag]");
      if (remove) {
        removeMaterialEditorTag(editor, remove.dataset.removeMaterialTag);
      } else {
        input?.focus();
      }
    });
  }

  function materialPreviewPicker({ idPrefix, previewUrl = "", hasPreview = false }) {
    return `
      <div class="material-preview-picker">
        <div class="material-preview-box" id="${escapeHtml(idPrefix)}-preview-box">
          ${previewUrl ? `<img src="${escapeHtml(previewUrl)}" alt="素材预览" />` : ""}
          <span>${previewUrl ? "" : "可选预览图"}</span>
        </div>
        <div class="material-preview-actions">
          <input id="${escapeHtml(idPrefix)}-preview-file" name="preview_file" type="file" accept="image/jpeg,image/png,image/webp" />
          <span class="material-field-help">JPG、PNG 或 WebP，最大 20 MB。列表只加载缩略图。</span>
          <button
            class="btn small soft"
            type="button"
            data-api-action="remove-material-preview"
            data-preview-target="${escapeHtml(idPrefix)}"
            ${hasPreview ? "" : "hidden"}
          >移除预览图</button>
        </div>
      </div>
    `;
  }

  function ensureMaterialCreateModal() {
    let modal = document.getElementById("material-create-modal");
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "material-create-modal";
    modal.className = "atelier-modal-backdrop";
    modal.hidden = true;
    modal.innerHTML = `
      <section class="atelier-modal material-editor-modal" role="dialog" aria-modal="true" aria-labelledby="material-create-title">
        <div class="material-modal-header">
          <div class="atelier-modal-icon">MT</div>
          <div class="material-modal-heading">
            <h2 id="material-create-title">新建素材</h2>
            <p>保存一个可以反复使用的内容积木。</p>
          </div>
          <button class="material-modal-close" type="button" data-api-action="close-material-modal" aria-label="关闭">×</button>
        </div>
        <div class="material-editor-scroll">
          <form id="material-create-form" class="material-editor-grid">
            <label class="material-field">
              名称
              <input class="modal-input" name="name" maxlength="80" autocomplete="off" placeholder="输入素材名称" required />
            </label>
            <label class="material-field">
              类型
              <select class="modal-input" name="material_type">${materialTypeOptions("composition")}</select>
            </label>
            <label class="material-field wide">
              简介
              <textarea class="modal-input material-textarea" name="description" maxlength="300" placeholder="一句话说明这个素材适合什么画面"></textarea>
            </label>
            <label class="material-field wide">
              素材正文
              <textarea class="modal-input material-textarea content" name="content" maxlength="50000" placeholder="填写人工阅读和编辑的素材内容" required></textarea>
            </label>
            <label class="material-field wide">
              提示词内容
              <textarea class="modal-input material-textarea" name="prompt_text" maxlength="50000" placeholder="可选：实际用于生成的提示词或标签串"></textarea>
            </label>
            <label class="material-field wide">
              负面提示词
              <textarea class="modal-input material-textarea" name="negative_prompt" maxlength="20000" placeholder="可选：只填写与该素材直接相关的排除内容"></textarea>
            </label>
            <div class="material-field wide">
              标签
              ${materialTagsEditor("material-create-tags")}
              <span class="material-field-help">回车添加；服装、动作、道具等可先作为标签管理。</span>
            </div>
            <label class="material-field">
              验证状态
              <select class="modal-input" name="validation_status">
                <option value="unverified">未验证</option>
                <option value="verified">已验证</option>
              </select>
            </label>
            <label class="material-field wide">
              备注
              <textarea class="modal-input material-textarea" name="notes" maxlength="5000" placeholder="可选：记录适用条件或测试结论"></textarea>
            </label>
            <div class="material-field wide">
              预览图
              ${materialPreviewPicker({ idPrefix: "material-create" })}
            </div>
            <div class="modal-error wide" role="alert"></div>
            <div class="material-editor-actions">
              <button class="btn" type="button" data-api-action="close-material-modal">取消</button>
              <button class="btn primary" type="submit">创建素材</button>
            </div>
          </form>
        </div>
      </section>
    `;
    document.body.appendChild(modal);
    modal.addEventListener("click", (event) => {
      if (event.target === modal) closeMaterialCreateModal();
    });
    modal.querySelector("form").addEventListener("submit", submitMaterialCreate);
    const tagEditor = modal.querySelector("#material-create-tags");
    bindMaterialTagsEditor(tagEditor);
    modal.querySelector("#material-create-preview-file")?.addEventListener("change", (event) => {
      previewMaterialFile(
        event.target.files?.[0],
        "material-create",
        (url) => {
          if (materialCreateObjectUrl) URL.revokeObjectURL(materialCreateObjectUrl);
          materialCreateObjectUrl = url;
        }
      );
    });
    return modal;
  }

  function openMaterialCreateModal() {
    const modal = ensureMaterialCreateModal();
    const form = modal.querySelector("form");
    form.reset();
    const editor = form.querySelector("#material-create-tags");
    editor.dataset.tags = "[]";
    renderMaterialEditorTags(editor);
    const box = form.querySelector("#material-create-preview-box");
    if (box) box.innerHTML = "<span>可选预览图</span>";
    form.querySelector('[data-api-action="remove-material-preview"]').hidden = true;
    form.querySelector(".modal-error").textContent = "";
    if (materialCreateObjectUrl) {
      URL.revokeObjectURL(materialCreateObjectUrl);
      materialCreateObjectUrl = null;
    }
    modal.hidden = false;
    requestAnimationFrame(() => modal.classList.add("show"));
    setTimeout(() => form.elements.name.focus(), 60);
  }

  function closeMaterialCreateModal() {
    const modal = document.getElementById("material-create-modal");
    if (!modal || modal.hidden) return;
    modal.classList.remove("show");
    setTimeout(() => {
      modal.hidden = true;
      if (materialCreateObjectUrl) {
        URL.revokeObjectURL(materialCreateObjectUrl);
        materialCreateObjectUrl = null;
      }
    }, 150);
  }

  function materialPayloadFromForm(form) {
    const editor = form.querySelector(".material-tags-editor");
    return {
      name: form.elements.name.value.trim().replace(/\s+/g, " "),
      material_type: form.elements.material_type.value,
      description: form.elements.description.value.trim(),
      content: form.elements.content.value,
      prompt_text: form.elements.prompt_text.value,
      negative_prompt: form.elements.negative_prompt.value,
      validation_status: form.elements.validation_status.value,
      notes: form.elements.notes.value,
      tags: getMaterialEditorTags(editor),
    };
  }

  function validateMaterialPreviewFile(file) {
    if (!file) return "";
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      return "预览图只支持 JPG、PNG 或 WebP。";
    }
    if (file.size > 20 * 1024 * 1024) {
      return "预览图不能超过 20 MB。";
    }
    return "";
  }

  function previewMaterialFile(file, targetPrefix, rememberUrl) {
    const error = validateMaterialPreviewFile(file);
    const modalError = document.querySelector(
      targetPrefix === "material-create"
        ? "#material-create-form .modal-error"
        : "#material-detail-form .material-detail-save-status"
    );
    if (error) {
      if (modalError) {
        modalError.textContent = error;
        modalError.classList.add("error");
      }
      return false;
    }
    if (!file) return true;
    const url = URL.createObjectURL(file);
    rememberUrl(url);
    const box = document.getElementById(`${targetPrefix}-preview-box`);
    if (box) box.innerHTML = `<img src="${escapeHtml(url)}" alt="待上传的素材预览" />`;
    const remove = document.querySelector(
      `[data-api-action="remove-material-preview"][data-preview-target="${targetPrefix}"]`
    );
    if (remove) remove.hidden = false;
    return true;
  }

  async function uploadMaterialPreview(materialId, file) {
    const formData = new FormData();
    formData.append("file", file);
    return request(`/api/materials/${materialId}/preview`, {
      method: "POST",
      body: formData,
    });
  }

  async function submitMaterialCreate(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const submit = form.querySelector('button[type="submit"]');
    const error = form.querySelector(".modal-error");
    const payload = materialPayloadFromForm(form);
    const file = form.elements.preview_file.files?.[0] || null;
    if (!payload.name) {
      error.textContent = "请输入素材名称。";
      form.elements.name.focus();
      return;
    }
    if (!payload.content.trim()) {
      error.textContent = "请填写素材正文。";
      form.elements.content.focus();
      return;
    }
    const fileError = validateMaterialPreviewFile(file);
    if (fileError) {
      error.textContent = fileError;
      return;
    }

    submit.disabled = true;
    submit.textContent = "正在创建…";
    error.textContent = "";
    try {
      const result = await request("/api/materials", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      const material = result.material || result;
      if (file) {
        try {
          await uploadMaterialPreview(material.id, file);
        } catch (uploadError) {
          if (typeof showToast === "function") {
            showToast(`素材已创建，但预览图上传失败：${uploadError.message}`);
          }
        }
      }
      closeMaterialCreateModal();
      if (typeof showToast === "function") showToast(`素材「${payload.name}」已创建`);
      navigateToMaterialDetail(material.id);
    } catch (requestError) {
      error.textContent = materialRequestIsMissing(requestError)
        ? "素材库后端尚未完成，暂时无法创建。"
        : requestError.message;
      form.elements.name.focus();
    } finally {
      submit.disabled = false;
      submit.textContent = "创建素材";
    }
  }

  function navigateToMaterialDetail(materialId) {
    const params = new URLSearchParams();
    params.set("page", "material-detail");
    params.set("material", materialId);
    window.location.search = `?${params.toString()}`;
  }

  function navigateToMaterials() {
    window.location.search = "?page=materials";
  }

  function resetMaterialDetailState() {
    if (materialDetailState.objectUrl) {
      URL.revokeObjectURL(materialDetailState.objectUrl);
    }
    materialDetailState.material = null;
    materialDetailState.snapshot = "";
    materialDetailState.previewFile = null;
    materialDetailState.removePreview = false;
    materialDetailState.objectUrl = null;
    materialDetailState.dirty = false;
  }

  function materialDetailForm(material) {
    const type = materialTypeInfo(material.material_type);
    const previewUrl = material.preview_url || material.thumbnail_url || "";
    return `
      <div class="material-detail-layout">
        <aside class="material-detail-preview-panel">
          <div class="material-detail-preview-large type-${escapeHtml(material.material_type)}" id="material-detail-preview-box">
            ${previewUrl ? `<img src="${escapeHtml(previewUrl)}" alt="${escapeHtml(material.name)}" />` : ""}
            ${previewUrl ? "" : `<span class="material-card-preview-code">${escapeHtml(type.code)}</span>`}
          </div>
          <div class="material-detail-preview-meta">
            <span class="material-type-badge">${escapeHtml(type.label)}</span>
            <span class="material-validation-badge ${material.validation_status === "verified" ? "verified" : "unverified"}">
              ${material.validation_status === "verified" ? "已验证" : "未验证"}
            </span>
          </div>
          <div class="material-detail-timestamps">
            创建：${escapeHtml(materialDate(material.created_at, true))}<br />
            修改：${escapeHtml(materialDate(material.updated_at, true))}
          </div>
        </aside>
        <section class="material-detail-form-panel">
          <form id="material-detail-form" class="material-editor-grid">
            <label class="material-field">
              名称
              <input class="modal-input" name="name" maxlength="80" value="${escapeHtml(material.name)}" required />
            </label>
            <label class="material-field">
              类型
              <select class="modal-input" name="material_type">${materialTypeOptions(material.material_type)}</select>
            </label>
            <label class="material-field wide">
              简介
              <textarea class="modal-input material-textarea" name="description" maxlength="300">${escapeHtml(material.description || "")}</textarea>
            </label>
            <label class="material-field wide">
              素材正文
              <textarea class="modal-input material-textarea content" name="content" maxlength="50000" required>${escapeHtml(material.content || "")}</textarea>
            </label>
            <label class="material-field wide">
              提示词内容
              <textarea class="modal-input material-textarea" name="prompt_text" maxlength="50000">${escapeHtml(material.prompt_text || "")}</textarea>
            </label>
            <label class="material-field wide">
              负面提示词
              <textarea class="modal-input material-textarea" name="negative_prompt" maxlength="20000">${escapeHtml(material.negative_prompt || "")}</textarea>
            </label>
            <div class="material-field wide">
              标签
              ${materialTagsEditor("material-detail-tags", Array.isArray(material.tags) ? material.tags : [])}
            </div>
            <label class="material-field">
              验证状态
              <select class="modal-input" name="validation_status">
                <option value="unverified" ${material.validation_status !== "verified" ? "selected" : ""}>未验证</option>
                <option value="verified" ${material.validation_status === "verified" ? "selected" : ""}>已验证</option>
              </select>
            </label>
            <label class="material-field wide">
              备注
              <textarea class="modal-input material-textarea" name="notes" maxlength="5000">${escapeHtml(material.notes || "")}</textarea>
            </label>
            <div class="material-field wide">
              预览图
              ${materialPreviewPicker({
                idPrefix: "material-detail",
                previewUrl,
                hasPreview: Boolean(previewUrl),
              })}
            </div>
            <div class="material-editor-actions">
              <span class="material-detail-save-status" role="status"></span>
            </div>
          </form>
        </section>
      </div>
    `;
  }

  function materialComparablePayload(payload) {
    return {
      ...payload,
      tags: [...(payload.tags || [])].map((tag) => tag.trim()).sort((a, b) => a.localeCompare(b)),
    };
  }

  function updateMaterialDetailDirty() {
    const form = document.getElementById("material-detail-form");
    const save = document.getElementById("material-detail-save");
    if (!form || !materialDetailState.material) return;
    const current = JSON.stringify(materialComparablePayload(materialPayloadFromForm(form)));
    materialDetailState.dirty = Boolean(
      current !== materialDetailState.snapshot ||
      materialDetailState.previewFile ||
      materialDetailState.removePreview
    );
    if (save) save.disabled = !materialDetailState.dirty;
    const status = form.querySelector(".material-detail-save-status");
    if (status && materialDetailState.dirty && !status.classList.contains("error")) {
      status.textContent = "有未保存修改";
      status.className = "material-detail-save-status";
    }
  }

  async function renderMaterialDetailPage() {
    resetMaterialDetailState();
    const runtime = document.getElementById("material-detail-runtime");
    const save = document.getElementById("material-detail-save");
    const remove = document.querySelector('[data-api-action="delete-current-material"]');
    if (!runtime) return;
    if (save) save.disabled = true;
    if (remove) remove.disabled = true;
    const materialId = new URLSearchParams(window.location.search).get("material");
    if (!materialId) {
      runtime.innerHTML = `
        <section class="material-detail-state">
          <span class="material-state-icon">?</span>
          <h2>没有指定素材</h2>
          <p>请从素材库打开一张素材卡片。</p>
          <button class="btn soft" type="button" data-api-action="back-to-materials">返回素材库</button>
        </section>
      `;
      return;
    }
    runtime.innerHTML = '<div class="material-detail-loading">正在读取素材详情…</div>';
    try {
      const payload = await request(`/api/materials/${materialId}`);
      const material = payload.material || payload;
      materialDetailState.material = material;
      runtime.innerHTML = materialDetailForm(material);
      const form = document.getElementById("material-detail-form");
      bindMaterialTagsEditor(form.querySelector("#material-detail-tags"));
      materialDetailState.snapshot = JSON.stringify(
        materialComparablePayload(materialPayloadFromForm(form))
      );
      form.addEventListener("input", updateMaterialDetailDirty);
      form.addEventListener("change", updateMaterialDetailDirty);
      form.addEventListener("submit", submitMaterialDetail);
      form.querySelector("#material-detail-preview-file")?.addEventListener("change", (event) => {
        const file = event.target.files?.[0] || null;
        if (!file) return;
        const valid = previewMaterialFile(file, "material-detail", (url) => {
          if (materialDetailState.objectUrl) URL.revokeObjectURL(materialDetailState.objectUrl);
          materialDetailState.objectUrl = url;
        });
        if (valid) {
          materialDetailState.previewFile = file;
          materialDetailState.removePreview = false;
          updateMaterialDetailDirty();
        }
      });
      if (remove) {
        remove.disabled = false;
        remove.dataset.materialId = material.id;
        remove.dataset.materialName = material.name;
      }
      const heading = document.querySelector(".page-header h1");
      if (heading) heading.textContent = `素材详情 · ${material.name}`;
    } catch (error) {
      if (materialRequestIsMissing(error)) {
        runtime.innerHTML = `
          <section class="material-detail-state backend-missing">
            <span class="material-state-icon">API</span>
            <h2>素材库后端尚未完成</h2>
            <p>前端详情页已经准备好，等待编程 AI 完成素材详情接口。</p>
            <button class="btn soft" type="button" data-api-action="back-to-materials">返回素材库</button>
          </section>
        `;
      } else if (Number(error.status) === 404) {
        runtime.innerHTML = `
          <section class="material-detail-state">
            <span class="material-state-icon">?</span>
            <h2>素材不存在</h2>
            <p>该素材可能已经被删除，请返回素材库重新选择。</p>
            <button class="btn soft" type="button" data-api-action="back-to-materials">返回素材库</button>
          </section>
        `;
      } else {
        runtime.innerHTML = `
          <section class="material-detail-state">
            <span class="material-state-icon">!</span>
            <h2>素材详情加载失败</h2>
            <p>${escapeHtml(error.message)}</p>
            <button class="btn soft" type="button" data-api-action="back-to-materials">返回素材库</button>
          </section>
        `;
      }
    }
  }

  function materialChangedFields(current, original) {
    const updates = {};
    Object.keys(current).forEach((key) => {
      if (JSON.stringify(current[key]) !== JSON.stringify(original[key])) {
        updates[key] = current[key];
      }
    });
    return updates;
  }

  async function submitMaterialDetail(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const save = document.getElementById("material-detail-save");
    const status = form.querySelector(".material-detail-save-status");
    const current = materialPayloadFromForm(form);
    const original = {
      name: materialDetailState.material.name,
      material_type: materialDetailState.material.material_type,
      description: materialDetailState.material.description || "",
      content: materialDetailState.material.content || "",
      prompt_text: materialDetailState.material.prompt_text || "",
      negative_prompt: materialDetailState.material.negative_prompt || "",
      validation_status: materialDetailState.material.validation_status || "unverified",
      notes: materialDetailState.material.notes || "",
      tags: Array.isArray(materialDetailState.material.tags) ? materialDetailState.material.tags : [],
    };
    if (!current.name || !current.content.trim()) {
      status.textContent = !current.name ? "名称不能为空" : "素材正文不能为空";
      status.className = "material-detail-save-status error";
      return;
    }
    save.disabled = true;
    save.textContent = "保存中…";
    status.textContent = "";
    status.className = "material-detail-save-status";
    try {
      const updates = materialChangedFields(current, original);
      if (Object.keys(updates).length) {
        await request(`/api/materials/${materialDetailState.material.id}`, {
          method: "PATCH",
          body: JSON.stringify(updates),
        });
      }
      if (materialDetailState.removePreview) {
        await request(`/api/materials/${materialDetailState.material.id}/preview`, {
          method: "DELETE",
        });
      } else if (materialDetailState.previewFile) {
        await uploadMaterialPreview(
          materialDetailState.material.id,
          materialDetailState.previewFile
        );
      }
      materialDetailState.dirty = false;
      if (typeof showToast === "function") showToast("素材已保存");
      await renderMaterialDetailPage();
    } catch (error) {
      status.textContent = error.message;
      status.className = "material-detail-save-status error";
      save.disabled = false;
    } finally {
      save.textContent = "保存修改";
    }
  }

  function removePendingMaterialPreview(targetPrefix) {
    const box = document.getElementById(`${targetPrefix}-preview-box`);
    const file = document.getElementById(`${targetPrefix}-preview-file`);
    const button = document.querySelector(
      `[data-api-action="remove-material-preview"][data-preview-target="${targetPrefix}"]`
    );
    if (file) file.value = "";
    if (box) box.innerHTML = "<span>无预览图</span>";
    if (button) button.hidden = true;
    if (targetPrefix === "material-create") {
      if (materialCreateObjectUrl) URL.revokeObjectURL(materialCreateObjectUrl);
      materialCreateObjectUrl = null;
    } else {
      if (materialDetailState.objectUrl) URL.revokeObjectURL(materialDetailState.objectUrl);
      materialDetailState.objectUrl = null;
      materialDetailState.previewFile = null;
      materialDetailState.removePreview = Boolean(
        materialDetailState.material?.preview_url ||
        materialDetailState.material?.thumbnail_url
      );
      updateMaterialDetailDirty();
    }
  }

  async function deleteMaterial(materialId, materialName, fromDetail = false) {
    const confirmed = await confirmDialog({
      title: "删除素材",
      message: `确定删除素材「${materialName}」吗？素材正文、标签关联和预览图都会被删除。`,
      confirmText: "删除",
      danger: true,
    });
    if (!confirmed) return;
    try {
      await request(`/api/materials/${materialId}`, { method: "DELETE" });
      if (typeof showToast === "function") showToast(`素材「${materialName}」已删除`);
      if (fromDetail) {
        materialDetailState.dirty = false;
        navigateToMaterials();
      } else {
        await loadMaterials(false);
      }
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    }
  }

  async function leaveMaterialDetail() {
    if (materialDetailState.dirty) {
      const confirmed = await confirmDialog({
        title: "放弃未保存修改",
        message: "当前素材还有未保存的修改，确定返回素材库吗？",
        confirmText: "放弃修改",
        danger: true,
      });
      if (!confirmed) return;
      materialDetailState.dirty = false;
    }
    navigateToMaterials();
  }

  function ensureCharacterDetailModal() {
    let modal = document.getElementById("character-detail-modal");
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "character-detail-modal";
    modal.className = "atelier-modal-backdrop";
    modal.hidden = true;
    modal.innerHTML = `
      <section class="atelier-modal character-detail-modal size-lg" role="dialog" aria-modal="true">
        <div class="character-detail-modal-body" id="character-detail-modal-body"></div>
      </section>
    `;
    document.body.appendChild(modal);
    modal.addEventListener("click", (event) => {
      if (event.target === modal) closeCharacterDetailModal();
    });
    return modal;
  }

  let confirmDialogResolver = null;
  function confirmDialog({ title, message, confirmText = "确认", cancelText = "取消", danger = true }) {
    closeConfirmDialog();
    let modal = document.getElementById("confirm-dialog");
    if (!modal) {
      modal = document.createElement("div");
      modal.id = "confirm-dialog";
      modal.className = "atelier-modal-backdrop";
      modal.hidden = true;
      modal.innerHTML = `
        <section class="atelier-modal size-sm confirm-dialog" role="dialog" aria-modal="true">
          <div class="confirm-icon">!</div>
          <h2 id="confirm-dialog-title"></h2>
          <p id="confirm-dialog-message"></p>
          <div class="confirm-actions">
            <button type="button" class="btn" data-confirm-action="cancel"></button>
            <button type="button" class="btn primary" data-confirm-action="confirm"></button>
          </div>
        </section>
      `;
      document.body.appendChild(modal);
      modal.addEventListener("click", (event) => {
        if (event.target === modal) resolveConfirmDialog(false);
      });
      modal.querySelectorAll("[data-confirm-action]").forEach((btn) => {
        btn.addEventListener("click", () => {
          resolveConfirmDialog(btn.dataset.confirmAction === "confirm");
        });
      });
    }
    modal.querySelector("#confirm-dialog-title").textContent = title || "请确认";
    modal.querySelector("#confirm-dialog-message").textContent = message || "";
    const confirmBtn = modal.querySelector('[data-confirm-action="confirm"]');
    const cancelBtn = modal.querySelector('[data-confirm-action="cancel"]');
    confirmBtn.textContent = confirmText;
    cancelBtn.textContent = cancelText;
    if (danger) {
      confirmBtn.classList.add("danger");
    } else {
      confirmBtn.classList.remove("danger");
    }
    return new Promise((resolve) => {
      confirmDialogResolver = resolve;
      modal.hidden = false;
      requestAnimationFrame(() => modal.classList.add("show"));
      setTimeout(() => confirmBtn.focus(), 60);
    });
  }

  function resolveConfirmDialog(result) {
    const modal = document.getElementById("confirm-dialog");
    if (!modal || modal.hidden) return;
    modal.classList.remove("show");
    modal.hidden = true;
    const resolver = confirmDialogResolver;
    confirmDialogResolver = null;
    if (resolver) resolver(result);
  }

  function closeConfirmDialog() {
    resolveConfirmDialog(false);
  }

  function openCharacterDetailModal() {
    const modal = ensureCharacterDetailModal();
    modal.hidden = false;
    requestAnimationFrame(() => modal.classList.add("show"));
  }

  function closeCharacterDetailModal() {
    const modal = document.getElementById("character-detail-modal");
    if (!modal) return;
    modal.classList.remove("show");
    setTimeout(() => {
      modal.hidden = true;
      const body = document.getElementById("character-detail-modal-body");
      if (body) body.innerHTML = "";
    }, 150);
  }

  async function renderCharacterDetail(characterId) {
    openCharacterDetailModal();
    const body = document.getElementById("character-detail-modal-body");
    if (body) body.innerHTML = '<div style="padding:24px;text-align:center;color:#8c94a5;">加载中…</div>';
    try {
      const [characterPayload, variantsPayload, specsPayload] = await Promise.all([
        request(`/api/characters/${characterId}`),
        request(`/api/characters/${characterId}/variants`),
        request(`/api/specs`),
      ]);
      const character = characterPayload.character;
      const stats =
        character.stats ||
        characterPayload.stats ||
        { variant_count: variantsPayload.items.length, spec_total: 0, spec_filled: 0 };
      const defaultVariant =
        variantsPayload.items.find((variant) => Number(variant.is_default) === 1) ||
        variantsPayload.items[0];
      body.innerHTML = `
        <div class="character-detail-modal-header">
          <div class="header-thumb"></div>
          <div class="header-name">
            <div class="header-name-text">${escapeHtml(character.name)}</div>
            <div class="header-name-sub">${stats.variant_count} 个变体 · ${specsPayload.total} 个规格 · 规格 ${stats.spec_filled}/${stats.spec_total}</div>
          </div>
          <button class="character-detail-modal-close" type="button" data-api-action="close-character-detail-modal" aria-label="关闭">×</button>
        </div>
        <div class="character-detail-modal-scroll" id="character-detail-modal-scroll">
          ${characterExpandedPanel(character, variantsPayload.items, specsPayload.items)}
        </div>
      `;
      if (defaultVariant) {
        await renderVariantSpecValues(defaultVariant.id, defaultVariant.name);
      }
    } catch (error) {
      body.innerHTML = `<div style="padding:24px;color:#c33;">加载失败：${escapeHtml(error.message)}</div>`;
    }
  }

  async function refreshCharacterDetail() {
    const modal = document.getElementById("character-detail-modal");
    if (!modal || modal.hidden) return;
    const scroll = document.getElementById("character-detail-modal-scroll");
    const characterId = scroll && scroll.querySelector("[data-character-id]")?.dataset.characterId;
    if (characterId) await renderCharacterDetail(characterId);
  }

  function ensureProjectModal() {
    let modal = document.getElementById("new-project-modal");
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "new-project-modal";
    modal.className = "atelier-modal-backdrop";
    modal.hidden = true;
    modal.innerHTML = `
      <section class="atelier-modal" role="dialog" aria-modal="true" aria-labelledby="new-project-title">
        <div class="atelier-modal-icon">PJ</div>
        <h2 id="new-project-title">新建项目</h2>
        <p>现在只需要输入项目名称，其他设置以后用到时再配置。</p>
        <form id="new-project-form">
          <label class="label" for="new-project-name">项目名称</label>
          <input id="new-project-name" class="modal-input" name="name" maxlength="80" autocomplete="off" placeholder="例如：海边度假篇" required />
          <div class="modal-error" id="new-project-error" role="alert"></div>
          <div class="modal-actions">
            <button class="btn" type="button" data-api-action="close-project-modal">取消</button>
            <button class="btn primary" type="submit">创建项目</button>
          </div>
        </form>
      </section>
    `;
    document.body.appendChild(modal);
    modal.addEventListener("click", (event) => {
      if (event.target === modal) closeProjectModal();
    });
    modal.querySelector("form").addEventListener("submit", submitProject);
    return modal;
  }

  function openProjectModal() {
    const modal = ensureProjectModal();
    const error = modal.querySelector(".modal-error");
    const input = modal.querySelector("input");
    error.textContent = "";
    input.value = "";
    modal.hidden = false;
    requestAnimationFrame(() => {
      modal.classList.add("show");
      input.focus();
    });
  }

  function closeProjectModal() {
    const modal = document.getElementById("new-project-modal");
    if (!modal) return;
    modal.classList.remove("show");
    window.setTimeout(() => {
      modal.hidden = true;
    }, 150);
  }

  async function submitProject(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const input = form.querySelector("input");
    const submit = form.querySelector('button[type="submit"]');
    const error = form.querySelector(".modal-error");
    const name = input.value.trim().replace(/\s+/g, " ");
    if (!name) {
      error.textContent = "请输入项目名称。";
      input.focus();
      return;
    }
    submit.disabled = true;
    submit.textContent = "正在创建…";
    error.textContent = "";
    try {
      await request("/api/projects", {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      closeProjectModal();
      await renderProductionProjects();
      if (typeof showToast === "function") showToast(`项目「${name}」已创建`);
    } catch (requestError) {
      error.textContent = requestError.message;
      input.focus();
    } finally {
      submit.disabled = false;
      submit.textContent = "创建项目";
    }
  }

  function ensureChapterModal() {
    let modal = document.getElementById("new-chapter-modal");
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "new-chapter-modal";
    modal.className = "atelier-modal-backdrop";
    modal.hidden = true;
    modal.innerHTML = `
      <section class="atelier-modal" role="dialog" aria-modal="true" aria-labelledby="new-chapter-title">
        <div class="atelier-modal-icon">CH</div>
        <h2 id="new-chapter-title">新建章节</h2>
        <p>输入章节名称。章节会按照创建顺序排列在画布中。</p>
        <form id="new-chapter-form">
          <label class="label" for="new-chapter-name">章节名称</label>
          <input id="new-chapter-name" class="modal-input" name="name" maxlength="80" autocomplete="off" placeholder="输入章节名称" required />
          <div class="modal-error" id="new-chapter-error" role="alert"></div>
          <div class="modal-actions">
            <button class="btn" type="button" data-api-action="close-chapter-modal">取消</button>
            <button class="btn primary" type="submit">创建章节</button>
          </div>
        </form>
      </section>
    `;
    document.body.appendChild(modal);
    modal.addEventListener("click", (event) => {
      if (event.target === modal) closeChapterModal();
    });
    modal.querySelector("form").addEventListener("submit", submitChapter);
    return modal;
  }

  function openChapterModal() {
    const modal = ensureChapterModal();
    const error = modal.querySelector(".modal-error");
    const input = modal.querySelector("input");
    error.textContent = "";
    input.value = "";
    modal.hidden = false;
    requestAnimationFrame(() => {
      modal.classList.add("show");
      input.focus();
    });
  }

  function closeChapterModal() {
    const modal = document.getElementById("new-chapter-modal");
    if (!modal) return;
    modal.classList.remove("show");
    window.setTimeout(() => {
      modal.hidden = true;
    }, 150);
  }

  async function submitChapter(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const input = form.querySelector("input");
    const submit = form.querySelector('button[type="submit"]');
    const error = form.querySelector(".modal-error");
    const name = input.value.trim().replace(/\s+/g, " ");
    const projectId = document.body.dataset.projectId;
    if (!name) {
      error.textContent = "请输入章节名称。";
      input.focus();
      return;
    }
    if (!projectId) {
      error.textContent = "当前项目不可用。";
      return;
    }
    submit.disabled = true;
    submit.textContent = "正在创建…";
    error.textContent = "";
    try {
      await request(`/api/projects/${projectId}/chapters`, {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      closeChapterModal();
      const project = await resolveCurrentProject();
      await renderProductionStoryCanvas(project);
      if (typeof showToast === "function") showToast(`章节「${name}」已创建`);
    } catch (requestError) {
      error.textContent = requestError.message;
      input.focus();
    } finally {
      submit.disabled = false;
      submit.textContent = "创建章节";
    }
  }

  function ensureLargeSceneModal() {
    let modal = document.getElementById("new-large-scene-modal");
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "new-large-scene-modal";
    modal.className = "atelier-modal-backdrop";
    modal.hidden = true;
    modal.innerHTML = `
      <section class="atelier-modal size-md" role="dialog" aria-modal="true" aria-labelledby="new-large-scene-title">
        <div class="atelier-modal-icon scene">SC</div>
        <h2 id="new-large-scene-title">新建大场景</h2>
        <p id="new-large-scene-context">大场景会按照创建顺序排列在所属章节中。</p>
        <form id="new-large-scene-form">
          <label class="label" for="new-large-scene-name">大场景名称</label>
          <input id="new-large-scene-name" class="modal-input" name="name" maxlength="80" autocomplete="off" placeholder="例如：公共沙滩" required />
          <label class="label" for="new-large-scene-type">类型</label>
          <select id="new-large-scene-type" class="modal-input" name="scene_type">
            <option value="content">内容段</option>
            <option value="transition">过渡段</option>
          </select>
          <div class="modal-error" id="new-large-scene-error" role="alert"></div>
          <div class="modal-actions">
            <button class="btn" type="button" data-api-action="close-large-scene-modal">取消</button>
            <button class="btn primary" type="submit">创建大场景</button>
          </div>
        </form>
      </section>
    `;
    document.body.appendChild(modal);
    modal.addEventListener("click", (event) => {
      if (event.target === modal) closeLargeSceneModal();
    });
    modal.querySelector("form").addEventListener("submit", submitLargeScene);
    return modal;
  }

  function openLargeSceneModal(chapterId, chapterName) {
    const modal = ensureLargeSceneModal();
    const error = modal.querySelector(".modal-error");
    const input = modal.querySelector("input");
    const select = modal.querySelector("select");
    const context = modal.querySelector("#new-large-scene-context");
    modal.dataset.chapterId = chapterId;
    context.textContent = `添加到章节「${chapterName}」，并按照创建顺序排列。`;
    error.textContent = "";
    input.value = "";
    if (select) select.value = "content";
    modal.hidden = false;
    requestAnimationFrame(() => {
      modal.classList.add("show");
      input.focus();
    });
  }

  function closeLargeSceneModal() {
    const modal = document.getElementById("new-large-scene-modal");
    if (!modal) return;
    modal.classList.remove("show");
    window.setTimeout(() => {
      modal.hidden = true;
    }, 150);
  }

  async function openLargeSceneEditModal(largeSceneId, currentName) {
    let modal = document.getElementById("large-scene-edit-modal");
    if (!modal) {
      modal = document.createElement("div");
      modal.id = "large-scene-edit-modal";
      modal.className = "atelier-modal-backdrop";
      modal.hidden = true;
      modal.innerHTML = `
        <section class="atelier-modal size-md" role="dialog" aria-modal="true" aria-labelledby="large-scene-edit-title">
          <div class="atelier-modal-icon scene">SC</div>
          <h2 id="large-scene-edit-title">编辑大场景</h2>
          <p id="large-scene-edit-context">修改大场景的名称、类型或所属章节。</p>
          <form id="large-scene-edit-form">
            <label class="label" for="large-scene-edit-name">大场景名称</label>
            <input id="large-scene-edit-name" class="modal-input" name="name" maxlength="80" autocomplete="off" required />
            <label class="label" for="large-scene-edit-type">类型</label>
            <select id="large-scene-edit-type" class="modal-input" name="scene_type">
              <option value="content">内容段</option>
              <option value="transition">过渡段</option>
            </select>
            <label class="label" for="large-scene-edit-chapter">所属章节</label>
            <select id="large-scene-edit-chapter" class="modal-input" name="chapter_id"></select>
            <div class="modal-error" id="large-scene-edit-error" role="alert"></div>
            <div class="modal-actions">
              <button class="btn" type="button" data-api-action="close-large-scene-edit-modal">取消</button>
              <button class="btn primary" type="submit">保存修改</button>
            </div>
          </form>
        </section>
      `;
      document.body.appendChild(modal);
      modal.addEventListener("click", (event) => {
        if (event.target === modal) closeLargeSceneEditModal();
      });
      modal.querySelector("form").addEventListener("submit", submitLargeSceneEdit);
    }
    modal.dataset.largeSceneId = largeSceneId;
    const error = modal.querySelector(".modal-error");
    const nameInput = modal.querySelector("#large-scene-edit-name");
    const typeSelect = modal.querySelector("#large-scene-edit-type");
    const chapterSelect = modal.querySelector("#large-scene-edit-chapter");
    const context = modal.querySelector("#large-scene-edit-context");
    const submitBtn = modal.querySelector('button[type="submit"]');
    error.textContent = "";
    nameInput.value = currentName;
    context.textContent = `正在编辑大场景「${currentName}」。`;
    if (submitBtn) submitBtn.disabled = false;
    // Fetch current scene + chapter list in parallel
    try {
      const project = await resolveCurrentProject();
      const [sceneRes, chaptersRes] = await Promise.all([
        request(`/api/large-scenes/${largeSceneId}`),
        request(`/api/projects/${project.id}/chapters`),
      ]);
      const scene = sceneRes.large_scene || sceneRes;
      typeSelect.value = scene.scene_type || "content";
      chapterSelect.innerHTML = chaptersRes.items
        .map(
          (ch) =>
            `<option value="${escapeHtml(ch.id)}"${ch.id === scene.chapter_id ? " selected" : ""}>${escapeHtml(ch.name)}</option>`
        )
        .join("");
      modal.dataset.currentChapterId = scene.chapter_id;
    } catch (err) {
      error.textContent = "加载大场景信息失败：" + err.message;
    }
    modal.hidden = false;
    requestAnimationFrame(() => {
      modal.classList.add("show");
      nameInput.focus();
      nameInput.select();
    });
  }

  function closeLargeSceneEditModal() {
    const modal = document.getElementById("large-scene-edit-modal");
    if (!modal) return;
    modal.classList.remove("show");
    window.setTimeout(() => {
      modal.hidden = true;
    }, 150);
  }

  async function submitLargeSceneEdit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const modal = form.closest(".atelier-modal-backdrop");
    const nameInput = form.querySelector("#large-scene-edit-name");
    const typeSelect = form.querySelector("#large-scene-edit-type");
    const chapterSelect = form.querySelector("#large-scene-edit-chapter");
    const submit = form.querySelector('button[type="submit"]');
    const error = form.querySelector(".modal-error");
    const largeSceneId = modal.dataset.largeSceneId;
    const originalChapterId = modal.dataset.currentChapterId;
    const name = nameInput.value.trim().replace(/\s+/g, " ");
    const sceneType = typeSelect.value;
    const chapterId = chapterSelect.value;
    if (!name) {
      error.textContent = "请输入大场景名称。";
      nameInput.focus();
      return;
    }
    const body = { name, scene_type: sceneType };
    if (chapterId && chapterId !== originalChapterId) {
      body.chapter_id = chapterId;
    }
    submit.disabled = true;
    submit.textContent = "正在保存…";
    error.textContent = "";
    try {
      await request(`/api/large-scenes/${largeSceneId}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      closeLargeSceneEditModal();
      const project = await resolveCurrentProject();
      await renderProductionStoryCanvas(project);
      if (typeof showToast === "function") showToast(`大场景「${name}」已更新`);
    } catch (requestError) {
      error.textContent = requestError.message;
      nameInput.focus();
    } finally {
      submit.disabled = false;
      submit.textContent = "保存修改";
    }
  }

  async function submitLargeScene(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const modal = form.closest(".atelier-modal-backdrop");
    const input = form.querySelector("input");
    const select = form.querySelector("select");
    const submit = form.querySelector('button[type="submit"]');
    const error = form.querySelector(".modal-error");
    const name = input.value.trim().replace(/\s+/g, " ");
    const sceneType = select ? select.value : "content";
    const chapterId = modal.dataset.chapterId;
    if (!name) {
      error.textContent = "请输入大场景名称。";
      input.focus();
      return;
    }
    if (!chapterId) {
      error.textContent = "当前章节不可用。";
      return;
    }
    submit.disabled = true;
    submit.textContent = "正在创建…";
    error.textContent = "";
    try {
      await request(`/api/chapters/${chapterId}/large-scenes`, {
        method: "POST",
        body: JSON.stringify({ name, scene_type: sceneType }),
      });
      closeLargeSceneModal();
      const project = await resolveCurrentProject();
      await renderProductionStoryCanvas(project);
      if (typeof showToast === "function") showToast(`大场景「${name}」已创建`);
    } catch (requestError) {
      error.textContent = requestError.message;
      input.focus();
    } finally {
      submit.disabled = false;
      submit.textContent = "创建大场景";
    }
  }

  function ensureCharacterModal() {
    let modal = document.getElementById("new-character-modal");
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "new-character-modal";
    modal.className = "atelier-modal-backdrop";
    modal.hidden = true;
    modal.innerHTML = `
      <section class="atelier-modal" role="dialog" aria-modal="true" aria-labelledby="new-character-title">
        <div class="atelier-modal-icon">CH</div>
        <h2 id="new-character-title">新建人物</h2>
        <p>输入人物名称。人物创建后会自动附带「默认」形象变体。</p>
        <form id="new-character-form">
          <label class="label" for="new-character-name">人物名称</label>
          <input id="new-character-name" class="modal-input" name="name" maxlength="80" autocomplete="off" placeholder="例如：角色 A" required />
          <div class="modal-error" id="new-character-error" role="alert"></div>
          <div class="modal-actions">
            <button class="btn" type="button" data-api-action="close-character-modal">取消</button>
            <button class="btn primary" type="submit">创建人物</button>
          </div>
        </form>
      </section>
    `;
    document.body.appendChild(modal);
    modal.addEventListener("click", (event) => {
      if (event.target === modal) closeCharacterModal();
    });
    modal.querySelector("form").addEventListener("submit", submitCharacter);
    return modal;
  }

  function openCharacterModal() {
    const modal = ensureCharacterModal();
    const error = modal.querySelector(".modal-error");
    const input = modal.querySelector("input");
    error.textContent = "";
    input.value = "";
    modal.hidden = false;
    requestAnimationFrame(() => {
      modal.classList.add("show");
      input.focus();
    });
  }

  function closeCharacterModal() {
    const modal = document.getElementById("new-character-modal");
    if (!modal) return;
    modal.classList.remove("show");
    window.setTimeout(() => {
      modal.hidden = true;
    }, 150);
  }

  async function submitCharacter(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const input = form.querySelector("input");
    const submit = form.querySelector('button[type="submit"]');
    const error = form.querySelector(".modal-error");
    const name = input.value.trim().replace(/\s+/g, " ");
    if (!name) {
      error.textContent = "请输入人物名称。";
      input.focus();
      return;
    }
    submit.disabled = true;
    submit.textContent = "正在创建…";
    error.textContent = "";
    try {
      await request(`/api/characters`, {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      closeCharacterModal();
      await renderProductionCharacters();
      if (typeof showToast === "function") showToast(`人物「${name}」已创建`);
    } catch (requestError) {
      error.textContent = requestError.message;
      input.focus();
    } finally {
      submit.disabled = false;
      submit.textContent = "创建人物";
    }
  }

  async function deleteCharacter(characterId, name) {
    const confirmed = await confirmDialog({
      title: `删除人物「${name}」`,
      message: "该人物的所有形象变体与规格值也会一并删除，此操作无法撤销。",
      confirmText: "删除"
    });
    if (!confirmed) {
      return;
    }
    try {
      await request(`/api/characters/${characterId}`, { method: "DELETE" });
      await renderProductionCharacters();
      if (typeof showToast === "function") showToast(`人物「${name}」已删除`);
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message);
    }
  }

  async function deleteCharacterVariant(variantId, name, isDefault) {
    if (isDefault) {
      if (typeof showToast === "function") showToast("默认形象变体不可删除");
      return;
    }
    if (!await confirmDialog({
      title: `删除形象变体「${name}」`,
      message: "此操作无法撤销。",
      confirmText: "删除"
    })) {
      return;
    }
    try {
      await request(`/api/character-variants/${variantId}`, { method: "DELETE" });
      await refreshExpandedOrAll();
      if (typeof showToast === "function") showToast(`形象变体「${name}」已删除`);
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message);
    }
  }

  async function refreshExpandedOrAll() {
    const activeCard = document.querySelector(".character-block.active");
    if (activeCard && activeCard.dataset.characterId) {
      await renderCharacterDetail(activeCard.dataset.characterId);
      return;
    }
    await renderProductionCharacters();
  }

  async function deleteProjectSpec(specId, name) {
    if (!await confirmDialog({
      title: `删除规格「${name}」`,
      message: "所有变体下对应的规格值也会一并删除，此操作无法撤销。",
      confirmText: "删除"
    })) {
      return;
    }
    try {
      await request(`/api/specs/${specId}`, { method: "DELETE" });
      await refreshExpandedOrAll();
      if (typeof showToast === "function") showToast(`规格「${name}」已删除`);
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message);
    }
  }

  function cssEscape(value) {
    if (typeof CSS !== "undefined" && CSS.escape) return CSS.escape(value);
    return String(value).replace(/[^a-zA-Z0-9_-]/g, (ch) => `\\${ch}`);
  }

  function ensureRenameModal() {
    let modal = document.getElementById("rename-structure-modal");
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "rename-structure-modal";
    modal.className = "atelier-modal-backdrop";
    modal.hidden = true;
    modal.innerHTML = `
      <section class="atelier-modal" role="dialog" aria-modal="true" aria-labelledby="rename-structure-title">
        <div class="atelier-modal-icon rename">RN</div>
        <h2 id="rename-structure-title">改名</h2>
        <p id="rename-structure-context">输入新的名称。</p>
        <form id="rename-structure-form">
          <label class="label" for="rename-structure-name">新名称</label>
          <input id="rename-structure-name" class="modal-input" name="name" maxlength="80" autocomplete="off" required />
          <div class="modal-error" id="rename-structure-error" role="alert"></div>
          <div class="modal-actions">
            <button class="btn" type="button" data-api-action="close-rename-modal">取消</button>
            <button class="btn primary" type="submit">保存名称</button>
          </div>
        </form>
      </section>
    `;
    document.body.appendChild(modal);
    modal.addEventListener("click", (event) => {
      if (event.target === modal) closeRenameModal();
    });
    modal.querySelector("form").addEventListener("submit", submitRename);
    return modal;
  }

  const renameTypeNames = {
    chapter: "章节",
    "large-scene": "大场景",
    character: "人物",
    "character-variant": "形象变体",
    "project-spec": "自定义规格标签",
  };

  function openRenameModal(type, id, currentName) {
    const modal = ensureRenameModal();
    const typeName = renameTypeNames[type] || "项目";
    const input = modal.querySelector("input");
    modal.dataset.structureType = type;
    modal.dataset.structureId = id;
    modal.querySelector("h2").textContent = `重命名${typeName}`;
    modal.querySelector("#rename-structure-context").textContent =
      `当前名称：${currentName}`;
    modal.querySelector("label").textContent = `${typeName}名称`;
    modal.querySelector(".modal-error").textContent = "";
    input.value = currentName;
    modal.hidden = false;
    requestAnimationFrame(() => {
      modal.classList.add("show");
      input.focus();
      input.select();
    });
  }

  function closeRenameModal() {
    const modal = document.getElementById("rename-structure-modal");
    if (!modal) return;
    modal.classList.remove("show");
    window.setTimeout(() => {
      modal.hidden = true;
    }, 150);
  }

  function renameRequestPath(type, id) {
    switch (type) {
      case "chapter":
        return `/api/chapters/${id}`;
      case "large-scene":
        return `/api/large-scenes/${id}`;
      case "character":
        return `/api/characters/${id}`;
      case "character-variant":
        return `/api/character-variants/${id}`;
      case "project-spec":
        return `/api/specs/${id}`;
      default:
        return null;
    }
  }

  async function submitRename(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const modal = form.closest(".atelier-modal-backdrop");
    const input = form.querySelector("input");
    const submit = form.querySelector('button[type="submit"]');
    const error = form.querySelector(".modal-error");
    const name = input.value.trim().replace(/\s+/g, " ");
    const type = modal.dataset.structureType;
    const id = modal.dataset.structureId;
    const typeName = renameTypeNames[type] || "项目";
    if (!name) {
      error.textContent = `请输入${typeName}名称。`;
      input.focus();
      return;
    }
    submit.disabled = true;
    submit.textContent = "正在保存…";
    error.textContent = "";
    try {
      const path = renameRequestPath(type, id);
      if (!path) throw new Error("未知的改名目标。");
      const body = type === "project-spec"
        ? { custom_label: name }
        : { name };
      await request(path, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      closeRenameModal();
      await refreshAfterRename(type, id);
      if (typeof showToast === "function") showToast(`${typeName}已改名为「${name}」`);
    } catch (requestError) {
      error.textContent = requestError.message;
      input.focus();
    } finally {
      submit.disabled = false;
      submit.textContent = "保存名称";
    }
  }

  async function refreshAfterRename(type, id) {
    if (type === "chapter" || type === "large-scene") {
      const project = await resolveCurrentProject();
      await renderProductionStoryCanvas(project);
      return;
    }
    if (type === "character") {
      await renderProductionCharacters();
      if (id) await renderCharacterDetail(id);
      return;
    }
    await refreshExpandedOrAll();
  }

  async function deleteChapter(chapterId, name, largeSceneCount) {
    const sceneWarning = largeSceneCount
      ? `其中 ${largeSceneCount} 个大场景也会一并删除，`
      : "";
    if (!await confirmDialog({
      title: `删除章节「${name}」`,
      message: `${sceneWarning}此操作无法撤销。`,
      confirmText: "删除"
    })) {
      return;
    }
    try {
      await request(`/api/chapters/${chapterId}`, { method: "DELETE" });
      const project = await resolveCurrentProject();
      await renderProductionStoryCanvas(project);
      if (typeof showToast === "function") showToast(`章节「${name}」已删除`);
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message);
    }
  }

  async function deleteLargeScene(largeSceneId, name) {
    if (!await confirmDialog({
      title: `删除大场景「${name}」`,
      message: "此操作无法撤销。",
      confirmText: "删除"
    })) {
      return;
    }
    try {
      await request(`/api/large-scenes/${largeSceneId}`, { method: "DELETE" });
      const project = await resolveCurrentProject();
      await renderProductionStoryCanvas(project);
      if (typeof showToast === "function") showToast(`大场景「${name}」已删除`);
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message);
    }
  }

  function ensureContextMenu() {
    let menu = document.getElementById("structure-context-menu");
    if (menu) return menu;
    menu = document.createElement("div");
    menu.id = "structure-context-menu";
    menu.className = "structure-context-menu";
    menu.setAttribute("role", "menu");
    menu.innerHTML = `
      <ul class="structure-context-menu-list">
        <li class="structure-context-menu-item" data-menu-action="rename" role="menuitem" tabindex="0">改名</li>
        <li class="structure-context-menu-item danger" data-menu-action="delete" role="menuitem" tabindex="0">删除</li>
      </ul>
    `;
    menu.hidden = true;
    document.body.appendChild(menu);
    return menu;
  }

  function showContextMenu(type, data, x, y) {
    const menu = ensureContextMenu();
    menu.dataset.contextType = type;
    menu.dataset.contextId = data.id;
    menu.dataset.contextName = data.name;
    menu.dataset.contextExtra =
      data.largeSceneCount != null ? String(data.largeSceneCount) : "";
    menu.dataset.contextIsDefault =
      data.isDefault ? "1" : "";
    menu.dataset.contextSpecType = data.specType || "";
    const menuWidth = 168;
    const menuHeight = 88;
    const safeX = Math.min(x, window.innerWidth - menuWidth - 8);
    const safeY = Math.min(y, window.innerHeight - menuHeight - 8);
    menu.style.left = `${Math.max(8, safeX)}px`;
    menu.style.top = `${Math.max(8, safeY)}px`;
    menu.hidden = false;
    requestAnimationFrame(() => {
      menu.classList.add("show");
      const firstItem = menu.querySelector(".structure-context-menu-item");
      if (firstItem) firstItem.focus();
    });
  }

  function hideContextMenu() {
    const menu = document.getElementById("structure-context-menu");
    if (!menu || menu.hidden) return;
    menu.classList.remove("show");
    window.setTimeout(() => {
      menu.hidden = true;
      menu.dataset.contextType = "";
      menu.dataset.contextId = "";
      menu.dataset.contextName = "";
      menu.dataset.contextExtra = "";
      menu.dataset.contextIsDefault = "";
      menu.dataset.contextSpecType = "";
      menu.style.left = "";
      menu.style.top = "";
    }, 140);
  }

  function openMenuFromElement(target, x, y) {
    const trigger = target.closest("[data-context-menu]");
    if (!trigger) return false;
    const type = trigger.dataset.contextMenu;
    if (type === "chapter") {
      showContextMenu(
        "chapter",
        {
          id: trigger.dataset.chapterId,
          name: trigger.dataset.name,
          largeSceneCount: Number(trigger.dataset.largeSceneCount || 0),
        },
        x,
        y
      );
      return true;
    }
    if (type === "large-scene") {
      showContextMenu(
        "large-scene",
        {
          id: trigger.dataset.largeSceneId,
          name: trigger.dataset.name,
        },
        x,
        y
      );
      return true;
    }
    if (type === "character") {
      showContextMenu(
        "character",
        {
          id: trigger.dataset.characterId,
          name: trigger.dataset.name,
        },
        x,
        y
      );
      return true;
    }
    if (type === "character-variant") {
      showContextMenu(
        "character-variant",
        {
          id: trigger.dataset.variantId,
          name: trigger.dataset.name,
          isDefault: trigger.dataset.isDefault === "1",
        },
        x,
        y
      );
      return true;
    }
    if (type === "project-spec") {
      showContextMenu(
        "project-spec",
        {
          id: trigger.dataset.specId,
          name: trigger.dataset.name,
          specType: trigger.dataset.specType,
        },
        x,
        y
      );
      return true;
    }
    return false;
  }

  function initContextMenu() {
    document.addEventListener("contextmenu", (event) => {
      if (openMenuFromElement(event.target, event.clientX, event.clientY)) {
        event.preventDefault();
      }
    });

    let longPressTimer = null;
    let longPressStart = null;
    document.addEventListener(
      "touchstart",
      (event) => {
        const touch = event.touches[0];
        if (!touch) return;
        const target = document.elementFromPoint(touch.clientX, touch.clientY);
        if (!target || !target.closest("[data-context-menu]")) return;
        longPressStart = { x: touch.clientX, y: touch.clientY };
        longPressTimer = window.setTimeout(() => {
          if (!longPressStart) return;
          openMenuFromElement(target, longPressStart.x, longPressStart.y);
        }, 500);
      },
      { passive: true }
    );
    document.addEventListener(
      "touchmove",
      (event) => {
        const touch = event.touches[0];
        if (!touch || !longPressStart) return;
        const dx = touch.clientX - longPressStart.x;
        const dy = touch.clientY - longPressStart.y;
        if (Math.hypot(dx, dy) > 10) {
          if (longPressTimer) {
            window.clearTimeout(longPressTimer);
            longPressTimer = null;
          }
          longPressStart = null;
        }
      },
      { passive: true }
    );
    const cancelLongPress = () => {
      if (longPressTimer) {
        window.clearTimeout(longPressTimer);
        longPressTimer = null;
      }
      longPressStart = null;
    };
    document.addEventListener("touchend", cancelLongPress, { passive: true });
    document.addEventListener("touchcancel", cancelLongPress, { passive: true });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") hideContextMenu();
    });

    window.addEventListener("scroll", hideContextMenu, true);
    window.addEventListener("resize", hideContextMenu);
  }

  initContextMenu();

  // ── 大场景拖动交互 ─────────────────────────────────────────
  let dragState = null;

  function initLargeSceneDrag() {
    document.addEventListener("dragstart", (event) => {
      const card = event.target.closest?.(".large-scene-block[draggable='true']");
      if (!card) return;
      const largeSceneId = card.dataset.largeSceneId;
      const sourceChapterId = card.dataset.chapterId;
      if (!largeSceneId || !sourceChapterId) return;
      dragState = {
        largeSceneId,
        sourceChapterId,
        card,
      };
      card.classList.add("dragging");
      event.dataTransfer.effectAllowed = "move";
      // Set empty image as drag image to use our own visual
      try {
        const dragImage = document.createElement("div");
        dragImage.style.width = "1px";
        dragImage.style.height = "1px";
        document.body.appendChild(dragImage);
        event.dataTransfer.setDragImage(dragImage, 0, 0);
        window.setTimeout(() => dragImage.remove(), 0);
      } catch (e) {
        // Fallback to default drag image
      }
    });

    document.addEventListener("dragend", () => {
      if (!dragState) return;
      dragState.card?.classList.remove("dragging");
      clearDropIndicators();
      dragState = null;
    });

    document.addEventListener("dragover", (event) => {
      if (!dragState) return;
      const dropZone = event.target.closest?.("[data-drop-zone]");
      if (!dropZone) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
      const targetChapterId = dropZone.dataset.chapterId;
      if (!targetChapterId) return;
      // Compute insertion position within this drop zone
      const cards = Array.from(
        dropZone.querySelectorAll(".large-scene-block:not(.dragging)")
      );
      let insertIndex = cards.length;
      let insertBeforeEl = null;
      for (let i = 0; i < cards.length; i++) {
        const rect = cards[i].getBoundingClientRect();
        const midX = rect.left + rect.width / 2;
        if (event.clientX < midX) {
          insertIndex = i;
          insertBeforeEl = cards[i];
          break;
        }
      }
      clearDropIndicators();
      const indicator = document.createElement("div");
      indicator.className = "large-scene-drop-indicator";
      indicator.setAttribute("aria-hidden", "true");
      if (insertBeforeEl) {
        dropZone.insertBefore(indicator, insertBeforeEl);
      } else {
        // Append at end, but before the "add card" if present
        const addCard = dropZone.querySelector(".large-scene-add-card");
        if (addCard) {
          dropZone.insertBefore(indicator, addCard);
        } else {
          dropZone.appendChild(indicator);
        }
      }
      dragState.targetChapterId = targetChapterId;
      dragState.targetIndex = insertIndex;
    });

    document.addEventListener("dragleave", (event) => {
      if (!dragState) return;
      // Only clear if leaving the document entirely
      if (event.relatedTarget === null) {
        clearDropIndicators();
      }
    });

    document.addEventListener("drop", async (event) => {
      if (!dragState) return;
      const dropZone = event.target.closest?.("[data-drop-zone]");
      if (!dropZone) {
        clearDropIndicators();
        return;
      }
      event.preventDefault();
      const { largeSceneId, sourceChapterId, targetChapterId, targetIndex } = dragState;
      dragState.card?.classList.remove("dragging");
      clearDropIndicators();
      dragState = null;
      if (!targetChapterId) return;
      // targetIndex is 0-based; convert to 1-based sort_order for API
      const targetSortOrder = (targetIndex ?? 0) + 1;
      try {
        await request(`/api/large-scenes/${largeSceneId}/move`, {
          method: "POST",
          body: JSON.stringify({
            target_chapter_id: targetChapterId,
            target_sort_order: targetSortOrder,
          }),
        });
        const project = await resolveCurrentProject();
        await renderProductionStoryCanvas(project);
        if (typeof showToast === "function") showToast("大场景已移动");
      } catch (requestError) {
        // Restore canvas to last server state
        const project = await resolveCurrentProject();
        await renderProductionStoryCanvas(project);
        if (typeof showToast === "function") {
          showToast("移动失败：" + requestError.message);
        } else {
          alert("移动失败：" + requestError.message);
        }
      }
    });
  }

  function clearDropIndicators() {
    document.querySelectorAll(".large-scene-drop-indicator").forEach((el) => el.remove());
  }

  initLargeSceneDrag();

  function renderDatabaseCard(database) {
    const card = document.getElementById(`database-${database.environment}`);
    if (!card) return;
    card.classList.toggle("active", database.active);
    card.querySelector(".database-state").textContent = database.active
      ? database.locked
        ? "正在使用 · 已锁定"
        : "正在使用"
      : "待机";
    card.querySelector(".database-state").className = `status database-state ${database.active ? "green" : ""}`;
    card.querySelector(".database-path").textContent = database.path;
    card.querySelector(".database-journal").textContent = `SQLite ${database.journal_mode}`;
    card.querySelector(".database-size").textContent = formatBytes(database.size_bytes);
    card.querySelector(".database-events").textContent = `${database.event_count} 条`;
    const action = card.querySelector(".database-action");
    action.disabled = database.active;
    action.textContent = database.active
      ? "当前正在使用"
      : `切换到${environmentNames[database.environment]}`;
  }

  async function request(path, options) {
    const isFormData = options?.body instanceof FormData;
    const response = await fetch(path, {
      headers: isFormData ? {} : { "Content-Type": "application/json" },
      ...options,
    });
    let payload = {};
    try {
      payload = await response.json();
    } catch (error) {
      payload = {};
    }
    if (!response.ok) {
      // 后端统一错误格式: {detail, error: {code, message, details, request_id}}
      const errorObj = payload.error || {};
      const message = errorObj.message || payload.detail || `请求失败（${response.status}）`;
      const requestError = new Error(message);
      requestError.status = response.status;
      requestError.payload = payload;
      requestError.errorCode = errorObj.code || "";
      requestError.requestId = errorObj.request_id || response.headers.get("X-Request-ID") || "";
      throw requestError;
    }
    return payload;
  }

  function formatDevelopmentUpdatedAt(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "更新时间未知";
    return `更新于 ${date.toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    })}`;
  }

  function developmentProgressMarkup(payload) {
    const progressPercent = Number(payload.progress_percent) || 0;
    const modules = Array.isArray(payload.modules) ? payload.modules : [];
    const stateLabel = {
      completed: "已完成",
      in_progress: "开发中",
      pending: "未开始",
    };
    const stateIcon = {
      completed: "✓",
      in_progress: "…",
      pending: "•",
    };
    const moduleMarkup = modules.length
      ? modules.map((module) => {
          const modulePercent = Number(module.progress_percent) || 0;
          const items = Array.isArray(module.items) ? module.items : [];
          return `
            <section class="development-module">
              <div class="development-module-header">
                <div>
                  <h3>${escapeHtml(module.name)}</h3>
                  <p>完成 ${Number(module.completed) || 0} · 开发中 ${Number(module.in_progress) || 0} · 未开始 ${Number(module.pending) || 0}</p>
                </div>
                <strong>${modulePercent}%</strong>
              </div>
              <div class="development-module-track"><i style="width:${Math.max(0, Math.min(100, modulePercent))}%"></i></div>
              <div class="development-module-items">
                ${items.map((item) => `
                  <article class="development-item ${escapeHtml(item.status)}">
                    <span class="development-item-state" aria-hidden="true">${stateIcon[item.status] || "•"}</span>
                    <div class="development-item-copy">
                      <div class="development-item-heading">
                        <strong>${escapeHtml(item.title)}</strong>
                        <span>${stateLabel[item.status] || "未开始"}</span>
                      </div>
                      ${item.description ? `<p>${escapeHtml(item.description)}</p>` : ""}
                    </div>
                  </article>
                `).join("")}
              </div>
            </section>
          `;
        }).join("")
      : '<div class="development-empty">系统功能清单中还没有可汇总的功能项。</div>';

    return `
      <div class="development-summary">
        <div class="development-progress-ring" style="--development-progress:${progressPercent * 3.6}deg">
          <div><strong>${progressPercent}%</strong><span>总体进度</span></div>
        </div>
        <div class="development-summary-copy">
          <span class="developer-eyebrow">LIVE CHECKLIST</span>
          <h2>全系统功能完成情况</h2>
          <p>共 ${Number(payload.total) || 0} 项，已完成 ${Number(payload.completed) || 0} 项，开发中 ${Number(payload.in_progress) || 0} 项。</p>
          <div class="development-progress-track">
            <i style="width:${Math.max(0, Math.min(100, progressPercent))}%"></i>
          </div>
          <div class="development-summary-meta">
            <span>${escapeHtml(payload.source || "功能开发待办.md")}</span>
            <span>${escapeHtml(formatDevelopmentUpdatedAt(payload.updated_at))}</span>
          </div>
        </div>
        <div class="development-metrics">
          <div><strong>${Number(payload.completed) || 0}</strong><span>已完成</span></div>
          <div><strong>${Number(payload.in_progress) || 0}</strong><span>开发中</span></div>
          <div><strong>${Number(payload.pending) || 0}</strong><span>未开始</span></div>
          <div><strong>${Number(payload.total) || 0}</strong><span>总计</span></div>
        </div>
      </div>
      <div class="development-progress-rule">${escapeHtml(payload.progress_rule || "只有完整交付的功能计入完成率。")}</div>
      <div class="development-list">${moduleMarkup}</div>
    `;
  }

  async function loadDevelopmentProgress() {
    const output = document.getElementById("development-progress-result");
    const button = document.querySelector('[data-api-action="load-development-progress"]');
    if (!output || !button) return;
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = "正在汇总…";
    output.hidden = false;
    output.innerHTML = '<div class="development-loading"><i></i><span>正在读取全系统功能清单…</span></div>';
    try {
      const payload = await request("/api/developer/progress");
      output.innerHTML = developmentProgressMarkup(payload);
      button.textContent = "刷新开发进度";
    } catch (error) {
      output.innerHTML = `
        <div class="development-error">
          <strong>暂时无法读取开发进度</strong>
          <p>${escapeHtml(error.message)}</p>
        </div>
      `;
      button.textContent = originalText;
    } finally {
      button.disabled = false;
    }
  }

  async function refreshDatabaseState() {
    try {
      const payload = await request("/api/settings/databases");
      payload.databases.forEach(renderDatabaseCard);
      document.body.dataset.databaseEnvironment = payload.active_environment;
      const pageKey = new URLSearchParams(window.location.search).get("page") || "projects";
      if (pageKey === "projects") {
        await renderProductionProjects();
      } else if (pageKey === "characters") {
        await renderProductionCharacters();
      } else if (pageKey === "character-database") {
        await renderCharacterDatabasePage();
      } else if (pageKey === "materials") {
        await renderMaterialsPage();
      } else if (pageKey === "material-detail") {
        await renderMaterialDetailPage();
      } else if (pageKey === "developer") {
        // 开发进度由用户点击后按需读取，避免把文档状态写死在页面里。
      } else if (pageKey !== "settings") {
        const project = await resolveCurrentProject();
        applyProjectHeader(project, pageKey);
        if (pageKey === "overview") await renderProductionOverview(project);
        else if (pageKey === "story-canvas") await renderProductionStoryCanvasV3(project);
        else applyProductionEmptyState();
      }
      const safety = document.getElementById("database-safety-status");
      if (safety) safety.innerHTML = '<span class="status green">物理隔离正常</span>';
      document.body.classList.remove("runtime-pending");
      return payload;
    } catch (error) {
      const safety = document.getElementById("database-safety-status");
      if (safety) safety.innerHTML = '<span class="status orange">后端未连接</span>';
      document.body.classList.remove("runtime-pending");
      return null;
    }
  }

  document.addEventListener("click", async (event) => {
    // 右键菜单项点击优先处理
    const menuItem = event.target.closest(".structure-context-menu-item");
    if (menuItem) {
      event.preventDefault();
      event.stopPropagation();
      const menu = menuItem.closest("#structure-context-menu");
      if (!menu || menu.hidden) return;
      const action = menuItem.dataset.menuAction;
      const type = menu.dataset.contextType;
      const id = menu.dataset.contextId;
      const name = menu.dataset.contextName;
      const largeSceneCount = Number(menu.dataset.contextExtra || 0);
      const isDefault = menu.dataset.contextIsDefault === "1";
      const specType = menu.dataset.contextSpecType;
      hideContextMenu();
      if (action === "rename") {
        if (type === "project-spec" && specType !== "custom") {
          if (typeof showToast === "function") showToast("仅自定义规格可改标签");
          return;
        }
        if (type === "character-variant" && isDefault) {
          if (typeof showToast === "function") showToast("默认变体可改名但不会取消默认");
        }
        if (type === "large-scene") {
          openLargeSceneEditModal(id, name);
        } else {
          openRenameModal(type, id, name);
        }
      } else if (action === "delete") {
        if (type === "chapter") {
          await deleteChapter(id, name, largeSceneCount);
        } else if (type === "large-scene") {
          await deleteLargeScene(id, name);
        } else if (type === "character") {
          await deleteCharacter(id, name);
        } else if (type === "character-variant") {
          await deleteCharacterVariant(id, name, isDefault);
        } else if (type === "project-spec") {
          await deleteProjectSpec(id, name);
        }
      }
      return;
    }

    // 点击菜单以外区域关闭菜单
    if (!event.target.closest("#structure-context-menu")) {
      hideContextMenu();
    }

    const button = event.target.closest("[data-api-action]");
    if (!button || button.disabled) return;

    if (button.dataset.apiAction === "load-development-progress") {
      await loadDevelopmentProgress();
      return;
    }

    if (button.dataset.apiAction === "open-material-modal") {
      openMaterialCreateModal();
      return;
    }

    if (button.dataset.apiAction === "close-material-modal") {
      closeMaterialCreateModal();
      return;
    }

    if (button.dataset.apiAction === "retry-materials") {
      await loadMaterials(false);
      return;
    }

    if (button.dataset.apiAction === "clear-material-filters") {
      resetMaterialFilters();
      return;
    }

    if (button.dataset.apiAction === "load-more-materials") {
      await loadMaterials(true);
      return;
    }

    if (button.dataset.apiAction === "delete-material") {
      await deleteMaterial(
        button.dataset.materialId,
        button.dataset.materialName || "未命名素材"
      );
      return;
    }

    if (button.dataset.apiAction === "back-to-materials") {
      await leaveMaterialDetail();
      return;
    }

    if (button.dataset.apiAction === "delete-current-material") {
      await deleteMaterial(
        button.dataset.materialId,
        button.dataset.materialName || "未命名素材",
        true
      );
      return;
    }

    if (button.dataset.apiAction === "remove-material-preview") {
      removePendingMaterialPreview(button.dataset.previewTarget);
      return;
    }

    if (button.dataset.apiAction === "open-project-modal") {
      openProjectModal();
      return;
    }

    if (button.dataset.apiAction === "close-project-modal") {
      closeProjectModal();
      return;
    }

    if (button.dataset.apiAction === "open-chapter-modal") {
      openChapterModal();
      return;
    }

    if (button.dataset.apiAction === "close-chapter-modal") {
      closeChapterModal();
      return;
    }

    if (button.dataset.apiAction === "open-large-scene-modal") {
      openLargeSceneModal(button.dataset.chapterId, button.dataset.chapterName);
      return;
    }

    if (button.dataset.apiAction === "close-large-scene-modal") {
      closeLargeSceneModal();
      return;
    }

    if (button.dataset.apiAction === "close-large-scene-edit-modal") {
      closeLargeSceneEditModal();
      return;
    }

    if (button.dataset.apiAction === "open-character-modal") {
      openCharacterModal();
      return;
    }

    if (button.dataset.apiAction === "close-character-modal") {
      closeCharacterModal();
      return;
    }

    if (button.dataset.apiAction === "close-character-detail-modal") {
      closeCharacterDetailModal();
      return;
    }

    if (button.dataset.apiAction === "select-character") {
      const card = button.closest(".character-block");
      if (card && card.dataset.characterId) {
        renderCharacterDetail(card.dataset.characterId);
      }
      return;
    }

    if (button.dataset.apiAction === "select-variant") {
      const modal = document.getElementById("character-detail-modal");
      modal?.querySelectorAll(".variant-tab.active").forEach((tab) => tab.classList.remove("active"));
      button.classList.add("active");
      await renderVariantSpecValues(
        button.dataset.variantId,
        button.dataset.variantName || ""
      );
      return;
    }

    if (button.dataset.apiAction === "retry-spec-values") {
      await renderVariantSpecValues(
        button.dataset.variantId,
        button.dataset.variantName || ""
      );
      return;
    }

    if (button.dataset.apiAction === "add-variant") {
      const modal = document.getElementById("character-detail-modal");
      const form = modal && modal.querySelector('form[data-inline-action="create-variant"]');
      if (form) {
        form.hidden = false;
        form.querySelector("input").focus();
      }
      return;
    }

    if (button.dataset.apiAction === "cancel-add-variant") {
      const form = button.closest('form[data-inline-action="create-variant"]');
      if (form) {
        form.hidden = true;
        form.reset();
      }
      return;
    }

    if (button.dataset.apiAction === "add-spec") {
      const modal = document.getElementById("character-detail-modal");
      const form = modal && modal.querySelector('form[data-inline-action="create-spec"]');
      if (form) {
        form.hidden = false;
        form.querySelector("select").focus();
      }
      return;
    }

    if (button.dataset.apiAction === "cancel-add-spec") {
      const form = button.closest('form[data-inline-action="create-spec"]');
      if (form) {
        form.hidden = true;
        form.reset();
      }
      return;
    }

    if (button.dataset.apiAction === "close-rename-modal") {
      closeRenameModal();
      return;
    }

    if (button.dataset.apiAction === "verify-isolation") {
      button.disabled = true;
      const originalText = button.textContent;
      button.textContent = "正在验证…";
      try {
        const result = await request("/api/settings/databases/verify-isolation", {
          method: "POST",
        });
        const message = `验证通过：测试库增加 1 条验证记录，生产库保持 ${result.production_rows_after} 条不变。`;
        const output = document.getElementById("database-result");
        if (output) {
          output.textContent = message;
          output.classList.add("success");
        }
        await refreshDatabaseState();
        if (typeof showToast === "function") showToast("生产库与测试库隔离验证通过");
      } catch (error) {
        const output = document.getElementById("database-result");
        if (output) output.textContent = `验证失败：${error.message}`;
        if (typeof showToast === "function") showToast(error.message);
      } finally {
        button.disabled = false;
        button.textContent = originalText;
      }
    }
  });

  document.addEventListener("click", (event) => {
    const card = event.target.closest(".real-project-card");
    if (!card) return;
    const params = new URLSearchParams();
    params.set("page", "overview");
    params.set("project", card.dataset.projectId);
    window.location.search = `?${params.toString()}`;
  });

  document.addEventListener("click", (event) => {
    const card = event.target.closest(".real-material-card");
    if (!card || event.target.closest("button, a, input, select, textarea")) return;
    navigateToMaterialDetail(card.dataset.materialId);
  });

  document.addEventListener("keydown", (event) => {
    const card = event.target.closest(".real-project-card");
    if (!card || !["Enter", " "].includes(event.key)) return;
    event.preventDefault();
    card.click();
  });

  document.addEventListener("keydown", (event) => {
    const card = event.target.closest(".real-material-card");
    if (!card || !["Enter", " "].includes(event.key)) return;
    event.preventDefault();
    navigateToMaterialDetail(card.dataset.materialId);
  });

  document.addEventListener("error", (event) => {
    const image = event.target.closest?.(".material-card-preview img, .material-detail-preview-large img");
    if (!image) return;
    image.remove();
  }, true);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeProjectModal();
      closeChapterModal();
      closeLargeSceneModal();
      closeLargeSceneEditModal();
      closeCharacterModal();
      closeRenameModal();
      closeConfirmDialog();
      closeMaterialCreateModal();
    }
  });

  window.addEventListener("beforeunload", (event) => {
    if (!materialDetailState.dirty) return;
    event.preventDefault();
    event.returnValue = "";
  });

  document.addEventListener("submit", async (event) => {
    const form = event.target.closest("form[data-inline-action]");
    if (!form) return;
    const action = form.dataset.inlineAction;
    if (action === "create-variant") {
      event.preventDefault();
      await submitInlineVariant(form);
    } else if (action === "create-spec") {
      event.preventDefault();
      await submitInlineSpec(form);
    } else if (action === "save-spec-value") {
      event.preventDefault();
      await submitCharacterSpecValue(form);
    }
  });

  async function submitInlineVariant(form) {
    const characterId = form.dataset.characterId;
    const input = form.querySelector("input");
    const submit = form.querySelector('button[type="submit"]');
    const error = submitInlineError(form);
    const name = input.value.trim().replace(/\s+/g, " ");
    if (!name) {
      error.textContent = "请输入变体名称。";
      input.focus();
      return;
    }
    submit.disabled = true;
    submit.textContent = "正在创建…";
    error.textContent = "";
    try {
      await request(`/api/characters/${characterId}/variants`, {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      form.hidden = true;
      form.reset();
      await refreshCharacterDetail();
      if (typeof showToast === "function") showToast(`形象变体「${name}」已创建`);
    } catch (requestError) {
      error.textContent = requestError.message;
      input.focus();
    } finally {
      submit.disabled = false;
      submit.textContent = "创建";
    }
  }

  async function submitInlineSpec(form) {
    const select = form.querySelector("select");
    const labelInput = form.querySelector('input[name="custom_label"]');
    const submit = form.querySelector('button[type="submit"]');
    const error = submitInlineError(form);
    const specType = select.value;
    const customLabel = (labelInput.value || "").trim().replace(/\s+/g, " ");
    if (specType === "custom" && !customLabel) {
      error.textContent = "自定义规格必须填写标签。";
      labelInput.focus();
      return;
    }
    submit.disabled = true;
    submit.textContent = "正在创建…";
    error.textContent = "";
    try {
      await request(`/api/specs`, {
        method: "POST",
        body: JSON.stringify({ spec_type: specType, custom_label: customLabel }),
      });
      form.hidden = true;
      form.reset();
      await refreshCharacterDetail();
      if (typeof showToast === "function") showToast("规格已创建");
    } catch (requestError) {
      error.textContent = requestError.message;
      select.focus();
    } finally {
      submit.disabled = false;
      submit.textContent = "创建";
    }
  }

  async function submitCharacterSpecValue(form) {
    const submit = form.querySelector('button[type="submit"]');
    const status = form.querySelector(".spec-save-status");
    const weightInput = form.elements.lora_weight;
    const weightText = weightInput.value.trim();
    const loraWeight = weightText === "" ? null : Number(weightText);
    if (
      loraWeight !== null &&
      (!Number.isFinite(loraWeight) || loraWeight < 0 || loraWeight > 2)
    ) {
      status.textContent = "权重必须在 0 到 2 之间";
      status.className = "spec-save-status error";
      weightInput.focus();
      return;
    }

    const payload = {
      prompt: form.elements.prompt.value,
      lora_name: form.elements.lora_name.value.trim(),
      lora_weight: loraWeight,
      model_override: form.elements.model_override.value.trim(),
      notes: form.elements.notes.value,
    };

    submit.disabled = true;
    submit.textContent = "保存中…";
    status.textContent = "";
    status.className = "spec-save-status";
    try {
      await request(`/api/character-spec-values/${form.dataset.specValueId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      const filled = Boolean(
        payload.prompt ||
        payload.lora_name ||
        payload.lora_weight !== null ||
        payload.model_override ||
        payload.notes
      );
      const fillState = form.querySelector(".spec-fill-state");
      if (fillState) {
        fillState.textContent = filled ? "已填写" : "未填写";
        fillState.classList.toggle("filled", filled);
      }
      status.textContent = "已保存";
      status.className = "spec-save-status success";
      if (typeof showToast === "function") showToast("人物规格已保存");
    } catch (requestError) {
      status.textContent = requestError.message;
      status.className = "spec-save-status error";
    } finally {
      submit.disabled = false;
      submit.textContent = "保存此规格";
    }
  }

  function submitInlineError(form) {
    let error = form.querySelector(".modal-error");
    if (!error) {
      error = document.createElement("div");
      error.className = "modal-error";
      form.insertBefore(error, form.firstChild);
    }
    return error;
  }

  refreshDatabaseState();
})();
