-- Auto-generated from SQLAlchemy metadata.
CREATE DATABASE IF NOT EXISTS FlightTicketingDB DEFAULT CHARSET utf8mb4;
USE FlightTicketingDB;


CREATE TABLE airplane (
	airplane_id VARCHAR(20) NOT NULL, 
	aircraft_type VARCHAR(50) NOT NULL, 
	f_class_capacity INTEGER NOT NULL, 
	y_class_capacity INTEGER NOT NULL, 
	PRIMARY KEY (airplane_id), 
	CONSTRAINT ck_airplane_f_capacity_nonneg CHECK (f_class_capacity >= 0), 
	CONSTRAINT ck_airplane_y_capacity_nonneg CHECK (y_class_capacity >= 0)
);


CREATE TABLE city (
	city_code VARCHAR(10) NOT NULL, 
	city_name VARCHAR(50) NOT NULL, 
	PRIMARY KEY (city_code), 
	UNIQUE (city_name)
);


CREATE TABLE demo_data_version (
	version_key VARCHAR(50) NOT NULL, 
	version INTEGER NOT NULL, 
	updated_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (version_key)
);


CREATE TABLE route (
	route_id VARCHAR(20) NOT NULL, 
	route_name VARCHAR(100) NOT NULL, 
	PRIMARY KEY (route_id)
);


CREATE TABLE user_type (
	type_id INTEGER NOT NULL AUTO_INCREMENT, 
	type_name VARCHAR(20) NOT NULL, 
	discount_rate NUMERIC(4, 2) NOT NULL, 
	PRIMARY KEY (type_id), 
	CONSTRAINT ck_user_type_discount_positive CHECK (discount_rate > 0), 
	CONSTRAINT ck_user_type_discount_max CHECK (discount_rate <= 1), 
	UNIQUE (type_name)
);


CREATE TABLE airport (
	airport_code VARCHAR(10) NOT NULL, 
	airport_name VARCHAR(50) NOT NULL, 
	city_code VARCHAR(10) NOT NULL, 
	PRIMARY KEY (airport_code), 
	FOREIGN KEY(city_code) REFERENCES city (city_code) ON DELETE RESTRICT
);


CREATE TABLE flight_template (
	template_id INTEGER NOT NULL AUTO_INCREMENT, 
	flight_no VARCHAR(20) NOT NULL, 
	route_id VARCHAR(20) NOT NULL, 
	default_airplane_id VARCHAR(20) NOT NULL, 
	default_flight_discount NUMERIC(4, 2) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	PRIMARY KEY (template_id), 
	CONSTRAINT ck_flight_template_discount_positive CHECK (default_flight_discount > 0), 
	CONSTRAINT ck_flight_template_discount_max CHECK (default_flight_discount <= 1), 
	CONSTRAINT ck_flight_template_status CHECK (status IN ('ACTIVE', 'INACTIVE')), 
	UNIQUE (flight_no), 
	FOREIGN KEY(route_id) REFERENCES route (route_id) ON DELETE RESTRICT, 
	FOREIGN KEY(default_airplane_id) REFERENCES airplane (airplane_id) ON DELETE RESTRICT
);


CREATE TABLE passenger (
	id_card VARCHAR(20) NOT NULL, 
	name VARCHAR(50) NOT NULL, 
	type_id INTEGER NOT NULL, 
	mileage_points NUMERIC(12, 2) NOT NULL DEFAULT '0.00', 
	PRIMARY KEY (id_card), 
	CONSTRAINT ck_passenger_mileage_nonneg CHECK (mileage_points >= 0), 
	FOREIGN KEY(type_id) REFERENCES user_type (type_id) ON DELETE RESTRICT
);


CREATE TABLE route_pricing (
	route_id VARCHAR(20) NOT NULL, 
	cabin_class VARCHAR(20) NOT NULL, 
	base_price NUMERIC(10, 2) NOT NULL, 
	PRIMARY KEY (route_id, cabin_class), 
	CONSTRAINT ck_route_pricing_cabin_class CHECK (cabin_class IN ('F', 'Y')), 
	CONSTRAINT ck_route_pricing_base_price_positive CHECK (base_price > 0), 
	FOREIGN KEY(route_id) REFERENCES route (route_id) ON DELETE CASCADE
);


CREATE TABLE account (
	account_id INTEGER NOT NULL AUTO_INCREMENT, 
	login_identifier VARCHAR(50) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	`role` VARCHAR(20) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	passenger_id_card VARCHAR(20), 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (account_id), 
	CONSTRAINT uq_account_passenger UNIQUE (passenger_id_card), 
	CONSTRAINT ck_account_role CHECK (role IN ('ADMIN', 'USER')), 
	CONSTRAINT ck_account_status CHECK (status IN ('ACTIVE', 'DISABLED')), 
	UNIQUE (login_identifier), 
	FOREIGN KEY(passenger_id_card) REFERENCES passenger (id_card) ON DELETE SET NULL
);


CREATE TABLE flight_schedule (
	flight_no VARCHAR(20) NOT NULL, 
	flight_date DATE NOT NULL, 
	route_id VARCHAR(20) NOT NULL, 
	airplane_id VARCHAR(20) NOT NULL, 
	flight_discount NUMERIC(4, 2) NOT NULL, 
	schedule_status VARCHAR(20) NOT NULL, 
	template_id INTEGER, 
	PRIMARY KEY (flight_no, flight_date), 
	CONSTRAINT ck_flight_schedule_discount_positive CHECK (flight_discount > 0), 
	CONSTRAINT ck_flight_schedule_discount_max CHECK (flight_discount <= 1), 
	CONSTRAINT ck_flight_schedule_status CHECK (schedule_status IN ('ACTIVE', 'CANCELLED')), 
	FOREIGN KEY(route_id) REFERENCES route (route_id) ON DELETE RESTRICT, 
	FOREIGN KEY(airplane_id) REFERENCES airplane (airplane_id) ON DELETE RESTRICT, 
	FOREIGN KEY(template_id) REFERENCES flight_template (template_id) ON DELETE SET NULL
);


CREATE TABLE flight_template_weekday (
	template_id INTEGER NOT NULL, 
	weekday INTEGER NOT NULL, 
	PRIMARY KEY (template_id, weekday), 
	CONSTRAINT ck_template_weekday_min CHECK (weekday >= 1), 
	CONSTRAINT ck_template_weekday_max CHECK (weekday <= 7), 
	FOREIGN KEY(template_id) REFERENCES flight_template (template_id) ON DELETE CASCADE
);


CREATE TABLE route_segment (
	segment_id INTEGER NOT NULL AUTO_INCREMENT, 
	route_id VARCHAR(20) NOT NULL, 
	segment_order INTEGER NOT NULL, 
	dep_airport_code VARCHAR(10) NOT NULL, 
	arr_airport_code VARCHAR(10) NOT NULL, 
	planned_dep_time TIME NOT NULL, 
	planned_arr_time TIME NOT NULL, 
	PRIMARY KEY (segment_id), 
	CONSTRAINT uq_route_segment_order UNIQUE (route_id, segment_order), 
	CONSTRAINT ck_route_segment_order_positive CHECK (segment_order >= 1), 
	CONSTRAINT ck_route_segment_distinct_airports CHECK (dep_airport_code <> arr_airport_code), 
	FOREIGN KEY(route_id) REFERENCES route (route_id) ON DELETE CASCADE, 
	FOREIGN KEY(dep_airport_code) REFERENCES airport (airport_code) ON DELETE RESTRICT, 
	FOREIGN KEY(arr_airport_code) REFERENCES airport (airport_code) ON DELETE RESTRICT
);


CREATE TABLE operation_audit_log (
	audit_id INTEGER NOT NULL AUTO_INCREMENT, 
	actor_account_id INTEGER, 
	action VARCHAR(100) NOT NULL, 
	entity_type VARCHAR(100) NOT NULL, 
	entity_id VARCHAR(100) NOT NULL, 
	detail TEXT NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	PRIMARY KEY (audit_id), 
	FOREIGN KEY(actor_account_id) REFERENCES account (account_id) ON DELETE SET NULL
);


CREATE TABLE schedule_inventory (
	flight_no VARCHAR(20) NOT NULL, 
	flight_date DATE NOT NULL, 
	segment_id INTEGER NOT NULL, 
	f_seats_left INTEGER NOT NULL, 
	y_seats_left INTEGER NOT NULL, 
	PRIMARY KEY (flight_no, flight_date, segment_id), 
	FOREIGN KEY(flight_no, flight_date) REFERENCES flight_schedule (flight_no, flight_date) ON DELETE CASCADE, 
	CONSTRAINT ck_inventory_f_nonneg CHECK (f_seats_left >= 0), 
	CONSTRAINT ck_inventory_y_nonneg CHECK (y_seats_left >= 0), 
	FOREIGN KEY(segment_id) REFERENCES route_segment (segment_id) ON DELETE RESTRICT
);

CREATE INDEX ix_schedule_inventory_flight_date_no ON schedule_inventory (flight_date, flight_no);


CREATE TABLE ticket_sale (
	ticket_no VARCHAR(50) NOT NULL, 
	flight_no VARCHAR(20) NOT NULL, 
	flight_date DATE NOT NULL, 
	id_card VARCHAR(20) NOT NULL, 
	start_segment_id INTEGER NOT NULL, 
	end_segment_id INTEGER NOT NULL, 
	cabin_class VARCHAR(20) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	is_active_ticket INTEGER NOT NULL DEFAULT '1', 
	actual_price NUMERIC(10, 2) NOT NULL, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	paid_at DATETIME, 
	refunded_at DATETIME, 
	PRIMARY KEY (ticket_no), 
	FOREIGN KEY(flight_no, flight_date) REFERENCES flight_schedule (flight_no, flight_date) ON DELETE RESTRICT, 
	CONSTRAINT uq_ticket_sale_active_flight_per_passenger UNIQUE (id_card, flight_no, flight_date, is_active_ticket), 
	CONSTRAINT ck_ticket_sale_cabin_class CHECK (cabin_class IN ('F', 'Y')), 
	CONSTRAINT ck_ticket_sale_status CHECK (status IN ('PAID', 'REFUNDED')), 
	CONSTRAINT ck_ticket_sale_is_active_ticket CHECK (is_active_ticket IN (0, 1)), 
	CONSTRAINT ck_ticket_sale_actual_price_nonneg CHECK (actual_price >= 0), 
	FOREIGN KEY(id_card) REFERENCES passenger (id_card) ON DELETE RESTRICT, 
	FOREIGN KEY(start_segment_id) REFERENCES route_segment (segment_id) ON DELETE RESTRICT, 
	FOREIGN KEY(end_segment_id) REFERENCES route_segment (segment_id) ON DELETE RESTRICT
);

CREATE INDEX ix_ticket_sale_owner_date_status ON ticket_sale (id_card, flight_date, status);


CREATE TABLE waitlist_record (
	waitlist_id INTEGER NOT NULL AUTO_INCREMENT, 
	flight_no VARCHAR(20) NOT NULL, 
	flight_date DATE NOT NULL, 
	start_segment_id INTEGER NOT NULL, 
	end_segment_id INTEGER NOT NULL, 
	cabin_class VARCHAR(20) NOT NULL, 
	id_card VARCHAR(20) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	request_time DATETIME NOT NULL DEFAULT now(), 
	released_at DATETIME, 
	PRIMARY KEY (waitlist_id), 
	FOREIGN KEY(flight_no, flight_date) REFERENCES flight_schedule (flight_no, flight_date) ON DELETE RESTRICT, 
	CONSTRAINT ck_waitlist_cabin_class CHECK (cabin_class IN ('F', 'Y')), 
	CONSTRAINT ck_waitlist_status CHECK (status IN ('WAITING', 'RELEASED', 'CANCELLED')), 
	FOREIGN KEY(start_segment_id) REFERENCES route_segment (segment_id) ON DELETE RESTRICT, 
	FOREIGN KEY(end_segment_id) REFERENCES route_segment (segment_id) ON DELETE RESTRICT, 
	FOREIGN KEY(id_card) REFERENCES passenger (id_card) ON DELETE RESTRICT
);

CREATE INDEX ix_waitlist_dispatch ON waitlist_record (flight_no, flight_date, cabin_class, status, request_time);
