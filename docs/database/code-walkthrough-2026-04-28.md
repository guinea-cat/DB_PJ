# 航空票务数据库项目代码总讲解

## 1. 后端入口与基础设施

### `app/main.py`

- 创建 FastAPI 应用。
- 注册 CORS，允许前端本地地址访问。
- 定义 `/health` 健康检查：
  - 通过执行 `SELECT 1` 判断数据库是否可用。
- 注册六组路由：
  - `auth`
  - `flights`
  - `tickets`
  - `waitlists`
  - `me`
  - `admin`

作用：整个后端服务的总入口。

### `app/config.py`

- 从环境变量读取应用名称、数据库地址、JWT 密钥、过期时间、CORS 白名单。

作用：把运行环境配置集中管理，避免把配置写死在代码里。

### `app/database.py`

- 定义 SQLAlchemy 的 `Base`。
- 根据 `DATABASE_URL` 创建数据库引擎。
- 如果是 SQLite，则加 `check_same_thread=False`。
- 创建 `SessionLocal` 会话工厂。
- 提供 `get_db()` 依赖，用于路由中注入数据库会话。

作用：后端访问数据库的基础设施层。

---

## 2. 安全认证

### `app/security.py`

- `hash_password(password)`
  - 用 `bcrypt` 生成密码哈希。
- `verify_password(password, password_hash)`
  - 校验用户输入密码是否匹配数据库哈希。
- `create_access_token(account_id, login_identifier, role)`
  - 生成 JWT。
- `decode_access_token(token)`
  - 解码 JWT。

作用：实现登录认证，不把明文密码直接存库。

### `app/dependencies.py`

- `get_current_account(...)`
  - 从请求头提取 Bearer Token。
  - 解码 JWT。
  - 查询当前账号。
  - 校验账号是否存在且为 `ACTIVE`。
- `require_admin(...)`
  - 在 `get_current_account` 基础上额外限制必须是管理员。

作用：把“登录态检查”和“管理员权限检查”封装成可复用依赖。

---

## 3. 数据模型 `app/models.py`

### `City`

- 城市字典表。
- 字段：
  - `city_code`
  - `city_name`

### `Airport`

- 机场表。
- 通过 `city_code` 外键连接 `City`。

### `Airplane`

- 飞机表。
- 保存机型与头等舱/经济舱容量。
- `CHECK` 保证容量不能为负数。

### `UserType`

- 用户类型表。
- 当前主要有 `NORMAL` 和 `VIP`。
- 保存折扣系数。
- 本次补充：
  - 折扣必须大于 0 且不超过 1。

### `Passenger`

- 乘客表。
- 用身份证号作为主键。
- 关联用户类型。
- 保存里程积分。
- `CHECK` 保证积分不能为负数。

### `Account`

- 登录账号表。
- 把“账号认证”与“乘客实体”解耦。
- 字段：
  - 登录名
  - 密码哈希
  - 角色
  - 状态
  - 可选的乘客绑定
- 本次补充：
  - 角色只能是 `ADMIN` 或 `USER`
  - 状态只能是 `ACTIVE` 或 `DISABLED`

### `Route`

- 航线表。
- 表示一条业务航线，如“上海-长沙-昆明”。

### `RouteSegment`

- 航线分段表。
- 一条航线被拆成若干连续航段。
- 用来解决经停、多机场、多段库存扣减问题。
- 本次补充：
  - `segment_order >= 1`
  - 起点机场和终点机场不能相同

### `RoutePricing`

- 航线定价表。
- 主键为 `(route_id, cabin_class)`。
- 保存不同舱位的基础票价。
- 本次补充：
  - 舱位只能是 `F` 或 `Y`
  - 基础价格必须大于 0

### `FlightTemplate`

- 固定航班模板。
- 保存一个航班号的默认航线、默认飞机、默认折扣和状态。
- 用于“按每周班期批量生成未来排班”。
- 本次补充：
  - 折扣必须在 `(0,1]`
  - 状态只能是 `ACTIVE/INACTIVE`

### `FlightTemplateWeekday`

- 模板对应的每周飞行日。
- 用复合主键 `(template_id, weekday)` 防止重复。
- 本次补充：
  - 星期值只能在 `1..7`

### `FlightSchedule`

- 某一天实际执行的航班。
- 主键 `(flight_no, flight_date)`。
- 保存当日飞机、折扣、状态、来源模板。
- 本次补充：
  - 折扣必须在 `(0,1]`
  - 状态只能是 `ACTIVE/CANCELLED`

### `DemoDataVersion`

- 演示数据版本表。
- 避免重复灌入同一套 seed 数据。

### `ScheduleInventory`

- 核心库存表。
- 粒度是：
  - 某个航班
  - 某个日期
  - 某个航段
- 分别记录 F / Y 剩余座位。
- 是并发扣库存的关键表。

### `TicketSale`

- 订单/售票记录表。
- 保存航班、区间、乘客、舱位、状态、价格、时间戳。
- 通过 `is_active_ticket` 和唯一约束限制：
  - 同一乘客在同一航班同一天最多只有一张有效票。
- 本次补充：
  - 舱位值域
  - 状态值域
  - `is_active_ticket` 值域
  - 票价非负

### `WaitlistRecord`

- 候补记录表。
- 记录候补请求、状态、请求时间、释放时间。
- 当前业务含义是：
  - `WAITING` 等待中
  - `RELEASED` 被释放，可优先重新购买
  - `CANCELLED` 因航班取消失效
- 本次补充：
  - 舱位值域
  - 状态值域

### `OperationAuditLog`

- 审计日志表。
- 记录谁在什么时候对什么对象做了什么操作。

---

## 4. 业务服务层 `app/services.py`

这是项目最关键的业务文件。

### 辅助函数

- `utcnow_naive()`
  - 统一生成无时区时间戳。

- `decimal_money(value)`
  - 统一把金额保留两位小数。

- `create_audit_log(...)`
  - 写入审计日志。

- `mask_id_card(id_card)`
  - 本次新增。
  - 用于管理员订单返回时做身份证脱敏。

### 用户与类型辅助

- `get_passenger_for_account(...)`
  - 从登录账号找到其绑定的乘客。

- `get_user_type_by_name(...)`
  - 按名称读取用户类型。

- `get_vip_type(...)`
  - 取 VIP 类型。

- `get_normal_type(...)`
  - 取 NORMAL 类型。

### 航段连续性与价格

- `get_segment_range(...)`
  - 核验起止航段是否存在、是否属于同一路线、顺序是否正确。
  - 进一步校验该区间是否连续。

- `compute_ticket_price(...)`
  - 按公式计算票价：
  - `基础价 × 航班折扣 × 用户类型折扣`

### 查票

- `search_flights(...)`
  - 按单日、起降机场、舱位搜索。
  - 遍历每个排班的可能区间。
  - 读取对应航段库存。
  - 以区间上的最小余票作为可售座位数。

- `_collect_schedule_matches(...)`
  - 给日期范围查询复用的内部函数。

- `search_flights_in_range(...)`
  - 范围日期查票。

### 并发库存控制

- `_lock_inventories(...)`
  - 对目标航段库存行执行锁定查询。
  - 这是并发售票的关键。

### 积分与会员

- `_sync_passenger_type(...)`
  - 本次整改后的核心逻辑。
  - 根据积分决定乘客应是 `NORMAL` 还是 `VIP`。
  - 不仅支持升级，也支持退款后的降级。

- `_reverse_passenger_points(...)`
  - 本次新增。
  - 退票时把积分扣回去，且最低不小于 0。

### 购票

- `purchase_ticket(...)`
  - 校验航班是否存在且可售。
  - 校验同一乘客同航班是否已有有效票。
  - 计算航段区间。
  - 锁定该区间所有库存行。
  - 判断最小余票是否大于 0。
  - 扣减库存。
  - 生成订单。
  - 增加积分。
  - 同步会员等级。
  - 写入审计日志。
  - 提交事务。

### 候补释放

- `_mark_first_waitlist_released(...)`
  - 退票后按 FIFO 取第一条符合条件的候补记录，并改为 `RELEASED`。
  - 注意：当前版本不是自动出票，只是释放通知。

### 起飞检查

- `_has_departed(...)`
  - 判断航班区间是否已经起飞。

### 退票

- `refund_ticket(...)`
  - 校验订单状态必须是 `PAID`。
  - 非管理员场景下，已起飞不能退。
  - 锁定对应库存区间。
  - 返还库存。
  - 本次整改后：
    - 回退积分
    - 重新同步用户等级
  - 更新订单状态为 `REFUNDED`
  - 触发候补释放
  - 写审计日志

### 候补创建

- `create_waitlist(...)`
  - 本次整改前：
    - 若航段 ID 不存在，会抛出服务器错误。
  - 本次整改后：
    - 明确先检查航段是否存在，不存在返回 404。
  - 如果该区间仍有票，则不允许候补。
  - 如果已有未完成候补，则不允许重复候补。
  - 创建候补记录并写审计日志。

### 生成排班

- `generate_schedules(...)`
  - 根据模板和日期范围批量生成实际航班。
  - 如果某日符合模板星期且还没有该排班，则：
    - 新建 `FlightSchedule`
    - 根据飞机容量初始化对应 `ScheduleInventory`
  - 记录哪些日期匹配、哪些已存在、哪些新生成。

### 取消航班

- `cancel_schedule(...)`
  - 把排班状态改为 `CANCELLED`
  - 找出该航班当天所有已支付订单
  - 逐单退款
  - 把相关候补改为 `CANCELLED`
  - 写审计日志

---

## 5. 路由层

### `app/routers/auth.py`

- `/auth/login`
  - 账号密码登录，返回 JWT。

- `/auth/me`
  - 返回当前账号、角色、乘客、会员等级、积分。

### `app/routers/flights.py`

- `/flights/search`
  - 单日航班查询。

- `/flights/search/range`
  - 日期范围查询。

### `app/routers/tickets.py`

- `/tickets/purchase`
  - 调用购票服务。

- `/tickets/{ticket_no}/refund`
  - 普通用户只能退自己的票。

### `app/routers/waitlists.py`

- `/waitlists`
  - 创建候补请求。

### `app/routers/me.py`

- `/me/orders`
  - 查询当前用户自己的订单。

- `/me/waitlists`
  - 查询当前用户自己的候补。

### `app/routers/admin.py`

管理员后台接口，主要分三类：

1. 基础字典管理
   - 城市
   - 机场
   - 飞机

2. 航线与模板管理
   - 航线增删改查
   - 航班模板增删改查

3. 调度与审计
   - 批量生成排班
   - 取消航班
   - 查看全网订单
   - 查看审计日志

本次整改后：

- 管理员订单接口返回 `id_card_masked`
- 不再直接暴露乘客身份证号

---

## 6. 数据初始化与脚本

### `app/db_bootstrap.py`

- 封装 Alembic 迁移执行。
- 支持：
  - reset
  - seed
  - reseed

### `app/seed.py`

- 填充演示数据。
- 包括：
  - 城市
  - 机场
  - 飞机
  - 用户类型
  - 用户与账号
  - 航线与航段
  - 定价
  - 航班模板
  - 模板星期
  - 具体排班
  - 每日航段库存

作用：保证演示环境开箱即用。

### `scripts/init_db.py`

- 重建数据库并灌入演示数据。

### `scripts/bootstrap_db.py`

- 运行迁移并可选 seed。

### `scripts/render_schema_sql.py`

- 根据 SQLAlchemy 模型导出 MySQL 建表 SQL。

### `scripts/start_backend.py`

- 等待数据库就绪
- 执行 bootstrap
- 启动 uvicorn

### `scripts/wait_for_db.py`

- 循环检测数据库连接是否可用。

---

## 7. 测试代码作用

### `backend/tests/test_ticketing_flow.py`

- 验证普通用户登录、查票、购票、退票、候补、日期范围查询等主链路。
- 本次新增测试：
  - 退票后积分与 VIP 回滚
  - 候补非法航段返回 404

### `backend/tests/test_admin_flow.py`

- 验证管理员排班生成、取消航班、字典维护、模板维护等功能。
- 本次新增验证：
  - 管理员订单接口必须使用脱敏身份证字段

### `backend/tests/mysql/test_mysql_ticketing_integration.py`

- 验证 MySQL 下真实并发行为：
  - 双用户并发抢一张票
  - 同用户并发重复购票
  - 退票后候补释放

### 其他测试

- `test_health.py`
  - 健康检查。
- `test_cors.py`
  - 跨域预检。
- `test_bootstrap.py`
  - 数据库引导流程。
- `test_seed.py`
  - 演示数据完整性。
- `test_startup_scripts.py`
  - 启动脚本和 Docker 配置检查。

---

## 8. 前端代码作用

### `frontend/src/api.js`

- 封装前端对后端的全部 HTTP 请求。
- 统一处理：
  - Bearer Token
  - JSON 请求
  - 错误格式化

### `frontend/src/App.vue`

- 整个前端页面的主组件。
- 负责：
  - 登录态管理
  - 单日/范围查票
  - 购票、退票、候补
  - 我的订单 / 我的候补
  - 管理员 CRUD
  - 生成排班 / 取消航班
  - 审计与全网订单展示

本质上它是一个“课程演示总控台”。

### `frontend/src/main.js`

- 挂载 Vue 应用。

### `frontend/src/styles.css`

- 整体页面视觉样式。
- 不涉及业务逻辑。

---

## 9. 这套代码的设计目的总结

这套项目代码的目标不是只证明“能查出一张票”，而是要证明：

1. 数据库结构是规范的。
2. 航线经停与跨航段库存问题被正确建模。
3. 并发购票不是靠前端侥幸，而是靠数据库事务与锁。
4. 普通用户和管理员有明确的数据权限边界。
5. 整个项目可以被演示、测试和验证。

也就是说，这个项目已经不是“只画 E-R 图”的数据库课程作业，而是一个围绕数据库设计展开的完整工程实现。
