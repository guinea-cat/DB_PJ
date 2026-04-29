# 航空票务系统 Demo

如果你不知道如何运行，可以把链接https://github.com/guinea-cat/DB_PJ发给gemini接受指导。

这是一个面向课程设计的航空票务系统最小全链路实现，技术栈为 `FastAPI + SQLAlchemy + Vue 3 + MySQL/SQLite`。项目当前版本已经完成课程版三项升级：

- 乘客敏感信息保护：身份证号和姓名不再明文暴露，系统改为内部 `passenger_id` 关联，数据库中保存哈希、密文和脱敏值。
- 轻量化支付流程：下单与支付分离，先创建 `PENDING_PAYMENT` 订单并锁库存，再通过模拟支付确认。
- 简洁定价与特价票：普通票采用基础价、航班折扣、用户折扣和余票阶梯联合定价；特价票采用管理员固定场次配置。

## 当前能力

- 支持单日搜索和日期范围搜索
- 支持同一航班内连续航段售票
- 支持事务扣减库存、防止超卖
- 支持待支付超时失效并自动释放库存
- 支持候补登记与 `RELEASED` 释放通知
- 支持管理员维护基础数据、排班模板、特价票活动和订单审计

## 快速运行

### 方式 1：本地运行

后端：

```powershell
python scripts/init_db.py
uvicorn app.main:app --reload
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

访问地址：

- 前端：`http://127.0.0.1:5173`
- 后端 Swagger：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/health`

### 方式 2：Docker 运行

首次建议先复制环境变量文件：

```powershell
Copy-Item .env.example .env -Force
```

启动：

```powershell
docker compose down -v
docker compose up -d
```

如需重新构建镜像：build等待三十秒左右都配置好了，然后打开 `http://localhost:5173` 即可 

```powershell
docker compose down -v
docker compose up --build -d
```

## 演示账号和密码

- 普通用户 1：`alice01 / user123`
- 普通用户 2：`bob01 / user123`
- 管理员：`admin / admin123`

## 课程版关键规则

- 普通票价格：`基础价 × 航班折扣 × 用户类型折扣 × 余票阶梯系数`
- 余票阶梯：余票率 `>= 50%` 为 `1.00`，`20% - 49%` 为 `1.05`，`< 20%` 为 `1.10`
- 特价票：管理员按“固定航班日期 + 舱位 + 区间 + 配额”手动配置
- 命中特价票时直接使用特价，不再叠加会员折扣和余票阶梯系数
- 未支付订单默认保留 15 分钟，超时后在下一次关键业务触发前被懒处理释放

