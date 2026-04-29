# 项目清理删除清单 + GitHub 上传教程

运行方法：终端依次输入`docker compose down -v` 和 `docker compose up --build -d`，注意需要开启tun模式，否则build会失败

这份文档按你当前这个项目的实际结构整理，目标是：

- 给出“可以清理删除”的文件与文件夹清单
- 不自动删除任何文件，避免误删核心代码
- 保证你后续仍可用 `docker compose down -v` 和 `docker compose up --build -d` 正常运行
- 提供一份适合新手的 GitHub 上传教程

---

## 一、可以清理删除的文件和文件夹清单

下面这些内容属于缓存、构建产物、本地测试数据库、编辑器过程文件或 AI 工作痕迹。
删除后**不会影响核心源码结构**，也**不建议上传到 GitHub**。

### 1. 前端依赖与构建产物

- `frontend/node_modules/`
- `frontend/dist/`

说明：

- `frontend/node_modules/` 是前端依赖安装目录，可以随时重新 `npm install`
- `frontend/dist/` 是前端打包产物，可以随时重新 `npm run build`

### 2. Python 缓存与测试缓存

- `.pytest_cache/`
- 所有 `__pycache__/`

说明：

- 这些都是 Python 和 pytest 自动生成的缓存目录
- 删除后不会影响项目运行

### 3. 本地数据库文件

- `flight_ticketing.db`
- `alembic_test.db`

说明：

- 这两个是本地 SQLite 数据库文件
- 你的 Docker 运行主流程使用的是 MySQL 容器，不依赖它们
- 如果你只是做课程项目提交和上传 GitHub，这两个文件可以不保留

### 4. 编辑器/AI 过程文件

- `.obsidian/`
- `.codex/`
- `findings.md`
- `progress.md`
- `task_plan.md`
- `docs/plans/`

说明：

- `.obsidian/` 是 Obsidian 编辑器工作区文件
- `.codex/` 是 AI 工具相关技能/过程目录
- `findings.md`、`progress.md`、`task_plan.md`、`docs/plans/` 属于开发过程记录，不属于项目运行核心

### 5. 空目录残留

- `frontend/public/`
- `backend/app/routers/`
- `docker/mysql-init/`

说明：

- 我检查过，这几个目录当前是空的
- 删除不会影响项目主流程

---

## 二、建议保留的核心文件和目录

下面这些内容建议保留，也建议上传到 GitHub：

- `app/`
- `backend/`
- `frontend/src/`
- `frontend/scripts/`
- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/vite.config.js`
- `frontend/index.html`
- `frontend/Dockerfile`
- `scripts/`
- `docker-compose.yml`
- `backend/Dockerfile`
- `backend/requirements.txt`
- `README.md`
- `docs/`
- `ER图.pdf`
- `flight_ticketing_db.sql`
- `数据库设计要求.md`
- `数据库设计思路-必须遵守.md`
- `.env.example`
- `.gitignore`

---

## 三、不建议上传 GitHub，但建议本地保留的文件

- `.env`

说明：

- `.env` 里通常包含数据库密码、JWT 密钥等本地环境配置
- 这个文件不要上传 GitHub
- 但你本地继续运行 Docker 项目时通常还需要它

---

## 四、推荐 `.gitignore` 内容

你当前项目根目录已经有 `.gitignore`，建议至少保留下面这些规则：

```gitignore
.env
.pytest_cache/
**/__pycache__/
*.db
frontend/node_modules/
frontend/dist/
```

作用是：

- 防止把本地环境文件传上 GitHub
- 防止把缓存、依赖和数据库文件一起提交

---

## 五、清理删除建议执行顺序

建议你按下面顺序手动清理：

### 第 1 步：先确认 `.gitignore` 存在

确认项目根目录已经有 `.gitignore`

### 第 2 步：删除不需要保留的内容

优先删除下面这些最典型的无用内容：

```text
frontend/node_modules/
frontend/dist/
.pytest_cache/
所有 __pycache__/
flight_ticketing.db
alembic_test.db
.obsidian/
.codex/
findings.md
progress.md
task_plan.md
docs/plans/
frontend/public/
backend/app/routers/
docker/mysql-init/
```

### 第 3 步：保留 `.env`

不要把 `.env` 删掉，否则你后面本地跑 Docker 可能还要重新配置

### 第 4 步：重新验证项目还能启动

在项目根目录执行：

```powershell
docker compose down -v
docker compose up --build -d
```

然后访问：

- `http://localhost:5173`
- `http://localhost:8000/health`

如果都正常，说明清理没有影响主项目

---

## 六、GitHub 上传完整教程（命令行 Git + HTTPS + 浏览器登录）

下面这套流程适合完全新手。

### 第 1 步：安装 Git

1. 打开 Git 官网  
   `https://git-scm.com/`
2. 下载 Windows 版本并安装
3. 安装完成后，打开 PowerShell，执行：

```powershell
git --version
```

如果显示版本号，说明安装成功。

---

### 第 2 步：进入项目根目录

在 PowerShell 中进入你的项目目录：

```powershell
cd "C:\Users\19588\Desktop\ds_study\数据库引论\DB_PJ"
```

---

### 第 3 步：先完成项目清理

按上面的“可清理删除清单”把不需要上传的内容删掉。

重点确保这些内容不要上传：

- `.env`
- `frontend/node_modules/`
- `frontend/dist/`
- `*.db`
- `__pycache__/`
- `.pytest_cache/`
- `.obsidian/`
- `.codex/`

---

### 第 4 步：在 GitHub 网站创建空仓库

1. 登录 GitHub
2. 点击右上角 `+`
3. 选择 `New repository`
4. 填写仓库名  
   例如：`flight-ticketing-course-project`
5. 选择 `Public` 或 `Private`
6. **不要勾选**：
   - `Add a README file`
   - `Add .gitignore`
   - `Choose a license`
7. 点击 `Create repository`

创建完成后，GitHub 会给你一个仓库地址，例如：

```text
https://github.com/你的用户名/flight-ticketing-course-project.git
```

---

### 第 5 步：初始化本地 Git 仓库

你当前这个目录还不是 Git 仓库，所以要先初始化：

```powershell
git init
```

---

### 第 6 步：配置 Git 用户信息

第一次使用 Git 时执行：

```powershell
git config --global user.name "你的GitHub用户名"
git config --global user.email "你的GitHub邮箱"
```

检查是否设置成功：

```powershell
git config --global --list
```

---

### 第 7 步：查看当前 Git 状态

执行：

```powershell
git status
```

这一步主要是确认 Git 已经识别当前目录文件。

---

### 第 8 步：把文件加入暂存区

执行：

```powershell
git add .
```

然后再次执行：

```powershell
git status
```

重点检查这些内容**没有**被加入提交：

- `.env`
- `frontend/node_modules/`
- `frontend/dist/`
- `*.db`
- `__pycache__/`
- `.pytest_cache/`

如果你发现 `.env` 被暂存了，执行：

```powershell
git restore --staged .env
```

---

### 第 9 步：创建第一次提交

执行：

```powershell
git commit -m "Initial upload for course project"
```

---

### 第 10 步：把主分支改成 main

执行：

```powershell
git branch -M main
```

---

### 第 11 步：关联 GitHub 远程仓库

把下面命令中的仓库地址替换成你自己的：

```powershell
git remote add origin https://github.com/你的用户名/你的仓库名.git
```

然后检查：

```powershell
git remote -v
```

如果提示：

```text
remote origin already exists
```

就先执行：

```powershell
git remote remove origin
```

然后重新执行 `git remote add origin ...`

---

### 第 12 步：首次推送到 GitHub

执行：

```powershell
git push -u origin main
```

第一次推送时，Git 会弹出 Git Credential Manager 或浏览器登录流程。

你只需要按提示完成：

1. 打开浏览器
2. 登录 GitHub
3. 授权 Git
4. 返回 PowerShell 等待推送完成

---

### 第 13 步：确认上传成功

回到 GitHub 仓库页面刷新，确认：

- 能看到项目源码
- 能看到课程文档
- 能看到 `README.md`
- 看不到 `.env`
- 看不到 `node_modules`
- 看不到 `dist`
- 看不到 `.db`

这就说明上传成功。

---

## 七、以后每次更新代码怎么上传

以后每次修改完项目后，在根目录执行：

```powershell
git status
git add .
git commit -m "说明本次修改"
git push
```

例如：

```powershell
git commit -m "feat: improve order and waitlist route display"
```

---

## 八、常见问题

### 1. 我不小心把不该上传的文件加进去了怎么办？

如果只是 `git add .` 了，还没提交：

```powershell
git restore --staged 文件名
```

例如：

```powershell
git restore --staged .env
```

### 2. 我已经提交了，但还没 push，怎么办？

可以先修改 `.gitignore`，再重新整理一次提交内容。

### 3. GitHub 上中文会不会乱码？

你当前项目里的 Markdown 字节看起来是 UTF-8，GitHub 一般能正常显示中文。

后续编辑时注意：

- 用 UTF-8 编码保存
- 不要用会强制转 ANSI 的旧编辑器另存

### 4. 清理后 Docker 还能跑吗？

只要你没有删掉下面这些核心文件，项目仍然可以运行：

- `app/`
- `backend/`
- `frontend/src/`
- `docker-compose.yml`
- `backend/Dockerfile`
- `frontend/Dockerfile`
- `backend/requirements.txt`
- `frontend/package.json`
- `.env`

