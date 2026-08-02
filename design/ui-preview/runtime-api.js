(function () {
  // API 路径常量：新代码应使用 API.* 而非硬编码字符串，避免 URL 分散。
  // 现有调用逐步迁移，不强制一次性全部替换。
  const API = {
    health: "/api/health",
    developerProgress: "/api/developer/progress",
    projects: "/api/projects",
    project: (id) => `/api/projects/${id}`,
    projectArchive: (id) => `/api/projects/${id}/archive`,
    projectRestore: (id) => `/api/projects/${id}/restore`,
    projectCopy: (id) => `/api/projects/${id}/copy`,
    projectOverview: (id) => `/api/projects/${id}/overview`,
    projectPermanent: (id) => `/api/projects/${id}/permanent`,
    projectCover: (id) => `/api/projects/${id}/cover`,
    projectCoverThumbnail: (id) => `/api/projects/${id}/cover/thumbnail`,
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
    branchOverrides: (branchId) => `/api/branches/${branchId}/overrides`,
    branchOverride: (id) => `/api/branch-overrides/${id}`,
    materials: "/api/materials",
    materialTrash: "/api/materials/trash",
    material: (id) => `/api/materials/${id}`,
    materialArchive: (id) => `/api/materials/${id}/archive`,
    materialRestore: (id) => `/api/materials/${id}/restore`,
    materialPermanent: (id) => `/api/materials/${id}/permanent`,
    materialReferences: (id) => `/api/materials/${id}/references`,
    materialCopy: (id) => `/api/materials/${id}/copy`,
    materialVersions: (id) => `/api/materials/${id}/versions`,
    materialVersion: (id, versionNumber) => `/api/materials/${id}/versions/${versionNumber}`,
    materialVersionRestore: (id, versionNumber) => `/api/materials/${id}/versions/${versionNumber}/restore`,
    materialPreview: (id) => `/api/materials/${id}/preview`,
    materialThumbnail: (id) => `/api/materials/${id}/thumbnail`,
    materialPages: (id) => `/api/materials/${id}/pages`,
    materialPagesOrder: (id) => `/api/materials/${id}/pages/order`,
    materialPage: (id) => `/api/material-pages/${id}`,
    materialPageCopy: (id) => `/api/material-pages/${id}/copy`,
    materialPagePreview: (id) => `/api/material-pages/${id}/preview`,
    materialPageThumbnail: (id) => `/api/material-pages/${id}/thumbnail`,
    materialTags: "/api/material-tags",
    storyTree: (projectId) => `/api/projects/${projectId}/story-tree`,
    characters: "/api/characters",
    character: (id) => `/api/characters/${id}`,
    characterArchive: (id) => `/api/characters/${id}/archive`,
    characterRestore: (id) => `/api/characters/${id}/restore`,
    characterPermanent: (id) => `/api/characters/${id}/permanent`,
    characterCopy: (id) => `/api/characters/${id}/copy`,
    characterReferences: (id) => `/api/characters/${id}/references`,
    characterTags: (id) => `/api/characters/${id}/tags`,
    characterCover: (id) => `/api/characters/${id}/cover`,
    characterCoverThumbnail: (id) => `/api/characters/${id}/cover/thumbnail`,
    characterMatrix: (id) => `/api/characters/${id}/matrix`,
    characterVariants: (id) => `/api/characters/${id}/variants`,
    characterVariantsReorder: (id) => `/api/characters/${id}/variants/reorder`,
    characterVariant: (id) => `/api/character-variants/${id}`,
    characterVariantArchive: (id) => `/api/character-variants/${id}/archive`,
    characterVariantRestore: (id) => `/api/character-variants/${id}/restore`,
    characterVariantCopy: (id) => `/api/character-variants/${id}/copy`,
    characterVariantPreview: (id) => `/api/character-variants/${id}/preview`,
    characterVariantPreviewThumbnail: (id) => `/api/character-variants/${id}/preview/thumbnail`,
    characterVariantReferences: (id) => `/api/character-variants/${id}/references`,
    characterVariantSpecValues: (id) => `/api/character-variants/${id}/spec-values`,
    characterSpecValue: (id) => `/api/character-spec-values/${id}`,
    characterSpecValuesBatch: `/api/character-spec-values/batch`,
    shotPageCharacter: (id) => `/api/shot-pages/${id}/character`,
    projectCharacters: (projectId, characterId) => `/api/projects/${projectId}/characters/${characterId}`,
    specs: "/api/specs",
    spec: (id) => `/api/specs/${id}`,
    characterDatabase: {
      status: "/api/character-database/status",
    },
    comfyuiInstances: "/api/comfyui/instances",
    comfyuiInstance: (id) => `/api/comfyui/instances/${id}`,
    comfyuiInstanceActivate: (id) => `/api/comfyui/instances/${id}/activate`,
    comfyuiInstanceTest: (id) => `/api/comfyui/instances/${id}/test`,
    comfyuiInstanceSync: (id) => `/api/comfyui/instances/${id}/sync`,
    comfyuiDiscover: "/api/comfyui/discover",
    comfyuiSettings: "/api/settings/comfyui",
    comfyuiTestConnection: "/api/comfyui/test-connection",
    comfyuiObjectInfo: "/api/comfyui/node-definitions",
    workflows: "/api/workflows",
    workflow: (id) => `/api/workflows/${id}`,
    workflowImport: (id) => `/api/workflows/${id}/import`,
    workflowImportFromImage: "/api/workflows/import-from-image",
    workflowDraft: (id) => `/api/workflows/${id}/draft`,
    workflowPublish: (id) => `/api/workflows/${id}/publish`,
    workflowExport: (id) => `/api/workflows/${id}/export`,
    workflowPrecheck: (id) => `/api/workflows/${id}/precheck`,
    workflowArchive: (id) => `/api/workflows/${id}/archive`,
    workflowRestore: (id) => `/api/workflows/${id}/restore`,
    workflowCopy: (id) => `/api/workflows/${id}/copy`,
    workflowVersions: (id) => `/api/workflows/${id}/versions`,
    workflowSlots: (id) => `/api/workflows/${id}/semantic-slots`,
    workflowSlot: (workflowId, slotName) => `/api/workflows/${workflowId}/semantic-slots/${slotName}`,
    workflowDraftNodes: (id) => `/api/workflows/${id}/draft/nodes`,
    workflowDraftNode: (id, nodeId) => `/api/workflows/${id}/draft/nodes/${nodeId}`,
    workflowDraftNodeDuplicate: (id, nodeId) => `/api/workflows/${id}/draft/nodes/${nodeId}/duplicate`,
    workflowDraftNodeReorder: (id, nodeId) => `/api/workflows/${id}/draft/nodes/${nodeId}/reorder`,
    workflowDraftNodeAssignGroup: (id, nodeId) => `/api/workflows/${id}/draft/nodes/${nodeId}/assign-group`,
    workflowDraftLinks: (id) => `/api/workflows/${id}/draft/links`,
    workflowDraftLink: (id, linkId) => `/api/workflows/${id}/draft/links/${linkId}`,
    workflowDraftLayoutCompute: (id) => `/api/workflows/${id}/draft/layout/compute`,
    workflowDraftGroups: (id) => `/api/workflows/${id}/draft/groups`,
    workflowDraftGroup: (id, groupId) => `/api/workflows/${id}/draft/groups/${groupId}`,
    workflowDraftFocus: (id) => `/api/workflows/${id}/draft/focus`,
    projectDefaultWorkflow: (projectId) => `/api/projects/${projectId}/default-workflow`,
    projectPrecheck: (projectId) => `/api/projects/${projectId}/precheck`,
    projectSnapshots: (projectId) => `/api/projects/${projectId}/snapshots`,
    projectSnapshot: (id) => `/api/story-snapshots/${id}`,
    projectSnapshotRestore: (id) => `/api/story-snapshots/${id}/restore`,
    projectOperations: (projectId) => `/api/projects/${projectId}/operations`,
    operationUndo: (id) => `/api/operations/${id}/undo`,
    operationRedo: (id) => `/api/operations/${id}/redo`,
    storyTreeBranches: (parentType, parentId) => `/api/${parentType}/${parentId}/branches`,
    batchDrafts: (projectId) => `/api/projects/${projectId}/batch-drafts`,
    batchDraft: (id) => `/api/batch-drafts/${id}`,
    batchDraftPreview: (id) => `/api/batch-drafts/${id}/preview`,
    batchDraftCommit: (id) => `/api/batch-drafts/${id}/commit`,
    projectBatches: (projectId) => `/api/projects/${projectId}/batches`,
    batch: (id) => `/api/batches/${id}`,
    batchStatus: (id) => `/api/batches/${id}/status`,
    batchTasks: (id) => `/api/batches/${id}/tasks`,
    batchProgress: (id) => `/api/batches/${id}/progress`,
    tasks: "/api/tasks",
    task: (id) => `/api/tasks/${id}`,
    taskPriority: (id) => `/api/tasks/${id}/priority`,
    taskClaim: "/api/tasks/claim",
    taskAttempts: (id) => `/api/tasks/${id}/attempts`,
    taskEvents: (id) => `/api/tasks/${id}/events`,
    taskErrorDetail: (id) => `/api/tasks/${id}/error-detail`,
    taskPreviewApiJson: (id) => `/api/tasks/${id}/preview-api-json`,
    taskSubmit: (taskId, attemptId) => `/api/tasks/${taskId}/attempts/${attemptId}/submit-to-comfyui`,
    attempt: (id) => `/api/attempts/${id}`,
    attemptProgress: (id) => `/api/attempts/${id}/progress`,
    attemptProgressSse: (id) => `/api/attempts/${id}/progress/sse`,
    attemptProgressPoll: (id) => `/api/attempts/${id}/progress/poll`,
    attemptCollectOutputs: (id) => `/api/attempts/${id}/collect-outputs`,
    taskCenterSummary: "/api/task-center/summary",
    recoverSubmittedTasks: "/api/tasks/recover-submitted",
    expireStaleLeases: "/api/tasks/expire-stale-leases",
    imageInstances: "/api/image-instances",
  };

  const emptyStateCopy = {
    projects: ["还没有项目", "创建第一个项目后，项目进度会显示在这里。", "新建项目"],
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
    library: ["图库为空", "尚未索引任何图片。", "添加图片"],
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
    `;
    page.appendChild(empty);
  }

  function projectEmptyState({ trash = false, archived = false } = {}) {
    if (trash) {
      return `
        <section class="production-empty-state">
          <span class="production-empty-icon">TR</span>
          <h2>回收站为空</h2>
          <p>被删除的项目会暂存在这里，可恢复或永久删除。</p>
          <button class="btn" type="button" data-api-action="projects-back-to-active">返回项目列表</button>
            </section>
      `;
    }
    if (archived) {
      return `
        <section class="production-empty-state">
          <span class="production-empty-icon">AR</span>
          <h2>没有已归档项目</h2>
          <p>归档的项目会显示在这里，可随时恢复。</p>
          <button class="btn" type="button" data-api-action="projects-back-to-active">返回项目列表</button>
            </section>
      `;
    }
    return `
      <section class="production-empty-state">
        <span class="production-empty-icon">A</span>
        <h2>还没有项目</h2>
        <p>输入项目名称，创建你的第一个真实项目。</p>
        <button class="btn primary" data-api-action="open-project-modal">新建项目</button>
        </section>
    `;
  }

  function projectStatusLabel(project) {
    if (project.deleted_at) return { text: "已删除", color: "red" };
    if (project.archived_at || project.status === "archived") {
      return { text: "已归档", color: "orange" };
    }
    if (project.status === "draft") return { text: "草稿", color: "purple" };
    if (project.status === "active") return { text: "进行中", color: "green" };
    return { text: "新建", color: "blue" };
  }

  function projectCard(project) {
    const status = projectStatusLabel(project);
    const created = formatProjectDate(project.created_at);
    const updated = formatProjectDate(project.updated_at);
    const rawDesc = (project.description || "").trim();
    const description = rawDesc
      ? escapeHtml(rawDesc.length > 96 ? `${rawDesc.slice(0, 96)}…` : rawDesc)
      : "暂无描述";
    const initial = escapeHtml((project.name || "?").slice(0, 1).toUpperCase());
    const isArchived = Boolean(project.archived_at || project.status === "archived");
    const hasCover = Boolean(project.cover_path);
    const coverHtml = hasCover
      ? `<img class="real-project-cover-img" src="${API.projectCoverThumbnail(project.id)}" alt="${escapeHtml(project.name)} 封面" loading="lazy" onerror="this.replaceWith(Object.assign(document.createElement('span'),{textContent:${JSON.stringify((project.name || '?').slice(0, 1).toUpperCase())}}))">`
      : `<span>${initial}</span>`;
    return `
      <article class="project-card real-project-card" data-project-id="${escapeHtml(project.id)}" role="button" tabindex="0" aria-label="打开项目 ${escapeHtml(project.name)}">
        <div class="real-project-cover" data-cover-target="${escapeHtml(project.id)}">${coverHtml}
          <button class="btn small soft real-project-cover-upload" type="button" data-api-action="upload-project-cover" data-project-id="${escapeHtml(project.id)}" data-project-name="${escapeHtml(project.name)}" aria-label="上传封面">${hasCover ? "换封面" : "加封面"}</button>
        </div>
        <div>
          <div style="display:flex;align-items:center;gap:7px">
            <span class="status ${status.color}"><i class="dot"></i>${status.text}</span>
          </div>
          <div class="project-title">${escapeHtml(project.name)}</div>
          <div class="project-meta">${description}<br>创建于 ${escapeHtml(created)}<br>更新于 ${escapeHtml(updated)}</div>
          <div class="project-tags"><span class="chip">生产项目</span></div>
          <div class="project-card-actions" style="display:flex;flex-wrap:wrap;gap:6px;margin-top:10px">
            <button class="btn small" type="button" data-api-action="edit-project" data-project-id="${escapeHtml(project.id)}" data-project-name="${escapeHtml(project.name)}" data-project-description="${escapeHtml(project.description || "")}">编辑</button>
            ${isArchived
              ? `<button class="btn small soft" type="button" data-api-action="restore-project" data-project-id="${escapeHtml(project.id)}" data-project-name="${escapeHtml(project.name)}">恢复</button>`
              : `<button class="btn small soft" type="button" data-api-action="archive-project" data-project-id="${escapeHtml(project.id)}" data-project-name="${escapeHtml(project.name)}">归档</button>`}
            <button class="btn small" type="button" data-api-action="copy-project" data-project-id="${escapeHtml(project.id)}" data-project-name="${escapeHtml(project.name)}">复制</button>
            ${hasCover ? `<button class="btn small danger-soft" type="button" data-api-action="remove-project-cover" data-project-id="${escapeHtml(project.id)}" data-project-name="${escapeHtml(project.name)}">移除封面</button>` : ""}
            <button class="btn small danger-soft" type="button" data-api-action="delete-project" data-project-id="${escapeHtml(project.id)}" data-project-name="${escapeHtml(project.name)}">删除</button>
          </div>
        </div>
      </article>
    `;
  }

  function projectTrashCard(project) {
    const deletedAt = formatProjectDate(project.deleted_at || project.updated_at);
    const initial = escapeHtml((project.name || "?").slice(0, 1).toUpperCase());
    const rawDesc = (project.description || "").trim();
    const description = rawDesc
      ? escapeHtml(rawDesc.length > 96 ? `${rawDesc.slice(0, 96)}…` : rawDesc)
      : "暂无描述";
    return `
      <article class="project-card real-project-card real-project-trash-card" data-project-id="${escapeHtml(project.id)}" aria-label="恢复或永久删除 ${escapeHtml(project.name)}">
        <div class="real-project-cover" style="opacity:0.65"><span>${initial}</span></div>
        <div>
          <span class="status red"><i class="dot"></i>已删除</span>
          <div class="project-title">${escapeHtml(project.name)}</div>
          <div class="project-meta">${description}<br>删除于 ${escapeHtml(deletedAt)}</div>
          <div class="project-card-actions" style="display:flex;flex-wrap:wrap;gap:6px;margin-top:10px">
            <button class="btn small soft" type="button" data-api-action="restore-project" data-project-id="${escapeHtml(project.id)}" data-project-name="${escapeHtml(project.name)}">恢复</button>
            <button class="btn small danger" type="button" data-api-action="permanent-delete-project" data-project-id="${escapeHtml(project.id)}" data-project-name="${escapeHtml(project.name)}">永久删除</button>
          </div>
        </div>
      </article>
    `;
  }

  function projectSkeletonCard() {
    return `
      <article class="project-card real-project-card-skeleton" aria-hidden="true">
        <div class="real-project-cover" style="opacity:0.55"></div>
        <div>
          <div style="height:14px;width:60px;background:#eef0f4;border-radius:7px;margin-bottom:8px"></div>
          <div style="height:18px;width:70%;background:#eef0f4;border-radius:9px;margin-bottom:8px"></div>
          <div style="height:10px;width:90%;background:#f1f3f7;border-radius:6px;margin-bottom:6px"></div>
          <div style="height:10px;width:80%;background:#f1f3f7;border-radius:6px"></div>
        </div>
      </article>
    `;
  }

  function projectsToolbar(state) {
    const statusOptions = [
      { value: "all", label: "全部状态" },
      { value: "draft", label: "草稿" },
      { value: "active", label: "进行中" },
      { value: "archived", label: "已归档" },
    ];
    const sortOptions = [
      { value: "updated", label: "更新时间" },
      { value: "name", label: "名称" },
      { value: "created", label: "创建时间" },
    ];
    return `
      <section class="panel projects-toolbar" aria-label="项目筛选">
        <div class="panel-body" style="display:flex;flex-wrap:wrap;gap:10px;align-items:center">
          <div class="search wide" style="flex:1;min-width:240px;max-width:380px;display:flex;align-items:center;gap:6px">
            <span>⌕</span>
            <input id="projects-search-input" type="search" value="${escapeHtml(state.q)}" placeholder="搜索项目名称或描述" style="border:0;outline:0;background:transparent;flex:1;font-size:11px;color:#4d576b" />
          </div>
          <label class="projects-filter-label" style="display:flex;align-items:center;gap:6px;color:#7d8698;font-size:10px">
            <span>状态</span>
            <select id="projects-status-select" class="modal-input" style="height:34px;padding:0 8px;font-size:11px">
              ${statusOptions.map((o) => `<option value="${o.value}" ${state.status === o.value ? "selected" : ""}>${o.label}</option>`).join("")}
            </select>
          </label>
          <label class="projects-filter-label" style="display:flex;align-items:center;gap:6px;color:#7d8698;font-size:10px">
            <span>排序</span>
            <select id="projects-sort-select" class="modal-input" style="height:34px;padding:0 8px;font-size:11px">
              ${sortOptions.map((o) => `<option value="${o.value}" ${state.sort === o.value ? "selected" : ""}>${o.label}</option>`).join("")}
            </select>
          </label>
          <span style="flex:1"></span>
          <button class="btn ${state.archived ? "" : "soft"}" type="button" data-api-action="projects-toggle-archived" aria-pressed="${state.archived ? "true" : "false"}">${state.archived ? "显示活跃" : "显示归档"}</button>
          <button class="btn ${state.trash ? "danger-soft" : ""}" type="button" data-api-action="projects-toggle-trash" aria-pressed="${state.trash ? "true" : "false"}">回收站</button>
          <button class="btn primary" type="button" data-api-action="open-project-modal">新建项目</button>
        </div>
      </section>
    `;
  }

  function projectsSummaryLine(state) {
    const heading = state.trash
      ? "回收站"
      : state.archived
      ? "已归档项目"
      : "我的项目";
    const detail = state.total
      ? `${state.total} 个项目 · 已加载 ${state.items.length} 个`
      : "暂无项目";
    return `
      <div class="section-line real-project-heading">
        <h3>${heading}</h3>
        <span>${detail}</span>
      </div>
    `;
  }

  function projectsLoadMoreWrap() {
    return `
      <div id="projects-load-more-wrap" style="display:flex;justify-content:center;margin-top:18px" hidden>
        <button class="btn soft" type="button" data-api-action="load-more-projects">加载更多</button>
      </div>
    `;
  }

  function projectsErrorState(message) {
    return `
      <section class="production-empty-state" style="grid-column:1/-1">
        <span class="production-empty-icon">!</span>
        <h2>项目列表加载失败</h2>
        <p>${escapeHtml(message)}</p>
        <button class="btn soft" type="button" data-api-action="retry-projects">重试</button>
      </section>
    `;
  }

  function bindProjectsToolbar() {
    const searchInput = document.getElementById("projects-search-input");
    if (searchInput) {
      searchInput.addEventListener("input", (event) => {
        window.clearTimeout(projectsListState.searchTimer);
        projectsListState.searchTimer = window.setTimeout(() => {
          projectsListState.q = event.target.value.trim();
          loadProjectsList(false);
        }, 280);
      });
    }
    const statusSelect = document.getElementById("projects-status-select");
    if (statusSelect) {
      statusSelect.addEventListener("change", (event) => {
        projectsListState.status = event.target.value;
        loadProjectsList(false);
      });
    }
    const sortSelect = document.getElementById("projects-sort-select");
    if (sortSelect) {
      sortSelect.addEventListener("change", (event) => {
        projectsListState.sort = event.target.value;
        loadProjectsList(false);
      });
    }
  }

  async function loadProjectsList(append = false) {
    const page = document.querySelector(".page-scroll");
    if (!page) return;
    if (append && projectsListState.loading) return;
    projectsListState.loading = true;
    const requestId = projectsListState.requestId + 1;
    projectsListState.requestId = requestId;

    const grid = page.querySelector(".real-project-grid");
    const summary = page.querySelector(".real-project-heading span");
    const loadMoreWrap = document.getElementById("projects-load-more-wrap");

    if (!append) {
      projectsListState.offset = 0;
      projectsListState.items = [];
      if (grid) grid.innerHTML = projectSkeletonCard().repeat(4);
      if (loadMoreWrap) loadMoreWrap.hidden = true;
    } else if (loadMoreWrap) {
      const btn = loadMoreWrap.querySelector("button");
      if (btn) {
        btn.disabled = true;
        btn.textContent = "正在加载…";
      }
    }

    const params = new URLSearchParams();
    if (projectsListState.q) params.set("q", projectsListState.q);
    if (projectsListState.status && projectsListState.status !== "all") {
      params.set("status", projectsListState.status);
    }
    params.set("archived", projectsListState.archived ? "true" : "false");
    params.set("trash", projectsListState.trash ? "true" : "false");
    params.set("sort", projectsListState.sort);
    params.set("limit", String(projectsListState.limit));
    params.set("offset", String(append ? projectsListState.items.length : 0));

    try {
      const payload = await request(`${API.projects}?${params.toString()}`);
      if (requestId !== projectsListState.requestId) return;
      const incoming = Array.isArray(payload.items) ? payload.items : [];
      projectsListState.items = append
        ? projectsListState.items.concat(incoming)
        : incoming;
      projectsListState.total = Number(payload.total || 0);
      projectsListState.hasMore = Boolean(payload.has_more);

      if (grid) {
        if (projectsListState.items.length) {
          grid.innerHTML = projectsListState.items
            .map((p) => (projectsListState.trash ? projectTrashCard(p) : projectCard(p)))
            .join("");
        } else {
          grid.innerHTML = `<div style="grid-column:1/-1">${projectEmptyState({
            trash: projectsListState.trash,
            archived: projectsListState.archived,
          })}</div>`;
        }
      }
      if (summary) {
        summary.textContent = projectsListState.total
          ? `${projectsListState.total} 个项目 · 已加载 ${projectsListState.items.length} 个`
          : "暂无项目";
      }
      if (loadMoreWrap) {
        loadMoreWrap.hidden = !projectsListState.hasMore;
        const btn = loadMoreWrap.querySelector("button");
        if (btn) {
          btn.disabled = false;
          btn.textContent = "加载更多";
        }
      }
    } catch (error) {
      if (requestId !== projectsListState.requestId) return;
      if (grid) grid.innerHTML = projectsErrorState(error.message);
      if (summary) summary.textContent = "";
      if (loadMoreWrap) loadMoreWrap.hidden = true;
    } finally {
      if (requestId === projectsListState.requestId) {
        projectsListState.loading = false;
      }
    }
  }

  async function renderProductionProjects() {
    const page = document.querySelector(".page-scroll");
    if (!page) return;
    const header = page.querySelector(".page-header");
    [...page.children].forEach((child) => {
      if (child !== header) child.remove();
    });
    const title = header?.querySelector(".page-title");
    const subtitle = header?.querySelector(".page-subtitle");
    const actions = header?.querySelector(".header-actions");
    if (title) title.textContent = "项目中心";
    if (subtitle) subtitle.textContent = "管理所有项目，包括归档、回收站和复制。";
    if (actions) {
      actions.innerHTML = '<button class="btn primary" type="button" data-api-action="open-project-modal">新建项目</button>';
    }

    page.insertAdjacentHTML("beforeend", projectsToolbar(projectsListState));
    page.insertAdjacentHTML("beforeend", projectsSummaryLine(projectsListState));
    page.insertAdjacentHTML(
      "beforeend",
      `<div class="grid cols-2 real-project-grid">${projectSkeletonCard().repeat(4)}</div>`
    );
    page.insertAdjacentHTML("beforeend", projectsLoadMoreWrap());

    bindProjectsToolbar();
    await loadProjectsList(false);
  }

  // 工作流库列表状态：与 projectsListState 保持一致的防竞态与分页结构。
  const workflowsListState = {
    q: "",
    status: "all",
    sort: "updated",
    limit: 24,
    offset: 0,
    total: 0,
    items: [],
    hasMore: false,
    loading: false,
    requestId: 0,
    searchTimer: null,
  };

  function workflowStatusLabel(workflow) {
    if (workflow.archived_at || workflow.status === "archived") {
      return { text: "已归档", color: "orange" };
    }
    if (workflow.status === "draft") return { text: "草稿", color: "purple" };
    if (workflow.status === "published") return { text: "已发布", color: "green" };
    return { text: "新建", color: "blue" };
  }

  function workflowSourceTypeLabel(workflow) {
    const sourceType = workflow.source_type || "manual";
    const map = {
      manual: { text: "手动创建", code: "MN" },
      api: { text: "API 导入", code: "API" },
      image: { text: "图片提取", code: "IMG" },
      comfyui: { text: "ComfyUI 读取", code: "CF" },
      template: { text: "全局模板", code: "TM" },
    };
    return map[sourceType] || { text: sourceType, code: "?" };
  }

  function workflowSkeletonCard() {
    return `
      <article class="project-card real-project-card-skeleton" aria-hidden="true">
        <div style="height:60px;background:#eef0f4;border-radius:8px;margin-bottom:10px"></div>
        <div style="height:16px;width:70%;background:#eef0f4;border-radius:8px;margin-bottom:8px"></div>
        <div style="height:10px;width:90%;background:#f1f3f7;border-radius:6px;margin-bottom:6px"></div>
        <div style="height:10px;width:60%;background:#f1f3f7;border-radius:6px"></div>
      </article>
    `;
  }

  function workflowsToolbar(state) {
    const statusOptions = [
      { value: "all", label: "全部" },
      { value: "draft", label: "草稿" },
      { value: "published", label: "已发布" },
      { value: "archived", label: "已归档" },
    ];
    const sortOptions = [
      { value: "updated", label: "更新时间" },
      { value: "name", label: "名称" },
      { value: "created", label: "创建时间" },
    ];
    return `
      <section class="panel projects-toolbar" aria-label="工作流筛选">
        <div class="panel-body" style="display:flex;flex-wrap:wrap;gap:10px;align-items:center">
          <div class="search wide" style="flex:1;min-width:240px;max-width:380px;display:flex;align-items:center;gap:6px">
            <span>⌕</span>
            <input id="workflows-search-input" type="search" value="${escapeHtml(state.q)}" placeholder="搜索工作流名称或节点" style="border:0;outline:0;background:transparent;flex:1;font-size:11px;color:#4d576b" />
          </div>
          <label class="projects-filter-label" style="display:flex;align-items:center;gap:6px;color:#7d8698;font-size:10px">
            <span>类型</span>
            <select id="workflows-status-select" class="modal-input" style="height:34px;padding:0 8px;font-size:11px">
              ${statusOptions.map((o) => `<option value="${o.value}" ${state.status === o.value ? "selected" : ""}>${o.label}</option>`).join("")}
            </select>
          </label>
          <label class="projects-filter-label" style="display:flex;align-items:center;gap:6px;color:#7d8698;font-size:10px">
            <span>排序</span>
            <select id="workflows-sort-select" class="modal-input" style="height:34px;padding:0 8px;font-size:11px">
              ${sortOptions.map((o) => `<option value="${o.value}" ${state.sort === o.value ? "selected" : ""}>${o.label}</option>`).join("")}
            </select>
          </label>
          <span style="flex:1"></span>
          <span id="workflows-connection-status" class="status orange"><i class="dot"></i>ComfyUI 未检测</span>
        </div>
      </section>
    `;
  }

  function workflowsSummaryLine(state) {
    const detail = state.total
      ? `${state.total} 个工作流 · 已加载 ${state.items.length} 个`
      : "暂无工作流";
    return `
      <div class="section-line real-project-heading">
        <h3>工作流库</h3>
        <span>${detail}</span>
      </div>
    `;
  }

  function workflowsLoadMoreWrap() {
    return `
      <div id="workflows-load-more-wrap" style="display:flex;justify-content:center;margin-top:18px" hidden>
        <button class="btn soft" type="button" data-api-action="load-more-workflows">加载更多</button>
      </div>
    `;
  }

  function workflowsEmptyState() {
    return `
      <section class="production-empty-state" style="grid-column:1/-1">
        <span class="production-empty-icon">WF</span>
        <h2>还没有工作流</h2>
        <p>准备第一次跑图时，再从 ComfyUI 读取或创建工作流。</p>
        <button class="btn primary" type="button" data-api-action="create-workflow">新建工作流</button>
        </section>
    `;
  }

  function workflowsErrorState(message) {
    return `
      <section class="production-empty-state" style="grid-column:1/-1">
        <span class="production-empty-icon">!</span>
        <h2>工作流列表加载失败</h2>
        <p>${escapeHtml(message)}</p>
        <button class="btn soft" type="button" data-api-action="retry-workflows">重试</button>
      </section>
    `;
  }

  function workflowCard(workflow) {
    const status = workflowStatusLabel(workflow);
    const source = workflowSourceTypeLabel(workflow);
    const updated = formatProjectDate(workflow.updated_at || workflow.created_at);
    const versionLabel = workflow.current_version ? `v${workflow.current_version}` : "未发布";
    const nodeCount = Number(workflow.node_count) || 0;
    const slotCount = Number(workflow.slot_count) || 0;
    const name = escapeHtml(workflow.name || "未命名工作流");
    const isArchived = Boolean(workflow.archived_at || workflow.status === "archived");
    return `
      <article class="project-card real-project-card real-workflow-card" data-workflow-id="${escapeHtml(workflow.id)}" role="button" tabindex="0" aria-label="打开工作流 ${name}">
        <div class="real-project-cover" style="min-height:60px;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#eef2ff,#f3dae9)">
          <span style="font-size:20px;font-weight:700;color:#7d8698">${escapeHtml(source.code)}</span>
        </div>
        <div>
          <div style="display:flex;align-items:center;gap:7px;justify-content:space-between">
            <span class="status ${status.color}"><i class="dot"></i>${status.text}</span>
            <span class="chip blue">${escapeHtml(versionLabel)}</span>
          </div>
          <div class="project-title">${name}</div>
          <div class="project-meta">${nodeCount} 节点 · ${slotCount} 个语义插槽<br>来源：${escapeHtml(source.text)}<br>更新于 ${escapeHtml(updated)}</div>
          <div class="project-card-actions" style="display:flex;flex-wrap:wrap;gap:6px;margin-top:10px">
            <button class="btn small" type="button" data-api-action="open-workflow" data-workflow-id="${escapeHtml(workflow.id)}">编辑</button>
            <button class="btn small" type="button" data-api-action="copy-workflow" data-workflow-id="${escapeHtml(workflow.id)}" data-workflow-name="${name}">复制</button>
            ${isArchived
              ? `<button class="btn small soft" type="button" data-api-action="restore-workflow" data-workflow-id="${escapeHtml(workflow.id)}" data-workflow-name="${name}">恢复</button>`
              : `<button class="btn small soft" type="button" data-api-action="archive-workflow" data-workflow-id="${escapeHtml(workflow.id)}" data-workflow-name="${name}">归档</button>`}
            <button class="btn small danger-soft" type="button" data-api-action="delete-workflow" data-workflow-id="${escapeHtml(workflow.id)}" data-workflow-name="${name}">删除</button>
          </div>
        </div>
      </article>
    `;
  }

  function bindWorkflowsToolbar() {
    const searchInput = document.getElementById("workflows-search-input");
    if (searchInput) {
      searchInput.addEventListener("input", (event) => {
        window.clearTimeout(workflowsListState.searchTimer);
        workflowsListState.searchTimer = window.setTimeout(() => {
          workflowsListState.q = event.target.value.trim();
          loadWorkflowsList(false);
        }, 280);
      });
    }
    const statusSelect = document.getElementById("workflows-status-select");
    if (statusSelect) {
      statusSelect.addEventListener("change", (event) => {
        workflowsListState.status = event.target.value;
        loadWorkflowsList(false);
      });
    }
    const sortSelect = document.getElementById("workflows-sort-select");
    if (sortSelect) {
      sortSelect.addEventListener("change", (event) => {
        workflowsListState.sort = event.target.value;
        loadWorkflowsList(false);
      });
    }
  }

  async function loadWorkflowsList(append = false) {
    const page = document.querySelector(".page-scroll");
    if (!page) return;
    if (append && workflowsListState.loading) return;
    workflowsListState.loading = true;
    const requestId = workflowsListState.requestId + 1;
    workflowsListState.requestId = requestId;

    const grid = page.querySelector(".real-workflow-grid");
    const summary = page.querySelector(".real-project-heading span");
    const loadMoreWrap = document.getElementById("workflows-load-more-wrap");

    if (!append) {
      workflowsListState.offset = 0;
      workflowsListState.items = [];
      if (grid) grid.innerHTML = workflowSkeletonCard().repeat(4);
      if (loadMoreWrap) loadMoreWrap.hidden = true;
    } else if (loadMoreWrap) {
      const btn = loadMoreWrap.querySelector("button");
      if (btn) {
        btn.disabled = true;
        btn.textContent = "正在加载…";
      }
    }

    const params = new URLSearchParams();
    if (workflowsListState.q) params.set("q", workflowsListState.q);
    if (workflowsListState.status && workflowsListState.status !== "all") {
      params.set("status", workflowsListState.status);
    }
    params.set("sort", workflowsListState.sort);
    params.set("limit", String(workflowsListState.limit));
    params.set("offset", String(append ? workflowsListState.items.length : 0));

    try {
      const payload = await request(`${API.workflows}?${params.toString()}`);
      if (requestId !== workflowsListState.requestId) return;
      const incoming = Array.isArray(payload.items) ? payload.items : [];
      workflowsListState.items = append
        ? workflowsListState.items.concat(incoming)
        : incoming;
      workflowsListState.total = Number(payload.total || 0);
      workflowsListState.hasMore = Boolean(payload.has_more);

      if (grid) {
        if (workflowsListState.items.length) {
          grid.innerHTML = workflowsListState.items
            .map((w) => workflowCard(w))
            .join("");
        } else {
          grid.innerHTML = `<div style="grid-column:1/-1">${workflowsEmptyState()}</div>`;
        }
      }
      if (summary) {
        summary.textContent = workflowsListState.total
          ? `${workflowsListState.total} 个工作流 · 已加载 ${workflowsListState.items.length} 个`
          : "暂无工作流";
      }
      if (loadMoreWrap) {
        loadMoreWrap.hidden = !workflowsListState.hasMore;
        const btn = loadMoreWrap.querySelector("button");
        if (btn) {
          btn.disabled = false;
          btn.textContent = "加载更多";
        }
      }
    } catch (error) {
      if (requestId !== workflowsListState.requestId) return;
      if (grid) grid.innerHTML = workflowsErrorState(error.message);
      if (summary) summary.textContent = "";
      if (loadMoreWrap) loadMoreWrap.hidden = true;
    } finally {
      if (requestId === workflowsListState.requestId) {
        workflowsListState.loading = false;
      }
    }
  }

  async function renderProductionWorkflows() {
    const page = document.querySelector(".page-scroll");
    if (!page) return;
    const header = page.querySelector(".page-header");
    [...page.children].forEach((child) => {
      if (child !== header) child.remove();
    });
    const title = header?.querySelector(".page-title");
    const subtitle = header?.querySelector(".page-subtitle");
    const actions = header?.querySelector(".header-actions");
    if (title) title.textContent = "工作流库";
    if (subtitle) subtitle.textContent = "管理 ComfyUI 工作流、版本和语义插槽。";
    if (actions) {
      actions.innerHTML = '<button class="btn" type="button" data-api-action="import-workflow-json">导入 JSON</button><button class="btn primary" type="button" data-api-action="create-workflow">新建工作流</button>';
    }

    page.insertAdjacentHTML("beforeend", workflowsToolbar(workflowsListState));
    page.insertAdjacentHTML("beforeend", workflowsSummaryLine(workflowsListState));
    page.insertAdjacentHTML(
      "beforeend",
      `<div class="grid cols-3 real-workflow-grid">${workflowSkeletonCard().repeat(4)}</div>`
    );
    page.insertAdjacentHTML("beforeend", workflowsLoadMoreWrap());

    bindWorkflowsToolbar();
    await loadWorkflowsList(false);
    // 渲染工作流页时同步刷新顶部 ComfyUI 状态指示器。
    updateComfyuiStatusIndicator();
  }

  // 新建工作流弹窗：仅采集名称，提交后 POST 到工作流集合接口。
  function ensureWorkflowCreateModal() {
    let modal = document.getElementById("workflow-create-modal");
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "workflow-create-modal";
    modal.className = "atelier-modal-backdrop";
    modal.hidden = true;
    modal.innerHTML = `
      <section class="atelier-modal" role="dialog" aria-modal="true" aria-labelledby="workflow-create-title">
        <div class="atelier-modal-icon">WF</div>
        <h2 id="workflow-create-title">新建工作流</h2>
        <p>输入工作流名称，创建后可在画布中编辑节点。</p>
        <form id="workflow-create-form">
          <label class="label" for="workflow-create-name">工作流名称</label>
          <input id="workflow-create-name" class="modal-input" name="name" maxlength="120" autocomplete="off" placeholder="例如：角色替换工作流" required />
          <div class="modal-error" id="workflow-create-error" role="alert"></div>
          <div class="modal-actions">
            <button class="btn" type="button" data-api-action="close-workflow-modal">取消</button>
            <button class="btn primary" type="submit">创建工作流</button>
          </div>
        </form>
      </section>
    `;
    document.body.appendChild(modal);
    modal.addEventListener("click", (event) => {
      if (event.target === modal) closeWorkflowCreateModal();
    });
    modal.querySelector("form").addEventListener("submit", submitWorkflowCreate);
    return modal;
  }

  function openWorkflowCreateModal() {
    const modal = ensureWorkflowCreateModal();
    const error = modal.querySelector(".modal-error");
    const nameInput = modal.querySelector('input[name="name"]');
    error.textContent = "";
    nameInput.value = "";
    modal.hidden = false;
    requestAnimationFrame(() => {
      modal.classList.add("show");
      nameInput.focus();
    });
  }

  function closeWorkflowCreateModal() {
    const modal = document.getElementById("workflow-create-modal");
    if (!modal) return;
    modal.classList.remove("show");
    window.setTimeout(() => {
      modal.hidden = true;
    }, 150);
  }

  async function submitWorkflowCreate(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const nameInput = form.querySelector('input[name="name"]');
    const submit = form.querySelector('button[type="submit"]');
    const error = form.querySelector(".modal-error");
    const name = nameInput.value.trim().replace(/\s+/g, " ");
    if (!name) {
      error.textContent = "请输入工作流名称。";
      nameInput.focus();
      return;
    }
    submit.disabled = true;
    submit.textContent = "正在创建…";
    error.textContent = "";
    try {
      await request(API.workflows, {
        method: "POST",
        body: JSON.stringify({ name, source_type: "manual" }),
      });
      closeWorkflowCreateModal();
      await loadWorkflowsList(false);
      if (typeof showToast === "function") showToast(`工作流「${name}」已创建`);
    } catch (requestError) {
      error.textContent = requestError.message;
      nameInput.focus();
    } finally {
      submit.disabled = false;
      submit.textContent = "创建工作流";
    }
  }

  // 导入 JSON 弹窗：采集 JSON 文本与来源格式（UI/API），提交后 POST。
  function ensureWorkflowImportModal() {
    let modal = document.getElementById("workflow-import-modal");
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "workflow-import-modal";
    modal.className = "atelier-modal-backdrop";
    modal.hidden = true;
    modal.innerHTML = `
      <section class="atelier-modal" role="dialog" aria-modal="true" aria-labelledby="workflow-import-title">
        <div class="atelier-modal-icon">WF</div>
        <h2 id="workflow-import-title">导入工作流</h2>
        <p>选择 ComfyUI 导出的工作流 JSON 文件，系统自动识别格式。</p>
        <form id="workflow-import-form">
          <label class="label" for="workflow-import-name">工作流名称</label>
          <input id="workflow-import-name" class="modal-input" name="name" maxlength="120" autocomplete="off" placeholder="给工作流命名" required />
          <label class="label">工作流文件</label>
          <div class="workflow-import-dropzone" id="workflow-import-dropzone">
            <input type="file" id="workflow-import-file" accept=".json,application/json" hidden />
            <div class="workflow-import-dropzone-empty" id="workflow-import-dropzone-empty">
              <div class="workflow-import-dropzone-icon">JSON</div>
              <div class="workflow-import-dropzone-text">
                <strong>点击选择文件</strong>
                <small>支持 ComfyUI UI/API 格式，自动识别</small>
              </div>
            </div>
            <div class="workflow-import-dropzone-filled" id="workflow-import-dropzone-filled" hidden>
              <div class="workflow-import-file-info">
                <strong id="workflow-import-file-name">—</strong>
                <small id="workflow-import-file-meta">—</small>
              </div>
              <button class="btn small" type="button" id="workflow-import-reselect">重新选择</button>
            </div>
          </div>
          <div class="modal-error" id="workflow-import-error" role="alert"></div>
          <div class="modal-actions">
            <button class="btn" type="button" data-api-action="close-workflow-import-modal">取消</button>
            <button class="btn primary" type="submit" id="workflow-import-submit">导入工作流</button>
          </div>
        </form>
      </section>
    `;
    document.body.appendChild(modal);
    modal.addEventListener("click", (event) => {
      if (event.target === modal) closeWorkflowImportModal();
    });
    modal.querySelector("form").addEventListener("submit", submitWorkflowImport);
    // 文件选择：读取 .json 文件，自动识别格式，文件名填入工作流名称
    const fileInput = modal.querySelector("#workflow-import-file");
    const dropzone = modal.querySelector("#workflow-import-dropzone");
    const dropzoneEmpty = modal.querySelector("#workflow-import-dropzone-empty");
    const dropzoneFilled = modal.querySelector("#workflow-import-dropzone-filled");
    const fileNameLabel = modal.querySelector("#workflow-import-file-name");
    const fileMetaLabel = modal.querySelector("#workflow-import-file-meta");
    const nameInput = modal.querySelector("#workflow-import-name");
    const reselectBtn = modal.querySelector("#workflow-import-reselect");
    const submitBtn = modal.querySelector("#workflow-import-submit");
    const errorBox = modal.querySelector("#workflow-import-error");

    function handleFile(file) {
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        const text = String(reader.result || "");
        let parsed;
        try {
          parsed = JSON.parse(text);
        } catch (e) {
          errorBox.textContent = "JSON 格式错误，无法解析";
          return;
        }
        // 自动识别格式
        const format = detectWorkflowFormat(parsed);
        if (!format) {
          errorBox.textContent = "无法识别工作流格式，请检查文件内容";
          return;
        }
        errorBox.textContent = "";
        // 暂存解析结果
        dropzone._parsedJson = parsed;
        dropzone._sourceFormat = format;
        // 切换为已选择状态
        dropzoneEmpty.hidden = true;
        dropzoneFilled.hidden = false;
        fileNameLabel.textContent = file.name;
        const formatLabel = format === "ui_json" ? "UI 格式" : "API 格式";
        const sizeKb = Math.max(1, Math.round(text.length / 1024));
        fileMetaLabel.textContent = `${formatLabel} · ${sizeKb} KB`;
        // 文件名（去掉 .json 扩展名）填入工作流名称（仅当名称为空时）
        if (!nameInput.value.trim()) {
          const baseName = file.name.replace(/\.json$/i, "").replace(/[_-]+/g, " ").trim();
          if (baseName) nameInput.value = baseName;
        }
      };
      reader.onerror = () => {
        errorBox.textContent = "读取文件失败，请重试";
      };
      reader.readAsText(file);
    }

    dropzone.addEventListener("click", (e) => {
      // 不在"重新选择"按钮上时才触发
      if (!e.target.closest("#workflow-import-reselect")) {
        fileInput.click();
      }
    });
    reselectBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      fileInput.click();
    });
    fileInput.addEventListener("change", () => {
      const file = fileInput.files && fileInput.files[0];
      handleFile(file);
      fileInput.value = ""; // 允许重复选择同一文件
    });
    // 拖拽支持
    dropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropzone.classList.add("drag-over");
    });
    dropzone.addEventListener("dragleave", () => {
      dropzone.classList.remove("drag-over");
    });
    dropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropzone.classList.remove("drag-over");
      const file = e.dataTransfer?.files?.[0];
      if (file) handleFile(file);
    });
    return modal;
  }

  // 自动识别工作流格式：UI JSON 有 nodes 数组，API JSON 值含 class_type
  function detectWorkflowFormat(raw) {
    if (!raw || typeof raw !== "object") return null;
    if (Array.isArray(raw.nodes)) return "ui_json";
    for (const value of Object.values(raw)) {
      if (value && typeof value === "object" && "class_type" in value) return "api_json";
    }
    return null;
  }

  function openWorkflowImportModal() {
    const modal = ensureWorkflowImportModal();
    const error = modal.querySelector(".modal-error");
    error.textContent = "";
    modal.querySelector('input[name="name"]').value = "";
    const dropzone = modal.querySelector("#workflow-import-dropzone");
    if (dropzone) {
      dropzone._parsedJson = null;
      dropzone._sourceFormat = null;
    }
    modal.querySelector("#workflow-import-dropzone-empty").hidden = false;
    modal.querySelector("#workflow-import-dropzone-filled").hidden = true;
    modal.hidden = false;
    requestAnimationFrame(() => {
      modal.classList.add("show");
      modal.querySelector('input[name="name"]').focus();
    });
  }

  function closeWorkflowImportModal() {
    const modal = document.getElementById("workflow-import-modal");
    if (!modal) return;
    modal.classList.remove("show");
    window.setTimeout(() => {
      modal.hidden = true;
    }, 150);
  }

  async function submitWorkflowImport(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const nameInput = form.querySelector('input[name="name"]');
    const submit = form.querySelector('button[type="submit"]');
    const error = form.querySelector(".modal-error");
    const dropzone = form.querySelector("#workflow-import-dropzone");
    const name = nameInput.value.trim().replace(/\s+/g, " ");
    if (!name) {
      error.textContent = "请输入工作流名称";
      nameInput.focus();
      return;
    }
    const parsed = dropzone?._parsedJson;
    const sourceFormat = dropzone?._sourceFormat;
    if (!parsed || !sourceFormat) {
      error.textContent = "请先选择工作流 JSON 文件";
      return;
    }
    submit.disabled = true;
    submit.textContent = "正在导入…";
    error.textContent = "";
    try {
      // 分两步：先创建空工作流，再导入 JSON 到草稿。
      const createResp = await request(API.workflows, {
        method: "POST",
        body: JSON.stringify({ name, source_type: sourceFormat }),
      });
      const workflowId = createResp.workflow?.id;
      if (!workflowId) {
        throw new Error("创建工作流失败，未返回工作流 ID");
      }
      try {
        await request(API.workflowImport(workflowId), {
          method: "POST",
          body: JSON.stringify({ raw_json: parsed, source_format: sourceFormat }),
        });
      } catch (importError) {
        // 导入失败时删除刚创建的空工作流
        try {
          await request(API.workflow(workflowId), { method: "DELETE" });
        } catch (_) {
          // 忽略清理失败
        }
        throw importError;
      }
      // API JSON 格式没有节点位置信息，导入后自动计算布局
      if (sourceFormat === "api_json") {
        try {
          await request(API.workflowDraftLayoutCompute(workflowId), {
            method: "POST",
            body: "{}",
          });
        } catch (_) {
          // 布局失败不阻断导入流程，用户可在画布中手动触发"自动整理"
        }
      }
      closeWorkflowImportModal();
      await loadWorkflowsList(false);
      if (typeof showToast === "function") showToast(`工作流「${name}」已导入`);
    } catch (requestError) {
      error.textContent = requestError.message;
      nameInput.focus();
    } finally {
      submit.disabled = false;
      submit.textContent = "导入工作流";
    }
  }

  // 从图片提取工作流：选择本地图片文件后上传。
  function openWorkflowImagePicker() {
    let input = document.getElementById("workflow-image-file-input");
    if (!input) {
      input = document.createElement("input");
      input.type = "file";
      input.id = "workflow-image-file-input";
      input.accept = "image/png,image/jpeg,image/webp";
      input.style.display = "none";
      document.body.appendChild(input);
    }
    input.value = "";
    input.onchange = async () => {
      const file = input.files && input.files[0];
      if (!file) return;
      const formData = new FormData();
      formData.append("file", file);
      formData.append("name", file.name.replace(/\.[^.]+$/, "").slice(0, 120) || "从图片提取的工作流");
      formData.append("source_type", "image_metadata");
      if (typeof showToast === "function") showToast("正在从图片提取工作流…");
      try {
        await request(API.workflows, {
          method: "POST",
          body: formData,
        });
        await loadWorkflowsList(false);
        if (typeof showToast === "function") showToast("工作流已从图片提取");
      } catch (requestError) {
        if (typeof showToast === "function") showToast(requestError.message);
      }
    };
    input.click();
  }

  async function archiveWorkflow(workflowId, name) {
    if (!await confirmDialog({
      title: `归档工作流「${name}」`,
      message: "归档后工作流会从活跃列表移除，可随时恢复。",
      confirmText: "归档",
      danger: false,
    })) {
      return;
    }
    try {
      await request(API.workflowArchive(workflowId), { method: "POST" });
      await loadWorkflowsList(false);
      if (typeof showToast === "function") showToast(`工作流「${name}」已归档`);
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message);
    }
  }

  async function restoreWorkflow(workflowId, name) {
    try {
      await request(API.workflowRestore(workflowId), { method: "POST" });
      await loadWorkflowsList(false);
      if (typeof showToast === "function") showToast(`工作流「${name}」已恢复`);
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message);
    }
  }

  async function copyWorkflow(workflowId, name) {
    try {
      await request(API.workflowCopy(workflowId), { method: "POST" });
      await loadWorkflowsList(false);
      if (typeof showToast === "function") showToast(`工作流「${name}」已复制`);
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message);
    }
  }

  async function deleteWorkflow(workflowId, name) {
    if (!await confirmDialog({
      title: `删除工作流「${name}」`,
      message: "工作流将移入回收站，可恢复。继续删除？",
      confirmText: "移入回收站",
      danger: true,
    })) {
      return;
    }
    try {
      await request(API.workflow(workflowId), { method: "DELETE" });
      await loadWorkflowsList(false);
      if (typeof showToast === "function") showToast(`工作流「${name}」已移入回收站`);
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message);
    }
  }

  // ComfyUI 实例状态：缓存当前实例列表，供设置页和顶部指示器共用。
  const comfyuiState = {
    instances: [],
    loading: false,
    requestId: 0,
  };

  function comfyuiInstancesFromPayload(payload) {
    if (Array.isArray(payload?.instances)) return payload.instances;
    if (Array.isArray(payload?.items)) return payload.items;
    return Array.isArray(payload) ? payload : [];
  }

  function comfyuiCandidatesFromPayload(payload) {
    if (Array.isArray(payload?.candidates)) return payload.candidates;
    if (Array.isArray(payload?.items)) return payload.items;
    return Array.isArray(payload) ? payload : [];
  }

  function comfyuiConnectionStatus(instance) {
    return String(instance?.last_connection_status || instance?.connection_status || "unknown").toLowerCase();
  }

  function comfyuiDeviceSummary(instance) {
    if (instance?.device) return String(instance.device);
    const devices = Array.isArray(instance?.device_summary) ? instance.device_summary : [];
    if (!devices.length) return "";
    return devices
      .map((device) => device?.name || device?.device_name || device?.type || "")
      .filter(Boolean)
      .join(" / ");
  }

  function comfyuiInstanceStatusLabel(instance) {
    const connectionStatus = comfyuiConnectionStatus(instance);
    if (instance.is_active && (connectionStatus === "ok" || connectionStatus === "connected")) {
      return { text: "已连接", color: "green" };
    }
    if (connectionStatus === "unreachable" || connectionStatus === "failed" || connectionStatus === "error") {
      return { text: "连接失败", color: "red" };
    }
    if (connectionStatus === "ok" || connectionStatus === "connected") {
      return { text: "已连接", color: "green" };
    }
    return { text: "未检测", color: "orange" };
  }

  function comfyuiInstanceCard(instance) {
    const status = comfyuiInstanceStatusLabel(instance);
    const name = escapeHtml(instance.name || "未命名实例");
    const httpUrl = escapeHtml(instance.base_url || instance.http_url || "—");
    const wsUrl = instance.websocket_url || instance.ws_url || "";
    const version = instance.comfyui_version || instance.version || "";
    const device = comfyuiDeviceSummary(instance);
    const nodeSummary = instance.node_definition_summary || {};
    const nodeCount = Number(nodeSummary.node_count || instance.node_count || 0);
    const lastChecked = instance.last_checked_at || "";
    const lastSynced = nodeSummary.last_synced_at || "";
    const syncTime = lastSynced || lastChecked || "连接后读取";
    const isActive = Boolean(instance.is_active);
    return `
      <article class="setting-card real-comfyui-card" data-instance-id="${escapeHtml(instance.id)}">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span class="status ${status.color}"><i class="dot"></i>${status.text}</span>
          <div style="display:flex;gap:6px;align-items:center">
            ${isActive ? '<span class="chip blue">活动实例</span>' : '<span class="chip">备用</span>'}
          </div>
        </div>
        <div class="setting-title" style="margin-top:12px">${name}</div>
        <div class="setting-desc">运行生成任务并提供节点定义。</div>
        <div class="setting-value">${httpUrl}</div>
        ${wsUrl ? `<div class="kv"><span>WebSocket</span><strong>${escapeHtml(wsUrl)}</strong></div>` : ""}
        <div class="kv"><span>版本</span><strong>${version ? escapeHtml(version) : "连接后读取"}</strong></div>
        <div class="kv"><span>GPU</span><strong>${device ? escapeHtml(device) : "连接后读取"}</strong></div>
        <div class="kv"><span>节点</span><strong>${nodeCount || "连接后读取"}</strong></div>
        <div class="kv"><span>同步时间</span><strong>${escapeHtml(syncTime)}</strong></div>
        <div class="project-card-actions" style="display:flex;flex-wrap:wrap;gap:6px;margin-top:10px">
          ${isActive ? "" : `<button class="btn small primary" type="button" data-api-action="activate-comfyui-instance" data-instance-id="${escapeHtml(instance.id)}" data-instance-name="${name}">激活</button>`}
          <button class="btn small" type="button" data-api-action="test-comfyui-instance" data-instance-id="${escapeHtml(instance.id)}" data-instance-name="${name}">测试连接</button>
          <button class="btn small soft" type="button" data-api-action="sync-comfyui-instance" data-instance-id="${escapeHtml(instance.id)}" data-instance-name="${name}">同步节点</button>
          <button class="btn small" type="button" data-api-action="edit-comfyui-instance" data-instance-id="${escapeHtml(instance.id)}" data-instance-name="${name}">编辑</button>
          <button class="btn small danger-soft" type="button" data-api-action="delete-comfyui-instance" data-instance-id="${escapeHtml(instance.id)}" data-instance-name="${name}">删除</button>
        </div>
      </article>
    `;
  }

  function comfyuiInstancesSkeleton() {
    return `
      <article class="setting-card real-comfyui-card-skeleton" aria-hidden="true">
        <div style="height:14px;width:50%;background:#eef0f4;border-radius:7px;margin-bottom:10px"></div>
        <div style="height:18px;width:70%;background:#eef0f4;border-radius:9px;margin-bottom:8px"></div>
        <div style="height:10px;width:90%;background:#f1f3f7;border-radius:6px;margin-bottom:6px"></div>
        <div style="height:10px;width:80%;background:#f1f3f7;border-radius:6px"></div>
      </article>
    `;
  }

  function comfyuiInstancesEmptyState() {
    return `
      <section class="production-empty-state">
        <span class="production-empty-icon">CF</span>
        <h2>还没有 ComfyUI 实例</h2>
        <p>添加一个 ComfyUI 实例后，工作流和生成任务才能运行。</p>
        <button class="btn primary" type="button" data-api-action="add-comfyui-instance">添加实例</button>
        <button class="btn soft" type="button" data-api-action="discover-comfyui-instances">发现局域网实例</button>
      </section>
    `;
  }

  function comfyuiInstancesErrorState(message) {
    return `
      <section class="production-empty-state">
        <span class="production-empty-icon">!</span>
        <h2>ComfyUI 实例列表加载失败</h2>
        <p>${escapeHtml(message)}</p>
        <button class="btn soft" type="button" data-api-action="retry-comfyui-instances">重试</button>
      </section>
    `;
  }

  function comfyuiInstancesHeader() {
    return `
      <div class="section-line real-project-heading" style="display:flex;align-items:center;gap:10px">
        <h3>ComfyUI 实例</h3>
        <span id="comfyui-instances-summary">正在加载…</span>
        <span style="flex:1"></span>
        <button class="btn soft" type="button" data-api-action="discover-comfyui-instances">发现实例</button>
        <button class="btn primary" type="button" data-api-action="add-comfyui-instance">添加实例</button>
      </div>
    `;
  }

  async function loadComfyuiInstances() {
    const wrap = document.getElementById("comfyui-instances-panel");
    if (!wrap) return;
    comfyuiState.loading = true;
    const requestId = comfyuiState.requestId + 1;
    comfyuiState.requestId = requestId;
    const summary = document.getElementById("comfyui-instances-summary");
    if (summary) summary.textContent = "正在加载…";
    try {
      const payload = await request(API.comfyuiInstances);
      if (requestId !== comfyuiState.requestId) return;
      const items = comfyuiInstancesFromPayload(payload);
      comfyuiState.instances = items;
      renderComfyuiInstancesList();
    } catch (error) {
      if (requestId !== comfyuiState.requestId) return;
      wrap.innerHTML = comfyuiInstancesErrorState(error.message);
    } finally {
      if (requestId === comfyuiState.requestId) {
        comfyuiState.loading = false;
      }
    }
  }

  function renderComfyuiInstancesList() {
    const wrap = document.getElementById("comfyui-instances-panel");
    if (!wrap) return;
    const summary = document.getElementById("comfyui-instances-summary");
    if (comfyuiState.instances.length) {
      const activeCount = comfyuiState.instances.filter((i) => i.is_active).length;
      wrap.innerHTML = `<div class="grid cols-2 real-comfyui-grid">${comfyuiState.instances.map((i) => comfyuiInstanceCard(i)).join("")}</div>`;
      if (summary) summary.textContent = `${comfyuiState.instances.length} 个实例 · ${activeCount} 个活动`;
    } else {
      wrap.innerHTML = comfyuiInstancesEmptyState();
      if (summary) summary.textContent = "暂无实例";
    }
    // 列表加载后同步刷新顶部状态指示器。
    updateComfyuiStatusIndicator();
  }

  async function renderProductionSettings() {
    const page = document.querySelector(".page-scroll");
    if (!page) return;
    const header = page.querySelector(".page-header");
    [...page.children].forEach((child) => {
      if (child !== header) child.remove();
    });
    const title = header?.querySelector(".page-title");
    const subtitle = header?.querySelector(".page-subtitle");
    const actions = header?.querySelector(".header-actions");
    if (title) title.textContent = "设置";
    if (subtitle) subtitle.textContent = "管理 ComfyUI 连接和应用配置。";
    if (actions) {
      actions.innerHTML = '<button class="btn primary" type="button" data-api-action="add-comfyui-instance">添加实例</button>';
    }

    page.insertAdjacentHTML("beforeend", comfyuiInstancesHeader());
    page.insertAdjacentHTML(
      "beforeend",
      `<div id="comfyui-instances-panel"><div class="grid cols-2 real-comfyui-grid">${comfyuiInstancesSkeleton().repeat(2)}</div></div>`
    );
    page.insertAdjacentHTML(
      "beforeend",
      `<section class="panel" style="margin-top:14px"><div class="panel-header"><div><div class="panel-title">应用配置</div><div class="panel-sub">单端口启动与性能索引。</div></div></div><div class="panel-body"><div class="kv"><span>前端与 API</span><strong>同一端口</strong></div><div class="kv"><span>健康接口</span><strong>/api/health</strong></div><div class="kv"><span>启动脚本</span><strong>start.bat</strong></div><div class="kv"><span>列表分页</span><strong>游标 · 每批 100</strong></div><div class="kv"><span>提示词搜索</span><strong>SQLite FTS5</strong></div><div class="kv"><span>重复检测</span><strong>SHA-256 + pHash</strong></div></div></section>`
    );

    await loadComfyuiInstances();
    updateComfyuiStatusIndicator();
  }

  // 添加/编辑实例弹窗：采集名称、HTTP 地址、WebSocket 地址（可选）、超时时间。
  function ensureComfyuiInstanceModal() {
    let modal = document.getElementById("comfyui-instance-modal");
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "comfyui-instance-modal";
    modal.className = "atelier-modal-backdrop";
    modal.hidden = true;
    modal.innerHTML = `
      <section class="atelier-modal" role="dialog" aria-modal="true" aria-labelledby="comfyui-instance-title">
        <div class="atelier-modal-icon">CF</div>
        <h2 id="comfyui-instance-title">添加 ComfyUI 实例</h2>
        <p id="comfyui-instance-context">填写 ComfyUI 实例的连接信息。</p>
        <form id="comfyui-instance-form">
          <label class="label" for="comfyui-instance-name">实例名称</label>
          <input id="comfyui-instance-name" class="modal-input" name="name" maxlength="80" autocomplete="off" placeholder="例如：本地 ComfyUI" required />
          <label class="label" for="comfyui-instance-http">HTTP 地址</label>
          <input id="comfyui-instance-http" class="modal-input" name="http_url" maxlength="200" autocomplete="off" placeholder="http://127.0.0.1:8188" required />
          <label class="label" for="comfyui-instance-ws">WebSocket 地址（可选）</label>
          <input id="comfyui-instance-ws" class="modal-input" name="ws_url" maxlength="200" autocomplete="off" placeholder="ws://127.0.0.1:8188/ws" />
          <label class="label" for="comfyui-instance-timeout">超时时间（秒）</label>
          <input id="comfyui-instance-timeout" class="modal-input" name="timeout_seconds" type="number" min="5" max="300" value="30" />
          <div class="modal-error" id="comfyui-instance-error" role="alert"></div>
          <div class="modal-actions">
            <button class="btn" type="button" data-api-action="close-comfyui-instance-modal">取消</button>
            <button class="btn primary" type="submit">保存实例</button>
          </div>
        </form>
      </section>
    `;
    document.body.appendChild(modal);
    modal.addEventListener("click", (event) => {
      if (event.target === modal) closeComfyuiInstanceModal();
    });
    modal.querySelector("form").addEventListener("submit", submitComfyuiInstance);
    return modal;
  }

  function openComfyuiInstanceAddModal() {
    const modal = ensureComfyuiInstanceModal();
    modal.dataset.mode = "create";
    delete modal.dataset.instanceId;
    modal.querySelector("h2").textContent = "添加 ComfyUI 实例";
    modal.querySelector("#comfyui-instance-context").textContent = "填写 ComfyUI 实例的连接信息。";
    modal.querySelector('button[type="submit"]').textContent = "保存实例";
    modal.querySelector(".modal-error").textContent = "";
    modal.querySelector('input[name="name"]').value = "";
    modal.querySelector('input[name="http_url"]').value = "";
    modal.querySelector('input[name="ws_url"]').value = "";
    modal.querySelector('input[name="timeout_seconds"]').value = "30";
    modal.hidden = false;
    requestAnimationFrame(() => {
      modal.classList.add("show");
      modal.querySelector('input[name="name"]').focus();
    });
  }

  function openComfyuiInstanceEditModal(instanceId, name) {
    const instance = comfyuiState.instances.find((i) => String(i.id) === String(instanceId));
    const modal = ensureComfyuiInstanceModal();
    modal.dataset.mode = "edit";
    modal.dataset.instanceId = instanceId;
    modal.querySelector("h2").textContent = "编辑 ComfyUI 实例";
    modal.querySelector("#comfyui-instance-context").textContent = `修改实例「${name}」的连接信息。`;
    modal.querySelector('button[type="submit"]').textContent = "保存修改";
    modal.querySelector(".modal-error").textContent = "";
    modal.querySelector('input[name="name"]').value = instance?.name || name || "";
    modal.querySelector('input[name="http_url"]').value = instance?.http_url || instance?.base_url || "";
    modal.querySelector('input[name="ws_url"]').value = instance?.websocket_url || instance?.ws_url || "";
    modal.querySelector('input[name="timeout_seconds"]').value = String(instance?.timeout_seconds || 30);
    modal.hidden = false;
    requestAnimationFrame(() => {
      modal.classList.add("show");
      modal.querySelector('input[name="name"]').focus();
      modal.querySelector('input[name="name"]').select();
    });
  }

  function closeComfyuiInstanceModal() {
    const modal = document.getElementById("comfyui-instance-modal");
    if (!modal) return;
    modal.classList.remove("show");
    window.setTimeout(() => {
      modal.hidden = true;
    }, 150);
  }

  async function submitComfyuiInstance(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const modal = form.closest(".atelier-modal-backdrop");
    const nameInput = form.querySelector('input[name="name"]');
    const httpInput = form.querySelector('input[name="http_url"]');
    const wsInput = form.querySelector('input[name="ws_url"]');
    const timeoutInput = form.querySelector('input[name="timeout_seconds"]');
    const submit = form.querySelector('button[type="submit"]');
    const error = form.querySelector(".modal-error");
    const name = nameInput.value.trim().replace(/\s+/g, " ");
    const httpUrl = httpInput.value.trim();
    const wsUrl = wsInput.value.trim();
    const timeoutSeconds = Number(timeoutInput.value) || 30;
    if (!name) {
      error.textContent = "请输入实例名称。";
      nameInput.focus();
      return;
    }
    if (!httpUrl) {
      error.textContent = "请输入 HTTP 地址。";
      httpInput.focus();
      return;
    }
    const body = { name, base_url: httpUrl, timeout_seconds: timeoutSeconds };
    if (wsUrl) body.websocket_url = wsUrl;
    const isEdit = modal.dataset.mode === "edit";
    const instanceId = modal.dataset.instanceId;
    submit.disabled = true;
    submit.textContent = isEdit ? "正在保存…" : "正在添加…";
    error.textContent = "";
    try {
      if (isEdit && instanceId) {
        await request(API.comfyuiInstance(instanceId), {
          method: "PATCH",
          body: JSON.stringify(body),
        });
        closeComfyuiInstanceModal();
        await loadComfyuiInstances();
        if (typeof showToast === "function") showToast(`实例「${name}」已更新`);
      } else {
        await request(API.comfyuiInstances, {
          method: "POST",
          body: JSON.stringify(body),
        });
        closeComfyuiInstanceModal();
        await loadComfyuiInstances();
        if (typeof showToast === "function") showToast(`实例「${name}」已添加`);
      }
    } catch (requestError) {
      error.textContent = requestError.message;
      nameInput.focus();
    } finally {
      submit.disabled = false;
      submit.textContent = isEdit ? "保存修改" : "保存实例";
    }
  }

  async function deleteComfyuiInstance(instanceId, name) {
    if (!await confirmDialog({
      title: `删除实例「${name}」`,
      message: "删除后实例配置将清除，无法恢复。继续删除？",
      confirmText: "删除实例",
      danger: true,
    })) {
      return;
    }
    try {
      await request(API.comfyuiInstance(instanceId), { method: "DELETE" });
      await loadComfyuiInstances();
      if (typeof showToast === "function") showToast(`实例「${name}」已删除`);
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message);
    }
  }

  async function activateComfyuiInstance(instanceId, name) {
    try {
      await request(API.comfyuiInstanceActivate(instanceId), { method: "POST" });
      await loadComfyuiInstances();
      if (typeof showToast === "function") showToast(`实例「${name}」已激活`);
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message);
    }
  }

  async function testComfyuiInstance(instanceId, name) {
    if (typeof showToast === "function") showToast(`正在测试「${name}」连接…`);
    try {
      const payload = await request(API.comfyuiInstanceTest(instanceId), { method: "POST" });
      const ok = payload && (payload.status === "ok" || payload.ok || payload.success || payload.connected);
      const latency = payload && payload.latency != null ? ` · 延迟 ${payload.latency} ms` : "";
      if (ok) {
        const version = payload.system && payload.system.comfyui_version ? ` · ${payload.system.comfyui_version}` : "";
        if (typeof showToast === "function") showToast(`「${name}」连接成功${version}${latency}`);
      } else {
        const reason = (payload && (payload.message || payload.reason)) || "连接失败";
        if (typeof showToast === "function") showToast(`「${name}」${reason}`);
      }
      await loadComfyuiInstances();
    } catch (requestError) {
      if (typeof showToast === "function") showToast(`「${name}」测试失败：${requestError.message}`);
    }
  }

  async function syncComfyuiInstance(instanceId, name) {
    if (typeof showToast === "function") showToast(`正在同步「${name}」节点定义…`);
    try {
      const payload = await request(API.comfyuiInstanceSync(instanceId), { method: "POST" });
      const count = payload && (payload.node_count || payload.synced_count || 0);
      const custom = payload && (payload.custom_node_count || 0);
      if (typeof showToast === "function") showToast(`「${name}」已同步 ${count} 个节点（自定义 ${custom}）`);
      await loadComfyuiInstances();
    } catch (requestError) {
      if (typeof showToast === "function") showToast(`「${name}」同步失败：${requestError.message}`);
    }
  }

  async function discoverComfyuiInstances() {
    if (typeof showToast === "function") showToast("正在搜索局域网 ComfyUI 实例…");
    try {
      const payload = await request(API.comfyuiDiscover, { method: "POST" });
      const candidates = comfyuiCandidatesFromPayload(payload);
      if (!candidates.length) {
        if (typeof showToast === "function") showToast("未发现局域网 ComfyUI 实例");
        return;
      }
      // 把候选列表渲染到实例面板顶部，便于用户一键添加。
      const wrap = document.getElementById("comfyui-instances-panel");
      if (wrap) {
        const list = candidates.map((c) => {
          const url = escapeHtml(c.http_url || c.base_url || c.url || "");
          const label = escapeHtml(c.name || url || "未知实例");
          return `<div class="kv" style="gap:8px"><span>${label}</span><strong>${url}</strong><button class="btn small soft" type="button" data-api-action="add-discovered-comfyui" data-url="${url}" data-name="${label}">添加</button></div>`;
        }).join("");
        wrap.insertAdjacentHTML("afterbegin", `<section class="panel" style="margin-bottom:12px"><div class="panel-header"><div><div class="panel-title">发现的实例</div><div class="panel-sub">点击添加把候选实例加入配置。</div></div></div><div class="panel-body">${list}</div></section>`);
      }
      if (typeof showToast === "function") showToast(`发现 ${candidates.length} 个候选实例`);
    } catch (requestError) {
      if (typeof showToast === "function") showToast(`发现失败：${requestError.message}`);
    }
  }

  // 顶部与侧边栏 ComfyUI 状态指示器：读取活动实例连接状态并刷新两类指示器。
  // 状态映射：绿点=已连接 / 橙点=未检测 / 红点=连接失败。
  let comfyuiStatusTimer = null;
  let comfyuiStatusRequestId = 0;

  function applyComfyuiStatusIndicator(state) {
    // state: { color: "green"|"orange"|"red", text: string }
    const colorClass = state.color || "orange";
    const text = state.text || "ComfyUI 未检测";
    // 顶部按钮指示器
    const btn = document.getElementById("comfyui-status-indicator");
    if (btn) {
      btn.classList.remove("green", "orange", "red", "pending");
      btn.classList.add(colorClass);
      const textEl = btn.querySelector(".comfyui-status-text");
      if (textEl) textEl.textContent = text;
    }
    // 侧边栏健康指示器
    const sidebar = document.getElementById("comfyui-sidebar-health");
    if (sidebar) {
      sidebar.classList.remove("green", "orange", "red", "pending");
      sidebar.classList.add(colorClass);
      const span = sidebar.querySelector("span:not(.health-dot)");
      if (span) span.textContent = text;
    }
    // 工作流工具栏连接状态
    const wfStatus = document.getElementById("workflows-connection-status");
    if (wfStatus) {
      wfStatus.classList.remove("green", "orange", "red");
      wfStatus.classList.add(colorClass);
      wfStatus.innerHTML = `<i class="dot"></i>${text}`;
    }
  }

  async function updateComfyuiStatusIndicator() {
    const requestId = comfyuiStatusRequestId + 1;
    comfyuiStatusRequestId = requestId;
    try {
      const payload = await request(API.comfyuiInstances);
      if (requestId !== comfyuiStatusRequestId) return;
      const items = comfyuiInstancesFromPayload(payload);
      const active = items.find((i) => i.is_active) || items[0];
      if (!active) {
        applyComfyuiStatusIndicator({ color: "orange", text: "ComfyUI 未配置" });
        return;
      }
      const connStatus = comfyuiConnectionStatus(active);
      if (connStatus === "ok" || connStatus === "connected") {
        applyComfyuiStatusIndicator({ color: "green", text: `ComfyUI 已连接 · ${active.name || ""}`.trim() });
      } else if (connStatus === "unreachable" || connStatus === "failed" || connStatus === "error") {
        applyComfyuiStatusIndicator({ color: "red", text: `ComfyUI 连接失败 · ${active.name || ""}`.trim() });
      } else {
        applyComfyuiStatusIndicator({ color: "orange", text: `ComfyUI 未检测 · ${active.name || ""}`.trim() });
      }
    } catch (error) {
      if (requestId !== comfyuiStatusRequestId) return;
      applyComfyuiStatusIndicator({ color: "orange", text: "ComfyUI 后端未连接" });
    }
  }

  function startComfyuiStatusPolling() {
    if (comfyuiStatusTimer) return;
    // 每 30 秒刷新一次顶部连接状态指示器。
    comfyuiStatusTimer = window.setInterval(updateComfyuiStatusIndicator, 30000);
  }

  // 页面加载后立即读取一次状态，并启动定时轮询。
  updateComfyuiStatusIndicator();
  startComfyuiStatusPolling();

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

  function overviewStatCard(label, value, note = "") {
    return `
      <div class="metric-card">
        <div class="metric-top"><span>${escapeHtml(label)}</span></div>
        <div class="metric-value">${escapeHtml(String(value))}</div>
        <div class="metric-note">${escapeHtml(note)}</div>
      </div>
    `;
  }

  function overviewBlockersList(blockers) {
    if (!Array.isArray(blockers) || !blockers.length) return "";
    return `
      <section class="panel overview-blockers-panel">
        <div class="panel-header">
          <div>
            <div class="panel-title">阻塞项</div>
            <div class="panel-sub">${blockers.length} 项需要处理</div>
          </div>
        </div>
        <div class="panel-body">
          <ul class="overview-blocker-list">
            ${blockers.map((blocker) => `
              <li class="overview-blocker-row">
                <span class="overview-blocker-code">${escapeHtml(blocker.code || "BLOCK")}</span>
                <span class="overview-blocker-msg">${escapeHtml(blocker.message || "未提供阻塞原因")}</span>
              </li>
            `).join("")}
          </ul>
        </div>
      </section>
    `;
  }

  function overviewJumpEntries(projectId) {
    return `
      <section class="panel overview-jump-panel">
        <div class="panel-header">
          <div>
            <div class="panel-title">快速跳转</div>
            <div class="panel-sub">进入项目制作的其他模块</div>
          </div>
        </div>
        <div class="panel-body overview-jump-grid">
          <a class="overview-jump-item" href="?page=story-canvas&project=${escapeHtml(projectId)}">
            <span class="overview-jump-icon">SC</span>
            <span class="overview-jump-label">剧本画布</span>
            <span class="overview-jump-sub">章节与大场景</span>
          </a>
          <a class="overview-jump-item" href="?page=materials">
            <span class="overview-jump-icon">MT</span>
            <span class="overview-jump-label">素材库</span>
            <span class="overview-jump-sub">人物、服装、场景素材</span>
          </a>
          <a class="overview-jump-item" href="?page=characters">
            <span class="overview-jump-icon">CH</span>
            <span class="overview-jump-label">人物库</span>
            <span class="overview-jump-sub">人物与形象变体</span>
          </a>
          <a class="overview-jump-item" href="?page=workflows">
            <span class="overview-jump-icon">WF</span>
            <span class="overview-jump-label">工作流</span>
            <span class="overview-jump-sub">ComfyUI 工作流</span>
          </a>
          <a class="overview-jump-item" href="?page=batch&project=${escapeHtml(projectId)}">
            <span class="overview-jump-icon">BG</span>
            <span class="overview-jump-label">批量跑图</span>
            <span class="overview-jump-sub">提交生成任务</span>
          </a>
          <a class="overview-jump-item" href="?page=review&project=${escapeHtml(projectId)}">
            <span class="overview-jump-icon">RV</span>
            <span class="overview-jump-label">项目审片</span>
            <span class="overview-jump-sub">采用生成图片</span>
          </a>
        </div>
      </section>
    `;
  }

  async function renderProductionOverview(project) {
    const page = document.querySelector(".page-scroll");
    if (!page) return;
    page.classList.add("overview-dashboard-page");
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

    page.insertAdjacentHTML(
      "beforeend",
      `<section class="panel overview-loading-panel"><div class="panel-body" style="padding:24px;color:#7d8698;font-size:11px">正在读取项目概览…</div></section>`
    );

    let payload;
    try {
      payload = await request(API.projectOverview(project.id));
    } catch (error) {
      const loading = page.querySelector(".overview-loading-panel");
      if (loading) loading.remove();
      page.insertAdjacentHTML(
        "beforeend",
        `<section class="production-empty-state project-overview-empty">
          <span class="production-empty-icon">!</span>
          <h2>概览加载失败</h2>
          <p>${escapeHtml(error.message)}</p>
          <button class="btn soft" type="button" data-api-action="retry-overview">重试</button>
        </section>`
      );
      return;
    }

    const loading = page.querySelector(".overview-loading-panel");
    if (loading) loading.remove();

    const overviewProject = payload.project || project;
    const stats = payload.stats || {};
    const blockers = Array.isArray(payload.blockers) ? payload.blockers : [];
    const updated = formatProjectDate(overviewProject.updated_at || project.updated_at);
    const description = (overviewProject.description || project.description || "").trim();
    const chapterCount = Number(stats.chapter_count || 0);

    if (title) title.textContent = overviewProject.name || project.name;
    if (subtitle) subtitle.textContent = `更新于 ${updated}`;

    page.insertAdjacentHTML(
      "beforeend",
      `
        <section class="panel overview-summary-panel">
          <div class="panel-body overview-summary-body">
            <div class="overview-summary-mark">${escapeHtml((overviewProject.name || project.name || "?").slice(0, 1).toUpperCase())}</div>
            <div class="overview-summary-copy">
              <div class="panel-title">${escapeHtml(overviewProject.name || project.name)}</div>
              <div class="overview-summary-description">${
                description ? escapeHtml(description) : "暂无项目描述"
              }</div>
              <div class="overview-summary-updated">更新于 ${escapeHtml(updated)}</div>
            </div>
            <div class="overview-summary-actions">
              <button class="btn soft" type="button" data-api-action="edit-project" data-project-id="${escapeHtml(project.id)}" data-project-name="${escapeHtml(overviewProject.name || project.name)}" data-project-description="${escapeHtml(overviewProject.description || project.description || "")}">编辑信息</button>
              <a class="btn primary" href="?page=story-canvas&project=${escapeHtml(project.id)}">打开剧本画布</a>
            </div>
          </div>
        </section>
      `
    );

    page.insertAdjacentHTML(
      "beforeend",
      `<div class="grid cols-3 overview-stats-grid">
        ${overviewStatCard("章节数", stats.chapter_count || 0, "剧本结构顶层")}
        ${overviewStatCard("大场景数", stats.large_scene_count || 0, "章节下的场景段")}
        ${overviewStatCard("小场景数", stats.small_scene_count || 0, "大场景中的子场景")}
        ${overviewStatCard("场景页数", stats.shot_page_count || 0, "分镜与镜头页")}
        ${overviewStatCard("关联素材", stats.material_count || 0, "已绑定到场景的素材")}
        ${overviewStatCard("关联人物", stats.character_count || 0, "项目使用的人物")}
      </div>`
    );

    if (blockers.length) {
      page.insertAdjacentHTML("beforeend", overviewBlockersList(blockers));
    }

    page.insertAdjacentHTML("beforeend", overviewJumpEntries(project.id));

    if (!chapterCount) {
      page.insertAdjacentHTML(
        "beforeend",
        `
          <section class="production-empty-state project-overview-empty">
            <span class="production-empty-icon">${escapeHtml((overviewProject.name || project.name || "?").slice(0, 1).toUpperCase())}</span>
            <h2>项目内容为空</h2>
            <p>该项目还没有章节。从剧本画布开始创建第一个章节。</p>
            <a class="btn primary" href="?page=story-canvas&project=${escapeHtml(project.id)}">创建章节</a>
            <small>创建于 ${escapeHtml(formatProjectDate(overviewProject.created_at || project.created_at))}</small>
          </section>
        `
      );
    }
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
    selectedShotPageId: null,
    shotPageDetail: null, // 当前选中页的详情缓存(含 characterBinding/promptDraft/precheck)
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
          data-context-menu="small-scene"
          data-name="${escapeHtml(smallScene.name)}"
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
            ${chapters.map((chapter) => `
              <li class="story-tree-branch">
                <button
                  class="story-tree-row story-tree-chapter"
                  type="button"
                  data-story-tree-node="chapter"
                  data-context-menu="chapter"
                  data-chapter-id="${escapeHtml(chapter.id)}"
                  data-name="${escapeHtml(chapter.name)}"
                  data-large-scene-count="${chapter.large_scenes.length}"
                >
                  <span class="story-tree-chevron">⌄</span>
                  <span class="story-tree-icon chapter">CH</span>
                  <span class="story-tree-name">${escapeHtml(chapter.name)}</span>
                  <span class="story-tree-count">${chapter.large_scenes.length}</span>
                </button>
                <ul
                  class="story-tree-children story-large-scene-drop-zone"
                  data-drop-zone
                  data-drop-axis="vertical"
                  data-chapter-id="${escapeHtml(chapter.id)}"
                >
                  ${chapter.large_scenes.map((largeScene) => `
                    <li
                      class="story-tree-branch"
                      data-large-scene-drag-item
                      data-large-scene-id="${escapeHtml(largeScene.id)}"
                      data-chapter-id="${escapeHtml(chapter.id)}"
                    >
                      <button
                        class="story-tree-row story-tree-large-scene"
                        type="button"
                        data-story-tree-node="large-scene"
                        data-context-menu="large-scene"
                        data-large-scene-drag-handle
                        data-large-scene-id="${escapeHtml(largeScene.id)}"
                        data-chapter-id="${escapeHtml(chapter.id)}"
                        data-name="${escapeHtml(largeScene.name)}"
                        title="拖动调整顺序或移动到其他章节"
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
        data-large-scene-drag-item
        data-large-scene-id="${escapeHtml(largeScene.id)}"
        data-chapter-id="${escapeHtml(largeScene.chapter_id)}"
      >
        <header
          class="story-wrapper-heading large-scene-block"
          data-context-menu="large-scene"
          data-large-scene-drag-handle
          data-large-scene-id="${escapeHtml(largeScene.id)}"
          data-chapter-id="${escapeHtml(largeScene.chapter_id)}"
          data-name="${escapeHtml(largeScene.name)}"
          data-sort-order="${escapeHtml(largeScene.sort_order)}"
          data-scene-type="${escapeHtml(largeScene.scene_type || "content")}"
          title="拖动调整顺序或移动到其他章节"
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
        <div
          class="story-large-scene-grid"
          data-drop-zone
          data-drop-axis="grid"
          data-chapter-id="${escapeHtml(chapter.id)}"
        >
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
          <button class="tool" type="button" data-api-action="manage-branches" data-project-id="${escapeHtml(project.id)}" title="分支管理">分支管理</button>
          <span class="story-operation-recent" id="story-operation-recent">最近操作：无</span>
          <button class="tool" type="button" data-api-action="undo-operation" data-project-id="${escapeHtml(project.id)}" title="撤销上一步操作" disabled>撤销</button>
          <button class="tool" type="button" data-api-action="redo-operation" data-project-id="${escapeHtml(project.id)}" title="重做已撤销操作" disabled>重做</button>
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
    const selected = storyWorkspaceState.selectedShotPageId === page.id;
    const status = shotPageStatusBadge(page, workspace);
    return `
      <article class="small-scene-page-card ${selected ? "selected" : ""}" data-scene-page-id="${escapeHtml(page.id)}" data-shot-page-select="${escapeHtml(page.id)}">
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
        ${status}
      </article>
    `;
  }

  function shotPageStatusBadge(page, workspace) {
    // 轻量状态徽章：仅基于本地可见字段判断"未完成/可编译"两档。
    // 真正的"可跑图"由详情区完成检查(含工作流检查)刷新。
    const hasName = !!(page.name && page.name.trim());
    const hasPrompt = !!(page.prompt_text && page.prompt_text.trim());
    const hasMaterial = (workspace.mappings || []).some(
      (m) => m.scene_page_id === page.id,
    );
    const complete = hasName && hasPrompt && hasMaterial;
    const label = complete ? "可编译" : "未完成";
    const cls = complete ? "ready" : "incomplete";
    return `<span class="shot-page-status-badge ${cls}" data-shot-page-status="${escapeHtml(page.id)}">${escapeHtml(label)}</span>`;
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
            <section class="shot-page-detail-section" id="shot-page-detail-section" hidden>
              <div class="shot-page-detail-loading">正在加载页面详情…</div>
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
      const selectPage = event.target.closest("[data-shot-page-select]");
      if (selectPage && !event.target.closest("[data-small-scene-page-action]")) {
        // 点击页面卡片任意非按钮区域 → 选中该页并展开详情
        const pageId = selectPage.dataset.shotPageSelect;
        await selectShotPage(pageId);
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

  // ==================== 场景页详情区(需求 §4) ====================

  async function selectShotPage(pageId) {
    const workspace = storyWorkspaceState.smallSceneWorkspace;
    if (!workspace) return;
    // 切换页前若有未保存提示词，提示用户
    const cur = storyWorkspaceState.shotPageDetail;
    if (cur && cur.promptDirty && storyWorkspaceState.selectedShotPageId !== pageId) {
      const confirmed = await confirmDialog({
        title: "放弃未保存的提示词？",
        message: "当前页面提示词已修改但未保存，切换页面将丢失修改。确定切换？",
        confirmText: "切换并放弃",
        danger: true,
      });
      if (!confirmed) return;
      cur.promptDirty = false;
    }
    const page = (workspace.pages || []).find((p) => p.id === pageId);
    if (!page) return;
    storyWorkspaceState.selectedShotPageId = pageId;
    // 刷新卡片选中态
    document.querySelectorAll(".small-scene-page-card").forEach((card) => {
      card.classList.toggle("selected", card.dataset.scenePageId === pageId);
    });
    const section = document.getElementById("shot-page-detail-section");
    if (!section) return;
    section.hidden = false;
    section.innerHTML = '<div class="shot-page-detail-loading">正在加载页面详情…</div>';
    section.scrollIntoView({ behavior: "smooth", block: "nearest" });
    const detail = await loadShotPageDetail(page);
    storyWorkspaceState.shotPageDetail = detail;
    // 加载项目默认工作流状态(需求 §4.5：完成状态区分"未完成/可编译/可跑图")
    const projectId = storyWorkspaceState.project?.id;
    if (projectId) {
      try {
        const wfRes = await requestOptional(`/api/projects/${projectId}/default-workflow`);
        if (wfRes && wfRes.workflow) {
          detail.projectWorkflow = { exists: true, workflow: wfRes.workflow };
        } else {
          detail.projectWorkflow = { exists: false };
        }
      } catch (e) {
        detail.projectWorkflow = { exists: false };
      }
    }
    section.innerHTML = renderShotPageDetail(page, workspace, detail);
    bindShotPageDetailEvents(section, page, workspace);
  }

  async function loadShotPageDetail(page) {
    const detail = {
      binding: null,
      characters: [],
      variants: [],
      specValues: [],
      specs: [],
      promptDraft: {
        prompt_text: page.prompt_text || "",
        negative_prompt: page.negative_prompt || "",
      },
      promptDirty: false,
      promptEditing: false,
      precheck: null,
      projectWorkflow: null, // null=未检查; {exists:false}; {exists:true, ...}
    };
    // 并行加载:人物绑定、人物列表、公共规格定义
    const [bindingRes, charactersRes, specsRes] = await Promise.all([
      requestOptional(API.shotPageCharacter(page.id)).then(
        (res) => res,
        () => null,
      ),
      request(`${API.characters}?limit=200&offset=0&sort=name_asc`).then(
        (res) => res,
        () => ({ items: [], total: 0 }),
      ),
      requestOptional(API.specs).then((res) => res, () => ({ items: [] })),
    ]);
    detail.binding = bindingRes?.reference || null;
    detail.characters = charactersRes?.items || [];
    detail.specs = specsRes?.items || [];
    // 如果已有绑定，预加载形象与规格值
    if (detail.binding) {
      try {
        const variantsRes = await request(
          `${API.characterVariants(detail.binding.character_id)}?include_archived=false`,
        );
        detail.variants = variantsRes?.items || [];
      } catch (e) { detail.variants = []; }
      if (detail.binding.variant_id) {
        try {
          const svRes = await request(
            API.characterVariantSpecValues(detail.binding.variant_id),
          );
          detail.specValues = svRes?.items || [];
        } catch (e) { detail.specValues = []; }
      }
    }
    return detail;
  }

  function renderShotPageDetail(page, workspace, detail) {
    return `
      <div class="shot-page-detail" data-shot-page-detail="${escapeHtml(page.id)}">
        <header class="shot-page-detail-header">
          <div>
            <small>P${String(page.sort_order || 0).padStart(2, "0")} · 页面详情</small>
            <strong>${escapeHtml(page.name)}</strong>
            ${page.description ? `<p>${escapeHtml(page.description)}</p>` : '<p class="muted">尚未填写画面描述</p>'}
          </div>
          <button class="btn small" type="button" data-shot-page-action="close">收起</button>
        </header>
        <div class="shot-page-detail-body">
          ${renderShotPageCharacterSection(page, detail)}
          ${renderShotPagePromptSection(page, detail)}
          ${renderShotPageMaterialSection(page, workspace)}
          ${renderShotPageCompletionSection(page, detail)}
        </div>
      </div>
    `;
  }

  // ── 4.2 主要人物配置 ──────────────────────────────────────
  function renderShotPageCharacterSection(page, detail) {
    const b = detail.binding;
    if (b && !storyWorkspaceState._shotPageEditingCharacter) {
      // 只读摘要
      const specLabel = b.spec_id
        ? (b.spec_name || b.spec_type || "未命名规格")
        : "未选择规格";
      return `
        <section class="shot-page-detail-block" data-shot-page-block="character">
          <div class="shot-page-block-heading">
            <div><span>02</span><div><strong>主要人物</strong><small>当前页面绑定的角色与形象</small></div></div>
            <div class="shot-page-block-actions">
              <button class="btn small soft" type="button" data-shot-page-action="edit-character">修改</button>
              <button class="btn small danger" type="button" data-shot-page-action="unbind-character">解除绑定</button>
            </div>
          </div>
          <div class="shot-page-character-summary">
            <div><label>人物</label><strong>${escapeHtml(b.character_name || "—")}</strong></div>
            <div><label>形象</label><strong>${escapeHtml(b.variant_name || "—")}</strong></div>
            <div><label>规格</label><strong>${escapeHtml(specLabel)}</strong></div>
          </div>
        </section>
      `;
    }
    // 编辑表单(三级联动)
    const characters = detail.characters || [];
    const variants = detail.variants || [];
    const specValues = detail.specValues || [];
    const specs = detail.specs || [];
    // 编辑态：从 detail 暂存的草稿读取，否则从 binding 初始化
    const draft = storyWorkspaceState._shotPageCharacterDraft || {
      character_id: b?.character_id || "",
      variant_id: b?.variant_id || "",
      spec_id: b?.spec_id || "",
    };
    const variantOptions = variants.map((v) =>
      `<option value="${escapeHtml(v.id)}" ${v.id === draft.variant_id ? "selected" : ""}>${escapeHtml(v.name)}</option>`
    ).join("");
    // 规格只显示已填写(prompt 非空)的规格
    const filledSpecIds = new Set(
      specValues.filter((sv) => sv.prompt && String(sv.prompt).trim()).map((sv) => sv.spec_id)
    );
    const specOptions = specs
      .filter((s) => filledSpecIds.has(s.id))
      .map((s) => {
        const label = s.custom_label || s.spec_type || s.id;
        return `<option value="${escapeHtml(s.id)}" ${s.id === draft.spec_id ? "selected" : ""}>${escapeHtml(label)}</option>`;
      })
      .join("");
    const hasVariants = variants.length > 0;
    const hasFilledSpecs = filledSpecIds.size > 0;
    return `
      <section class="shot-page-detail-block" data-shot-page-block="character">
        <div class="shot-page-block-heading">
          <div><span>02</span><div><strong>主要人物</strong><small>三级联动：人物 → 形象 → 规格</small></div></div>
          ${b ? `<div class="shot-page-block-actions"><button class="btn small" type="button" data-shot-page-action="cancel-character">取消</button></div>` : ""}
        </div>
        <form class="shot-page-character-form" data-shot-page-character-form>
          <label class="label">人物</label>
          <select class="modal-input" name="character_id" data-shot-page-cascade="character">
            <option value="">请选择人物</option>
            ${characters.map((c) =>
              `<option value="${escapeHtml(c.id)}" ${c.id === draft.character_id ? "selected" : ""}>${escapeHtml(c.name)}</option>`
            ).join("")}
          </select>
          <label class="label">形象</label>
          <select class="modal-input" name="variant_id" data-shot-page-cascade="variant" ${hasVariants ? "" : "disabled"}>
            <option value="">请选择形象</option>
            ${variantOptions}
          </select>
          ${!hasVariants && draft.character_id ? '<p class="shot-page-hint">该人物没有可用形象。</p>' : ""}
          <label class="label">规格</label>
          <select class="modal-input" name="spec_id" data-shot-page-cascade="spec" ${hasFilledSpecs ? "" : "disabled"}>
            <option value="">请选择规格</option>
            ${specOptions}
          </select>
          ${draft.variant_id && !hasFilledSpecs ? '<p class="shot-page-hint">该形象尚未填写任何规格值。</p>' : ""}
          <div class="modal-error shot-page-character-error" role="alert"></div>
          <div class="shot-page-form-actions">
            <button class="btn primary" type="submit">保存人物配置</button>
            ${b ? '<button class="btn" type="button" data-shot-page-action="cancel-character">取消</button>' : ""}
          </div>
        </form>
      </section>
    `;
  }

  // ── 4.3 页级提示词 ──────────────────────────────────────
  function renderShotPagePromptSection(page, detail) {
    const draft = detail.promptDraft;
    const editing = detail.promptEditing;
    if (editing) {
      return `
        <section class="shot-page-detail-block" data-shot-page-block="prompt">
          <div class="shot-page-block-heading">
            <div><span>03</span><div><strong>页级提示词</strong><small>只保存当前页专属内容；人物与素材由绑定解析</small></div></div>
            <div class="shot-page-block-actions">
              <button class="btn small" type="button" data-shot-page-action="cancel-prompt">取消</button>
            </div>
          </div>
          <form class="shot-page-prompt-form" data-shot-page-prompt-form>
            <label class="label" for="shot-page-prompt-positive">页级正向提示词</label>
            <textarea id="shot-page-prompt-positive" class="modal-input shot-page-textarea" name="prompt_text" rows="6">${escapeHtml(draft.prompt_text || "")}</textarea>
            <label class="label" for="shot-page-prompt-negative">页级负向提示词</label>
            <textarea id="shot-page-prompt-negative" class="modal-input shot-page-textarea" name="negative_prompt" rows="4">${escapeHtml(draft.negative_prompt || "")}</textarea>
            <div class="modal-error shot-page-prompt-error" role="alert"></div>
            <div class="shot-page-form-actions">
              <button class="btn primary" type="submit">保存提示词</button>
              <button class="btn" type="button" data-shot-page-action="cancel-prompt">取消</button>
            </div>
          </form>
        </section>
      `;
    }
    // 只读完整展示
    const pos = (draft.prompt_text || "").trim();
    const neg = (draft.negative_prompt || "").trim();
    return `
      <section class="shot-page-detail-block" data-shot-page-block="prompt">
        <div class="shot-page-block-heading">
          <div><span>03</span><div><strong>页级提示词</strong><small>完整展示；点击编辑修改</small></div></div>
          <div class="shot-page-block-actions">
            <button class="btn small soft" type="button" data-shot-page-action="edit-prompt">编辑</button>
          </div>
        </div>
        <div class="shot-page-prompt-readonly">
          <label class="label">页级正向提示词</label>
          <pre class="shot-page-prompt-text ${pos ? "" : "muted"}">${escapeHtml(pos || "尚未填写")}</pre>
          <label class="label">页级负向提示词</label>
          <pre class="shot-page-prompt-text ${neg ? "" : "muted"}">${escapeHtml(neg || "尚未填写")}</pre>
        </div>
      </section>
    `;
  }

  // ── 4.4 已关联素材及其页映射 ────────────────────────────
  function renderShotPageMaterialSection(page, workspace) {
    const mappings = (workspace.mappings || []).filter((m) => m.scene_page_id === page.id);
    const resources = workspace.resources || [];
    const rows = mappings.map((m) => {
      const res = resources.find((r) => r.material_id === m.material_id);
      const pageLabel = m.material_page_name || (m.material_page_id || "").slice(0, 8);
      const typeLabel = storyResourceTypeLabels[m.material_type] || m.material_type;
      return `
        <div class="shot-page-material-row type-${escapeHtml(m.material_type)}">
          <span class="shot-page-material-type">${escapeHtml(typeLabel)}</span>
          <strong>${escapeHtml(res?.name || m.material_name || "素材")}</strong>
          <small>素材页：${escapeHtml(pageLabel)}</small>
          <button class="btn small danger" type="button" data-shot-page-action="unmap-material" data-material-type="${escapeHtml(m.material_type)}">解除</button>
        </div>
      `;
    }).join("");
    return `
      <section class="shot-page-detail-block" data-shot-page-block="material">
        <div class="shot-page-block-heading">
          <div><span>04</span><div><strong>已关联素材</strong><small>该页绑定的素材页映射；下方素材页映射区可管理全部</small></div></div>
          <div class="shot-page-block-actions">
            <button class="btn small soft" type="button" data-shot-page-action="scroll-to-resources">管理映射</button>
          </div>
        </div>
        <div class="shot-page-material-list">
          ${rows || '<p class="muted">该页尚未关联任何素材页。</p>'}
        </div>
      </section>
    `;
  }

  // ── 4.4 / 4.5 完成状态与默认工作流 ──────────────────────
  function renderShotPageCompletionSection(page, detail) {
    const pre = detail.precheck;
    const wf = detail.projectWorkflow;
    const checks = computeShotPageChecks(page, detail);
    const blocking = checks.filter((c) => !c.passed);
    const wfMissing = wf && wf.exists === false;
    const statusLabel = blocking.length
      ? "未完成"
      : (wfMissing ? "可编译" : (wf && wf.exists ? "可跑图" : "可编译"));
    const statusCls = blocking.length ? "incomplete" : "ready";
    return `
      <section class="shot-page-detail-block" data-shot-page-block="completion">
        <div class="shot-page-block-heading">
          <div><span>05</span><div><strong>完成状态</strong><small>检查页面是否可编译或跑图</small></div></div>
          <div class="shot-page-block-actions">
            <span class="shot-page-completion-status ${statusCls}">${escapeHtml(statusLabel)}</span>
            <button class="btn small soft" type="button" data-shot-page-action="run-precheck">重新检查</button>
          </div>
        </div>
        <ul class="shot-page-check-list">
          ${checks.map((c) => `
            <li class="${c.passed ? "passed" : "failed"}">
              <span class="shot-page-check-icon">${c.passed ? "✓" : "✕"}</span>
              <span class="shot-page-check-label">${escapeHtml(c.label)}</span>
              ${!c.passed && c.action ? `<button class="btn small soft" type="button" data-shot-page-action="${escapeHtml(c.action)}">${escapeHtml(c.actionLabel || "前往处理")}</button>` : ""}
            </li>
          `).join("")}
        </ul>
        ${wfMissing ? `
          <div class="shot-page-workflow-notice">
            <strong>项目尚未设置默认工作流</strong>
            <p>页面内容已完整，但当前项目没有默认工作流，暂不能跑图。</p>
            <button class="btn primary" type="button" data-shot-page-action="goto-workflow">前往工作流</button>
          </div>
        ` : ""}
        ${pre ? `<div class="shot-page-precheck-summary">${renderShotPagePrecheckSummary(pre)}</div>` : ""}
      </section>
    `;
  }

  function computeShotPageChecks(page, detail) {
    const b = detail.binding;
    const hasName = !!(page.name && page.name.trim());
    const hasPrompt = !!(detail.promptDraft && (detail.promptDraft.prompt_text || "").trim());
    const hasCharacter = !!(b && b.character_id);
    const hasVariant = !!(b && b.variant_id);
    const hasSpec = !!(b && b.spec_id);
    const workspace = storyWorkspaceState.smallSceneWorkspace;
    const hasMaterial = (workspace?.mappings || []).some((m) => m.scene_page_id === page.id);
    const wf = detail.projectWorkflow;
    const hasWorkflow = !!(wf && wf.exists);
    return [
      { key: "name", label: "页面名称已填写", passed: hasName, action: "focus-name", actionLabel: "编辑名称" },
      { key: "prompt", label: "页级正向提示词已填写", passed: hasPrompt, action: "edit-prompt", actionLabel: "编辑提示词" },
      { key: "character", label: "已绑定主要人物", passed: hasCharacter, action: "edit-character", actionLabel: "绑定人物" },
      { key: "variant", label: "已选择人物形象", passed: hasVariant, action: "edit-character", actionLabel: "选择形象" },
      { key: "spec", label: "已选择公共规格", passed: hasSpec, action: "edit-character", actionLabel: "选择规格" },
      { key: "material", label: "至少关联一个素材页", passed: hasMaterial, action: "scroll-to-resources", actionLabel: "关联素材" },
      { key: "workflow", label: "项目默认工作流存在且可用", passed: hasWorkflow, action: "goto-workflow", actionLabel: "前往工作流" },
    ];
  }

  function renderShotPagePrecheckSummary(pre) {
    const errors = pre.errors || pre.blockers || [];
    const warnings = pre.warnings || [];
    if (!errors.length && !warnings.length) return '<p class="muted">预检查无阻塞项。</p>';
    const items = [
      ...errors.map((e) => `<li class="failed"><span>✕</span>${escapeHtml(e.message || e.type || "阻塞错误")}</li>`),
      ...warnings.map((w) => `<li class="warn"><span>!</span>${escapeHtml(w.message || w.type || "警告")}</li>`),
    ].join("");
    return `<ul class="shot-page-precheck-list">${items}</ul>`;
  }

  function bindShotPageDetailEvents(section, page, workspace) {
    section.addEventListener("click", async (event) => {
      const btn = event.target.closest("[data-shot-page-action]");
      if (!btn) return;
      const action = btn.dataset.shotPageAction;
      try {
        if (action === "close") {
          storyWorkspaceState.selectedShotPageId = null;
          storyWorkspaceState.shotPageDetail = null;
          storyWorkspaceState._shotPageEditingCharacter = false;
          storyWorkspaceState._shotPageCharacterDraft = null;
          section.hidden = true;
          section.innerHTML = "";
          document.querySelectorAll(".small-scene-page-card").forEach((c) => c.classList.remove("selected"));
          return;
        }
        if (action === "edit-character") {
          storyWorkspaceState._shotPageEditingCharacter = true;
          storyWorkspaceState._shotPageCharacterDraft = null;
          await rerenderShotPageDetail(page, workspace);
          return;
        }
        if (action === "cancel-character") {
          storyWorkspaceState._shotPageEditingCharacter = false;
          storyWorkspaceState._shotPageCharacterDraft = null;
          await rerenderShotPageDetail(page, workspace);
          return;
        }
        if (action === "unbind-character") {
          const confirmed = await confirmDialog({
            title: "解除人物绑定",
            message: `确定解除「${page.name}」的人物绑定吗？人物库与规格数据不会被删除。`,
            confirmText: "解除绑定",
            danger: true,
          });
          if (!confirmed) return;
          await request(API.shotPageCharacter(page.id), { method: "DELETE" });
          storyWorkspaceState._shotPageEditingCharacter = false;
          storyWorkspaceState._shotPageCharacterDraft = null;
          await reloadShotPageDetailBinding(page);
          if (typeof showToast === "function") showToast("已解除人物绑定");
          return;
        }
        if (action === "edit-prompt") {
          storyWorkspaceState.shotPageDetail.promptEditing = true;
          await rerenderShotPageDetail(page, workspace);
          return;
        }
        if (action === "cancel-prompt") {
          if (storyWorkspaceState.shotPageDetail.promptDirty) {
            const confirmed = await confirmDialog({
              title: "放弃未保存的提示词？",
              message: "当前提示词已修改但未保存，确定放弃？",
              confirmText: "放弃",
              danger: true,
            });
            if (!confirmed) return;
          }
          storyWorkspaceState.shotPageDetail.promptEditing = false;
          storyWorkspaceState.shotPageDetail.promptDirty = false;
          // 恢复草稿为已保存值
          const ws = storyWorkspaceState.smallSceneWorkspace;
          const fresh = (ws.pages || []).find((p) => p.id === page.id);
          storyWorkspaceState.shotPageDetail.promptDraft = {
            prompt_text: fresh?.prompt_text || "",
            negative_prompt: fresh?.negative_prompt || "",
          };
          await rerenderShotPageDetail(page, workspace);
          return;
        }
        if (action === "run-precheck") {
          await runShotPagePrecheck(page);
          return;
        }
        if (action === "goto-workflow") {
          const params = new URLSearchParams(window.location.search);
          const projectId = storyWorkspaceState.project?.id;
          // 跳转到工作流列表页，保留 project 参数以便回到当前项目
          const next = new URLSearchParams();
          next.set("page", "workflows");
          if (projectId) next.set("project", String(projectId));
          next.set("from", "shotPage");
          if (params.get("smallScene")) next.set("smallScene", params.get("smallScene"));
          next.set("shotPage", page.id);
          window.location.search = `?${next.toString()}`;
          return;
        }
        if (action === "scroll-to-resources") {
          document.querySelector(".small-scene-resources-section")
            ?.scrollIntoView({ behavior: "smooth", block: "start" });
          return;
        }
        if (action === "focus-name") {
          await selectShotPage(page.id);
          // 触发编辑名称对话框
          const ws = storyWorkspaceState.smallSceneWorkspace;
          openStoryEditorDialog({
            title: "编辑场景页",
            description: `正在编辑 P${String(page.sort_order).padStart(2, "0")}`,
            nameLabel: "页面名称",
            nameValue: page.name || "",
            descriptionValue: page.description || "",
            showDescription: true,
            submitText: "保存修改",
            onSubmit: async (values) => {
              await request(`/api/small-scene-pages/${page.id}`, {
                method: "PATCH",
                body: JSON.stringify(values),
              });
              await refreshSmallSceneWorkspace();
              // 刷新后重新选中
              await selectShotPage(page.id);
            },
          });
          return;
        }
        if (action === "unmap-material") {
          const mt = btn.dataset.materialType;
          await request(API.scenePageMapping(page.id, mt), {
            method: "PUT",
            body: JSON.stringify({ material_page_id: null }),
          });
          await refreshSmallSceneWorkspace();
          await selectShotPage(page.id);
          return;
        }
      } catch (error) {
        if (typeof showToast === "function") showToast(error.message || "操作失败");
      }
    });

    // 三级联动
    const cascade = section.querySelector("[data-shot-page-character-form]");
    if (cascade) {
      cascade.addEventListener("change", async (event) => {
        const sel = event.target;
        if (!sel.dataset.shotPageCascade) return;
        const level = sel.dataset.shotPageCascade;
        const draft = {
          character_id: cascade.elements.character_id.value,
          variant_id: cascade.elements.variant_id.value,
          spec_id: cascade.elements.spec_id.value,
        };
        if (level === "character") {
          // 切换人物 → 清空形象与规格
          draft.variant_id = "";
          draft.spec_id = "";
          storyWorkspaceState._shotPageCharacterDraft = draft;
          if (draft.character_id) {
            try {
              const res = await request(`${API.characterVariants(draft.character_id)}?include_archived=false`);
              storyWorkspaceState.shotPageDetail.variants = res?.items || [];
            } catch (e) { storyWorkspaceState.shotPageDetail.variants = []; }
            storyWorkspaceState.shotPageDetail.specValues = [];
          } else {
            storyWorkspaceState.shotPageDetail.variants = [];
            storyWorkspaceState.shotPageDetail.specValues = [];
          }
          await rerenderShotPageDetail(page, workspace);
          return;
        }
        if (level === "variant") {
          // 切换形象 → 清空规格
          draft.spec_id = "";
          storyWorkspaceState._shotPageCharacterDraft = draft;
          if (draft.variant_id) {
            try {
              const res = await request(API.characterVariantSpecValues(draft.variant_id));
              storyWorkspaceState.shotPageDetail.specValues = res?.items || [];
            } catch (e) { storyWorkspaceState.shotPageDetail.specValues = []; }
          } else {
            storyWorkspaceState.shotPageDetail.specValues = [];
          }
          await rerenderShotPageDetail(page, workspace);
          return;
        }
        if (level === "spec") {
          storyWorkspaceState._shotPageCharacterDraft = draft;
        }
      });
      cascade.addEventListener("submit", async (event) => {
        event.preventDefault();
        const errorEl = cascade.querySelector(".shot-page-character-error");
        const submit = cascade.querySelector('[type="submit"]');
        const draft = {
          character_id: cascade.elements.character_id.value,
          variant_id: cascade.elements.variant_id.value,
          spec_id: cascade.elements.spec_id.value,
        };
        if (!draft.character_id || !draft.variant_id) {
          if (errorEl) errorEl.textContent = "请选择人物与形象。";
          return;
        }
        submit.disabled = true;
        try {
          await request(API.shotPageCharacter(page.id), {
            method: "PUT",
            body: JSON.stringify(draft),
          });
          storyWorkspaceState._shotPageEditingCharacter = false;
          storyWorkspaceState._shotPageCharacterDraft = null;
          await reloadShotPageDetailBinding(page);
          if (typeof showToast === "function") showToast("人物配置已保存");
        } catch (error) {
          if (errorEl) errorEl.textContent = error.message || "保存失败";
        } finally {
          submit.disabled = false;
        }
      });
    }

    // 提示词表单
    const promptForm = section.querySelector("[data-shot-page-prompt-form]");
    if (promptForm) {
      const positive = promptForm.elements.prompt_text;
      const negative = promptForm.elements.negative_prompt;
      const checkDirty = () => {
        const d = storyWorkspaceState.shotPageDetail.promptDraft;
        const dirty = (positive.value !== (d.prompt_text || "")) || (negative.value !== (d.negative_prompt || ""));
        storyWorkspaceState.shotPageDetail.promptDirty = dirty;
      };
      positive.addEventListener("input", checkDirty);
      negative.addEventListener("input", checkDirty);
      promptForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const errorEl = promptForm.querySelector(".shot-page-prompt-error");
        const submit = promptForm.querySelector('[type="submit"]');
        const payload = {
          prompt_text: positive.value,
          negative_prompt: negative.value,
        };
        submit.disabled = true;
        try {
          await request(`/api/small-scene-pages/${page.id}`, {
            method: "PATCH",
            body: JSON.stringify(payload),
          });
          // 同步 workspace 中的 page 数据
          const ws = storyWorkspaceState.smallSceneWorkspace;
          const idx = (ws.pages || []).findIndex((p) => p.id === page.id);
          if (idx >= 0) {
            ws.pages[idx].prompt_text = payload.prompt_text;
            ws.pages[idx].negative_prompt = payload.negative_prompt;
            page.prompt_text = payload.prompt_text;
            page.negative_prompt = payload.negative_prompt;
          }
          storyWorkspaceState.shotPageDetail.promptDraft = payload;
          storyWorkspaceState.shotPageDetail.promptDirty = false;
          storyWorkspaceState.shotPageDetail.promptEditing = false;
          await rerenderShotPageDetail(page, ws);
          // 刷新页面卡片状态徽章
          await refreshPageStripStatus();
          if (typeof showToast === "function") showToast("提示词已保存");
        } catch (error) {
          if (errorEl) errorEl.textContent = error.message || "保存失败";
        } finally {
          submit.disabled = false;
        }
      });
    }
  }

  async function reloadShotPageDetailBinding(page) {
    const detail = storyWorkspaceState.shotPageDetail;
    try {
      const res = await requestOptional(API.shotPageCharacter(page.id));
      detail.binding = res?.reference || null;
      if (detail.binding) {
        const vRes = await request(`${API.characterVariants(detail.binding.character_id)}?include_archived=false`);
        detail.variants = vRes?.items || [];
        if (detail.binding.variant_id) {
          const svRes = await request(API.characterVariantSpecValues(detail.binding.variant_id));
          detail.specValues = svRes?.items || [];
        }
      }
    } catch (e) {
      detail.binding = null;
    }
    await rerenderShotPageDetail(page, storyWorkspaceState.smallSceneWorkspace);
    await refreshPageStripStatus();
  }

  async function rerenderShotPageDetail(page, workspace) {
    const section = document.getElementById("shot-page-detail-section");
    if (!section || section.hidden) return;
    const detail = storyWorkspaceState.shotPageDetail;
    section.innerHTML = renderShotPageDetail(page, workspace, detail);
    bindShotPageDetailEvents(section, page, workspace);
  }

  async function runShotPagePrecheck(page) {
    const detail = storyWorkspaceState.shotPageDetail;
    const section = document.getElementById("shot-page-detail-section");
    const statusEl = section?.querySelector(".shot-page-precheck-summary");
    if (statusEl) statusEl.innerHTML = '<p class="muted">正在执行预检查…</p>';
    const projectId = storyWorkspaceState.project?.id;
    try {
      const payload = await request(API.projectPrecheck(projectId), {
        method: "POST",
        body: JSON.stringify({ scope: "shot_pages", scope_id: page.id }),
      });
      detail.precheck = payload;
    } catch (error) {
      detail.precheck = { errors: [{ message: error.message || "预检查失败" }], warnings: [] };
    }
    // 同时检查项目默认工作流
    try {
      const wfRes = await requestOptional(`/api/projects/${projectId}/default-workflow`);
      detail.projectWorkflow = { exists: true, workflow: wfRes?.workflow };
    } catch (e) {
      detail.projectWorkflow = { exists: false };
    }
    await rerenderShotPageDetail(page, storyWorkspaceState.smallSceneWorkspace);
  }

  async function refreshPageStripStatus() {
    const workspace = storyWorkspaceState.smallSceneWorkspace;
    if (!workspace) return;
    document.querySelectorAll(".small-scene-page-card").forEach((card) => {
      const pageId = card.dataset.scenePageId;
      const page = (workspace.pages || []).find((p) => p.id === pageId);
      if (!page) return;
      const badge = card.querySelector(".shot-page-status-badge");
      if (!badge) return;
      const hasName = !!(page.name && page.name.trim());
      const hasPrompt = !!(page.prompt_text && page.prompt_text.trim());
      const hasMaterial = (workspace.mappings || []).some((m) => m.scene_page_id === pageId);
      const complete = hasName && hasPrompt && hasMaterial;
      badge.textContent = complete ? "可编译" : "未完成";
      badge.classList.toggle("ready", complete);
      badge.classList.toggle("incomplete", !complete);
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
    // 刷新后若仍选中某页，且该页仍存在，则重新打开详情区(保留未保存草稿)
    const selectedId = storyWorkspaceState.selectedShotPageId;
    const stillExists = selectedId && (payload.pages || []).some((p) => p.id === selectedId);
    if (stillExists && storyWorkspaceState.shotPageDetail) {
      const freshPage = (payload.pages || []).find((p) => p.id === selectedId);
      // 同步草稿为最新已保存值(若非编辑态)
      if (!storyWorkspaceState.shotPageDetail.promptEditing) {
        storyWorkspaceState.shotPageDetail.promptDraft = {
          prompt_text: freshPage.prompt_text || "",
          negative_prompt: freshPage.negative_prompt || "",
        };
      }
      // 重新检查项目默认工作流状态
      try {
        const wfRes = await requestOptional(`/api/projects/${project.id}/default-workflow`);
        storyWorkspaceState.shotPageDetail.projectWorkflow = { exists: true, workflow: wfRes?.workflow };
      } catch (e) {
        storyWorkspaceState.shotPageDetail.projectWorkflow = { exists: false };
      }
      await selectShotPage(selectedId);
    } else if (!stillExists) {
      storyWorkspaceState.selectedShotPageId = null;
      storyWorkspaceState.shotPageDetail = null;
    }
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
      actions.innerHTML = `
        <button class="btn" data-api-action="show-snapshots" data-project-id="${escapeHtml(project.id)}">版本历史</button>
        <button class="btn" data-api-action="run-precheck" data-project-id="${escapeHtml(project.id)}">预检查</button>
        <button class="btn primary" data-api-action="open-chapter-modal">新建章节</button>
      `;
    }
    const hierarchy = await loadStoryHierarchy(project.id);
    storyWorkspaceState.tree = hierarchy.chapters;
    storyWorkspaceState.smallSceneBackendAvailable = hierarchy.backendAvailable;
    page.insertAdjacentHTML(
      "beforeend",
      storyWorkspaceShell(project, hierarchy.chapters, hierarchy.backendAvailable)
    );
    bindStoryHierarchy(project.id);
    await refreshStoryOperationControls(project.id);
  }

  // ==================== 剧本分支管理 ====================

  // 收集项目中所有大场景和小场景，用于分支父级选择
  function collectProjectScenes() {
    const chapters = storyWorkspaceState.tree || [];
    const largeScenes = [];
    const smallScenes = [];
    chapters.forEach((chapter) => {
      (chapter.large_scenes || []).forEach((scene) => {
        largeScenes.push({ id: scene.id, name: scene.name, chapter_name: chapter.name });
        (scene.small_scenes || []).forEach((small) => {
          smallScenes.push({ id: small.id, name: small.name, large_scene_name: scene.name });
        });
      });
    });
    return { largeScenes, smallScenes };
  }

  function ensureBranchModal() {
    let modal = document.getElementById("branch-manage-modal");
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "branch-manage-modal";
    modal.className = "atelier-modal-backdrop";
    modal.hidden = true;
    modal.innerHTML = `
      <section class="atelier-modal size-lg" role="dialog" aria-modal="true" aria-labelledby="branch-manage-title">
        <header class="atelier-modal-head">
          <div>
            <h2 id="branch-manage-title">分支管理</h2>
            <p class="atelier-modal-sub">管理剧本分支及其覆盖项，按大场景和小场景分组。</p>
          </div>
          <button class="btn small" type="button" data-api-action="close-branch-modal">关闭</button>
        </header>
        <div class="atelier-modal-body" id="branch-modal-body">
          <div class="branch-modal-loading">正在加载分支…</div>
        </div>
      </section>
    `;
    document.body.appendChild(modal);
    modal.addEventListener("click", (event) => {
      if (event.target === modal) closeBranchModal();
    });
    return modal;
  }

  async function openBranchModal(projectId) {
    const modal = ensureBranchModal();
    modal.dataset.projectId = projectId;
    modal.hidden = false;
    requestAnimationFrame(() => modal.classList.add("show"));
    await refreshBranchList(projectId);
  }

  function closeBranchModal() {
    const modal = document.getElementById("branch-manage-modal");
    if (!modal) return;
    modal.classList.remove("show");
    window.setTimeout(() => {
      modal.hidden = true;
    }, 150);
  }

  async function refreshBranchList(projectId) {
    const body = document.getElementById("branch-modal-body");
    if (!body) return;
    body.innerHTML = '<div class="branch-modal-loading">正在加载分支…</div>';
    try {
      const scenes = collectProjectScenes();
      const largeSceneBranchResults = await Promise.all(
        scenes.largeScenes.map(async (scene) => {
          try {
            const payload = await request(API.branches("large-scenes", scene.id));
            return { parentType: "large-scenes", parent: scene, branches: payload.items || [] };
          } catch (error) {
            return { parentType: "large-scenes", parent: scene, branches: [], error: error.message };
          }
        })
      );
      const smallSceneBranchResults = await Promise.all(
        scenes.smallScenes.map(async (scene) => {
          try {
            const payload = await request(API.branches("small-scenes", scene.id));
            return { parentType: "small-scenes", parent: scene, branches: payload.items || [] };
          } catch (error) {
            return { parentType: "small-scenes", parent: scene, branches: [], error: error.message };
          }
        })
      );
      body.innerHTML = renderBranchModalContent(scenes, largeSceneBranchResults, smallSceneBranchResults);
    } catch (error) {
      body.innerHTML = `<div class="branch-modal-error">分支加载失败：${escapeHtml(error.message)}</div>`;
    }
  }

  function renderBranchModalContent(scenes, largeSceneGroups, smallSceneGroups) {
    const allSceneOptions = [
      ...scenes.largeScenes.map((s) => ({
        value: `large-scenes:${s.id}`,
        label: `大场景 · ${s.name}（${s.chapter_name}）`,
      })),
      ...scenes.smallScenes.map((s) => ({
        value: `small-scenes:${s.id}`,
        label: `小场景 · ${s.name}（${s.large_scene_name}）`,
      })),
    ];
    const totalBranches = [...largeSceneGroups, ...smallSceneGroups].reduce(
      (sum, g) => sum + g.branches.length, 0
    );
    return `
      <div class="branch-modal-section">
        <h3>新建分支</h3>
        <form id="create-branch-form" class="branch-create-form">
          <label class="label">父级场景</label>
          <select name="parent" class="modal-input" required>
            ${allSceneOptions.map((s) => `<option value="${escapeHtml(s.value)}">${escapeHtml(s.label)}</option>`).join("")}
          </select>
          <label class="label">分支名称</label>
          <input name="name" class="modal-input" maxlength="80" autocomplete="off" placeholder="例如：分支A" required />
          <label class="label">说明（可选）</label>
          <textarea name="description" class="modal-input" maxlength="500" rows="2" placeholder="这个分支用于处理什么变化"></textarea>
          <label class="label">条件（可选）</label>
          <input name="condition" class="modal-input" maxlength="500" autocomplete="off" placeholder="分支触发条件描述" />
          <label class="label">返回点（可选）</label>
          <input name="return_point" class="modal-input" maxlength="500" autocomplete="off" placeholder="例如：完成后返回主线第 5 页" />
          <div class="modal-error" id="create-branch-error" role="alert"></div>
          <button class="btn small primary" type="button" data-api-action="create-branch">创建分支</button>
        </form>
      </div>
      <div class="branch-modal-section">
        <h3>已有分支（${totalBranches}）</h3>
        ${totalBranches === 0 ? '<p class="branch-empty">还没有分支。在上方创建第一个分支。</p>' : ""}
        ${largeSceneGroups.filter((g) => g.branches.length).map(renderBranchGroup).join("")}
        ${smallSceneGroups.filter((g) => g.branches.length).map(renderBranchGroup).join("")}
      </div>
    `;
  }

  function renderBranchGroup(group) {
    return `
      <div class="branch-group">
        <div class="branch-group-head">
          <span class="branch-group-type">${group.parentType === "large-scenes" ? "大场景" : "小场景"}</span>
          <span class="branch-group-name">${escapeHtml(group.parent.name)}</span>
          <span class="branch-group-count">${group.branches.length} 个分支</span>
        </div>
        <div class="branch-group-list">
          ${group.branches.map((branch) => renderBranchCard(branch)).join("")}
        </div>
      </div>
    `;
  }

  function renderBranchCard(branch) {
    const isActive = branch.is_enabled !== false && branch.is_enabled !== 0;
    const condition = branch.condition_value || branch.condition || "";
    const description = branch.description || "";
    const returnPoint = branch.return_point || "";
    return `
      <div class="branch-card" data-branch-id="${escapeHtml(branch.id)}">
        <div class="branch-card-head">
          <strong>${escapeHtml(branch.name)}</strong>
          <span class="branch-card-status ${isActive ? "active" : "inactive"}">${isActive ? "启用" : "禁用"}</span>
        </div>
        <div class="branch-card-meta">
          ${description ? `<span>说明：${escapeHtml(description)}</span>` : ""}
          ${condition ? `<span>条件：${escapeHtml(condition)}</span>` : '<span class="muted">无条件</span>'}
          ${returnPoint ? `<span>返回点：${escapeHtml(returnPoint)}</span>` : ""}
        </div>
        <div class="branch-card-actions">
          <button class="btn small" type="button" data-api-action="edit-branch" data-branch-id="${escapeHtml(branch.id)}" data-branch-name="${escapeHtml(branch.name)}" data-branch-description="${escapeHtml(description)}" data-branch-condition="${escapeHtml(condition)}" data-branch-return-point="${escapeHtml(returnPoint)}" data-branch-active="${isActive ? "1" : "0"}">编辑</button>
          <button class="btn small soft" type="button" data-api-action="toggle-branch-active" data-branch-id="${escapeHtml(branch.id)}" data-branch-active="${isActive ? "1" : "0"}" data-branch-name="${escapeHtml(branch.name)}">${isActive ? "禁用" : "启用"}</button>
          <button class="btn small soft" type="button" data-api-action="add-branch-override" data-branch-id="${escapeHtml(branch.id)}" data-branch-name="${escapeHtml(branch.name)}">覆盖项</button>
          <button class="btn small danger-soft" type="button" data-api-action="delete-branch" data-branch-id="${escapeHtml(branch.id)}" data-branch-name="${escapeHtml(branch.name)}">删除</button>
        </div>
        <div class="branch-overrides-section" data-branch-overrides="${escapeHtml(branch.id)}"></div>
      </div>
    `;
  }

  async function submitCreateBranch(button) {
    const form = button.closest("form");
    if (!form) return;
    const error = form.querySelector(".modal-error");
    const submitBtn = button;
    const parentValue = form.querySelector('[name="parent"]').value;
    const name = form.querySelector('[name="name"]').value.trim().replace(/\s+/g, " ");
    const description = form.querySelector('[name="description"]').value.trim();
    const condition = form.querySelector('[name="condition"]').value.trim();
    const returnPoint = form.querySelector('[name="return_point"]').value.trim();
    if (!name) {
      if (error) error.textContent = "请输入分支名称。";
      form.querySelector('[name="name"]').focus();
      return;
    }
    const [parentType, parentId] = parentValue.split(":");
    if (!parentType || !parentId) {
      if (error) error.textContent = "请选择父级场景。";
      return;
    }
    submitBtn.disabled = true;
    submitBtn.textContent = "正在创建…";
    if (error) error.textContent = "";
    try {
      await request(API.branches(parentType, parentId), {
        method: "POST",
        body: JSON.stringify({
          name,
          description,
          condition_type: condition ? "description" : "",
          condition_value: condition,
          return_point: returnPoint || null,
        }),
      });
      if (typeof showToast === "function") showToast(`分支「${name}」已创建`);
      const modal = document.getElementById("branch-manage-modal");
      const projectId = modal?.dataset.projectId;
      if (projectId) {
        await refreshBranchList(projectId);
        await refreshStoryOperationControls(projectId);
      }
    } catch (requestError) {
      if (error) error.textContent = requestError.message;
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "创建分支";
    }
  }

  function startEditBranch(button) {
    const card = button.closest(".branch-card");
    if (!card) return;
    const branchId = button.dataset.branchId;
    const name = button.dataset.branchName || "";
    const description = button.dataset.branchDescription || "";
    const condition = button.dataset.branchCondition || "";
    const returnPoint = button.dataset.branchReturnPoint || "";
    const isActive = button.dataset.branchActive === "1";
    card.innerHTML = `
      <form class="branch-edit-form" data-branch-id="${escapeHtml(branchId)}">
        <label class="label">分支名称</label>
        <input name="name" class="modal-input" maxlength="80" value="${escapeHtml(name)}" required />
        <label class="label">说明</label>
        <textarea name="description" class="modal-input" maxlength="500" rows="2">${escapeHtml(description)}</textarea>
        <label class="label">条件</label>
        <input name="condition" class="modal-input" maxlength="500" value="${escapeHtml(condition)}" />
        <label class="label">返回点</label>
        <input name="return_point" class="modal-input" maxlength="500" value="${escapeHtml(returnPoint)}" />
        <label class="label">启用状态</label>
        <select name="is_active" class="modal-input">
          <option value="1" ${isActive ? "selected" : ""}>启用</option>
          <option value="0" ${!isActive ? "selected" : ""}>禁用</option>
        </select>
        <div class="modal-error" role="alert"></div>
        <div class="branch-edit-actions">
          <button class="btn small primary" type="button" data-api-action="edit-branch" data-branch-id="${escapeHtml(branchId)}" data-mode="save">保存</button>
          <button class="btn small" type="button" data-api-action="close-branch-modal" data-mode="cancel-edit">取消</button>
        </div>
      </form>
    `;
  }

  async function submitEditBranch(button) {
    const form = button.closest("form");
    if (!form) return;
    const branchId = button.dataset.branchId;
    const error = form.querySelector(".modal-error");
    const name = form.querySelector('[name="name"]').value.trim().replace(/\s+/g, " ");
    const description = form.querySelector('[name="description"]').value.trim();
    const condition = form.querySelector('[name="condition"]').value.trim();
    const returnPoint = form.querySelector('[name="return_point"]').value.trim();
    const isActive = form.querySelector('[name="is_active"]').value === "1";
    if (!name) {
      if (error) error.textContent = "请输入分支名称。";
      return;
    }
    button.disabled = true;
    button.textContent = "正在保存…";
    try {
      await request(API.branch(branchId), {
        method: "PATCH",
        body: JSON.stringify({
          name,
          description,
          condition_type: condition ? "description" : "",
          condition_value: condition,
          return_point: returnPoint,
          is_enabled: isActive,
        }),
      });
      if (typeof showToast === "function") showToast(`分支「${name}」已更新`);
      const modal = document.getElementById("branch-manage-modal");
      const projectId = modal?.dataset.projectId;
      if (projectId) {
        await refreshBranchList(projectId);
        await refreshStoryOperationControls(projectId);
      }
    } catch (requestError) {
      if (error) error.textContent = requestError.message;
    } finally {
      button.disabled = false;
      button.textContent = "保存";
    }
  }

  async function deleteBranch(branchId, name) {
    const confirmed = await confirmDialog({
      title: "删除分支",
      message: `确定要删除分支「${name}」吗？该分支下的所有覆盖项也会被删除。`,
      confirmText: "删除",
      danger: true,
    });
    if (!confirmed) return;
    try {
      await request(API.branch(branchId), { method: "DELETE" });
      if (typeof showToast === "function") showToast(`分支「${name}」已删除`);
      const modal = document.getElementById("branch-manage-modal");
      const projectId = modal?.dataset.projectId;
      if (projectId) {
        await refreshBranchList(projectId);
        await refreshStoryOperationControls(projectId);
      }
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message);
    }
  }

  async function toggleBranchActive(branchId, currentActive, name) {
    try {
      await request(API.branch(branchId), {
        method: "PATCH",
        body: JSON.stringify({ is_enabled: !currentActive }),
      });
      if (typeof showToast === "function") showToast(`分支「${name}」已${currentActive ? "禁用" : "启用"}`);
      const modal = document.getElementById("branch-manage-modal");
      const projectId = modal?.dataset.projectId;
      if (projectId) {
        await refreshBranchList(projectId);
        await refreshStoryOperationControls(projectId);
      }
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message);
    }
  }

  async function showBranchOverrides(branchId, branchName) {
    const section = document.querySelector(`[data-branch-overrides="${CSS.escape(branchId)}"]`);
    if (!section) return;
    if (section.innerHTML.trim()) {
      section.innerHTML = "";
      return;
    }
    section.innerHTML = '<div class="branch-overrides-loading">正在加载覆盖项…</div>';
    try {
      const payload = await request(API.branchOverrides(branchId));
      const overrides = payload.items || [];
      section.innerHTML = `
        <div class="branch-overrides-list">
          ${overrides.length === 0 ? '<p class="muted">暂无覆盖项</p>' : ""}
          ${overrides.map((override) => renderBranchOverrideItem(override)).join("")}
        </div>
        <form class="branch-override-form" data-branch-id="${escapeHtml(branchId)}">
          <label class="label">覆盖类型</label>
          <select name="override_type" class="modal-input">
            <option value="character">人物</option>
            <option value="material">素材</option>
            <option value="parameter">参数</option>
          </select>
          <label class="label">作用目标 ID（可选）</label>
          <input name="target_id" class="modal-input" maxlength="100" placeholder="留空表示整个分支；也可填写页面 ID" />
          <div data-override-fields="character">
            <label class="label">人物 ID</label>
            <input name="character_id" class="modal-input" maxlength="100" placeholder="要采用的人物 ID" />
            <label class="label">人物变体 ID（可选）</label>
            <input name="variant_id" class="modal-input" maxlength="100" placeholder="要采用的人物变体 ID" />
          </div>
          <div data-override-fields="material" hidden>
            <label class="label">素材 ID</label>
            <input name="material_id" class="modal-input" maxlength="100" placeholder="要采用的素材 ID" />
            <label class="label">素材页 ID（可选）</label>
            <input name="material_page_id" class="modal-input" maxlength="100" placeholder="要采用的素材页 ID" />
          </div>
          <div data-override-fields="parameter" hidden>
            <label class="label">参数键</label>
            <input name="param_key" class="modal-input" maxlength="100" placeholder="例如 width" />
            <label class="label">参数值</label>
            <textarea name="param_value" class="modal-input" rows="2" maxlength="2000" placeholder="例如 1024"></textarea>
          </div>
          <div class="modal-error" role="alert"></div>
          <button class="btn small primary" type="button" data-api-action="add-branch-override" data-branch-id="${escapeHtml(branchId)}" data-mode="save">添加覆盖</button>
        </form>
      `;
      const typeSelect = section.querySelector('[name="override_type"]');
      typeSelect?.addEventListener("change", () => {
        section.querySelectorAll("[data-override-fields]").forEach((group) => {
          group.hidden = group.dataset.overrideFields !== typeSelect.value;
        });
      });
    } catch (error) {
      section.innerHTML = `<div class="branch-modal-error">覆盖项加载失败：${escapeHtml(error.message)}</div>`;
    }
  }

  function renderBranchOverrideItem(override) {
    const typeLabels = { character: "人物", material: "素材", parameter: "参数" };
    const typeLabel = typeLabels[override.override_type] || override.override_type || "未知";
    let value = "";
    if (override.override_type === "character") {
      value = [override.character_id, override.variant_id].filter(Boolean).join(" / ");
    } else if (override.override_type === "material") {
      value = [override.material_id, override.material_page_id].filter(Boolean).join(" / ");
    } else {
      value = [override.param_key, override.param_value]
        .filter((item) => item !== null && item !== undefined && item !== "")
        .join(" = ");
    }
    return `
      <div class="branch-override-item">
        <span class="branch-override-type">${escapeHtml(typeLabel)}</span>
        <span class="branch-override-target">${escapeHtml(override.target_id || "")}</span>
        <span class="branch-override-value">${escapeHtml(value || "未设置")}</span>
        <button class="btn small danger-soft" type="button" data-api-action="delete-branch-override" data-override-id="${escapeHtml(override.id)}">删除</button>
      </div>
    `;
  }

  async function submitAddBranchOverride(button) {
    const form = button.closest("form");
    if (!form) return;
    const branchId = button.dataset.branchId;
    const error = form.querySelector(".modal-error");
    const overrideType = form.querySelector('[name="override_type"]').value;
    const targetId = form.querySelector('[name="target_id"]').value.trim();
    const characterId = form.querySelector('[name="character_id"]').value.trim();
    const variantId = form.querySelector('[name="variant_id"]').value.trim();
    const materialId = form.querySelector('[name="material_id"]').value.trim();
    const materialPageId = form.querySelector('[name="material_page_id"]').value.trim();
    const paramKey = form.querySelector('[name="param_key"]').value.trim();
    const paramValue = form.querySelector('[name="param_value"]').value.trim();
    const typeIsValid = (overrideType === "character" && characterId)
      || (overrideType === "material" && materialId)
      || (overrideType === "parameter" && paramKey && paramValue);
    if (!typeIsValid) {
      if (error) error.textContent = "请填写当前覆盖类型所需的 ID 或参数键值。";
      return;
    }
    button.disabled = true;
    button.textContent = "正在添加…";
    try {
      await request(API.branchOverrides(branchId), {
        method: "POST",
        body: JSON.stringify({
          override_type: overrideType,
          target_id: targetId || null,
          character_id: overrideType === "character" ? characterId : null,
          variant_id: overrideType === "character" ? (variantId || null) : null,
          material_id: overrideType === "material" ? materialId : null,
          material_page_id: overrideType === "material" ? (materialPageId || null) : null,
          param_key: overrideType === "parameter" ? paramKey : null,
          param_value: overrideType === "parameter" ? paramValue : null,
        }),
      });
      if (typeof showToast === "function") showToast("覆盖项已添加");
      const section = document.querySelector(`[data-branch-overrides="${CSS.escape(branchId)}"]`);
      if (section) section.innerHTML = "";
      await showBranchOverrides(branchId, "");
    } catch (requestError) {
      if (error) error.textContent = requestError.message;
    } finally {
      button.disabled = false;
      button.textContent = "添加覆盖";
    }
  }

  async function deleteBranchOverride(overrideId) {
    const confirmed = await confirmDialog({
      title: "删除覆盖项",
      message: "确定要删除此覆盖项吗？",
      confirmText: "删除",
      danger: true,
    });
    if (!confirmed) return;
    try {
      await request(API.branchOverride(overrideId), { method: "DELETE" });
      if (typeof showToast === "function") showToast("覆盖项已删除");
      const section = document.querySelector(".branch-overrides-section:not(:empty)");
      if (section) {
        const branchId = section.dataset.branchOverrides;
        if (branchId) {
          section.innerHTML = "";
          await showBranchOverrides(branchId, "");
        }
      }
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message);
    }
  }

  // ==================== 剧本快照 ====================

  function ensureSnapshotModal() {
    let modal = document.getElementById("snapshot-modal");
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "snapshot-modal";
    modal.className = "atelier-modal-backdrop";
    modal.hidden = true;
    modal.innerHTML = `
      <section class="atelier-modal size-lg" role="dialog" aria-modal="true" aria-labelledby="snapshot-modal-title">
        <header class="atelier-modal-head">
          <div>
            <h2 id="snapshot-modal-title">版本历史</h2>
            <p class="atelier-modal-sub">创建剧本快照并可在需要时恢复。</p>
          </div>
          <button class="btn small" type="button" data-api-action="close-snapshot-modal">关闭</button>
        </header>
        <div class="atelier-modal-body" id="snapshot-modal-body">
          <div class="snapshot-modal-loading">正在加载快照…</div>
        </div>
      </section>
    `;
    document.body.appendChild(modal);
    modal.addEventListener("click", (event) => {
      if (event.target === modal) closeSnapshotModal();
    });
    return modal;
  }

  async function openSnapshotModal(projectId) {
    const modal = ensureSnapshotModal();
    modal.dataset.projectId = projectId;
    modal.hidden = false;
    requestAnimationFrame(() => modal.classList.add("show"));
    await refreshSnapshotList(projectId);
  }

  function closeSnapshotModal() {
    const modal = document.getElementById("snapshot-modal");
    if (!modal) return;
    modal.classList.remove("show");
    window.setTimeout(() => {
      modal.hidden = true;
    }, 150);
  }

  async function refreshSnapshotList(projectId) {
    const body = document.getElementById("snapshot-modal-body");
    if (!body) return;
    body.innerHTML = '<div class="snapshot-modal-loading">正在加载快照…</div>';
    try {
      const payload = await request(API.projectSnapshots(projectId));
      const snapshots = payload.items || [];
      body.innerHTML = `
        <div class="snapshot-modal-section">
          <h3>创建快照</h3>
          <form id="create-snapshot-form" class="snapshot-create-form">
            <label class="label">标签</label>
            <input name="label" class="modal-input" maxlength="80" autocomplete="off" placeholder="例如：v1.0 初稿" required />
            <div class="modal-error" id="create-snapshot-error" role="alert"></div>
            <button class="btn small primary" type="button" data-api-action="create-snapshot" data-project-id="${escapeHtml(projectId)}">创建快照</button>
          </form>
        </div>
        <div class="snapshot-modal-section">
          <h3>历史快照（${snapshots.length}）</h3>
          ${snapshots.length === 0
            ? '<p class="snapshot-empty">还没有快照。在上方创建第一个快照。</p>'
            : `<div class="snapshot-list">${snapshots.map(renderSnapshotCard).join("")}</div>`
          }
        </div>
      `;
    } catch (error) {
      body.innerHTML = `<div class="snapshot-modal-error">快照加载失败：${escapeHtml(error.message)}</div>`;
    }
  }

  function renderSnapshotCard(snapshot) {
    const created = snapshot.created_at
      ? new Date(snapshot.created_at).toLocaleString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })
      : "未知时间";
    const pageCount = snapshot.page_count != null ? snapshot.page_count : "—";
    return `
      <div class="snapshot-card">
        <div class="snapshot-card-head">
          <strong>${escapeHtml(snapshot.label || "未命名")}</strong>
          <span class="snapshot-card-time">${escapeHtml(created)}</span>
        </div>
        <div class="snapshot-card-meta">
          <span>页数：${escapeHtml(String(pageCount))}</span>
        </div>
        <div class="snapshot-card-actions">
          <button class="btn small soft" type="button" data-api-action="restore-snapshot" data-snapshot-id="${escapeHtml(snapshot.id)}" data-snapshot-label="${escapeHtml(snapshot.label || "未命名")}">恢复此快照</button>
        </div>
      </div>
    `;
  }

  async function submitCreateSnapshot(button) {
    const form = button.closest("form");
    if (!form) return;
    const projectId = button.dataset.projectId;
    const error = form.querySelector(".modal-error");
    const label = form.querySelector('[name="label"]').value.trim().replace(/\s+/g, " ");
    if (!label) {
      if (error) error.textContent = "请输入快照标签。";
      return;
    }
    button.disabled = true;
    button.textContent = "正在创建…";
    if (error) error.textContent = "";
    try {
      await request(API.projectSnapshots(projectId), {
        method: "POST",
        body: JSON.stringify({ label }),
      });
      if (typeof showToast === "function") showToast(`快照「${label}」已创建`);
      await refreshSnapshotList(projectId);
    } catch (requestError) {
      if (error) error.textContent = requestError.message;
    } finally {
      button.disabled = false;
      button.textContent = "创建快照";
    }
  }

  async function restoreSnapshot(snapshotId, label) {
    const confirmed = await confirmDialog({
      title: "恢复快照",
      message: `确定要将剧本恢复到快照「${label}」吗？当前未保存的更改将丢失。`,
      confirmText: "恢复",
      danger: true,
    });
    if (!confirmed) return;
    try {
      await request(API.projectSnapshotRestore(snapshotId), { method: "POST" });
      if (typeof showToast === "function") showToast(`已恢复到快照「${label}」`);
      closeSnapshotModal();
      const project = await resolveCurrentProject();
      if (project) await renderProductionStoryCanvasV3(project);
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message);
    }
  }

  // ==================== 撤销重做 ====================

  async function undoLastOperation(projectId) {
    try {
      const payload = await request(API.projectOperations(projectId));
      const operations = payload.items || [];
      const redoKey = `atelier-story-redo-${projectId}`;
      const pendingRedoId = window.sessionStorage.getItem(redoKey);
      const undoable = pendingRedoId ? null : operations[0];
      if (!undoable) {
        if (typeof showToast === "function") showToast("没有可撤销的操作");
        return;
      }
      const result = await request(API.operationUndo(undoable.id), { method: "POST" });
      if (result.redo_operation_id) {
        window.sessionStorage.setItem(redoKey, result.redo_operation_id);
      }
      if (typeof showToast === "function") showToast("操作已撤销");
      const project = await resolveCurrentProject();
      if (project) await renderProductionStoryCanvasV3(project);
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message);
    }
  }

  async function redoLastOperation(projectId) {
    try {
      const redoKey = `atelier-story-redo-${projectId}`;
      const redoOperationId = window.sessionStorage.getItem(redoKey);
      if (!redoOperationId) {
        if (typeof showToast === "function") showToast("没有可重做的操作");
        return;
      }
      await request(API.operationRedo(redoOperationId), { method: "POST" });
      window.sessionStorage.removeItem(redoKey);
      if (typeof showToast === "function") showToast("操作已重做");
      const project = await resolveCurrentProject();
      if (project) await renderProductionStoryCanvasV3(project);
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message);
    }
  }

  // ==================== 编译预检查 ====================

  function ensurePrecheckModal() {
    let modal = document.getElementById("precheck-modal");
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "precheck-modal";
    modal.className = "atelier-modal-backdrop";
    modal.hidden = true;
    modal.innerHTML = `
      <section class="atelier-modal size-lg" role="dialog" aria-modal="true" aria-labelledby="precheck-modal-title">
        <header class="atelier-modal-head">
          <div>
            <h2 id="precheck-modal-title">编译预检查</h2>
            <p class="atelier-modal-sub">在正式编译前检查项目完整性。</p>
          </div>
          <button class="btn small" type="button" data-api-action="close-precheck-modal">关闭</button>
        </header>
        <div class="atelier-modal-body" id="precheck-modal-body">
        </div>
      </section>
    `;
    document.body.appendChild(modal);
    modal.addEventListener("click", (event) => {
      if (event.target === modal) closePrecheckModal();
    });
    return modal;
  }

  function openPrecheckModal(projectId) {
    const modal = ensurePrecheckModal();
    modal.dataset.projectId = projectId;
    const scenes = collectProjectScenes();
    const body = document.getElementById("precheck-modal-body");
    if (body) {
      body.innerHTML = `
        <div class="precheck-modal-section">
          <h3>检查范围</h3>
          <form id="precheck-form" class="precheck-form">
            <label class="label">范围</label>
            <select name="scope" class="modal-input" id="precheck-scope">
              <option value="project">整个项目</option>
              <option value="chapter">指定章节</option>
              <option value="large_scene">指定大场景</option>
              <option value="small_scene">指定小场景</option>
              <option value="shot_pages">指定场景页</option>
            </select>
            <div id="precheck-target-wrap" hidden>
              <label class="label">目标</label>
              <select name="target_id" class="modal-input" id="precheck-target"></select>
            </div>
            <div class="modal-error" id="precheck-error" role="alert"></div>
            <button class="btn small primary" type="button" data-api-action="execute-precheck" data-project-id="${escapeHtml(projectId)}">运行预检查</button>
          </form>
        </div>
        <div class="precheck-modal-section" id="precheck-results" hidden>
          <h3>检查结果</h3>
          <div id="precheck-results-body"></div>
        </div>
      `;
      const scopeSelect = body.querySelector("#precheck-scope");
      const targetWrap = body.querySelector("#precheck-target-wrap");
      const targetSelect = body.querySelector("#precheck-target");
      scopeSelect.addEventListener("change", () => {
        const scope = scopeSelect.value;
        if (scope === "project") {
          targetWrap.hidden = true;
          return;
        }
        targetWrap.hidden = false;
        const chapters = storyWorkspaceState.tree || [];
        const ws = storyWorkspaceState.smallSceneWorkspace;
        let options = [];
        if (scope === "chapter") {
          options = chapters.map((ch) => ({ value: ch.id, label: ch.name }));
        } else if (scope === "large_scene") {
          chapters.forEach((ch) => {
            (ch.large_scenes || []).forEach((ls) => {
              options.push({ value: ls.id, label: `${ls.name}（${ch.name}）` });
            });
          });
        } else if (scope === "small_scene") {
          chapters.forEach((ch) => {
            (ch.large_scenes || []).forEach((ls) => {
              (ls.small_scenes || []).forEach((ss) => {
                options.push({ value: ss.id, label: `${ss.name}（${ls.name}）` });
              });
            });
          });
        } else if (scope === "shot_pages") {
          (ws?.pages || []).forEach((p) => {
            options.push({ value: p.id, label: `P${String(p.sort_order || 0).padStart(2, "0")} ${p.name || ""}` });
          });
        }
        targetSelect.innerHTML = options.length
          ? options.map((o) => `<option value="${escapeHtml(o.value)}">${escapeHtml(o.label)}</option>`).join("")
          : '<option value="">无可用选项</option>';
      });
    }
    modal.hidden = false;
    requestAnimationFrame(() => modal.classList.add("show"));
  }

  function closePrecheckModal() {
    const modal = document.getElementById("precheck-modal");
    if (!modal) return;
    modal.classList.remove("show");
    window.setTimeout(() => {
      modal.hidden = true;
    }, 150);
  }

  async function executePrecheck(button) {
    const form = button.closest("form");
    if (!form) return;
    const projectId = button.dataset.projectId;
    const error = form.querySelector(".modal-error");
    const scope = form.querySelector('[name="scope"]').value;
    const targetWrap = form.querySelector("#precheck-target-wrap");
    const targetId = targetWrap && !targetWrap.hidden
      ? form.querySelector('[name="target_id"]').value
      : null;
    if (scope !== "project" && !targetId) {
      if (error) error.textContent = "请选择预检查目标。";
      return;
    }
    const body = {};
    body.scope = scope;
    if (targetId) {
      // 后端统一使用 scope_id(下划线 scope 值：project/chapter/large_scene/small_scene/branch/shot_pages)
      body.scope_id = targetId;
    }
    button.disabled = true;
    button.textContent = "正在检查…";
    if (error) error.textContent = "";
    const resultsSection = document.getElementById("precheck-results");
    const resultsBody = document.getElementById("precheck-results-body");
    if (resultsBody) resultsBody.innerHTML = '<div class="precheck-loading">正在执行预检查…</div>';
    if (resultsSection) resultsSection.hidden = false;
    try {
      const payload = await request(API.projectPrecheck(projectId), {
        method: "POST",
        body: JSON.stringify(body),
      });
      if (resultsBody) resultsBody.innerHTML = renderPrecheckResults(payload);
      if (typeof showToast === "function") showToast("预检查完成");
    } catch (requestError) {
      if (resultsBody) resultsBody.innerHTML = `<div class="precheck-error">预检查失败：${escapeHtml(requestError.message)}</div>`;
    } finally {
      button.disabled = false;
      button.textContent = "运行预检查";
    }
  }

  function renderPrecheckResults(payload) {
    const errors = payload.errors || payload.blockers || [];
    const warnings = payload.warnings || [];
    const passed = payload.passed || payload.successes || [];
    return `
      <div class="precheck-summary">
        <span class="precheck-stat danger">${errors.length} 个阻塞错误</span>
        <span class="precheck-stat warning">${warnings.length} 个警告</span>
        <span class="precheck-stat success">${passed.length} 项通过</span>
      </div>
      ${errors.length ? `
        <div class="precheck-group precheck-errors">
          <h4>阻塞错误</h4>
          ${errors.map((item) => renderPrecheckItem(item, "error")).join("")}
        </div>
      ` : ""}
      ${warnings.length ? `
        <div class="precheck-group precheck-warnings">
          <h4>警告</h4>
          ${warnings.map((item) => renderPrecheckItem(item, "warning")).join("")}
        </div>
      ` : ""}
      ${passed.length ? `
        <div class="precheck-group precheck-passed">
          <h4>通过项</h4>
          ${passed.map((item) => renderPrecheckItem(item, "passed")).join("")}
        </div>
      ` : ""}
      ${!errors.length && !warnings.length && !passed.length ? '<p class="muted">无检查结果</p>' : ""}
    `;
  }

  function renderPrecheckItem(item, level) {
    const type = item.type || item.code || "未知";
    const description = item.description || item.message || "";
    const target = item.entity_name || item.target || item.target_id || item.related_object || "";
    const entityId = item.entity_id || item.target_id || "";
    const entityType = item.entity_type || "";
    return `
      <div class="precheck-item precheck-item-${level}">
        <span class="precheck-item-type">${escapeHtml(String(type))}</span>
        <span class="precheck-item-desc">${escapeHtml(description)}</span>
        ${target ? `<span class="precheck-item-target">${escapeHtml(String(target))}</span>` : ""}
        ${entityId ? `<button class="btn small soft" type="button" data-api-action="jump-precheck-issue" data-entity-id="${escapeHtml(String(entityId))}" data-entity-type="${escapeHtml(String(entityType))}">前往处理</button>` : ""}
      </div>
    `;
  }

  function jumpToPrecheckIssue(entityType, entityId) {
    let target = null;
    if (entityType === "shot_page") {
      target = document.querySelector(`[data-scene-page-id="${CSS.escape(entityId)}"]`);
    } else if (entityType === "small_scene") {
      target = document.querySelector(`[data-small-scene-id="${CSS.escape(entityId)}"]`);
    } else if (entityType === "large_scene") {
      target = document.querySelector(`[data-large-scene-id="${CSS.escape(entityId)}"]`);
    } else if (entityType === "chapter") {
      target = document.querySelector(`[data-chapter-id="${CSS.escape(entityId)}"]`);
    }
    if (!target) {
      if (typeof showToast === "function") showToast("当前画布中找不到对应对象");
      return;
    }
    closePrecheckModal();
    if (entityType === "shot_page" || entityType === "small_scene") {
      openSmallSceneRoute(target.dataset.smallSceneId || entityId, entityType === "shot_page" ? entityId : "");
      return;
    }
    target.scrollIntoView({ behavior: "smooth", block: "center" });
    target.click();
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

  function characterEmptyState(filtered) {
    if (filtered) {
      return `
        <section class="production-empty-state">
          <span class="production-empty-icon">CH</span>
          <h2>没有匹配的人物</h2>
          <p>调整搜索关键词或标签筛选后再试。</p>
          <button class="btn soft" data-api-action="characters-back-to-active">清除筛选</button>
        </section>
      `;
    }
    return `
      <section class="production-empty-state">
        <span class="production-empty-icon">CH</span>
        <h2>还没有人物</h2>
        <p>创建人物后，可以为不同形象填写规格和提示词。</p>
        <button class="btn primary" data-api-action="open-character-modal">新建人物</button>
        <small>尚未创建任何人物</small>
      </section>
    `;
  }

  function characterDate(value, includeTime = false) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "刚刚";
    return date.toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      ...(includeTime ? { hour: "2-digit", minute: "2-digit" } : {}),
    });
  }

  function characterCard(character, stats, specCount) {
    stats = stats || character.stats || {};
    const filled = stats.spec_filled || 0;
    const total = stats.spec_total || 0;
    const variantCount = stats.variant_count != null ? stats.variant_count : (character.variant_count || 0);
    specCount = specCount != null
      ? specCount
      : (variantCount > 0 ? Math.floor(total / variantCount) : total);
    const completeness = total > 0 ? `${filled}/${total}` : "0/0";
    const isArchived = Boolean(character.archived_at);
    const hasCover = Boolean(character.cover_path);
    const initial = escapeHtml((character.name || "?").slice(0, 1).toUpperCase());
    const coverHtml = hasCover
      ? `<img src="${API.characterCoverThumbnail(character.id)}" alt="${escapeHtml(character.name)} 封面" loading="lazy" decoding="async" onerror="this.replaceWith(Object.assign(document.createElement('span'),{textContent:${JSON.stringify((character.name || '?').slice(0, 1).toUpperCase())}}))" />`
      : `<span class="character-block-thumb-placeholder">${initial}</span>`;
    return `
      <article
        class="character-block real-character-card${isArchived ? " character-card-archived" : ""}"
        data-character-id="${escapeHtml(character.id)}"
        data-api-action="select-character"
        data-context-menu="character"
        data-name="${escapeHtml(character.name)}"
        tabindex="0"
        role="button"
        aria-label="打开人物 ${escapeHtml(character.name)}"
      >
        <div class="character-block-thumb">${coverHtml}
          ${isArchived ? `<span class="character-card-status-flag">已归档</span>` : ""}
        </div>
        <div class="character-block-body">
          <div class="character-block-name">${escapeHtml(character.name)}</div>
          <div class="character-block-meta">${variantCount} 个形象 · ${specCount} 个公共规格</div>
          <div class="character-block-stats">
            <span class="stats-pill ${filled > 0 ? "" : "muted"}">提示词 ${completeness}</span>
            <span class="character-card-time">${escapeHtml(characterDate(character.updated_at))}</span>
          </div>
          <div class="character-card-actions">
            ${isArchived
              ? `<button class="btn small soft" type="button" data-api-action="restore-character" data-character-id="${escapeHtml(character.id)}" data-character-name="${escapeHtml(character.name)}">恢复</button>`
              : `<button class="btn small soft" type="button" data-api-action="archive-character" data-character-id="${escapeHtml(character.id)}" data-character-name="${escapeHtml(character.name)}">归档</button>`}
            <button class="btn small" type="button" data-api-action="copy-character" data-character-id="${escapeHtml(character.id)}" data-character-name="${escapeHtml(character.name)}">复制</button>
            <button class="btn small danger-soft" type="button" data-api-action="delete-character" data-character-id="${escapeHtml(character.id)}" data-character-name="${escapeHtml(character.name)}">移入回收站</button>
          </div>
        </div>
      </article>
    `;
  }

  function characterTrashCard(character) {
    const stats = character.stats || {};
    const variantCount = stats.variant_count != null ? stats.variant_count : (character.variant_count || 0);
    const deletedAt = characterDate(character.deleted_at || character.updated_at, true);
    const hasCover = Boolean(character.cover_path);
    const initial = escapeHtml((character.name || "?").slice(0, 1).toUpperCase());
    const coverHtml = hasCover
      ? `<img src="${API.characterCoverThumbnail(character.id)}" alt="" loading="lazy" decoding="async" style="opacity:0.65" />`
      : `<span class="character-block-thumb-placeholder">${initial}</span>`;
    return `
      <article
        class="character-block real-character-card character-trash-card"
        data-character-id="${escapeHtml(character.id)}"
        aria-label="恢复或永久删除人物 ${escapeHtml(character.name)}"
      >
        <div class="character-block-thumb" style="opacity:0.65">${coverHtml}
          <span class="character-card-status-flag">已删除</span>
        </div>
        <div class="character-block-body">
          <div class="character-block-name">${escapeHtml(character.name)}</div>
          <div class="character-block-meta">${variantCount} 个形象</div>
          <div class="character-block-stats">
            <span class="character-card-time">删除于 ${escapeHtml(deletedAt)}</span>
          </div>
          <div class="character-card-actions">
            <button class="btn small soft" type="button" data-api-action="restore-character" data-character-id="${escapeHtml(character.id)}" data-character-name="${escapeHtml(character.name)}">恢复</button>
            <button class="btn small danger" type="button" data-api-action="permanent-delete-character" data-character-id="${escapeHtml(character.id)}" data-character-name="${escapeHtml(character.name)}">永久删除</button>
          </div>
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

  const characterSpecViewState = {
    variantId: "",
    variantName: "",
    items: [],
    activeSpecId: "",
  };

  function characterSpecMiniCard(value, isActive) {
    const label = specLabel(value);
    const filled = Boolean((value.prompt || "").trim());
    return `
      <button
        class="character-spec-mini-card${isActive ? " active" : ""}"
        type="button"
        role="tab"
        aria-selected="${isActive ? "true" : "false"}"
        data-api-action="select-character-spec"
        data-spec-id="${escapeHtml(value.spec_id)}"
      >
        <span class="character-spec-mini-name">${escapeHtml(label)}</span>
        <span class="character-spec-mini-state${filled ? " filled" : ""}">${filled ? "已填写" : "未填写"}</span>
      </button>
    `;
  }

  function characterSpecWorkspace(items, activeSpecId) {
    const activeValue = items.find((item) => item.spec_id === activeSpecId) || items[0];
    return `
      <div class="character-spec-mini-list" role="tablist" aria-label="规格列表">
        ${items.map((item) => characterSpecMiniCard(item, item.spec_id === activeValue?.spec_id)).join("")}
        <button class="character-spec-mini-card add" type="button" data-api-action="add-spec" aria-label="添加规格">
          <span class="character-spec-mini-add-icon">+</span>
          <span class="character-spec-mini-name">添加规格</span>
        </button>
      </div>
      <div class="character-spec-detail-panel" data-character-spec-detail>
        ${activeValue ? specValueEditor(activeValue) : '<div class="character-spec-editor-empty">请选择或添加规格。</div>'}
      </div>
    `;
  }

  function renderSelectedCharacterSpec(specId, editing = false) {
    const modal = document.getElementById("character-detail-modal");
    if (!modal) return null;
    const item = characterSpecViewState.items.find((value) => value.spec_id === specId);
    const detail = modal.querySelector("[data-character-spec-detail]");
    if (!item || !detail) return null;
    characterSpecViewState.activeSpecId = specId;
    modal.querySelectorAll(".character-spec-mini-card[data-spec-id]").forEach((card) => {
      const active = card.dataset.specId === specId;
      card.classList.toggle("active", active);
      card.setAttribute("aria-selected", active ? "true" : "false");
    });
    detail.innerHTML = specValueEditor(item);
    const form = detail.querySelector(".character-spec-simple-editor");
    if (form && editing) setCharacterSpecEditorMode(form, true);
    return form;
  }

  function specValueEditor(value) {
    const label = specLabel(value);
    const canRename = value.spec_type === "custom";
    const prompt = value.prompt || "";
    return `
      <form
        class="character-spec-editor character-spec-simple-editor is-viewing"
        data-inline-action="save-spec-value"
        data-spec-value-id="${escapeHtml(value.id)}"
        data-spec-id="${escapeHtml(value.spec_id)}"
        data-spec-type="${escapeHtml(value.spec_type)}"
        data-original-name="${escapeHtml(label)}"
      >
        <div class="character-spec-readonly" data-spec-display>
          <div class="character-spec-readonly-name">
            <span>规格名称</span>
            <strong data-spec-name-output>${escapeHtml(label)}</strong>
          </div>
          <div class="character-spec-readonly-prompt">
            <span>提示词</span>
            <div class="character-spec-prompt-content${prompt.trim() ? "" : " is-empty"}" data-spec-prompt-output>${escapeHtml(prompt || "尚未填写提示词")}</div>
          </div>
        </div>
        <label class="character-spec-field character-spec-name-field" data-spec-edit-field hidden>
          <span>规格名称</span>
          <input
            name="spec_name"
            type="text"
            maxlength="80"
            value="${escapeHtml(label)}"
            ${canRename ? "" : "readonly"}
            data-context-menu="project-spec"
            data-spec-id="${escapeHtml(value.spec_id)}"
            data-name="${escapeHtml(label)}"
            data-spec-type="${escapeHtml(value.spec_type)}"
            title="${canRename ? "" : "旧版内置规格名称不可修改"}"
          />
        </label>
        <label class="character-spec-field character-spec-prompt-field" data-spec-edit-field hidden>
          <span>提示词</span>
          <textarea name="prompt" rows="5" placeholder="输入这个规格使用的提示词">${escapeHtml(prompt)}</textarea>
        </label>
        <div class="character-spec-editor-actions">
          <span class="spec-save-status" role="status"></span>
          <button class="btn small danger-soft" type="button" data-api-action="delete-character-spec" data-spec-id="${escapeHtml(value.spec_id)}">删除规格</button>
          <button class="btn small" type="button" data-api-action="edit-character-spec">编辑</button>
          <button class="btn small primary" type="submit" hidden>保存规格</button>
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
          <div class="variant-tabs" role="tablist" data-character-id="${escapeHtml(character.id)}">
            ${variants.map((v) => variantTab(v, v.id === activeVariantId)).join("")}
            <button class="variant-tab-add" type="button" data-api-action="add-variant" data-character-id="${escapeHtml(character.id)}" aria-label="添加形象">+</button>
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
              <div class="character-expanded-sub">当前形象：${escapeHtml(defaultVariant ? defaultVariant.name : "无")}</div>
            </div>
          </div>
          <div
            class="character-spec-editor-list"
            data-variant-spec-values
            data-active-variant-id="${escapeHtml(activeVariantId)}"
          >
            ${activeVariantId
              ? '<div class="character-spec-editor-loading">正在读取规格内容…</div>'
              : '<div class="character-spec-editor-empty">请先创建一个形象。</div>'}
          </div>
        </div>
      </section>
    `;
  }

  async function renderVariantSpecValues(variantId, variantName, preferredSpecId = "") {
    const modal = document.getElementById("character-detail-modal");
    if (!modal || modal.hidden) return;
    const list = modal.querySelector("[data-variant-spec-values]");
    if (!list) return;
    list.dataset.activeVariantId = variantId;
    list.innerHTML = '<div class="character-spec-editor-loading">正在读取规格内容…</div>';
    try {
      const payload = await request(`/api/character-variants/${variantId}/spec-values`);
      if (list.dataset.activeVariantId !== variantId) return;
      const activeSpecId = payload.items.some((item) => item.spec_id === preferredSpecId)
        ? preferredSpecId
        : (payload.items[0]?.spec_id || "");
      characterSpecViewState.variantId = variantId;
      characterSpecViewState.variantName = variantName || "";
      characterSpecViewState.items = payload.items;
      characterSpecViewState.activeSpecId = activeSpecId;
      list.innerHTML = characterSpecWorkspace(payload.items, activeSpecId);
      const sub = modal.querySelector(".character-expanded-sub");
      if (sub) {
        sub.textContent = `${payload.total} 个规格 · 当前形象：${variantName || ""}`;
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
        draggable="true"
        title="拖拽排序；右键进行复制、移动或删除"
        data-api-action="select-variant"
        data-variant-id="${escapeHtml(variant.id)}"
        data-variant-name="${escapeHtml(variant.name)}"
        data-context-menu="character-variant"
        data-name="${escapeHtml(variant.name)}"
        data-is-default="${isDefault ? "1" : "0"}"
      >
        <span class="variant-tab-name">${escapeHtml(variant.name)}</span>
        ${isDefault && variant.name !== "默认" ? '<span class="variant-tab-default">默认</span>' : ""}
      </button>
    `;
  }

  const characterListState = {
    q: "",
    tag: "",
    sort: "sort_asc",
    archived: false,
    trash: false,
    limit: 20,
    offset: 0,
    total: 0,
    items: [],
    loading: false,
    requestId: 0,
    searchTimer: null,
    tagTimer: null,
  };

  function charactersToolbar(state) {
    const sortOptions = [
      { value: "sort_asc", label: "默认顺序" },
      { value: "updated_desc", label: "最近修改" },
      { value: "name_asc", label: "名称 A→Z" },
      { value: "name_desc", label: "名称 Z→A" },
    ];
    return `
      <section class="panel characters-toolbar" aria-label="人物筛选">
        <div class="panel-body" style="display:flex;flex-wrap:wrap;gap:10px;align-items:center">
          <div class="search wide" style="flex:1;min-width:240px;max-width:380px;display:flex;align-items:center;gap:6px">
            <span>⌕</span>
            <input id="characters-search-input" type="search" value="${escapeHtml(state.q)}" placeholder="搜索人物名称或描述" style="border:0;outline:0;background:transparent;flex:1;font-size:11px;color:#4d576b" />
          </div>
          <label class="projects-filter-label" style="display:flex;align-items:center;gap:6px;color:#7d8698;font-size:10px">
            <span>排序</span>
            <select id="characters-sort-select" class="modal-input" style="height:34px;padding:0 8px;font-size:11px">
              ${sortOptions.map((o) => `<option value="${o.value}" ${state.sort === o.value ? "selected" : ""}>${o.label}</option>`).join("")}
            </select>
          </label>
          <span style="flex:1"></span>
          <button class="btn ${state.archived ? "" : "soft"}" type="button" data-api-action="characters-toggle-archived" aria-pressed="${state.archived ? "true" : "false"}">${state.archived ? "显示活跃" : "显示归档"}</button>
          <button class="btn ${state.trash ? "danger-soft" : ""}" type="button" data-api-action="characters-toggle-trash" aria-pressed="${state.trash ? "true" : "false"}">回收站</button>
          <button class="btn soft" type="button" data-api-action="characters-back-to-active" hidden>返回活跃</button>
        </div>
      </section>
    `;
  }

  function charactersSummaryLine(state) {
    const heading = state.trash
      ? "回收站"
      : state.archived
      ? "已归档人物"
      : "全局人物";
    const detail = state.total
      ? `${state.total} 个人物 · 已加载 ${state.items.length} 个`
      : "暂无人物";
    return `
      <div class="section-line real-character-heading">
        <h3>${heading}</h3>
        <span>${detail}</span>
      </div>
    `;
  }

  function charactersLoadMoreWrap() {
    return `
      <div id="characters-load-more-wrap" style="display:flex;justify-content:center;margin-top:18px" hidden>
        <button class="btn soft" type="button" data-api-action="load-more-characters">加载更多</button>
      </div>
    `;
  }

  function charactersSkeletonCard() {
    return `
      <article class="character-block real-character-card-skeleton" aria-hidden="true">
        <div class="character-block-thumb" style="opacity:0.55"></div>
        <div class="character-block-body">
          <div style="height:16px;width:60%;background:#eef0f4;border-radius:8px;margin-bottom:8px"></div>
          <div style="height:10px;width:80%;background:#f1f3f7;border-radius:6px;margin-bottom:6px"></div>
          <div style="height:10px;width:50%;background:#f1f3f7;border-radius:6px"></div>
        </div>
      </article>
    `;
  }

  function charactersErrorState(message) {
    return `
      <section class="production-empty-state" style="grid-column:1/-1">
        <span class="production-empty-icon">!</span>
        <h2>人物列表加载失败</h2>
        <p>${escapeHtml(message)}</p>
        <button class="btn soft" type="button" data-api-action="retry-characters">重试</button>
      </section>
    `;
  }

  function updateCharactersViewToggleState() {
    const archiveBtn = document.querySelector('[data-api-action="characters-toggle-archived"]');
    const trashBtn = document.querySelector('[data-api-action="characters-toggle-trash"]');
    const backBtn = document.querySelector('[data-api-action="characters-back-to-active"]');
    if (archiveBtn) {
      archiveBtn.textContent = characterListState.archived ? "显示活跃" : "显示归档";
      archiveBtn.classList.toggle("soft", !characterListState.archived);
      archiveBtn.setAttribute("aria-pressed", characterListState.archived ? "true" : "false");
    }
    if (trashBtn) {
      trashBtn.classList.toggle("danger-soft", characterListState.trash);
      trashBtn.setAttribute("aria-pressed", characterListState.trash ? "true" : "false");
    }
    if (backBtn) {
      backBtn.hidden = !characterListState.trash && !characterListState.archived;
    }
  }

  function bindCharactersToolbar() {
    const search = document.getElementById("characters-search-input");
    const tag = document.getElementById("character-tag-filter");
    const sort = document.getElementById("characters-sort-select");

    search?.addEventListener("input", () => {
      clearTimeout(characterListState.searchTimer);
      characterListState.searchTimer = setTimeout(() => {
        characterListState.q = search.value.trim();
        loadCharacters(false);
      }, 280);
    });

    sort?.addEventListener("change", () => {
      characterListState.sort = sort.value;
      loadCharacters(false);
    });

    const scheduleTagWork = () => {
      clearTimeout(characterListState.tagTimer);
      characterListState.tagTimer = setTimeout(() => {
        characterListState.tag = tag.value.trim();
        loadCharacters(false);
      }, 280);
    };
    tag?.addEventListener("input", scheduleTagWork);
    tag?.addEventListener("change", scheduleTagWork);
  }

  async function loadCharacters(append) {
    const grid = document.getElementById("character-grid");
    const summary = document.getElementById("character-library-summary");
    const loadMoreWrap = document.getElementById("characters-load-more-wrap");
    if (!grid || (append && characterListState.loading)) return;
    updateCharactersViewToggleState();

    characterListState.loading = true;
    const requestId = characterListState.requestId + 1;
    characterListState.requestId = requestId;
    if (!append) {
      characterListState.offset = 0;
      characterListState.items = [];
      grid.innerHTML = characterListState.items.length
        ? ""
        : '<div class="character-list-loading">正在读取人物库…</div>';
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
    if (characterListState.q) params.set("q", characterListState.q);
    if (characterListState.tag) params.set("tag", characterListState.tag);
    params.set("archived", characterListState.archived ? "true" : "false");
    params.set("trash", characterListState.trash ? "true" : "false");
    params.set("sort", characterListState.sort);
    params.set("limit", String(characterListState.limit));
    params.set("offset", String(append ? characterListState.items.length : 0));

    try {
      const payload = await request(`${API.characters}?${params.toString()}`);
      if (requestId !== characterListState.requestId) return;
      let incoming = Array.isArray(payload.items) ? payload.items : [];
      if (characterListState.archived && !characterListState.trash) {
        incoming = incoming.filter((item) => item.archived_at && !item.deleted_at);
      }
      characterListState.items = append
        ? characterListState.items.concat(incoming)
        : incoming;
      characterListState.total = Number(payload.total || 0);
      characterListState.offset = characterListState.items.length;

      const filtered = Boolean(characterListState.q || characterListState.tag);
      const cardRenderer = characterListState.trash
        ? characterTrashCard
        : characterCard;
      grid.innerHTML = characterListState.items.length
        ? characterListState.items.map((character) => cardRenderer(character)).join("")
        : characterEmptyState(filtered);
      if (summary) {
        const heading = characterListState.trash
          ? "回收站"
          : characterListState.archived
          ? "已归档人物"
          : "全局人物";
        summary.textContent = characterListState.items.length
          ? `${heading} · 共 ${characterListState.items.length} 个`
          : `${heading} · 暂无人物`;
      }
      const hasMore = Boolean(payload.has_more) ||
        characterListState.items.length < characterListState.total;
      if (loadMoreWrap) {
        loadMoreWrap.hidden = !hasMore;
        const button = loadMoreWrap.querySelector("button");
        if (button) {
          button.disabled = false;
          button.textContent = "加载更多";
        }
      }
    } catch (error) {
      if (requestId !== characterListState.requestId) return;
      grid.innerHTML = charactersErrorState(error.message);
      if (summary) summary.textContent = "";
      if (loadMoreWrap) loadMoreWrap.hidden = true;
    } finally {
      if (requestId === characterListState.requestId) {
        characterListState.loading = false;
      }
    }
  }

  async function renderProductionCharacters() {
    const page = document.querySelector(".page-scroll");
    if (!page) return;
    const header = page.querySelector(".page-header");
    [...page.children].forEach((child) => {
      if (child !== header) child.remove();
    });
    const title = header?.querySelector(".page-title");
    const subtitle = header?.querySelector(".page-subtitle");
    const actions = header?.querySelector(".header-actions");
    if (title) title.textContent = "人物库";
    characterListState.tag = "";
    if (subtitle) subtitle.textContent = "管理人物形象、规格名称和提示词。";
    if (actions) {
      actions.innerHTML = '<button class="btn primary" type="button" data-api-action="open-character-modal">新建人物</button>';
    }

    page.insertAdjacentHTML("beforeend", charactersToolbar(characterListState));
    page.insertAdjacentHTML(
      "beforeend",
      `<div class="character-library-summary" id="character-library-summary" aria-live="polite"></div>`
    );
    page.insertAdjacentHTML(
      "beforeend",
      `<div class="character-grid" id="character-grid">${charactersSkeletonCard().repeat(4)}</div>`
    );
    page.insertAdjacentHTML("beforeend", charactersLoadMoreWrap());

    bindCharactersToolbar();
    await loadCharacters(false);
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

  const projectsListState = {
    q: "",
    status: "all",
    sort: "updated",
    archived: false,
    trash: false,
    limit: 24,
    offset: 0,
    total: 0,
    items: [],
    hasMore: false,
    loading: false,
    requestId: 0,
    searchTimer: null,
  };

  const materialListState = {
    q: "",
    materialType: "",
    validationStatus: "",
    tag: "",
    sort: "updated_desc",
    archived: false,
    trash: false,
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
    const isArchived = Boolean(item.archived_at);
    return `
      <article
        class="material-card real-material-card${isArchived ? " material-card-archived" : ""}"
        data-material-id="${escapeHtml(item.id)}"
        tabindex="0"
        role="button"
        aria-label="打开素材 ${escapeHtml(item.name)}"
      >
        <div class="material-card-preview type-${escapeHtml(item.material_type)}">
          ${image}
          ${image ? "" : `<span class="material-card-preview-code">${escapeHtml(type.code)}</span>`}
          ${isArchived ? `<span class="material-card-status-flag">已归档</span>` : ""}
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
          <div class="material-card-actions">
            ${isArchived
              ? `<button class="btn small soft" type="button" data-api-action="restore-material" data-material-id="${escapeHtml(item.id)}" data-material-name="${escapeHtml(item.name)}">恢复</button>`
              : `<button class="btn small soft" type="button" data-api-action="archive-material" data-material-id="${escapeHtml(item.id)}" data-material-name="${escapeHtml(item.name)}">归档</button>`}
            <button class="btn small" type="button" data-api-action="copy-material" data-material-id="${escapeHtml(item.id)}" data-material-name="${escapeHtml(item.name)}">复制</button>
            <button class="btn small danger-soft" type="button" data-api-action="delete-material" data-material-id="${escapeHtml(item.id)}" data-material-name="${escapeHtml(item.name)}">移入回收站</button>
          </div>
        </div>
      </article>
    `;
  }

  function materialTrashCard(item) {
    const type = materialTypeInfo(item.material_type);
    const deletedAt = materialDate(item.deleted_at || item.updated_at, true);
    const image = item.thumbnail_url
      ? `<img src="${escapeHtml(item.thumbnail_url)}" alt="" loading="lazy" decoding="async" />`
      : "";
    return `
      <article
        class="material-card real-material-card material-trash-card"
        data-material-id="${escapeHtml(item.id)}"
        aria-label="恢复或永久删除素材 ${escapeHtml(item.name)}"
      >
        <div class="material-card-preview type-${escapeHtml(item.material_type)}" style="opacity:0.65">
          ${image}
          ${image ? "" : `<span class="material-card-preview-code">${escapeHtml(type.code)}</span>`}
          <span class="material-card-status-flag">已删除</span>
        </div>
        <div class="material-card-body">
          <div class="material-card-head">
            <span class="material-name">${escapeHtml(item.name)}</span>
            <span class="material-type-badge">${escapeHtml(type.label)}</span>
          </div>
          <div class="material-desc">${escapeHtml(item.description || "暂无简介")}</div>
          <div class="material-footer">
            <span class="material-card-time">删除于 ${escapeHtml(deletedAt)}</span>
          </div>
          <div class="material-card-actions">
            <button class="btn small soft" type="button" data-api-action="restore-material" data-material-id="${escapeHtml(item.id)}" data-material-name="${escapeHtml(item.name)}">恢复</button>
            <button class="btn small danger" type="button" data-api-action="permanent-delete-material" data-material-id="${escapeHtml(item.id)}" data-material-name="${escapeHtml(item.name)}">永久删除</button>
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
    if (materialListState.trash) {
      return `
        <section class="material-list-state">
          <span class="material-state-icon">MT</span>
          <h2>回收站为空</h2>
          <p>删除的素材会暂存在这里，可恢复或永久清除。</p>
          <button class="btn soft" type="button" data-api-action="materials-back-to-active">返回素材库</button>
        </section>
      `;
    }
    if (materialListState.archived) {
      return `
        <section class="material-list-state">
          <span class="material-state-icon">MT</span>
          <h2>没有已归档的素材</h2>
          <p>归档的素材会显示在这里，可随时恢复。</p>
          <button class="btn soft" type="button" data-api-action="materials-back-to-active">返回素材库</button>
        </section>
      `;
    }
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

  function ensureMaterialsViewToggle() {
    const runtime = document.querySelector(".material-library-runtime");
    if (!runtime) return;
    let toolbar = document.getElementById("materials-view-toggle");
    if (toolbar) {
      updateMaterialsViewToggleState(toolbar);
      return;
    }
    toolbar = document.createElement("div");
    toolbar.id = "materials-view-toggle";
    toolbar.className = "materials-view-toggle";
    toolbar.innerHTML = `
      <button class="btn small soft" type="button" data-api-action="materials-toggle-archived">显示归档</button>
      <button class="btn small" type="button" data-api-action="materials-toggle-trash">回收站</button>
      <button class="btn small soft" type="button" data-api-action="materials-back-to-active" hidden>返回活跃</button>
    `;
    const typeFilters = runtime.querySelector("#material-type-filters");
    if (typeFilters) {
      typeFilters.before(toolbar);
    } else {
      runtime.prepend(toolbar);
    }
    updateMaterialsViewToggleState(toolbar);
  }

  function updateMaterialsViewToggleState(toolbar) {
    const archiveBtn = toolbar.querySelector('[data-api-action="materials-toggle-archived"]');
    const trashBtn = toolbar.querySelector('[data-api-action="materials-toggle-trash"]');
    const backBtn = toolbar.querySelector('[data-api-action="materials-back-to-active"]');
    if (archiveBtn) {
      archiveBtn.textContent = materialListState.archived ? "显示活跃" : "显示归档";
      archiveBtn.classList.toggle("soft", !materialListState.archived);
      archiveBtn.setAttribute("aria-pressed", materialListState.archived ? "true" : "false");
    }
    if (trashBtn) {
      trashBtn.classList.toggle("danger-soft", materialListState.trash);
      trashBtn.setAttribute("aria-pressed", materialListState.trash ? "true" : "false");
    }
    if (backBtn) {
      backBtn.hidden = !materialListState.trash && !materialListState.archived;
    }
  }

  async function renderMaterialsPage() {
    bindMaterialLibraryControls();
    ensureMaterialsViewToggle();
    await loadMaterials(false);
  }

  async function loadMaterials(append) {
    const grid = document.getElementById("material-grid");
    const summary = document.getElementById("material-library-summary");
    const loadMoreWrap = document.getElementById("material-load-more-wrap");
    if (!grid || (append && materialListState.loading)) return;
    ensureMaterialsViewToggle();

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
    params.set("archived", materialListState.archived ? "true" : "false");
    params.set("trash", materialListState.trash ? "true" : "false");
    params.set("sort", materialListState.sort);
    params.set("limit", String(materialListState.limit));
    params.set("offset", String(append ? materialListState.items.length : 0));

    try {
      const payload = materialListState.trash
        ? await request(API.materialTrash)
        : await request(`${API.materials}?${params.toString()}`);
      if (requestId !== materialListState.requestId) return;
      let incoming = Array.isArray(payload.items) ? payload.items : [];
      // 归档视图下仅显示已归档（archived_at 非空）且未删除的素材
      if (materialListState.archived && !materialListState.trash) {
        incoming = incoming.filter(
          (item) => item.archived_at && !item.deleted_at
        );
      }
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
      const cardRenderer = materialListState.trash
        ? materialTrashCard
        : materialCard;
      grid.innerHTML = materialListState.items.length
        ? materialListState.items.map(cardRenderer).join("")
        : materialEmptyState(filtered);
      if (summary) {
        const heading = materialListState.trash
          ? "回收站"
          : materialListState.archived
          ? "已归档素材"
          : "素材库";
        summary.textContent = materialListState.items.length
          ? `${heading} · 共 ${materialListState.items.length} 个`
          : `${heading} · 暂无素材`;
      }
      const hasMore = materialListState.trash
        ? false
        : Boolean(payload.has_more) ||
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
      <section class="material-pages-panel" id="material-pages-panel">
        <div class="material-pages-header">
          <h3>素材页</h3>
          <button class="btn small primary" type="button" data-api-action="create-material-page">新建素材页</button>
        </div>
        <div class="material-pages-list" id="material-pages-list">
          <div class="material-pages-loading">正在读取素材页…</div>
        </div>
      </section>
      <section class="material-versions-panel" id="material-versions-panel">
        <div class="material-versions-header">
          <h3>版本历史</h3>
          <button class="btn small soft" type="button" data-api-action="create-material-version">保存版本快照</button>
        </div>
        <div class="material-versions-list" id="material-versions-list">
          <div class="material-versions-loading">正在读取版本…</div>
        </div>
      </section>
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
      loadMaterialPages(materialId);
      loadMaterialVersions(materialId);
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
    let refMessage = `确定将素材「${materialName}」移入回收站吗？可随时恢复。`;
    try {
      const refs = await request(API.materialReferences(materialId));
      const sceneCount = Array.isArray(refs.small_scenes) ? refs.small_scenes.length : 0;
      const pageCount = Array.isArray(refs.scene_pages) ? refs.scene_pages.length : 0;
      if (sceneCount || pageCount) {
        refMessage = `素材「${materialName}」被 ${sceneCount} 个小场景、${pageCount} 个场景页引用。移入回收站后引用仍保留，但素材不可用。\n确定继续？`;
      }
    } catch (_) {
      // 引用反查失败时不阻塞删除
    }
    const confirmed = await confirmDialog({
      title: "移入回收站",
      message: refMessage,
      confirmText: "移入回收站",
      danger: true,
    });
    if (!confirmed) return;
    try {
      await request(API.material(materialId), { method: "DELETE" });
      if (typeof showToast === "function") showToast(`素材「${materialName}」已移入回收站`);
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

  async function archiveMaterial(materialId, materialName) {
    if (!await confirmDialog({
      title: `归档素材「${materialName}」`,
      message: "归档后素材会从活跃列表移除，可随时恢复。",
      confirmText: "归档",
      danger: false,
    })) {
      return;
    }
    try {
      await request(API.materialArchive(materialId), { method: "POST" });
      await loadMaterials(false);
      if (typeof showToast === "function") showToast(`素材「${materialName}」已归档`);
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    }
  }

  async function restoreMaterial(materialId, materialName) {
    try {
      await request(API.materialRestore(materialId), { method: "POST" });
      await loadMaterials(false);
      if (typeof showToast === "function") showToast(`素材「${materialName}」已恢复`);
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    }
  }

  async function permanentDeleteMaterial(materialId, materialName) {
    if (!await confirmDialog({
      title: `永久删除「${materialName}」`,
      message: "永久删除后无法恢复，素材数据和预览图将彻底清除。",
      confirmText: "永久删除",
      danger: true,
    })) {
      return;
    }
    if (!await confirmDialog({
      title: `再次确认永久删除「${materialName}」`,
      message: "这是最后一次确认，删除后无法找回。",
      confirmText: "我确认永久删除",
      danger: true,
    })) {
      return;
    }
    try {
      await request(API.materialPermanent(materialId), { method: "DELETE" });
      await loadMaterials(false);
      if (typeof showToast === "function") showToast(`素材「${materialName}」已永久删除`);
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    }
  }

  function ensureMaterialCopyModal() {
    let modal = document.getElementById("material-copy-modal");
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "material-copy-modal";
    modal.className = "atelier-modal-backdrop";
    modal.hidden = true;
    modal.innerHTML = `
      <section class="atelier-modal" role="dialog" aria-modal="true" aria-labelledby="material-copy-title">
        <div class="atelier-modal-icon">CP</div>
        <h2 id="material-copy-title">复制素材</h2>
        <p id="material-copy-context">输入新素材名称，将复制素材内容及素材页。</p>
        <form id="material-copy-form">
          <label class="label" for="material-copy-name">新素材名称</label>
          <input id="material-copy-name" class="modal-input" name="name" maxlength="80" autocomplete="off" placeholder="输入新素材名称" required />
          <div class="modal-error" id="material-copy-error" role="alert"></div>
          <div class="modal-actions">
            <button class="btn" type="button" data-api-action="close-material-copy-modal">取消</button>
            <button class="btn primary" type="submit">复制素材</button>
          </div>
        </form>
      </section>
    `;
    document.body.appendChild(modal);
    modal.addEventListener("click", (event) => {
      if (event.target === modal) closeMaterialCopyModal();
    });
    modal.querySelector("form").addEventListener("submit", submitMaterialCopy);
    return modal;
  }

  function openMaterialCopyModal(materialId, currentName) {
    const modal = ensureMaterialCopyModal();
    modal.dataset.materialId = materialId;
    const error = modal.querySelector(".modal-error");
    const nameInput = modal.querySelector('input[name="name"]');
    const context = modal.querySelector("#material-copy-context");
    if (context) context.textContent = `将「${currentName}」复制为新素材，包含内容和素材页。`;
    error.textContent = "";
    nameInput.value = `${currentName} 副本`;
    modal.hidden = false;
    requestAnimationFrame(() => {
      modal.classList.add("show");
      nameInput.focus();
      nameInput.select();
    });
  }

  function closeMaterialCopyModal() {
    const modal = document.getElementById("material-copy-modal");
    if (!modal) return;
    modal.classList.remove("show");
    window.setTimeout(() => {
      modal.hidden = true;
    }, 150);
  }

  async function submitMaterialCopy(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const modal = form.closest(".atelier-modal-backdrop");
    const materialId = modal.dataset.materialId;
    const nameInput = form.querySelector('input[name="name"]');
    const submit = form.querySelector('button[type="submit"]');
    const error = form.querySelector(".modal-error");
    const name = nameInput.value.trim().replace(/\s+/g, " ");
    if (!name) {
      error.textContent = "请输入新素材名称。";
      nameInput.focus();
      return;
    }
    if (!materialId) {
      error.textContent = "未指定要复制的素材。";
      return;
    }
    submit.disabled = true;
    submit.textContent = "正在复制…";
    error.textContent = "";
    try {
      await request(API.materialCopy(materialId), {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      closeMaterialCopyModal();
      await loadMaterials(false);
      if (typeof showToast === "function") showToast(`素材已复制为「${name}」`);
    } catch (requestError) {
      error.textContent = requestError.message;
      nameInput.focus();
    } finally {
      submit.disabled = false;
      submit.textContent = "复制素材";
    }
  }

  // ── Material Pages Panel ────────────────────────────────────

  async function loadMaterialPages(materialId) {
    const list = document.getElementById("material-pages-list");
    if (!list) return;
    list.innerHTML = '<div class="material-pages-loading">正在读取素材页…</div>';
    try {
      const payload = await request(API.materialPages(materialId));
      const pages = Array.isArray(payload.pages) ? payload.pages : [];
      list.innerHTML = pages.length
        ? pages.map(materialPageCard).join("")
        : `
          <div class="material-pages-empty">
            <span>暂无素材页</span>
            <button class="btn small soft" type="button" data-api-action="create-material-page">新建素材页</button>
          </div>
        `;
    } catch (error) {
      list.innerHTML = `<div class="material-pages-error">加载失败：${escapeHtml(error.message)}</div>`;
    }
  }

  function materialPageCard(page) {
    const hasPreview = Boolean(page.preview_thumbnail_path || page.preview_original_path);
    const thumbnailUrl = hasPreview ? API.materialPageThumbnail(page.id) : "";
    const preview = hasPreview
      ? `<img src="${escapeHtml(thumbnailUrl)}" alt="${escapeHtml(page.name)} 预览" loading="lazy" decoding="async" />`
      : `<span class="material-page-preview-placeholder">无预览</span>`;
    const contentPreview = (page.content || "").length > 120
      ? escapeHtml((page.content || "").slice(0, 120) + "…")
      : escapeHtml(page.content || "暂无内容");
    return `
      <article class="material-page-card" data-material-page-id="${escapeHtml(page.id)}" data-reference-mode="${escapeHtml(page.reference_mode || "independent")}">
        <div class="material-page-card-preview">${preview}</div>
        <div class="material-page-card-body">
          <div class="material-page-card-head">
            <span class="material-page-name">${escapeHtml(page.name)}</span>
            <span class="material-page-order">#${escapeHtml(String(page.sort_order || 0))}</span>
          </div>
          <div class="material-page-card-desc">${escapeHtml(page.description || "暂无说明")}</div>
          <div class="material-page-card-content">${contentPreview}</div>
          <div class="material-page-card-actions">
            <button class="btn small" type="button" data-api-action="edit-material-page" data-page-id="${escapeHtml(page.id)}">编辑</button>
            <button class="btn small soft" type="button" data-api-action="copy-material-page" data-page-id="${escapeHtml(page.id)}">复制</button>
            <button class="btn small soft" type="button" data-api-action="upload-material-page-preview" data-page-id="${escapeHtml(page.id)}">上传预览</button>
            ${hasPreview ? `<button class="btn small danger-soft" type="button" data-api-action="remove-material-page-preview" data-page-id="${escapeHtml(page.id)}">移除预览</button>` : ""}
            <button class="btn small soft" type="button" data-api-action="move-material-page-up" data-page-id="${escapeHtml(page.id)}">上移</button>
            <button class="btn small soft" type="button" data-api-action="move-material-page-down" data-page-id="${escapeHtml(page.id)}">下移</button>
            <button class="btn small danger-soft" type="button" data-api-action="delete-material-page" data-page-id="${escapeHtml(page.id)}" data-page-name="${escapeHtml(page.name)}">删除</button>
          </div>
        </div>
      </article>
    `;
  }

  function ensureMaterialPageModal() {
    let modal = document.getElementById("material-page-modal");
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "material-page-modal";
    modal.className = "atelier-modal-backdrop";
    modal.hidden = true;
    modal.innerHTML = `
      <section class="atelier-modal material-editor-modal" role="dialog" aria-modal="true" aria-labelledby="material-page-modal-title">
        <div class="material-modal-header">
          <div class="atelier-modal-icon">MP</div>
          <div class="material-modal-heading">
            <h2 id="material-page-modal-title">素材页</h2>
            <p id="material-page-modal-context">编辑素材页的名称、说明和内容。</p>
          </div>
          <button class="material-modal-close" type="button" data-api-action="close-material-page-modal" aria-label="关闭">×</button>
        </div>
        <div class="material-editor-scroll">
          <form id="material-page-form" class="material-editor-grid">
            <input type="hidden" name="page_id" />
            <label class="material-field wide">
              名称
              <input class="modal-input" name="name" maxlength="80" autocomplete="off" placeholder="素材页名称" required />
            </label>
            <label class="material-field wide">
              说明
              <textarea class="modal-input material-textarea" name="description" maxlength="300" placeholder="可选：素材页用途说明"></textarea>
            </label>
            <label class="material-field wide">
              素材页内容
              <textarea class="modal-input material-textarea content" name="content" maxlength="50000" placeholder="素材页正文内容"></textarea>
            </label>
            <label class="material-field wide">
              提示词内容
              <textarea class="modal-input material-textarea" name="prompt_text" maxlength="50000" placeholder="可选：提示词"></textarea>
            </label>
            <label class="material-field wide">
              负面提示词
              <textarea class="modal-input material-textarea" name="negative_prompt" maxlength="20000" placeholder="可选：负面提示词"></textarea>
            </label>
            <div class="modal-error wide" role="alert"></div>
            <div class="material-editor-actions">
              <button class="btn" type="button" data-api-action="close-material-page-modal">取消</button>
              <button class="btn primary" type="submit">保存素材页</button>
            </div>
          </form>
        </div>
      </section>
    `;
    document.body.appendChild(modal);
    modal.addEventListener("click", (event) => {
      if (event.target === modal) closeMaterialPageModal();
    });
    modal.querySelector("form").addEventListener("submit", submitMaterialPage);
    return modal;
  }

  function openMaterialPageCreateModal() {
    const materialId = materialDetailState.material?.id;
    if (!materialId) return;
    const modal = ensureMaterialPageModal();
    const form = modal.querySelector("form");
    form.reset();
    form.elements.page_id.value = "";
    modal.querySelector("#material-page-modal-title").textContent = "新建素材页";
    modal.querySelector("#material-page-modal-context").textContent = "为当前素材添加一个新的素材页。";
    modal.querySelector(".modal-error").textContent = "";
    modal.hidden = false;
    requestAnimationFrame(() => {
      modal.classList.add("show");
      form.elements.name.focus();
    });
  }

  async function openMaterialPageEditModal(pageId) {
    const modal = ensureMaterialPageModal();
    const form = modal.querySelector("form");
    const error = modal.querySelector(".modal-error");
    error.textContent = "";
    modal.querySelector("#material-page-modal-title").textContent = "编辑素材页";
    modal.querySelector("#material-page-modal-context").textContent = "修改素材页的名称、说明或内容。";
    form.elements.page_id.value = pageId;
    modal.hidden = false;
    requestAnimationFrame(() => modal.classList.add("show"));
    try {
      const payload = await request(API.materialPage(pageId));
      const page = payload.id ? payload : (payload.page || payload);
      form.elements.name.value = page.name || "";
      form.elements.description.value = page.description || "";
      form.elements.content.value = page.content || "";
      form.elements.prompt_text.value = page.prompt_text || "";
      form.elements.negative_prompt.value = page.negative_prompt || "";
    } catch (requestError) {
      error.textContent = requestError.message;
    }
  }

  function closeMaterialPageModal() {
    const modal = document.getElementById("material-page-modal");
    if (!modal) return;
    modal.classList.remove("show");
    window.setTimeout(() => {
      modal.hidden = true;
    }, 150);
  }

  async function submitMaterialPage(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const materialId = materialDetailState.material?.id;
    if (!materialId) return;
    const pageId = form.elements.page_id.value;
    const submit = form.querySelector('button[type="submit"]');
    const error = form.querySelector(".modal-error");
    const payload = {
      name: form.elements.name.value.trim().replace(/\s+/g, " "),
      description: form.elements.description.value.trim(),
      content: form.elements.content.value,
      prompt_text: form.elements.prompt_text.value,
      negative_prompt: form.elements.negative_prompt.value,
    };
    if (!payload.name) {
      error.textContent = "请输入素材页名称。";
      form.elements.name.focus();
      return;
    }
    submit.disabled = true;
    submit.textContent = "保存中…";
    error.textContent = "";
    try {
      if (pageId) {
        await request(API.materialPage(pageId), {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        if (typeof showToast === "function") showToast("素材页已保存");
      } else {
        await request(API.materialPages(materialId), {
          method: "POST",
          body: JSON.stringify(payload),
        });
        if (typeof showToast === "function") showToast("素材页已创建");
      }
      closeMaterialPageModal();
      await loadMaterialPages(materialId);
    } catch (requestError) {
      error.textContent = requestError.message;
    } finally {
      submit.disabled = false;
      submit.textContent = "保存素材页";
    }
  }

  async function deleteMaterialPage(pageId, pageName) {
    const materialId = materialDetailState.material?.id;
    let refMessage = `确定删除素材页「${pageName}」吗？`;
    try {
      const refs = await request(API.materialReferences(materialId));
      const pageCount = Array.isArray(refs.scene_pages) ? refs.scene_pages.length : 0;
      if (pageCount) {
        refMessage = `该素材被 ${pageCount} 个场景页引用。删除素材页可能影响引用。\n确定删除「${pageName}」？`;
      }
    } catch (_) {
      // 引用反查失败时不阻塞
    }
    if (!await confirmDialog({
      title: "删除素材页",
      message: refMessage,
      confirmText: "删除",
      danger: true,
    })) {
      return;
    }
    try {
      await request(API.materialPage(pageId), { method: "DELETE" });
      if (typeof showToast === "function") showToast(`素材页「${pageName}」已删除`);
      await loadMaterialPages(materialId);
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    }
  }

  async function copyMaterialPage(pageId) {
    const materialId = materialDetailState.material?.id;
    try {
      await request(API.materialPageCopy(pageId), { method: "POST" });
      if (typeof showToast === "function") showToast("素材页已复制");
      await loadMaterialPages(materialId);
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    }
  }

  async function reorderMaterialPages(pageId, direction) {
    const materialId = materialDetailState.material?.id;
    if (!materialId) return;
    const list = document.getElementById("material-pages-list");
    if (!list) return;
    const cards = Array.from(list.querySelectorAll("[data-material-page-id]"));
    const index = cards.findIndex((card) => card.dataset.materialPageId === pageId);
    if (index < 0) return;
    const swapIndex = direction === "up" ? index - 1 : index + 1;
    if (swapIndex < 0 || swapIndex >= cards.length) return;
    const pageIds = cards.map((card) => card.dataset.materialPageId);
    [pageIds[index], pageIds[swapIndex]] = [pageIds[swapIndex], pageIds[index]];
    try {
      await request(API.materialPagesOrder(materialId), {
        method: "PUT",
        body: JSON.stringify({ page_ids: pageIds }),
      });
      await loadMaterialPages(materialId);
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    }
  }

  function openMaterialPagePreviewPicker(pageId) {
    let input = document.getElementById("material-page-preview-file-input");
    if (!input) {
      input = document.createElement("input");
      input.type = "file";
      input.id = "material-page-preview-file-input";
      input.accept = "image/jpeg,image/png,image/webp";
      input.style.display = "none";
      document.body.appendChild(input);
    }
    input.value = "";
    input.onchange = async () => {
      const file = input.files && input.files[0];
      if (!file) return;
      await uploadMaterialPagePreview(pageId, file);
    };
    input.click();
  }

  async function uploadMaterialPagePreview(pageId, file) {
    const materialId = materialDetailState.material?.id;
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await fetch(API.materialPagePreview(pageId), { method: "POST", body: formData });
      if (!res.ok) {
        let message = `预览图上传失败（${res.status}）`;
        try {
          const data = await res.json();
          if (data && data.detail) message = data.detail;
          else if (data && data.error && data.error.message) message = data.error.message;
        } catch (_) { /* keep default */ }
        if (typeof showToast === "function") showToast(message);
        return;
      }
      if (typeof showToast === "function") showToast("素材页预览图已更新");
      await loadMaterialPages(materialId);
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message || "预览图上传失败，请检查网络。");
    }
  }

  async function removeMaterialPagePreview(pageId) {
    const materialId = materialDetailState.material?.id;
    if (!await confirmDialog({
      title: "移除素材页预览",
      message: "预览图将被删除。",
      confirmText: "移除预览",
      danger: true,
    })) {
      return;
    }
    try {
      await request(API.materialPagePreview(pageId), { method: "DELETE" });
      if (typeof showToast === "function") showToast("素材页预览图已移除");
      await loadMaterialPages(materialId);
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    }
  }

  // ── Material Versions Panel ─────────────────────────────────

  async function loadMaterialVersions(materialId) {
    const list = document.getElementById("material-versions-list");
    if (!list) return;
    list.innerHTML = '<div class="material-versions-loading">正在读取版本…</div>';
    try {
      const payload = await request(API.materialVersions(materialId));
      const items = Array.isArray(payload.items) ? payload.items : [];
      list.innerHTML = items.length
        ? items.map(materialVersionCard).join("")
        : `<div class="material-versions-empty">暂无版本记录</div>`;
    } catch (error) {
      list.innerHTML = `<div class="material-versions-error">加载失败：${escapeHtml(error.message)}</div>`;
    }
  }

  function materialVersionCard(version) {
    const label = version.label ? escapeHtml(version.label) : "无标签";
    const created = materialDate(version.created_at, true);
    return `
      <article class="material-version-card" data-version-number="${escapeHtml(String(version.version_number))}">
        <div class="material-version-info">
          <span class="material-version-number">v${escapeHtml(String(version.version_number))}</span>
          <span class="material-version-label">${label}</span>
          <span class="material-version-time">${escapeHtml(created)}</span>
        </div>
        <button class="btn small soft" type="button" data-api-action="restore-material-version" data-version-number="${escapeHtml(String(version.version_number))}">恢复</button>
      </article>
    `;
  }

  async function createMaterialVersion() {
    const materialId = materialDetailState.material?.id;
    if (!materialId) return;
    const label = window.prompt("为该版本添加标签（可选）：", "") || "";
    try {
      await request(API.materialVersions(materialId), {
        method: "POST",
        body: JSON.stringify({ label: label.trim() }),
      });
      if (typeof showToast === "function") showToast("版本快照已保存");
      await loadMaterialVersions(materialId);
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    }
  }

  async function restoreMaterialVersion(versionNumber) {
    const materialId = materialDetailState.material?.id;
    if (!materialId) return;
    if (!await confirmDialog({
      title: `恢复到版本 v${versionNumber}`,
      message: "恢复后当前素材内容会被版本内容覆盖，未保存的修改将丢失。",
      confirmText: "恢复版本",
      danger: true,
    })) {
      return;
    }
    try {
      await request(API.materialVersionRestore(materialId, versionNumber), { method: "POST" });
      if (typeof showToast === "function") showToast(`已恢复到版本 v${versionNumber}`);
      await renderMaterialDetailPage();
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

  function characterDetailCover(character) {
    const hasCover = Boolean(character.cover_path);
    const initial = escapeHtml((character.name || "?").slice(0, 1).toUpperCase());
    const coverHtml = hasCover
      ? `<img src="${API.characterCoverThumbnail(character.id)}" alt="${escapeHtml(character.name)} 封面" loading="lazy" decoding="async" onerror="this.replaceWith(Object.assign(document.createElement('span'),{textContent:${JSON.stringify((character.name || '?').slice(0, 1).toUpperCase())},className:'header-thumb-placeholder'}))" />`
      : `<span class="header-thumb-placeholder">${initial}</span>`;
    return `
      <div class="character-detail-cover" data-cover-target="${escapeHtml(character.id)}">
        ${coverHtml}
        <div class="character-detail-cover-actions">
          <button class="btn small soft" type="button" data-api-action="upload-character-cover" data-character-id="${escapeHtml(character.id)}" data-character-name="${escapeHtml(character.name)}">${hasCover ? "换封面" : "加封面"}</button>
          ${hasCover ? `<button class="btn small danger-soft" type="button" data-api-action="remove-character-cover" data-character-id="${escapeHtml(character.id)}" data-character-name="${escapeHtml(character.name)}">移除封面</button>` : ""}
        </div>
      </div>
    `;
  }

  function characterTagsSection(character) {
    const tags = Array.isArray(character.tags) ? character.tags : [];
    return `
      <div class="character-tags-section" data-character-id="${escapeHtml(character.id)}" data-tags="${escapeHtml(JSON.stringify(tags))}">
        <div class="character-tags-label">标签</div>
        <div class="character-tags-list"></div>
        <div class="character-tag-add-row">
          <input class="modal-input character-tag-add-input" type="text" maxlength="40" placeholder="输入标签后按回车添加" autocomplete="off" />
          <button class="btn small primary" type="button" data-api-action="character-tag-add">添加</button>
        </div>
      </div>
    `;
  }

  function renderCharacterDetailTags(section) {
    if (!section) return;
    const list = section.querySelector(".character-tags-list");
    if (!list) return;
    let tags = [];
    try {
      tags = JSON.parse(section.dataset.tags || "[]");
      if (!Array.isArray(tags)) tags = [];
    } catch (_) { tags = []; }
    list.innerHTML = tags.length
      ? tags.map((tag) => `
        <span class="character-tag-chip">
          <span>${escapeHtml(tag)}</span>
          <button class="character-tag-remove" type="button" data-api-action="character-tag-remove" data-tag="${escapeHtml(tag)}" aria-label="删除标签 ${escapeHtml(tag)}">×</button>
        </span>
      `).join("")
      : '<span class="character-tags-empty">暂无标签</span>';
  }

  function characterMatrixSection() {
    return `
      <section class="character-matrix-section">
        <div class="character-expanded-head">
          <div>
            <div class="character-expanded-title">景别矩阵</div>
            <div class="character-expanded-sub">横轴为景别，纵轴为形象，可批量编辑。</div>
          </div>
          <button class="btn small primary" type="button" data-api-action="save-character-matrix" disabled>保存全部修改</button>
        </div>
        <div class="character-matrix-wrap" id="character-matrix-wrap">
          <div class="character-spec-editor-loading">正在读取规格矩阵…</div>
        </div>
      </section>
    `;
  }

  async function renderCharacterMatrix(characterId) {
    const wrap = document.getElementById("character-matrix-wrap");
    if (!wrap) return;
    wrap.innerHTML = '<div class="character-spec-editor-loading">正在读取规格矩阵…</div>';
    try {
      const payload = await request(API.characterMatrix(characterId));
      const specs = Array.isArray(payload.specs) ? payload.specs : [];
      const variants = Array.isArray(payload.variants) ? payload.variants : [];
      const values = payload.values || {};
      if (!specs.length || !variants.length) {
        wrap.innerHTML = '<div class="character-spec-editor-empty">需要先创建变体和规格才能编辑矩阵。</div>';
        return;
      }
      wrap.innerHTML = `
        <div class="character-matrix-table-wrap">
          <table class="character-matrix-table">
            <thead>
              <tr>
                <th class="character-matrix-corner">形象 / 景别</th>
                ${specs.map((spec) => `<th>${escapeHtml(specLabel(spec))}</th>`).join("")}
              </tr>
            </thead>
            <tbody>
              ${variants.map((variant) => {
                const rowValues = values[variant.id] || {};
                return `
                  <tr data-variant-id="${escapeHtml(variant.id)}">
                    <th class="character-matrix-row-head">
                      <span>${escapeHtml(variant.name)}</span>
                      ${Number(variant.is_default) === 1 ? '<span class="character-variant-default-badge">默认</span>' : ""}
                    </th>
                    ${specs.map((spec) => {
                      const cell = rowValues[spec.id] || {};
                      const weight = cell.lora_weight === null || cell.lora_weight === undefined ? "" : String(cell.lora_weight);
                      return `
                        <td data-spec-value-id="${escapeHtml(cell.id || "")}" data-variant-id="${escapeHtml(variant.id)}" data-spec-id="${escapeHtml(spec.id)}">
                          <input class="character-matrix-input" data-field="prompt" type="text" value="${escapeHtml(cell.prompt || "")}" placeholder="提示词" title="提示词" />
                          <input class="character-matrix-input" data-field="lora_name" type="text" value="${escapeHtml(cell.lora_name || "")}" placeholder="LoRA" title="LoRA 文件" />
                          <input class="character-matrix-input character-matrix-weight" data-field="lora_weight" type="number" min="0" max="2" step="0.01" value="${escapeHtml(weight)}" placeholder="权重" title="LoRA 权重" />
                          <input class="character-matrix-input" data-field="model_override" type="text" value="${escapeHtml(cell.model_override || "")}" placeholder="模型覆盖" title="模型覆盖" />
                        </td>
                      `;
                    }).join("")}
                  </tr>
                `;
              }).join("")}
            </tbody>
          </table>
        </div>
      `;
      const saveBtn = document.querySelector('[data-api-action="save-character-matrix"]');
      if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.textContent = "保存全部修改";
      }
      wrap.querySelectorAll(".character-matrix-input").forEach((input) => {
        input.addEventListener("input", () => {
          if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.textContent = "保存全部修改";
          }
        });
      });
    } catch (error) {
      wrap.innerHTML = `
        <div class="character-spec-editor-error">
          <span>规格矩阵加载失败：${escapeHtml(error.message)}</span>
          <button class="btn small" type="button" data-api-action="retry-character-matrix" data-character-id="${escapeHtml(characterId)}">重新加载</button>
        </div>
      `;
    }
  }

  async function saveCharacterMatrix() {
    const wrap = document.getElementById("character-matrix-wrap");
    const saveBtn = document.querySelector('[data-api-action="save-character-matrix"]');
    if (!wrap) return;
    const cells = wrap.querySelectorAll("td[data-spec-value-id]");
    const updates = [];
    cells.forEach((cell) => {
      const specValueId = cell.dataset.specValueId;
      if (!specValueId) return;
      const fields = {};
      cell.querySelectorAll(".character-matrix-input").forEach((input) => {
        const field = input.dataset.field;
        if (!field) return;
        let value = input.value;
        if (field === "lora_weight") {
          value = value === "" ? null : Number(value);
        }
        fields[field] = value;
      });
      updates.push({ spec_value_id: specValueId, ...fields });
    });
    if (!updates.length) {
      if (typeof showToast === "function") showToast("没有可保存的规格值");
      return;
    }
    if (saveBtn) {
      saveBtn.disabled = true;
      saveBtn.textContent = "正在保存…";
    }
    try {
      const result = await request(API.characterSpecValuesBatch, {
        method: "POST",
        body: JSON.stringify({ updates }),
      });
      if (typeof showToast === "function") showToast(`已保存 ${result.updated || updates.length} 项规格值`);
      if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.textContent = "保存全部修改";
      }
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
      if (saveBtn) {
        saveBtn.disabled = false;
        saveBtn.textContent = "保存全部修改";
      }
    }
  }

  async function renderCharacterDetail(characterId) {
    openCharacterDetailModal();
    const body = document.getElementById("character-detail-modal-body");
    if (body) body.innerHTML = '<div style="padding:24px;text-align:center;color:#8c94a5;">加载中…</div>';
    try {
      const [characterPayload, variantsPayload, specsPayload] = await Promise.all([
        request(API.character(characterId)),
        request(API.characterVariants(characterId)),
        request(API.specs),
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
          ${characterDetailCover(character)}
          <div class="header-name">
            <div class="header-name-text">${escapeHtml(character.name)}</div>
            <div class="header-name-sub">${stats.variant_count} 个形象 · ${specsPayload.total} 个规格 · 已填写 ${stats.spec_filled}/${stats.spec_total}</div>
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

  function bindCharacterTagAddInput(input, characterId) {
    if (!input || input.dataset.bound) return;
    input.dataset.bound = "1";
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        addCharacterTag(characterId, input.value);
      }
    });
  }

  async function addCharacterTag(characterId, rawTag) {
    const tag = String(rawTag || "").trim().replace(/\s+/g, " ");
    if (!tag) return;
    const section = document.querySelector(".character-tags-section");
    if (!section) return;
    let tags = [];
    try {
      tags = JSON.parse(section.dataset.tags || "[]");
      if (!Array.isArray(tags)) tags = [];
    } catch (_) { tags = []; }
    if (tags.length >= 30) {
      if (typeof showToast === "function") showToast("每个人物最多 30 个标签");
      return;
    }
    if (tags.some((item) => item.toLocaleLowerCase() === tag.toLocaleLowerCase())) {
      if (typeof showToast === "function") showToast("标签已存在");
      return;
    }
    tags.push(tag);
    const input = section.querySelector(".character-tag-add-input");
    if (input) input.value = "";
    try {
      await request(API.characterTags(characterId), {
        method: "PUT",
        body: JSON.stringify({ tags }),
      });
      section.dataset.tags = JSON.stringify(tags);
      renderCharacterDetailTags(section);
      if (typeof showToast === "function") showToast(`标签「${tag}」已添加`);
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    }
  }

  async function removeCharacterTag(characterId, tag) {
    const section = document.querySelector(".character-tags-section");
    if (!section) return;
    let tags = [];
    try {
      tags = JSON.parse(section.dataset.tags || "[]");
      if (!Array.isArray(tags)) tags = [];
    } catch (_) { tags = []; }
    tags = tags.filter((item) => item !== tag);
    try {
      await request(API.characterTags(characterId), {
        method: "PUT",
        body: JSON.stringify({ tags }),
      });
      section.dataset.tags = JSON.stringify(tags);
      renderCharacterDetailTags(section);
      if (typeof showToast === "function") showToast(`标签「${tag}」已删除`);
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
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
        <p id="new-project-context">输入项目名称和描述，其他设置以后用到时再配置。</p>
        <form id="new-project-form">
          <label class="label" for="new-project-name">项目名称</label>
          <input id="new-project-name" class="modal-input" name="name" maxlength="80" autocomplete="off" placeholder="例如：海边度假篇" required />
          <label class="label" for="new-project-description">项目描述（可选）</label>
          <textarea id="new-project-description" class="modal-input" name="description" maxlength="500" rows="3" placeholder="简单描述项目主题或目标" style="resize:vertical;min-height:72px;font-family:inherit"></textarea>
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
    modal.dataset.mode = "create";
    delete modal.dataset.projectId;
    const error = modal.querySelector(".modal-error");
    const nameInput = modal.querySelector('input[name="name"]');
    const descInput = modal.querySelector('textarea[name="description"]');
    const title = modal.querySelector("h2");
    const context = modal.querySelector("#new-project-context");
    const submitBtn = modal.querySelector('button[type="submit"]');
    if (title) title.textContent = "新建项目";
    if (context) context.textContent = "输入项目名称和描述，其他设置以后用到时再配置。";
    if (submitBtn) submitBtn.textContent = "创建项目";
    error.textContent = "";
    nameInput.value = "";
    if (descInput) descInput.value = "";
    modal.hidden = false;
    requestAnimationFrame(() => {
      modal.classList.add("show");
      nameInput.focus();
    });
  }

  function openProjectEditModal(projectId, currentName, currentDescription) {
    const modal = ensureProjectModal();
    modal.dataset.mode = "edit";
    modal.dataset.projectId = projectId;
    const error = modal.querySelector(".modal-error");
    const nameInput = modal.querySelector('input[name="name"]');
    const descInput = modal.querySelector('textarea[name="description"]');
    const title = modal.querySelector("h2");
    const context = modal.querySelector("#new-project-context");
    const submitBtn = modal.querySelector('button[type="submit"]');
    if (title) title.textContent = "编辑项目";
    if (context) context.textContent = `修改项目「${currentName}」的名称或描述。`;
    if (submitBtn) submitBtn.textContent = "保存修改";
    error.textContent = "";
    nameInput.value = currentName || "";
    if (descInput) descInput.value = currentDescription || "";
    modal.hidden = false;
    requestAnimationFrame(() => {
      modal.classList.add("show");
      nameInput.focus();
      nameInput.select();
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
    const modal = form.closest(".atelier-modal-backdrop");
    const nameInput = form.querySelector('input[name="name"]');
    const descInput = form.querySelector('textarea[name="description"]');
    const submit = form.querySelector('button[type="submit"]');
    const error = form.querySelector(".modal-error");
    const name = nameInput.value.trim().replace(/\s+/g, " ");
    const description = descInput ? descInput.value.trim() : "";
    if (!name) {
      error.textContent = "请输入项目名称。";
      nameInput.focus();
      return;
    }
    const isEdit = modal.dataset.mode === "edit";
    const projectId = modal.dataset.projectId;
    submit.disabled = true;
    submit.textContent = isEdit ? "正在保存…" : "正在创建…";
    error.textContent = "";
    try {
      if (isEdit && projectId) {
        await request(API.project(projectId), {
          method: "PATCH",
          body: JSON.stringify({ name, description }),
        });
        closeProjectModal();
        await refreshAfterProjectChange();
        if (typeof showToast === "function") showToast(`项目「${name}」已更新`);
      } else {
        await request(API.projects, {
          method: "POST",
          body: JSON.stringify({ name, description }),
        });
        closeProjectModal();
        await refreshAfterProjectChange();
        if (typeof showToast === "function") showToast(`项目「${name}」已创建`);
      }
    } catch (requestError) {
      error.textContent = requestError.message;
      nameInput.focus();
    } finally {
      submit.disabled = false;
      submit.textContent = isEdit ? "保存修改" : "创建项目";
    }
  }

  async function refreshAfterProjectChange() {
    const pageKey = new URLSearchParams(window.location.search).get("page") || "projects";
    if (pageKey === "projects") {
      await loadProjectsList(false);
    } else if (pageKey === "overview") {
      const project = await resolveCurrentProject();
      if (project) await renderProductionOverview(project);
    }
  }

  function ensureProjectCopyModal() {
    let modal = document.getElementById("project-copy-modal");
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "project-copy-modal";
    modal.className = "atelier-modal-backdrop";
    modal.hidden = true;
    modal.innerHTML = `
      <section class="atelier-modal" role="dialog" aria-modal="true" aria-labelledby="project-copy-title">
        <div class="atelier-modal-icon">CP</div>
        <h2 id="project-copy-title">复制项目</h2>
        <p id="project-copy-context">输入新项目名称，将复制项目结构到新项目。</p>
        <form id="project-copy-form">
          <label class="label" for="project-copy-name">新项目名称</label>
          <input id="project-copy-name" class="modal-input" name="name" maxlength="80" autocomplete="off" placeholder="输入新项目名称" required />
          <div class="modal-error" id="project-copy-error" role="alert"></div>
          <div class="modal-actions">
            <button class="btn" type="button" data-api-action="close-project-copy-modal">取消</button>
            <button class="btn primary" type="submit">复制项目</button>
          </div>
        </form>
      </section>
    `;
    document.body.appendChild(modal);
    modal.addEventListener("click", (event) => {
      if (event.target === modal) closeProjectCopyModal();
    });
    modal.querySelector("form").addEventListener("submit", submitProjectCopy);
    return modal;
  }

  function openProjectCopyModal(projectId, currentName) {
    const modal = ensureProjectCopyModal();
    modal.dataset.projectId = projectId;
    const error = modal.querySelector(".modal-error");
    const nameInput = modal.querySelector('input[name="name"]');
    const context = modal.querySelector("#project-copy-context");
    if (context) context.textContent = `将「${currentName}」复制为新项目，可在此基础上修改。`;
    error.textContent = "";
    nameInput.value = `${currentName} 副本`;
    modal.hidden = false;
    requestAnimationFrame(() => {
      modal.classList.add("show");
      nameInput.focus();
      nameInput.select();
    });
  }

  function closeProjectCopyModal() {
    const modal = document.getElementById("project-copy-modal");
    if (!modal) return;
    modal.classList.remove("show");
    window.setTimeout(() => {
      modal.hidden = true;
    }, 150);
  }

  async function submitProjectCopy(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const modal = form.closest(".atelier-modal-backdrop");
    const projectId = modal.dataset.projectId;
    const nameInput = form.querySelector('input[name="name"]');
    const submit = form.querySelector('button[type="submit"]');
    const error = form.querySelector(".modal-error");
    const name = nameInput.value.trim().replace(/\s+/g, " ");
    if (!name) {
      error.textContent = "请输入新项目名称。";
      nameInput.focus();
      return;
    }
    if (!projectId) {
      error.textContent = "未指定要复制的项目。";
      return;
    }
    submit.disabled = true;
    submit.textContent = "正在复制…";
    error.textContent = "";
    try {
      await request(API.projectCopy(projectId), {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      closeProjectCopyModal();
      await refreshAfterProjectChange();
      if (typeof showToast === "function") showToast(`项目已复制为「${name}」`);
    } catch (requestError) {
      error.textContent = requestError.message;
      nameInput.focus();
    } finally {
      submit.disabled = false;
      submit.textContent = "复制项目";
    }
  }

  async function archiveProject(projectId, name) {
    if (!await confirmDialog({
      title: `归档项目「${name}」`,
      message: "归档后项目会从活跃列表移除，可随时恢复。",
      confirmText: "归档",
      danger: false,
    })) {
      return;
    }
    try {
      await request(API.projectArchive(projectId), { method: "POST" });
      await loadProjectsList(false);
      if (typeof showToast === "function") showToast(`项目「${name}」已归档`);
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message);
    }
  }

  async function restoreProject(projectId, name) {
    try {
      await request(API.projectRestore(projectId), { method: "POST" });
      await loadProjectsList(false);
      if (typeof showToast === "function") showToast(`项目「${name}」已恢复`);
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message);
    }
  }

  function projectDeletionImpactMessage(impact, permanent = false) {
    const counts = impact?.counts || {};
    const totals = impact?.totals || {};
    const countLines = [
      `章节 ${Number(counts.chapters) || 0} · 大场景 ${Number(counts.large_scenes) || 0} · 小场景 ${Number(counts.small_scenes) || 0}`,
      `分镜页 ${Number(counts.shot_pages) || 0} · 关联素材 ${Number(counts.linked_materials) || 0} · 人物 ${Number(counts.characters) || 0}`,
      `批次 ${Number(counts.batches) || 0} · 任务 ${Number(counts.tasks) || 0} · 图片实例 ${Number(counts.image_instances) || 0}`,
      `历史记录 ${Number(totals.history) || 0} · 受影响项目数据共 ${Number(totals.affected) || 0} 项`,
    ];
    const warnings = Array.isArray(impact?.warnings) ? impact.warnings : [];
    return [
      permanent ? "永久删除后无法恢复。" : "项目将移入回收站，可以恢复。",
      "",
      ...countLines,
      ...(warnings.length ? ["", ...warnings.map((warning) => `注意：${warning}`)] : []),
    ].join("\n");
  }

  async function loadProjectDeletionImpact(projectId) {
    const payload = await request(`/api/projects/${encodeURIComponent(projectId)}/deletion-impact`);
    return payload.impact || payload;
  }

  async function deleteProject(projectId, name) {
    let impact;
    try {
      impact = await loadProjectDeletionImpact(projectId);
    } catch (requestError) {
      if (typeof showToast === "function") showToast(`无法读取删除影响：${requestError.message}`);
      return;
    }
    if (!await confirmDialog({
      title: `删除项目「${name}」`,
      message: projectDeletionImpactMessage(impact, false),
      confirmText: "移入回收站",
      danger: true,
    })) {
      return;
    }
    try {
      await request(API.project(projectId), { method: "DELETE" });
      await loadProjectsList(false);
      if (typeof showToast === "function") showToast(`项目「${name}」已移入回收站`);
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message);
    }
  }

  async function permanentDeleteProject(projectId, name) {
    let impact;
    try {
      impact = await loadProjectDeletionImpact(projectId);
    } catch (requestError) {
      if (typeof showToast === "function") showToast(`无法读取删除影响：${requestError.message}`);
      return;
    }
    if (!await confirmDialog({
      title: `永久删除「${name}」`,
      message: projectDeletionImpactMessage(impact, true),
      confirmText: "永久删除",
      danger: true,
    })) {
      return;
    }
    if (!await confirmDialog({
      title: `再次确认永久删除「${name}」`,
      message: "这是最后一次确认，删除后无法找回。",
      confirmText: "我确认永久删除",
      danger: true,
    })) {
      return;
    }
    try {
      await request(API.projectPermanent(projectId), { method: "DELETE" });
      await loadProjectsList(false);
      if (typeof showToast === "function") showToast(`项目「${name}」已永久删除`);
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message);
    }
  }

  function openProjectCoverPicker(projectId, name) {
    let input = document.getElementById("project-cover-file-input");
    if (!input) {
      input = document.createElement("input");
      input.type = "file";
      input.id = "project-cover-file-input";
      input.accept = "image/jpeg,image/png,image/webp";
      input.style.display = "none";
      document.body.appendChild(input);
    }
    input.value = "";
    input.onchange = async () => {
      const file = input.files && input.files[0];
      if (!file) return;
      await uploadProjectCover(projectId, name, file);
    };
    input.click();
  }

  async function uploadProjectCover(projectId, name, file) {
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await fetch(API.projectCover(projectId), { method: "POST", body: formData });
      if (!res.ok) {
        let message = `封面上传失败（${res.status}）`;
        try {
          const data = await res.json();
          if (data && data.detail) message = data.detail;
          else if (data && data.error && data.error.message) message = data.error.message;
        } catch (_) { /* keep default */ }
        if (typeof showToast === "function") showToast(message);
        return;
      }
      await loadProjectsList(false);
      if (typeof showToast === "function") showToast(`项目「${name}」封面已更新`);
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message || "封面上传失败，请检查网络。");
    }
  }

  async function removeProjectCover(projectId, name) {
    if (!await confirmDialog({
      title: `移除「${name}」封面`,
      message: "封面将被删除，卡片恢复为首字母占位。",
      confirmText: "移除封面",
      danger: true,
    })) {
      return;
    }
    try {
      await request(API.projectCover(projectId), { method: "DELETE" });
      await loadProjectsList(false);
      if (typeof showToast === "function") showToast(`项目「${name}」封面已移除`);
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message);
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
      await renderProductionStoryCanvasV3(project);
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
      await renderProductionStoryCanvasV3(project);
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
      await renderProductionStoryCanvasV3(project);
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
        <p>输入人物名称。创建后会自动附带一个「默认」形象。</p>
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
    let refMessage = `确定将人物「${name}」移入回收站吗？可随时恢复。`;
    try {
      const refs = await request(API.characterReferences(characterId));
      const projectCount = refs.project_count || 0;
      const pageCount = refs.shot_page_count || 0;
      if (projectCount || pageCount) {
        refMessage = `人物「${name}」被 ${projectCount} 个项目、${pageCount} 个分镜页引用。移入回收站后引用仍保留，但人物不可用。\n确定继续？`;
      }
    } catch (_) {
      // 引用反查失败时不阻塞删除
    }
    const confirmed = await confirmDialog({
      title: "移入回收站",
      message: refMessage,
      confirmText: "移入回收站",
      danger: true,
    });
    if (!confirmed) {
      return;
    }
    try {
      await request(API.character(characterId), { method: "DELETE" });
      await loadCharacters(false);
      if (typeof showToast === "function") showToast(`人物「${name}」已移入回收站`);
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message);
    }
  }

  async function archiveCharacter(characterId, name) {
    if (!await confirmDialog({
      title: `归档人物「${name}」`,
      message: "归档后会从活跃列表移除，可随时恢复。",
      confirmText: "归档",
      danger: false,
    })) {
      return;
    }
    try {
      await request(API.characterArchive(characterId), { method: "POST" });
      await loadCharacters(false);
      if (typeof showToast === "function") showToast(`人物「${name}」已归档`);
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    }
  }

  async function restoreCharacter(characterId, name) {
    try {
      await request(API.characterRestore(characterId), { method: "POST" });
      await loadCharacters(false);
      if (typeof showToast === "function") showToast(`人物「${name}」已恢复`);
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    }
  }

  async function permanentDeleteCharacter(characterId, name) {
    if (!await confirmDialog({
      title: `永久删除「${name}」`,
      message: "永久删除后无法恢复，人物数据和封面将彻底清除。",
      confirmText: "永久删除",
      danger: true,
    })) {
      return;
    }
    if (!await confirmDialog({
      title: `再次确认永久删除「${name}」`,
      message: "这是最后一次确认，删除后无法找回。",
      confirmText: "我确认永久删除",
      danger: true,
    })) {
      return;
    }
    try {
      await request(API.characterPermanent(characterId), { method: "DELETE" });
      await loadCharacters(false);
      if (typeof showToast === "function") showToast(`人物「${name}」已永久删除`);
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    }
  }

  function ensureCharacterCopyModal() {
    let modal = document.getElementById("character-copy-modal");
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "character-copy-modal";
    modal.className = "atelier-modal-backdrop";
    modal.hidden = true;
    modal.innerHTML = `
      <section class="atelier-modal" role="dialog" aria-modal="true" aria-labelledby="character-copy-title">
        <div class="atelier-modal-icon">CP</div>
        <h2 id="character-copy-title">复制人物</h2>
        <p id="character-copy-context">输入新人物名称，将复制人物及全部变体与规格值。</p>
        <form id="character-copy-form">
          <label class="label" for="character-copy-name">新人物名称</label>
          <input id="character-copy-name" class="modal-input" name="new_name" maxlength="80" autocomplete="off" placeholder="输入新人物名称" required />
          <div class="modal-error" id="character-copy-error" role="alert"></div>
          <div class="modal-actions">
            <button class="btn" type="button" data-api-action="close-character-copy-modal">取消</button>
            <button class="btn primary" type="submit">复制人物</button>
          </div>
        </form>
      </section>
    `;
    document.body.appendChild(modal);
    modal.addEventListener("click", (event) => {
      if (event.target === modal) closeCharacterCopyModal();
    });
    modal.querySelector("form").addEventListener("submit", submitCharacterCopy);
    return modal;
  }

  function openCharacterCopyModal(characterId, currentName) {
    const modal = ensureCharacterCopyModal();
    modal.dataset.characterId = characterId;
    modal.dataset.copyTarget = "character";
    delete modal.dataset.variantId;
    const error = modal.querySelector(".modal-error");
    const nameInput = modal.querySelector('input[name="new_name"]');
    const context = modal.querySelector("#character-copy-context");
    const title = modal.querySelector("h2");
    const submitBtn = modal.querySelector('button[type="submit"]');
    if (title) title.textContent = "复制人物";
    if (context) context.textContent = `将「${currentName}」复制为新人物，包含变体与规格值。`;
    if (submitBtn) submitBtn.textContent = "复制人物";
    error.textContent = "";
    nameInput.value = `${currentName} 副本`;
    modal.hidden = false;
    requestAnimationFrame(() => {
      modal.classList.add("show");
      nameInput.focus();
      nameInput.select();
    });
  }

  function openCharacterVariantCopyModal(variantId, currentName) {
    const modal = ensureCharacterCopyModal();
    modal.dataset.variantId = variantId;
    modal.dataset.copyTarget = "variant";
    delete modal.dataset.characterId;
    const error = modal.querySelector(".modal-error");
    const nameInput = modal.querySelector('input[name="new_name"]');
    const context = modal.querySelector("#character-copy-context");
    const title = modal.querySelector("h2");
    const submitBtn = modal.querySelector('button[type="submit"]');
    if (title) title.textContent = "复制形象";
    if (context) context.textContent = `将「${currentName}」复制为新形象，并保留规格内容。`;
    if (submitBtn) submitBtn.textContent = "复制形象";
    error.textContent = "";
    nameInput.value = `${currentName} 副本`;
    modal.hidden = false;
    requestAnimationFrame(() => {
      modal.classList.add("show");
      nameInput.focus();
      nameInput.select();
    });
  }

  function closeCharacterCopyModal() {
    const modal = document.getElementById("character-copy-modal");
    if (!modal) return;
    modal.classList.remove("show");
    window.setTimeout(() => {
      modal.hidden = true;
    }, 150);
  }

  async function submitCharacterCopy(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const modal = form.closest(".atelier-modal-backdrop");
    const nameInput = form.querySelector('input[name="new_name"]');
    const submit = form.querySelector('button[type="submit"]');
    const error = form.querySelector(".modal-error");
    const name = nameInput.value.trim().replace(/\s+/g, " ");
    if (!name) {
      error.textContent = "请输入新名称。";
      nameInput.focus();
      return;
    }
    submit.disabled = true;
    submit.textContent = "正在复制…";
    error.textContent = "";
    try {
      const target = modal.dataset.copyTarget;
      if (target === "variant") {
        const variantId = modal.dataset.variantId;
        if (!variantId) {
          error.textContent = "未指定要复制的形象。";
          return;
        }
        await request(API.characterVariantCopy(variantId), {
          method: "POST",
          body: JSON.stringify({ new_name: name }),
        });
        closeCharacterCopyModal();
        await refreshCharacterDetail();
        if (typeof showToast === "function") showToast(`形象已复制为「${name}」`);
      } else {
        const characterId = modal.dataset.characterId;
        if (!characterId) {
          error.textContent = "未指定要复制的人物。";
          return;
        }
        await request(API.characterCopy(characterId), {
          method: "POST",
          body: JSON.stringify({ new_name: name }),
        });
        closeCharacterCopyModal();
        await loadCharacters(false);
        if (typeof showToast === "function") showToast(`人物已复制为「${name}」`);
      }
    } catch (requestError) {
      error.textContent = requestError.message;
      nameInput.focus();
    } finally {
      submit.disabled = false;
      submit.textContent = modal.dataset.copyTarget === "variant" ? "复制形象" : "复制人物";
    }
  }

  function openCharacterCoverPicker(characterId, name) {
    let input = document.getElementById("character-cover-file-input");
    if (!input) {
      input = document.createElement("input");
      input.type = "file";
      input.id = "character-cover-file-input";
      input.accept = "image/jpeg,image/png,image/webp";
      input.style.display = "none";
      document.body.appendChild(input);
    }
    input.value = "";
    input.onchange = async () => {
      const file = input.files && input.files[0];
      if (!file) return;
      await uploadCharacterCover(characterId, name, file);
    };
    input.click();
  }

  async function uploadCharacterCover(characterId, name, file) {
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await fetch(API.characterCover(characterId), { method: "POST", body: formData });
      if (!res.ok) {
        let message = `封面上传失败（${res.status}）`;
        try {
          const data = await res.json();
          if (data && data.detail) message = data.detail;
          else if (data && data.error && data.error.message) message = data.error.message;
        } catch (_) { /* keep default */ }
        if (typeof showToast === "function") showToast(message);
        return;
      }
      await refreshCharacterDetail();
      if (typeof showToast === "function") showToast(`人物「${name}」封面已更新`);
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message || "封面上传失败，请检查网络。");
    }
  }

  async function removeCharacterCover(characterId, name) {
    if (!await confirmDialog({
      title: `移除「${name}」封面`,
      message: "封面将被删除，恢复为首字母占位。",
      confirmText: "移除封面",
      danger: true,
    })) {
      return;
    }
    try {
      await request(API.characterCover(characterId), { method: "DELETE" });
      await refreshCharacterDetail();
      if (typeof showToast === "function") showToast(`人物「${name}」封面已移除`);
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message);
    }
  }

  async function deleteCharacterVariant(variantId, name, isDefault) {
    if (isDefault) {
      if (typeof showToast === "function") showToast("默认形象不可删除");
      return;
    }
    if (!await confirmDialog({
      title: `删除形象「${name}」`,
      message: "此操作无法撤销。",
      confirmText: "删除",
      danger: true,
    })) {
      return;
    }
    try {
      await request(API.characterVariant(variantId), { method: "DELETE" });
      await refreshCharacterDetail();
      if (typeof showToast === "function") showToast(`形象「${name}」已删除`);
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message);
    }
  }

  async function archiveCharacterVariant(variantId, name) {
    try {
      await request(API.characterVariantArchive(variantId), { method: "POST" });
      await refreshCharacterDetail();
      if (typeof showToast === "function") showToast(`变体「${name}」已归档`);
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    }
  }

  async function restoreCharacterVariant(variantId, name) {
    try {
      await request(API.characterVariantRestore(variantId), { method: "POST" });
      await refreshCharacterDetail();
      if (typeof showToast === "function") showToast(`变体「${name}」已恢复`);
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    }
  }

  function openVariantPreviewPicker(variantId, name) {
    let input = document.getElementById("variant-preview-file-input");
    if (!input) {
      input = document.createElement("input");
      input.type = "file";
      input.id = "variant-preview-file-input";
      input.accept = "image/jpeg,image/png,image/webp";
      input.style.display = "none";
      document.body.appendChild(input);
    }
    input.value = "";
    input.onchange = async () => {
      const file = input.files && input.files[0];
      if (!file) return;
      await uploadVariantPreview(variantId, name, file);
    };
    input.click();
  }

  async function uploadVariantPreview(variantId, name, file) {
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await fetch(API.characterVariantPreview(variantId), { method: "POST", body: formData });
      if (!res.ok) {
        let message = `预览图上传失败（${res.status}）`;
        try {
          const data = await res.json();
          if (data && data.detail) message = data.detail;
          else if (data && data.error && data.error.message) message = data.error.message;
        } catch (_) { /* keep default */ }
        if (typeof showToast === "function") showToast(message);
        return;
      }
      await refreshCharacterDetail();
      if (typeof showToast === "function") showToast(`变体「${name}」预览图已更新`);
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message || "预览图上传失败，请检查网络。");
    }
  }

  async function removeVariantPreview(variantId) {
    if (!await confirmDialog({
      title: "移除变体预览图",
      message: "预览图将被删除。",
      confirmText: "移除预览",
      danger: true,
    })) {
      return;
    }
    try {
      await request(API.characterVariantPreview(variantId), { method: "DELETE" });
      await refreshCharacterDetail();
      if (typeof showToast === "function") showToast("变体预览图已移除");
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message);
    }
  }

  async function persistCharacterVariantOrder(characterId, variantIds) {
    if (!characterId || !variantIds.length) return;
    await request(API.characterVariantsReorder(characterId), {
      method: "PUT",
      body: JSON.stringify({ variant_ids: variantIds }),
    });
    await refreshCharacterDetail();
    if (typeof showToast === "function") showToast("形象顺序已更新");
  }

  async function reorderCharacterVariants(characterId, variantId, direction) {
    const modal = document.getElementById("character-detail-modal");
    if (!modal || modal.hidden) return;
    const items = [...modal.querySelectorAll(".variant-tabs .variant-tab[data-variant-id]")];
    const index = items.findIndex((item) => item.dataset.variantId === variantId);
    if (index < 0) return;
    const swapIndex = direction === "up" ? index - 1 : index + 1;
    if (swapIndex < 0 || swapIndex >= items.length) return;
    const variantIds = items.map((item) => item.dataset.variantId);
    [variantIds[index], variantIds[swapIndex]] = [variantIds[swapIndex], variantIds[index]];
    try {
      await persistCharacterVariantOrder(characterId, variantIds);
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    }
  }

  let characterVariantDragState = null;

  function initCharacterVariantDrag() {
    document.addEventListener("dragstart", (event) => {
      const tab = event.target.closest(".variant-tab[data-variant-id]");
      const tabs = tab?.closest(".variant-tabs[data-character-id]");
      if (!tab || !tabs) return;
      characterVariantDragState = {
        tab,
        tabs,
        characterId: tabs.dataset.characterId,
        originalIds: [...tabs.querySelectorAll(".variant-tab[data-variant-id]")].map((item) => item.dataset.variantId),
      };
      tab.classList.add("dragging");
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", tab.dataset.variantId);
    });

    document.addEventListener("dragover", (event) => {
      const state = characterVariantDragState;
      const tabs = event.target.closest(".variant-tabs[data-character-id]");
      if (!state || tabs !== state.tabs) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
      const target = event.target.closest(".variant-tab[data-variant-id]");
      const addButton = tabs.querySelector(".variant-tab-add");
      if (!target || target === state.tab) {
        if (!target && addButton) tabs.insertBefore(state.tab, addButton);
        return;
      }
      const rect = target.getBoundingClientRect();
      const insertAfter = event.clientX > rect.left + rect.width / 2;
      tabs.insertBefore(state.tab, insertAfter ? target.nextSibling : target);
    });

    document.addEventListener("drop", async (event) => {
      const state = characterVariantDragState;
      const tabs = event.target.closest(".variant-tabs[data-character-id]");
      if (!state || tabs !== state.tabs) return;
      event.preventDefault();
      const variantIds = [...tabs.querySelectorAll(".variant-tab[data-variant-id]")].map((item) => item.dataset.variantId);
      state.tab.classList.remove("dragging");
      characterVariantDragState = null;
      if (variantIds.join("|") === state.originalIds.join("|")) return;
      try {
        await persistCharacterVariantOrder(state.characterId, variantIds);
      } catch (error) {
        await refreshCharacterDetail();
        if (typeof showToast === "function") showToast(error.message);
      }
    });

    document.addEventListener("dragend", () => {
      if (!characterVariantDragState) return;
      characterVariantDragState.tab.classList.remove("dragging");
      characterVariantDragState = null;
    });
  }

  async function refreshExpandedOrAll() {
    const modal = document.getElementById("character-detail-modal");
    if (modal && !modal.hidden) {
      const scroll = document.getElementById("character-detail-modal-scroll");
      const characterId = scroll && scroll.querySelector("[data-character-id]")?.dataset.characterId;
      if (characterId) {
        await renderCharacterDetail(characterId);
        return;
      }
    }
    await loadCharacters(false);
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
    "small-scene": "小场景",
    character: "人物",
    "character-variant": "形象",
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
      case "small-scene":
        return `/api/small-scenes/${id}`;
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
    if (type === "chapter" || type === "large-scene" || type === "small-scene") {
      const project = await resolveCurrentProject();
      await renderProductionStoryCanvasV3(project);
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
      await renderProductionStoryCanvasV3(project);
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
      await renderProductionStoryCanvasV3(project);
      if (typeof showToast === "function") showToast(`大场景「${name}」已删除`);
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message);
    }
  }

  async function deleteSmallScene(smallSceneId, name) {
    if (!await confirmDialog({
      title: `删除小场景「${name}」`,
      message: "其中的场景页、素材关联和页面映射也会一并删除，此操作无法撤销。",
      confirmText: "删除"
    })) {
      return;
    }
    try {
      await request(`/api/small-scenes/${smallSceneId}`, { method: "DELETE" });
      const project = await resolveCurrentProject();
      await renderProductionStoryCanvasV3(project);
      if (typeof showToast === "function") showToast(`小场景「${name}」已删除`);
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
    menu.dataset.contextCharacterId = data.characterId || "";
    const list = menu.querySelector(".structure-context-menu-list");
    if (list) {
      if (type === "chapter") {
        list.innerHTML = `
          <li class="structure-context-menu-item" data-menu-action="add-large-scene" role="menuitem" tabindex="0">添加大场景</li>
          <li class="structure-context-menu-item" data-menu-action="rename" role="menuitem" tabindex="0">改名</li>
          <li class="structure-context-menu-item danger" data-menu-action="delete" role="menuitem" tabindex="0">删除</li>
        `;
      } else if (type === "large-scene") {
        list.innerHTML = `
          <li class="structure-context-menu-item" data-menu-action="add-small-scene" role="menuitem" tabindex="0">添加小场景</li>
          <li class="structure-context-menu-item" data-menu-action="rename" role="menuitem" tabindex="0">改名</li>
          <li class="structure-context-menu-item danger" data-menu-action="delete" role="menuitem" tabindex="0">删除</li>
        `;
      } else if (type === "small-scene") {
        list.innerHTML = `
          <li class="structure-context-menu-item" data-menu-action="open-small-scene" role="menuitem" tabindex="0">打开小场景画布</li>
          <li class="structure-context-menu-item" data-menu-action="rename" role="menuitem" tabindex="0">改名</li>
          <li class="structure-context-menu-item danger" data-menu-action="delete" role="menuitem" tabindex="0">删除</li>
        `;
      } else if (type === "character-variant") {
        list.innerHTML = `
          <li class="structure-context-menu-item" data-menu-action="rename" role="menuitem" tabindex="0">改名</li>
          <li class="structure-context-menu-item" data-menu-action="copy" role="menuitem" tabindex="0">复制</li>
          <li class="structure-context-menu-item" data-menu-action="move-up" role="menuitem" tabindex="0">上移</li>
          <li class="structure-context-menu-item" data-menu-action="move-down" role="menuitem" tabindex="0">下移</li>
          <li class="structure-context-menu-item danger" data-menu-action="delete" role="menuitem" tabindex="0">删除</li>
        `;
      } else {
        list.innerHTML = `
          <li class="structure-context-menu-item" data-menu-action="rename" role="menuitem" tabindex="0">改名</li>
          <li class="structure-context-menu-item danger" data-menu-action="delete" role="menuitem" tabindex="0">删除</li>
        `;
      }
    }
    const menuWidth = 168;
    const menuHeight = Math.max(48, (list?.children.length || 1) * 38 + 12);
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
      menu.dataset.contextCharacterId = "";
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
    if (type === "small-scene") {
      showContextMenu(
        "small-scene",
        {
          id: trigger.dataset.smallSceneId,
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
      const tabs = trigger.closest(".variant-tabs[data-character-id]");
      showContextMenu(
        "character-variant",
        {
          id: trigger.dataset.variantId,
          name: trigger.dataset.name,
          isDefault: trigger.dataset.isDefault === "1",
          characterId: tabs?.dataset.characterId || "",
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
  initCharacterVariantDrag();

  // ── 大场景拖动交互 ─────────────────────────────────────────
  let dragState = null;

  function initLargeSceneDrag() {
    document.addEventListener("dragstart", (event) => {
      const handle = event.target.closest?.(
        "[data-large-scene-drag-handle][draggable='true'], .large-scene-block[draggable='true']"
      );
      if (!handle) return;
      const item = handle.closest?.("[data-large-scene-drag-item]") || handle;
      const largeSceneId = handle.dataset.largeSceneId || item.dataset.largeSceneId;
      const sourceChapterId = handle.dataset.chapterId || item.dataset.chapterId;
      if (!largeSceneId || !sourceChapterId) return;
      dragState = {
        largeSceneId,
        sourceChapterId,
        handle,
        item,
      };
      item.classList.add("dragging");
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", largeSceneId);
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
      dragState.item?.classList.remove("dragging");
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
      const cards = Array.from(dropZone.children).filter((child) =>
        !child.classList.contains("dragging") &&
        (
          child.matches("[data-large-scene-drag-item]") ||
          child.matches(".large-scene-block")
        )
      );
      let insertIndex = cards.length;
      let insertBeforeEl = null;
      const axis = dropZone.dataset.dropAxis || "horizontal";
      for (let i = 0; i < cards.length; i++) {
        const rect = cards[i].getBoundingClientRect();
        const before = axis === "vertical"
          ? event.clientY < rect.top + rect.height / 2
          : axis === "grid"
            ? (
                event.clientY < rect.top + rect.height / 2 ||
                (
                  event.clientY <= rect.bottom &&
                  event.clientX < rect.left + rect.width / 2
                )
              )
            : event.clientX < rect.left + rect.width / 2;
        if (before) {
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
        const addCard = Array.from(dropZone.children).find((child) =>
          child.matches(".large-scene-add-card, .story-large-scene-add")
        );
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
      dragState.item?.classList.remove("dragging");
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
        await renderProductionStoryCanvasV3(project);
        if (typeof showToast === "function") showToast("大场景已移动");
      } catch (requestError) {
        // Restore canvas to last server state
        const project = await resolveCurrentProject();
        await renderProductionStoryCanvasV3(project);
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

  function updateLargeSceneDropIndicator(dropZone, clientX, clientY, draggedItem) {
    const targetChapterId = dropZone?.dataset.chapterId;
    if (!targetChapterId) return null;
    const cards = Array.from(dropZone.children).filter((child) =>
      child !== draggedItem &&
      !child.classList.contains("dragging") &&
      (
        child.matches("[data-large-scene-drag-item]") ||
        child.matches(".large-scene-block")
      )
    );
    let insertIndex = cards.length;
    let insertBeforeEl = null;
    const axis = dropZone.dataset.dropAxis || "horizontal";
    for (let index = 0; index < cards.length; index += 1) {
      const hitTarget = axis === "vertical"
        ? cards[index].querySelector(":scope > [data-large-scene-drag-handle]") || cards[index]
        : cards[index];
      const rect = hitTarget.getBoundingClientRect();
      const before = axis === "vertical"
        ? clientY < rect.top + rect.height / 2
        : axis === "grid"
          ? (
              clientY < rect.top + rect.height / 2 ||
              (clientY <= rect.bottom && clientX < rect.left + rect.width / 2)
            )
          : clientX < rect.left + rect.width / 2;
      if (before) {
        insertIndex = index;
        insertBeforeEl = cards[index];
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
      const addCard = Array.from(dropZone.children).find((child) =>
        child.matches(".large-scene-add-card, .story-large-scene-add")
      );
      if (addCard) dropZone.insertBefore(indicator, addCard);
      else dropZone.appendChild(indicator);
    }
    return { targetChapterId, targetIndex: insertIndex };
  }

  let pointerLargeSceneDrag = null;
  let suppressLargeSceneClickUntil = 0;

  async function commitLargeScenePointerMove(state) {
    if (!state?.targetChapterId) return;
    try {
      await request(`/api/large-scenes/${state.largeSceneId}/move`, {
        method: "POST",
        body: JSON.stringify({
          target_chapter_id: state.targetChapterId,
          target_sort_order: Number(state.targetIndex || 0) + 1,
        }),
      });
      const project = await resolveCurrentProject();
      await renderProductionStoryCanvasV3(project);
      if (typeof showToast === "function") showToast("大场景已移动");
    } catch (requestError) {
      const project = await resolveCurrentProject();
      await renderProductionStoryCanvasV3(project);
      if (typeof showToast === "function") showToast("移动失败：" + requestError.message);
    }
  }

  function finishLargeScenePointerDrag() {
    const state = pointerLargeSceneDrag;
    if (!state) return null;
    state.item?.classList.remove("dragging");
    try {
      if (state.handle?.hasPointerCapture?.(state.pointerId)) {
        state.handle.releasePointerCapture(state.pointerId);
      }
    } catch (_) {
      // Pointer capture may already be released by the browser.
    }
    document.body.classList.remove("is-dragging-large-scene");
    clearDropIndicators();
    pointerLargeSceneDrag = null;
    return state;
  }

  function initLargeScenePointerDrag() {
    document.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      const handle = event.target.closest?.("[data-large-scene-drag-handle]");
      if (!handle) return;
      const item = handle.closest("[data-large-scene-drag-item]");
      const largeSceneId = handle.dataset.largeSceneId || item?.dataset.largeSceneId;
      const sourceChapterId = handle.dataset.chapterId || item?.dataset.chapterId;
      if (!item || !largeSceneId || !sourceChapterId) return;
      pointerLargeSceneDrag = {
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        largeSceneId,
        sourceChapterId,
        handle,
        item,
        started: false,
        targetChapterId: "",
        targetIndex: 0,
      };
      handle.setPointerCapture?.(event.pointerId);
    });

    document.addEventListener("pointermove", (event) => {
      const state = pointerLargeSceneDrag;
      if (!state || state.pointerId !== event.pointerId) return;
      if (!state.started) {
        if (Math.hypot(event.clientX - state.startX, event.clientY - state.startY) < 6) return;
        state.started = true;
        state.item.classList.add("dragging");
        document.body.classList.add("is-dragging-large-scene");
      }
      event.preventDefault();
      const target = document.elementFromPoint(event.clientX, event.clientY);
      const dropZone = target?.closest?.("[data-drop-zone]");
      const placement = updateLargeSceneDropIndicator(
        dropZone,
        event.clientX,
        event.clientY,
        state.item
      );
      state.targetChapterId = placement?.targetChapterId || "";
      state.targetIndex = placement?.targetIndex || 0;
      if (!placement) clearDropIndicators();
    }, { passive: false });

    document.addEventListener("pointerup", async (event) => {
      const state = pointerLargeSceneDrag;
      if (!state || state.pointerId !== event.pointerId) return;
      const wasDragging = state.started;
      const completed = finishLargeScenePointerDrag();
      if (!wasDragging) return;
      event.preventDefault();
      suppressLargeSceneClickUntil = Date.now() + 250;
      await commitLargeScenePointerMove(completed);
    });

    document.addEventListener("pointercancel", (event) => {
      if (pointerLargeSceneDrag?.pointerId !== event.pointerId) return;
      finishLargeScenePointerDrag();
    });

    document.addEventListener("click", (event) => {
      if (Date.now() > suppressLargeSceneClickUntil) return;
      if (!event.target.closest?.("[data-large-scene-drag-handle]")) return;
      event.preventDefault();
      event.stopImmediatePropagation();
    }, true);
  }

  initLargeSceneDrag();
  initLargeScenePointerDrag();

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

  async function refreshStoryOperationControls(projectId) {
    const undoButton = document.querySelector(`[data-api-action="undo-operation"][data-project-id="${CSS.escape(projectId)}"]`);
    const redoButton = document.querySelector(`[data-api-action="redo-operation"][data-project-id="${CSS.escape(projectId)}"]`);
    const recent = document.getElementById("story-operation-recent");
    if (!undoButton || !redoButton) return;
    try {
      const payload = await request(API.projectOperations(projectId));
      const operations = payload.items || [];
      const redoKey = `atelier-story-redo-${projectId}`;
      let pendingRedoId = window.sessionStorage.getItem(redoKey);
      if (pendingRedoId && operations[0] && String(operations[0].id) !== String(pendingRedoId)) {
        window.sessionStorage.removeItem(redoKey);
        pendingRedoId = null;
      }
      undoButton.disabled = !operations.length || Boolean(pendingRedoId);
      redoButton.disabled = !pendingRedoId;
      const latest = operations[0];
      const operationLabels = {
        move: "移动",
        create: "新建",
        delete: "删除",
        rename: "编辑",
        reorder: "排序",
        map: "建立映射",
        unmap: "取消映射",
      };
      const entityLabels = {
        chapter: "章节",
        large_scene: "大场景",
        small_scene: "小场景",
        shot_page: "场景页",
        branch: "分支",
        mapping: "素材映射",
      };
      if (recent) {
        recent.textContent = latest
          ? `最近操作：${operationLabels[latest.operation_type] || latest.operation_type} ${entityLabels[latest.entity_type] || latest.entity_type}`
          : "最近操作：无";
      }
    } catch (error) {
      undoButton.disabled = true;
      redoButton.disabled = true;
      if (recent) recent.textContent = "操作历史读取失败";
    }
  }

  // ==================== 阶段 3：批量配置与任务中心 ====================

  const batchUiState = {
    project: null,
    drafts: [],
    batches: [],
    workflows: [],
    tree: null,
    activeDraftId: "",
  };

  const taskUiState = {
    project: null,
    batches: [],
    tasks: [],
    summary: {},
    status: "all",
    batchId: "",
    hasError: false,
    runnerActive: false,
    runnerBatchId: "",
    currentProgress: null,
    refreshTimer: null,
  };

  function stage3Date(value) {
    if (!value) return "—";
    const date = new Date(value);
    return Number.isNaN(date.getTime())
      ? "—"
      : date.toLocaleString("zh-CN", {
          month: "2-digit",
          day: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
        });
  }

  function stage3Status(statusValue) {
    const labels = {
      pending: ["等待开始", "orange"],
      running: ["运行中", "blue"],
      retrying: ["等待重试", "orange"],
      paused: ["已暂停", ""],
      completed: ["已完成", "green"],
      cancelled: ["已取消", ""],
      failed: ["失败", "red"],
      submitted: ["已提交", "blue"],
      unknown: ["状态未知", "orange"],
    };
    const current = labels[statusValue] || [statusValue || "未知", ""];
    return `<span class="status ${current[1]}"><i class="dot"></i>${escapeHtml(current[0])}</span>`;
  }

  function stage3Navigate(pageKey, extra = {}) {
    const params = new URLSearchParams();
    params.set("page", pageKey);
    const projectId = extra.project || batchUiState.project?.id || taskUiState.project?.id;
    if (projectId) params.set("project", projectId);
    Object.entries(extra).forEach(([key, value]) => {
      if (key !== "project" && value) params.set(key, value);
    });
    window.location.search = `?${params.toString()}`;
  }

  function batchTargetOptions(project, tree, selectedScope, selectedScopeId) {
    const selected = (scope, id) =>
      scope === selectedScope && String(id || "") === String(selectedScopeId || "")
        ? " selected"
        : "";
    const options = [
      `<option value="project|"${selected("project", null)}>整个项目 · ${escapeHtml(project.name)}</option>`,
    ];
    const chapters = Array.isArray(tree?.chapters) ? tree.chapters : [];
    chapters.forEach((chapter) => {
      options.push(
        `<option value="chapter|${escapeHtml(chapter.id)}"${selected("chapter", chapter.id)}>章节 · ${escapeHtml(chapter.name)}</option>`
      );
      (chapter.large_scenes || []).forEach((largeScene) => {
        options.push(
          `<option value="large_scene|${escapeHtml(largeScene.id)}"${selected("large_scene", largeScene.id)}>　大场景 · ${escapeHtml(largeScene.name)}</option>`
        );
        (largeScene.branches || []).forEach((branch) => {
          options.push(
            `<option value="branch|${escapeHtml(branch.id)}"${selected("branch", branch.id)}>　　分支 · ${escapeHtml(branch.name)}</option>`
          );
        });
        (largeScene.small_scenes || []).forEach((smallScene) => {
          options.push(
            `<option value="small_scene|${escapeHtml(smallScene.id)}"${selected("small_scene", smallScene.id)}>　　小场景 · ${escapeHtml(smallScene.name)}</option>`
          );
          (smallScene.branches || []).forEach((branch) => {
            options.push(
              `<option value="branch|${escapeHtml(branch.id)}"${selected("branch", branch.id)}>　　　分支 · ${escapeHtml(branch.name)}</option>`
            );
          });
          (smallScene.pages || []).forEach((page) => {
            options.push(
              `<option value="shot_pages|${escapeHtml(page.id)}"${selected("shot_pages", page.id)}>　　　页面 · ${escapeHtml(page.name || page.title || "未命名页")}</option>`
            );
          });
        });
      });
    });
    return options.join("");
  }

  function batchWorkflowOptions(workflows, config) {
    const currentWorkflow = config?.workflow_id || "";
    const currentVersion = config?.workflow_version_id || "";
    const options = [
      `<option value="|"${currentWorkflow ? "" : " selected"}>使用项目默认工作流</option>`,
    ];
    workflows.forEach((workflow) => {
      const versionId = workflow.current_version_id || "";
      const isSelected =
        workflow.id === currentWorkflow &&
        (!currentVersion || versionId === currentVersion);
      const versionText = versionId ? "已发布版本" : "未发布";
      options.push(
        `<option value="${escapeHtml(workflow.id)}|${escapeHtml(versionId)}"${isSelected ? " selected" : ""}${versionId ? "" : " disabled"}>${escapeHtml(workflow.name)} · ${versionText}</option>`
      );
    });
    return options.join("");
  }

  function batchPreviewMarkup(preview) {
    if (!preview) {
      return `
        <section class="stage3-preview-empty">
          <span>PREVIEW</span>
          <h3>还没有检查跑图列表</h3>
          <p>设置页面范围、图片数量和工作流后，点击“检查跑图列表”。这里会显示实际任务、阻塞项和提醒。</p>
        </section>
      `;
    }
    const summary = preview.summary || {};
    const items = Array.isArray(preview.items) ? preview.items : [];
    const blockers = Array.isArray(preview.blocking_errors) ? preview.blocking_errors : [];
    const warnings = Array.isArray(preview.warnings) ? preview.warnings : [];
    const estimatedTasks = items.reduce(
      (total, item) => total + (Number(item.instance_count) || 1),
      0
    );
    const issueMarkup = [...blockers.map((item) => ({ ...item, level: "blocker" })), ...warnings.map((item) => ({ ...item, level: "warning" }))]
      .slice(0, 20)
      .map(
        (item) => `
          <div class="stage3-issue ${item.level}">
            <span>${item.level === "blocker" ? "!" : "△"}</span>
            <div><strong>${item.level === "blocker" ? "阻塞" : "警告"}</strong><p>${escapeHtml(item.message || item.type || "未说明")}</p></div>
          </div>
        `
      )
      .join("");
    const rows = items
      .slice(0, 200)
      .map((item) => {
        const effective = item.effective_config || {};
        const size =
          effective.width && effective.height
            ? `${effective.width} × ${effective.height}`
            : "工作流默认";
        return `
          <tr>
            <td><strong>${escapeHtml(item.shot_page_title || item.sort_key || "未命名页")}</strong><small>${escapeHtml([item.chapter_name, item.large_scene_name, item.small_scene_name].filter(Boolean).join(" / "))}</small></td>
            <td>${escapeHtml(item.branch_name || "主线")}</td>
            <td>${escapeHtml(item.workflow_label || item.workflow_version_id || "未设置")}</td>
            <td>${escapeHtml(size)}</td>
            <td>${Number(item.instance_count) || 1}</td>
            <td>${escapeHtml(item.seed_strategy || "fixed")}${item.seed_value === null || item.seed_value === undefined ? "" : `<small>${escapeHtml(item.seed_value)}</small>`}</td>
          </tr>
        `;
      })
      .join("");
    return `
      <div class="stage3-metrics">
        <div><span>范围页面</span><strong>${Number(summary.total_pages) || 0}</strong></div>
        <div><span>可运行项</span><strong>${items.length}</strong></div>
        <div><span>预计任务</span><strong>${estimatedTasks}</strong></div>
        <div><span>跳过</span><strong>${Number(summary.skipped_pages) || 0}</strong></div>
        <div class="${blockers.length ? "danger" : ""}"><span>阻塞</span><strong>${blockers.length}</strong></div>
        <div class="${warnings.length ? "warning" : ""}"><span>警告</span><strong>${warnings.length}</strong></div>
      </div>
      ${!items.length
        ? '<div class="stage3-empty-preview-note">当前范围没有可创建的任务。请先在剧本画布添加场景页，或调整页面范围。</div>'
        : issueMarkup
          ? `<div class="stage3-issues">${issueMarkup}</div>`
          : '<div class="stage3-success-note">完整性检查通过，没有阻塞项或警告。</div>'}
      <div class="stage3-table-wrap">
        <table class="table stage3-table">
          <thead><tr><th>页面与来源</th><th>分支</th><th>工作流</th><th>尺寸</th><th>实例</th><th>种子</th></tr></thead>
          <tbody>${rows || '<tr><td colspan="6"><div class="stage3-empty-row">当前范围没有可运行页面。</div></td></tr>'}</tbody>
        </table>
      </div>
      ${items.length > 200 ? `<div class="stage3-table-note">当前显示前 200 项，共 ${items.length} 项；创建任务时会包含全部项目。</div>` : ""}
    `;
  }

  function batchFlowSteps(activeStep = 1) {
    const steps = [
      ["1", "选择页面", "决定哪些分镜页需要跑图"],
      ["2", "设置生成", "选择工作流和每页图片数"],
      ["3", "检查列表", "确认实际任务及阻塞项"],
      ["4", "创建任务", "前往任务中心后手动开始"],
    ];
    return `<div class="stage3-flow-steps">${steps.map(([number, title, note], index) => `<div class="stage3-flow-step ${index + 1 < activeStep ? "done" : index + 1 === activeStep ? "active" : ""}"><span>${number}</span><div><strong>${title}</strong><small>${note}</small></div></div>`).join("")}</div>`;
  }

  function batchDraftWorkspace(project, draft) {
    const config = draft.config || {};
    const preview = draft.preview_stale ? null : draft.preview;
    const activeStep = preview?.items?.length ? 3 : 2;
    return `
      <div class="stage3-layout">
        <aside class="panel stage3-sidebar">
          <div class="panel-header">
            <div><div class="panel-title">未开始的批次</div><div class="panel-sub">可以保存并稍后继续设置</div></div>
            <button class="btn small" type="button" data-api-action="batch-new-draft">新建批次</button>
          </div>
          <label class="label" for="batch-draft-select">当前配置</label>
          <select class="field stage3-control" id="batch-draft-select">
            ${batchUiState.drafts.map((item) => `<option value="${escapeHtml(item.id)}"${item.id === draft.id ? " selected" : ""}>${escapeHtml(item.name || "未命名跑图批次")}</option>`).join("")}
          </select>
          <div class="stage3-sidebar-actions">
            <button class="btn small danger-soft" type="button" data-api-action="batch-delete-draft" data-draft-id="${escapeHtml(draft.id)}">删除配置</button>
          </div>
          <div class="stage3-batch-list">
            <div class="label">已创建的任务批次</div>
            ${batchUiState.batches.length
              ? batchUiState.batches.slice(0, 20).map((batch) => `
                <button type="button" class="stage3-batch-card" data-api-action="open-task-center" data-batch-id="${escapeHtml(batch.id)}">
                  <span>${stage3Status(batch.status)}</span>
                  <strong>${escapeHtml(batch.name || "未命名批次")}</strong>
                  <small>${Number(batch.item_count) || 0} 项 · ${stage3Date(batch.created_at)}</small>
                </button>`).join("")
              : '<div class="stage3-sidebar-empty">还没有创建任务</div>'}
          </div>
        </aside>
        <main class="stage3-main">
          ${batchFlowSteps(activeStep)}
          <section class="panel stage3-config-panel">
            <div class="panel-header">
              <div><div class="panel-title">选择页面与生成方式</div><div class="panel-sub">这里的修改只保存配置，不会立即开始跑图</div></div>
              <span class="status ${draft.preview_stale ? "orange" : "green"}"><i class="dot"></i>${draft.preview_stale ? "需要重新检查" : "列表已检查"}</span>
            </div>
            <div class="stage3-form-grid">
              <div class="stage3-span-2">
                <label class="label" for="batch-name">批次名称</label>
                <input class="field stage3-control" id="batch-name" maxlength="120" value="${escapeHtml(draft.name || "")}" />
              </div>
              <div class="stage3-span-2">
                <label class="label" for="batch-target">要跑哪些页面</label>
                <select class="field stage3-control" id="batch-target">${batchTargetOptions(project, batchUiState.tree, draft.scope, draft.scope_id)}</select>
              </div>
              <div>
                <label class="label" for="batch-instance-count">每页生成图片数</label>
                <input class="field stage3-control" id="batch-instance-count" type="number" min="1" max="100" value="${Number(config.instance_count) || 1}" />
              </div>
              <div class="stage3-span-3">
                <label class="label" for="batch-workflow">使用的 ComfyUI 工作流</label>
                <select class="field stage3-control" id="batch-workflow">${batchWorkflowOptions(batchUiState.workflows, config)}</select>
              </div>
              <details class="stage3-advanced stage3-span-4">
                <summary>高级设置（随机种子、输出尺寸和跳过规则）</summary>
                <div class="stage3-advanced-grid">
                  <div><label class="label" for="batch-seed-strategy">随机方式</label><select class="field stage3-control" id="batch-seed-strategy"><option value="fixed"${config.seed_strategy === "fixed" ? " selected" : ""}>所有图片使用同一种子</option><option value="random"${config.seed_strategy === "random" ? " selected" : ""}>每张图片随机</option><option value="increment"${config.seed_strategy === "increment" ? " selected" : ""}>从基础种子依次递增</option><option value="reuse_last"${config.seed_strategy === "reuse_last" ? " selected" : ""}>沿用上次结果</option></select></div>
                  <div><label class="label" for="batch-seed-base">基础种子</label><input class="field stage3-control" id="batch-seed-base" type="number" min="0" value="${config.seed_base ?? ""}" placeholder="留空使用工作流设置" /></div>
                  <div><label class="label">覆盖输出尺寸</label><div class="stage3-inline-fields"><input class="field stage3-control" id="batch-width" type="number" min="64" max="16384" value="${config.width ?? ""}" placeholder="宽" /><span>×</span><input class="field stage3-control" id="batch-height" type="number" min="64" max="16384" value="${config.height ?? ""}" placeholder="高" /></div></div>
                  <label class="stage3-check"><input id="batch-skip-adopted" type="checkbox"${config.skip_adopted ? " checked" : ""} /><span><strong>跳过已有采用图片的页面</strong><small>这些页面不会再次创建任务</small></span></label>
                  <label class="stage3-check"><input id="batch-only-failed" type="checkbox"${config.only_failed ? " checked" : ""} /><span><strong>只重新运行失败页面</strong><small>不会复制已经成功的任务</small></span></label>
                </div>
              </details>
            </div>
            <div class="stage3-config-actions">
              <span class="stage3-action-note">创建任务后仍不会自动运行；请在任务中心点击“开始跑图”。</span>
              <button class="btn" type="button" data-api-action="batch-save-draft">保存配置</button>
              <button class="btn soft" type="button" data-api-action="batch-preview-draft">检查跑图列表</button>
              <button class="btn primary" type="button" data-api-action="batch-commit-draft"${preview?.items?.length ? "" : " disabled"}>创建任务并前往开始</button>
            </div>
          </section>
          <section class="panel stage3-preview-panel">
            <div class="panel-header"><div><div class="panel-title">跑图列表检查</div><div class="panel-sub">这里会列出将要创建的页面任务、工作流和图片数量</div></div></div>
            <div id="batch-preview-content">${batchPreviewMarkup(preview)}</div>
          </section>
        </main>
      </div>
    `;
  }

  function batchNoDraftMarkup(project) {
    return `
      <section class="panel stage3-first-draft">
        <span class="production-empty-icon">B</span>
        <h2>创建第一个跑图批次</h2>
        <p>先给这次跑图命名。创建后再选择页面、每页图片数和工作流；现在不会开始跑图。</p>
        ${batchFlowSteps(1)}
        <div class="stage3-first-draft-form">
          <input id="batch-first-name" class="field stage3-control" maxlength="120" placeholder="例如：第一章首次跑图" />
          <button class="btn primary" type="button" data-api-action="batch-create-first-draft" data-project-id="${escapeHtml(project.id)}">创建跑图批次</button>
        </div>
      </section>
    `;
  }

  async function renderProductionBatch(project) {
    const page = document.querySelector(".page-scroll");
    if (!page || !project) return;
    batchUiState.project = project;
    page.innerHTML = `
      <div class="page-header">
        <div><h1 class="page-title">跑图批次</h1><p class="page-subtitle">选择页面和工作流，检查任务列表，然后前往任务中心开始跑图。</p></div>
        <div class="header-actions"><button class="btn" type="button" data-api-action="open-task-center">任务中心</button></div>
      </div>
      <section class="stage3-loading"><i></i><span>正在读取批次配置、项目页面和工作流…</span></section>
    `;
    const [draftPayload, batchPayload, treePayload, workflowPayload] = await Promise.all([
      request(API.batchDrafts(project.id)),
      request(API.projectBatches(project.id)),
      request(API.storyTree(project.id)),
      request(`${API.workflows}?limit=200&offset=0&sort=updated_desc`),
    ]);
    batchUiState.drafts = Array.isArray(draftPayload.drafts) ? draftPayload.drafts : [];
    batchUiState.batches = Array.isArray(batchPayload.batches) ? batchPayload.batches : [];
    batchUiState.tree = treePayload || { chapters: [] };
    batchUiState.workflows = Array.isArray(workflowPayload.items) ? workflowPayload.items : [];
    const requestedDraft = new URLSearchParams(window.location.search).get("draft");
    const activeDraft =
      batchUiState.drafts.find((draft) => draft.id === requestedDraft) ||
      batchUiState.drafts[0] ||
      null;
    batchUiState.activeDraftId = activeDraft?.id || "";
    const header = page.querySelector(".page-header");
    [...page.children].forEach((child) => {
      if (child !== header) child.remove();
    });
    page.insertAdjacentHTML(
      "beforeend",
      activeDraft ? batchDraftWorkspace(project, activeDraft) : batchNoDraftMarkup(project)
    );
    const draftSelect = document.getElementById("batch-draft-select");
    if (draftSelect) {
      draftSelect.addEventListener("change", () => {
        stage3Navigate("batch", { project: project.id, draft: draftSelect.value });
      });
    }
    bindBatchDraftDirtyTracking();
  }

  function bindBatchDraftDirtyTracking() {
    const controls = document.querySelectorAll(
      ".stage3-config-panel .stage3-control, #batch-skip-adopted, #batch-only-failed"
    );
    const markStale = () => {
      const commitButton = document.querySelector('[data-api-action="batch-commit-draft"]');
      if (commitButton) commitButton.disabled = true;
      const status = document.querySelector(".stage3-config-panel .status");
      if (status) {
        status.classList.remove("green");
        status.classList.add("orange");
        status.innerHTML = '<i class="dot"></i>预览已过期';
      }
    };
    controls.forEach((control) => {
      control.addEventListener("input", markStale);
      control.addEventListener("change", markStale);
    });
  }

  function readBatchDraftForm() {
    const targetValue = document.getElementById("batch-target")?.value || "project|";
    const separator = targetValue.indexOf("|");
    const scope = separator >= 0 ? targetValue.slice(0, separator) : "project";
    const scopeId = separator >= 0 ? targetValue.slice(separator + 1) : "";
    const workflowValue = document.getElementById("batch-workflow")?.value || "|";
    const workflowSeparator = workflowValue.indexOf("|");
    const workflowId = workflowValue.slice(0, workflowSeparator);
    const workflowVersionId = workflowValue.slice(workflowSeparator + 1);
    const optionalNumber = (id) => {
      const raw = document.getElementById(id)?.value?.trim();
      return raw === "" || raw === undefined ? null : Number(raw);
    };
    return {
      name: document.getElementById("batch-name")?.value.trim() || "未命名跑图批次",
      scope,
      scope_id: scope === "project" ? null : scopeId,
      config: {
        instance_count: Number(document.getElementById("batch-instance-count")?.value) || 1,
        seed_strategy: document.getElementById("batch-seed-strategy")?.value || "fixed",
        seed_base: optionalNumber("batch-seed-base"),
        width: optionalNumber("batch-width"),
        height: optionalNumber("batch-height"),
        workflow_id: workflowId || null,
        workflow_version_id: workflowVersionId || null,
        skip_adopted: Boolean(document.getElementById("batch-skip-adopted")?.checked),
        only_failed: Boolean(document.getElementById("batch-only-failed")?.checked),
      },
    };
  }

  async function createBatchDraftFromInput(inputId) {
    const nameInput = document.getElementById(inputId);
    const name = nameInput?.value.trim();
    if (!name) {
      if (typeof showToast === "function") showToast("请先输入批次名称");
      nameInput?.focus();
      return;
    }
    const payload = await request(API.batchDrafts(batchUiState.project.id), {
      method: "POST",
      body: JSON.stringify({ name, scope: "project" }),
    });
    if (typeof showToast === "function") showToast("跑图批次配置已创建");
    stage3Navigate("batch", {
      project: batchUiState.project.id,
      draft: payload.draft?.id,
    });
  }

  async function saveBatchDraft({ quiet = false } = {}) {
    if (!batchUiState.activeDraftId) return null;
    const payload = await request(API.batchDraft(batchUiState.activeDraftId), {
      method: "PATCH",
      body: JSON.stringify(readBatchDraftForm()),
    });
    if (!quiet && typeof showToast === "function") showToast("跑图批次配置已保存");
    return payload.draft;
  }

  async function previewBatchDraft() {
    const previewContent = document.getElementById("batch-preview-content");
    if (previewContent) {
      previewContent.innerHTML = '<section class="stage3-loading"><i></i><span>正在编译全部页面…</span></section>';
    }
    try {
      await saveBatchDraft({ quiet: true });
      const payload = await request(API.batchDraftPreview(batchUiState.activeDraftId), {
        method: "POST",
        body: JSON.stringify({ force: true, resolve_slots: true }),
      });
      if (previewContent) previewContent.innerHTML = batchPreviewMarkup(payload.preview);
      const commitButton = document.querySelector('[data-api-action="batch-commit-draft"]');
      if (commitButton) commitButton.disabled = !(payload.preview?.items?.length);
      if (typeof showToast === "function") showToast("跑图列表检查完成");
    } catch (error) {
      if (previewContent) {
        previewContent.innerHTML = `<section class="stage3-error"><strong>编译失败</strong><p>${escapeHtml(error.message)}</p><button class="btn small" type="button" data-api-action="batch-preview-draft">重试</button></section>`;
      }
    }
  }

  async function commitBatchDraft() {
    const draftPayload = await request(API.batchDraft(batchUiState.activeDraftId));
    const preview = draftPayload.draft?.preview;
    if (!preview || draftPayload.draft?.preview_stale || !preview.items?.length) {
      if (typeof showToast === "function") showToast("请先检查跑图列表");
      return;
    }
    const blockers = preview.blocking_errors?.length || 0;
    const warnings = preview.warnings?.length || 0;
    const taskCount = preview.items.reduce(
      (total, item) => total + (Number(item.instance_count) || 1),
      0
    );
    const message =
      `将为 ${preview.items.length} 个页面创建 ${taskCount} 个跑图任务。` +
      (blockers ? `\n有 ${blockers} 个阻塞页面不会进入队列。` : "") +
      (warnings ? `\n另有 ${warnings} 条警告，请确认已查看。` : "") +
      "\n创建后将进入任务中心，由你点击“开始跑图”后才会提交到 ComfyUI。是否继续？";
    if (!window.confirm(message)) return;
    const commitPayload = await request(API.batchDraftCommit(batchUiState.activeDraftId), {
      method: "POST",
      body: JSON.stringify({ name: readBatchDraftForm().name }),
    });
    const batch = commitPayload.batch;
    await request(API.batchTasks(batch.id), {
      method: "POST",
      body: JSON.stringify({ max_attempts: 3 }),
    });
    if (typeof showToast === "function") showToast("跑图任务已创建，请确认后开始跑图");
    stage3Navigate("tasks", { project: batchUiState.project.id, batch: batch.id });
  }

  function taskBatchControls(batch) {
    if (!batch) return '<span class="stage3-help">选择一个批次后可开始执行。</span>';
    const controls = [];
    if (batch.status === "pending" || batch.status === "paused") {
      controls.push(`<button class="btn primary" type="button" data-api-action="task-start-batch" data-batch-id="${escapeHtml(batch.id)}">${batch.status === "paused" ? "继续批次" : "开始批次"}</button>`);
    }
    if (batch.status === "running") {
      controls.push(`<button class="btn primary" type="button" data-api-action="${taskUiState.runnerActive ? "task-stop-runner" : "task-run-queue"}" data-batch-id="${escapeHtml(batch.id)}">${taskUiState.runnerActive ? "停止自动领取" : "连续运行待处理项"}</button>`);
      controls.push(`<button class="btn" type="button" data-api-action="task-pause-batch" data-batch-id="${escapeHtml(batch.id)}">暂停批次</button>`);
    }
    if (!["completed", "cancelled"].includes(batch.status)) {
      controls.push(`<button class="btn danger-soft" type="button" data-api-action="task-cancel-batch" data-batch-id="${escapeHtml(batch.id)}">取消批次</button>`);
    }
    return controls.join("");
  }

  function taskRowActions(task) {
    const actions = [
      `<button class="btn small" type="button" data-api-action="task-show-detail" data-task-id="${escapeHtml(task.id)}">详情</button>`,
    ];
    if (task.status === "pending" || task.status === "retrying") {
      actions.push(`<button class="btn small soft" type="button" data-api-action="task-control" data-task-action="pause" data-task-id="${escapeHtml(task.id)}">暂停</button>`);
    } else if (task.status === "paused") {
      actions.push(`<button class="btn small soft" type="button" data-api-action="task-control" data-task-action="resume" data-task-id="${escapeHtml(task.id)}">继续</button>`);
    } else if (task.status === "failed" || task.status === "cancelled") {
      actions.push(`<button class="btn small soft" type="button" data-api-action="task-control" data-task-action="retry" data-task-id="${escapeHtml(task.id)}">重试</button>`);
    } else if (task.status === "running" && task.last_attempt_id) {
      actions.push(`<button class="btn small soft" type="button" data-api-action="task-resume-attempt" data-attempt-id="${escapeHtml(task.last_attempt_id)}">恢复进度</button>`);
    }
    return actions.join("");
  }

  function taskProgressBanner() {
    const progress = taskUiState.currentProgress;
    if (!progress) return "";
    const percent = Math.max(0, Math.min(100, Number(progress.percent) || 0));
    return `
      <section class="stage3-live-progress">
        <div>
          <span class="stage3-live-dot"></span>
          <strong>${escapeHtml(progress.label || "正在运行")}</strong>
          <small>${escapeHtml(progress.node || progress.message || "等待 ComfyUI 进度")}</small>
        </div>
        <div class="stage3-progress-track"><i style="width:${percent}%"></i></div>
        <span>${percent}%</span>
      </section>
    `;
  }

  function taskCenterMarkup(project) {
    const selectedBatch =
      taskUiState.batches.find((batch) => batch.id === taskUiState.batchId) || null;
    const summary = taskUiState.summary || {};
    const rows = taskUiState.tasks.map((task) => {
      const item = task.item || {};
      return `
        <tr>
          <td><strong>${escapeHtml(item.shot_page_title || task.sort_key || task.id.slice(0, 8))}</strong><small>${escapeHtml([item.chapter_name, item.large_scene_name, item.small_scene_name].filter(Boolean).join(" / "))}</small></td>
          <td>${stage3Status(task.status)}</td>
          <td>${escapeHtml(task.batch_name || task.batch_id.slice(0, 8))}</td>
          <td>${Number(task.attempt_count) || 0} / ${Number(task.max_attempts) || 0}</td>
          <td><input class="stage3-priority" type="number" min="0" max="1000" value="${Number(task.priority) || 0}" data-task-priority-id="${escapeHtml(task.id)}" aria-label="任务优先级" /></td>
          <td>${task.error_message ? `<span class="stage3-error-text" title="${escapeHtml(task.error_message)}">${escapeHtml(task.error_type || "错误")}</span>` : "—"}</td>
          <td class="stage3-row-actions">${taskRowActions(task)}</td>
        </tr>
      `;
    }).join("");
    return `
      <div class="page-header">
        <div><h1 class="page-title">任务中心</h1><p class="page-subtitle">持久化任务、真实 ComfyUI 进度、错误和产出都在这里。</p></div>
        <div class="header-actions">
          <button class="btn" type="button" data-api-action="task-recover-submitted">恢复中断任务</button>
          <button class="btn primary" type="button" data-api-action="open-batch-page">新建批次</button>
        </div>
      </div>
      <div class="stage3-metrics stage3-task-metrics">
        <div><span>全部任务</span><strong>${Number(summary.total_tasks) || 0}</strong></div>
        <div><span>运行中</span><strong>${(Number(summary.running) || 0) + (Number(summary.retrying) || 0)}</strong></div>
        <div><span>等待</span><strong>${Number(summary.pending) || 0}</strong></div>
        <div><span>完成</span><strong>${Number(summary.completed) || 0}</strong></div>
        <div class="${Number(summary.failed) ? "danger" : ""}"><span>失败</span><strong>${Number(summary.failed) || 0}</strong></div>
        <div><span>批次</span><strong>${Number(summary.total_batches) || 0}</strong></div>
      </div>
      ${taskProgressBanner()}
      <section class="panel stage3-task-panel">
        <div class="stage3-task-toolbar">
          <select class="field stage3-control" id="task-batch-filter">
            <option value="">全部批次</option>
            ${taskUiState.batches.map((batch) => `<option value="${escapeHtml(batch.id)}"${batch.id === taskUiState.batchId ? " selected" : ""}>${escapeHtml(batch.name || "未命名批次")} · ${stage3Date(batch.created_at)}</option>`).join("")}
          </select>
          <select class="field stage3-control" id="task-status-filter">
            <option value="all"${taskUiState.status === "all" ? " selected" : ""}>全部状态</option>
            <option value="pending"${taskUiState.status === "pending" ? " selected" : ""}>等待</option>
            <option value="running"${taskUiState.status === "running" ? " selected" : ""}>运行中</option>
            <option value="paused"${taskUiState.status === "paused" ? " selected" : ""}>已暂停</option>
            <option value="failed"${taskUiState.status === "failed" ? " selected" : ""}>失败</option>
            <option value="completed"${taskUiState.status === "completed" ? " selected" : ""}>已完成</option>
          </select>
          <label class="stage3-filter-check"><input type="checkbox" id="task-error-filter"${taskUiState.hasError ? " checked" : ""} /> 只看错误</label>
          <button class="btn small" type="button" data-api-action="task-refresh">刷新</button>
          ${Number(summary.failed) ? '<button class="btn small soft" type="button" data-api-action="task-retry-failed">只重试失败项</button>' : ""}
          <span class="spacer"></span>
          <div class="stage3-batch-controls">${stage3Status(selectedBatch?.status)}${taskBatchControls(selectedBatch)}</div>
        </div>
        <div class="stage3-table-wrap stage3-task-table-wrap">
          <table class="table stage3-table">
            <thead><tr><th>页面与来源</th><th>状态</th><th>批次</th><th>尝试</th><th>优先级</th><th>错误</th><th>操作</th></tr></thead>
            <tbody>${rows || '<tr><td colspan="7"><div class="stage3-empty-row">当前筛选条件下没有任务。</div></td></tr>'}</tbody>
          </table>
        </div>
      </section>
    `;
  }

  async function renderProductionTasks(project, { preserveProgress = false } = {}) {
    const page = document.querySelector(".page-scroll");
    if (!page || !project) return;
    taskUiState.project = project;
    if (!preserveProgress) {
      const params = new URLSearchParams(window.location.search);
      taskUiState.batchId = params.get("batch") || taskUiState.batchId || "";
    }
    const query = new URLSearchParams({ project_id: project.id, limit: "200", offset: "0" });
    if (taskUiState.status !== "all") query.set("status", taskUiState.status);
    if (taskUiState.batchId) query.set("batch_id", taskUiState.batchId);
    if (taskUiState.hasError) query.set("has_error", "true");
    if (!preserveProgress) {
      page.innerHTML = '<section class="stage3-loading"><i></i><span>正在读取持久化任务…</span></section>';
    }
    const [summaryPayload, taskPayload, batchPayload] = await Promise.all([
      request(`${API.taskCenterSummary}?project_id=${encodeURIComponent(project.id)}`),
      request(`${API.tasks}?${query.toString()}`),
      request(API.projectBatches(project.id)),
    ]);
    taskUiState.summary = summaryPayload.summary || {};
    taskUiState.tasks = Array.isArray(taskPayload.tasks) ? taskPayload.tasks : [];
    taskUiState.batches = Array.isArray(batchPayload.batches) ? batchPayload.batches : [];
    page.innerHTML = taskCenterMarkup(project);
    bindTaskCenterFilters();
  }

  function bindTaskCenterFilters() {
    const batchFilter = document.getElementById("task-batch-filter");
    const statusFilter = document.getElementById("task-status-filter");
    const errorFilter = document.getElementById("task-error-filter");
    batchFilter?.addEventListener("change", async () => {
      taskUiState.batchId = batchFilter.value;
      await renderProductionTasks(taskUiState.project, { preserveProgress: true });
    });
    statusFilter?.addEventListener("change", async () => {
      taskUiState.status = statusFilter.value;
      await renderProductionTasks(taskUiState.project, { preserveProgress: true });
    });
    errorFilter?.addEventListener("change", async () => {
      taskUiState.hasError = errorFilter.checked;
      await renderProductionTasks(taskUiState.project, { preserveProgress: true });
    });
    document.querySelectorAll("[data-task-priority-id]").forEach((input) => {
      input.addEventListener("change", async () => {
        try {
          await request(API.taskPriority(input.dataset.taskPriorityId), {
            method: "PATCH",
            body: JSON.stringify({ priority: Number(input.value) || 0 }),
          });
          if (typeof showToast === "function") showToast("任务优先级已更新");
        } catch (error) {
          if (typeof showToast === "function") showToast(error.message);
        }
      });
    });
  }

  function updateTaskLiveProgress(data, label) {
    const value = Number(data?.value);
    const max = Number(data?.max);
    const percent = Number.isFinite(value) && Number.isFinite(max) && max > 0
      ? Math.round((value / max) * 100)
      : data?.status === "completed"
        ? 100
        : Number(data?.percent) || 0;
    taskUiState.currentProgress = {
      label: label || "ComfyUI 正在生成",
      node: data?.current_node ? `节点 ${data.current_node}` : "",
      message: data?.message || data?.status || "",
      percent,
    };
    const oldBanner = document.querySelector(".stage3-live-progress");
    const metrics = document.querySelector(".stage3-task-metrics");
    if (oldBanner) oldBanner.outerHTML = taskProgressBanner();
    else if (metrics) metrics.insertAdjacentHTML("afterend", taskProgressBanner());
  }

  function monitorAttemptWithSse(attemptId, label) {
    return new Promise((resolve) => {
      let settled = false;
      let polling = false;
      const source = new EventSource(API.attemptProgressSse(attemptId));
      const timer = window.setTimeout(() => finish("timeout"), 300000);
      const pollTimer = window.setInterval(async () => {
        if (settled || polling) return;
        polling = true;
        try {
          const payload = await request(API.attemptProgressPoll(attemptId), {
            method: "POST",
            body: "{}",
          });
          const result = payload.result || {};
          const status = result.completed ? "completed" : result.status;
          updateTaskLiveProgress(
            { status, percent: result.completed ? 100 : Number(result.percent) || 0 },
            label
          );
          if (["completed", "error", "interrupted"].includes(status)) finish(status);
        } catch (error) {
          // The prompt may not be present in history during the first few polls.
        } finally {
          polling = false;
        }
      }, 1600);
      function finish(status) {
        if (settled) return;
        settled = true;
        window.clearTimeout(timer);
        window.clearInterval(pollTimer);
        source.close();
        resolve(status);
      }
      source.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          updateTaskLiveProgress(data, label);
          if (["completed", "error", "interrupted", "timeout"].includes(data.status)) {
            finish(data.status);
          }
        } catch (error) {
          // Ignore malformed transient events; the polling fallback remains available.
        }
      };
      source.onerror = () => finish("sse_error");
    });
  }

  async function pollAttemptUntilTerminal(attemptId, label) {
    for (let index = 0; index < 150; index += 1) {
      try {
        const payload = await request(API.attemptProgressPoll(attemptId), {
          method: "POST",
          body: "{}",
        });
        const result = payload.result || {};
        updateTaskLiveProgress(
          { status: result.completed ? "completed" : result.status, percent: result.completed ? 100 : 0 },
          label
        );
        if (result.completed) return "completed";
        if (result.status === "error") return "error";
      } catch (error) {
        // A prompt may not be in history yet. Keep polling until the bounded deadline.
      }
      await new Promise((resolve) => window.setTimeout(resolve, 2000));
    }
    return "timeout";
  }

  async function executeClaim(claim) {
    const label = claim.item?.shot_page_title || claim.sort_key || claim.task_id.slice(0, 8);
    updateTaskLiveProgress({ status: "submitting", percent: 0 }, `正在提交：${label}`);
    const submitPayload = await request(API.taskSubmit(claim.task_id, claim.attempt_id), {
      method: "POST",
      body: "{}",
    });
    const result = submitPayload.result || {};
    if (result.timeout || !result.prompt_id) {
      if (typeof showToast === "function") showToast("提交状态不确定，已保留记录且不会自动重复提交");
      return "unknown";
    }
    let status = await monitorAttemptWithSse(claim.attempt_id, `正在生成：${label}`);
    if (status === "sse_error" || status === "timeout") {
      status = await pollAttemptUntilTerminal(claim.attempt_id, `轮询恢复：${label}`);
    }
    if (status === "completed") {
      const outputPayload = await request(API.attemptCollectOutputs(claim.attempt_id), {
        method: "POST",
        body: "{}",
      });
      const collected = Number(outputPayload.result?.collected) || 0;
      if (typeof showToast === "function") showToast(`任务完成，已保存 ${collected} 张图片实例`);
    } else if (status === "error" || status === "interrupted") {
      if (typeof showToast === "function") showToast("ComfyUI 执行失败，错误已记录");
    }
    return status;
  }

  async function runTaskQueue(batchId) {
    if (taskUiState.runnerActive) return;
    taskUiState.runnerActive = true;
    taskUiState.runnerBatchId = batchId;
    await renderProductionTasks(taskUiState.project, { preserveProgress: true });
    try {
      while (taskUiState.runnerActive) {
        const claimPayload = await request(API.taskClaim, {
          method: "POST",
          body: JSON.stringify({
            lease_holder: `atelier-web-${window.sessionStorage.getItem("atelier-runner-id") || Date.now()}`,
            lease_seconds: 600,
            batch_id: batchId || null,
          }),
        });
        const claim = claimPayload.claim;
        if (!claim) {
          if (typeof showToast === "function") showToast("当前批次没有待处理任务");
          break;
        }
        await executeClaim(claim);
        await renderProductionTasks(taskUiState.project, { preserveProgress: true });
      }
    } catch (error) {
      if (typeof showToast === "function") showToast(`任务执行已停止：${error.message}`);
    } finally {
      taskUiState.runnerActive = false;
      taskUiState.runnerBatchId = "";
      taskUiState.currentProgress = null;
      await renderProductionTasks(taskUiState.project, { preserveProgress: true });
    }
  }

  async function updateTaskBatchStatus(batchId, statusValue) {
    await request(API.batchStatus(batchId), {
      method: "PATCH",
      body: JSON.stringify({ status: statusValue }),
    });
    if (statusValue !== "running") taskUiState.runnerActive = false;
    await renderProductionTasks(taskUiState.project, { preserveProgress: true });
  }

  async function collectAttemptOutputsOnce(attemptId) {
    const existing = await request(
      `${API.imageInstances}?attempt_id=${encodeURIComponent(attemptId)}&limit=1&offset=0`
    );
    if (Number(existing.count) > 0) return Number(existing.count);
    const outputPayload = await request(API.attemptCollectOutputs(attemptId), {
      method: "POST",
      body: "{}",
    });
    return Number(outputPayload.result?.collected) || 0;
  }

  async function resumeTaskAttempt(attemptId) {
    const attemptPayload = await request(API.attempt(attemptId));
    const attempt = attemptPayload.attempt || {};
    if (!attempt.prompt_id) {
      throw new Error("该尝试没有 prompt_id，不能从 ComfyUI 恢复");
    }
    let status = attempt.status === "completed"
      ? "completed"
      : await monitorAttemptWithSse(attemptId, "正在恢复 ComfyUI 进度");
    if (status === "sse_error" || status === "timeout") {
      status = await pollAttemptUntilTerminal(attemptId, "正在轮询 ComfyUI 历史");
    }
    if (status === "completed") {
      const count = await collectAttemptOutputsOnce(attemptId);
      if (typeof showToast === "function") showToast(`恢复完成，已有或新收集 ${count} 张图片`);
    }
    taskUiState.currentProgress = null;
    await renderProductionTasks(taskUiState.project, { preserveProgress: true });
  }

  async function retryFailedTasks() {
    const params = new URLSearchParams({
      project_id: taskUiState.project.id,
      status: "failed",
      limit: "1000",
      offset: "0",
    });
    if (taskUiState.batchId) params.set("batch_id", taskUiState.batchId);
    const payload = await request(`${API.tasks}?${params.toString()}`);
    const failedTasks = Array.isArray(payload.tasks) ? payload.tasks : [];
    if (!failedTasks.length) {
      if (typeof showToast === "function") showToast("没有可重试的失败任务");
      return;
    }
    if (!window.confirm(`只把 ${failedTasks.length} 个失败任务放回队列；已成功任务不会改变。是否继续？`)) {
      return;
    }
    for (const task of failedTasks) {
      await request(API.task(task.id), {
        method: "PATCH",
        body: JSON.stringify({ action: "retry" }),
      });
    }
    if (typeof showToast === "function") showToast(`已重新排队 ${failedTasks.length} 个失败任务`);
    await renderProductionTasks(taskUiState.project, { preserveProgress: true });
  }

  function ensureTaskDetailModal() {
    let modal = document.getElementById("task-detail-modal");
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "task-detail-modal";
    modal.className = "atelier-modal-backdrop";
    modal.hidden = true;
    modal.innerHTML = `
      <section class="atelier-modal stage3-detail-modal" role="dialog" aria-modal="true" aria-labelledby="task-detail-title">
        <div class="stage3-detail-head"><div><span class="developer-eyebrow">TASK TRACE</span><h2 id="task-detail-title">任务追踪</h2></div><button class="btn small" type="button" data-api-action="task-close-detail">关闭</button></div>
        <div id="task-detail-content" class="stage3-detail-content"></div>
      </section>
    `;
    document.body.appendChild(modal);
    return modal;
  }

  async function showTaskDetail(taskId) {
    const modal = ensureTaskDetailModal();
    const content = modal.querySelector("#task-detail-content");
    modal.hidden = false;
    requestAnimationFrame(() => modal.classList.add("show"));
    content.innerHTML = '<section class="stage3-loading"><i></i><span>正在读取任务快照与事件…</span></section>';
    try {
      const payload = await request(API.taskErrorDetail(taskId));
      const task = payload.task || {};
      const item = task.item || {};
      content.innerHTML = `
        <div class="stage3-detail-grid">
          <section><label>页面</label><strong>${escapeHtml(item.shot_page_title || task.sort_key || "未命名")}</strong><small>${escapeHtml([item.chapter_name, item.large_scene_name, item.small_scene_name].filter(Boolean).join(" / "))}</small></section>
          <section><label>状态</label>${stage3Status(task.status)}<small>尝试 ${Number(task.attempt_count) || 0} / ${Number(task.max_attempts) || 0}</small></section>
          <section><label>工作流快照</label><strong>${escapeHtml(item.workflow_label || item.workflow_version_id || "未设置")}</strong><small>${escapeHtml(item.input_hash || "")}</small></section>
          <section><label>错误</label><strong>${escapeHtml(task.error_type || "无")}</strong><small>${escapeHtml(task.error_message || "没有技术错误")}</small></section>
        </div>
        <h3>尝试记录</h3>
        <div class="stage3-trace-list">${(payload.attempts || []).map((attempt) => `<div><span>${stage3Status(attempt.status)}</span><strong>#${attempt.attempt_number}</strong><small>${escapeHtml(attempt.prompt_id || "尚无 prompt_id")} · ${stage3Date(attempt.created_at)}</small></div>`).join("") || "<p>还没有尝试记录。</p>"}</div>
        <h3>事件</h3>
        <div class="stage3-trace-list">${(payload.events || []).map((event) => `<div><strong>${escapeHtml(event.event_type)}</strong><small>${stage3Date(event.created_at)}</small></div>`).join("") || "<p>还没有事件。</p>"}</div>
      `;
    } catch (error) {
      content.innerHTML = `<section class="stage3-error"><strong>读取失败</strong><p>${escapeHtml(error.message)}</p></section>`;
    }
  }

  function closeTaskDetail() {
    const modal = document.getElementById("task-detail-modal");
    if (!modal) return;
    modal.classList.remove("show");
    window.setTimeout(() => { modal.hidden = true; }, 150);
  }

  async function refreshDatabaseState() {
    try {
      document.body.dataset.databaseEnvironment = "production";
      const pageKey = new URLSearchParams(window.location.search).get("page") || "projects";
      if (pageKey === "projects") {
        await renderProductionProjects();
      } else if (pageKey === "characters") {
        await renderProductionCharacters();
        await window.AtelierGapFillUI?.enhance(pageKey);
      } else if (pageKey === "character-database") {
        await renderCharacterDatabasePage();
        await window.AtelierGapFillUI?.enhance(pageKey);
      } else if (pageKey === "materials") {
        await renderMaterialsPage();
        await window.AtelierGapFillUI?.enhance(pageKey);
      } else if (pageKey === "material-detail") {
        await renderMaterialDetailPage();
        await window.AtelierGapFillUI?.enhance(pageKey);
      } else if (pageKey === "developer") {
        // 开发进度由用户点击后按需读取，避免把文档状态写死在页面里。
      } else if (pageKey === "workflows") {
        await renderProductionWorkflows();
      } else if (pageKey === "workflow-canvas") {
        await renderProductionWorkflowCanvas();
        await window.AtelierGapFillUI?.enhance(pageKey);
      } else if (pageKey === "batch") {
        const project = await resolveCurrentProject();
        applyProjectHeader(project, pageKey);
        await renderProductionBatch(project);
        await window.AtelierGapFillUI?.enhance(pageKey, project);
      } else if (pageKey === "tasks") {
        const project = await resolveCurrentProject();
        applyProjectHeader(project, pageKey);
        await renderProductionTasks(project);
        await window.AtelierGapFillUI?.enhance(pageKey, project);
      } else if (pageKey === "library" || pageKey === "image-detail") {
        await window.AtelierGapFillUI?.render(pageKey, null);
      } else if (pageKey === "settings") {
        await renderProductionSettings();
        await window.AtelierGapFillUI?.render(pageKey, null);
      } else if (pageKey !== "settings") {
        const project = await resolveCurrentProject();
        applyProjectHeader(project, pageKey);
        if (pageKey === "overview") await renderProductionOverview(project);
        else if (pageKey === "story-canvas") {
          await renderProductionStoryCanvasV3(project);
          await window.AtelierGapFillUI?.enhance(pageKey, project);
        }
        else if (["review", "assembly", "export"].includes(pageKey)) {
          await window.AtelierGapFillUI?.render(pageKey, project);
        }
        else applyProductionEmptyState();
      }
      const safety = document.getElementById("database-safety-status");
      if (safety) safety.innerHTML = '<span class="status green">数据可用</span>';
      document.body.classList.remove("runtime-pending");
      return { active_environment: "production" };
    } catch (error) {
      const safety = document.getElementById("database-safety-status");
      if (safety) safety.innerHTML = '<span class="status orange">后端未连接</span>';
      document.body.classList.remove("runtime-pending");
      return null;
    }
  }

  // ==================== 工作流画布 ====================

  // 工作流画布状态：缓存草稿、图数据、插槽和节点定义，避免重复请求。
  const workflowCanvasState = {
    workflowId: "",
    workflowName: "",
    draftRevision: null,
    isDirty: false,
    graph: { nodes: [], links: [], groups: [], metadata: {} },
    slots: [],
    objectInfo: null,
    objectInfoLoaded: false,
    selectedNodeId: null,
    pendingLinkFrom: null, // 新增连线时暂存输出端口 {nodeId, slot}
    loading: false,
    paletteSearchTimer: null,
    pendingMutation: Promise.resolve(),
    layoutGroups: [],
    zoom: 1,
    focus: null,
  };

  function normalizeWorkflowNodeDefinitions(payload) {
    if (!payload || typeof payload !== "object") return null;
    if (!Array.isArray(payload.items)) return payload;
    const definitions = {};
    payload.items.forEach((item) => {
      const nodeClass = item?.node_class;
      if (!nodeClass) return;
      definitions[nodeClass] = {
        name: item.display_name || nodeClass,
        category: item.category || "其他",
        python_module: item.python_module || "",
        is_custom_node: Boolean(item.is_custom_node),
      };
    });
    return definitions;
  }

  // 将草稿中的 normalized_graph 字符串解析为图对象，容错空值和非法 JSON。
  function parseWorkflowGraph(draft) {
    if (!draft) return { nodes: [], links: [], groups: [], metadata: {} };
    const raw = draft.normalized_graph;
    if (!raw) return { nodes: [], links: [], groups: [], metadata: {} };
    if (typeof raw === "string") {
      try {
        const parsed = JSON.parse(raw);
        return {
          nodes: Array.isArray(parsed.nodes) ? parsed.nodes : [],
          links: Array.isArray(parsed.links) ? parsed.links : [],
          groups: Array.isArray(parsed.groups) ? parsed.groups : [],
          metadata: parsed.metadata || {},
        };
      } catch (error) {
        return { nodes: [], links: [], groups: [], metadata: {} };
      }
    }
    if (typeof raw === "object") {
      return {
        nodes: Array.isArray(raw.nodes) ? raw.nodes : [],
        links: Array.isArray(raw.links) ? raw.links : [],
        groups: Array.isArray(raw.groups) ? raw.groups : [],
        metadata: raw.metadata || {},
      };
    }
    return { nodes: [], links: [], groups: [], metadata: {} };
  }

  // 解析草稿中的 semantic_slots_json，容错处理。
  function parseWorkflowSlots(draft) {
    if (!draft) return [];
    const raw = draft.semantic_slots_json;
    if (!raw) return [];
    if (typeof raw === "string") {
      try {
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed : [];
      } catch (error) {
        return [];
      }
    }
    if (Array.isArray(raw)) return raw;
    return [];
  }

  // 根据节点类型返回对应的颜色标识，用于节点头像和端口。
  function workflowNodeColor(node) {
    const type = String(node.type || "").toLowerCase();
    if (type.includes("checkpoint") || type.includes("vae")) return "blue";
    if (type.includes("lora")) return "purple";
    if (type.includes("clip") || type.includes("text") || type.includes("save")) return "green";
    if (type.includes("ksampler") || type.includes("sampler")) return "orange";
    if (type.includes("latent") || type.includes("empty")) return "cyan";
    return "blue";
  }

  // 估算节点高度，用于连线端口定位。头部38px + 内边距18px + 字段数*26px。
  function workflowNodeHeight(node) {
    const widgetCount = Array.isArray(node.widgets_values) ? node.widgets_values.length : 0;
    const inputCount = Array.isArray(node.inputs) ? node.inputs.length : 0;
    const outputCount = Array.isArray(node.outputs) ? node.outputs.length : 0;
    const fieldCount = Math.max(widgetCount, inputCount, outputCount, 1);
    return 38 + 18 + fieldCount * 26;
  }

  // 计算输入端口在节点上的 Y 坐标（相对节点左上角）。
  function workflowInputPortY(node, slotIndex) {
    return 38 + 8 + slotIndex * 26 + 13;
  }

  // 计算输出端口在节点上的 Y 坐标。
  function workflowOutputPortY(node, slotIndex) {
    return 38 + 8 + slotIndex * 26 + 13;
  }

  function workflowLinkParts(link) {
    if (Array.isArray(link)) {
      return {
        id: link[0],
        sourceNode: link[1],
        sourceSlot: Number(link[2]) || 0,
        targetNode: link[3],
        targetSlot: Number(link[4]) || 0,
        type: link[5] || "",
      };
    }
    return {
      id: link?.id,
      sourceNode: link?.source_node,
      sourceSlot: Number(link?.source_slot) || 0,
      targetNode: link?.target_node,
      targetSlot: Number(link?.target_slot) || 0,
      type: link?.type || "",
    };
  }

  async function autoLayoutWorkflow() {
    const nodes = workflowCanvasState.graph.nodes || [];
    if (!nodes.length) return;
    try {
      await request(API.workflowDraftLayoutCompute(workflowCanvasState.workflowId), {
        method: "POST",
        body: "{}",
      });
      await loadWorkflowCanvasData(workflowCanvasState.workflowId);
      refreshWorkflowCanvasAndInspector();
      if (typeof showToast === "function") showToast("自动布局已完成");
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    }
  }

  // 工作流画布空状态：未传入工作流 ID 时显示。
  function workflowCanvasEmptyHTML(message) {
    return `
      <section class="production-empty-state">
        <span class="production-empty-icon">WF</span>
        <h2>未打开工作流</h2>
        <p>${escapeHtml(message || "请从工作流库选择一个工作流进入画布。")}</p>
        <button class="btn primary" type="button" onclick="window.location.search='?page=workflows'">返回工作流库</button>
        </section>
    `;
  }

  // 工作流画布错误状态。
  function workflowCanvasErrorHTML(message) {
    return `
      <section class="production-empty-state">
        <span class="production-empty-icon">!</span>
        <h2>画布加载失败</h2>
        <p>${escapeHtml(message)}</p>
        <button class="btn soft" type="button" data-api-action="retry-workflow-canvas">重试</button>
      </section>
    `;
  }

  // 工作流画布工具栏：包含保存、预检查、发布、导出等操作按钮。
  function workflowCanvasToolbarHTML(state) {
    const dirtyBadge = state.isDirty
      ? '<span class="chip orange">未保存</span>'
      : '<span class="chip green">已保存</span>';
    return `
      <div class="toolbar" id="workflow-canvas-toolbar">
        <button class="tool active" type="button" data-api-action="workflow-layout-ltr" title="从左到右布局">从左到右</button>
        <button class="tool ${state.focus ? "active" : ""}" type="button" data-api-action="workflow-focus-path" title="聚焦当前节点的上下游">${state.focus ? "取消聚焦" : "聚焦路径"}</button>
        <span class="spacer"></span>
        <button class="tool" type="button" data-api-action="workflow-zoom-out" title="缩小">−</button>
        <button class="tool" type="button" data-api-action="workflow-zoom-reset" title="重置缩放">${Math.round((state.zoom || 1) * 100)}%</button>
        <button class="tool" type="button" data-api-action="workflow-zoom-in" title="放大">＋</button>
        <button class="tool" type="button" data-api-action="workflow-auto-layout" title="自动整理">自动整理</button>
        <span class="spacer"></span>
        ${dirtyBadge}
        <button class="tool" type="button" data-api-action="save-workflow-draft" title="保存草稿">保存</button>
        <button class="tool" type="button" data-api-action="export-workflow" title="导出 JSON">导出</button>
        <button class="tool" type="button" data-api-action="precheck-workflow" title="预检查">预检查</button>
        <button class="btn small primary" type="button" data-api-action="publish-workflow" title="发布新版本">发布</button>
      </div>
    `;
  }

  // 节点库（左栏）：如果已加载 object_info 则按分类列出，否则使用常用节点回退。
  function workflowCanvasPaletteHTML(objectInfo) {
    const fallback = [
      { type: "CheckpointLoaderSimple", name: "模型加载", color: "blue", category: "常用" },
      { type: "LoraLoader", name: "LoRA 加载", color: "purple", category: "常用" },
      { type: "CLIPTextEncode", name: "文本编码", color: "green", category: "常用" },
      { type: "KSampler", name: "KSampler", color: "orange", category: "常用" },
      { type: "EmptyLatentImage", name: "空潜空间", color: "cyan", category: "常用" },
      { type: "VAEDecode", name: "VAE 解码", color: "blue", category: "常用" },
      { type: "SaveImage", name: "保存图片", color: "green", category: "常用" },
    ];
    let groups = {};
    if (objectInfo && typeof objectInfo === "object" && Object.keys(objectInfo).length > 0) {
      Object.keys(objectInfo).forEach((type) => {
        const def = objectInfo[type] || {};
        const category = def.category || "其他";
        if (!groups[category]) groups[category] = [];
        groups[category].push({ type, name: def.name || type, color: "blue", category });
      });
    }
    const hasObjectInfo = Object.keys(groups).length > 0;
    if (!hasObjectInfo) {
      groups = { 常用: fallback };
    }
    const groupHTML = Object.keys(groups).map((category) => {
      const items = groups[category];
      return `
        <div class="palette-title">${escapeHtml(category)}${hasObjectInfo ? ` · ${items.length}` : ""}</div>
        ${items.map((item) => `
          <button class="palette-item" type="button" data-api-action="add-workflow-node" data-node-type="${escapeHtml(item.type)}">
            <span class="palette-swatch ${item.color}"></span>
            <span style="flex:1;text-align:left">${escapeHtml(item.name)}</span>
            <span style="color:#aab1bf">＋</span>
          </button>
        `).join("")}
      `;
    }).join("");
    return `
      <div class="panel-body" style="display:flex;flex-direction:column;height:100%;overflow:hidden">
        <div class="search" style="margin:10px;display:flex;align-items:center;gap:6px">
          <span>⌕</span>
          <input id="workflow-palette-search" type="search" placeholder="搜索节点" style="border:0;outline:0;background:transparent;flex:1;font-size:11px;color:#4d576b" />
        </div>
        <div class="palette-list" style="overflow-y:auto;flex:1">
          ${groupHTML}
        </div>
      </div>
    `;
  }

  // 渲染单个节点卡片，包含端口和字段。
  function workflowNodeCardHTML(node, isSelected) {
    const color = workflowNodeColor(node);
    const title = escapeHtml(node.title || node.type || "未命名节点");
    const type = escapeHtml(node.type || "unknown");
    const x = Array.isArray(node.position) ? Number(node.position[0]) || 0 : 0;
    const y = Array.isArray(node.position) ? Number(node.position[1]) || 0 : 0;
    const widgets = Array.isArray(node.widgets_values) ? node.widgets_values : [];
    const inputs = Array.isArray(node.inputs) ? node.inputs : [];
    const outputs = Array.isArray(node.outputs) ? node.outputs : [];
    const id = escapeHtml(node.id);

    // 输入端口
    const inputPorts = inputs.map((input, i) => {
      const portY = workflowInputPortY(node, i);
      return `<i class="node-port in" style="top:${portY - 5}px" data-api-action="add-workflow-link-to" data-node-id="${id}" data-slot="${i}" title="${escapeHtml(input.name || "")}:${escapeHtml(input.type || "")}"></i>`;
    }).join("");
    // 输出端口
    const outputPorts = outputs.map((output, i) => {
      const portY = workflowOutputPortY(node, i);
      return `<i class="node-port out" style="top:${portY - 5}px" data-api-action="add-workflow-link-from" data-node-id="${id}" data-slot="${i}" title="${escapeHtml(output.name || "")}:${escapeHtml(output.type || "")}"></i>`;
    }).join("");

    // 字段：显示 widgets_values
    const fields = widgets.map((w, i) => {
      const value = w === null || w === undefined ? "" : String(w);
      const display = value.length > 24 ? `${value.slice(0, 24)}…` : value;
      return `<div class="node-field"><span class="node-field-name">参数${i}</span><span class="node-value">${escapeHtml(display)}</span></div>`;
    }).join("");

    const isDimmed = Array.isArray(workflowCanvasState.focus?.dimmed)
      && workflowCanvasState.focus.dimmed.map(String).includes(String(node.id));
    const isUnknown = Boolean(node.is_unknown);
    const isCollapsed = Boolean(node.flags?.collapsed);
    return `
      <div class="node-card ${isSelected ? "selected" : ""} ${isDimmed ? "workflow-node-dimmed" : ""} ${isUnknown ? "workflow-node-unknown" : ""} ${isCollapsed ? "workflow-node-collapsed" : ""}" style="left:${x}px;top:${y}px" data-api-action="select-workflow-node" data-node-id="${id}">
        <div class="node-head"><i class="node-type ${color}"></i>${title}</div>
        <div class="node-body">${isUnknown ? '<div class="node-field"><span class="node-field-name">状态</span><span class="node-value">未知节点 · 只读保留</span></div>' : (fields || `<div class="node-field"><span class="node-field-name">类型</span><span class="node-value">${type}</span></div>`)}</div>
        ${inputPorts}${outputPorts}
      </div>
    `;
  }

  function workflowGroupsHTML(nodes, groups) {
    if (!Array.isArray(groups) || !groups.length) return "";
    const nodeMap = new Map(nodes.map((node) => [String(node.id), node]));
    return groups.map((group) => {
      const members = (group.members || []).map(String).map((id) => nodeMap.get(id)).filter(Boolean);
      if (!members.length) return "";
      const xs = members.map((node) => Number(node.position?.[0]) || 0);
      const ys = members.map((node) => Number(node.position?.[1]) || 0);
      const x = Math.min(...xs) - 24;
      const y = Math.min(...ys) - 38;
      const right = Math.max(...members.map((node) => (Number(node.position?.[0]) || 0) + 208));
      const bottom = Math.max(...members.map((node) => (Number(node.position?.[1]) || 0) + workflowNodeHeight(node)));
      return `<div class="workflow-group-lane" style="left:${x}px;top:${y}px;width:${right - x + 24}px;height:${bottom - y + 24}px;border-color:${escapeHtml(group.color || "#3f789e")}"><span style="background:${escapeHtml(group.color || "#3f789e")}">${escapeHtml(group.title || "未命名分组")}</span></div>`;
    }).join("");
  }

  // 渲染 SVG 连线：每条连线包含可见路径和不可见点击区域。
  function workflowLinksSVG(graph) {
    const nodeMap = {};
    (graph.nodes || []).forEach((n) => {
      nodeMap[String(n.id)] = n;
    });
    const links = graph.links || [];
    const paths = links.map((link) => {
      const part = workflowLinkParts(link);
      const linkId = part.id;
      const fromId = String(part.sourceNode);
      const fromSlot = part.sourceSlot;
      const toId = String(part.targetNode);
      const toSlot = part.targetSlot;
      const type = part.type;
      const fromNode = nodeMap[fromId];
      const toNode = nodeMap[toId];
      if (!fromNode || !toNode) return "";
      const fromX = (Array.isArray(fromNode.position) ? Number(fromNode.position[0]) || 0 : 0) + 184;
      const fromY = (Array.isArray(fromNode.position) ? Number(fromNode.position[1]) || 0 : 0) + workflowOutputPortY(fromNode, fromSlot);
      const toX = Array.isArray(toNode.position) ? Number(toNode.position[0]) || 0 : 0;
      const toY = (Array.isArray(toNode.position) ? Number(toNode.position[1]) || 0 : 0) + workflowInputPortY(toNode, toSlot);
      const dx = Math.max(30, Math.abs(toX - fromX) * 0.4);
      const d = `M ${fromX} ${fromY} C ${fromX + dx} ${fromY}, ${toX - dx} ${toY}, ${toX} ${toY}`;
      const colorClass = type === "CONDITIONING" ? "green" : type === "LATENT" ? "orange" : "";
      return `
        <path d="${d}" class="${colorClass}" data-link-id="${escapeHtml(linkId)}" pointer-events="none"></path>
        <path d="${d}" fill="none" stroke="transparent" stroke-width="14" style="cursor:pointer;pointer-events:stroke" data-api-action="delete-workflow-link" data-link-id="${escapeHtml(linkId)}" title="点击删除连线"></path>
      `;
    }).join("");
    return `<svg class="wf-connections" xmlns="http://www.w3.org/2000/svg">${paths}</svg>`;
  }

  // 画布（中栏）：可滚动画布区域，包含节点卡片和 SVG 连线。
  function workflowCanvasStageHTML(graph, selectedNodeId) {
    const nodes = graph.nodes || [];
    if (!nodes.length) {
      return `
        <div class="canvas" style="overflow:auto">
          <div class="production-empty-state" style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center">
            <span class="production-empty-icon">WC</span>
            <h2>画布为空</h2>
            <p>从左侧节点库选择节点添加到画布。</p>
          </div>
        </div>
      `;
    }
    // 计算画布尺寸：取所有节点最远位置加边距。
    let maxWidth = 0;
    let maxHeight = 0;
    nodes.forEach((n) => {
      const x = Array.isArray(n.position) ? Number(n.position[0]) || 0 : 0;
      const y = Array.isArray(n.position) ? Number(n.position[1]) || 0 : 0;
      const h = workflowNodeHeight(n);
      maxWidth = Math.max(maxWidth, x + 240);
      maxHeight = Math.max(maxHeight, y + h + 40);
    });
    const stageWidth = Math.max(maxWidth, 800);
    const stageHeight = Math.max(maxHeight, 500);
    const nodesHTML = nodes.map((n) => workflowNodeCardHTML(n, String(n.id) === String(selectedNodeId))).join("");
    const linksHTML = workflowLinksSVG(graph);
    return `
      <div class="canvas" id="workflow-canvas-area" style="overflow:auto">
        <div class="workflow-stage" style="position:relative;width:${stageWidth}px;height:${stageHeight}px;inset:auto;transform:scale(${workflowCanvasState.zoom || 1});transform-origin:0 0">
          ${workflowGroupsHTML(nodes, workflowCanvasState.layoutGroups)}
          ${linksHTML}
          ${nodesHTML}
        </div>
      </div>
    `;
  }

  // 检查器（右栏）：显示选中节点的属性和已绑定插槽。
  function workflowCanvasInspectorHTML(node, slots) {
    if (!node) {
      return `
        <div class="panel-header"><div><div class="panel-title">检查器</div><div class="panel-sub">未选中节点</div></div></div>
        <div class="inspector-section">
          <div class="empty-note">点击画布中的节点查看属性，或从左侧添加节点。</div>
        </div>
      `;
    }
    const title = node.title || node.type || "未命名节点";
    const type = node.type || "unknown";
    const mode = Number(node.mode) || 0;
    const widgets = Array.isArray(node.widgets_values) ? node.widgets_values : [];
    const inputs = Array.isArray(node.inputs) ? node.inputs : [];
    const outputs = Array.isArray(node.outputs) ? node.outputs : [];
    const nodeId = escapeHtml(node.id);
    const isUnknown = Boolean(node.is_unknown);
    const groups = workflowCanvasState.layoutGroups || [];
    const assignedGroup = groups.find((group) => (group.members || []).map(String).includes(String(node.id)));
    // 当前节点绑定的插槽
    const boundSlots = slots.filter((s) => String(s.node_id) === String(node.id));

    const widgetsHTML = widgets.map((w, i) => {
      const value = w === null || w === undefined ? "" : String(w);
      const isNumber = value !== "" && !isNaN(Number(value)) && value.length < 12;
      return `
        <div style="margin-bottom:8px">
          <label class="label">参数 ${i}</label>
          <input class="modal-input" type="${isNumber ? "number" : "text"}" value="${escapeHtml(value)}" data-widget-index="${i}" style="width:100%;height:32px;font-size:11px" />
        </div>
      `;
    }).join("");

    const inputsHTML = inputs.map((input, i) => `
      <div class="mini-list-item">
        <span class="mini-list-icon">${i}</span>
        <div class="mini-list-text">${escapeHtml(input.name || "输入")}<div class="mini-list-sub">${escapeHtml(input.type || "")}</div></div>
      </div>
    `).join("") || '<div class="empty-note">无输入端口</div>';

    const outputsHTML = outputs.map((output, i) => `
      <div class="mini-list-item">
        <span class="mini-list-icon">${i}</span>
        <div class="mini-list-text">${escapeHtml(output.name || "输出")}<div class="mini-list-sub">${escapeHtml(output.type || "")}</div></div>
      </div>
    `).join("") || '<div class="empty-note">无输出端口</div>';

    const slotsHTML = boundSlots.length
      ? boundSlots.map((slot) => `
        <div class="mini-list-item">
          <span class="mini-list-icon">◇</span>
          <div class="mini-list-text">${escapeHtml(slot.slot_type || "插槽")}<div class="mini-list-sub">${escapeHtml(slot.slot_name || slot.slot_key || slot.display_name || "")}</div></div>
          <button class="btn small danger-soft" type="button" data-api-action="delete-workflow-slot" data-slot-id="${escapeHtml(slot.id)}" data-slot-name="${escapeHtml(slot.slot_name || slot.slot_key || slot.display_name || "")}">删除</button>
        </div>
      `).join("")
      : '<div class="empty-note">该节点尚未绑定语义插槽</div>';

    return `
      <div class="panel-header">
        <div>
          <div class="panel-title">${escapeHtml(title)}</div>
          <div class="panel-sub">${escapeHtml(type)} · 节点 ${nodeId}</div>
        </div>
        <span class="status green"><i class="dot"></i>有效</span>
      </div>
      <div class="inspector-section">
        <label class="label">节点标题</label>
        <input class="modal-input" id="workflow-inspector-title" type="text" value="${escapeHtml(title)}" style="width:100%;height:32px;font-size:11px" ${isUnknown ? "disabled" : ""} />
        <div style="height:8px"></div>
        <label class="label">节点模式</label>
        <select class="modal-input" id="workflow-inspector-mode" style="width:100%;height:32px;font-size:11px" ${isUnknown ? "disabled" : ""}>
          <option value="0" ${mode === 0 ? "selected" : ""}>激活</option>
          <option value="2" ${mode === 2 ? "selected" : ""}>禁用</option>
          <option value="4" ${mode === 4 ? "selected" : ""}>旁路</option>
        </select>
        ${isUnknown ? '<div class="empty-note" style="margin-top:8px">节点定义未同步，节点与未知字段会原样保留，但不允许编辑。</div>' : ""}
      </div>
      <div class="inspector-section">
        <label class="label">组件值 (widgets_values)</label>
        ${widgetsHTML || '<div class="empty-note">无组件值</div>'}
      </div>
      <div class="inspector-section">
        <label class="label">输入端口</label>
        ${inputsHTML}
      </div>
      <div class="inspector-section">
        <label class="label">输出端口</label>
        ${outputsHTML}
      </div>
      <div class="inspector-section">
        <label class="label">语义插槽</label>
        ${slotsHTML}
        <div style="margin-top:10px">
          <button class="btn small soft" type="button" data-api-action="add-workflow-slot" data-node-id="${nodeId}">绑定插槽</button>
        </div>
      </div>
      <div class="inspector-section">
        <label class="label">规整位置</label>
        <div class="workflow-inspector-actions">
          <button class="btn small" type="button" data-api-action="reorder-workflow-node" data-node-id="${nodeId}" data-reorder-action="forward">前移</button>
          <button class="btn small" type="button" data-api-action="reorder-workflow-node" data-node-id="${nodeId}" data-reorder-action="backward">后移</button>
          <button class="btn small" type="button" data-api-action="reorder-workflow-node" data-node-id="${nodeId}" data-reorder-action="prev_column">上一列</button>
          <button class="btn small" type="button" data-api-action="reorder-workflow-node" data-node-id="${nodeId}" data-reorder-action="next_column">下一列</button>
          <button class="btn small" type="button" data-api-action="reorder-workflow-node" data-node-id="${nodeId}" data-reorder-action="to_top">置顶</button>
          <button class="btn small" type="button" data-api-action="reorder-workflow-node" data-node-id="${nodeId}" data-reorder-action="to_bottom">置底</button>
        </div>
      </div>
      <div class="inspector-section">
        <label class="label">分组泳道</label>
        <select class="modal-input" data-workflow-group-select data-node-id="${nodeId}" style="width:100%;height:32px;font-size:11px">
          <option value="">不属于任何分组</option>
          ${groups.map((group) => `<option value="${escapeHtml(group.id)}" ${assignedGroup && String(assignedGroup.id) === String(group.id) ? "selected" : ""}>${escapeHtml(group.title || "未命名分组")}</option>`).join("")}
        </select>
        <div class="workflow-group-create-row">
          <input class="modal-input" id="workflow-new-group-title" maxlength="80" placeholder="新分组名称" />
          <button class="btn small soft" type="button" data-api-action="create-workflow-group" data-node-id="${nodeId}">新建并加入</button>
        </div>
        ${assignedGroup ? `<button class="btn small danger-soft" type="button" data-api-action="delete-workflow-group" data-group-id="${escapeHtml(assignedGroup.id)}" data-group-title="${escapeHtml(assignedGroup.title || "未命名分组")}">删除当前分组</button>` : ""}
      </div>
      <div class="inspector-section" style="display:flex;gap:7px;flex-wrap:wrap">
        <button class="btn small" type="button" data-api-action="focus-workflow-node" data-node-id="${nodeId}" data-focus-direction="upstream">聚焦上游</button>
        <button class="btn small" type="button" data-api-action="focus-workflow-node" data-node-id="${nodeId}" data-focus-direction="downstream">聚焦下游</button>
        <button class="btn small soft" type="button" data-api-action="toggle-workflow-node-collapse" data-node-id="${nodeId}">${node.flags?.collapsed ? "展开节点" : "折叠节点"}</button>
        <button class="btn small soft" type="button" data-api-action="duplicate-workflow-node" data-node-id="${nodeId}" ${isUnknown ? "disabled" : ""}>复制节点</button>
        <button class="btn small danger-soft" type="button" data-api-action="delete-workflow-node" data-node-id="${nodeId}">删除节点</button>
      </div>
    `;
  }

  // 主渲染函数：从 URL 读取工作流 ID，加载草稿并渲染三栏布局。
  async function renderProductionWorkflowCanvas() {
    const page = document.querySelector(".page-scroll");
    if (!page) return;
    const header = page.querySelector(".page-header");
    [...page.children].forEach((child) => {
      if (child !== header) child.remove();
    });

    const params = new URLSearchParams(window.location.search);
    const workflowId = params.get("workflow");
    if (!workflowId) {
      page.insertAdjacentHTML("beforeend", workflowCanvasEmptyHTML("请从工作流库选择一个工作流进入画布。"));
      return;
    }

    // 占位骨架
    page.insertAdjacentHTML("beforeend", `
      <div class="three-pane" id="workflow-canvas-root" style="grid-template-columns:206px minmax(0,1fr) 274px;height:calc(100% - 79px)">
        <section class="panel" style="overflow:hidden"><div class="panel-header"><div><div class="panel-title">节点库</div></div></div></section>
        <section class="panel" style="overflow:hidden"><div class="panel-header"><div><div class="panel-title">画布加载中…</div></div></div></section>
        <section class="panel inspector" style="overflow:hidden"><div class="panel-header"><div><div class="panel-title">检查器</div></div></div></section>
      </div>
    `);

    workflowCanvasState.workflowId = workflowId;
    workflowCanvasState.loading = true;

    // 异步加载节点定义（不阻塞画布渲染）
    if (!workflowCanvasState.objectInfoLoaded) {
      request(`${API.comfyuiObjectInfo}?limit=500&offset=0`).then((payload) => {
        workflowCanvasState.objectInfo = normalizeWorkflowNodeDefinitions(payload);
        workflowCanvasState.objectInfoLoaded = true;
        renderWorkflowCanvasPalette();
      }).catch(() => {
        workflowCanvasState.objectInfoLoaded = true;
        renderWorkflowCanvasPalette();
      });
    }

    try {
      await loadWorkflowCanvasData(workflowId);
      // 如果所有节点都堆在 (0,0)（如 API JSON 导入后），自动计算布局
      const nodes = workflowCanvasState.graph.nodes || [];
      const allAtOrigin = nodes.length > 1 && nodes.every((n) => {
        const x = Array.isArray(n.position) ? Number(n.position[0]) || 0 : 0;
        const y = Array.isArray(n.position) ? Number(n.position[1]) || 0 : 0;
        return x === 0 && y === 0;
      });
      if (allAtOrigin) {
        try {
          await request(API.workflowDraftLayoutCompute(workflowId), {
            method: "POST",
            body: "{}",
          });
          await loadWorkflowCanvasData(workflowId);
        } catch (_) {
          // 布局失败不阻断渲染，用户可手动触发"自动整理"
        }
      }
      // 更新 header
      const title = header?.querySelector(".page-title");
      const subtitle = header?.querySelector(".page-subtitle");
      const actions = header?.querySelector(".header-actions");
      if (title) title.textContent = workflowCanvasState.workflowName || "工作流画布";
      const nodeCount = (workflowCanvasState.graph.nodes || []).length;
      const revision = workflowCanvasState.draftRevision != null ? `r${workflowCanvasState.draftRevision}` : "草稿";
      if (subtitle) subtitle.textContent = `${revision} · ${nodeCount} 节点 · ${workflowCanvasState.slots.length} 个语义插槽${workflowCanvasState.isDirty ? " · 有未保存修改" : ""}`;
      if (actions) actions.innerHTML = '<button class="btn primary" type="button" data-api-action="save-workflow-draft">保存草稿</button>';
      renderWorkflowCanvasContent();
    } catch (error) {
      const root = document.getElementById("workflow-canvas-root");
      if (root) root.remove();
      page.insertAdjacentHTML("beforeend", workflowCanvasErrorHTML(error.message));
    } finally {
      workflowCanvasState.loading = false;
    }
  }

  // 加载工作流草稿数据并更新本地状态。
  async function loadWorkflowCanvasData(workflowId) {
    const [response, slotResponse] = await Promise.all([
      request(API.workflowDraft(workflowId)),
      request(API.workflowSlots(workflowId)).catch(() => ({ slots: [] })),
    ]);
    // API 返回 {database_environment, draft: {...}}，提取 draft 对象。
    const draft = response.draft || response;
    // 工作流名称不在 draft 中，通过工作流详情 API 获取（如果有的话）。
    if (!workflowCanvasState.workflowName || workflowCanvasState.workflowName === "工作流画布") {
      try {
        const wfResp = await request(API.workflow(workflowId));
        workflowCanvasState.workflowName = wfResp.workflow?.name || "工作流画布";
      } catch (_) {
        workflowCanvasState.workflowName = "工作流画布";
      }
    }
    workflowCanvasState.draftRevision = draft.draft_revision != null ? draft.draft_revision : null;
    workflowCanvasState.isDirty = Boolean(draft.is_dirty);
    workflowCanvasState.graph = parseWorkflowGraph(draft);
    workflowCanvasState.slots = Array.isArray(slotResponse.slots)
      ? slotResponse.slots
      : parseWorkflowSlots(draft);
    try {
      const layoutState = typeof draft.layout_state === "string"
        ? JSON.parse(draft.layout_state || "{}")
        : (draft.layout_state || {});
      workflowCanvasState.layoutGroups = Array.isArray(layoutState.groups) ? layoutState.groups : [];
    } catch (_) {
      workflowCanvasState.layoutGroups = [];
    }
    if (!workflowCanvasState.selectedNodeId) {
      const first = (workflowCanvasState.graph.nodes || [])[0];
      if (first) workflowCanvasState.selectedNodeId = first.id;
    }
  }

  // 渲染画布全部内容（三栏），保留已选中节点。
  function renderWorkflowCanvasContent() {
    const root = document.getElementById("workflow-canvas-root");
    if (!root) return;
    const state = workflowCanvasState;
    const selectedNode = (state.graph.nodes || []).find((n) => String(n.id) === String(state.selectedNodeId)) || null;
    root.innerHTML = `
      <section class="panel" id="workflow-palette-panel" style="overflow:hidden;display:flex;flex-direction:column">
        <div class="panel-header"><div><div class="panel-title">节点库</div><div class="panel-sub">点击添加节点到画布</div></div></div>
        ${workflowCanvasPaletteHTML(state.objectInfo)}
      </section>
      <section class="panel" id="workflow-canvas-panel" style="overflow:hidden;display:flex;flex-direction:column">
        ${workflowCanvasToolbarHTML(state)}
        ${workflowCanvasStageHTML(state.graph, state.selectedNodeId)}
      </section>
      <section class="panel inspector" id="workflow-inspector" style="overflow-y:auto">
        ${workflowCanvasInspectorHTML(selectedNode, state.slots)}
      </section>
    `;
    bindWorkflowInspectorEvents();
    bindWorkflowPaletteSearch();
  }

  // 仅刷新节点库面板（object_info 加载完成后调用）。
  function renderWorkflowCanvasPalette() {
    const panel = document.getElementById("workflow-palette-panel");
    if (!panel) return;
    const header = panel.querySelector(".panel-header");
    if (header) {
      [...panel.children].forEach((c) => { if (c !== header) c.remove(); });
      panel.insertAdjacentHTML("beforeend", workflowCanvasPaletteHTML(workflowCanvasState.objectInfo));
    }
    bindWorkflowPaletteSearch();
  }

  // 刷新画布的中栏和右栏（用于选中节点或局部更新后）。
  function refreshWorkflowCanvasAndInspector() {
    const canvasPanel = document.getElementById("workflow-canvas-panel");
    if (canvasPanel) {
      const state = workflowCanvasState;
      canvasPanel.innerHTML = `${workflowCanvasToolbarHTML(state)}${workflowCanvasStageHTML(state.graph, state.selectedNodeId)}`;
    }
    const inspector = document.getElementById("workflow-inspector");
    if (inspector) {
      const state = workflowCanvasState;
      const selectedNode = (state.graph.nodes || []).find((n) => String(n.id) === String(state.selectedNodeId)) || null;
      inspector.innerHTML = workflowCanvasInspectorHTML(selectedNode, state.slots);
      bindWorkflowInspectorEvents();
    }
  }

  // 绑定检查器内联编辑事件：标题、模式、组件值在失焦时自动 PATCH。
  function bindWorkflowInspectorEvents() {
    const inspector = document.getElementById("workflow-inspector");
    if (!inspector) return;
    const titleInput = inspector.querySelector("#workflow-inspector-title");
    if (titleInput) {
      titleInput.addEventListener("blur", async () => {
        const val = titleInput.value.trim();
        const node = (workflowCanvasState.graph.nodes || []).find((n) => String(n.id) === String(workflowCanvasState.selectedNodeId));
        if (!node) return;
        if ((node.title || "") === val) return;
        workflowCanvasState.pendingMutation = patchWorkflowNode(node.id, { title: val });
        await workflowCanvasState.pendingMutation;
      });
    }
    const modeSelect = inspector.querySelector("#workflow-inspector-mode");
    if (modeSelect) {
      modeSelect.addEventListener("change", async () => {
        const val = Number(modeSelect.value) || 0;
        const node = (workflowCanvasState.graph.nodes || []).find((n) => String(n.id) === String(workflowCanvasState.selectedNodeId));
        if (!node) return;
        if ((Number(node.mode) || 0) === val) return;
        workflowCanvasState.pendingMutation = patchWorkflowNode(node.id, { mode: val });
        await workflowCanvasState.pendingMutation;
      });
    }
    const widgetInputs = inspector.querySelectorAll("[data-widget-index]");
    widgetInputs.forEach((input) => {
      input.addEventListener("blur", async () => {
        const node = (workflowCanvasState.graph.nodes || []).find((n) => String(n.id) === String(workflowCanvasState.selectedNodeId));
        if (!node) return;
        const widgets = Array.isArray(node.widgets_values) ? [...node.widgets_values] : [];
        const idx = Number(input.dataset.widgetIndex);
        const raw = input.value;
        // 数字字段尝试转为数字
        let val = raw;
        if (raw !== "" && !isNaN(Number(raw)) && raw.length < 12) val = Number(raw);
        if (widgets[idx] === val) return;
        widgets[idx] = val;
        workflowCanvasState.pendingMutation = patchWorkflowNode(node.id, { widgets_values: widgets });
        await workflowCanvasState.pendingMutation;
      });
    });
    const groupSelect = inspector.querySelector("[data-workflow-group-select]");
    if (groupSelect) {
      groupSelect.addEventListener("change", async () => {
        await assignWorkflowNodeGroup(groupSelect.dataset.nodeId, groupSelect.value || null);
      });
    }
  }

  // 绑定节点库搜索过滤。
  function bindWorkflowPaletteSearch() {
    const search = document.getElementById("workflow-palette-search");
    if (!search) return;
    search.addEventListener("input", () => {
      const q = search.value.trim().toLowerCase();
      const panel = document.getElementById("workflow-palette-panel");
      if (!panel) return;
      const items = panel.querySelectorAll(".palette-item");
      items.forEach((item) => {
        const text = item.textContent.toLowerCase();
        item.style.display = q && !text.includes(q) ? "none" : "";
      });
      window.clearTimeout(workflowCanvasState.paletteSearchTimer);
      workflowCanvasState.paletteSearchTimer = window.setTimeout(async () => {
        try {
          const params = new URLSearchParams({ limit: "300", offset: "0" });
          if (q) params.set("search", q);
          const payload = await request(`${API.comfyuiObjectInfo}?${params.toString()}`);
          workflowCanvasState.objectInfo = normalizeWorkflowNodeDefinitions(payload);
          renderWorkflowCanvasPalette();
          const nextSearch = document.getElementById("workflow-palette-search");
          if (nextSearch) {
            nextSearch.value = q;
            nextSearch.focus();
          }
        } catch (error) {
          // Keep the current local result list when the server search fails.
        }
      }, 260);
    });
  }

  // 选中节点并刷新检查器和高亮（不重新加载后端数据）。
  function selectWorkflowNode(nodeId) {
    workflowCanvasState.selectedNodeId = nodeId;
    // 仅更新节点卡片选中状态和检查器，避免完整重渲染
    const cards = document.querySelectorAll("#workflow-canvas-area .node-card");
    cards.forEach((card) => {
      card.classList.toggle("selected", card.dataset.nodeId === String(nodeId));
    });
    const inspector = document.getElementById("workflow-inspector");
    if (inspector) {
      const node = (workflowCanvasState.graph.nodes || []).find((n) => String(n.id) === String(nodeId)) || null;
      inspector.innerHTML = workflowCanvasInspectorHTML(node, workflowCanvasState.slots);
      bindWorkflowInspectorEvents();
    }
  }

  // PATCH 节点字段并刷新本地状态和画布。
  async function patchWorkflowNode(nodeId, patch) {
    try {
      const response = await request(API.workflowDraftNode(workflowCanvasState.workflowId, nodeId), {
        method: "PUT",
        body: JSON.stringify(patch),
      });
      const updated = response?.node || response;
      // 更新本地节点数据：优先使用后端返回值，回退到本地 patch
      const nodes = workflowCanvasState.graph.nodes || [];
      const idx = nodes.findIndex((n) => String(n.id) === String(nodeId));
      if (idx >= 0) {
        const merged = { ...nodes[idx], ...(updated || {}) };
        if (patch.title != null) merged.title = patch.title;
        if (patch.mode != null) merged.mode = patch.mode;
        if (patch.widgets_values != null) merged.widgets_values = patch.widgets_values;
        nodes[idx] = merged;
      }
      workflowCanvasState.isDirty = true;
      // 刷新画布节点卡片和工具栏的未保存标记（保持检查器不动以保留焦点）
      const canvasPanel = document.getElementById("workflow-canvas-panel");
      if (canvasPanel) {
        canvasPanel.innerHTML = `${workflowCanvasToolbarHTML(workflowCanvasState)}${workflowCanvasStageHTML(workflowCanvasState.graph, workflowCanvasState.selectedNodeId)}`;
      }
      if (typeof showToast === "function") showToast("节点已更新");
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    }
  }

  // 保存草稿：PUT 整个 normalized_graph 到后端。
  async function saveWorkflowDraft() {
    if (!workflowCanvasState.workflowId) return;
    const btn = document.querySelector('[data-api-action="save-workflow-draft"]');
    if (btn) { btn.disabled = true; btn.textContent = "保存中…"; }
    try {
      await workflowCanvasState.pendingMutation;
      await request(API.workflowDraft(workflowCanvasState.workflowId), {
        method: "PUT",
        body: JSON.stringify({
          normalized_graph: JSON.stringify(workflowCanvasState.graph),
        }),
      });
      workflowCanvasState.isDirty = false;
      await loadWorkflowCanvasData(workflowCanvasState.workflowId);
      refreshWorkflowCanvasAndInspector();
      if (typeof showToast === "function") showToast("草稿已保存");
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "保存"; }
    }
  }

  // 预检查：POST precheck 端点，弹窗显示结果。
  async function precheckWorkflow() {
    if (!workflowCanvasState.workflowId) return;
    const btn = document.querySelector('[data-api-action="precheck-workflow"]');
    if (btn) { btn.disabled = true; btn.textContent = "检查中…"; }
    try {
      const result = await request(API.workflowPrecheck(workflowCanvasState.workflowId), { method: "POST" });
      const warnings = Array.isArray(result.warnings) ? result.warnings : [];
      const errors = Array.isArray(result.errors) ? result.errors : [];
      const ok = errors.length === 0;
      const summary = ok
        ? `预检查通过${warnings.length ? `，${warnings.length} 条警告` : ""}`
        : `预检查失败：${errors.length} 条错误`;
      if (typeof showToast === "function") showToast(summary);
      const detail = [
        ...errors.map((e) => `✗ ${typeof e === "string" ? e : JSON.stringify(e)}`),
        ...warnings.map((w) => `⚠ ${typeof w === "string" ? w : JSON.stringify(w)}`),
      ].join("\n");
      if (detail) {
        await confirmDialog({ title: "预检查结果", message: detail, confirmText: "知道了", cancelText: "关闭", danger: !ok });
      }
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "预检查"; }
    }
  }

  // 新增节点：POST 到草稿节点集合。
  async function addWorkflowNode(nodeType) {
    if (!workflowCanvasState.workflowId) return;
    try {
      const nodes = workflowCanvasState.graph.nodes || [];
      const maxX = nodes.reduce((value, node) => {
        const x = Array.isArray(node.position) ? Number(node.position[0]) || 0 : 0;
        return Math.max(value, x);
      }, 0);
      const response = await request(API.workflowDraftNodes(workflowCanvasState.workflowId), {
        method: "POST",
        body: JSON.stringify({
          node_class: nodeType,
          position_x: maxX + 260,
          position_y: 80 + (nodes.length % 5) * 140,
        }),
      });
      const node = response?.node || response;
      if (node && node.id) {
        (workflowCanvasState.graph.nodes = workflowCanvasState.graph.nodes || []).push(node);
        workflowCanvasState.selectedNodeId = node.id;
        workflowCanvasState.isDirty = true;
        refreshWorkflowCanvasAndInspector();
        if (typeof showToast === "function") showToast(`节点「${nodeType}」已添加`);
      }
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    }
  }

  // 删除节点：确认后 DELETE，并清理本地连线和选中状态。
  async function deleteWorkflowNode(nodeId) {
    if (!workflowCanvasState.workflowId) return;
    const node = (workflowCanvasState.graph.nodes || []).find((n) => String(n.id) === String(nodeId));
    const name = node ? (node.title || node.type || "该节点") : "该节点";
    const ok = await confirmDialog({
      title: "删除节点",
      message: `确定删除「${name}」吗？关联的连线也会被移除。`,
      confirmText: "删除",
      cancelText: "取消",
      danger: true,
    });
    if (!ok) return;
    try {
      await request(API.workflowDraftNode(workflowCanvasState.workflowId, nodeId), { method: "DELETE" });
      workflowCanvasState.graph.nodes = (workflowCanvasState.graph.nodes || []).filter((n) => String(n.id) !== String(nodeId));
      workflowCanvasState.graph.links = (workflowCanvasState.graph.links || []).filter((l) => {
        const part = workflowLinkParts(l);
        return String(part.sourceNode) !== String(nodeId) && String(part.targetNode) !== String(nodeId);
      });
      if (String(workflowCanvasState.selectedNodeId) === String(nodeId)) {
        workflowCanvasState.selectedNodeId = (workflowCanvasState.graph.nodes[0] || {}).id || null;
      }
      workflowCanvasState.isDirty = true;
      refreshWorkflowCanvasAndInspector();
      if (typeof showToast === "function") showToast("节点已删除");
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    }
  }

  async function duplicateWorkflowNode(nodeId) {
    try {
      const response = await request(
        API.workflowDraftNodeDuplicate(workflowCanvasState.workflowId, nodeId),
        { method: "POST", body: "{}" }
      );
      const node = response.node;
      if (!node) throw new Error("后端未返回复制后的节点");
      workflowCanvasState.graph.nodes.push(node);
      workflowCanvasState.selectedNodeId = node.id;
      workflowCanvasState.isDirty = true;
      refreshWorkflowCanvasAndInspector();
      if (typeof showToast === "function") showToast("节点已复制");
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    }
  }

  async function reorderWorkflowNode(nodeId, action) {
    try {
      await request(API.workflowDraftNodeReorder(workflowCanvasState.workflowId, nodeId), {
        method: "POST",
        body: JSON.stringify({ action }),
      });
      await loadWorkflowCanvasData(workflowCanvasState.workflowId);
      workflowCanvasState.selectedNodeId = nodeId;
      refreshWorkflowCanvasAndInspector();
      if (typeof showToast === "function") showToast("节点位置已规整");
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    }
  }

  async function toggleWorkflowNodeCollapse(nodeId) {
    const node = workflowCanvasState.graph.nodes.find((item) => String(item.id) === String(nodeId));
    if (!node) return;
    const flags = { ...(node.flags || {}), collapsed: !Boolean(node.flags?.collapsed) };
    await patchWorkflowNode(nodeId, { flags });
    node.flags = flags;
    refreshWorkflowCanvasAndInspector();
  }

  async function createWorkflowGroup(nodeId) {
    const input = document.getElementById("workflow-new-group-title");
    const title = input?.value.trim().replace(/\s+/g, " ");
    if (!title) {
      if (typeof showToast === "function") showToast("请输入分组名称");
      input?.focus();
      return;
    }
    try {
      await request(API.workflowDraftGroups(workflowCanvasState.workflowId), {
        method: "POST",
        body: JSON.stringify({ title, members: [String(nodeId)] }),
      });
      await loadWorkflowCanvasData(workflowCanvasState.workflowId);
      workflowCanvasState.selectedNodeId = nodeId;
      refreshWorkflowCanvasAndInspector();
      if (typeof showToast === "function") showToast(`分组「${title}」已创建`);
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    }
  }

  async function assignWorkflowNodeGroup(nodeId, groupId) {
    try {
      await request(API.workflowDraftNodeAssignGroup(workflowCanvasState.workflowId, nodeId), {
        method: "POST",
        body: JSON.stringify({ group_id: groupId }),
      });
      await loadWorkflowCanvasData(workflowCanvasState.workflowId);
      workflowCanvasState.selectedNodeId = nodeId;
      refreshWorkflowCanvasAndInspector();
      if (typeof showToast === "function") showToast(groupId ? "节点已加入分组" : "节点已移出分组");
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    }
  }

  async function deleteWorkflowGroup(groupId, title) {
    const ok = await confirmDialog({
      title: "删除分组",
      message: `确定删除分组「${title}」吗？节点本身不会被删除。`,
      confirmText: "删除",
      cancelText: "取消",
      danger: true,
    });
    if (!ok) return;
    try {
      await request(API.workflowDraftGroup(workflowCanvasState.workflowId, groupId), { method: "DELETE" });
      await loadWorkflowCanvasData(workflowCanvasState.workflowId);
      refreshWorkflowCanvasAndInspector();
      if (typeof showToast === "function") showToast("分组已删除");
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    }
  }

  async function focusWorkflowNode(nodeId, direction = "both") {
    if (workflowCanvasState.focus && workflowCanvasState.focus.focus_node === String(nodeId)
        && workflowCanvasState.focus.direction === direction) {
      workflowCanvasState.focus = null;
      refreshWorkflowCanvasAndInspector();
      return;
    }
    try {
      const response = await request(API.workflowDraftFocus(workflowCanvasState.workflowId), {
        method: "POST",
        body: JSON.stringify({ node_id: String(nodeId), direction }),
      });
      workflowCanvasState.focus = response.focus || null;
      refreshWorkflowCanvasAndInspector();
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    }
  }

  function updateWorkflowZoom(delta, reset = false) {
    workflowCanvasState.zoom = reset
      ? 1
      : Math.min(1.5, Math.max(0.5, Math.round(((workflowCanvasState.zoom || 1) + delta) * 10) / 10));
    refreshWorkflowCanvasAndInspector();
  }

  // 新增连线：POST 到草稿连线集合，类型从源节点输出定义获取。
  async function addWorkflowLink(fromNodeId, fromSlot, toNodeId, toSlot) {
    if (!workflowCanvasState.workflowId) return;
    const fromNode = (workflowCanvasState.graph.nodes || []).find((n) => String(n.id) === String(fromNodeId));
    const outputs = fromNode && Array.isArray(fromNode.outputs) ? fromNode.outputs : [];
    const type = (outputs[fromSlot] || {}).type || "*";
    try {
      const response = await request(API.workflowDraftLinks(workflowCanvasState.workflowId), {
        method: "POST",
        body: JSON.stringify({
          source_node: String(fromNodeId),
          source_slot: fromSlot,
          target_node: String(toNodeId),
          target_slot: toSlot,
          link_type: type,
        }),
      });
      const link = response?.link || response;
      if (link && (Array.isArray(link) || link.id != null)) {
        (workflowCanvasState.graph.links = workflowCanvasState.graph.links || []).push(link);
        workflowCanvasState.isDirty = true;
        refreshWorkflowCanvasAndInspector();
        if (typeof showToast === "function") showToast("连线已创建");
      } else {
        // 后端可能返回完整图而非单条 link，刷新数据
        await loadWorkflowCanvasData(workflowCanvasState.workflowId);
        refreshWorkflowCanvasAndInspector();
        if (typeof showToast === "function") showToast("连线已创建");
      }
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    }
  }

  // 删除连线：确认后 DELETE。
  async function deleteWorkflowLink(linkId) {
    if (!workflowCanvasState.workflowId) return;
    const ok = await confirmDialog({
      title: "删除连线",
      message: "确定删除这条连线吗？",
      confirmText: "删除",
      cancelText: "取消",
      danger: true,
    });
    if (!ok) return;
    try {
      await request(API.workflowDraftLink(workflowCanvasState.workflowId, linkId), { method: "DELETE" });
      workflowCanvasState.graph.links = (workflowCanvasState.graph.links || []).filter(
        (link) => String(workflowLinkParts(link).id) !== String(linkId)
      );
      workflowCanvasState.isDirty = true;
      refreshWorkflowCanvasAndInspector();
      if (typeof showToast === "function") showToast("连线已删除");
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    }
  }

  // 新增语义插槽：PUT 到工作流插槽集合。
  async function addWorkflowSlot(payload) {
    if (!workflowCanvasState.workflowId) return;
    try {
      await request(API.workflowSlots(workflowCanvasState.workflowId), {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      await loadWorkflowCanvasData(workflowCanvasState.workflowId);
      refreshWorkflowCanvasAndInspector();
      closeWorkflowSlotModal();
      if (typeof showToast === "function") showToast("插槽已绑定");
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    }
  }

  // 删除语义插槽：确认后 DELETE（后端按 slot_name 删除）。
  async function deleteWorkflowSlot(slotId, slotName) {
    if (!workflowCanvasState.workflowId) return;
    const ok = await confirmDialog({
      title: "删除插槽",
      message: `确定删除插槽「${slotName || ""}」吗？`,
      confirmText: "删除",
      cancelText: "取消",
      danger: true,
    });
    if (!ok) return;
    try {
      await request(API.workflowSlot(workflowCanvasState.workflowId, slotName), { method: "DELETE" });
      workflowCanvasState.slots = workflowCanvasState.slots.filter((s) => String(s.id) !== String(slotId));
      refreshWorkflowCanvasAndInspector();
      if (typeof showToast === "function") showToast("插槽已删除");
    } catch (error) {
      if (typeof showToast === "function") showToast(error.message);
    }
  }

  // ==================== 发布弹窗 ====================
  function ensureWorkflowPublishModal() {
    let modal = document.getElementById("workflow-publish-modal");
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "workflow-publish-modal";
    modal.className = "atelier-modal-backdrop";
    modal.hidden = true;
    modal.innerHTML = `
      <section class="atelier-modal size-sm" role="dialog" aria-modal="true" aria-labelledby="workflow-publish-title">
        <div class="atelier-modal-icon">PB</div>
        <h2 id="workflow-publish-title">发布工作流版本</h2>
        <p>输入版本标签，发布后可在批量跑图中使用。</p>
        <form id="workflow-publish-form">
          <label class="label" for="workflow-publish-label">版本标签</label>
          <input id="workflow-publish-label" class="modal-input" name="label" maxlength="60" autocomplete="off" placeholder="例如 v1.0" required />
          <div class="modal-error" id="workflow-publish-error" role="alert"></div>
          <div class="modal-actions">
            <button class="btn" type="button" data-api-action="close-workflow-publish-modal">取消</button>
            <button class="btn primary" type="submit">发布</button>
          </div>
        </form>
      </section>
    `;
    document.body.appendChild(modal);
    modal.addEventListener("click", (event) => {
      if (event.target === modal) closeWorkflowPublishModal();
    });
    modal.querySelector("form").addEventListener("submit", submitWorkflowPublish);
    return modal;
  }

  function openWorkflowPublishModal() {
    const modal = ensureWorkflowPublishModal();
    modal.querySelector(".modal-error").textContent = "";
    modal.querySelector('input[name="label"]').value = "";
    modal.hidden = false;
    requestAnimationFrame(() => {
      modal.classList.add("show");
      modal.querySelector('input[name="label"]').focus();
    });
  }

  function closeWorkflowPublishModal() {
    const modal = document.getElementById("workflow-publish-modal");
    if (!modal) return;
    modal.classList.remove("show");
    window.setTimeout(() => { modal.hidden = true; }, 150);
  }

  async function submitWorkflowPublish(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const input = form.querySelector('input[name="label"]');
    const submit = form.querySelector('button[type="submit"]');
    const error = form.querySelector(".modal-error");
    const label = input.value.trim().replace(/\s+/g, " ");
    if (!label) {
      error.textContent = "请输入版本标签。";
      input.focus();
      return;
    }
    submit.disabled = true;
    submit.textContent = "发布中…";
    error.textContent = "";
    try {
      await request(API.workflowPublish(workflowCanvasState.workflowId), {
        method: "POST",
        body: JSON.stringify({
          label,
          normalized_graph: "",
          is_validated: true,
        }),
      });
      workflowCanvasState.isDirty = false;
      closeWorkflowPublishModal();
      await loadWorkflowCanvasData(workflowCanvasState.workflowId);
      refreshWorkflowCanvasAndInspector();
      if (typeof showToast === "function") showToast(`版本「${label}」已发布`);
    } catch (requestError) {
      error.textContent = requestError.message;
      input.focus();
    } finally {
      submit.disabled = false;
      submit.textContent = "发布";
    }
  }

  // ==================== 导出弹窗 ====================
  function ensureWorkflowExportModal() {
    let modal = document.getElementById("workflow-export-modal");
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "workflow-export-modal";
    modal.className = "atelier-modal-backdrop";
    modal.hidden = true;
    modal.innerHTML = `
      <section class="atelier-modal size-sm" role="dialog" aria-modal="true" aria-labelledby="workflow-export-title">
        <div class="atelier-modal-icon">EX</div>
        <h2 id="workflow-export-title">导出工作流</h2>
        <p>选择导出格式，下载工作流 JSON 文件。</p>
        <form id="workflow-export-form">
          <label class="label" for="workflow-export-format">导出格式</label>
          <select id="workflow-export-format" class="modal-input" name="format" style="height:36px">
            <option value="api_json">API 格式（prompt 链路）</option>
            <option value="ui_json">UI 格式（画布节点）</option>
          </select>
          <div class="modal-error" id="workflow-export-error" role="alert"></div>
          <div class="modal-actions">
            <button class="btn" type="button" data-api-action="close-workflow-export-modal">取消</button>
            <button class="btn primary" type="submit">导出</button>
          </div>
        </form>
      </section>
    `;
    document.body.appendChild(modal);
    modal.addEventListener("click", (event) => {
      if (event.target === modal) closeWorkflowExportModal();
    });
    modal.querySelector("form").addEventListener("submit", submitWorkflowExport);
    return modal;
  }

  function openWorkflowExportModal() {
    const modal = ensureWorkflowExportModal();
    modal.querySelector(".modal-error").textContent = "";
    modal.querySelector('select[name="format"]').value = "api_json";
    modal.hidden = false;
    requestAnimationFrame(() => {
      modal.classList.add("show");
    });
  }

  function closeWorkflowExportModal() {
    const modal = document.getElementById("workflow-export-modal");
    if (!modal) return;
    modal.classList.remove("show");
    window.setTimeout(() => { modal.hidden = true; }, 150);
  }

  async function submitWorkflowExport(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const format = form.querySelector('select[name="format"]').value;
    const submit = form.querySelector('button[type="submit"]');
    const error = form.querySelector(".modal-error");
    submit.disabled = true;
    submit.textContent = "导出中…";
    error.textContent = "";
    try {
      const data = await request(API.workflowExport(workflowCanvasState.workflowId), {
        method: "POST",
        body: JSON.stringify({ format }),
      });
      const json = JSON.stringify(data, null, 2);
      const blob = new Blob([json], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const safeName = (workflowCanvasState.workflowName || "workflow").replace(/[^\w\u4e00-\u9fa5-]/g, "_");
      a.download = `${safeName}_${format}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      closeWorkflowExportModal();
      if (typeof showToast === "function") showToast("工作流已导出");
    } catch (requestError) {
      error.textContent = requestError.message;
    } finally {
      submit.disabled = false;
      submit.textContent = "导出";
    }
  }

  // ==================== 插槽绑定弹窗 ====================
  function ensureWorkflowSlotModal() {
    let modal = document.getElementById("workflow-slot-modal");
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "workflow-slot-modal";
    modal.className = "atelier-modal-backdrop";
    modal.hidden = true;
    modal.innerHTML = `
      <section class="atelier-modal" role="dialog" aria-modal="true" aria-labelledby="workflow-slot-title">
        <div class="atelier-modal-icon">SL</div>
        <h2 id="workflow-slot-title">绑定语义插槽</h2>
        <p>选择插槽类型和绑定的节点输入。</p>
        <form id="workflow-slot-form">
          <label class="label" for="workflow-slot-type">插槽类型</label>
          <select id="workflow-slot-type" class="modal-input" name="slot_type" style="height:36px">
            <option value="positive_prompt">正向提示词</option>
            <option value="negative_prompt">负向提示词</option>
            <option value="character_prompt">人物提示词</option>
            <option value="lora_name">LoRA 名称</option>
            <option value="lora_weight">LoRA 权重</option>
            <option value="checkpoint">Checkpoint</option>
            <option value="vae">VAE</option>
            <option value="seed">Seed</option>
            <option value="width">Width</option>
            <option value="height">Height</option>
            <option value="batch_size">Batch Size</option>
            <option value="output_prefix">输出文件前缀</option>
            <option value="custom">自定义</option>
          </select>
          <div style="height:8px"></div>
          <label class="label" for="workflow-slot-key">插槽键名</label>
          <input id="workflow-slot-key" class="modal-input" name="slot_key" maxlength="80" autocomplete="off" placeholder="例如 character_a_lora" required />
          <div style="height:8px"></div>
          <label class="label" for="workflow-slot-input">绑定输入端口（可选）</label>
          <select id="workflow-slot-input" class="modal-input" name="input_name" style="height:36px">
            <option value="">不绑定具体输入</option>
          </select>
          <div class="modal-error" id="workflow-slot-error" role="alert"></div>
          <div class="modal-actions">
            <button class="btn" type="button" data-api-action="close-workflow-slot-modal">取消</button>
            <button class="btn primary" type="submit">绑定</button>
          </div>
        </form>
      </section>
    `;
    document.body.appendChild(modal);
    modal.addEventListener("click", (event) => {
      if (event.target === modal) closeWorkflowSlotModal();
    });
    modal.querySelector("form").addEventListener("submit", submitWorkflowSlot);
    return modal;
  }

  function openWorkflowSlotModal(nodeId) {
    const modal = ensureWorkflowSlotModal();
    const error = modal.querySelector(".modal-error");
    error.textContent = "";
    modal.querySelector('input[name="slot_key"]').value = "";
    modal.querySelector('select[name="slot_type"]').value = "positive_prompt";
    // 填充当前节点的输入端口选项
    const inputSelect = modal.querySelector('select[name="input_name"]');
    const node = (workflowCanvasState.graph.nodes || []).find((n) => String(n.id) === String(nodeId));
    const inputOpts = node && Array.isArray(node.inputs) ? node.inputs : [];
    inputSelect.innerHTML = '<option value="">不绑定具体输入</option>' + inputOpts.map((inp, i) => `<option value="${escapeHtml(inp.name || "")}">${i}: ${escapeHtml(inp.name || "")} (${escapeHtml(inp.type || "")})</option>`).join("");
    modal.dataset.nodeId = nodeId;
    modal.hidden = false;
    requestAnimationFrame(() => {
      modal.classList.add("show");
      modal.querySelector('input[name="slot_key"]').focus();
    });
  }

  function closeWorkflowSlotModal() {
    const modal = document.getElementById("workflow-slot-modal");
    if (!modal) return;
    modal.classList.remove("show");
    window.setTimeout(() => { modal.hidden = true; }, 150);
  }

  async function submitWorkflowSlot(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const modal = document.getElementById("workflow-slot-modal");
    const nodeId = modal?.dataset.nodeId;
    const slotType = form.querySelector('select[name="slot_type"]').value;
    const slotKey = form.querySelector('input[name="slot_key"]').value.trim().replace(/\s+/g, "_");
    const inputName = form.querySelector('select[name="input_name"]').value;
    const submit = form.querySelector('button[type="submit"]');
    const error = form.querySelector(".modal-error");
    if (!slotKey) {
      error.textContent = "请输入插槽键名。";
      return;
    }
    submit.disabled = true;
    submit.textContent = "绑定中…";
    error.textContent = "";
    try {
      await addWorkflowSlot({
        node_id: nodeId,
        slot_type: slotType,
        slot_name: slotKey,
        input_name: inputName || "",
      });
    } catch (requestError) {
      error.textContent = requestError.message;
    } finally {
      submit.disabled = false;
      submit.textContent = "绑定";
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
      const characterId = menu.dataset.contextCharacterId;
      hideContextMenu();
      if (action === "add-large-scene" && type === "chapter") {
        openLargeSceneModal(id, name);
      } else if (action === "add-small-scene" && type === "large-scene") {
        openSmallSceneCreateDialog(id, name);
      } else if (action === "open-small-scene" && type === "small-scene") {
        openSmallSceneRoute(id);
      } else if (action === "rename") {
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
      } else if (action === "copy" && type === "character-variant") {
        openCharacterVariantCopyModal(id, name);
      } else if ((action === "move-up" || action === "move-down") && type === "character-variant") {
        await reorderCharacterVariants(characterId, id, action === "move-up" ? "up" : "down");
      } else if (action === "delete") {
        if (type === "chapter") {
          await deleteChapter(id, name, largeSceneCount);
        } else if (type === "large-scene") {
          await deleteLargeScene(id, name);
        } else if (type === "small-scene") {
          await deleteSmallScene(id, name);
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

    // 阶段 3：批量草稿、批次和任务中心
    if (button.dataset.apiAction === "batch-create-first-draft") {
      await createBatchDraftFromInput("batch-first-name");
      return;
    }

    if (button.dataset.apiAction === "batch-new-draft") {
      const name = window.prompt("输入新的跑图批次名称", "");
      if (name === null) return;
      const trimmed = name.trim();
      if (!trimmed) {
        if (typeof showToast === "function") showToast("批次名称不能为空");
        return;
      }
      const payload = await request(API.batchDrafts(batchUiState.project.id), {
        method: "POST",
        body: JSON.stringify({ name: trimmed, scope: "project" }),
      });
      stage3Navigate("batch", {
        project: batchUiState.project.id,
        draft: payload.draft?.id,
      });
      return;
    }

    if (button.dataset.apiAction === "batch-delete-draft") {
      if (!window.confirm("删除这个尚未开始的批次配置？已经创建的任务不会受影响。")) return;
      await request(API.batchDraft(button.dataset.draftId), { method: "DELETE" });
      if (typeof showToast === "function") showToast("跑图批次配置已删除");
      stage3Navigate("batch", { project: batchUiState.project.id });
      return;
    }

    if (button.dataset.apiAction === "batch-save-draft") {
      try {
        await saveBatchDraft();
        await renderProductionBatch(batchUiState.project);
      } catch (error) {
        if (typeof showToast === "function") showToast(error.message);
      }
      return;
    }

    if (button.dataset.apiAction === "batch-preview-draft") {
      await previewBatchDraft();
      return;
    }

    if (button.dataset.apiAction === "batch-commit-draft") {
      try {
        await commitBatchDraft();
      } catch (error) {
        if (typeof showToast === "function") showToast(error.message);
      }
      return;
    }

    if (button.dataset.apiAction === "open-task-center") {
      stage3Navigate("tasks", {
        project: batchUiState.project?.id || taskUiState.project?.id,
        batch: button.dataset.batchId || "",
      });
      return;
    }

    if (button.dataset.apiAction === "open-batch-page") {
      stage3Navigate("batch", { project: taskUiState.project?.id });
      return;
    }

    if (button.dataset.apiAction === "task-refresh") {
      await renderProductionTasks(taskUiState.project, { preserveProgress: true });
      return;
    }

    if (button.dataset.apiAction === "task-start-batch") {
      await updateTaskBatchStatus(button.dataset.batchId, "running");
      if (typeof showToast === "function") showToast("批次已进入运行状态，点击“连续运行待处理项”开始提交");
      return;
    }

    if (button.dataset.apiAction === "task-run-queue") {
      void runTaskQueue(button.dataset.batchId);
      return;
    }

    if (button.dataset.apiAction === "task-stop-runner") {
      taskUiState.runnerActive = false;
      if (typeof showToast === "function") showToast("将在当前任务结束后停止自动领取");
      return;
    }

    if (button.dataset.apiAction === "task-pause-batch") {
      await updateTaskBatchStatus(button.dataset.batchId, "paused");
      if (typeof showToast === "function") showToast("批次已暂停，不再领取新任务");
      return;
    }

    if (button.dataset.apiAction === "task-cancel-batch") {
      if (!window.confirm("取消这个批次？已经提交到 ComfyUI 的任务不会被重复提交。")) return;
      await updateTaskBatchStatus(button.dataset.batchId, "cancelled");
      if (typeof showToast === "function") showToast("批次已取消");
      return;
    }

    if (button.dataset.apiAction === "task-control") {
      try {
        await request(API.task(button.dataset.taskId), {
          method: "PATCH",
          body: JSON.stringify({ action: button.dataset.taskAction }),
        });
        await renderProductionTasks(taskUiState.project, { preserveProgress: true });
      } catch (error) {
        if (typeof showToast === "function") showToast(error.message);
      }
      return;
    }

    if (button.dataset.apiAction === "task-retry-failed") {
      await retryFailedTasks();
      return;
    }

    if (button.dataset.apiAction === "task-resume-attempt") {
      try {
        await resumeTaskAttempt(button.dataset.attemptId);
      } catch (error) {
        if (typeof showToast === "function") showToast(error.message);
      }
      return;
    }

    if (button.dataset.apiAction === "task-recover-submitted") {
      try {
        const payload = await request(API.recoverSubmittedTasks, {
          method: "POST",
          body: "{}",
        });
        const recovery = payload.recovery || {};
        if (typeof showToast === "function") {
          showToast(`已核对 ${Number(recovery.checked) || 0} 项：完成 ${Number(recovery.recovered_completed) || 0}，失败 ${Number(recovery.recovered_failed) || 0}，未知 ${Number(recovery.marked_unknown) || 0}`);
        }
        await renderProductionTasks(taskUiState.project, { preserveProgress: true });
      } catch (error) {
        if (typeof showToast === "function") showToast(error.message);
      }
      return;
    }

    if (button.dataset.apiAction === "task-show-detail") {
      await showTaskDetail(button.dataset.taskId);
      return;
    }

    if (button.dataset.apiAction === "task-close-detail") {
      closeTaskDetail();
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

    if (button.dataset.apiAction === "materials-toggle-archived") {
      materialListState.trash = false;
      materialListState.archived = !materialListState.archived;
      await loadMaterials(false);
      return;
    }

    if (button.dataset.apiAction === "materials-toggle-trash") {
      if (materialListState.trash) {
        materialListState.trash = false;
      } else {
        materialListState.trash = true;
        materialListState.archived = false;
      }
      await loadMaterials(false);
      return;
    }

    if (button.dataset.apiAction === "materials-back-to-active") {
      materialListState.trash = false;
      materialListState.archived = false;
      await loadMaterials(false);
      return;
    }

    if (button.dataset.apiAction === "archive-material") {
      await archiveMaterial(button.dataset.materialId, button.dataset.materialName || "未命名素材");
      return;
    }

    if (button.dataset.apiAction === "restore-material") {
      await restoreMaterial(button.dataset.materialId, button.dataset.materialName || "未命名素材");
      return;
    }

    if (button.dataset.apiAction === "permanent-delete-material") {
      await permanentDeleteMaterial(button.dataset.materialId, button.dataset.materialName || "未命名素材");
      return;
    }

    if (button.dataset.apiAction === "copy-material") {
      openMaterialCopyModal(button.dataset.materialId, button.dataset.materialName || "未命名素材");
      return;
    }

    if (button.dataset.apiAction === "close-material-copy-modal") {
      closeMaterialCopyModal();
      return;
    }

    if (button.dataset.apiAction === "create-material-page") {
      openMaterialPageCreateModal();
      return;
    }

    if (button.dataset.apiAction === "close-material-page-modal") {
      closeMaterialPageModal();
      return;
    }

    if (button.dataset.apiAction === "edit-material-page") {
      await openMaterialPageEditModal(button.dataset.pageId);
      return;
    }

    if (button.dataset.apiAction === "delete-material-page") {
      await deleteMaterialPage(button.dataset.pageId, button.dataset.pageName || "未命名素材页");
      return;
    }

    if (button.dataset.apiAction === "copy-material-page") {
      await copyMaterialPage(button.dataset.pageId);
      return;
    }

    if (button.dataset.apiAction === "upload-material-page-preview") {
      openMaterialPagePreviewPicker(button.dataset.pageId);
      return;
    }

    if (button.dataset.apiAction === "remove-material-page-preview") {
      await removeMaterialPagePreview(button.dataset.pageId);
      return;
    }

    if (button.dataset.apiAction === "move-material-page-up") {
      await reorderMaterialPages(button.dataset.pageId, "up");
      return;
    }

    if (button.dataset.apiAction === "move-material-page-down") {
      await reorderMaterialPages(button.dataset.pageId, "down");
      return;
    }

    if (button.dataset.apiAction === "create-material-version") {
      await createMaterialVersion();
      return;
    }

    if (button.dataset.apiAction === "restore-material-version") {
      await restoreMaterialVersion(Number(button.dataset.versionNumber));
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

    if (button.dataset.apiAction === "edit-project") {
      openProjectEditModal(
        button.dataset.projectId,
        button.dataset.projectName,
        button.dataset.projectDescription
      );
      return;
    }

    if (button.dataset.apiAction === "archive-project") {
      await archiveProject(button.dataset.projectId, button.dataset.projectName);
      return;
    }

    if (button.dataset.apiAction === "restore-project") {
      await restoreProject(button.dataset.projectId, button.dataset.projectName);
      return;
    }

    if (button.dataset.apiAction === "copy-project") {
      openProjectCopyModal(button.dataset.projectId, button.dataset.projectName);
      return;
    }

    if (button.dataset.apiAction === "close-project-copy-modal") {
      closeProjectCopyModal();
      return;
    }

    if (button.dataset.apiAction === "delete-project") {
      await deleteProject(button.dataset.projectId, button.dataset.projectName);
      return;
    }

    if (button.dataset.apiAction === "permanent-delete-project") {
      await permanentDeleteProject(button.dataset.projectId, button.dataset.projectName);
      return;
    }

    if (button.dataset.apiAction === "upload-project-cover") {
      openProjectCoverPicker(button.dataset.projectId, button.dataset.projectName);
      return;
    }

    if (button.dataset.apiAction === "remove-project-cover") {
      await removeProjectCover(button.dataset.projectId, button.dataset.projectName);
      return;
    }

    if (button.dataset.apiAction === "projects-toggle-archived") {
      projectsListState.trash = false;
      projectsListState.archived = !projectsListState.archived;
      await renderProductionProjects();
      return;
    }

    if (button.dataset.apiAction === "projects-toggle-trash") {
      if (projectsListState.trash) {
        projectsListState.trash = false;
      } else {
        projectsListState.trash = true;
        projectsListState.archived = false;
      }
      await renderProductionProjects();
      return;
    }

    if (button.dataset.apiAction === "projects-back-to-active") {
      projectsListState.trash = false;
      projectsListState.archived = false;
      await renderProductionProjects();
      return;
    }

    if (button.dataset.apiAction === "load-more-projects") {
      await loadProjectsList(true);
      return;
    }

    if (button.dataset.apiAction === "retry-projects") {
      await loadProjectsList(false);
      return;
    }

    if (button.dataset.apiAction === "retry-overview") {
      const project = await resolveCurrentProject();
      if (project) await renderProductionOverview(project);
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

    if (button.dataset.apiAction === "select-character-spec") {
      renderSelectedCharacterSpec(button.dataset.specId);
      return;
    }

    if (button.dataset.apiAction === "add-spec") {
      await createCharacterSpec(button);
      return;
    }

    if (button.dataset.apiAction === "delete-character-spec") {
      const form = button.closest(".character-spec-simple-editor");
      const currentName = form?.elements.spec_name?.value.trim() || "未命名规格";
      await deleteProjectSpec(button.dataset.specId, currentName);
      return;
    }

    if (button.dataset.apiAction === "edit-character-spec") {
      const form = button.closest(".character-spec-simple-editor");
      if (!form) return;
      setCharacterSpecEditorMode(form, true);
      form.elements.spec_name?.focus();
      form.elements.spec_name?.select();
      return;
    }

    if (button.dataset.apiAction === "load-more-characters") {
      await loadCharacters(true);
      return;
    }

    if (button.dataset.apiAction === "retry-characters") {
      await loadCharacters(false);
      return;
    }

    if (button.dataset.apiAction === "characters-toggle-archived") {
      characterListState.trash = false;
      characterListState.archived = !characterListState.archived;
      await loadCharacters(false);
      return;
    }

    if (button.dataset.apiAction === "characters-toggle-trash") {
      if (characterListState.trash) {
        characterListState.trash = false;
      } else {
        characterListState.trash = true;
        characterListState.archived = false;
      }
      await loadCharacters(false);
      return;
    }

    if (button.dataset.apiAction === "characters-back-to-active") {
      characterListState.trash = false;
      characterListState.archived = false;
      characterListState.q = "";
      characterListState.tag = "";
      const search = document.getElementById("characters-search-input");
      const tag = document.getElementById("character-tag-filter");
      if (search) search.value = "";
      if (tag) tag.value = "";
      await loadCharacters(false);
      return;
    }

    if (button.dataset.apiAction === "archive-character") {
      await archiveCharacter(button.dataset.characterId, button.dataset.characterName || "未命名人物");
      return;
    }

    if (button.dataset.apiAction === "restore-character") {
      await restoreCharacter(button.dataset.characterId, button.dataset.characterName || "未命名人物");
      return;
    }

    if (button.dataset.apiAction === "copy-character") {
      openCharacterCopyModal(button.dataset.characterId, button.dataset.characterName || "未命名人物");
      return;
    }

    if (button.dataset.apiAction === "delete-character") {
      await deleteCharacter(button.dataset.characterId, button.dataset.characterName || "未命名人物");
      return;
    }

    if (button.dataset.apiAction === "permanent-delete-character") {
      await permanentDeleteCharacter(button.dataset.characterId, button.dataset.characterName || "未命名人物");
      return;
    }

    if (button.dataset.apiAction === "close-character-copy-modal") {
      closeCharacterCopyModal();
      return;
    }

    if (button.dataset.apiAction === "upload-character-cover") {
      openCharacterCoverPicker(button.dataset.characterId, button.dataset.characterName || "未命名人物");
      return;
    }

    if (button.dataset.apiAction === "remove-character-cover") {
      await removeCharacterCover(button.dataset.characterId, button.dataset.characterName || "未命名人物");
      return;
    }

    if (button.dataset.apiAction === "character-tag-add") {
      const section = button.closest(".character-tags-section");
      const input = section?.querySelector(".character-tag-add-input");
      if (section && input) {
        await addCharacterTag(section.dataset.characterId, input.value);
      }
      return;
    }

    if (button.dataset.apiAction === "character-tag-remove") {
      const section = button.closest(".character-tags-section");
      if (section) {
        await removeCharacterTag(section.dataset.characterId, button.dataset.tag);
      }
      return;
    }

    if (button.dataset.apiAction === "archive-character-variant") {
      await archiveCharacterVariant(button.dataset.variantId, button.dataset.variantName || "未命名变体");
      return;
    }

    if (button.dataset.apiAction === "restore-character-variant") {
      await restoreCharacterVariant(button.dataset.variantId, button.dataset.variantName || "未命名变体");
      return;
    }

    if (button.dataset.apiAction === "copy-character-variant") {
      openCharacterVariantCopyModal(button.dataset.variantId, button.dataset.variantName || "未命名变体");
      return;
    }

    if (button.dataset.apiAction === "delete-character-variant") {
      await deleteCharacterVariant(
        button.dataset.variantId,
        button.dataset.variantName || "未命名变体",
        button.dataset.isDefault === "1"
      );
      return;
    }

    if (button.dataset.apiAction === "upload-variant-preview") {
      openVariantPreviewPicker(button.dataset.variantId, button.dataset.variantName || "未命名变体");
      return;
    }

    if (button.dataset.apiAction === "remove-variant-preview") {
      await removeVariantPreview(button.dataset.variantId);
      return;
    }

    if (button.dataset.apiAction === "move-variant-up" || button.dataset.apiAction === "move-variant-down") {
      const scroll = document.getElementById("character-detail-modal-scroll");
      const characterId = scroll && scroll.querySelector("[data-character-id]")?.dataset.characterId;
      if (characterId) {
        await reorderCharacterVariants(
          characterId,
          button.dataset.variantId,
          button.dataset.apiAction === "move-variant-up" ? "up" : "down"
        );
      }
      return;
    }

    if (button.dataset.apiAction === "save-character-matrix") {
      await saveCharacterMatrix();
      return;
    }

    if (button.dataset.apiAction === "retry-character-matrix") {
      await renderCharacterMatrix(button.dataset.characterId);
      return;
    }

    // 工作流库相关操作
    if (button.dataset.apiAction === "create-workflow") {
      openWorkflowCreateModal();
      return;
    }

    if (button.dataset.apiAction === "close-workflow-modal") {
      closeWorkflowCreateModal();
      return;
    }

    if (button.dataset.apiAction === "import-workflow-json") {
      openWorkflowImportModal();
      return;
    }

    if (button.dataset.apiAction === "close-workflow-import-modal") {
      closeWorkflowImportModal();
      return;
    }

    if (button.dataset.apiAction === "extract-workflow-from-image") {
      openWorkflowImagePicker();
      return;
    }

    if (button.dataset.apiAction === "open-workflow") {
      const wfId = button.dataset.workflowId;
      if (wfId) {
        const params = new URLSearchParams();
        params.set("page", "workflow-canvas");
        params.set("workflow", wfId);
        window.location.search = `?${params.toString()}`;
      }
      return;
    }

    if (button.dataset.apiAction === "archive-workflow") {
      await archiveWorkflow(button.dataset.workflowId, button.dataset.workflowName);
      return;
    }

    if (button.dataset.apiAction === "restore-workflow") {
      await restoreWorkflow(button.dataset.workflowId, button.dataset.workflowName);
      return;
    }

    if (button.dataset.apiAction === "copy-workflow") {
      await copyWorkflow(button.dataset.workflowId, button.dataset.workflowName);
      return;
    }

    if (button.dataset.apiAction === "delete-workflow") {
      await deleteWorkflow(button.dataset.workflowId, button.dataset.workflowName);
      return;
    }

    if (button.dataset.apiAction === "retry-workflows") {
      await loadWorkflowsList(false);
      return;
    }

    if (button.dataset.apiAction === "load-more-workflows") {
      await loadWorkflowsList(true);
      return;
    }

    // ==================== 工作流画布操作 ====================
    if (button.dataset.apiAction === "retry-workflow-canvas") {
      await renderProductionWorkflowCanvas();
      return;
    }

    if (button.dataset.apiAction === "save-workflow-draft") {
      await saveWorkflowDraft();
      return;
    }

    if (button.dataset.apiAction === "precheck-workflow") {
      await precheckWorkflow();
      return;
    }

    if (button.dataset.apiAction === "publish-workflow") {
      openWorkflowPublishModal();
      return;
    }

    if (button.dataset.apiAction === "close-workflow-publish-modal") {
      closeWorkflowPublishModal();
      return;
    }

    if (button.dataset.apiAction === "export-workflow") {
      openWorkflowExportModal();
      return;
    }

    if (button.dataset.apiAction === "close-workflow-export-modal") {
      closeWorkflowExportModal();
      return;
    }

    if (button.dataset.apiAction === "add-workflow-node") {
      await addWorkflowNode(button.dataset.nodeType);
      return;
    }

    if (button.dataset.apiAction === "delete-workflow-node") {
      await deleteWorkflowNode(button.dataset.nodeId);
      return;
    }

    if (button.dataset.apiAction === "duplicate-workflow-node") {
      await duplicateWorkflowNode(button.dataset.nodeId);
      return;
    }

    if (button.dataset.apiAction === "toggle-workflow-node-collapse") {
      await toggleWorkflowNodeCollapse(button.dataset.nodeId);
      return;
    }

    if (button.dataset.apiAction === "reorder-workflow-node") {
      await reorderWorkflowNode(button.dataset.nodeId, button.dataset.reorderAction);
      return;
    }

    if (button.dataset.apiAction === "create-workflow-group") {
      await createWorkflowGroup(button.dataset.nodeId);
      return;
    }

    if (button.dataset.apiAction === "delete-workflow-group") {
      await deleteWorkflowGroup(button.dataset.groupId, button.dataset.groupTitle || "未命名分组");
      return;
    }

    if (button.dataset.apiAction === "focus-workflow-node") {
      await focusWorkflowNode(button.dataset.nodeId, button.dataset.focusDirection || "both");
      return;
    }

    if (button.dataset.apiAction === "select-workflow-node") {
      selectWorkflowNode(button.dataset.nodeId);
      return;
    }

    // 点击输出端口：暂存为连线起点
    if (button.dataset.apiAction === "add-workflow-link-from") {
      workflowCanvasState.pendingLinkFrom = {
        nodeId: button.dataset.nodeId,
        slot: Number(button.dataset.slot) || 0,
      };
      if (typeof showToast === "function") showToast("已选择输出端口，点击输入端口完成连线");
      return;
    }

    // 点击输入端口：若已有起点则创建连线
    if (button.dataset.apiAction === "add-workflow-link-to") {
      if (!workflowCanvasState.pendingLinkFrom) {
        if (typeof showToast === "function") showToast("请先点击一个输出端口");
        return;
      }
      const from = workflowCanvasState.pendingLinkFrom;
      workflowCanvasState.pendingLinkFrom = null;
      await addWorkflowLink(from.nodeId, from.slot, button.dataset.nodeId, Number(button.dataset.slot) || 0);
      return;
    }

    if (button.dataset.apiAction === "delete-workflow-link") {
      await deleteWorkflowLink(button.dataset.linkId);
      return;
    }

    if (button.dataset.apiAction === "add-workflow-slot") {
      openWorkflowSlotModal(button.dataset.nodeId);
      return;
    }

    if (button.dataset.apiAction === "delete-workflow-slot") {
      await deleteWorkflowSlot(button.dataset.slotId, button.dataset.slotName);
      return;
    }

    if (button.dataset.apiAction === "close-workflow-slot-modal") {
      closeWorkflowSlotModal();
      return;
    }

    if (
      button.dataset.apiAction === "workflow-layout-ltr" ||
      button.dataset.apiAction === "workflow-auto-layout"
    ) {
      await autoLayoutWorkflow();
      return;
    }

    if (button.dataset.apiAction === "workflow-focus-path") {
      if (workflowCanvasState.focus) {
        workflowCanvasState.focus = null;
        refreshWorkflowCanvasAndInspector();
      } else if (workflowCanvasState.selectedNodeId != null) {
        await focusWorkflowNode(workflowCanvasState.selectedNodeId, "both");
      } else if (typeof showToast === "function") {
        showToast("请先选择一个节点");
      }
      return;
    }

    if (button.dataset.apiAction === "workflow-zoom-in") {
      updateWorkflowZoom(0.1);
      return;
    }

    if (button.dataset.apiAction === "workflow-zoom-out") {
      updateWorkflowZoom(-0.1);
      return;
    }

    if (button.dataset.apiAction === "workflow-zoom-reset") {
      updateWorkflowZoom(0, true);
      return;
    }

    // ComfyUI 实例管理相关操作
    if (button.dataset.apiAction === "add-comfyui-instance") {
      openComfyuiInstanceAddModal();
      return;
    }

    if (button.dataset.apiAction === "close-comfyui-instance-modal") {
      closeComfyuiInstanceModal();
      return;
    }

    if (button.dataset.apiAction === "edit-comfyui-instance") {
      openComfyuiInstanceEditModal(button.dataset.instanceId, button.dataset.instanceName);
      return;
    }

    if (button.dataset.apiAction === "delete-comfyui-instance") {
      await deleteComfyuiInstance(button.dataset.instanceId, button.dataset.instanceName);
      return;
    }

    if (button.dataset.apiAction === "activate-comfyui-instance") {
      await activateComfyuiInstance(button.dataset.instanceId, button.dataset.instanceName);
      return;
    }

    if (button.dataset.apiAction === "test-comfyui-instance") {
      await testComfyuiInstance(button.dataset.instanceId, button.dataset.instanceName);
      return;
    }

    if (button.dataset.apiAction === "sync-comfyui-instance") {
      await syncComfyuiInstance(button.dataset.instanceId, button.dataset.instanceName);
      return;
    }

    if (button.dataset.apiAction === "discover-comfyui-instances") {
      await discoverComfyuiInstances();
      return;
    }

    if (button.dataset.apiAction === "retry-comfyui-instances") {
      await loadComfyuiInstances();
      return;
    }

    if (button.dataset.apiAction === "add-discovered-comfyui") {
      // 把发现的实例预填到添加弹窗中。
      openComfyuiInstanceAddModal();
      const modal = document.getElementById("comfyui-instance-modal");
      if (modal) {
        if (button.dataset.url) modal.querySelector('input[name="http_url"]').value = button.dataset.url;
        if (button.dataset.name) modal.querySelector('input[name="name"]').value = button.dataset.name;
      }
      return;
    }

    if (button.dataset.apiAction === "open-settings-from-status") {
      // 顶部状态指示器点击跳转到设置页。
      const params = new URLSearchParams(window.location.search);
      params.set("page", "settings");
      window.location.search = `?${params.toString()}`;
      return;
    }

    if (button.dataset.apiAction === "close-rename-modal") {
      closeRenameModal();
      return;
    }

    // ==================== 分支管理action ====================
    if (button.dataset.apiAction === "manage-branches") {
      await openBranchModal(button.dataset.projectId);
      return;
    }

    if (button.dataset.apiAction === "close-branch-modal") {
      if (button.dataset.mode === "cancel-edit") {
        // 取消编辑：刷新分支列表恢复原卡片
        const modal = document.getElementById("branch-manage-modal");
        const projectId = modal?.dataset.projectId;
        if (projectId) await refreshBranchList(projectId);
        return;
      }
      closeBranchModal();
      return;
    }

    if (button.dataset.apiAction === "create-branch") {
      await submitCreateBranch(button);
      return;
    }

    if (button.dataset.apiAction === "edit-branch") {
      if (button.dataset.mode === "save") {
        await submitEditBranch(button);
      } else {
        startEditBranch(button);
      }
      return;
    }

    if (button.dataset.apiAction === "delete-branch") {
      await deleteBranch(button.dataset.branchId, button.dataset.branchName || "未命名分支");
      return;
    }

    if (button.dataset.apiAction === "toggle-branch-active") {
      await toggleBranchActive(
        button.dataset.branchId,
        button.dataset.branchActive === "1",
        button.dataset.branchName || "未命名分支"
      );
      return;
    }

    if (button.dataset.apiAction === "add-branch-override") {
      if (button.dataset.mode === "save") {
        await submitAddBranchOverride(button);
      } else {
        await showBranchOverrides(button.dataset.branchId, button.dataset.branchName || "");
      }
      return;
    }

    if (button.dataset.apiAction === "delete-branch-override") {
      await deleteBranchOverride(button.dataset.overrideId);
      return;
    }

    // ==================== 快照action ====================
    if (button.dataset.apiAction === "show-snapshots") {
      await openSnapshotModal(button.dataset.projectId);
      return;
    }

    if (button.dataset.apiAction === "close-snapshot-modal") {
      closeSnapshotModal();
      return;
    }

    if (button.dataset.apiAction === "create-snapshot") {
      await submitCreateSnapshot(button);
      return;
    }

    if (button.dataset.apiAction === "restore-snapshot") {
      await restoreSnapshot(button.dataset.snapshotId, button.dataset.snapshotLabel || "未命名");
      return;
    }

    // ==================== 撤销重做action ====================
    if (button.dataset.apiAction === "undo-operation") {
      await undoLastOperation(button.dataset.projectId);
      return;
    }

    if (button.dataset.apiAction === "redo-operation") {
      await redoLastOperation(button.dataset.projectId);
      return;
    }

    // ==================== 预检查action ====================
    if (button.dataset.apiAction === "run-precheck") {
      openPrecheckModal(button.dataset.projectId);
      return;
    }

    if (button.dataset.apiAction === "close-precheck-modal") {
      closePrecheckModal();
      return;
    }

    if (button.dataset.apiAction === "execute-precheck") {
      await executePrecheck(button);
      return;
    }

    if (button.dataset.apiAction === "jump-precheck-issue") {
      jumpToPrecheckIssue(button.dataset.entityType, button.dataset.entityId);
      return;
    }
  });

  document.addEventListener("click", (event) => {
    const card = event.target.closest(".real-project-card");
    if (!card) return;
    if (event.target.closest("button, a, input, select, textarea")) return;
    if (card.classList.contains("real-project-trash-card")) return;
    if (card.classList.contains("real-project-card-skeleton")) return;
    // 工作流卡片由独立处理器接管，避免误跳到项目概览。
    if (card.classList.contains("real-workflow-card")) return;
    const params = new URLSearchParams();
    params.set("page", "overview");
    params.set("project", card.dataset.projectId);
    window.location.search = `?${params.toString()}`;
  });

  // 工作流卡片点击：跳转到工作流画布。
  document.addEventListener("click", (event) => {
    const card = event.target.closest(".real-workflow-card");
    if (!card || event.target.closest("button, a, input, select, textarea")) return;
    const wfId = card.dataset.workflowId;
    if (!wfId) return;
    const params = new URLSearchParams();
    params.set("page", "workflow-canvas");
    params.set("workflow", wfId);
    window.location.search = `?${params.toString()}`;
  });

  document.addEventListener("click", (event) => {
    const card = event.target.closest(".real-material-card");
    if (!card || event.target.closest("button, a, input, select, textarea")) return;
    if (card.classList.contains("material-trash-card")) return;
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
    if (card.classList.contains("material-trash-card")) return;
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
      closeProjectCopyModal();
      closeChapterModal();
      closeLargeSceneModal();
      closeLargeSceneEditModal();
      closeCharacterModal();
      closeRenameModal();
      closeConfirmDialog();
      closeMaterialCreateModal();
      closeMaterialCopyModal();
      closeMaterialPageModal();
      closeWorkflowCreateModal();
      closeWorkflowImportModal();
      closeComfyuiInstanceModal();
      closeWorkflowPublishModal();
      closeWorkflowExportModal();
      closeWorkflowSlotModal();
      closeBranchModal();
      closeSnapshotModal();
      closePrecheckModal();
    }
  });

  window.addEventListener("beforeunload", (event) => {
    if (!materialDetailState.dirty) return;
    event.preventDefault();
    event.returnValue = "";
  });

  // 场景页详情区：未保存提示词时刷新/离开页面提示
  window.addEventListener("beforeunload", (event) => {
    const detail = storyWorkspaceState.shotPageDetail;
    if (detail && detail.promptDirty) {
      event.preventDefault();
      event.returnValue = "";
    }
  });

  document.addEventListener("submit", async (event) => {
    const form = event.target.closest("form[data-inline-action]");
    if (!form) return;
    const action = form.dataset.inlineAction;
    if (action === "create-variant") {
      event.preventDefault();
      await submitInlineVariant(form);
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
      if (typeof showToast === "function") showToast(`形象「${name}」已创建`);
    } catch (requestError) {
      error.textContent = requestError.message;
      input.focus();
    } finally {
      submit.disabled = false;
      submit.textContent = "创建";
    }
  }

  async function createCharacterSpec(button) {
    const modal = document.getElementById("character-detail-modal");
    if (!modal || modal.hidden) return;
    const activeVariantId = characterSpecViewState.variantId;
    const activeVariantName = characterSpecViewState.variantName;
    const existingNames = new Set(characterSpecViewState.items.map(specLabel).filter(Boolean));
    let index = 1;
    let name = "未命名规格";
    while (existingNames.has(name)) {
      index += 1;
      name = `未命名规格 ${index}`;
    }
    button.disabled = true;
    button.textContent = "正在添加…";
    try {
      const payload = await request(API.specs, {
        method: "POST",
        body: JSON.stringify({ spec_type: "custom", custom_label: name }),
      });
      const specId = payload.spec?.id;
      await refreshCharacterDetail();
      if (activeVariantId && specId) {
        const tabs = modal.querySelectorAll(".variant-tab[data-variant-id]");
        tabs.forEach((tab) => tab.classList.toggle("active", tab.dataset.variantId === activeVariantId));
        await renderVariantSpecValues(activeVariantId, activeVariantName, specId);
      }
      const input = specId
        ? document.querySelector(`.character-spec-simple-editor input[data-spec-id="${cssEscape(specId)}"]`)
        : null;
      const form = input?.closest(".character-spec-simple-editor");
      if (form) setCharacterSpecEditorMode(form, true);
      input?.focus();
      input?.select();
      if (typeof showToast === "function") showToast("规格已添加，请填写名称和提示词");
    } catch (requestError) {
      if (typeof showToast === "function") showToast(requestError.message);
    } finally {
      if (button.isConnected) {
        button.disabled = false;
        button.textContent = "添加规格";
      }
    }
  }

  function setCharacterSpecEditorMode(form, editing) {
    form.classList.toggle("is-editing", editing);
    form.classList.toggle("is-viewing", !editing);
    const display = form.querySelector("[data-spec-display]");
    if (display) display.hidden = editing;
    form.querySelectorAll("[data-spec-edit-field]").forEach((field) => {
      field.hidden = !editing;
    });
    const editButton = form.querySelector('[data-api-action="edit-character-spec"]');
    const submitButton = form.querySelector('button[type="submit"]');
    if (editButton) editButton.hidden = editing;
    if (submitButton) submitButton.hidden = !editing;
  }

  async function submitCharacterSpecValue(form) {
    const submit = form.querySelector('button[type="submit"]');
    const status = form.querySelector(".spec-save-status");
    const nameInput = form.elements.spec_name;
    const specName = nameInput.value.trim().replace(/\s+/g, " ");
    if (!specName) {
      status.textContent = "请输入规格名称";
      status.className = "spec-save-status error";
      nameInput.focus();
      return;
    }
    const prompt = form.elements.prompt.value;

    submit.disabled = true;
    submit.textContent = "保存中…";
    status.textContent = "";
    status.className = "spec-save-status";
    try {
      if (form.dataset.specType === "custom" && specName !== form.dataset.originalName) {
        await request(API.spec(form.dataset.specId), {
          method: "PATCH",
          body: JSON.stringify({ custom_label: specName }),
        });
        form.dataset.originalName = specName;
        nameInput.dataset.name = specName;
      }
      await request(`/api/character-spec-values/${form.dataset.specValueId}`, {
        method: "PATCH",
        body: JSON.stringify({ prompt }),
      });
      const nameOutput = form.querySelector("[data-spec-name-output]");
      const promptOutput = form.querySelector("[data-spec-prompt-output]");
      if (nameOutput) nameOutput.textContent = specName;
      if (promptOutput) {
        promptOutput.textContent = prompt || "尚未填写提示词";
        promptOutput.classList.toggle("is-empty", !prompt.trim());
      }
      const stateItem = characterSpecViewState.items.find((item) => item.spec_id === form.dataset.specId);
      if (stateItem) {
        stateItem.custom_label = specName;
        stateItem.prompt = prompt;
      }
      const miniCard = document.querySelector(`.character-spec-mini-card[data-spec-id="${cssEscape(form.dataset.specId)}"]`);
      if (miniCard) {
        const miniName = miniCard.querySelector(".character-spec-mini-name");
        const miniState = miniCard.querySelector(".character-spec-mini-state");
        if (miniName) miniName.textContent = specName;
        if (miniState) {
          const filled = Boolean(prompt.trim());
          miniState.textContent = filled ? "已填写" : "未填写";
          miniState.classList.toggle("filled", filled);
        }
      }
      status.textContent = "已保存";
      status.className = "spec-save-status success";
      setCharacterSpecEditorMode(form, false);
      if (typeof showToast === "function") showToast(`规格「${specName}」已保存`);
    } catch (requestError) {
      status.textContent = requestError.message;
      status.className = "spec-save-status error";
    } finally {
      submit.disabled = false;
      submit.textContent = "保存规格";
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
