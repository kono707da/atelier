# Atelier

Atelier 是一套面向 ComfyUI 的项目化视觉生产工作台。

当前已开始按实际使用路径逐模块开发。现阶段包含可运行的 FastAPI
底座，以及生产/测试双数据库隔离功能；其他业务模块仍以 UI 设计预览为主。

## 当前可用功能

- FastAPI 单端口应用服务
- SQLite WAL 生产数据库：`data/databases/atelier.production.sqlite3`
- SQLite WAL 测试数据库：`data/databases/atelier.test.sqlite3`
- 设置页显示当前数据库、文件路径、大小和锁定状态
- 一键验证测试写入不会改变生产库
- 测试服务强制锁定测试数据库，拒绝切换到生产库
- 英文 BAT 启动脚本及端口归属检查

## 启动

首次使用：

```bat
setup.bat
```

你的正式应用：

```bat
start.bat
```

访问 `http://127.0.0.1:8110`。普通启动默认使用生产数据库。

开发测试应用：

```bat
start-test.bat
```

访问 `http://127.0.0.1:8111`。该进程锁定测试数据库，不能切换到生产数据库。

## 数据库安全规则

- 用户正式操作使用 `production`。
- 自动化测试和开发验证使用 `test`。
- 两套数据库具有不同的绝对文件路径和环境标记。
- 测试进程尝试切换生产库时返回 HTTP 409。
- 后端测试使用临时目录，不读取实际生产数据库。

## 设计交付

- [`design/Atelier-需求设计文档.md`](design/Atelier-需求设计文档.md)
- [`design/ui-preview/index.html`](design/ui-preview/index.html)
- `design/ui-preview/screenshots/`：全部页面 PNG 预览
- `design/ui-preview/contact-sheet.html`：页面总览

## 设计范围

- 明亮苹果风视觉系统
- ComfyUI 完整节点画布设计
- 线性剧本积木画布与分支设计
- 人物规格、提示词与 LoRA 语义插槽设计
- 批量出图、审片、多实例采用与最终排序设计
- 百万级图片索引与无阻塞预览方案

暂未实现：

- 项目、素材、剧本画布和工作流的持久化业务功能
- 旧数据导入
- AI 自动编剧或提示词生成

## 版本控制分支策略

本仓库区分不同 AI 协作者的产出，分支命名格式为 `dev-YYMMDD-<作者>-<简述>`：

- `dev-260727-chatgpt-baseline`：ChatGPT 协作开发的基线版本，包含 FastAPI 底座、双数据库隔离、项目/章节/大场景的完整后端与前端预览。
- `dev-260727-glm-*`：GLM 接管后的开发分支，与 ChatGPT 分支相互独立演进。

`main` 分支保存已通过验收的稳定基线，由各作者分支合并而来。
