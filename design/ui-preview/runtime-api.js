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
      <article class="large-scene-block" data-large-scene-id="${escapeHtml(largeScene.id)}">
        <div class="large-scene-kicker">大场景 ${String(largeScene.sort_order).padStart(2, "0")}</div>
        <div class="large-scene-name">${escapeHtml(largeScene.name)}</div>
        <div class="large-scene-meta">尚未添加小场景</div>
        <div class="structure-actions">
          <button
            class="structure-action"
            data-api-action="rename-large-scene"
            data-large-scene-id="${escapeHtml(largeScene.id)}"
            data-name="${escapeHtml(largeScene.name)}"
          >改名</button>
          <button
            class="structure-action danger"
            data-api-action="delete-large-scene"
            data-large-scene-id="${escapeHtml(largeScene.id)}"
            data-name="${escapeHtml(largeScene.name)}"
          >删除</button>
        </div>
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
        <article class="real-chapter-block">
          <div class="real-chapter-kicker">章节 ${String(chapter.sort_order).padStart(2, "0")}</div>
          <div class="real-chapter-name">${escapeHtml(chapter.name)}</div>
          <div class="real-chapter-meta">${largeScenes.length} 个大场景</div>
          <div class="structure-actions">
            <button
              class="structure-action"
              data-api-action="rename-chapter"
              data-chapter-id="${escapeHtml(chapter.id)}"
              data-name="${escapeHtml(chapter.name)}"
            >改名</button>
            <button
              class="structure-action danger"
              data-api-action="delete-chapter"
              data-chapter-id="${escapeHtml(chapter.id)}"
              data-name="${escapeHtml(chapter.name)}"
              data-large-scene-count="${largeScenes.length}"
            >删除</button>
          </div>
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

  function openRenameModal(type, id, currentName) {
    const modal = ensureRenameModal();
    const typeName = type === "chapter" ? "章节" : "大场景";
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
    const typeName = type === "chapter" ? "章节" : "大场景";
    if (!name) {
      error.textContent = `请输入${typeName}名称。`;
      input.focus();
      return;
    }
    submit.disabled = true;
    submit.textContent = "正在保存…";
    error.textContent = "";
    try {
      const path = type === "chapter"
        ? `/api/chapters/${id}`
        : `/api/large-scenes/${id}`;
      await request(path, {
        method: "PATCH",
        body: JSON.stringify({ name }),
      });
      closeRenameModal();
      const project = await resolveCurrentProject();
      await renderProductionStoryCanvas(project);
      if (typeof showToast === "function") showToast(`${typeName}已改名为「${name}」`);
    } catch (requestError) {
      error.textContent = requestError.message;
      input.focus();
    } finally {
      submit.disabled = false;
      submit.textContent = "保存名称";
    }
  }

  async function deleteChapter(button) {
    const chapterId = button.dataset.chapterId;
    const name = button.dataset.name;
    const largeSceneCount = Number(button.dataset.largeSceneCount || 0);
    const sceneWarning = largeSceneCount
      ? `，其中 ${largeSceneCount} 个大场景也会一并删除`
      : "";
    if (!window.confirm(`确定删除章节「${name}」吗${sceneWarning}？此操作无法撤销。`)) {
      return;
    }
    button.disabled = true;
    try {
      await request(`/api/chapters/${chapterId}`, { method: "DELETE" });
      const project = await resolveCurrentProject();
      await renderProductionStoryCanvas(project);
      if (typeof showToast === "function") showToast(`章节「${name}」已删除`);
    } catch (requestError) {
      button.disabled = false;
      if (typeof showToast === "function") showToast(requestError.message);
    }
  }

  async function deleteLargeScene(button) {
    const largeSceneId = button.dataset.largeSceneId;
    const name = button.dataset.name;
    if (!window.confirm(`确定删除大场景「${name}」吗？此操作无法撤销。`)) {
      return;
    }
    button.disabled = true;
    try {
      await request(`/api/large-scenes/${largeSceneId}`, { method: "DELETE" });
      const project = await resolveCurrentProject();
      await renderProductionStoryCanvas(project);
      if (typeof showToast === "function") showToast(`大场景「${name}」已删除`);
    } catch (requestError) {
      button.disabled = false;
      if (typeof showToast === "function") showToast(requestError.message);
    }
  }

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

    if (button.dataset.apiAction === "rename-chapter") {
      openRenameModal("chapter", button.dataset.chapterId, button.dataset.name);
      return;
    }

    if (button.dataset.apiAction === "rename-large-scene") {
      openRenameModal(
        "large-scene",
        button.dataset.largeSceneId,
        button.dataset.name
      );
      return;
    }

    if (button.dataset.apiAction === "close-rename-modal") {
      closeRenameModal();
      return;
    }

    if (button.dataset.apiAction === "delete-chapter") {
      await deleteChapter(button);
      return;
    }

    if (button.dataset.apiAction === "delete-large-scene") {
      await deleteLargeScene(button);
      return;
    }

    if (button.dataset.apiAction === "activate-database") {
      const environment = button.dataset.environment;
      const warning = environment === "production"
        ? "将切换到生产数据库。这里保存的内容会成为你的正式数据，确认继续吗？"
        : "将切换到测试数据库。这里的数据只用于开发测试，不会进入你的正式项目，确认继续吗？";
      if (!window.confirm(warning)) return;
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
      closeRenameModal();
    }
  });

  refreshDatabaseState();
})();
