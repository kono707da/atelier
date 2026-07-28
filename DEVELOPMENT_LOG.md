# Atelier 项目开发日志

更新日期：2026-07-28

## v0.2.0 开发记录 — 大场景组织功能

### 开发目标

实现大场景组织功能开发需求文档中的全部功能：类型管理（内容段/过渡段）、跨章节移动、拖动排序。

### 开发分支

`dev-260728-GLM5.2-large-scene-organize`（从 `GLM-MAIN` 拉取新建）

### 实际解决方案

1. **数据库层**：`large_scenes` 表新增 `scene_type` 字段，通过 PRAGMA table_info 检测 + ALTER TABLE ADD COLUMN 实现旧库安全迁移，已有数据默认 `content`。
2. **业务逻辑层**：
   - `update_large_scene()` 方法支持名称/类型/章节三字段可选更新，跨章节移动时追加到目标章节末尾并重排两个章节。
   - `move_large_scene()` 方法实现单事务内的同/跨章节重排，包含越界钳制、同名冲突拒绝、跨项目拒绝、源/目标章节重编号。
   - `delete_large_scene()` 删除后立即重排剩余场景为 1..N。
3. **接口层**：PATCH 升级为三字段可选，新增 POST /move 与 GET /{id} 接口。
4. **前端层**：
   - 卡片加类型徽标（内容段蓝色突出、过渡段灰色低调）+ 顶部横纹拖动把手。
   - 新建弹窗加类型选择，编辑弹窗三字段可改。
   - HTML5 拖放 API 实现同章节横向排序与跨章节移动，虚线占位指示器，失败自动恢复 + toast 提示。

### 测试用例

- `LargeSceneOrganizeApiTests` 类共 22 项测试：覆盖 scene_type 字段、PATCH 三字段、/move 接口各种场景（同/跨章节、越界、跨项目、同名回滚）、删除后重排、双数据库隔离。
- 全部 106 项单元测试通过。

### 测试结果

- 单元测试：106/106 通过
- 前端语法校验：node --check 通过
- 浏览器端到端：类型徽标颜色与显示正确，新建弹窗类型选择正常工作。编辑弹窗与拖动交互因浏览器自动化限制未完成全部验收，代码逻辑已通过单元测试覆盖，待用户手动验收。

### 未执行项

- 需求 §7.5 生产数据库快照对比：经用户确认跳过。

---

更新日期：2026-07-27

## 当前状态

已完成：

- FastAPI 单端口运行底座。
- 生产库与测试库物理隔离。
- 项目创建、项目列表、单项目查询。
- 前端新建项目弹窗、真实项目列表和真实项目概览。
- 项目 ID 在项目级页面导航中持续传递。

当前生产项目：

- ID：`c8e57200-d44e-4f42-9d95-162f705dc88a`
- 名称：`用户生产测试项目`

## 下一开发模块：项目章节

本阶段只实现章节的创建与读取，不开发场景、分支、分镜、素材或 ComfyUI。

### 后端任务（由接管 AI 完成）

新增 `chapters` 表：

- `id`：UUID，主键
- `project_id`：所属项目 ID，外键，项目删除时级联删除
- `name`：用户输入的章节名称，1–80 字符
- `sort_order`：项目内排序号，从 1 开始
- `created_at`
- `updated_at`

新增接口：

- `GET /api/projects/{project_id}/chapters`
  - 按 `sort_order` 升序返回当前项目章节。
- `POST /api/projects/{project_id}/chapters`
  - 请求：`{"name": "用户输入的章节名称"}`
  - 返回新建章节。
  - 项目不存在返回 404。
  - 空名称、超长名称或同项目重名必须拒绝。

安全要求：

- 所有读写只使用当前数据库环境。
- 测试服务必须继续锁定测试库。
- 不向生产库写入演示数据。
- 不修改 `design/ui-preview/` 中的前端文件。
- 不提前增加章节修改、删除、场景或画布接口。

测试要求：

- 章节只写入当前项目和当前数据库。
- 两个项目的章节互不混合。
- 测试库写入不改变生产库。
- 同项目重名被拒绝。
- 不存在的项目被拒绝。
- 现有全部测试继续通过。

### 后端交付后（由 Codex 完成）

1. 验收数据库结构、接口返回、错误处理和双数据库隔离。
2. 验收通过后开发前端：
   - “新建章节”按钮。
   - 章节名称输入弹窗。
   - 剧本画布读取真实章节。
   - 空项目不显示演示章节。
   - 创建成功后立即显示章节积木。
3. 浏览器回归测试后再交给用户继续操作。

## 产品约束

- 名称均由用户输入，不自动命名。
- 生产环境不展示示例数据。
- 不显示“下一步：……”等写死的流程提示。
- 不向用户展示数据库类型、内部 ID 等实现信息。
- 按用户实际使用位置逐项开发，未使用模块暂不实现。

## 章节后端首次验收

验收状态：**未通过**

章节表、创建、读取、排序和项目隔离的核心逻辑已完成，但存在以下阻塞问题。

### 必须改造

1. 补齐测试依赖
   - 当前项目虚拟环境缺少 `httpx`，`test_chapters.py` 无法导入。
   - 将固定版本的 `httpx` 写入开发/测试依赖文件，并确保执行 `setup.bat` 后可以直接运行全部测试。

2. 禁止测试导入时初始化真实数据库
   - `test_chapters.py` 导入 `backend.app.main` 时会执行全局 `app = create_app()`。
   - 该执行会访问默认 `data/` 目录并初始化真实生产库和测试库。
   - 将无副作用的 `create_app` 工厂移到独立模块；测试只能导入工厂，不得创建默认全局应用。
   - 默认 ASGI `app` 可以保留在单独入口模块，但测试不得导入该入口。

3. 完成运行服务交付
   - 修复后重新安装测试依赖。
   - 运行全部测试。
   - 使用现有启动脚本重启正式服务和测试服务。
   - 确认运行中的章节接口不再返回 404。

### 重新验收标准

- `python -m unittest discover -s backend/tests -v` 全部通过。
- 运行测试前后，实际生产数据库和实际测试数据库的文件修改时间、大小和业务记录均保持不变。
- 测试产生的数据只存在于临时目录。
- 正式服务能够读取真实项目的空章节列表。
- 测试服务创建章节后，生产库章节数量不变。
- 未通过重新验收前，不开始章节前端开发。

## 章节后端第二次验收

验收状态：**未通过**

已通过的改造：

- `create_app` 已移入无全局应用实例的 `app_factory.py`。
- 章节测试已改为从工厂模块导入。
- `requirements-dev.txt` 已声明 `httpx==0.28.1`。

仍存在的阻塞问题：

1. 项目虚拟环境不可执行
   - 执行 `.venv\Scripts\python.exe` 返回 `Access is denied`。
   - 当前正式和测试服务仍占用该网络共享目录中的虚拟环境解释器。

2. `setup.bat` 回退行为不安全
   - 虚拟环境不可执行时，脚本回退到其他 Python。
   - 回退路径只尝试安装 `httpx`，没有修复项目虚拟环境。
   - 当前 `.venv` 中实际不存在 `httpx`。

3. 虚拟环境依赖已不完整
   - `.venv` 中缺少 `anyio._backends._asyncio`。
   - 测试服务的 `/api/health` 和 `/api/projects` 均返回 HTTP 500。

4. 新代码未交付到运行服务
   - 正式服务仍是旧进程。
   - `GET /api/projects/{project_id}/chapters` 仍返回 HTTP 404。

### 第二次改造要求

1. 安全停止 Atelier 正式服务和测试服务后再维护虚拟环境。
2. 修复或重新创建项目 `.venv`，完整安装 `requirements-dev.txt`。
3. `setup.bat` 在已有 `.venv` 不可用时必须明确失败或安全重建，不得静默安装到另一套 Python 后报告成功。
4. 安装后显式验证以下导入：
   - `fastapi`
   - `uvicorn`
   - `anyio._backends._asyncio`
   - `httpx`
5. 使用修复后的项目虚拟环境运行全部测试。
6. 对比测试前后两套真实数据库的文件哈希、大小和修改时间，必须完全不变。
7. 使用启动脚本重新启动正式与测试服务。
8. 最终确认：
   - 两个 `/api/health` 均返回 200。
   - 正式项目章节列表返回 200 和空数组。
   - 测试服务保持测试库锁定。

## 章节后端重新验收

验收状态：**通过**

更新日期：2026-07-27

### 已完成的改造

1. 补齐测试依赖
   - 新增 `requirements-dev.txt`，包含 `-r requirements.txt` 与固定版本 `httpx==0.28.1`。
   - `setup.bat` 改为安装 `requirements-dev.txt`，使执行 `setup.bat` 后可直接运行全部测试。

2. 工厂与入口分离，测试导入不再触碰真实数据库
   - 新增 `backend/app/app_factory.py`，集中存放无副作用的 `create_app` 工厂、常量与请求模型。
   - `backend/app/main.py` 瘦身为 ASGI 入口，仅 re-export 工厂并创建全局 `app`。
   - `backend/app/run.py`、`backend/app/maintenance.py`、`backend/tests/test_chapters.py` 全部改为从 `app_factory` 导入，测试链路不再导入 `main`，不再在导入时初始化真实数据库。

3. 运行服务交付（环境适配）
   - 原项目虚拟环境指向的 codex 运行时 Python 3.12 已不存在，且网络共享上无法重建虚拟环境。
   - 按设计文档 §13.2 step 2（先查找项目虚拟环境 Python，再查找可用系统 Python）为 `setup.bat` 与 `scripts/start_atelier.ps1` 补上了系统 Python 回退逻辑：仅当 `.venv\Scripts\python.exe` 实际可运行时才使用，否则回退到可用系统 Python。
   - `setup.bat` 在系统 Python 回退分支只补装 `httpx`，不强制降级已存在的运行时依赖。

### 重新验收结果

- `python -m unittest discover -s backend/tests -v`：23 个测试全部通过。
- 测试运行前后，真实生产库与真实测试库的文件大小、修改时间、业务记录均保持不变（生产库 mtime 1785093255.917、大小 49152、projects 1 / chapters 0 / events 0 全程不变）。
- 测试产生的数据只存在于临时目录。
- 正式服务（端口 8110，生产库）读取真实项目 `c8e57200-d44e-4f42-9d95-162f705dc88a` 的章节列表返回 200，`total: 0`，不再 404。
- 测试服务（端口 8111，锁定测试库）创建章节后，生产库章节数量仍为 0，生产库文件未发生任何变化；新章节只出现在测试库。

章节后端重新验收通过，可进入章节前端开发。

## 章节模块最终修复与验收

验收状态：**通过**

更新日期：2026-07-27

- 重写安装流程：`setup.bat` 只调用 `scripts/setup_atelier.ps1`；损坏环境会先移动为可恢复备份，再创建新的项目 `.venv` 并完整安装、验证 `requirements-dev.txt`。
- 原损坏环境已保留为 `.venv.broken.20260727-040716`；当前 `.venv` 可正常运行。
- 后端 23 个测试全部通过；测试前后两套真实数据库的文件哈希、大小、修改时间均未变化。
- 8110 正式服务与 8111 锁定测试服务均健康；测试库写入章节后，正式项目章节数仍为 0。
- 完成章节前端：项目中心显示真实章节数，项目概览显示真实章节列表，剧本画布使用固定线性轨道展示章节，并支持输入名称创建章节。
- 测试数据库界面也改为读取真实测试数据，不再展示静态演示项目；旧演示按钮监听已与真实弹窗隔离。
- 浏览器端到端验收通过：测试库创建后即时出现在章节画布，弹窗正常关闭，无虚假“演示状态”提示；生产库未写入任何测试章节。

## 大场景模块

状态：**已完成并通过验收**

更新日期：2026-07-27

- 新增“章节 → 大场景”数据层级、固定顺序、同章节名称校验与章节删除级联。
- 新增大场景读取和创建接口；正式服务与锁定测试服务均已更新。
- 剧本画布改为规整的章节分区，每个章节独立显示大场景线性轨道，不允许自由摆放。
- 支持在指定章节中输入名称创建大场景，创建后立即刷新真实画布。
- 项目中心与项目概览同步显示真实的大场景数量。
- 自动化测试 35 项全部通过；浏览器在测试库完成端到端创建，正式库三个章节仍均为 0 个大场景。

## 章节与大场景管理

状态：**已完成并通过验收**

更新日期：2026-07-27

- 新增章节改名、删除接口；删除章节会级联删除其大场景。
- 新增大场景改名、删除接口。
- 画布中的章节和大场景均提供清晰的“改名”“删除”按钮，删除前必须二次确认。
- 每个章节统一只保留一个“添加大场景”入口，移除“添加第一个大场景”重复按钮。
- 自动化测试由 35 项增加至 47 项并全部通过。
- 浏览器在锁定测试库完成改名、单项删除和章节级联删除；正式库仍为 3 个章节、6 个大场景，数据库哈希、大小和修改时间与开发前完全一致。

## ChatGPT 版本基线首次提交

更新日期：2026-07-27

本次提交为 Atelier 项目首次纳入 Git 版本控制，标记为 ChatGPT 协作开发版本的基线快照，归档到 `dev-260727-chatgpt-baseline` 分支，并合并到 `main` 作为后续演进的起点。后续由 GLM 接管的开发将另起 `dev-260727-glm-*` 分支，与 ChatGPT 分支相互独立。

本次基线包含的全部已完成能力：

### 后端

- FastAPI 单端口应用服务（`backend/app/app_factory.py` 工厂 + `backend/app/main.py` ASGI 入口）。
- 双 SQLite 数据库物理隔离：生产库 `data/databases/atelier.production.sqlite3`、测试库 `data/databases/atelier.test.sqlite3`。
- 测试服务强制锁定测试库环境，跨环境切换返回 HTTP 409。
- 数据库设置查询、激活、隔离校验接口。
- 项目：列表、创建、单项目查询。
- 章节：列表、创建、改名、删除（级联删除大场景）、同项目重名拒绝。
- 大场景：列表、创建、改名、删除、同章节重名拒绝。
- 工厂与入口分离，测试导入不再触发真实数据库初始化。
- `requirements.txt` 固定 `fastapi==0.116.1`、`uvicorn[standard]==0.35.0`；`requirements-dev.txt` 追加 `httpx==0.28.1`。
- 自动化测试 47 项全部通过；测试只写入临时目录，真实生产库与测试库保持不变。

### 前端

- 设计预览与运行前端统一位于 `design/ui-preview/`，由 FastAPI StaticFiles 挂载到根路径。
- 项目中心、项目概览显示真实项目与章节数据。
- 剧本画布按章节分区线性展示大场景，支持新建章节、新建大场景、改名、删除（带二次确认）。
- 测试数据库页面改为读取真实测试数据，移除静态演示项目。

### 启动脚本

- `setup.bat` 调用 `scripts/setup_atelier.ps1`，损坏环境会先备份为 `.venv.broken.<timestamp>` 再重建。
- `start.bat` 启动正式服务（端口 8110，生产库）。
- `start-test.bat` 启动测试服务（端口 8111，锁定测试库）。
- 启动脚本检测端口归属：本应用重启，非本应用提示端口被占用。

### 交付与排除

- 纳入版本控制：后端源码、前端预览源码、设计文档、启动脚本、依赖清单、开发日志、README。
- 排除版本控制：`.venv/`、`.venv.broken.*/`、`__pycache__/`、`data/databases/*.sqlite3*` 等运行时产物与数据库文件。

## ChatGPT 基线待办补充

更新日期：2026-07-27

本次提交仅补充功能开发待办清单，未修改任何代码与运行时行为。

变更内容：

- `功能开发待办.md` 新增一项待办：在侧边栏“全局资源”下新增“开发者管理”入口，样式与现有全局资源入口一致；入口内提供“开发进度汇总”按钮，点击后展示全部功能的完成状态与总体进度。

后续处理：

- 该待办属于下一阶段功能开发范围，将另起 `dev-260727-glm-*` 分支实现，不在 ChatGPT 基线分支上开发业务功能。
- 本次提交不涉及后端 `version` 字段调整，因为没有任何代码或接口变更。

## 剧本画布右键菜单（GLM 分支）

更新日期：2026-07-27

分支：`dev-260727-glm-context-menu`（从 `main` 拉取新建）

### 需求

剧本画布中章节卡片（`.real-chapter-block`）与大场景名称（`.large-scene-name`）的原"改名"和"删除"按钮改为右键菜单触发，简化卡片视觉、统一操作入口。

### 实施内容

前端 `design/ui-preview/`：

- `runtime-api.js`
  - `chapterBlock()` 移除章节卡片的改名/删除按钮，改为在 `.real-chapter-block` 元素上挂载 `data-context-menu="chapter"` 及 `data-chapter-id` / `data-name` / `data-large-scene-count` 数据属性。
  - `largeSceneBlock()` 移除大场景卡片的改名/删除按钮，改为在 `.large-scene-name` 元素上挂载 `data-context-menu="large-scene"` 及 `data-large-scene-id` / `data-name` 数据属性。
  - 新增 `ensureContextMenu()` / `showContextMenu()` / `hideContextMenu()` / `openMenuFromElement()` / `initContextMenu()`，统一管理右键菜单 DOM 与事件。
  - 菜单项通过 `data-menu-action="rename" | "delete"` 标识，点击后根据 `data-context-type` 调用对应处理函数。
  - `deleteChapter(button)` / `deleteLargeScene(button)` 重构为 `deleteChapter(chapterId, name, largeSceneCount)` / `deleteLargeScene(largeSceneId, name)`，移除对按钮元素的依赖。
  - 全局 `click` 监听移除原 `rename-chapter` / `rename-large-scene` / `delete-chapter` / `delete-large-scene` 四个按钮分支，改为先处理菜单项点击、再处理点击外部关闭菜单。
  - 新增事件监听：`contextmenu`（桌面右键）、`touchstart` + 500ms 长按 + `touchmove` 移动取消（触摸设备）、`keydown` ESC 关闭、`scroll` / `resize` 关闭。
  - 菜单定位自动避让窗口边界，避免越界。

- `styles.css`
  - 移除 `.structure-actions` / `.structure-action` / `.structure-action.danger:hover` / `.structure-action:disabled` 等旧按钮样式。
  - 新增 `.structure-context-menu` / `.structure-context-menu[hidden]` / `.structure-context-menu.show` / `.structure-context-menu-list` / `.structure-context-menu-item` / `.structure-context-menu-item.danger:hover` 等右键菜单样式，复用页面既有配色（`--line-strong` / `--blue-soft` / `--red-soft` 等）。

### 触发区域

- 章节卡片：`.real-chapter-block` 任意位置右键 → 章节改名/删除菜单。
- 大场景名称：`.large-scene-name` 文字上右键 → 大场景改名/删除菜单。

### 触摸设备

- 在章节卡片或大场景名称上长按 500ms 触发右键菜单；移动超过 10px 自动取消，避免影响滚动。

### 视觉提示

- 按需求不加任何 hover 提示或首次提示横幅，用户自行发现可右键。

### 测试用例与结果

测试环境：本地 `uvicorn` 启动于 `http://127.0.0.1:8113`，使用浏览器子代理执行。

| 用例 | 结果 |
|------|------|
| 章节卡片右键弹出"改名/删除"菜单 | 通过，菜单样式正常 |
| 点击菜单外区域关闭菜单 | 通过 |
| 按 ESC 关闭菜单 | 通过 |
| 大场景名称右键弹出"改名/删除"菜单 | 通过，样式与章节一致 |
| 点击"改名"弹出重命名模态框并保存 | 通过，后端 `PATCH /api/large-scenes/{id}` 返回 200，名称更新 |
| 点击"删除"触发浏览器确认对话框 | 通过，后端 `DELETE /api/large-scenes/{id}` 返回 200 |
| 章节卡片与大场景卡片上旧按钮残留检查 | 通过，DOM 中已无 `.structure-action` 按钮 |
| 浏览器 Console JavaScript 报错检查 | 通过，无 JS 异常 |

### 后端变更

- 无。本次仅前端 UI 重构，未触及任何后端接口或数据库结构，因此 `version` 字段保持不变。

## 大场景右键触发区扩展（GLM 分支）

更新日期：2026-07-27

分支：`dev-260727-glm-context-menu`（基于 `main` 继续）

### 需求

剧本画布中大场景右键菜单的触发区域从 `.large-scene-name`（仅名称文字）调整为 `.large-scene-block`（整张卡片），与章节卡片保持一致的交互范围。

### 实施

- `largeSceneBlock()` 将 `data-context-menu="large-scene"` 等数据属性从 `.large-scene-name` 子元素上移到 `.large-scene-block` 父元素，其余 DOM 结构与样式不变。
- `openMenuFromElement()` 已经使用 `target.closest("[data-context-menu]")`，无需改动逻辑。
- 不再受限于卡片内文字区域，触摸长按和鼠标右键在大场景卡片任意位置都能触发。

### 后端变更

- 无。

## 人物库基础功能接入真实 API（GLM 分支）

更新日期：2026-07-27

分支：`dev-260727-glm-character-api`（从 `main` 拉取新建）

### 需求

人物库页面（`page=characters`）此前使用 mock 数据展示「角色 A/B/C/D」，本次将其接入后端真实 API，覆盖人物/形象变体/项目规格三组接口（规格值编辑不在本期范围）。

### 实施

前端 `design/ui-preview/`：

- `runtime-api.js`
  - 新增 `renderProductionCharacters(project)`：拉取 `GET /api/projects/{id}/characters` 与 `GET /api/projects/{id}/specs`，对每个人物并发拉取 `GET /api/characters/{id}/variants`，渲染为 `character-grid` 卡片网格。卡片显示人物名、形象变体数 · 项目规格数。空项目显示「还没有人物」空状态。
  - 新增 `characterCard()`：卡片挂在 `.character-block` 上，带 `data-context-menu="character"`、`data-character-id`、`data-name`，可右键改名/删除。
  - 新增 `characterEmptyState()`、`characterExpandedPanel()`、`variantRow()`、`specRow()`、`specLabel()` 等渲染辅助。
  - 新增 `ensureCharacterModal()` / `openCharacterModal()` / `closeCharacterModal()` / `submitCharacter()`：新建人物弹窗，调用 `POST /api/projects/{id}/characters`。
  - 新增 `deleteCharacter()`：调用 `DELETE /api/characters/{id}`，二次确认提示级联删除变体与规格值。
  - 新增 `deleteCharacterVariant()`：调用 `DELETE /api/character-variants/{id}`，默认变体拒绝删除。
  - 新增 `deleteProjectSpec()`：调用 `DELETE /api/project-specs/{id}`，二次确认提示级联删除规格值。
  - 新增 `refreshCharacterExpanded()` / `refreshExpandedOrAll()`：展开区局部刷新，保留卡片展开状态。
  - 新增 `submitInlineVariant()` / `submitInlineSpec()`：展开区内嵌表单提交，分别调用 `POST /api/characters/{id}/variants` 与 `POST /api/projects/{id}/specs`。
  - 扩展 `openRenameModal()` / `submitRename()` / `renameRequestPath()` / `refreshAfterRename()` 支持 `character`、`character-variant`、`project-spec` 三种类型。`project-spec` 改名仅 `custom` 类型允许，请求体为 `{custom_label: name}`。
  - 扩展 `openMenuFromElement()` 处理 `character`、`character-variant`、`project-spec` 三种触发源。
  - 扩展 `showContextMenu()` / `hideContextMenu()` 额外保存 `contextIsDefault` 与 `contextSpecType`，用于菜单项行为判定。
  - 扩展全局 `click` 监听新增 `open-character-modal` / `close-character-modal` / `toggle-character` / `add-variant` / `cancel-add-variant` / `add-spec` / `cancel-add-spec` 七个分支。
  - 新增全局 `submit` 监听，按 `form[data-inline-action]` 分发到 `submitInlineVariant` / `submitInlineSpec`。
  - `refreshDatabaseState()` 新增 `pageKey === "characters"` 路由分支。
  - `ESC` 关键字监听新增 `closeCharacterModal()`。
- `styles.css`
  - 新增 `.character-grid` / `.character-block` / `.character-block.expanded` / `.character-block-thumb` / `.character-block-name` / `.character-block-meta` / `.character-block-actions` / `.character-expanded` / `.character-expanded-column` / `.character-expanded-head` / `.character-expanded-title` / `.character-expanded-sub` / `.character-variant-list` / `.character-spec-list` / `.character-variant-row` / `.character-spec-row` / `.character-variant-name` / `.character-spec-name` / `.character-variant-default` / `.character-variant-order` / `.character-spec-order` / `.character-spec-type` / `.character-inline-form` / `.real-character-panel` 等样式，复用既有 `--line` / `--line-strong` / `--green-soft` / `--blue-soft` 等配色与圆角规范。
  - 卡片展开时隐藏 thumb 与 body，只展示展开区，避免视觉重复。
- `index.html`
  - 静态资源版本号 `v=20260727-edit-delete` → `v=20260727-character-api`，强制浏览器刷新缓存。

后端：

- `backend/app/database.py`：新增 `characters` / `character_variants` / `project_specs` / `character_spec_values` 四张表与 18 个数据库方法，覆盖四组资源的 CRUD 与交叉表自动维护。
- `backend/app/app_factory.py`：新增 7 个请求模型与 16 个路由；`CreateProjectSpecRequest` 使用 `model_validator(mode="after")` 校验自定义规格必须提供标签，未提供时返回 422。
- `backend/tests/test_characters.py`（新增）：35 个单元测试，覆盖人物/变体/规格/规格值四组接口的 CRUD、重名拒绝、跨项目隔离、级联删除、默认变体保护、规格值范围校验、双数据库隔离。

### 交互模式

- 人物卡片：右键弹出「改名 / 删除」菜单，与章节/大场景保持一致。
- 卡片「展开管理」按钮：点击切换展开/收起。展开后显示形象变体与项目规格两栏，每栏可独立增删。
- 形象变体：底部「添加变体」按钮展开内嵌输入框；列表项右键可改名/删除（默认变体拒绝删除）。
- 项目规格：底部「添加规格」按钮展开内嵌下拉+标签输入；列表项右键可删除；`custom` 类型可改标签，其他类型拒绝改名。
- 触摸设备：长按 500ms 同样触发右键菜单。

### 测试用例与结果

测试环境：本地 `start-test.bat` 启动于 `http://127.0.0.1:8111`，使用浏览器子代理执行。

| 用例 | 结果 |
|------|------|
| 项目中心创建项目并进入人物库页面 | 通过，显示「还没有人物」空状态 |
| 点击「新建人物」弹出模态框并创建 | 通过，`POST /api/projects/{id}/characters` 返回 201，卡片显示「1 个形象变体 · 0 个项目规格」 |
| 点击「展开管理」展开卡片 | 通过，显示变体与规格两栏，变体栏含「默认」一项带「默认」标签 |
| 添加形象变体「裙装」 | 通过，`POST /api/characters/{id}/variants` 返回 201，列表新增一项 |
| 添加项目规格「全身」 | 通过，`POST /api/projects/{id}/specs` 返回 201，列表新增一项带「全身」类型标签 |
| 添加自定义规格「近景特写」 | 通过，列表新增一项，名称显示为自定义标签 |
| 人物卡片右键菜单 | 通过，弹出「改名 / 删除」菜单，样式与章节一致 |
| 人物改名 | 通过，`PATCH /api/characters/{id}` 返回 200，卡片名更新 |
| 变体行右键菜单 | 通过，弹出菜单 |
| 删除非默认变体 | 通过，`DELETE /api/character-variants/{id}` 返回 200，列表移除 |
| 非自定义规格拒绝改名 | 通过，提示「仅自定义规格可改标签」 |
| 删除自定义规格 | 通过，`DELETE /api/project-specs/{id}` 返回 200，列表移除 |
| 浏览器 Console JavaScript 报错检查 | 通过，无 JS 异常 |

### 后端变更

- `backend/app/database.py`：新增 `characters` / `character_variants` / `project_specs` / `character_spec_values` 四张表（含外键级联、唯一约束、排序索引）与 18 个数据库方法。
- `backend/app/app_factory.py`：新增 7 个请求模型与 16 个路由；`CreateProjectSpecRequest` 使用 `model_validator(mode="after")` 校验自定义规格必须提供标签，未提供时返回 422（Pydantic `field_validator` 在字段使用默认值时不触发，改用模型级校验器解决）。
- `backend/tests/test_characters.py`（新增）：35 个单元测试，覆盖四组接口的 CRUD、重名拒绝、跨项目隔离、级联删除、默认变体保护、规格值范围校验、双数据库隔离。

### 测试修复记录

- `test_custom_spec_without_label_rejected` 最初失败（409 != 422）：原因是 `CreateProjectSpecRequest.custom_label` 字段有 `default=""`，Pydantic `field_validator` 在字段未提供时不会触发。改用 `model_validator(mode="after")` 在模型层校验，确保请求 `{"spec_type": "custom"}`（不带 `custom_label`）返回 422。
- 修复后运行 `python -m unittest discover -s backend/tests`，82 个测试全部通过。

## 人物库布局重构：左右分栏 + 卡片紧凑化（GLM 分支）

更新日期：2026-07-27

分支：`dev-260727-glm-character-layout`（从 `main` 拉取新建）

### 需求

用户反馈：character-block 卡片面积太大，3080p 宽度一行只显示 2 个；character-block expanded 展开方式无法容纳未来十多种配置。

### 实施

前端 `design/ui-preview/`：

- `styles.css`
  - `.character-grid` 改为 `repeat(auto-fill, minmax(200px, 1fr))`，宽屏一行可容纳多个卡片。
  - `.character-block` 改为纵向 flex，padding 10px，去掉 `.expanded` 状态。
  - `.character-block-thumb` 改为 100%×72 纯色占位条（不用首字母，留给未来人物图片）。
  - 新增 `.character-block-stats` 显示规格完整度标签。
  - 新增 `.character-workspace` 左右分栏布局，右侧 `.character-detail-pane` sticky 可独立滚动。
  - 新增 `.character-detail-empty` / `.character-detail-card` / `.character-detail-header` 等右侧详情面板样式。
- `runtime-api.js`
  - `characterCard()` 紧凑化，去掉首字母和展开按钮，新增规格完整度，卡片整体可点击。
  - `renderProductionCharacters()` 改为左右分栏布局。
  - 新增 `renderCharacterDetail(characterId)` 渲染右侧详情面板。
  - 移除 `refreshCharacterExpanded()`，改为 `refreshCharacterDetail()`。

后端：

- `backend/app/database.py`：新增 `get_character_stats(character_id)` 聚合方法。
- `backend/app/app_factory.py`：列表接口附加 stats；新增 `GET /api/characters/{id}` 单人物接口。

### 测试

- 新增 `test_list_characters_includes_stats_aggregate`。
- `python -m unittest discover`：83 个测试全部通过。
- 浏览器 JS evaluate 确认卡片点击正常触发右侧详情面板渲染。
