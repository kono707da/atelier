(function () {
  const environmentNames = {
    production: "生产数据库",
    test: "测试数据库",
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

  function setEnvironmentPill(environment, locked) {
    const pill = document.getElementById("environment-pill");
    if (!pill) return;
    pill.className = `environment-pill ${environment}`;
    pill.innerHTML = `<span class="environment-dot"></span><span>${environmentNames[environment]}${locked ? " · 已锁定" : ""}</span>`;
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
    return `
      <article
        class="large-scene-block"
        data-large-scene-id="${escapeHtml(largeScene.id)}"
        data-context-menu="large-scene"
        data-name="${escapeHtml(largeScene.name)}"
      >
        <div class="large-scene-kicker">大场景 ${String(largeScene.sort_order).padStart(2, "0")}</div>
        <div class="large-scene-name">${escapeHtml(largeScene.name)}</div>
        <div class="large-scene-meta">尚未添加小场景</div>
      </article>
    `;
  }

  function chapterBlock(chapter) {
    const largeScenes = chapter.large_scenes || [];
    const addLargeSceneButton = `
      <button
        class="btn compact"
        data-api-action="open-large-scene-modal"
        data-chapter-id="${escapeHtml(chapter.id)}"
        data-chapter-name="${escapeHtml(chapter.name)}"
      >添加大场景</button>
    `;
    return `
      <section class="real-chapter-section" data-chapter-id="${escapeHtml(chapter.id)}">
        <article
          class="real-chapter-block"
          data-context-menu="chapter"
          data-chapter-id="${escapeHtml(chapter.id)}"
          data-name="${escapeHtml(chapter.name)}"
          data-large-scene-count="${largeScenes.length}"
        >
          <div class="real-chapter-kicker">章节 ${String(chapter.sort_order).padStart(2, "0")}</div>
          <div class="real-chapter-name">${escapeHtml(chapter.name)}</div>
          <div class="real-chapter-meta">${largeScenes.length} 个大场景</div>
        </article>
        <div class="chapter-scene-connector" aria-hidden="true"></div>
        <div class="large-scene-lane">
          ${
            largeScenes.length
              ? `
                <div class="large-scene-track">
                  ${largeScenes.map(largeSceneBlock).join("")}
                  <div class="large-scene-add-card">${addLargeSceneButton}</div>
                </div>
              `
              : `
                <div class="large-scene-empty">
                  <span>这个章节还没有大场景</span>
                  ${addLargeSceneButton}
                </div>
              `
          }
        </div>
      </section>
    `;
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
    if (!chapters.total) {
      page.insertAdjacentHTML("beforeend", chapterEmptyState());
      return;
    }
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
      `
        <section class="panel real-story-panel">
          <div class="panel-header">
            <div>
              <div class="panel-title">章节与大场景</div>
              <div class="panel-sub">${chapters.total} 个章节 · ${largeSceneTotal} 个大场景 · 自动规整排列</div>
            </div>
          </div>
          <div class="real-story-viewport">
            <div class="real-story-stack">
              ${chapterItems.map(chapterBlock).join("")}
            </div>
          </div>
        </section>
      `
    );
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
          <ul class="character-spec-list">
            ${specs.map(specRow).join("")}
          </ul>
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
    hasMore: true,
    observer: null,
    statusTimer: null,
  };

  async function renderCharacterDatabasePage() {
    const page = document.querySelector(".page-scroll");
    if (!page) return;
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
    // Reset results container with table shell + scroll sentinel.
    const resultsEl = document.getElementById("character-database-results");
    if (resultsEl) {
      resultsEl.innerHTML =
        '<table class="character-database-table"><thead><tr>'
        + '<th>角色名</th><th>作品系列</th><th>触发词</th><th>核心标签</th><th>标签数</th><th>Danbooru</th>'
        + '</tr></thead><tbody></tbody></table>'
        + '<div class="character-database-sentinel" id="character-database-sentinel"></div>';
      setupCharacterDatabaseScrollObserver();
    }
    // Check backend status first; poll if still loading the CSV index.
    try {
      const statusPayload = await request("/api/character-database/status");
      if (statusPayload.state === "ready") {
        await loadCharacterDatabaseCopyrights();
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
          clearInterval(characterDatabaseState.statusTimer);
          characterDatabaseState.statusTimer = null;
          const resultsEl = document.getElementById("character-database-results");
          if (resultsEl) {
            resultsEl.innerHTML =
              '<table class="character-database-table"><thead><tr>'
              + '<th>角色名</th><th>作品系列</th><th>触发词</th><th>核心标签</th><th>标签数</th><th>Danbooru</th>'
              + '</tr></thead><tbody></tbody></table>'
              + '<div class="character-database-sentinel" id="character-database-sentinel"></div>';
            setupCharacterDatabaseScrollObserver();
          }
          await loadCharacterDatabaseCopyrights();
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
              !characterDatabaseState.isLoading &&
              characterDatabaseState.hasMore
            ) {
              characterDatabaseState.page += 1;
              loadCharacterDatabaseResults(true);
            }
          }
        }
      },
      { root: document.getElementById("character-database-results"), rootMargin: "64px" }
    );
    observer.observe(sentinel);
    characterDatabaseState.observer = observer;
  }

  async function loadCharacterDatabaseCopyrights() {
    const select = document.getElementById("character-database-copyright");
    if (!select) return;
    try {
      const payload = await request("/api/character-database/copyrights");
      const items = Array.isArray(payload.items)
        ? payload.items
        : Array.isArray(payload)
        ? payload
        : [];
      const current = characterDatabaseState.copyright;
      select.innerHTML =
        '<option value="">全部作品系列</option>' +
        items
          .map((item) => {
            const value =
              typeof item === "string"
                ? item
                : item.value || item.copyright || item.name || "";
            const label =
              typeof item === "string"
                ? item
                : item.label || item.copyright || item.name || value;
            return `<option value="${escapeHtml(value)}">${escapeHtml(label)}</option>`;
          })
          .join("");
      if (current) select.value = current;
    } catch (error) {
      select.innerHTML = '<option value="">全部作品系列</option>';
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
      const stats = characterPayload.stats || { variant_count: variantsPayload.items.length, spec_total: 0, spec_filled: 0 };
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
      <section class="atelier-modal" role="dialog" aria-modal="true" aria-labelledby="new-large-scene-title">
        <div class="atelier-modal-icon scene">SC</div>
        <h2 id="new-large-scene-title">新建大场景</h2>
        <p id="new-large-scene-context">大场景会按照创建顺序排列在所属章节中。</p>
        <form id="new-large-scene-form">
          <label class="label" for="new-large-scene-name">大场景名称</label>
          <input id="new-large-scene-name" class="modal-input" name="name" maxlength="80" autocomplete="off" placeholder="例如：公共沙滩" required />
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
    const context = modal.querySelector("#new-large-scene-context");
    modal.dataset.chapterId = chapterId;
    context.textContent = `添加到章节「${chapterName}」，并按照创建顺序排列。`;
    error.textContent = "";
    input.value = "";
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

  async function submitLargeScene(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const modal = form.closest(".atelier-modal-backdrop");
    const input = form.querySelector("input");
    const submit = form.querySelector('button[type="submit"]');
    const error = form.querySelector(".modal-error");
    const name = input.value.trim().replace(/\s+/g, " ");
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
        body: JSON.stringify({ name }),
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
    const response = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "请求失败");
    return payload;
  }

  async function refreshDatabaseState() {
    try {
      const payload = await request("/api/settings/databases");
      setEnvironmentPill(payload.active_environment, Boolean(payload.locked_environment));
      payload.databases.forEach(renderDatabaseCard);
      document.body.dataset.databaseEnvironment = payload.active_environment;
      const pageKey = new URLSearchParams(window.location.search).get("page") || "projects";
      if (pageKey === "projects") {
        await renderProductionProjects();
      } else if (pageKey === "characters") {
        await renderProductionCharacters();
      } else if (pageKey === "character-database") {
        await renderCharacterDatabasePage();
      } else if (pageKey !== "settings") {
        const project = await resolveCurrentProject();
        applyProjectHeader(project, pageKey);
        if (pageKey === "overview") await renderProductionOverview(project);
        else if (pageKey === "story-canvas") await renderProductionStoryCanvas(project);
        else applyProductionEmptyState();
      }
      const safety = document.getElementById("database-safety-status");
      if (safety) safety.innerHTML = '<span class="status green">物理隔离正常</span>';
      document.body.classList.remove("runtime-pending");
      return payload;
    } catch (error) {
      const pill = document.getElementById("environment-pill");
      if (pill) {
        pill.className = "environment-pill offline";
        pill.innerHTML = '<span class="environment-dot"></span><span>后端未连接</span>';
      }
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
        openRenameModal(type, id, name);
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
      document.querySelectorAll(".variant-tab.active").forEach((tab) => tab.classList.remove("active"));
      button.classList.add("active");
      const sub = document.querySelector(".character-expanded-sub");
      if (sub) {
        const specsCount = document.querySelectorAll(".character-spec-list .character-spec-row").length;
        sub.textContent = `${specsCount} 个规格 · 全项目共享 · 当前变体：${button.dataset.variantName || ""}`;
      }
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

    if (button.dataset.apiAction === "activate-database") {
      const environment = button.dataset.environment;
      const isProduction = environment === "production";
      const confirmed = await confirmDialog({
        title: isProduction ? "切换到生产数据库" : "切换到测试数据库",
        message: isProduction
          ? "这里保存的内容会成为你的正式数据，确认继续吗？"
          : "这里的数据只用于开发测试，不会进入你的正式项目，确认继续吗？",
        confirmText: "切换",
        danger: isProduction
      });
      if (!confirmed) return;
      button.disabled = true;
      try {
        await request("/api/settings/databases/activate", {
          method: "POST",
          body: JSON.stringify({
            environment,
            confirmation: environment === "production" ? "USE PRODUCTION" : null,
          }),
        });
        await refreshDatabaseState();
        if (typeof showToast === "function") showToast(`已切换到${environmentNames[environment]}`);
      } catch (error) {
        button.disabled = false;
        if (typeof showToast === "function") showToast(error.message);
      }
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

  document.addEventListener("keydown", (event) => {
    const card = event.target.closest(".real-project-card");
    if (!card || !["Enter", " "].includes(event.key)) return;
    event.preventDefault();
    card.click();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeProjectModal();
      closeChapterModal();
      closeLargeSceneModal();
      closeCharacterModal();
      closeRenameModal();
      closeConfirmDialog();
    }
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
