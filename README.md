# Atelier

Atelier 是一套面向 ComfyUI 的项目化视觉生产工作台。

当前已按《Atelier 全功能产品与技术开发需求》逐阶段实现核心业务闭环。包含可运行的 FastAPI
底座、SQLite 生产数据库、版本化迁移框架，以及项目管理、素材库、人物库、剧本结构等
第一阶段功能。

## 当前可用功能

- FastAPI 单端口应用服务（默认 8110）
- SQLite WAL 生产数据库：`data/atelier.db`
- 版本化数据库迁移框架（`schema_migrations` 表追踪迁移版本，幂等执行）
- 核心编辑表乐观并发控制（`revision` 字段）
- 统一错误响应格式与 Request ID 追踪（响应头 `X-Request-ID`）
- 项目管理闭环：项目 CRUD、同名支持、搜索/筛选/排序/分页、归档/恢复、软删除/回收站/永久删除、项目复制、概览统计、封面上传
- 素材库闭环：素材归档/恢复/软删除/回收站/永久删除、引用反查、素材页预览图/复制、版本历史、素材复制
- 人物库闭环：人物/变体/规格的 CRUD、归档/恢复/软删除/永久删除、标签管理、预览图上传、复制、引用反查、规格矩阵管理、场景页人物绑定
- 剧本结构补全：分支条件字段、分支覆盖数据（人物/素材/参数，支持页面级优先）、剧本快照和版本、操作历史与撤销重做、页面级继承来源展示、编译预检查
- 章节和大场景的创建/改名/删除、跨章节移动
- 小场景工作区：场景页 CRUD、素材关联、素材页映射（同类型原子替换）
- 英文 BAT 启动脚本，启动前自动检查端口归属

## 启动

首次使用：

```bat
setup.bat
```

正式应用：

```bat
start.bat
```

访问 `http://127.0.0.1:8110`。

开发测试应用：

```bat
start-test.bat
```

## 数据库安全规则

- 用户界面只连接生产数据库，不展示数据库环境名称，不提供环境切换按钮。
- 自动化测试使用临时隔离数据目录，绝不能写入生产数据库。
- 数据库 schema 变更通过版本化迁移框架安全升级，支持 PRAGMA 检查和 ALTER TABLE 操作。

## 设计交付

- [`design/Atelier-需求设计文档.md`](design/Atelier-需求设计文档.md)
- [`design/ui-preview/index.html`](design/ui-preview/index.html)
- `design/ui-preview/screenshots/`：全部页面 PNG 预览
- `design/ui-preview/contact-sheet.html`：页面总览

## 版本控制分支策略

本仓库区分不同 AI 协作者的产出，分支命名格式为 `dev-YYMMDD-<作者>-<简述>`：

- `dev-260727-chatgpt-baseline`：ChatGPT 协作开发的基线版本，包含 FastAPI 底座、项目/章节/大场景的基础后端与前端预览。
- `dev-260729-GLM5.2-*`：GLM 接管后的开发分支，按全功能需求文档逐阶段实现核心业务闭环。

`main` 分支保存已通过验收的稳定基线；`GLM-MAIN` 分支为测试分支，开发分支合并至 `GLM-MAIN` 供用户测试通过后再合并到 `main`。

## 致谢

本项目参考并使用了以下开源项目的思路与工具：

- [FastAPI](https://fastapi.tiangolo.com/)
- [Pydantic](https://docs.pydantic.dev/)
- [SQLite](https://www.sqlite.org/)
