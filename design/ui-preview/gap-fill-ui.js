(function () {
  "use strict";

  const state = {
    project: null,
    review: { instances: [], tags: [], selectedPage: "", selectedInstance: "" },
    assembly: { versions: [], selectedVersion: "", items: [] },
    gallery: { items: [], cursor: "", nextCursor: null, history: [], query: "", loading: false, controller: null },
    export: { versions: [], presets: [], jobs: [], selectedVersion: "" },
    settings: { directory: null, system: null, recycle: [], projects: [], legacyJob: null },
  };

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (character) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;",
    })[character]);
  }

  function parseJson(value, fallback = null) {
    if (value === null || value === undefined || value === "") return fallback;
    if (typeof value === "object") return value;
    try { return JSON.parse(value); } catch (_) { return fallback; }
  }

  function formatDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString("zh-CN", { hour12: false });
  }

  function formatBytes(value) {
    const bytes = Number(value) || 0;
    if (!bytes) return "0 B";
    const units = ["B", "KB", "MB", "GB", "TB"];
    const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    return `${(bytes / 1024 ** index).toFixed(index > 1 ? 2 : 0)} ${units[index]}`;
  }

  function shortId(value) {
    return String(value || "").slice(0, 8) || "—";
  }

  function toast(message) {
    if (typeof window.showToast === "function") {
      window.showToast(message);
      return;
    }
    let node = document.getElementById("gap-fill-toast");
    if (!node) {
      node = document.createElement("div");
      node.id = "gap-fill-toast";
      node.className = "gap-fill-toast";
      document.body.appendChild(node);
    }
    node.textContent = message;
    node.classList.add("show");
    window.clearTimeout(node._timer);
    node._timer = window.setTimeout(() => node.classList.remove("show"), 2400);
  }

  async function request(path, options = {}) {
    const isFormData = options.body instanceof FormData;
    const response = await fetch(path, {
      ...options,
      headers: isFormData ? (options.headers || {}) : { "Content-Type": "application/json", ...(options.headers || {}) },
    });
    const contentType = response.headers.get("content-type") || "";
    let payload = {};
    if (contentType.includes("application/json")) {
      try { payload = await response.json(); } catch (_) { payload = {}; }
    }
    if (!response.ok) {
      const message = payload?.error?.message || payload?.detail || `请求失败（${response.status}）`;
      const error = new Error(typeof message === "string" ? message : JSON.stringify(message));
      error.status = response.status;
      error.payload = payload;
      throw error;
    }
    return payload;
  }

  function pageElement() {
    return document.querySelector(".page-scroll") || document.querySelector(".page");
  }

  function currentParams() {
    return new URLSearchParams(window.location.search);
  }

  function projectId() {
    return state.project?.id || currentParams().get("project") || "";
  }

  function navigate(page, values = {}) {
    const params = currentParams();
    params.set("page", page);
    Object.entries(values).forEach(([key, value]) => {
      if (value === null || value === undefined || value === "") params.delete(key);
      else params.set(key, value);
    });
    window.location.search = `?${params.toString()}`;
  }

  function loading(label = "正在读取数据…") {
    return `<section class="gap-fill-loading"><i></i><span>${escapeHtml(label)}</span></section>`;
  }

  function empty(title, description, action = "") {
    return `<section class="gap-fill-empty"><span>AT</span><h2>${escapeHtml(title)}</h2><p>${escapeHtml(description)}</p>${action}</section>`;
  }

  function statusPill(value) {
    const labels = {
      pending: "等待", running: "运行中", paused: "已暂停", completed: "已完成",
      failed: "失败", cancelled: "已取消", open: "待处理", resolved: "已解决",
      ignored: "已忽略", active: "有效", adopted: "已采用", rejected: "已淘汰",
    };
    const css = ["completed", "resolved", "active", "adopted"].includes(value)
      ? "green" : ["failed", "open", "rejected"].includes(value) ? "red" : "orange";
    return `<span class="status ${css}"><i class="dot"></i>${escapeHtml(labels[value] || value || "未知")}</span>`;
  }

  function imageUrl(fileId, size = "640") {
    return `/api/files/${encodeURIComponent(fileId)}/thumbnails/${size}/image`;
  }

  function originalUrl(fileId) {
    return `/api/files/${encodeURIComponent(fileId)}/download`;
  }

  function lazyImage(fileId, alt, css = "") {
    if (!fileId) return `<div class="gap-fill-image-placeholder">无图片</div>`;
    return `<img class="gap-fill-lazy-image ${css}" src="${imageUrl(fileId)}" data-original-src="${originalUrl(fileId)}" alt="${escapeHtml(alt)}" loading="lazy" decoding="async" />`;
  }

  function setPage(markup) {
    const page = pageElement();
    if (page) page.innerHTML = markup;
  }

  async function render(pageKey, project) {
    state.project = project || state.project;
    if (pageKey === "review") return renderReview(project);
    if (pageKey === "assembly") return renderAssembly(project);
    if (pageKey === "library") return renderGallery();
    if (pageKey === "image-detail") return renderImageDetail();
    if (pageKey === "export") return renderExport(project);
    if (pageKey === "settings") return enhanceSettings();
    return enhance(pageKey, project);
  }

  async function enhance(pageKey, project) {
    state.project = project || state.project;
    if (pageKey === "materials") enhanceMaterials();
    else if (pageKey === "material-detail") enhanceMaterialDetail();
    else if (pageKey === "characters") enhanceCharacters();
    else if (pageKey === "character-database") enhanceCharacterDatabase();
    else if (pageKey === "story-canvas") enhanceStoryCanvas();
    else if (pageKey === "workflow-canvas") enhanceWorkflowCanvas();
    else if (pageKey === "batch" || pageKey === "tasks") enhanceBatchPages(pageKey);
    else if (pageKey === "settings") await enhanceSettings();
  }

  function reviewState(instance) {
    if (Number(instance.is_rejected)) return "rejected";
    if (Number(instance.is_adopted)) return "adopted";
    return "candidate";
  }

  function reviewCard(instance) {
    const selected = String(instance.id) === String(state.review.selectedInstance);
    const review = reviewState(instance);
    return `
      <article class="gap-review-card ${review} ${selected ? "selected" : ""}" data-gap-action="review-select" data-instance-id="${escapeHtml(instance.id)}">
        <div class="gap-review-image">
          ${lazyImage(instance.file_id, `图片 ${shortId(instance.id)}`)}
          <span class="gap-review-index">${shortId(instance.id)}</span>
          ${Number(instance.is_representative) ? '<span class="gap-review-representative">代表图</span>' : ""}
        </div>
        <div class="gap-review-card-meta">
          ${statusPill(review)}
          <span>${Number(instance.width) || "?"} × ${Number(instance.height) || "?"}</span>
          <span>Seed ${instance.seed ?? "—"}</span>
        </div>
        <div class="gap-review-card-actions">
          ${review === "adopted"
            ? `<button class="btn small" data-gap-action="review-unadopt" data-instance-id="${escapeHtml(instance.id)}">取消采用</button>`
            : `<button class="btn small primary" data-gap-action="review-adopt" data-instance-id="${escapeHtml(instance.id)}">采用</button>`}
          <button class="btn small danger-soft" data-gap-action="review-reject" data-instance-id="${escapeHtml(instance.id)}">${review === "rejected" ? "保持淘汰" : "淘汰"}</button>
        </div>
      </article>`;
  }

  function reviewInspector(instance) {
    if (!instance) return `<div class="gap-review-inspector-empty">选择一张图片后，可评分、写备注、设置标签和查看完整追踪。</div>`;
    const attached = parseJson(instance.tags_json, []);
    return `
      <div class="gap-review-inspector-head">
        <div><span>图片实例</span><strong>${escapeHtml(shortId(instance.id))}</strong></div>
        <button class="btn small" data-gap-action="open-image-detail" data-instance-id="${escapeHtml(instance.id)}" data-file-id="${escapeHtml(instance.file_id)}">详情</button>
      </div>
      <label class="gap-field"><span>评分</span><select id="gap-review-rating">
        ${[0,1,2,3,4,5].map((value) => `<option value="${value}"${Number(instance.star_rating || 0) === value ? " selected" : ""}>${value ? `${"★".repeat(value)} ${value} 星` : "未评分"}</option>`).join("")}
      </select></label>
      <label class="gap-field"><span>颜色标记</span><select id="gap-review-color">
        ${["none","red","orange","yellow","green","blue","purple"].map((value) => `<option value="${value}"${(instance.color_label || "none") === value ? " selected" : ""}>${({none:"无",red:"红",orange:"橙",yellow:"黄",green:"绿",blue:"蓝",purple:"紫"})[value]}</option>`).join("")}
      </select></label>
      <label class="gap-field"><span>审片备注</span><textarea id="gap-review-note" rows="5" placeholder="记录选择理由、需要重跑的细节或后续处理">${escapeHtml(instance.review_note || "")}</textarea></label>
      <button class="btn primary" data-gap-action="review-save" data-instance-id="${escapeHtml(instance.id)}">保存审片信息</button>
      <div class="gap-review-tag-section">
        <div class="gap-section-title"><strong>标签</strong><button class="btn small" data-gap-action="review-create-tag">新建标签</button></div>
        <div class="gap-review-tags" id="gap-review-tags">
          ${state.review.tags.map((tag) => {
            const active = attached.some((item) => String(item.id || item) === String(tag.id));
            return `<button class="gap-tag ${active ? "active" : ""}" style="--tag-color:${escapeHtml(tag.color || "#7c8aa5")}" data-gap-action="review-toggle-tag" data-instance-id="${escapeHtml(instance.id)}" data-tag-id="${escapeHtml(tag.id)}" data-active="${active ? "1" : "0"}">${escapeHtml(tag.name)}</button>`;
          }).join("") || '<span class="gap-muted">还没有标签</span>'}
        </div>
      </div>
      <div class="gap-review-secondary-actions">
        <button class="btn small" data-gap-action="review-representative" data-instance-id="${escapeHtml(instance.id)}">设为代表图</button>
        <button class="btn small" data-gap-action="review-tracking" data-instance-id="${escapeHtml(instance.id)}">生成追踪</button>
        <button class="btn small" data-gap-action="review-copy-params" data-instance-id="${escapeHtml(instance.id)}">复制参数</button>
      </div>`;
  }

  async function loadSelectedInstanceTags() {
    const id = state.review.selectedInstance;
    if (!id) return;
    try {
      const payload = await request(`/api/image-instances/${encodeURIComponent(id)}/tags`);
      const result = payload.result || {};
      const tags = Array.isArray(result) ? result : (result.tags || []);
      const instance = state.review.instances.find((item) => String(item.id) === String(id));
      if (instance) instance.tags_json = JSON.stringify(tags);
    } catch (_) { /* 图片可能尚未设置标签。 */ }
  }

  async function renderReview(project) {
    const page = pageElement();
    if (!page) return;
    if (!project) {
      setPage(empty("没有可审片的项目", "先从项目中心打开一个项目，再进入审片图库。"));
      return;
    }
    page.innerHTML = loading("正在按分镜页读取图片实例…");
    const [instancesPayload, tagsPayload] = await Promise.all([
      request(`/api/image-instances?project_id=${encodeURIComponent(project.id)}&limit=500&offset=0`),
      request("/api/image-tags"),
    ]);
    state.review.instances = instancesPayload.image_instances || [];
    state.review.tags = tagsPayload.tags || [];
    const pages = [...new Set(state.review.instances.map((item) => item.shot_page_id).filter(Boolean))];
    const requestedPage = currentParams().get("shotPage");
    if (!state.review.selectedPage || !pages.includes(state.review.selectedPage)) {
      state.review.selectedPage = pages.includes(requestedPage) ? requestedPage : (pages[0] || "");
    }
    const pageInstances = state.review.instances.filter((item) => item.shot_page_id === state.review.selectedPage);
    if (!state.review.selectedInstance || !pageInstances.some((item) => String(item.id) === String(state.review.selectedInstance))) {
      state.review.selectedInstance = pageInstances[0]?.id || "";
    }
    await loadSelectedInstanceTags();
    const selected = state.review.instances.find((item) => String(item.id) === String(state.review.selectedInstance));
    const adopted = pageInstances.filter((item) => Number(item.is_adopted)).sort((a, b) => Number(a.sort_order) - Number(b.sort_order));
    page.innerHTML = `
      <div class="page-header">
        <div><h1 class="page-title">项目审片图库</h1><p class="page-subtitle">${escapeHtml(project.name)} · 按分镜页采用、淘汰、排序并记录审片结论。</p></div>
        <div class="header-actions"><button class="btn" data-gap-action="review-refresh">刷新</button><button class="btn primary" data-gap-action="open-batch-for-project">生成更多</button></div>
      </div>
      ${state.review.instances.length ? `
        <div class="gap-review-layout">
          <aside class="panel gap-review-pages">
            <div class="gap-panel-head"><div><strong>分镜页</strong><span>${pages.length} 页 · ${state.review.instances.length} 个实例</span></div></div>
            <div class="gap-review-page-list">${pages.map((id, index) => {
              const list = state.review.instances.filter((item) => item.shot_page_id === id);
              const adoptedCount = list.filter((item) => Number(item.is_adopted)).length;
              return `<button class="gap-review-page ${id === state.review.selectedPage ? "active" : ""}" data-gap-action="review-page" data-page-id="${escapeHtml(id)}"><span>${String(index + 1).padStart(3,"0")}</span><div><strong>页面 ${shortId(id)}</strong><small>${list.length} 个实例 · ${adoptedCount} 张采用</small></div></button>`;
            }).join("")}</div>
          </aside>
          <main class="panel gap-review-main">
            <div class="gap-panel-head"><div><strong>候选实例</strong><span>页面 ${shortId(state.review.selectedPage)} · 可同时采用多张</span></div><div class="gap-review-summary"><span>${adopted.length} 张已采用</span><span>${pageInstances.filter((item) => Number(item.is_rejected)).length} 张已淘汰</span></div></div>
            <div class="gap-review-grid">${pageInstances.map(reviewCard).join("")}</div>
            <div class="gap-adopted-order">
              <div class="gap-section-title"><strong>本页采用顺序</strong><span>通过上移/下移确定进入最终作品的页内顺序</span></div>
              <div class="gap-adopted-list">${adopted.map((item, index) => `<article><span>${index + 1}</span>${lazyImage(item.file_id, "已采用图片", "tiny")}<strong>${shortId(item.id)}</strong><div><button class="btn small" data-gap-action="review-order-up" data-instance-id="${escapeHtml(item.id)}" ${index === 0 ? "disabled" : ""}>上移</button><button class="btn small" data-gap-action="review-order-down" data-instance-id="${escapeHtml(item.id)}" ${index === adopted.length - 1 ? "disabled" : ""}>下移</button></div></article>`).join("") || '<p class="gap-muted">本页还没有采用图片。</p>'}</div>
            </div>
          </main>
          <aside class="panel gap-review-inspector">${reviewInspector(selected)}</aside>
        </div>` : empty("还没有图片实例", "完成一次真实出图并收集输出后，候选图片会按分镜页出现在这里。", '<button class="btn primary" data-gap-action="open-batch-for-project">前往批量配置</button>')}
    `;
  }

  async function mutateReview(instanceId, action) {
    await request(`/api/image-instances/${encodeURIComponent(instanceId)}/${action}`, { method: "POST", body: "{}" });
    await renderReview(state.project);
  }

  async function reorderAdopted(instanceId, delta) {
    const pageItems = state.review.instances
      .filter((item) => item.shot_page_id === state.review.selectedPage && Number(item.is_adopted))
      .sort((a, b) => Number(a.sort_order) - Number(b.sort_order));
    const index = pageItems.findIndex((item) => String(item.id) === String(instanceId));
    const target = index + delta;
    if (index < 0 || target < 0 || target >= pageItems.length) return;
    [pageItems[index], pageItems[target]] = [pageItems[target], pageItems[index]];
    await request(`/api/shot-pages/${encodeURIComponent(state.review.selectedPage)}/adopted-order`, {
      method: "PUT",
      body: JSON.stringify({ instance_ids: pageItems.map((item) => item.id) }),
    });
    await renderReview(state.project);
  }

  function finalVersionCard(version) {
    return `<button class="gap-version-card ${String(version.id) === String(state.assembly.selectedVersion) ? "active" : ""}" data-gap-action="assembly-select-version" data-version-id="${escapeHtml(version.id)}">
      <span>FV</span><div><strong>${escapeHtml(version.name || "未命名版本")}</strong><small>${escapeHtml(version.description || "没有说明")} · ${formatDate(version.updated_at || version.created_at)}</small></div>${Number(version.is_archived) ? statusPill("paused") : statusPill("active")}
    </button>`;
  }

  function sequenceItem(item, index, total) {
    const fileId = item.file_id || item.image_file_id;
    return `<article class="gap-sequence-item">
      <div class="gap-sequence-number">${String(index + 1).padStart(3, "0")}</div>
      <button class="gap-sequence-image" data-gap-action="open-image-detail" data-instance-id="${escapeHtml(item.image_instance_id || "")}" data-file-id="${escapeHtml(fileId || "")}">${lazyImage(fileId, `最终序列 ${index + 1}`)}</button>
      <div class="gap-sequence-copy"><strong>${escapeHtml(item.original_name || shortId(item.image_instance_id))}</strong><small>来源页 ${shortId(item.source_shot_page_id)}${item.source_branch_id ? ` · 分支 ${shortId(item.source_branch_id)}` : ""}</small></div>
      <div class="gap-sequence-actions">
        <button class="btn small" data-gap-action="assembly-move" data-item-id="${escapeHtml(item.id)}" data-delta="-1" ${index === 0 ? "disabled" : ""}>前移</button>
        <button class="btn small" data-gap-action="assembly-move" data-item-id="${escapeHtml(item.id)}" data-delta="1" ${index === total - 1 ? "disabled" : ""}>后移</button>
        <button class="btn small danger-soft" data-gap-action="assembly-remove" data-item-id="${escapeHtml(item.id)}">移除</button>
      </div>
    </article>`;
  }

  async function renderAssembly(project) {
    const page = pageElement();
    if (!page) return;
    if (!project) {
      setPage(empty("没有可装配的项目", "先打开一个项目并在审片页采用图片。"));
      return;
    }
    page.innerHTML = loading("正在读取最终版本与作品顺序…");
    const payload = await request(`/api/projects/${encodeURIComponent(project.id)}/final-versions`);
    state.assembly.versions = payload.items || [];
    const requested = currentParams().get("version");
    if (!state.assembly.selectedVersion || !state.assembly.versions.some((item) => String(item.id) === String(state.assembly.selectedVersion))) {
      state.assembly.selectedVersion = state.assembly.versions.some((item) => String(item.id) === String(requested)) ? requested : (state.assembly.versions[0]?.id || "");
    }
    if (state.assembly.selectedVersion) {
      const itemsPayload = await request(`/api/final-versions/${encodeURIComponent(state.assembly.selectedVersion)}/items`);
      state.assembly.items = itemsPayload.items || [];
    } else {
      state.assembly.items = [];
    }
    const selected = state.assembly.versions.find((item) => String(item.id) === String(state.assembly.selectedVersion));
    page.innerHTML = `
      <div class="page-header">
        <div><h1 class="page-title">最终作品装配</h1><p class="page-subtitle">${escapeHtml(project.name)} · 最终顺序独立于剧本页序，可建立多个成片版本。</p></div>
        <div class="header-actions"><button class="btn" data-gap-action="assembly-refresh">刷新</button><button class="btn primary" data-gap-action="assembly-create-version">创建版本</button></div>
      </div>
      <div class="gap-assembly-layout">
        <aside class="panel gap-version-list">
          <div class="gap-panel-head"><div><strong>成片版本</strong><span>${state.assembly.versions.length} 个版本</span></div></div>
          <div>${state.assembly.versions.map(finalVersionCard).join("") || '<p class="gap-muted gap-pad">还没有最终版本。</p>'}</div>
        </aside>
        <main class="panel gap-sequence-panel">
          ${selected ? `
            <div class="gap-panel-head gap-sequence-toolbar"><div><strong>${escapeHtml(selected.name)}</strong><span>${state.assembly.items.length} 张图片 · ${escapeHtml(selected.description || "没有说明")}</span></div><div>
              <button class="btn small" data-gap-action="assembly-rename-version">改名</button>
              <button class="btn small" data-gap-action="assembly-generate-default">补充默认顺序</button>
              <button class="btn small" data-gap-action="assembly-rebuild">从采用结果重建</button>
              <button class="btn small danger-soft" data-gap-action="assembly-delete-version">删除版本</button>
            </div></div>
            <div class="gap-sequence-list">${state.assembly.items.map((item, index) => sequenceItem(item, index, state.assembly.items.length)).join("") || empty("版本还是空的", "点击“从采用结果重建”，把项目中已采用的图片按默认顺序加入。")}</div>
          ` : empty("还没有最终版本", "创建版本后，可以从采用结果生成默认成片序列。", '<button class="btn primary" data-gap-action="assembly-create-version">创建第一个版本</button>')}
        </main>
      </div>`;
  }

  async function createFinalVersion() {
    const name = window.prompt("最终版本名称", "成片版本 1");
    if (name === null || !name.trim()) return;
    const description = window.prompt("版本说明（可留空）", "") ?? "";
    const payload = await request(`/api/projects/${encodeURIComponent(projectId())}/final-versions`, {
      method: "POST", body: JSON.stringify({ name: name.trim(), description: description.trim() }),
    });
    state.assembly.selectedVersion = payload.final_version?.id || "";
    await renderAssembly(state.project);
  }

  async function reorderFinalItem(itemId, delta) {
    const items = [...state.assembly.items];
    const index = items.findIndex((item) => String(item.id) === String(itemId));
    const target = index + delta;
    if (index < 0 || target < 0 || target >= items.length) return;
    [items[index], items[target]] = [items[target], items[index]];
    await request(`/api/final-versions/${encodeURIComponent(state.assembly.selectedVersion)}/items/reorder`, {
      method: "PUT", body: JSON.stringify({ item_ids: items.map((item) => item.id) }),
    });
    state.assembly.items = items;
    await renderAssembly(state.project);
  }

  function galleryCard(item) {
    const fileId = item.file_id || item.id;
    return `<button class="gap-gallery-card" data-gap-action="gallery-open" data-file-id="${escapeHtml(fileId)}">
      <div class="gap-gallery-image">${lazyImage(fileId, item.original_name || `图库图片 ${shortId(fileId)}`)}<span>${escapeHtml(item.format || item.mime_type || "IMAGE")}</span></div>
      <div class="gap-gallery-meta"><strong>${escapeHtml(item.original_name || shortId(fileId))}</strong><small>${Number(item.width) || "?"} × ${Number(item.height) || "?"} · ${formatBytes(item.size_bytes)}</small><small>${item.project_name ? escapeHtml(item.project_name) : `项目 ${shortId(item.project_id)}`} · Seed ${item.seed ?? "—"}</small></div>
    </button>`;
  }

  async function loadGallery({ reset = false, previous = false } = {}) {
    if (state.gallery.loading) return;
    state.gallery.loading = true;
    if (state.gallery.controller) state.gallery.controller.abort();
    state.gallery.controller = new AbortController();
    const form = document.getElementById("gap-gallery-filter");
    if (form) state.gallery.query = form.elements.q.value.trim();
    if (reset) {
      state.gallery.cursor = "";
      state.gallery.nextCursor = null;
      state.gallery.history = [];
    }
    if (previous) {
      state.gallery.cursor = state.gallery.history.pop() || "";
    }
    const params = new URLSearchParams({ limit: "100" });
    if (state.gallery.cursor) params.set("cursor", state.gallery.cursor);
    if (form) {
      if (form.elements.project_id.value) params.set("project_id", form.elements.project_id.value);
      if (form.elements.mime_type.value) params.set("mime_type", form.elements.mime_type.value);
      if (form.elements.has_phash.value) params.set("has_phash", form.elements.has_phash.value);
      if (form.elements.state.value) params.set("state", form.elements.state.value);
      params.set("sort", form.elements.sort.value || "created_desc");
    }
    const path = state.gallery.query
      ? `/api/gallery/search?q=${encodeURIComponent(state.gallery.query)}&cursor=${encodeURIComponent(state.gallery.cursor)}&limit=100`
      : `/api/gallery?${params.toString()}`;
    try {
      const payload = await request(path, { signal: state.gallery.controller.signal });
      state.gallery.items = payload.items || [];
      state.gallery.nextCursor = payload.next_cursor || null;
      renderGalleryBody();
    } catch (error) {
      if (error.name !== "AbortError") toast(error.message);
    } finally {
      state.gallery.loading = false;
    }
  }

  function renderGalleryBody() {
    const grid = document.getElementById("gap-gallery-grid");
    const meta = document.getElementById("gap-gallery-meta");
    const previous = document.querySelector('[data-gap-action="gallery-previous"]');
    const next = document.querySelector('[data-gap-action="gallery-next"]');
    if (grid) grid.innerHTML = state.gallery.items.map(galleryCard).join("") || empty("这一批没有图片", "调整搜索或筛选条件后重试。");
    if (meta) meta.textContent = `当前批次 ${state.gallery.items.length} 张 · 页面只保留这一批 DOM，适合百万级索引`;
    if (previous) previous.disabled = state.gallery.history.length === 0;
    if (next) next.disabled = !state.gallery.nextCursor;
  }

  async function renderGallery() {
    const page = pageElement();
    if (!page) return;
    page.innerHTML = `
      <div class="page-header"><div><h1 class="page-title">全局图库</h1><p class="page-subtitle">游标分页、服务端筛选和懒加载；页面只渲染当前 100 张，不随图库总量膨胀。</p></div><div class="header-actions"><button class="btn" data-gap-action="gallery-worker">生成缺失缩略图</button><button class="btn" data-gap-action="gallery-reindex">增量索引</button><button class="btn danger-soft" data-gap-action="gallery-reindex-force">全量重建</button></div></div>
      <section class="panel gap-gallery-shell">
        <form class="gap-gallery-filter" id="gap-gallery-filter">
          <input class="field" name="q" placeholder="搜索提示词（FTS5）" value="${escapeHtml(state.gallery.query)}" />
          <input class="field" name="project_id" placeholder="项目 ID（可选）" />
          <select class="field" name="mime_type"><option value="">全部格式</option><option value="image/png">PNG</option><option value="image/jpeg">JPEG</option><option value="image/webp">WebP</option></select>
          <select class="field" name="state"><option value="">全部状态</option><option value="active">有效</option><option value="deleted">已删除</option></select>
          <select class="field" name="has_phash"><option value="">感知哈希不限</option><option value="true">已计算 pHash</option><option value="false">缺少 pHash</option></select>
          <select class="field" name="sort"><option value="created_desc">最新优先</option><option value="created_asc">最早优先</option><option value="dimensions_desc">像素优先</option><option value="size_desc">文件大小优先</option></select>
          <button class="btn primary" type="submit">应用</button>
        </form>
        <div class="gap-gallery-batchbar"><span id="gap-gallery-meta">正在读取…</span><div><button class="btn small" data-gap-action="gallery-previous" disabled>上一批</button><button class="btn small primary" data-gap-action="gallery-next" disabled>下一批</button></div></div>
        <div class="gap-gallery-grid" id="gap-gallery-grid">${loading("正在读取图库索引…")}</div>
      </section>`;
    await loadGallery({ reset: true });
  }

  function detailMetaRows(file, index, instance) {
    const rows = [
      ["文件名", file.original_name || file.storage_key || "—"],
      ["尺寸", `${index.width || instance?.width || "?"} × ${index.height || instance?.height || "?"}`],
      ["格式", file.mime_type || index.mime_type || instance?.format || "—"],
      ["大小", formatBytes(file.size_bytes || index.size_bytes)],
      ["内容哈希", file.content_hash || index.content_hash || "—"],
      ["感知哈希", file.perceptual_hash || index.perceptual_hash || "尚未计算"],
      ["来源项目", index.project_name || shortId(index.project_id || instance?.project_id)],
      ["来源页面", index.shot_page_title || shortId(index.shot_page_id || instance?.shot_page_id)],
      ["工作流", index.workflow_name || shortId(index.workflow_version_id || instance?.workflow_version_id)],
      ["种子", index.seed ?? instance?.seed ?? "—"],
      ["创建时间", formatDate(file.created_at || index.source_created_at || instance?.created_at)],
    ];
    return rows.map(([key, value]) => `<div class="meta-row"><span class="meta-key">${escapeHtml(key)}</span><span class="meta-value">${escapeHtml(value)}</span></div>`).join("");
  }

  async function renderImageDetail() {
    const page = pageElement();
    if (!page) return;
    page.innerHTML = loading("正在读取图片、来源和审片信息…");
    const params = currentParams();
    let fileId = params.get("file") || "";
    let selectedInstance = null;
    if (!fileId && params.get("instance")) {
      const payload = await request(`/api/image-instances/${encodeURIComponent(params.get("instance"))}`);
      selectedInstance = payload.image_instance || null;
      fileId = payload.file?.id || selectedInstance?.file_id || "";
    }
    if (!fileId) {
      setPage(empty("没有选择图片", "请从全局图库或项目审片页打开一张图片。", '<button class="btn primary" data-gap-action="open-gallery">返回全局图库</button>'));
      return;
    }
    const payload = await request(`/api/gallery/${encodeURIComponent(fileId)}`);
    const detail = payload.detail || {};
    const file = detail.file || {};
    const index = detail.gallery_index || detail.index || {};
    const instances = detail.image_instances || detail.instances || [];
    selectedInstance = selectedInstance || instances[0] || null;
    const prompt = index.prompt_text || parseJson(selectedInstance?.snapshot_json, {})?.effective_config?.positive_prompt || "";
    page.innerHTML = `
      <div class="page-header"><div><h1 class="page-title">图片详情 · ${escapeHtml(file.original_name || shortId(fileId))}</h1><p class="page-subtitle">完整文件元数据、来源实例、审片状态和相同/近似图片。</p></div><div class="header-actions"><button class="btn" data-gap-action="open-gallery">返回图库</button><a class="btn primary" href="${originalUrl(fileId)}" download>下载原图</a></div></div>
      <div class="gap-image-detail-layout">
        <section class="panel gap-image-hero">${lazyImage(fileId, file.original_name || "原图", "hero")}<div class="gap-image-hero-actions"><button class="btn small" data-gap-action="detail-phash" data-file-id="${escapeHtml(fileId)}">计算 pHash</button><button class="btn small" data-gap-action="detail-reindex" data-file-id="${escapeHtml(fileId)}">刷新索引</button><button class="btn small" data-gap-action="detail-duplicates" data-file-id="${escapeHtml(fileId)}">查找相同</button><button class="btn small" data-gap-action="detail-similar" data-file-id="${escapeHtml(fileId)}">查找近似</button></div><div id="gap-image-related"></div></section>
        <section class="panel gap-image-meta"><div class="gap-panel-head"><div><strong>图片信息</strong><span>${instances.length} 个来源实例</span></div>${selectedInstance ? statusPill(reviewState(selectedInstance)) : ""}</div><div class="meta-list">${detailMetaRows(file, index, selectedInstance)}</div><label class="gap-field gap-pad"><span>最终提示词快照</span><textarea rows="8" readonly>${escapeHtml(prompt)}</textarea></label>${instances.length ? `<div class="gap-source-instances"><strong>来源实例</strong>${instances.map((instance) => `<button data-gap-action="image-detail-instance" data-instance-id="${escapeHtml(instance.id)}">${shortId(instance.id)} · ${statusPill(reviewState(instance))}</button>`).join("")}</div>` : ""}</section>
      </div>`;
  }

  function exportPresetCard(preset) {
    return `<article class="gap-export-preset"><div><strong>${escapeHtml(preset.name)}</strong><small>${escapeHtml(preset.format || "original")} · ${escapeHtml(preset.copy_mode || "copy")} · ${Number(preset.strip_metadata) ? "移除元数据" : "保留元数据"}</small><small>${escapeHtml(preset.output_pattern || "{index:04d}_{original_name}")}</small></div><button class="btn small danger-soft" data-gap-action="export-delete-preset" data-preset-id="${escapeHtml(preset.id)}">删除</button></article>`;
  }

  function exportJobRow(job) {
    const canRun = ["pending", "failed"].includes(job.status);
    const canCancel = ["pending", "running"].includes(job.status);
    return `<tr><td><strong>${shortId(job.id)}</strong><small>${escapeHtml(job.output_dir || "—")}</small></td><td>${escapeHtml(job.final_version_name || shortId(job.final_version_id))}</td><td>${statusPill(job.status)}</td><td>${Number(job.completed_items) || 0} / ${Number(job.total_items) || 0}</td><td>${formatDate(job.created_at)}</td><td><div class="gap-row-actions">${canRun ? `<button class="btn small primary" data-gap-action="export-run" data-job-id="${escapeHtml(job.id)}">执行</button>` : ""}${canCancel ? `<button class="btn small danger-soft" data-gap-action="export-cancel" data-job-id="${escapeHtml(job.id)}">取消</button>` : ""}</div></td></tr>`;
  }

  async function renderExport(project) {
    const page = pageElement();
    if (!page) return;
    if (!project) {
      setPage(empty("没有可导出的项目", "先打开一个项目并创建最终版本。"));
      return;
    }
    page.innerHTML = loading("正在读取最终版本、导出预设和历史记录…");
    const [versionPayload, presetPayload, jobPayload] = await Promise.all([
      request(`/api/projects/${encodeURIComponent(project.id)}/final-versions`),
      request("/api/export-presets"),
      request("/api/export-jobs"),
    ]);
    state.export.versions = versionPayload.items || [];
    state.export.presets = presetPayload.items || [];
    state.export.jobs = (jobPayload.items || []).filter((job) => state.export.versions.some((version) => version.id === job.final_version_id));
    if (!state.export.selectedVersion || !state.export.versions.some((item) => item.id === state.export.selectedVersion)) state.export.selectedVersion = state.export.versions[0]?.id || "";
    page.innerHTML = `
      <div class="page-header"><div><h1 class="page-title">导出中心</h1><p class="page-subtitle">${escapeHtml(project.name)} · 按最终序列重新编号，生成文件和来源清单。</p></div><div class="header-actions"><button class="btn" data-gap-action="export-refresh">刷新</button><button class="btn" data-gap-action="export-create-preset">新建预设</button></div></div>
      <div class="gap-export-layout">
        <section class="panel gap-export-create">
          <div class="gap-panel-head"><div><strong>新建导出</strong><span>创建任务后再执行，避免误写目标目录</span></div></div>
          ${state.export.versions.length ? `<form id="gap-export-job-form" class="gap-form-stack">
            <label class="gap-field"><span>最终版本</span><select name="version_id">${state.export.versions.map((item) => `<option value="${escapeHtml(item.id)}"${item.id === state.export.selectedVersion ? " selected" : ""}>${escapeHtml(item.name)}</option>`).join("")}</select></label>
            <label class="gap-field"><span>导出预设</span><select name="preset_id"><option value="">使用后端默认</option>${state.export.presets.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)}</option>`).join("")}</select></label>
            <label class="gap-field"><span>目标目录</span><input name="output_dir" placeholder="例如 D:\\Atelier Exports\\作品名" required /></label>
            <button class="btn primary" type="submit">创建导出任务</button>
          </form>` : empty("还没有最终版本", "先到最终作品装配页创建一个版本。", '<button class="btn primary" data-gap-action="open-assembly">前往装配</button>')}
          <div class="gap-export-presets"><div class="gap-section-title"><strong>导出预设</strong><span>${state.export.presets.length} 个</span></div>${state.export.presets.map(exportPresetCard).join("") || '<p class="gap-muted">还没有自定义预设。</p>'}</div>
        </section>
        <section class="panel gap-export-jobs"><div class="gap-panel-head"><div><strong>导出记录</strong><span>执行、取消与错误状态都会持久化</span></div><button class="btn small" data-gap-action="export-worker">运行一个等待任务</button></div><div class="gap-table-wrap"><table class="table"><thead><tr><th>任务</th><th>版本</th><th>状态</th><th>进度</th><th>创建时间</th><th>操作</th></tr></thead><tbody>${state.export.jobs.map(exportJobRow).join("") || '<tr><td colspan="6"><div class="gap-table-empty">还没有导出记录。</div></td></tr>'}</tbody></table></div></section>
      </div>`;
  }

  async function createExportPreset() {
    const name = window.prompt("预设名称", "原图导出");
    if (name === null || !name.trim()) return;
    const format = window.prompt("格式：original / png / jpeg", "original") || "original";
    const copyMode = window.prompt("写入方式：copy / hardlink / reencode", "copy") || "copy";
    await request("/api/export-presets", { method: "POST", body: JSON.stringify({ name: name.trim(), description: "", format: format.trim(), copy_mode: copyMode.trim(), strip_metadata: false, output_pattern: "{index:04d}_{original_name}" }) });
    await renderExport(state.project);
  }

  function directoryPanel(directory) {
    const fields = [
      ["data_dir", "数据目录", directory?.data_dir || ""],
      ["images_dir", "图片目录", directory?.images_dir || ""],
      ["cache_dir", "缓存目录", directory?.cache_dir || ""],
      ["tmp_dir", "临时目录", directory?.tmp_dir || ""],
    ];
    return `<section class="panel gap-settings-panel"><div class="gap-panel-head"><div><strong>目录配置</strong><span>留空保存可恢复后端默认目录；保存前可逐项检查可写性与剩余空间。</span></div></div><form id="gap-directory-form" class="gap-directory-form">${fields.map(([key, label, value]) => `<label class="gap-field"><span>${label}</span><div><input name="${key}" value="${escapeHtml(value)}" placeholder="使用默认目录" /><button class="btn small" type="button" data-gap-action="directory-check" data-field="${key}">检查</button></div><small data-directory-result="${key}"></small></label>`).join("")}<button class="btn primary" type="submit">保存目录配置</button></form></section>`;
  }

  function systemInfoPanel(info) {
    const migrations = info?.migrations || info?.migration_versions || [];
    return `<section class="panel gap-settings-panel"><div class="gap-panel-head"><div><strong>数据库与系统</strong><span>所有维护操作都显示真实结果，不修改生产数据前会要求确认。</span></div><button class="btn small" data-gap-action="maintenance-refresh">刷新信息</button></div><div class="gap-system-metrics"><div><span>数据库路径</span><strong>${escapeHtml(info?.database_path || info?.db_path || "—")}</strong></div><div><span>数据库大小</span><strong>${formatBytes(info?.database_size || info?.database_size_bytes)}</strong></div><div><span>数据表</span><strong>${Number(info?.table_count || Object.keys(info?.table_counts || {}).length) || 0}</strong></div><div><span>迁移版本</span><strong>${Array.isArray(migrations) ? migrations.length : Object.keys(migrations || {}).length}</strong></div></div><div class="gap-maintenance-grid">
      <button class="btn" data-gap-action="maintenance-integrity">完整性检查</button><button class="btn" data-gap-action="maintenance-orphans">孤立文件检查</button><button class="btn" data-gap-action="maintenance-optimize">优化数据库</button><button class="btn" data-gap-action="maintenance-clear-cache">清理缓存</button><button class="btn" data-gap-action="maintenance-rebuild-fts">重建全文索引</button><button class="btn" data-gap-action="maintenance-recompute-phash">补算 pHash</button><button class="btn" data-gap-action="maintenance-clean-temp">清理临时文件</button><button class="btn" data-gap-action="maintenance-clean-trash">清理过期回收站</button><button class="btn primary" data-gap-action="maintenance-backup">创建备份</button><button class="btn danger-soft" data-gap-action="maintenance-restore">从备份恢复</button></div><pre class="gap-result-box" id="gap-maintenance-result">选择一项维护操作后，结果会显示在这里。</pre></section>`;
  }

  function recyclePanel(entries) {
    return `<section class="panel gap-settings-panel"><div class="gap-panel-head"><div><strong>统一回收站</strong><span>${entries.length} 项 · 恢复会返回保存的实体快照，永久清除不可撤销。</span></div><button class="btn small danger-soft" data-gap-action="recycle-purge-expired">清理 30 天前条目</button></div><div class="gap-recycle-list">${entries.map((entry) => `<article><span class="gap-entity-code">${escapeHtml(String(entry.entity_type || "IT").slice(0,2).toUpperCase())}</span><div><strong>${escapeHtml(entry.entity_name || shortId(entry.entity_id))}</strong><small>${escapeHtml(entry.entity_type)} · ${formatDate(entry.deleted_at || entry.created_at)}${entry.expires_at ? ` · 到期 ${formatDate(entry.expires_at)}` : ""}</small></div><button class="btn small" data-gap-action="recycle-restore" data-entry-id="${escapeHtml(entry.id)}">恢复</button><button class="btn small danger-soft" data-gap-action="recycle-purge" data-entry-id="${escapeHtml(entry.id)}">永久清除</button></article>`).join("") || '<p class="gap-muted gap-pad">回收站为空。</p>'}</div></section>`;
  }

  function importPanel(projects) {
    return `<section class="panel gap-settings-panel gap-import-panel"><div class="gap-panel-head"><div><strong>导入、包交换与历史图库</strong><span>导入前先预检 manifest；旧图库采用增量检查点，可暂停、恢复和取消。</span></div></div><div class="gap-import-tabs">
      <section><h3>项目包</h3><label class="gap-field"><span>导出项目</span><select id="gap-package-project"><option value="">选择项目</option>${projects.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)}</option>`).join("")}</select></label><button class="btn" data-gap-action="package-export-project">生成项目 manifest</button><label class="gap-field"><span>项目 manifest JSON</span><textarea id="gap-project-manifest" rows="7" placeholder="导出结果或待导入 JSON"></textarea></label><div class="gap-row-actions"><button class="btn" data-gap-action="package-project-dry-run">预检</button><button class="btn primary" data-gap-action="package-project-import">执行导入</button></div></section>
      <section><h3>素材包</h3><label class="gap-field"><span>素材 ID（每行一个）</span><textarea id="gap-material-ids" rows="3" placeholder="material-id-1"></textarea></label><button class="btn" data-gap-action="package-export-materials">生成素材 manifest</button><label class="gap-field"><span>素材 manifest JSON</span><textarea id="gap-material-manifest" rows="7" placeholder="导出结果或待导入 JSON"></textarea></label><div class="gap-row-actions"><button class="btn" data-gap-action="package-materials-dry-run">预检</button><button class="btn primary" data-gap-action="package-materials-import">执行导入</button></div></section>
      <section><h3>旧图库索引</h3><label class="gap-field"><span>旧图片目录</span><input id="gap-legacy-directory" placeholder="例如 Z:\\主机文件共享\\AI作图笔记" /></label><label class="gap-field"><span>写入方式</span><select id="gap-legacy-link-mode"><option value="hardlink">硬链接（推荐）</option><option value="copy">复制</option></select></label><div class="gap-row-actions"><button class="btn" data-gap-action="legacy-scan">只扫描</button><button class="btn primary" data-gap-action="legacy-create-job">创建索引作业</button></div><div id="gap-legacy-job" class="gap-legacy-job"><span>尚未创建作业。</span></div></section>
    </div><pre class="gap-result-box" id="gap-import-result">预检和导入结果会显示在这里。</pre></section>`;
  }

  async function enhanceSettings() {
    const page = pageElement();
    if (!page || document.getElementById("gap-settings-root")) return;
    const root = document.createElement("div");
    root.id = "gap-settings-root";
    root.innerHTML = loading("正在读取目录、系统和回收站状态…");
    page.appendChild(root);
    try {
      const [directoryPayload, systemPayload, recyclePayload, projectPayload] = await Promise.all([
        request("/api/settings/directory"),
        request("/api/maintenance/system-info"),
        request("/api/recycle-bin?limit=100&offset=0"),
        request("/api/projects?limit=100&offset=0"),
      ]);
      state.settings.directory = directoryPayload.directory || {};
      state.settings.system = systemPayload.system_info || {};
      state.settings.recycle = recyclePayload.recycle_bin?.items || [];
      state.settings.projects = projectPayload.items || projectPayload.projects || [];
      root.innerHTML = `<div class="gap-settings-grid">${directoryPanel(state.settings.directory)}${systemInfoPanel(state.settings.system)}</div>${recyclePanel(state.settings.recycle)}${importPanel(state.settings.projects)}`;
    } catch (error) {
      root.innerHTML = `<section class="gap-fill-error"><strong>高级设置读取失败</strong><p>${escapeHtml(error.message)}</p><button class="btn" data-gap-action="settings-retry">重试</button></section>`;
    }
  }

  async function refreshSettings() {
    document.getElementById("gap-settings-root")?.remove();
    await enhanceSettings();
  }

  function maintenanceResult(payload) {
    const box = document.getElementById("gap-maintenance-result");
    if (box) box.textContent = JSON.stringify(payload, null, 2);
  }

  async function runMaintenance(path, options = {}) {
    const payload = await request(path, { method: options.method || "POST", body: options.body === undefined ? "{}" : JSON.stringify(options.body) });
    maintenanceResult(payload);
    toast("维护操作已完成");
    return payload;
  }

  function importResult(payload) {
    const box = document.getElementById("gap-import-result");
    if (box) box.textContent = JSON.stringify(payload, null, 2);
  }

  function renderLegacyJob(job) {
    state.settings.legacyJob = job;
    const wrap = document.getElementById("gap-legacy-job");
    if (!wrap || !job) return;
    const progress = parseJson(job.progress_json, {}) || job.progress || {};
    wrap.innerHTML = `<div><strong>作业 ${shortId(job.id)}</strong>${statusPill(job.status)}<small>已索引 ${Number(progress.indexed) || 0} · 跳过 ${Number(progress.skipped) || 0} · 错误 ${Number(progress.errors) || 0}</small></div><div class="gap-row-actions">${job.status === "running" ? `<button class="btn small" data-gap-action="legacy-pause" data-job-id="${escapeHtml(job.id)}">暂停</button>` : ""}${job.status === "paused" ? `<button class="btn small primary" data-gap-action="legacy-resume" data-job-id="${escapeHtml(job.id)}">恢复</button>` : ""}${["pending","running","paused"].includes(job.status) ? `<button class="btn small" data-gap-action="legacy-execute" data-job-id="${escapeHtml(job.id)}">运行一批</button><button class="btn small danger-soft" data-gap-action="legacy-cancel" data-job-id="${escapeHtml(job.id)}">取消</button>` : ""}<button class="btn small" data-gap-action="legacy-status" data-job-id="${escapeHtml(job.id)}">刷新</button></div>`;
  }

  function addHeaderButton(id, label, action, className = "btn") {
    if (document.getElementById(id)) return null;
    const actions = document.querySelector(".page-header .header-actions");
    if (!actions) return null;
    const button = document.createElement("button");
    button.id = id;
    button.type = "button";
    button.className = className;
    button.dataset.gapAction = action;
    button.textContent = label;
    actions.prepend(button);
    return button;
  }

  function ensureModal(id, title, body, size = "") {
    let modal = document.getElementById(id);
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = id;
    modal.className = "atelier-modal-backdrop gap-fill-modal-backdrop";
    modal.hidden = true;
    modal.innerHTML = `<section class="atelier-modal gap-fill-modal ${size}" role="dialog" aria-modal="true"><div class="gap-modal-head"><div><span class="developer-eyebrow">ATELIER</span><h2>${escapeHtml(title)}</h2></div><button class="btn small" type="button" data-gap-action="modal-close" data-modal-id="${escapeHtml(id)}">关闭</button></div><div class="gap-modal-body">${body}</div></section>`;
    document.body.appendChild(modal);
    modal.addEventListener("click", (event) => { if (event.target === modal) closeModal(id); });
    return modal;
  }

  function showModal(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.hidden = false;
    requestAnimationFrame(() => modal.classList.add("show"));
  }

  function closeModal(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.classList.remove("show");
    window.setTimeout(() => { modal.hidden = true; }, 140);
  }

  function enhanceMaterials() {
    addHeaderButton("gap-material-templates-button", "素材模板", "templates-open");
  }

  async function openTemplates() {
    const modal = ensureModal("gap-template-modal", "素材模板", `<div id="gap-template-content">${loading("正在读取镜头模板、场景包和转场包…")}</div>`, "wide");
    showModal(modal.id);
    await refreshTemplates();
  }

  function templateCard(template) {
    const labels = { shot_template: "镜头模板", scene_pack: "场景包", transition_pack: "转场包" };
    const pages = parseJson(template.pages_json, []);
    const tags = parseJson(template.tags_json, []);
    return `<article class="gap-template-card"><span>${escapeHtml((labels[template.template_type] || template.template_type).slice(0,2))}</span><div><strong>${escapeHtml(template.name)}</strong><small>${escapeHtml(labels[template.template_type] || template.template_type)} · ${pages.length} 页 · ${tags.map((tag) => `#${tag}`).join(" ") || "无标签"}</small><p>${escapeHtml(template.description || "没有说明")}</p></div><button class="btn small" data-gap-action="template-edit" data-template-id="${escapeHtml(template.id)}">编辑</button><button class="btn small danger-soft" data-gap-action="template-delete" data-template-id="${escapeHtml(template.id)}">删除</button></article>`;
  }

  async function refreshTemplates() {
    const content = document.getElementById("gap-template-content");
    if (!content) return;
    const payload = await request("/api/material-templates?include_archived=true&limit=100&offset=0");
    const templates = payload.templates?.items || [];
    content.innerHTML = `<form id="gap-template-form" class="gap-template-form"><input type="hidden" name="template_id" /><label class="gap-field"><span>名称</span><input name="name" required /></label><label class="gap-field"><span>类型</span><select name="template_type"><option value="shot_template">镜头模板</option><option value="scene_pack">场景包</option><option value="transition_pack">转场包</option></select></label><label class="gap-field span-2"><span>说明</span><input name="description" /></label><label class="gap-field span-2"><span>标签（逗号分隔）</span><input name="tags" /></label><label class="gap-field span-2"><span>页面 JSON 数组</span><textarea name="pages" rows="4">[]</textarea></label><div class="gap-row-actions span-2"><button class="btn primary" type="submit">保存模板</button><button class="btn" type="button" data-gap-action="template-reset">清空表单</button></div></form><div class="gap-template-list">${templates.map(templateCard).join("") || '<p class="gap-muted">还没有素材模板。</p>'}</div>`;
  }

  function enhanceMaterialDetail() {
    document.querySelectorAll(".material-page-card[data-material-page-id]").forEach((card) => {
      if (card.querySelector("[data-gap-reference-mode]")) return;
      const actions = card.querySelector(".material-page-card-actions");
      if (!actions) return;
      const select = document.createElement("select");
      select.className = "btn small gap-reference-mode";
      select.dataset.gapReferenceMode = "1";
      select.dataset.pageId = card.dataset.materialPageId;
      select.innerHTML = '<option value="independent">独立复制</option><option value="link">链接引用</option>';
      const mode = card.dataset.referenceMode || card.getAttribute("data-reference-mode") || "independent";
      select.value = mode;
      actions.prepend(select);
    });
  }

  function enhanceCharacters() {
    document.querySelectorAll(".character-expanded[data-character-id]").forEach((panel) => {
      const head = panel.querySelector(".character-expanded-head");
      if (!head || head.querySelector("[data-gap-action='character-completeness']")) return;
      const actions = document.createElement("div");
      actions.className = "gap-row-actions";
      actions.innerHTML = `<button class="btn small" type="button" data-gap-action="character-completeness" data-character-id="${escapeHtml(panel.dataset.characterId)}">完整性检查</button><button class="btn small" type="button" data-gap-action="character-batch-paste" data-character-id="${escapeHtml(panel.dataset.characterId)}">批量粘贴</button>`;
      head.appendChild(actions);
    });
  }

  async function showCompleteness(characterId) {
    const modal = ensureModal("gap-completeness-modal", "人物规格完整性", `<div id="gap-completeness-content">${loading("正在检查变体 × 规格矩阵…")}</div>`, "wide");
    showModal(modal.id);
    const payload = await request(`/api/characters/${encodeURIComponent(characterId)}/spec-completeness`);
    const result = payload.completeness || {};
    const matrix = result.matrix || {};
    const rows = Object.values(matrix);
    document.getElementById("gap-completeness-content").innerHTML = `<div class="gap-system-metrics"><div><span>变体</span><strong>${Number(result.variant_count) || rows.length}</strong></div><div><span>规格</span><strong>${Number(result.spec_count) || 0}</strong></div><div><span>完整单元格</span><strong>${Number(result.complete_cells) || 0}</strong></div><div><span>缺失单元格</span><strong>${Number(result.incomplete_cells) || 0}</strong></div></div><div class="gap-completeness-list">${rows.map((variant) => `<section><strong>${escapeHtml(variant.name)}</strong>${Object.values(variant.specs || {}).map((spec) => `<div class="${spec.missing?.length ? "missing" : "complete"}"><span>${escapeHtml(spec.name)}</span><small>${spec.missing?.length ? `缺少：${spec.missing.join("、")}` : "完整"}</small></div>`).join("")}</section>`).join("") || '<p class="gap-muted">没有可检查的规格。</p>'}</div>`;
  }

  function showBatchPaste(characterId) {
    const modal = ensureModal("gap-batch-paste-modal", "批量粘贴人物规格", `<form id="gap-batch-paste-form" class="gap-form-stack"><input type="hidden" name="character_id" /><label class="gap-field"><span>目标变体</span><select name="variant_id"></select></label><label class="gap-field"><span>JSON 数组或 TSV</span><textarea name="values" rows="14" placeholder='[{"spec_type":"full_body","prompt":"...","lora_name":"..."}]'></textarea><small>TSV 首行字段可用：spec_type、custom_label、prompt、lora_name、lora_weight、model_override、notes。</small></label><button class="btn primary" type="submit">解析并写入</button></form>`, "wide");
    const form = modal.querySelector("form");
    form.elements.character_id.value = characterId;
    form.elements.variant_id.innerHTML = '<option value="">正在读取变体…</option>';
    showModal(modal.id);
    request(`/api/characters/${encodeURIComponent(characterId)}/variants`).then((payload) => {
      form.elements.variant_id.innerHTML = (payload.items || []).map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)}</option>`).join("");
    }).catch((error) => toast(error.message));
  }

  function parseBatchPaste(text) {
    const trimmed = text.trim();
    if (!trimmed) return [];
    if (trimmed.startsWith("[")) {
      const parsed = JSON.parse(trimmed);
      if (!Array.isArray(parsed)) throw new Error("JSON 顶层必须是数组");
      return parsed;
    }
    const lines = trimmed.split(/\r?\n/).filter(Boolean);
    const headers = lines.shift().split("\t").map((item) => item.trim());
    return lines.map((line) => Object.fromEntries(headers.map((header, index) => [header, line.split("\t")[index] || ""])));
  }

  function enhanceCharacterDatabase() {
    const table = document.querySelector(".character-database-table");
    if (!table) return;
    if (!table.dataset.gapEnhanced) {
      table.dataset.gapEnhanced = "1";
      const header = table.querySelector("thead tr");
      if (header) header.insertAdjacentHTML("beforeend", "<th>人物库</th>");
    }
    table.querySelectorAll("tbody tr:not([data-gap-enhanced])").forEach((row) => {
      row.dataset.gapEnhanced = "1";
      const name = row.querySelector(".character-database-name")?.textContent?.trim() || "";
      row.insertAdjacentHTML("beforeend", `<td><button class="btn small" data-gap-action="character-link" data-record-id="${escapeHtml(name)}" data-record-name="${escapeHtml(name)}">关联</button></td>`);
    });
  }

  function enhanceStoryCanvas() {
    if (!projectId()) return;
    addHeaderButton("gap-story-tools-button", "转场与自动保存", "story-tools-open");
  }

  function collectShotPages(value, output = [], seen = new Set(), parentKey = "") {
    if (!value || typeof value !== "object") return output;
    if (seen.has(value)) return output;
    seen.add(value);
    if (!Array.isArray(value)) {
      const id = value.id || value.page_id;
      const looksLikePage = value.page_number !== undefined || value.entity_type === "shot_page" || value.type === "shot_page" || value.node_type === "shot_page" || (parentKey === "pages" && value.small_scene_id !== undefined);
      if (id && looksLikePage && !output.some((item) => String(item.id) === String(id))) output.push({ id, name: value.title || value.name || `页面 ${shortId(id)}` });
    }
    if (Array.isArray(value)) {
      value.forEach((child) => { if (child && typeof child === "object") collectShotPages(child, output, seen, parentKey); });
    } else {
      Object.entries(value).forEach(([key, child]) => { if (child && typeof child === "object") collectShotPages(child, output, seen, key); });
    }
    return output;
  }

  async function openStoryTools() {
    const modal = ensureModal("gap-story-tools-modal", "转场与自动保存", `<div id="gap-story-tools-content">${loading("正在读取转场结构和自动保存历史…")}</div>`, "wide");
    showModal(modal.id);
    await refreshStoryTools();
  }

  async function refreshStoryTools() {
    const content = document.getElementById("gap-story-tools-content");
    if (!content) return;
    const id = projectId();
    const [blocksPayload, autosavePayload, treePayload] = await Promise.all([
      request(`/api/projects/${encodeURIComponent(id)}/transition-blocks`),
      request(`/api/projects/${encodeURIComponent(id)}/autosave?limit=50&offset=0`),
      request(`/api/projects/${encodeURIComponent(id)}/story-tree`),
    ]);
    const blocks = blocksPayload.blocks?.items || blocksPayload.blocks || [];
    const autosaves = autosavePayload.autosave?.items || [];
    const pages = collectShotPages(treePayload);
    const options = '<option value="">未指定</option>' + pages.map((page) => `<option value="${escapeHtml(page.id)}">${escapeHtml(page.name)}</option>`).join("");
    content.innerHTML = `<div class="gap-story-tools-grid"><section><div class="gap-section-title"><strong>转场结构块</strong><span>${blocks.length} 个</span></div><form id="gap-transition-form" class="gap-form-stack"><div class="gap-two-fields"><label class="gap-field"><span>来源页</span><select name="source_page_id">${options}</select></label><label class="gap-field"><span>目标页</span><select name="target_page_id">${options}</select></label></div><div class="gap-two-fields"><label class="gap-field"><span>类型</span><select name="transition_type"><option value="cut">直接切换</option><option value="fade">淡入淡出</option><option value="dissolve">叠化</option><option value="wipe">划像</option><option value="custom">自定义</option></select></label><label class="gap-field"><span>持续帧</span><input name="duration_frames" type="number" min="0" value="0" /></label></div><button class="btn primary" type="submit">添加转场</button></form><div class="gap-transition-list">${blocks.map((block) => `<article><div><strong>${escapeHtml(block.transition_type)}</strong><small>${shortId(block.source_page_id)} → ${shortId(block.target_page_id)} · ${Number(block.duration_frames) || 0} 帧</small></div><button class="btn small danger-soft" data-gap-action="transition-delete" data-block-id="${escapeHtml(block.id)}">删除</button></article>`).join("") || '<p class="gap-muted">还没有转场结构块。</p>'}</div></section><section><div class="gap-section-title"><strong>自动保存历史</strong><button class="btn small" data-gap-action="autosave-now">保存当前画布恢复点</button></div><div class="gap-autosave-list">${autosaves.map((item) => `<article><span>${escapeHtml(item.operation_type || "update")}</span><div><strong>${escapeHtml(item.entity_type)} · ${shortId(item.entity_id)}</strong><small>${formatDate(item.created_at)}</small></div></article>`).join("") || '<p class="gap-muted">还没有自动保存记录。</p>'}</div></section></div>`;
  }

  function enhanceWorkflowCanvas() {
    const workflowId = currentParams().get("workflow");
    if (!workflowId) return;
    const button = addHeaderButton("gap-workflow-validation-button", "验证记录", "workflow-validation-open");
    if (button) button.dataset.workflowId = workflowId;
  }

  async function openWorkflowValidation(workflowId) {
    const modal = ensureModal("gap-workflow-validation-modal", "工作流验证记录", `<div id="gap-workflow-validation-content">${loading("正在读取验证历史…")}</div>`, "wide");
    modal.dataset.workflowId = workflowId;
    showModal(modal.id);
    await refreshWorkflowValidation(workflowId);
  }

  async function refreshWorkflowValidation(workflowId) {
    const content = document.getElementById("gap-workflow-validation-content");
    if (!content) return;
    const payload = await request(`/api/workflow-validation-runs?workflow_id=${encodeURIComponent(workflowId)}&limit=50&offset=0`);
    const runs = payload.runs?.items || [];
    content.innerHTML = `<div class="gap-section-title"><div><strong>验证历史</strong><span>保存每次预检的错误、警告、节点和连线统计。</span></div><button class="btn primary" data-gap-action="workflow-validation-run" data-workflow-id="${escapeHtml(workflowId)}">运行并记录预检</button></div><div class="gap-validation-list">${runs.map((run) => `<article><span>${statusPill(run.status)}</span><div><strong>${escapeHtml(run.run_type)} · ${shortId(run.id)}</strong><small>${Number(run.node_count) || 0} 节点 · ${Number(run.connection_count) || 0} 连线 · ${Number(run.duration_ms) || 0} ms</small><small>${formatDate(run.created_at)}</small></div><button class="btn small" data-gap-action="workflow-validation-detail" data-run-id="${escapeHtml(run.id)}">详情</button></article>`).join("") || '<p class="gap-muted">还没有验证记录。</p>'}</div><pre class="gap-result-box" id="gap-validation-result">选择一条记录查看详情。</pre>`;
  }

  async function runWorkflowValidation(workflowId) {
    const start = performance.now();
    const created = await request("/api/workflow-validation-runs", { method: "POST", body: JSON.stringify({ workflow_id: workflowId, run_type: "precheck" }) });
    const run = created.run;
    try {
      const [precheck, draft] = await Promise.all([
        request(`/api/workflows/${encodeURIComponent(workflowId)}/precheck`, { method: "POST", body: "{}" }),
        request(`/api/workflows/${encodeURIComponent(workflowId)}/draft`),
      ]);
      const result = precheck.result || precheck;
      const errors = result.errors || result.blocking || [];
      const warnings = result.warnings || [];
      const graph = draft.graph || draft.draft?.graph || {};
      await request(`/api/workflow-validation-runs/${encodeURIComponent(run.id)}`, { method: "PATCH", body: JSON.stringify({ status: errors.length ? "failed" : "passed", errors, warnings, node_count: (graph.nodes || []).length, connection_count: (graph.links || []).length, duration_ms: Math.round(performance.now() - start), comfyui_response: null }) });
      toast(errors.length ? "预检完成，存在阻塞错误" : "工作流预检通过");
    } catch (error) {
      await request(`/api/workflow-validation-runs/${encodeURIComponent(run.id)}`, { method: "PATCH", body: JSON.stringify({ status: "failed", errors: [{ message: error.message }], duration_ms: Math.round(performance.now() - start) }) });
      toast(`预检失败：${error.message}`);
      await refreshWorkflowValidation(workflowId);
      return;
    }
    await refreshWorkflowValidation(workflowId);
  }

  function enhanceBatchPages(pageKey) {
    const id = projectId();
    if (!id) return;
    const blockers = addHeaderButton("gap-blockers-button", "阻塞项", "blockers-open");
    if (blockers) blockers.dataset.projectId = id;
    if (pageKey === "tasks") {
      const rename = addHeaderButton("gap-batch-rename-button", "批次改名", "batch-rename");
      if (rename) rename.dataset.batchId = currentParams().get("batch") || "";
    }
  }

  async function openBlockers() {
    const modal = ensureModal("gap-blockers-modal", "项目阻塞项", `<div id="gap-blockers-content">${loading("正在读取阻塞项…")}</div>`, "wide");
    showModal(modal.id);
    await refreshBlockers();
  }

  async function refreshBlockers() {
    const content = document.getElementById("gap-blockers-content");
    if (!content) return;
    const params = new URLSearchParams({ project_id: projectId(), limit: "100", offset: "0" });
    const batchId = currentParams().get("batch");
    if (batchId) params.set("batch_id", batchId);
    const payload = await request(`/api/blocking-issues?${params.toString()}`);
    const issues = payload.issues?.items || [];
    content.innerHTML = `<form id="gap-blocker-form" class="gap-blocker-form"><select name="severity"><option value="error">错误</option><option value="warning">警告</option><option value="info">信息</option></select><input name="category" value="manual" placeholder="分类" /><input name="message" placeholder="阻塞说明" required /><button class="btn primary" type="submit">添加</button></form><div class="gap-blocker-list">${issues.map((issue) => `<article class="${escapeHtml(issue.severity)}"><span>${escapeHtml(issue.severity)}</span><div><strong>${escapeHtml(issue.message)}</strong><small>${escapeHtml(issue.category)} · ${statusPill(issue.status)} · ${formatDate(issue.created_at)}</small></div>${issue.status === "open" ? `<button class="btn small" data-gap-action="blocker-status" data-issue-id="${escapeHtml(issue.id)}" data-status="resolved">解决</button><button class="btn small" data-gap-action="blocker-status" data-issue-id="${escapeHtml(issue.id)}" data-status="ignored">忽略</button>` : `<button class="btn small" data-gap-action="blocker-status" data-issue-id="${escapeHtml(issue.id)}" data-status="open">重新打开</button>`}</article>`).join("") || '<p class="gap-muted">当前没有阻塞项。</p>'}</div>`;
  }

  async function handleClick(event) {
    const button = event.target.closest("[data-gap-action]");
    if (!button || button.disabled) return;
    const action = button.dataset.gapAction;
    try {
      if (action === "modal-close") return closeModal(button.dataset.modalId);
      if (action === "review-refresh") return renderReview(state.project);
      if (action === "open-batch-for-project") return navigate("batch", { project: projectId() });
      if (action === "review-page") {
        state.review.selectedPage = button.dataset.pageId;
        state.review.selectedInstance = "";
        return renderReview(state.project);
      }
      if (action === "review-select") {
        state.review.selectedInstance = button.dataset.instanceId;
        return renderReview(state.project);
      }
      if (action === "review-adopt") return mutateReview(button.dataset.instanceId, "adopt");
      if (action === "review-unadopt") return mutateReview(button.dataset.instanceId, "unadopt");
      if (action === "review-reject") return mutateReview(button.dataset.instanceId, "reject");
      if (action === "review-representative") return mutateReview(button.dataset.instanceId, "representative");
      if (action === "review-order-up") return reorderAdopted(button.dataset.instanceId, -1);
      if (action === "review-order-down") return reorderAdopted(button.dataset.instanceId, 1);
      if (action === "review-save") {
        await request(`/api/image-instances/${encodeURIComponent(button.dataset.instanceId)}/review`, { method: "PATCH", body: JSON.stringify({ star_rating: Number(document.getElementById("gap-review-rating")?.value) || 0, color_label: document.getElementById("gap-review-color")?.value || "none", review_note: document.getElementById("gap-review-note")?.value || "" }) });
        toast("审片信息已保存");
        return renderReview(state.project);
      }
      if (action === "review-create-tag") {
        const name = window.prompt("标签名称", "");
        if (name === null || !name.trim()) return;
        await request("/api/image-tags", { method: "POST", body: JSON.stringify({ name: name.trim(), color: "blue" }) });
        return renderReview(state.project);
      }
      if (action === "review-toggle-tag") {
        await request(`/api/image-instances/${encodeURIComponent(button.dataset.instanceId)}/tags/${encodeURIComponent(button.dataset.tagId)}`, { method: button.dataset.active === "1" ? "DELETE" : "POST", body: button.dataset.active === "1" ? undefined : "{}" });
        return renderReview(state.project);
      }
      if (action === "review-tracking") {
        const payload = await request(`/api/image-instances/${encodeURIComponent(button.dataset.instanceId)}/tracking`);
        const modal = ensureModal("gap-json-modal", "生成追踪", `<pre class="gap-json-view">${escapeHtml(JSON.stringify(payload.tracking || payload, null, 2))}</pre>`, "wide");
        modal.querySelector(".gap-modal-body").innerHTML = `<pre class="gap-json-view">${escapeHtml(JSON.stringify(payload.tracking || payload, null, 2))}</pre>`;
        return showModal(modal.id);
      }
      if (action === "review-copy-params") {
        const payload = await request(`/api/image-instances/${encodeURIComponent(button.dataset.instanceId)}/copy-params`, { method: "POST", body: "{}" });
        await navigator.clipboard?.writeText(JSON.stringify(payload.params || {}, null, 2));
        toast("参数 JSON 已复制");
        return;
      }
      if (action === "open-image-detail") return navigate("image-detail", { instance: button.dataset.instanceId || null, file: button.dataset.fileId || null, project: projectId() || null });
      if (action === "open-gallery") return navigate("library", { file: null, instance: null });
      if (action === "assembly-refresh") return renderAssembly(state.project);
      if (action === "assembly-create-version") return createFinalVersion();
      if (action === "assembly-select-version") { state.assembly.selectedVersion = button.dataset.versionId; return renderAssembly(state.project); }
      if (action === "assembly-generate-default") { await request(`/api/final-versions/${encodeURIComponent(state.assembly.selectedVersion)}/generate-default-sequence`, { method: "POST", body: "{}" }); return renderAssembly(state.project); }
      if (action === "assembly-rebuild") {
        if (!window.confirm("这会清空当前手动排序，并按采用结果重新生成。继续吗？")) return;
        await request(`/api/final-versions/${encodeURIComponent(state.assembly.selectedVersion)}/rebuild-from-adoptions`, { method: "POST", body: "{}" });
        return renderAssembly(state.project);
      }
      if (action === "assembly-rename-version") {
        const current = state.assembly.versions.find((item) => item.id === state.assembly.selectedVersion);
        const name = window.prompt("版本名称", current?.name || "");
        if (name === null || !name.trim()) return;
        await request(`/api/final-versions/${encodeURIComponent(state.assembly.selectedVersion)}`, { method: "PATCH", body: JSON.stringify({ name: name.trim() }) });
        return renderAssembly(state.project);
      }
      if (action === "assembly-delete-version") {
        if (!window.confirm("删除这个最终版本？原图片不会被删除。")) return;
        await request(`/api/final-versions/${encodeURIComponent(state.assembly.selectedVersion)}`, { method: "DELETE" });
        state.assembly.selectedVersion = "";
        return renderAssembly(state.project);
      }
      if (action === "assembly-move") return reorderFinalItem(button.dataset.itemId, Number(button.dataset.delta));
      if (action === "assembly-remove") { await request(`/api/final-version-items/${encodeURIComponent(button.dataset.itemId)}`, { method: "DELETE" }); return renderAssembly(state.project); }
      if (action === "gallery-open") return navigate("image-detail", { file: button.dataset.fileId, instance: null });
      if (action === "gallery-next") {
        if (!state.gallery.nextCursor) return;
        state.gallery.history.push(state.gallery.cursor);
        state.gallery.cursor = state.gallery.nextCursor;
        return loadGallery();
      }
      if (action === "gallery-previous") return loadGallery({ previous: true });
      if (action === "gallery-reindex" || action === "gallery-reindex-force") {
        if (action.endsWith("force") && !window.confirm("全量重建会清空现有图库索引后重新生成。继续吗？")) return;
        const payload = await request(`/api/gallery/reindex?force=${action.endsWith("force") ? "true" : "false"}`, { method: "POST", body: "{}" });
        toast(`索引完成：${Number(payload.stats?.indexed) || 0} 张`);
        return loadGallery({ reset: true });
      }
      if (action === "gallery-worker") { const payload = await request("/api/thumbnails/rebuild-all?limit=100", { method: "POST", body: "{}" }); const result = payload.rebuild_result || {}; toast(`缩略图已生成：${Number(result.completed) || 0} 张，失败 ${Number(result.failed) || 0} 张`); return loadGallery({ reset: true }); }
      if (action === "detail-phash") { const payload = await request(`/api/files/${encodeURIComponent(button.dataset.fileId)}/phash`, { method: "POST", body: "{}" }); toast(`pHash：${payload.perceptual_hash}`); return renderImageDetail(); }
      if (action === "detail-reindex") { await request(`/api/gallery/index/${encodeURIComponent(button.dataset.fileId)}`, { method: "POST", body: "{}" }); toast("索引已刷新"); return renderImageDetail(); }
      if (action === "detail-duplicates" || action === "detail-similar") {
        const path = action === "detail-duplicates" ? "duplicates" : "similar";
        const payload = await request(`/api/gallery/${encodeURIComponent(button.dataset.fileId)}/${path}`);
        const target = document.getElementById("gap-image-related");
        if (target) target.innerHTML = `<div class="gap-related-grid">${(payload.items || []).map(galleryCard).join("") || '<p class="gap-muted">没有找到相关图片。</p>'}</div>`;
        return;
      }
      if (action === "export-refresh") return renderExport(state.project);
      if (action === "export-create-preset") return createExportPreset();
      if (action === "export-delete-preset") { if (!window.confirm("删除这个导出预设？")) return; await request(`/api/export-presets/${encodeURIComponent(button.dataset.presetId)}`, { method: "DELETE" }); return renderExport(state.project); }
      if (action === "export-run") { button.disabled = true; button.textContent = "执行中…"; await request(`/api/export-jobs/${encodeURIComponent(button.dataset.jobId)}/execute?conflict_strategy=suffix`, { method: "POST", body: "{}" }); return renderExport(state.project); }
      if (action === "export-cancel") { await request(`/api/export-jobs/${encodeURIComponent(button.dataset.jobId)}/cancel`, { method: "POST", body: "{}" }); return renderExport(state.project); }
      if (action === "export-worker") { await request("/api/export-jobs/worker/run?max_jobs=1&conflict_strategy=suffix", { method: "POST", body: "{}" }); return renderExport(state.project); }
      if (action === "open-assembly") return navigate("assembly", { project: projectId() });
      if (action === "settings-retry" || action === "maintenance-refresh") return refreshSettings();
      if (action === "directory-check") {
        const input = document.querySelector(`#gap-directory-form [name="${CSS.escape(button.dataset.field)}"]`);
        const result = document.querySelector(`[data-directory-result="${CSS.escape(button.dataset.field)}"]`);
        const payload = await request("/api/settings/directory/check", { method: "POST", body: JSON.stringify({ path: input?.value || "" }) });
        if (result) result.textContent = JSON.stringify(payload.check);
        return;
      }
      if (action === "maintenance-integrity") return maintenanceResult(await request("/api/maintenance/integrity-check"));
      if (action === "maintenance-orphans") return maintenanceResult(await request("/api/maintenance/orphan-check"));
      if (action === "maintenance-optimize") return runMaintenance("/api/maintenance/optimize");
      if (action === "maintenance-clear-cache") { if (!window.confirm("清理缓存和临时缓存文件？原图不会删除。")) return; return runMaintenance("/api/maintenance/clear-cache"); }
      if (action === "maintenance-rebuild-fts") return runMaintenance("/api/maintenance/rebuild-fts");
      if (action === "maintenance-recompute-phash") return runMaintenance("/api/maintenance/recompute-phash?limit=100");
      if (action === "maintenance-clean-temp") { if (!window.confirm("清理 7 天前的临时文件？")) return; return runMaintenance("/api/maintenance/clean-temp?retention_days=7"); }
      if (action === "maintenance-clean-trash") { if (!window.confirm("物理清理 30 天前的回收站内容？此操作不可撤销。")) return; return runMaintenance("/api/maintenance/clean-trash?retention_days=30"); }
      if (action === "maintenance-backup") { const path = window.prompt("备份文件路径", "backups/atelier-backup.sqlite3"); if (!path) return; return runMaintenance("/api/maintenance/backup", { body: { target_path: path } }); }
      if (action === "maintenance-restore") { const path = window.prompt("要恢复的 SQLite 备份路径", ""); if (!path || !window.confirm("恢复数据库会替换当前数据库。系统会先自动备份，是否继续？")) return; return runMaintenance("/api/maintenance/restore", { body: { backup_path: path, pre_restore_backup: true } }); }
      if (action === "recycle-restore") { await request(`/api/recycle-bin/${encodeURIComponent(button.dataset.entryId)}/restore`, { method: "POST", body: "{}" }); toast("回收站条目已恢复"); return refreshSettings(); }
      if (action === "recycle-purge") { if (!window.confirm("永久清除这条回收站记录？")) return; await request("/api/recycle-bin/purge", { method: "POST", body: JSON.stringify({ entry_id: button.dataset.entryId }) }); return refreshSettings(); }
      if (action === "recycle-purge-expired") { if (!window.confirm("永久清除 30 天前的回收站记录？")) return; await request("/api/recycle-bin/purge", { method: "POST", body: JSON.stringify({ older_than_days: 30 }) }); return refreshSettings(); }
      if (action === "package-export-project") { const id = document.getElementById("gap-package-project")?.value; if (!id) throw new Error("请选择项目"); const payload = await request(`/api/projects/${encodeURIComponent(id)}/export-package`, { method: "POST", body: "{}" }); document.getElementById("gap-project-manifest").value = JSON.stringify(payload.manifest, null, 2); return importResult(payload); }
      if (action === "package-project-dry-run" || action === "package-project-import") { const manifest = JSON.parse(document.getElementById("gap-project-manifest")?.value || "{}"); const payload = await request("/api/projects/import-package", { method: "POST", body: JSON.stringify({ manifest, dry_run: action.endsWith("dry-run") }) }); return importResult(payload); }
      if (action === "package-export-materials") { const ids = (document.getElementById("gap-material-ids")?.value || "").split(/\r?\n|,/).map((value) => value.trim()).filter(Boolean); const payload = await request("/api/materials/export-package", { method: "POST", body: JSON.stringify({ material_ids: ids }) }); document.getElementById("gap-material-manifest").value = JSON.stringify(payload.manifest, null, 2); return importResult(payload); }
      if (action === "package-materials-dry-run" || action === "package-materials-import") { const manifest = JSON.parse(document.getElementById("gap-material-manifest")?.value || "{}"); const payload = await request("/api/materials/import-package", { method: "POST", body: JSON.stringify({ manifest, dry_run: action.endsWith("dry-run") }) }); return importResult(payload); }
      if (action === "legacy-scan") { const directory = document.getElementById("gap-legacy-directory")?.value || ""; return importResult(await request("/api/import/scan-legacy", { method: "POST", body: JSON.stringify({ directory, dry_run: true }) })); }
      if (action === "legacy-create-job") { const payload = await request("/api/import/legacy/index", { method: "POST", body: JSON.stringify({ directory: document.getElementById("gap-legacy-directory")?.value || "", link_mode: document.getElementById("gap-legacy-link-mode")?.value || "hardlink", force: false, max_files: 200 }) }); renderLegacyJob(payload.job); return importResult(payload); }
      if (["legacy-status","legacy-pause","legacy-resume","legacy-cancel","legacy-execute"].includes(action)) { const suffix = ({"legacy-status":"","legacy-pause":"/pause","legacy-resume":"/resume","legacy-cancel":"/cancel","legacy-execute":"/execute"})[action]; const payload = await request(`/api/import/legacy/index/${encodeURIComponent(button.dataset.jobId)}${suffix}`, { method: action === "legacy-status" ? "GET" : "POST", body: action === "legacy-execute" ? JSON.stringify({ directory: document.getElementById("gap-legacy-directory")?.value || ".", link_mode: "hardlink", force: false, max_files: 200 }) : (action === "legacy-status" ? undefined : "{}") }); renderLegacyJob(payload.job); return importResult(payload); }
      if (action === "templates-open") return openTemplates();
      if (action === "template-reset") { document.getElementById("gap-template-form")?.reset(); document.querySelector('#gap-template-form [name="template_id"]').value = ""; return; }
      if (action === "template-delete") { if (!window.confirm("删除这个素材模板？")) return; await request(`/api/material-templates/${encodeURIComponent(button.dataset.templateId)}`, { method: "DELETE" }); return refreshTemplates(); }
      if (action === "template-edit") { const payload = await request(`/api/material-templates/${encodeURIComponent(button.dataset.templateId)}`); const template = payload.template || {}; const form = document.getElementById("gap-template-form"); form.elements.template_id.value = template.id; form.elements.name.value = template.name || ""; form.elements.template_type.value = template.template_type || "shot_template"; form.elements.description.value = template.description || ""; form.elements.tags.value = (parseJson(template.tags_json, []) || []).join(", "); form.elements.pages.value = JSON.stringify(parseJson(template.pages_json, []), null, 2); return; }
      if (action === "spec-preview-upload") {
        const input = document.createElement("input");
        input.type = "file";
        input.accept = "image/png,image/jpeg,image/webp";
        input.addEventListener("change", async () => {
          if (!input.files?.[0]) return;
          const formData = new FormData();
          formData.append("file", input.files[0]);
          try {
            await request(`/api/character-spec-values/${encodeURIComponent(button.dataset.specValueId)}/preview`, { method: "POST", body: formData });
            toast("规格预览图已上传");
          } catch (error) { toast(error.message); }
        }, { once: true });
        input.click();
        return;
      }
      if (action === "character-completeness") return showCompleteness(button.dataset.characterId);
      if (action === "character-batch-paste") return showBatchPaste(button.dataset.characterId);
      if (action === "character-link") {
        const name = button.dataset.recordName;
        const characterName = window.prompt("人物库名称", name);
        if (characterName === null || !characterName.trim()) return;
        const payload = await request("/api/character-database/link", { method: "POST", body: JSON.stringify({ record_id: button.dataset.recordId, character_name: characterName.trim(), project_id: projectId() || null }) });
        toast(`已关联人物：${payload.link?.character_name || characterName}`);
        button.textContent = "已关联"; button.disabled = true; return;
      }
      if (action === "story-tools-open") return openStoryTools();
      if (action === "transition-delete") { await request(`/api/transition-blocks/${encodeURIComponent(button.dataset.blockId)}`, { method: "DELETE" }); return refreshStoryTools(); }
      if (action === "autosave-now") { await request("/api/autosave/snapshots", { method: "POST", body: JSON.stringify({ project_id: projectId(), entity_type: "project", entity_id: projectId(), operation_type: "manual_checkpoint", payload: { url: window.location.search, saved_from: "frontend", surface: "story_canvas" } }) }); toast("画布恢复点已保存"); return refreshStoryTools(); }
      if (action === "workflow-validation-open") return openWorkflowValidation(button.dataset.workflowId);
      if (action === "workflow-validation-run") return runWorkflowValidation(button.dataset.workflowId);
      if (action === "workflow-validation-detail") { const payload = await request(`/api/workflow-validation-runs/${encodeURIComponent(button.dataset.runId)}`); document.getElementById("gap-validation-result").textContent = JSON.stringify(payload.run, null, 2); return; }
      if (action === "blockers-open") return openBlockers();
      if (action === "blocker-status") { await request(`/api/blocking-issues/${encodeURIComponent(button.dataset.issueId)}`, { method: "PATCH", body: JSON.stringify({ status: button.dataset.status }) }); return refreshBlockers(); }
      if (action === "batch-rename") { let id = button.dataset.batchId || document.getElementById("task-batch-filter")?.value || ""; if (!id) throw new Error("请先选择一个批次"); const name = window.prompt("新的批次名称", ""); if (!name?.trim()) return; await request(`/api/batches/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify({ name: name.trim() }) }); toast("批次已改名"); window.location.reload(); }
    } catch (error) {
      toast(error.message || "操作失败");
    }
  }

  async function handleSubmit(event) {
    const form = event.target;
    try {
      if (form.id === "gap-gallery-filter") {
        event.preventDefault();
        return loadGallery({ reset: true });
      }
      if (form.id === "gap-export-job-form") {
        event.preventDefault();
        const payload = await request(`/api/final-versions/${encodeURIComponent(form.elements.version_id.value)}/export-jobs`, { method: "POST", body: JSON.stringify({ output_dir: form.elements.output_dir.value.trim(), preset_id: form.elements.preset_id.value || null }) });
        toast(`导出任务 ${shortId(payload.job?.id)} 已创建`);
        return renderExport(state.project);
      }
      if (form.id === "gap-directory-form") {
        event.preventDefault();
        const payload = Object.fromEntries(["data_dir","images_dir","cache_dir","tmp_dir"].map((key) => [key, form.elements[key].value.trim()]));
        await request("/api/settings/directory", { method: "PUT", body: JSON.stringify(payload) });
        toast("目录配置已保存");
        return refreshSettings();
      }
      if (form.id === "gap-template-form") {
        event.preventDefault();
        const id = form.elements.template_id.value;
        const pages = JSON.parse(form.elements.pages.value || "[]");
        const tags = form.elements.tags.value.split(",").map((item) => item.trim()).filter(Boolean);
        const payload = { name: form.elements.name.value.trim(), description: form.elements.description.value.trim(), pages, tags };
        if (id) await request(`/api/material-templates/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(payload) });
        else await request("/api/material-templates", { method: "POST", body: JSON.stringify({ ...payload, template_type: form.elements.template_type.value }) });
        toast("素材模板已保存");
        return refreshTemplates();
      }
      if (form.id === "gap-batch-paste-form") {
        event.preventDefault();
        const values = parseBatchPaste(form.elements.values.value);
        const payload = await request("/api/character-spec-values/batch-paste", { method: "POST", body: JSON.stringify({ character_id: form.elements.character_id.value, variant_id: form.elements.variant_id.value, spec_values: values }) });
        toast(`批量写入完成：${Number(payload.result?.created) || 0} 新建，${Number(payload.result?.updated) || 0} 更新`);
        closeModal("gap-batch-paste-modal");
        window.location.reload();
        return;
      }
      if (form.id === "gap-transition-form") {
        event.preventDefault();
        await request("/api/transition-blocks", { method: "POST", body: JSON.stringify({ project_id: projectId(), source_page_id: form.elements.source_page_id.value || null, target_page_id: form.elements.target_page_id.value || null, transition_type: form.elements.transition_type.value, duration_frames: Number(form.elements.duration_frames.value) || 0, sort_order: 0 }) });
        toast("转场结构块已添加");
        return refreshStoryTools();
      }
      if (form.id === "gap-blocker-form") {
        event.preventDefault();
        await request("/api/blocking-issues", { method: "POST", body: JSON.stringify({ project_id: projectId(), batch_id: currentParams().get("batch") || null, severity: form.elements.severity.value, category: form.elements.category.value.trim() || "manual", message: form.elements.message.value.trim() }) });
        toast("阻塞项已添加");
        return refreshBlockers();
      }
    } catch (error) {
      event.preventDefault();
      toast(error.message || "提交失败");
    }
  }

  async function handleChange(event) {
    const select = event.target.closest("[data-gap-reference-mode]");
    if (!select) return;
    try {
      await request(`/api/material-pages/${encodeURIComponent(select.dataset.pageId)}/reference-mode`, { method: "PATCH", body: JSON.stringify({ mode: select.value }) });
      toast(select.value === "link" ? "已改为链接引用" : "已改为独立复制");
    } catch (error) {
      toast(error.message);
    }
  }

  function enhanceCurrentPage() {
    const pageKey = currentParams().get("page") || "projects";
    enhance(pageKey, state.project).catch(() => {});
  }

  document.addEventListener("click", handleClick);
  document.addEventListener("submit", handleSubmit);
  document.addEventListener("change", handleChange);
  document.addEventListener("error", (event) => {
    const image = event.target.closest?.("img.gap-fill-lazy-image");
    if (!image || image.dataset.fallbackUsed === "1") return;
    image.dataset.fallbackUsed = "1";
    image.src = image.dataset.originalSrc;
  }, true);
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    document.querySelectorAll(".gap-fill-modal-backdrop.show").forEach((modal) => closeModal(modal.id));
  });

  let observerQueued = false;
  const observer = new MutationObserver(() => {
    if (observerQueued) return;
    observerQueued = true;
    requestAnimationFrame(() => {
      observerQueued = false;
      enhanceCurrentPage();
    });
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });

  window.AtelierGapFillUI = { render, enhance, request };
})();
