# 本地部署说明

## 方式一：直接运行 Python + Vite
1. 创建并激活虚拟环境
2. `pip install -r backend/requirements.txt`
3. 配置 `.env`，至少提供 `DATABASE_URL` 与 `JWT_SECRET`
4. 运行 `python scripts/init_db.py`
5. 启动后端：`uvicorn app.main:app --reload`
6. 进入 `frontend/`
7. `npm install`
8. `npm run dev`

## 方式二：Docker Compose
1. 复制 `.env.example` 为 `.env`
2. 执行 `docker compose up --build`
3. 容器启动顺序为：MySQL 健康检查通过 -> 后端等待数据库并执行迁移/种子 -> 前端启动
4. 前端默认 `http://localhost:5173`
5. 后端默认 `http://localhost:8000`
6. Swagger 默认 `http://localhost:8000/docs`
7. 健康检查默认 `http://localhost:8000/health`

## 数据初始化
- `scripts/init_db.py`：重建数据库、执行 Alembic 迁移并写入演示数据
- `scripts/bootstrap_db.py`：执行 Alembic 迁移并按需灌入演示数据，可用 `--reset` 重建数据库
- `scripts/wait_for_db.py`：等待真实数据库连通后再继续后续步骤
- `scripts/render_schema_sql.py`：根据 SQLAlchemy metadata 重新生成 `flight_ticketing_db.sql`

## MySQL 集成测试
1. 准备一个可写的 MySQL 测试库
2. 设置环境变量 `TEST_MYSQL_DATABASE_URL`
3. 执行 `pytest backend/tests/mysql -q`
4. 重点关注并发购票、退票返库和候补释放是否符合 InnoDB 事务预期

## 备份恢复
- 备份：`powershell -File scripts/backup_mysql.ps1`
- 恢复：`powershell -File scripts/restore_mysql.ps1`
