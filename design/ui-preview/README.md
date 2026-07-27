# Atelier UI 预览

本目录包含 Atelier 第一版明亮苹果风 UI 设计。

## 查看方式

- 直接打开 `contact-sheet.html` 查看全部页面总览。
- 打开 `index.html?page=页面键` 查看单页可复现原型。
- `screenshots/` 保存 1600×1000 的逐页 PNG。
- 在本目录执行 `node preview-server.mjs`，再访问 `http://127.0.0.1:8127` 查看可点击演示。

## 演示交互

- 侧边栏、项目卡片和关键流程按钮支持页面跳转。
- 剧本积木、画布分支、ComfyUI 节点和分镜页支持选中反馈。
- 审片候选可采用或取消采用，并实时更新本页采用数量。
- 最终作品分组支持拖拽排序，也可聚焦后使用左右方向键调整顺序。
- 标签页、工具按钮和未接后端的操作按钮均提供明确状态反馈。

## 页面与截图

| 编号 | 页面键 | 页面 | 截图 |
|---|---|---|---|
| 01 | `projects` | 项目中心 | `01-projects.png` |
| 02 | `overview` | 项目概览 | `02-overview.png` |
| 03 | `story-canvas` | 剧本画布 | `03-story-canvas.png` |
| 04 | `scene-editor` | 场景编辑 | `04-scene-editor.png` |
| 05 | `shot-inspector` | 分镜检查器 | `05-shot-inspector.png` |
| 06 | `materials` | 素材库 | `06-materials.png` |
| 07 | `material-detail` | 素材详情 | `07-material-detail.png` |
| 08 | `characters` | 人物库 | `08-characters.png` |
| 09 | `character-matrix` | 人物替换矩阵 | `09-character-matrix.png` |
| 10 | `workflows` | 工作流库 | `10-workflows.png` |
| 11 | `workflow-canvas` | 工作流画布 | `11-workflow-canvas.png` |
| 12 | `batch` | 批量配置 | `12-batch.png` |
| 13 | `tasks` | 任务中心 | `13-tasks.png` |
| 14 | `review` | 项目审片图库 | `14-review.png` |
| 15 | `assembly` | 最终作品装配 | `15-assembly.png` |
| 16 | `library` | 全局图库 | `16-library.png` |
| 17 | `image-detail` | 图片详情 | `17-image-detail.png` |
| 18 | `export` | 导出中心 | `18-export.png` |
| 19 | `settings` | 设置与 ComfyUI | `19-settings.png` |

## 设计说明

- 预览中的图片均为抽象占位图，仅用于表现布局和图片密度。
- ComfyUI 工作流画布展示自动分列、固定节点位置、端口连线、自定义节点库和语义插槽。
- 剧本画布展示主线、场景分支、形象变体覆盖和重新汇合。
- 项目审片支持单页同时采用多张实例，并在页内排序。
- 最终作品装配支持跨分镜页调整图片顺序，同时保留来源。
- 全局图库采用紧凑缩略图密度，实际开发使用游标分页与二维虚拟化。
