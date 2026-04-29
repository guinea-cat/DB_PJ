# 课程规范 / E-R 图 / 实际实现对照矩阵

## 1. 核心实体对照

| 课程基线实体 | E-R 图 | 实际实现 | 结论 |
|---|---|---|---|
| City | 有 | `City` | 一致 |
| Airport | 有 | `Airport` | 一致 |
| Airplane | 有 | `Airplane` | 一致 |
| User_Type | 有 | `UserType` | 一致 |
| Passenger | 有 | `Passenger` | 一致 |
| Route | 有 | `Route` | 一致 |
| Route_Segment | 有 | `RouteSegment` | 一致 |
| Route_Pricing | 有 | `RoutePricing` | 一致 |
| Flight_Schedule | 有 | `FlightSchedule` | 一致 |
| Schedule_Inventory | 有 | `ScheduleInventory` | 一致 |
| Ticket_Sale | 有 | `TicketSale` | 一致 |

## 2. 扩展实体对照

| 实际扩展表 | 是否在课程基线中 | 作用 | 评价 |
|---|---|---|---|
| `Account` | 否 | 登录认证与角色隔离 | 合理扩展 |
| `FlightTemplate` | 否 | 固定航班模板 | 合理扩展 |
| `FlightTemplateWeekday` | 否 | 每周飞行日 | 合理扩展 |
| `WaitlistRecord` | 否 | 候补机制 | 合理扩展 |
| `OperationAuditLog` | 否 | 审计与追踪 | 合理扩展 |
| `DemoDataVersion` | 否 | seed 版本控制 | 工程辅助表 |

## 3. 字段与关系对照

### 3.1 City / Airport

- 课程要求：
  - 城市与机场一对多。
- 实现：
  - `Airport.city_code -> City.city_code`
- 结论：
  - 完全一致。

### 3.2 航班 / 经停 / 航线

- 课程要求：
  - 航班与机场多对多，考虑经停。
- 实现：
  - 不是直接把“经停机场”塞在一张表里，而是拆成：
    - `Route`
    - `RouteSegment`
- 结论：
  - 符合关系模型规范化思路，比单字段存经停更好。

### 3.3 舱位定价

- 课程要求：
  - 需要记录航班号、舱位等级、价格。
- 实现：
  - 采用 `RoutePricing(route_id, cabin_class, base_price)`。
- 结论：
  - 与“按航班号定价”略有表达差异，但设计更规范。
  - 逻辑含义是“定价归属于航线”，实际销售时再乘以航班折扣。

### 3.4 售票记录

- 课程要求：
  - 至少包含身份证号、姓名、出发城市、到达城市、日期、舱位、价格、航班号。
- 实现：
  - `TicketSale` 中只存：
    - `id_card`
    - `flight_no`
    - `flight_date`
    - `start_segment_id`
    - `end_segment_id`
    - `cabin_class`
    - `actual_price`
    - `status`
- 结论：
  - 从“字段列表展示”看少了姓名/出发城市/到达城市。
  - 但从数据库规范化角度，这是正确做法。
  - 这些字段都可通过外键关联推导，不应冗余存储。

## 4. 业务逻辑对照

### 4.1 每周飞行日

- 课程要求：支持设置每周飞行日。
- 实现：
  - `FlightTemplateWeekday`
  - `generate_schedules()`
- 结论：
  - 已实现，且比单字段存储更规范。

### 4.2 并发售票

- 课程要求：必须考虑并发锁。
- 实现：
  - 服务层锁定 `ScheduleInventory`
  - 真实 MySQL 接口并发实测：一张余票只成功一单
- 结论：
  - 已实现。

### 4.3 特价票 / 差异化销售

- 课程要求：实现特价票和销售策略。
- 实现：
  - `RoutePricing.base_price`
  - `FlightSchedule.flight_discount`
  - `UserType.discount_rate`
- 结论：
  - 已实现基础版差异化销售。
  - 但没有更复杂的促销规则表。

### 4.4 候补

- 设计思路文档强调：
  - 候补可作为高分扩展。
- 实现：
  - `WaitlistRecord`
  - 退票后 FIFO 标记 `RELEASED`
- 结论：
  - 已实现通知型候补。
  - 未实现自动出票型候补。

### 4.5 积分与 VIP

- 设计思路文档提到：
  - 积分累计、VIP 升级是高分设计点。
- 实现：
  - 购票后加积分
  - 达阈值升级 VIP
  - 本次整改后：退票后积分回滚，不再错误保留 VIP
- 结论：
  - 已实现，且一致性比整改前更好。

## 5. 安全与隐私对照

| 要求 | 实现情况 | 结论 |
|---|---|---|
| 乘客信息保护 | 密码哈希、角色隔离、管理员订单脱敏 | 基本合格 |
| 支付信息保护 | 未保存真实支付信息 | 通过简化规避风险 |
| 更高标准隐私防护 | 身份证仍明文存库 | 仍有提升空间 |

## 6. 不一致与不合理点

### 已整改

1. 退票后积分与 VIP 身份未回滚。
2. 候补非法航段参数可能触发 500。
3. 管理员查看订单直接暴露身份证号。
4. 数据库级完整性约束不足。
5. 导出 SQL 需重新同步当前模型。

### 仍需解释但不一定算错误

1. 实现比 E-R 图多出多张扩展表。
2. 使用 Python ORM 作为主要开发方式，而不是纯手写 SQL 页面逻辑。
3. 候补是“释放通知”，不是“自动出票”。

## 7. 总体判断

从数据库核心设计看，项目没有偏离课程主线，反而在以下方面做得更完整：

- 路线规范化
- 航段库存建模
- 排班模板化
- 权限分层
- 审计追踪

真正需要注意的不是“设计方向错了”，而是：

- 需要在答辩时把“扩展实现”和“课程核心要求”的关系讲清楚；
- 需要补足 SQL 说明材料，证明你不仅会写 Python，也真正理解数据库与 SQL。
