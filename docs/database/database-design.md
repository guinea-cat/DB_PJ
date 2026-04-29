# 航空票务数据库设计说明

## 设计原则

- 遵循课程数据库设计规范，以 `3NF` 为基础，避免在交易表中冗余存储机场名、乘客明文身份信息等字段。
- 使用 `RouteSegment` 表示多航段航线，使用 `ScheduleInventory` 解决同一航班跨航段共享库存问题。
- 业务复杂度控制在课程项目可落地范围内，不实现跨航班联程、不实现选座、不接入真实第三方支付。
- 在课程级别上体现并发控制、支付安全和隐私保护意识，同时保持实现轻量。

## 核心实体

- 基础字典：`City`、`Airport`、`Airplane`、`UserType`
- 用户与认证：`Passenger`、`Account`
- 航线与定价：`Route`、`RouteSegment`、`RoutePricing`、`SpecialFarePlan`
- 班期与排班：`FlightTemplate`、`FlightTemplateWeekday`、`FlightSchedule`
- 库存与交易：`ScheduleInventory`、`TicketSale`、`PaymentRecord`、`WaitlistRecord`
- 审计：`OperationAuditLog`

## 数据字典摘要

- `Passenger`：内部 `passenger_id`、身份证哈希、身份证密文、身份证脱敏值、姓名密文、姓名脱敏值、用户类型、里程积分。
- `Account`：登录标识、密码哈希、角色、状态、绑定乘客和创建时间。
- `Route` / `RouteSegment`：航线主数据与连续航段定义。
- `RoutePricing`：按航线和舱位维护基础票价。
- `FlightTemplate` / `FlightTemplateWeekday`：固定航班模板与每周班期规则。
- `FlightSchedule`：某天的具体航班，记录折扣、飞机、模板来源和状态。
- `ScheduleInventory`：按航班日期、航段和舱位维护剩余座位。
- `SpecialFarePlan`：管理员配置的固定航班日期、舱位、区间特价活动及其配额。
- `TicketSale`：订单主表，保存订单状态、价格快照、价格来源、特价关联和关键时间戳。
- `PaymentRecord`：支付主表，保存模拟支付方式、支付状态、付款账号哈希、付款账号脱敏值和支付时间。
- `WaitlistRecord`：候补申请、候补状态、申请时间和释放时间。
- `OperationAuditLog`：关键业务操作的执行人、对象、动作和摘要明细。

## 关键业务规则

- 搜索仅支持“同一航班内连续航段”。
- 普通票价格：
  `基础价 × 航班折扣 × 用户类型折扣 × 余票阶梯系数`
- 余票阶梯固定三档：
  - 余票率 `>= 50%`：`1.00`
  - 余票率 `20% - 49%`：`1.05`
  - 余票率 `< 20%`：`1.10`
- 余票率按目标区间涉及航段中的最小剩余座位数除以舱位总容量计算。
- 特价票由管理员按“固定航班日期 + 舱位 + 区间 + 配额”手动配置。
- 命中特价票时，最终价格直接取 `special_price`，不再叠加会员折扣和余票阶梯系数。
- 下单先创建 `PENDING_PAYMENT` 订单并锁定库存；支付成功后订单改为 `PAID`。
- 未支付订单默认保留 15 分钟，超时后在搜索、下单、支付、退款、候补等关键业务前被懒处理释放。
- 退票仅允许对已支付订单执行，退款后返还库存，订单改为 `REFUNDED`。
- 候补释放采用 FIFO，当前版本只标记 `RELEASED`，不自动占座。

## 关键约束与索引

- `Passenger(id_card_hash)` 唯一，保证同一身份证只能对应一名乘客。
- `RouteSegment(route_id, segment_order)` 唯一，保证同一航线内航段顺序不重复。
- `FlightTemplateWeekday(template_id, weekday)` 复合唯一。
- `ScheduleInventory(flight_date, flight_no)` 建立查询索引，加速库存定位。
- `TicketSale(passenger_id, flight_date, status)` 建立检索索引，支撑用户查单和管理员筛单。
- `PaymentRecord(ticket_no)` 唯一，保证一张票只对应一条支付主记录。
- `SpecialFarePlan(flight_no, flight_date, cabin_class, start_segment_id, end_segment_id, status)` 建立检索索引。
- 基础数据被引用时禁止删除，由外键约束和后端 `409` 校验共同保护。

## 核心事务说明

- 购票事务：
  对目标区间全部 `ScheduleInventory` 记录执行锁定，统一判断最小库存；若命中特价票则先占用特价配额，再扣减库存并创建 `PENDING_PAYMENT` 订单。
- 支付事务：
  锁定订单与支付记录，校验订单未过期、未重复支付后，将订单改为 `PAID`，写入模拟支付信息。
- 超时释放：
  在关键业务入口先扫描已超时的待支付订单，过期后返还库存和未支付特价配额，并将订单改为 `EXPIRED`。
- 退票事务：
  锁定对应库存区间后返库，将订单改为 `REFUNDED`，同步更新 `PaymentRecord` 为 `REFUNDED`，再按 FIFO 将第一条候补标记为 `RELEASED`。
- 取消航班：
  先将 `FlightSchedule.schedule_status` 置为 `CANCELLED`，再批量退款所有已支付订单，并取消相关候补。

## 隐私与安全设计

- 不再使用身份证号作为主键或外键，统一改为内部 `passenger_id`。
- 身份证号采用 `HMAC-SHA256` 做唯一检索哈希，采用 `Fernet` 做密文存储，同时保存脱敏展示值。
- 姓名采用密文和脱敏值分层保存，不在普通接口中返回明文。
- 账号登录标识与身份证脱钩，避免“账号即身份证”的直接泄露。
- 支付信息只保留付款账号脱敏值和哈希值，不保存完整卡号、CVV、支付密码等高敏感数据。
- 审计日志和管理员订单页均禁止输出明文身份证号、明文姓名和完整付款账号。

## 当前边界

- 仅支持同一航班内连续航段，不支持跨航班联程。
- 仅管理舱位库存，不管理座位号。
- 支付采用轻量化模拟支付，不接入真实支付网关。
- 候补释放仅表示优先通知资格，不保留自动锁座窗口。
