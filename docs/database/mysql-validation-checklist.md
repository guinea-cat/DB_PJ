# MySQL 真库验收清单

## 目标
- 在真实 MySQL 9.6 + InnoDB 环境中验证迁移、初始化、主链路事务、并发锁与容器部署行为。

## 环境准备
1. 复制 `.env.example` 为 `.env`
2. 确认本机可访问 Docker
3. 如需单独跑 MySQL 测试，准备 `TEST_MYSQL_DATABASE_URL`

## 执行步骤
1. 运行 `docker compose --env-file .env.example up --build`
2. 观察 `mysql` 健康检查通过
3. 观察 `backend` 日志中依次出现等待数据库、执行迁移、灌入演示数据、启动 uvicorn
4. 访问 `http://localhost:8000/health`
5. 访问 `http://localhost:8000/docs`
6. 访问 `http://localhost:5173`
7. 使用普通用户账号执行登录、查票、购票、退票、候补
8. 使用管理员账号执行模板排班、取消航班、查看订单、查看审计
9. 设置 `TEST_MYSQL_DATABASE_URL` 后运行 `pytest backend/tests/mysql -q`

## 验收标准
- 健康检查返回 `{"status":"ok","database":"ok"}`
- Alembic 迁移成功且演示数据可直接使用
- 普通用户主链路和管理员主链路都可完成
- 并发购票结果稳定为一成一败，库存不为负
- 退票返库和候补释放符合设计说明

## 验收记录
- 日期：
- MySQL 版本：
- Docker 版本：
- `docker compose up --build` 结果：
- `pytest backend/tests/mysql -q` 结果：
- 发现的问题与修复：
