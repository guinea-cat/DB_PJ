# 后端接口说明

## 认证
- `POST /auth/login`
  - 请求：`{ "login_identifier": "...", "password": "..." }`
  - 返回：`{ "access_token": "...", "token_type": "bearer" }`
- `GET /auth/me`
  - 返回当前账号、角色、乘机人信息、用户等级与积分

## 普通用户接口
- `GET /flights/search`
  - 参数：`origin_airport_code`、`destination_airport_code`、`flight_date`、`cabin_class`
  - 返回：航班号、日期、起止机场、起止航段、舱位、可售座位、最终价格、起降时间
- `POST /tickets/purchase`
  - 请求：`flight_no`、`flight_date`、`start_segment_id`、`end_segment_id`、`cabin_class`
- `POST /tickets/{ticketNo}/refund`
- `POST /waitlists`
- `GET /me/orders`
- `GET /me/waitlists`

## 管理员接口
- `GET/POST/PUT/DELETE /admin/cities`
- `GET/POST/PUT/DELETE /admin/airports`
- `GET/POST/PUT/DELETE /admin/airplanes`
- `GET/POST/DELETE /admin/routes`
- `GET/POST/DELETE /admin/flight-templates`
- `POST /admin/schedules/generate`
- `POST /admin/schedules/{flightNo}/{date}/cancel`
- `GET /admin/orders`
- `GET /admin/audits`

## 文档方式
- 启动后访问 `/docs`
- OpenAPI 由 FastAPI 自动生成
