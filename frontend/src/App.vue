<script setup>
import { computed, onBeforeUnmount, reactive, ref } from "vue";
import { api, createInventoryEventSource } from "./api";

const DEMO_USER_WINDOW = {
  start: "2030-01-13",
  end: "2030-01-26"
};

const DEMO_ADMIN_WINDOW = {
  start: "2030-01-27",
  end: "2030-02-02"
};

const WEEKDAY_LABELS = {
  1: "Mon",
  2: "Tue",
  3: "Wed",
  4: "Thu",
  5: "Fri",
  6: "Sat",
  7: "Sun"
};

const token = ref(sessionStorage.getItem("flight_token") || "");
const me = ref(null);
const sensitiveProfile = ref(null);
const showSensitiveProfile = ref(false);
const sensitiveProfileLoading = ref(false);
const maskedPassengerName = ref("");
const maskedPassengerIdCard = ref("");
const errorMessage = ref("");
const successMessage = ref("");
const loading = ref(false);
const scheduleGenerationResult = ref(null);
const hasSearchedFlights = ref(false);
const inventoryEventSource = ref(null);
const activeSearchRequest = ref(null);
const expandedRangeDates = ref({});

const loginForm = reactive({
  login_identifier: "",
  password: ""
});

const searchMode = ref("single");
const searchForm = reactive({
  origin_city_code: "SHA",
  destination_city_code: "KMG",
  flight_date: "2030-01-15",
  cabin_class: "Y"
});
const rangeSearchForm = reactive({
  origin_city_code: "",
  destination_city_code: "",
  start_date: "2030-01-15",
  end_date: "2030-01-17",
  cabin_class: "Y"
});

const paymentForm = reactive({
  payment_method: "ALIPAY",
  payer_account: ""
});

const adminGenerateForm = reactive({
  template_id: "",
  start_date: DEMO_ADMIN_WINDOW.start,
  end_date: DEMO_ADMIN_WINDOW.start
});

const adminCancelForm = reactive({
  flight_no: "MU2001",
  flight_date: "2030-01-20"
});

const cityForm = reactive({
  city_code: "",
  city_name: ""
});

const airportForm = reactive({
  airport_code: "",
  airport_name: "",
  city_code: ""
});

const airplaneForm = reactive({
  airplane_id: "",
  aircraft_type: "",
  f_class_capacity: 2,
  y_class_capacity: 10
});

const routeForm = reactive({
  route_id: "",
  route_name: "",
  segments_text:
    '[{"segment_order":1,"dep_airport_code":"SHA","arr_airport_code":"CSX","planned_dep_time":"09:00:00","planned_arr_time":"11:00:00"}]',
  pricing_text:
    '[{"cabin_class":"Y","base_price":580},{"cabin_class":"F","base_price":1080}]'
});

const templateForm = reactive({
  flight_no: "",
  route_id: "",
  default_airplane_id: "",
  default_flight_discount: 0.88,
  status: "ACTIVE",
  weekdays_csv: "1,3,5"
});

const specialFareForm = reactive({
  flight_no: "MU3003",
  flight_date: "2030-01-15",
  cabin_class: "Y",
  start_segment_id: 6,
  end_segment_id: 7,
  special_price: 599,
  quota_total: 5,
  sale_start: "2025-01-01T00:00:00",
  sale_end: "2030-01-15T23:59:59",
  status: "ACTIVE"
});

const editState = reactive({
  cityCode: "",
  airportCode: "",
  airplaneId: "",
  routeId: "",
  templateId: null,
  specialFareId: null
});

const adminSections = reactive({
  schedule: true,
  reference: true,
  resource: true,
  orders: true,
  audits: false
});

const flights = ref([]);
const myOrders = ref([]);
const myWaitlists = ref([]);
const referenceCities = ref([]);
const cities = ref([]);
const airports = ref([]);
const airplanes = ref([]);
const routes = ref([]);
const templates = ref([]);
const specialFares = ref([]);
const adminOrders = ref([]);
const audits = ref([]);

const isAdmin = computed(() => me.value?.role === "ADMIN");
const isUser = computed(() => me.value?.role === "USER");
const displayedPassengerName = computed(() => {
  return me.value?.passenger_name_masked || me.value?.login_identifier || "";
});
const displayedPassengerIdCard = computed(() => {
  return me.value?.passenger_id_card_masked || "";
});

const routeNameById = computed(() =>
  Object.fromEntries(routes.value.map((route) => [route.route_id, route.route_name]))
);

const templateOptions = computed(() =>
  templates.value.map((template) => ({
    value: template.template_id,
    label: `${template.flight_no} | ${routeNameById.value[template.route_id] || template.route_id} | ${formatWeekdays(template.weekdays)}`
  }))
);

const cityOptions = computed(() =>
  referenceCities.value.map((city) => ({
    value: city.city_code,
    label: `${city.city_name} (${city.city_code})`
  }))
);

const searchHeading = computed(() =>
  searchMode.value === "single" ? "Single-day search" : "Date-range search"
);

const groupedRangeFlights = computed(() => {
  if (searchMode.value !== "range") {
    return [];
  }

  const groups = new Map();
  flights.value.forEach((flight) => {
    if (!groups.has(flight.flight_date)) {
      groups.set(flight.flight_date, []);
    }
    groups.get(flight.flight_date).push(flight);
  });

  return Array.from(groups.entries()).map(([flightDate, items]) => ({
    flightDate,
    items
  }));
});

function normalizeText(value) {
  return String(value ?? "").trim();
}

function normalizeUpper(value) {
  return normalizeText(value).toUpperCase();
}

function setMessage(type, message) {
  if (type === "error") {
    errorMessage.value = message;
    successMessage.value = "";
  } else {
    successMessage.value = message;
    errorMessage.value = "";
  }
}

function resetMessages() {
  errorMessage.value = "";
  successMessage.value = "";
}

function closeInventoryStream() {
  if (inventoryEventSource.value) {
    inventoryEventSource.value.close();
    inventoryEventSource.value = null;
  }
}

function formatWeekdays(weekdays) {
  return weekdays.map((weekday) => WEEKDAY_LABELS[weekday] || `W${weekday}`).join(", ");
}

function formatTimestamp(value) {
  if (!value) {
    return "-";
  }
  return value.replace("T", " ").slice(0, 16);
}

function formatPriceSource(value) {
  return value === "SPECIAL" ? "Special Fare" : "Standard Fare";
}

function formatOrderStatus(value) {
  const mapping = {
    PENDING_PAYMENT: "Pending Payment",
    PAID: "Paid",
    EXPIRED: "Expired",
    REFUNDED: "Refunded",
    WAITING: "Waiting",
    RELEASED: "Seat Locked",
    FULFILLED: "Completed",
    CANCELLED: "Cancelled",
    ACTIVE: "Active",
    INACTIVE: "Inactive"
  };
  return mapping[value] || value;
}

function formatPaymentStatus(value) {
  const mapping = {
    PENDING: "Pending",
    PAID: "Paid",
    EXPIRED: "Expired",
    REFUNDED: "Refunded"
  };
  return mapping[value] || value;
}

function formatSpecialFareTag(value) {
  return value ? "Promo" : "";
}

function formatSpecialFareWindow(item) {
  return `${formatTimestamp(item.sale_start)} - ${formatTimestamp(item.sale_end)}`;
}

function formatBlockedReason(item) {
  return item?.blocked_reason || "";
}

function routeSegmentsSummary(route) {
  if (!Array.isArray(route?.segments) || !route.segments.length) {
    return "-";
  }
  return route.segments
    .map(
      (segment) =>
        `${segment.dep_airport_code}->${segment.arr_airport_code} ${segment.planned_dep_time.slice(0, 5)}-${segment.planned_arr_time.slice(0, 5)}`
    )
    .join(" | ");
}

function routePricingSummary(route) {
  if (!Array.isArray(route?.pricing) || !route.pricing.length) {
    return "-";
  }
  return route.pricing
    .map((item) => `${item.cabin_class} ${Number(item.base_price).toFixed(0)}`)
    .join(" / ");
}

function parseJsonArray(label, text) {
  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error(`${label} must be a valid JSON array.`);
  }

  if (!Array.isArray(parsed) || parsed.length === 0) {
    throw new Error(`${label} must be a non-empty array.`);
  }

  return parsed;
}

function parseWeekdaysCsv(value) {
  const weekdays = value
    .split(",")
    .map((item) => normalizeText(item))
    .filter(Boolean)
    .map((item) => Number(item));

  if (!weekdays.length) {
    throw new Error("Weekdays are required.");
  }

  if (weekdays.some((item) => !Number.isInteger(item) || item < 1 || item > 7)) {
    throw new Error("Weekdays must be integers from 1 to 7.");
  }

  if (new Set(weekdays).size !== weekdays.length) {
    throw new Error("Weekdays cannot repeat.");
  }

  return weekdays;
}

function requireNonEmptyFields(entries) {
  for (const [label, value] of entries) {
    if (!normalizeText(value)) {
      throw new Error(`${label} cannot be blank.`);
    }
  }
}

function validateGenerateForm() {
  if (!adminGenerateForm.template_id) {
    throw new Error("Please choose a template.");
  }
  if (!adminGenerateForm.start_date || !adminGenerateForm.end_date) {
    throw new Error("Please fill both dates.");
  }
  if (adminGenerateForm.end_date < adminGenerateForm.start_date) {
    throw new Error("End date cannot be earlier than start date.");
  }
}

function validateRangeSearchForm() {
  if (!rangeSearchForm.start_date || !rangeSearchForm.end_date) {
    throw new Error("Please fill both dates.");
  }
  if (rangeSearchForm.end_date < rangeSearchForm.start_date) {
    throw new Error("End date cannot be earlier than start date.");
  }
}

function buildCityPayload() {
  requireNonEmptyFields([
    ["City code", cityForm.city_code],
    ["City name", cityForm.city_name]
  ]);
  return {
    city_code: normalizeUpper(cityForm.city_code),
    city_name: normalizeText(cityForm.city_name)
  };
}

function buildAirportPayload() {
  requireNonEmptyFields([
    ["Airport code", airportForm.airport_code],
    ["Airport name", airportForm.airport_name],
    ["City code", airportForm.city_code]
  ]);
  return {
    airport_code: normalizeUpper(airportForm.airport_code),
    airport_name: normalizeText(airportForm.airport_name),
    city_code: normalizeUpper(airportForm.city_code)
  };
}

function buildAirplanePayload() {
  requireNonEmptyFields([
    ["Airplane ID", airplaneForm.airplane_id],
    ["Aircraft type", airplaneForm.aircraft_type]
  ]);
  return {
    airplane_id: normalizeUpper(airplaneForm.airplane_id),
    aircraft_type: normalizeText(airplaneForm.aircraft_type),
    f_class_capacity: Number(airplaneForm.f_class_capacity),
    y_class_capacity: Number(airplaneForm.y_class_capacity)
  };
}

function buildRoutePayload() {
  requireNonEmptyFields([
    ["Route ID", routeForm.route_id],
    ["Route name", routeForm.route_name]
  ]);
  return {
    route_id: normalizeUpper(routeForm.route_id),
    route_name: normalizeText(routeForm.route_name),
    segments: parseJsonArray("Segments", routeForm.segments_text),
    pricing: parseJsonArray("Pricing", routeForm.pricing_text)
  };
}

function buildTemplatePayload() {
  requireNonEmptyFields([
    ["Flight number", templateForm.flight_no],
    ["Route ID", templateForm.route_id],
    ["Airplane ID", templateForm.default_airplane_id]
  ]);
  return {
    flight_no: normalizeUpper(templateForm.flight_no),
    route_id: normalizeUpper(templateForm.route_id),
    default_airplane_id: normalizeUpper(templateForm.default_airplane_id),
    default_flight_discount: Number(templateForm.default_flight_discount),
    status: normalizeUpper(templateForm.status) || "ACTIVE",
    weekdays: parseWeekdaysCsv(templateForm.weekdays_csv)
  };
}

function buildSpecialFarePayload() {
  requireNonEmptyFields([
    ["Flight number", specialFareForm.flight_no],
    ["Flight date", specialFareForm.flight_date],
    ["Sale start", specialFareForm.sale_start],
    ["Sale end", specialFareForm.sale_end]
  ]);
  return {
    flight_no: normalizeUpper(specialFareForm.flight_no),
    flight_date: specialFareForm.flight_date,
    cabin_class: normalizeUpper(specialFareForm.cabin_class),
    start_segment_id: Number(specialFareForm.start_segment_id),
    end_segment_id: Number(specialFareForm.end_segment_id),
    special_price: Number(specialFareForm.special_price),
    quota_total: Number(specialFareForm.quota_total),
    sale_start: specialFareForm.sale_start,
    sale_end: specialFareForm.sale_end,
    status: normalizeUpper(specialFareForm.status) || "ACTIVE"
  };
}

function buildScheduleGenerationSummary(result) {
  if (!result) {
    return null;
  }
  return {
    headline: result.generated_count
      ? `Generated ${result.generated_count} schedules`
      : "No new schedules generated",
    hint: result.generated_count
      ? "Matching dates without existing schedules were created."
      : "The selected dates were already covered or did not match the template weekdays.",
    lines: [
      {
        label: "Template weekdays",
        value: formatWeekdays(result.template_weekdays || [])
      },
      {
        label: "Matched dates",
        value: (result.matched_dates || []).join(", ") || "-"
      },
      {
        label: "Generated dates",
        value: (result.generated_dates || []).join(", ") || "-"
      },
      {
        label: "Skipped dates",
        value: (result.skipped_existing_dates || []).join(", ") || "-"
      }
    ]
  };
}

function resetCityForm() {
  cityForm.city_code = "";
  cityForm.city_name = "";
  editState.cityCode = "";
}

function resetAirportForm() {
  airportForm.airport_code = "";
  airportForm.airport_name = "";
  airportForm.city_code = "";
  editState.airportCode = "";
}

function resetAirplaneForm() {
  airplaneForm.airplane_id = "";
  airplaneForm.aircraft_type = "";
  airplaneForm.f_class_capacity = 2;
  airplaneForm.y_class_capacity = 10;
  editState.airplaneId = "";
}

function resetRouteForm() {
  routeForm.route_id = "";
  routeForm.route_name = "";
  routeForm.segments_text =
    '[{"segment_order":1,"dep_airport_code":"SHA","arr_airport_code":"CSX","planned_dep_time":"09:00:00","planned_arr_time":"11:00:00"}]';
  routeForm.pricing_text =
    '[{"cabin_class":"Y","base_price":580},{"cabin_class":"F","base_price":1080}]';
  editState.routeId = "";
}

function resetTemplateForm() {
  templateForm.flight_no = "";
  templateForm.route_id = "";
  templateForm.default_airplane_id = "";
  templateForm.default_flight_discount = 0.88;
  templateForm.status = "ACTIVE";
  templateForm.weekdays_csv = "1,3,5";
  editState.templateId = null;
}

function resetSpecialFareForm() {
  specialFareForm.flight_no = "MU3003";
  specialFareForm.flight_date = "2030-01-15";
  specialFareForm.cabin_class = "Y";
  specialFareForm.start_segment_id = 6;
  specialFareForm.end_segment_id = 7;
  specialFareForm.special_price = 599;
  specialFareForm.quota_total = 5;
  specialFareForm.sale_start = "2025-01-01T00:00:00";
  specialFareForm.sale_end = "2030-01-15T23:59:59";
  specialFareForm.status = "ACTIVE";
  editState.specialFareId = null;
}

function hydrateRouteForm(route) {
  if (!route.can_edit) {
    setMessage("error", formatBlockedReason(route) || "This route cannot be edited.");
    return;
  }
  routeForm.route_id = route.route_id;
  routeForm.route_name = route.route_name;
  routeForm.segments_text = JSON.stringify(route.segments, null, 2);
  routeForm.pricing_text = JSON.stringify(route.pricing, null, 2);
  editState.routeId = route.route_id;
}

function hydrateTemplateForm(template) {
  templateForm.flight_no = template.flight_no;
  templateForm.route_id = template.route_id;
  templateForm.default_airplane_id = template.default_airplane_id;
  templateForm.default_flight_discount = template.default_flight_discount;
  templateForm.status = template.status;
  templateForm.weekdays_csv = template.weekdays.join(",");
  editState.templateId = template.template_id;
}

function hydrateSpecialFareForm(item) {
  specialFareForm.flight_no = item.flight_no;
  specialFareForm.flight_date = item.flight_date;
  specialFareForm.cabin_class = item.cabin_class;
  specialFareForm.start_segment_id = item.start_segment_id;
  specialFareForm.end_segment_id = item.end_segment_id;
  specialFareForm.special_price = item.special_price;
  specialFareForm.quota_total = item.quota_total;
  specialFareForm.sale_start = item.sale_start.slice(0, 19);
  specialFareForm.sale_end = item.sale_end.slice(0, 19);
  specialFareForm.status = item.status;
  editState.specialFareId = item.special_fare_id;
}

function confirmDeletion(label, value) {
  return window.confirm(`Delete ${label} ${value}? This action cannot be undone.`);
}

function shouldRefreshSearchFromEvent(payload) {
  if (!hasSearchedFlights.value || loading.value) {
    return false;
  }

  if (!payload?.flight_date || !payload?.cabin_class) {
    return false;
  }

  if (!activeSearchRequest.value) {
    return false;
  }

  if (activeSearchRequest.value.mode === "single") {
    return (
      payload.flight_date === activeSearchRequest.value.params.flight_date &&
      payload.cabin_class === activeSearchRequest.value.params.cabin_class
    );
  }

  return (
    payload.flight_date >= activeSearchRequest.value.params.start_date &&
    payload.flight_date <= activeSearchRequest.value.params.end_date &&
    payload.cabin_class === activeSearchRequest.value.params.cabin_class
  );
}

function buildSearchRequestFromForms() {
  if (searchMode.value === "single") {
    return {
      mode: "single",
      params: {
        origin_city_code: normalizeUpper(searchForm.origin_city_code),
        destination_city_code: normalizeUpper(searchForm.destination_city_code),
        flight_date: searchForm.flight_date,
        cabin_class: normalizeUpper(searchForm.cabin_class)
      }
    };
  }

  validateRangeSearchForm();
  return {
    mode: "range",
    params: {
      origin_city_code: normalizeUpper(rangeSearchForm.origin_city_code),
      destination_city_code: normalizeUpper(rangeSearchForm.destination_city_code),
      start_date: rangeSearchForm.start_date,
      end_date: rangeSearchForm.end_date,
      cabin_class: normalizeUpper(rangeSearchForm.cabin_class)
    }
  };
}

function resetExpandedRangeDates(nextFlights) {
  expandedRangeDates.value = Object.fromEntries(
    nextFlights.map((flight) => [flight.flight_date, true])
  );
}

function isRangeDateExpanded(flightDate) {
  return expandedRangeDates.value[flightDate] !== false;
}

function toggleRangeDate(flightDate) {
  expandedRangeDates.value = {
    ...expandedRangeDates.value,
    [flightDate]: !isRangeDateExpanded(flightDate)
  };
}

async function executeSearchRequest(searchRequest, { silent = false } = {}) {
  if (searchRequest.mode === "single") {
    flights.value = await api.searchFlights(token.value, searchRequest.params);
    expandedRangeDates.value = {};
  } else {
    flights.value = await api.searchFlightsRange(token.value, searchRequest.params);
    resetExpandedRangeDates(flights.value);
  }

  activeSearchRequest.value = searchRequest;
  hasSearchedFlights.value = true;

  if (!silent) {
    setMessage("success", `Found ${flights.value.length} sellable results.`);
  }
}

async function runCurrentSearch({ silent = false } = {}) {
  const searchRequest = buildSearchRequestFromForms();
  await executeSearchRequest(searchRequest, { silent });
}

async function refreshActiveSearch({ silent = false } = {}) {
  if (!hasSearchedFlights.value || !activeSearchRequest.value) {
    return;
  }

  await executeSearchRequest(activeSearchRequest.value, { silent });
}

function startInventoryStream() {
  closeInventoryStream();
  if (!token.value || !isUser.value) {
    return;
  }

  const source = createInventoryEventSource(token.value);
  source.addEventListener("inventory_update", async (event) => {
    try {
      const payload = JSON.parse(event.data);
      const tasks = [loadOrders(), loadWaitlists()];
      if (shouldRefreshSearchFromEvent(payload)) {
        tasks.push(refreshActiveSearch({ silent: true }));
      }
      await Promise.all(tasks);
    } catch {
      // Keep the current UI stable if a single stream event is malformed.
    }
  });
  source.onerror = () => {
    closeInventoryStream();
  };
  inventoryEventSource.value = source;
}

function buildDeleteErrorMessage(label, value, error) {
  const message = error?.message || `Failed to delete ${label} ${value}.`;
  if (message.includes("still referenced")) {
    return `${label} ${value} is still referenced and cannot be deleted.`;
  }
  if (message.includes("not found")) {
    return `${label} ${value} does not exist or has already been deleted.`;
  }
  return message;
}

function toggleAdminSection(sectionKey) {
  adminSections[sectionKey] = !adminSections[sectionKey];
}

async function toggleSensitiveProfile() {
  if (!isUser.value) {
    return;
  }
  if (showSensitiveProfile.value) {
    showSensitiveProfile.value = false;
    if (me.value) {
      me.value.passenger_name_masked = maskedPassengerName.value;
      me.value.passenger_id_card_masked = maskedPassengerIdCard.value;
    }
    return;
  }
  try {
    sensitiveProfileLoading.value = true;
    if (!sensitiveProfile.value) {
      sensitiveProfile.value = await api.meSensitive(token.value);
    }
    if (me.value) {
      me.value.passenger_name_masked = sensitiveProfile.value.passenger_name_full;
      me.value.passenger_id_card_masked = sensitiveProfile.value.passenger_id_card_full;
    }
    showSensitiveProfile.value = true;
  } catch (error) {
    setMessage("error", error.message);
  } finally {
    sensitiveProfileLoading.value = false;
  }
}

async function bootstrap() {
  if (!token.value) {
    closeInventoryStream();
    return;
  }

  try {
    resetMessages();
    if (!referenceCities.value.length) {
      referenceCities.value = await api.listReferenceCities();
    }
    me.value = await api.me(token.value);
    maskedPassengerName.value = me.value?.passenger_name_masked || "";
    maskedPassengerIdCard.value = me.value?.passenger_id_card_masked || "";
    if (showSensitiveProfile.value && isUser.value && sensitiveProfile.value) {
      me.value.passenger_name_masked = sensitiveProfile.value.passenger_name_full;
      me.value.passenger_id_card_masked = sensitiveProfile.value.passenger_id_card_full;
    }
    if (isUser.value) {
      await Promise.all([loadOrders(), loadWaitlists()]);
    }
    if (isAdmin.value) {
      await Promise.all([
        loadCities(),
        loadAirports(),
        loadAirplanes(),
        loadRoutes(),
        loadTemplates(),
        loadSpecialFares(),
        loadAdminOrders(),
        loadAudits()
      ]);
    }
    startInventoryStream();
  } catch (error) {
    closeInventoryStream();
    token.value = "";
    me.value = null;
    sessionStorage.removeItem("flight_token");
    setMessage("error", error.message);
  }
}

async function withLoading(action) {
  loading.value = true;
  try {
    await action();
  } finally {
    loading.value = false;
  }
}

async function login() {
  await withLoading(async () => {
    const result = await api.login(normalizeText(loginForm.login_identifier), normalizeText(loginForm.password));
    token.value = result.access_token;
    sessionStorage.setItem("flight_token", token.value);
    await bootstrap();
    setMessage("success", "Signed in successfully.");
  }).catch((error) => {
    setMessage("error", error.message);
  });
}

function logout() {
  closeInventoryStream();
  token.value = "";
  me.value = null;
  sensitiveProfile.value = null;
  showSensitiveProfile.value = false;
  sensitiveProfileLoading.value = false;
  maskedPassengerName.value = "";
  maskedPassengerIdCard.value = "";
  flights.value = [];
  myOrders.value = [];
  myWaitlists.value = [];
  specialFares.value = [];
  scheduleGenerationResult.value = null;
  hasSearchedFlights.value = false;
  activeSearchRequest.value = null;
  sessionStorage.removeItem("flight_token");
  setMessage("success", "Signed out.");
}

async function searchFlights() {
  await withLoading(async () => {
    await runCurrentSearch();
  }).catch((error) => {
    setMessage("error", error.message);
  });
}

async function purchase(flight) {
  await withLoading(async () => {
    await api.purchaseTicket(token.value, {
      flight_no: flight.flight_no,
      flight_date: flight.flight_date,
      start_segment_id: flight.origin_segment_id,
      end_segment_id: flight.destination_segment_id,
      cabin_class: flight.cabin_class
    });
    await Promise.all([loadOrders(), refreshActiveSearch(), bootstrap()]);
    setMessage("success", `Created pending order for ${flight.flight_no}.`);
  }).catch((error) => {
    setMessage("error", error.message);
  });
}

async function confirmOrderPayment(order) {
  await withLoading(async () => {
    const payerAccount = normalizeText(paymentForm.payer_account) || `${me.value.login_identifier}-pay`;
    await api.confirmPayment(token.value, order.payment_id, {
      payment_method: normalizeUpper(paymentForm.payment_method),
      payer_account: payerAccount
    });
    await Promise.all([loadOrders(), refreshActiveSearch(), bootstrap()]);
    setMessage("success", `Payment confirmed for ${order.ticket_no}.`);
  }).catch((error) => {
    setMessage("error", error.message);
  });
}

async function joinWaitlist(flight) {
  await withLoading(async () => {
    await api.createWaitlist(token.value, {
      flight_no: flight.flight_no,
      flight_date: flight.flight_date,
      start_segment_id: flight.origin_segment_id,
      end_segment_id: flight.destination_segment_id,
      cabin_class: flight.cabin_class
    });
    await loadWaitlists();
    setMessage("success", `Joined waitlist for ${flight.flight_no}.`);
  }).catch((error) => {
    setMessage("error", error.message);
  });
}

async function refund(ticketNo) {
  await withLoading(async () => {
    await api.refundTicket(token.value, ticketNo);
    await Promise.all([loadOrders(), loadWaitlists(), refreshActiveSearch(), bootstrap()]);
    setMessage("success", `Order ${ticketNo} refunded.`);
  }).catch((error) => {
    setMessage("error", error.message);
  });
}

async function cancelPendingOrder(ticketNo) {
  await withLoading(async () => {
    await api.cancelPendingTicket(token.value, ticketNo);
    await Promise.all([loadOrders(), loadWaitlists(), refreshActiveSearch(), bootstrap()]);
    setMessage("success", `Order ${ticketNo} cancelled.`);
  }).catch((error) => {
    setMessage("error", error.message);
  });
}

async function loadOrders() {
  myOrders.value = await api.listMyOrders(token.value);
}

async function loadWaitlists() {
  myWaitlists.value = await api.listMyWaitlists(token.value);
}

async function loadCities() {
  cities.value = await api.listCities(token.value);
}

async function loadAirports() {
  airports.value = await api.listAirports(token.value);
}

async function loadAirplanes() {
  airplanes.value = await api.listAirplanes(token.value);
}

async function loadRoutes() {
  routes.value = await api.listRoutes(token.value);
}

async function loadTemplates() {
  templates.value = await api.listTemplates(token.value);
  if (!adminGenerateForm.template_id && templates.value.length) {
    const preferredTemplate = templates.value.find((template) => template.flight_no === "MU2001") || templates.value[0];
    adminGenerateForm.template_id = String(preferredTemplate.template_id);
  }
}

async function loadSpecialFares() {
  specialFares.value = await api.listSpecialFares(token.value);
}

async function loadAdminOrders() {
  adminOrders.value = await api.listAdminOrders(token.value);
}

async function loadAudits() {
  audits.value = await api.listAudits(token.value);
}

async function submitCity() {
  try {
    const payload = buildCityPayload();
    if (editState.cityCode) {
      await api.updateCity(token.value, editState.cityCode, payload);
      setMessage("success", `City ${payload.city_code} updated.`);
    } else {
      await api.createCity(token.value, payload);
      setMessage("success", `City ${payload.city_code} created.`);
    }
    resetCityForm();
    await loadCities();
  } catch (error) {
    setMessage("error", error.message);
  }
}

function editCity(city) {
  if (!city.can_edit) {
    setMessage("error", formatBlockedReason(city) || "This city cannot be edited.");
    return;
  }
  cityForm.city_code = city.city_code;
  cityForm.city_name = city.city_name;
  editState.cityCode = city.city_code;
}

async function deleteCity(code) {
  if (!confirmDeletion("city", code)) {
    return;
  }
  try {
    await api.deleteCity(token.value, code);
    if (editState.cityCode === code) {
      resetCityForm();
    }
    await loadCities();
    setMessage("success", `City ${code} deleted.`);
  } catch (error) {
    setMessage("error", buildDeleteErrorMessage("city", code, error));
  }
}

async function submitAirport() {
  try {
    const payload = buildAirportPayload();
    if (editState.airportCode) {
      await api.updateAirport(token.value, editState.airportCode, payload);
      setMessage("success", `Airport ${payload.airport_code} updated.`);
    } else {
      await api.createAirport(token.value, payload);
      setMessage("success", `Airport ${payload.airport_code} created.`);
    }
    resetAirportForm();
    await loadAirports();
  } catch (error) {
    setMessage("error", error.message);
  }
}

function editAirport(airport) {
  if (!airport.can_edit) {
    setMessage("error", formatBlockedReason(airport) || "This airport cannot be edited.");
    return;
  }
  airportForm.airport_code = airport.airport_code;
  airportForm.airport_name = airport.airport_name;
  airportForm.city_code = airport.city_code;
  editState.airportCode = airport.airport_code;
}

async function deleteAirport(code) {
  if (!confirmDeletion("airport", code)) {
    return;
  }
  try {
    await api.deleteAirport(token.value, code);
    if (editState.airportCode === code) {
      resetAirportForm();
    }
    await loadAirports();
    setMessage("success", `Airport ${code} deleted.`);
  } catch (error) {
    setMessage("error", buildDeleteErrorMessage("airport", code, error));
  }
}

async function submitAirplane() {
  try {
    const payload = buildAirplanePayload();
    if (editState.airplaneId) {
      await api.updateAirplane(token.value, editState.airplaneId, payload);
      setMessage("success", `Airplane ${payload.airplane_id} updated.`);
    } else {
      await api.createAirplane(token.value, payload);
      setMessage("success", `Airplane ${payload.airplane_id} created.`);
    }
    resetAirplaneForm();
    await loadAirplanes();
  } catch (error) {
    setMessage("error", error.message);
  }
}

function editAirplane(airplane) {
  if (!airplane.can_edit) {
    setMessage("error", formatBlockedReason(airplane) || "This airplane cannot be edited.");
    return;
  }
  airplaneForm.airplane_id = airplane.airplane_id;
  airplaneForm.aircraft_type = airplane.aircraft_type;
  airplaneForm.f_class_capacity = airplane.f_class_capacity;
  airplaneForm.y_class_capacity = airplane.y_class_capacity;
  editState.airplaneId = airplane.airplane_id;
}

async function deleteAirplane(id) {
  if (!confirmDeletion("airplane", id)) {
    return;
  }
  try {
    await api.deleteAirplane(token.value, id);
    if (editState.airplaneId === id) {
      resetAirplaneForm();
    }
    await loadAirplanes();
    setMessage("success", `Airplane ${id} deleted.`);
  } catch (error) {
    setMessage("error", buildDeleteErrorMessage("airplane", id, error));
  }
}

async function submitRoute() {
  try {
    const payload = buildRoutePayload();
    if (editState.routeId) {
      await api.updateRoute(token.value, editState.routeId, payload);
      setMessage("success", `Route ${payload.route_id} updated.`);
    } else {
      await api.createRoute(token.value, payload);
      setMessage("success", `Route ${payload.route_id} created.`);
    }
    resetRouteForm();
    await loadRoutes();
  } catch (error) {
    setMessage("error", error.message);
  }
}

async function deleteRoute(routeId) {
  if (!confirmDeletion("route", routeId)) {
    return;
  }
  try {
    await api.deleteRoute(token.value, routeId);
    if (editState.routeId === routeId) {
      resetRouteForm();
    }
    await loadRoutes();
    setMessage("success", `Route ${routeId} deleted.`);
  } catch (error) {
    setMessage("error", buildDeleteErrorMessage("route", routeId, error));
  }
}

async function submitTemplate() {
  try {
    const payload = buildTemplatePayload();
    if (editState.templateId) {
      await api.updateTemplate(token.value, editState.templateId, payload);
      setMessage("success", `Template ${payload.flight_no} updated.`);
    } else {
      await api.createTemplate(token.value, payload);
      setMessage("success", `Template ${payload.flight_no} created.`);
    }
    resetTemplateForm();
    await loadTemplates();
  } catch (error) {
    setMessage("error", error.message);
  }
}

async function deleteTemplate(templateId) {
  if (!confirmDeletion("template", `#${templateId}`)) {
    return;
  }
  try {
    await api.deleteTemplate(token.value, templateId);
    if (editState.templateId === templateId) {
      resetTemplateForm();
    }
    if (String(templateId) === adminGenerateForm.template_id) {
      adminGenerateForm.template_id = "";
    }
    await loadTemplates();
    setMessage("success", `Template #${templateId} deleted.`);
  } catch (error) {
    setMessage("error", buildDeleteErrorMessage("template", `#${templateId}`, error));
  }
}

async function submitSpecialFare() {
  try {
    const payload = buildSpecialFarePayload();
    if (editState.specialFareId) {
      await api.updateSpecialFare(token.value, editState.specialFareId, payload);
      setMessage("success", `Special fare #${editState.specialFareId} updated.`);
    } else {
      await api.createSpecialFare(token.value, payload);
      setMessage("success", `Special fare for ${payload.flight_no} created.`);
    }
    resetSpecialFareForm();
    await loadSpecialFares();
  } catch (error) {
    setMessage("error", error.message);
  }
}

async function deleteSpecialFare(specialFareId) {
  if (!confirmDeletion("special fare", `#${specialFareId}`)) {
    return;
  }
  try {
    await api.deleteSpecialFare(token.value, specialFareId);
    if (editState.specialFareId === specialFareId) {
      resetSpecialFareForm();
    }
    await loadSpecialFares();
    setMessage("success", `Special fare #${specialFareId} deleted.`);
  } catch (error) {
    setMessage("error", buildDeleteErrorMessage("special fare", `#${specialFareId}`, error));
  }
}

async function generateSchedules() {
  await withLoading(async () => {
    validateGenerateForm();
    const result = await api.generateSchedules(token.value, {
      template_id: Number(adminGenerateForm.template_id),
      start_date: adminGenerateForm.start_date,
      end_date: adminGenerateForm.end_date
    });
    scheduleGenerationResult.value = buildScheduleGenerationSummary(result);
    setMessage("success", scheduleGenerationResult.value.headline);
  }).catch((error) => {
    setMessage("error", error.message);
  });
}

async function cancelFlight() {
  await withLoading(async () => {
    await api.cancelSchedule(token.value, normalizeUpper(adminCancelForm.flight_no), adminCancelForm.flight_date);
    await Promise.all([loadAdminOrders(), loadAudits()]);
    setMessage("success", "Schedule cancelled and paid orders refunded.");
  }).catch((error) => {
    setMessage("error", error.message);
  });
}

onBeforeUnmount(() => {
  closeInventoryStream();
});

bootstrap();
</script>

<template>
  <div class="shell">
    <div class="aurora aurora-a"></div>
    <div class="aurora aurora-b"></div>

    <header class="hero">
      <div>
        <p class="eyebrow">Flight Ticketing Control Deck</p>
        <h1>Course Demo Airline Ticketing System</h1>
        <p class="hero-copy">
          This demo focuses on the key course features that need to be shown clearly:
          masked passenger data, pending-payment orders, mock payment confirmation,
          special-fare display, admin configuration, and mileage rollback after refunds.
        </p>
      </div>
      <div v-if="me" class="hero-card">
        <p class="hero-card-label">Current session</p>
        <h2>{{ displayedPassengerName }}</h2>
        <p>{{ me.role }} / {{ me.user_type || "ADMIN" }}</p>
        <p v-if="displayedPassengerIdCard">ID Card {{ displayedPassengerIdCard }}</p>
        <p v-if="me.mileage_points != null">Mileage Points {{ Number(me.mileage_points).toFixed(2) }}</p>
        <button
          v-if="isUser"
          class="secondary"
          :disabled="sensitiveProfileLoading"
          @click="toggleSensitiveProfile"
        >
          {{ showSensitiveProfile ? "Mask Sensitive Fields" : "Show Full Sensitive Fields" }}
        </button>
        <button class="secondary" @click="logout">Sign Out</button>
      </div>
    </header>

    <section v-if="!me" class="panel panel-login">
      <div class="panel-title">
        <h2>Sign In</h2>
        <p>
          Demo passenger accounts now use independent usernames instead of raw ID-card
          numbers as login identifiers.
        </p>
      </div>
      <div class="form-grid">
        <label>
          Login Identifier
          <input v-model="loginForm.login_identifier" placeholder="alice01 / admin" />
        </label>
        <label>
          Password
          <input v-model="loginForm.password" type="password" placeholder="Enter password" />
        </label>
      </div>
      <div class="action-row">
        <button @click="login" :disabled="loading">Sign In</button>
        <span class="muted">
          Demo accounts:
          <code>alice01 / user123</code>,
          <code>bob01 / user123</code>,
          <code>admin / admin123</code>
        </span>
      </div>
    </section>

    <section v-if="errorMessage" class="flash flash-error">{{ errorMessage }}</section>
    <section v-if="successMessage" class="flash flash-success">{{ successMessage }}</section>

    <template v-if="isUser">
      <section class="panel">
        <div class="panel-title">
          <h2>Flight Search and Quotes</h2>
          <p>
            Standard fares follow the regular pricing formula. When a special-fare plan
            matches, the result shows the activity price directly and marks the price source.
          </p>
        </div>

        <div class="mode-switch">
          <button class="secondary" :class="{ active: searchMode === 'single' }" @click="searchMode = 'single'">
            Single-day Search
          </button>
          <button class="secondary" :class="{ active: searchMode === 'range' }" @click="searchMode = 'range'">
            Date-range Search
          </button>
        </div>

        <div class="query-banner">
          <strong>{{ searchHeading }}</strong>
          <span>
            Demo user window: {{ DEMO_USER_WINDOW.start }} to {{ DEMO_USER_WINDOW.end }}
          </span>
        </div>

        <div v-if="searchMode === 'single'" class="form-grid four">
          <label>
            Origin City
            <select v-model="searchForm.origin_city_code">
              <option value="">All</option>
              <option v-for="city in cityOptions" :key="city.value" :value="city.value">
                {{ city.label }}
              </option>
            </select>
          </label>
          <label>
            Destination City
            <select v-model="searchForm.destination_city_code">
              <option value="">All</option>
              <option v-for="city in cityOptions" :key="city.value" :value="city.value">
                {{ city.label }}
              </option>
            </select>
          </label>
          <label>
            Date
            <input v-model="searchForm.flight_date" type="date" />
          </label>
          <label>
            Cabin
            <select v-model="searchForm.cabin_class">
              <option value="Y">Economy Y</option>
              <option value="F">First F</option>
            </select>
          </label>
        </div>
        <div v-else class="form-grid five">
          <label>
            Origin City
            <select v-model="rangeSearchForm.origin_city_code">
              <option value="">All</option>
              <option v-for="city in cityOptions" :key="city.value" :value="city.value">
                {{ city.label }}
              </option>
            </select>
          </label>
          <label>
            Destination City
            <select v-model="rangeSearchForm.destination_city_code">
              <option value="">All</option>
              <option v-for="city in cityOptions" :key="city.value" :value="city.value">
                {{ city.label }}
              </option>
            </select>
          </label>
          <label>
            Start Date
            <input v-model="rangeSearchForm.start_date" type="date" />
          </label>
          <label>
            End Date
            <input v-model="rangeSearchForm.end_date" type="date" />
          </label>
          <label>
            Cabin
            <select v-model="rangeSearchForm.cabin_class">
              <option value="Y">Economy Y</option>
              <option value="F">First F</option>
            </select>
          </label>
        </div>

        <div class="action-row">
          <button @click="searchFlights" :disabled="loading">Search Flights</button>
        </div>

        <p v-if="!flights.length" class="muted">No search results yet. Run a search to load sellable flights.</p>

        <div v-if="flights.length && searchMode === 'single'" class="card-grid">
          <article
            v-for="flight in flights"
            :key="`${flight.flight_no}-${flight.flight_date}-${flight.origin_segment_id}-${flight.destination_segment_id}-${flight.cabin_class}`"
            class="flight-card"
          >
            <div class="flight-head">
              <div>
                <p class="eyebrow">Flight {{ flight.flight_no }}</p>
                <h3>{{ flight.origin_airport_name }} -> {{ flight.destination_airport_name }}</h3>
              </div>
              <strong>{{ flight.final_price.toFixed(2) }} CNY</strong>
            </div>
            <p class="muted">Airport Codes: {{ flight.origin_airport }} -> {{ flight.destination_airport }}</p>
            <p>{{ flight.flight_date }} / {{ flight.departure_time }} - {{ flight.arrival_time }}</p>
            <p>Cabin {{ flight.cabin_class }} / Seats Left {{ flight.available_seats }}</p>
            <p class="flight-tags">
              <span class="pill" :class="{ 'pill-special': flight.is_special_fare }">{{ formatPriceSource(flight.price_source) }}</span>
              <span v-if="flight.special_fare_tag" class="pill pill-special">{{ formatSpecialFareTag(flight.special_fare_tag) }}</span>
            </p>
            <p v-if="flight.is_special_fare" class="muted">
              Special fare does not stack with member discounts or inventory factors.
            </p>
            <p v-else class="muted">
              Standard fare already includes flight discount, user discount, and inventory factor.
            </p>
            <div class="action-row">
              <button v-if="flight.available_seats > 0" @click="purchase(flight)">Create Pending Order</button>
              <button v-else class="secondary" @click="joinWaitlist(flight)">Join Waitlist</button>
            </div>
          </article>
        </div>

        <div v-if="flights.length && searchMode === 'range'" class="range-results-shell">
          <section
            v-for="group in groupedRangeFlights"
            :key="group.flightDate"
            class="range-day-group"
          >
            <button class="range-day-toggle" @click="toggleRangeDate(group.flightDate)">
              <div>
                <span class="eyebrow">Flight Date</span>
                <h3>{{ group.flightDate }}</h3>
                <p class="range-day-meta">{{ group.items.length }} result{{ group.items.length > 1 ? "s" : "" }}</p>
              </div>
              <span>{{ isRangeDateExpanded(group.flightDate) ? "Collapse" : "Expand" }}</span>
            </button>

            <div v-if="isRangeDateExpanded(group.flightDate)" class="range-day-grid card-grid">
              <article
                v-for="flight in group.items"
                :key="`${flight.flight_no}-${flight.flight_date}-${flight.origin_segment_id}-${flight.destination_segment_id}-${flight.cabin_class}`"
                class="flight-card"
              >
                <div class="flight-head">
                  <div>
                    <p class="eyebrow">Flight {{ flight.flight_no }}</p>
                    <h3>{{ flight.origin_airport_name }} -> {{ flight.destination_airport_name }}</h3>
                  </div>
                  <strong>{{ flight.final_price.toFixed(2) }} CNY</strong>
                </div>
                <p class="muted">Airport Codes: {{ flight.origin_airport }} -> {{ flight.destination_airport }}</p>
                <p>{{ flight.flight_date }} / {{ flight.departure_time }} - {{ flight.arrival_time }}</p>
                <p>Cabin {{ flight.cabin_class }} / Seats Left {{ flight.available_seats }}</p>
                <p class="flight-tags">
                  <span class="pill" :class="{ 'pill-special': flight.is_special_fare }">{{ formatPriceSource(flight.price_source) }}</span>
                  <span v-if="flight.special_fare_tag" class="pill pill-special">{{ formatSpecialFareTag(flight.special_fare_tag) }}</span>
                </p>
                <p v-if="flight.is_special_fare" class="muted">
                  Special fare does not stack with member discounts or inventory factors.
                </p>
                <p v-else class="muted">
                  Standard fare already includes flight discount, user discount, and inventory factor.
                </p>
                <div class="action-row">
                  <button v-if="flight.available_seats > 0" @click="purchase(flight)">Create Pending Order</button>
                  <button v-else class="secondary" @click="joinWaitlist(flight)">Join Waitlist</button>
                </div>
              </article>
            </div>
          </section>
        </div>
      </section>

      <section class="split">
        <div class="panel">
          <div class="panel-title">
            <h2>My Orders</h2>
            <p>
              Purchase creates a pending order first. The order becomes paid only after the
              user clicks mock payment confirmation.
            </p>
          </div>
          <div class="form-grid">
            <label>
              Payment Method
              <select v-model="paymentForm.payment_method">
                <option value="ALIPAY">ALIPAY</option>
                <option value="WECHAT">WECHAT</option>
                <option value="BANK_CARD">BANK_CARD</option>
              </select>
            </label>
            <label>
              Payer Account
              <input v-model="paymentForm.payer_account" placeholder="for example alice-pay-001" />
            </label>
          </div>
          <table>
            <thead>
              <tr>
                <th>Order</th>
                <th>Flight</th>
                <th>Status</th>
                <th>Price</th>
                <th>Deadline / Finish Time</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!myOrders.length">
                <td colspan="6" class="muted">No orders yet.</td>
              </tr>
              <tr v-for="order in myOrders" :key="order.ticket_no">
                <td>
                  <strong>{{ order.ticket_no }}</strong>
                  <div class="muted">{{ formatPriceSource(order.price_source) }}</div>
                </td>
                <td>
                  <div>{{ order.flight_no }} / {{ order.flight_date }}</div>
                  <div class="muted">Route: {{ order.origin_city_name }} -> {{ order.destination_city_name }}</div>
                </td>
                <td>
                  <div>{{ formatOrderStatus(order.status) }}</div>
                  <div v-if="order.status === 'PENDING_PAYMENT'" class="muted">Pay Before (System Time): {{ formatTimestamp(order.hold_expires_at) }}</div>
                </td>
                <td>{{ Number(order.actual_price).toFixed(2) }}</td>
                <td>{{ formatTimestamp(order.hold_expires_at || order.paid_at || order.refunded_at) }}</td>
                <td>
                  <div class="inline-actions">
                    <button
                      v-if="order.status === 'PENDING_PAYMENT'"
                      class="secondary"
                      @click="confirmOrderPayment(order)"
                    >
                      Mock Pay
                    </button>
                    <button
                      v-if="order.status === 'PENDING_PAYMENT'"
                      class="ghost"
                      @click="cancelPendingOrder(order.ticket_no)"
                    >
                      Cancel Order
                    </button>
                    <button
                      v-if="order.status === 'PAID'"
                      class="danger"
                      @click="refund(order.ticket_no)"
                    >
                      Refund
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="panel">
          <div class="panel-title">
            <h2>My Waitlists</h2>
            <p>Released seats now auto-lock for the first waitlist user and open a 15-minute payment window.</p>
          </div>
          <ul class="stack-list">
            <li v-if="!myWaitlists.length">
              <span class="muted">No waitlist records yet.</span>
            </li>
            <li v-for="wait in myWaitlists" :key="wait.waitlist_id">
              <strong>{{ wait.flight_no }} / {{ wait.flight_date }}</strong>
              <span class="muted">Route: {{ wait.origin_city_name }} -> {{ wait.destination_city_name }}</span>
              <span>Cabin {{ wait.cabin_class }} / Segment {{ wait.start_segment_id }} -> {{ wait.end_segment_id }}</span>
              <span class="pill">{{ formatOrderStatus(wait.status) }}</span>
              <span class="muted">Requested: {{ formatTimestamp(wait.request_time) }}</span>
              <span v-if="wait.linked_ticket_no" class="muted">Linked Order: {{ wait.linked_ticket_no }}</span>
              <span v-if="wait.offer_expires_at" class="muted">Offer Expires: {{ formatTimestamp(wait.offer_expires_at) }}</span>
            </li>
          </ul>
        </div>
      </section>
    </template>

    <template v-if="isAdmin">
      <section class="panel admin-section">
        <button class="section-toggle" @click="toggleAdminSection('schedule')">
          <div>
            <span class="eyebrow">Admin Section</span>
            <h2>Schedule and Flight Control</h2>
          </div>
          <span>{{ adminSections.schedule ? "Collapse" : "Expand" }}</span>
        </button>
        <div v-if="adminSections.schedule" class="section-content">
          <p class="subcopy">
            Generate concrete schedules from templates, or cancel a flight and refund paid tickets.
          </p>
          <div class="split">
            <div class="subpanel">
              <h3>Generate Schedules</h3>
              <div class="form-grid">
                <label>
                  Template
                  <select v-model="adminGenerateForm.template_id">
                    <option value="">Choose a template</option>
                    <option v-for="option in templateOptions" :key="option.value" :value="String(option.value)">
                      {{ option.label }}
                    </option>
                  </select>
                </label>
                <label>
                  Start Date
                  <input v-model="adminGenerateForm.start_date" type="date" />
                </label>
                <label>
                  End Date
                  <input v-model="adminGenerateForm.end_date" type="date" />
                </label>
              </div>
              <div class="action-row">
                <button @click="generateSchedules" :disabled="loading">Generate Schedules</button>
              </div>
              <div v-if="scheduleGenerationResult" class="result-card">
                <h4>{{ scheduleGenerationResult.headline }}</h4>
                <p class="muted">{{ scheduleGenerationResult.hint }}</p>
                <p v-for="line in scheduleGenerationResult.lines" :key="line.label">
                  <strong>{{ line.label }}:</strong> {{ line.value }}
                </p>
              </div>
            </div>
            <div class="subpanel">
              <h3>Cancel Flight</h3>
              <div class="form-grid">
                <label>
                  Flight No
                  <input v-model="adminCancelForm.flight_no" />
                </label>
                <label>
                  Date
                  <input v-model="adminCancelForm.flight_date" type="date" />
                </label>
              </div>
              <div class="action-row">
                <button class="danger" @click="cancelFlight">Cancel and Refund</button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section class="panel admin-section">
        <button class="section-toggle" @click="toggleAdminSection('reference')">
          <div>
            <span class="eyebrow">Admin Section</span>
            <h2>Reference Data Maintenance</h2>
          </div>
          <span>{{ adminSections.reference ? "Collapse" : "Expand" }}</span>
        </button>
        <div v-if="adminSections.reference" class="section-content">
          <p class="subcopy">
            Maintain the city and airport data used by the course project. Delete actions require confirmation first.
          </p>
          <div class="split">
            <div class="subpanel">
              <h3 class="section-head">Cities</h3>
              <div class="form-grid">
                <label>
                  City Code
                  <input v-model="cityForm.city_code" :readonly="!!editState.cityCode" />
                </label>
                <label>
                  City Name
                  <input v-model="cityForm.city_name" />
                </label>
              </div>
              <div class="action-row">
                <button @click="submitCity">{{ editState.cityCode ? "Save City" : "Create City" }}</button>
                <button v-if="editState.cityCode" class="secondary" @click="resetCityForm">Cancel Edit</button>
              </div>
              <ul class="stack-list compact scroll-list">
                <li v-if="!cities.length">
                  <span class="muted">No cities found.</span>
                </li>
                <li v-for="city in cities" :key="city.city_code">
                  <div>
                    <span>{{ city.city_code }} / {{ city.city_name }}</span>
                    <div v-if="city.blocked_reason" class="muted">{{ city.blocked_reason }}</div>
                  </div>
                  <div class="inline-actions">
                    <button class="ghost" :disabled="!city.can_edit" :title="city.blocked_reason || ''" @click="editCity(city)">Edit</button>
                    <button class="ghost danger-text" :disabled="!city.can_delete" :title="city.blocked_reason || ''" @click="deleteCity(city.city_code)">Delete</button>
                  </div>
                </li>
              </ul>
            </div>
            <div class="subpanel">
              <h3 class="section-head">Airports</h3>
              <div class="form-grid three">
                <label>
                  Airport Code
                  <input v-model="airportForm.airport_code" :readonly="!!editState.airportCode" />
                </label>
                <label>
                  Airport Name
                  <input v-model="airportForm.airport_name" />
                </label>
                <label>
                  City Code
                  <input v-model="airportForm.city_code" />
                </label>
              </div>
              <div class="action-row">
                <button @click="submitAirport">{{ editState.airportCode ? "Save Airport" : "Create Airport" }}</button>
                <button v-if="editState.airportCode" class="secondary" @click="resetAirportForm">Cancel Edit</button>
              </div>
              <ul class="stack-list compact scroll-list">
                <li v-if="!airports.length">
                  <span class="muted">No airports found.</span>
                </li>
                <li v-for="airport in airports" :key="airport.airport_code">
                  <div>
                    <span>{{ airport.airport_code }} / {{ airport.airport_name }} / {{ airport.city_code }}</span>
                    <div v-if="airport.blocked_reason" class="muted">{{ airport.blocked_reason }}</div>
                  </div>
                  <div class="inline-actions">
                    <button class="ghost" :disabled="!airport.can_edit" :title="airport.blocked_reason || ''" @click="editAirport(airport)">Edit</button>
                    <button class="ghost danger-text" :disabled="!airport.can_delete" :title="airport.blocked_reason || ''" @click="deleteAirport(airport.airport_code)">Delete</button>
                  </div>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      <section class="panel admin-section">
        <button class="section-toggle" @click="toggleAdminSection('resource')">
          <div>
            <span class="eyebrow">Admin Section</span>
            <h2>Airplanes, Routes, Templates, and Special Fares</h2>
          </div>
          <span>{{ adminSections.resource ? "Collapse" : "Expand" }}</span>
        </button>
        <div v-if="adminSections.resource" class="section-content">
          <p class="subcopy">
            Manage schedule templates and fixed-date special fares with compact lists that are easier to demo.
          </p>

          <div class="admin-grid">
            <div class="subpanel">
              <h3 class="section-head">Airplanes</h3>
              <div class="form-grid four">
                <label>
                  Airplane ID
                  <input v-model="airplaneForm.airplane_id" :readonly="!!editState.airplaneId" />
                </label>
                <label>
                  Aircraft Type
                  <input v-model="airplaneForm.aircraft_type" />
                </label>
                <label>
                  F Capacity
                  <input v-model="airplaneForm.f_class_capacity" type="number" min="0" />
                </label>
                <label>
                  Y Capacity
                  <input v-model="airplaneForm.y_class_capacity" type="number" min="0" />
                </label>
              </div>
              <div class="action-row">
                <button @click="submitAirplane">{{ editState.airplaneId ? "Save Airplane" : "Create Airplane" }}</button>
                <button v-if="editState.airplaneId" class="secondary" @click="resetAirplaneForm">Cancel Edit</button>
              </div>
              <ul class="stack-list compact scroll-list">
                <li v-if="!airplanes.length">
                  <span class="muted">No airplanes found.</span>
                </li>
                <li v-for="airplane in airplanes" :key="airplane.airplane_id">
                  <div>
                    <span>{{ airplane.airplane_id }} / {{ airplane.aircraft_type }} / F{{ airplane.f_class_capacity }} / Y{{ airplane.y_class_capacity }}</span>
                    <div v-if="airplane.blocked_reason" class="muted">{{ airplane.blocked_reason }}</div>
                  </div>
                  <div class="inline-actions">
                    <button class="ghost" :disabled="!airplane.can_edit" :title="airplane.blocked_reason || ''" @click="editAirplane(airplane)">Edit</button>
                    <button class="ghost danger-text" :disabled="!airplane.can_delete" :title="airplane.blocked_reason || ''" @click="deleteAirplane(airplane.airplane_id)">Delete</button>
                  </div>
                </li>
              </ul>
            </div>

            <div class="subpanel">
              <h3 class="section-head">Routes</h3>
              <div class="form-grid">
                <label>
                  Route ID
                  <input v-model="routeForm.route_id" :readonly="!!editState.routeId" />
                </label>
                <label>
                  Route Name
                  <input v-model="routeForm.route_name" />
                </label>
                <label class="full">
                  Segments JSON
                  <textarea v-model="routeForm.segments_text" rows="6"></textarea>
                </label>
                <label class="full">
                  Pricing JSON
                  <textarea v-model="routeForm.pricing_text" rows="5"></textarea>
                </label>
              </div>
              <div class="action-row">
                <button @click="submitRoute">{{ editState.routeId ? "Save Route" : "Create Route" }}</button>
                <button v-if="editState.routeId" class="secondary" @click="resetRouteForm">Cancel Edit</button>
              </div>
              <div class="table-shell scroll-list">
                <table>
                  <thead>
                    <tr>
                      <th>Route</th>
                      <th>Segment Summary</th>
                      <th>Pricing Summary</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-if="!routes.length">
                      <td colspan="4" class="muted">No routes found.</td>
                    </tr>
                    <tr v-for="route in routes" :key="route.route_id">
                      <td>
                        {{ route.route_id }} / {{ route.route_name }}
                        <div v-if="route.blocked_reason" class="muted">{{ route.blocked_reason }}</div>
                      </td>
                      <td>{{ routeSegmentsSummary(route) }}</td>
                      <td>{{ routePricingSummary(route) }}</td>
                      <td>
                        <div class="inline-actions">
                          <button class="ghost" :disabled="!route.can_edit" :title="route.blocked_reason || ''" @click="hydrateRouteForm(route)">Edit</button>
                          <button class="ghost danger-text" :disabled="!route.can_delete" :title="route.blocked_reason || ''" @click="deleteRoute(route.route_id)">Delete</button>
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div class="subpanel">
              <h3 class="section-head">Flight Templates</h3>
              <div class="form-grid four">
                <label>
                  Flight No
                  <input v-model="templateForm.flight_no" />
                </label>
                <label>
                  Route ID
                  <input v-model="templateForm.route_id" />
                </label>
                <label>
                  Default Airplane
                  <input v-model="templateForm.default_airplane_id" />
                </label>
                <label>
                  Default Discount
                  <input v-model="templateForm.default_flight_discount" type="number" step="0.01" min="0.01" max="1" />
                </label>
                <label>
                  Status
                  <select v-model="templateForm.status">
                    <option value="ACTIVE">ACTIVE</option>
                    <option value="INACTIVE">INACTIVE</option>
                  </select>
                </label>
                <label class="full">
                  Weekdays
                  <input v-model="templateForm.weekdays_csv" placeholder="1,3,5" />
                </label>
              </div>
              <div class="action-row">
                <button @click="submitTemplate">{{ editState.templateId ? "Save Template" : "Create Template" }}</button>
                <button v-if="editState.templateId" class="secondary" @click="resetTemplateForm">Cancel Edit</button>
              </div>
              <div class="table-shell scroll-list">
                <table>
                  <thead>
                    <tr>
                      <th>Template</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-if="!templates.length">
                      <td colspan="3" class="muted">No templates found.</td>
                    </tr>
                    <tr v-for="template in templates" :key="template.template_id">
                      <td>#{{ template.template_id }} / {{ template.flight_no }} / {{ template.route_id }} / {{ formatWeekdays(template.weekdays) }}</td>
                      <td>{{ formatOrderStatus(template.status) }}</td>
                      <td>
                        <div class="inline-actions">
                          <button class="ghost" @click="hydrateTemplateForm(template)">Edit</button>
                          <button class="ghost danger-text" @click="deleteTemplate(template.template_id)">Delete</button>
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div class="subpanel">
              <h3 class="section-head">Special Fare Plans</h3>
              <div class="form-grid three">
                <label>
                  Flight No
                  <input v-model="specialFareForm.flight_no" />
                </label>
                <label>
                  Date
                  <input v-model="specialFareForm.flight_date" type="date" />
                </label>
                <label>
                  Cabin
                  <select v-model="specialFareForm.cabin_class">
                    <option value="Y">Y</option>
                    <option value="F">F</option>
                  </select>
                </label>
                <label>
                  Start Segment
                  <input v-model="specialFareForm.start_segment_id" type="number" min="1" />
                </label>
                <label>
                  End Segment
                  <input v-model="specialFareForm.end_segment_id" type="number" min="1" />
                </label>
                <label>
                  Special Price
                  <input v-model="specialFareForm.special_price" type="number" min="1" step="1" />
                </label>
                <label>
                  Quota
                  <input v-model="specialFareForm.quota_total" type="number" min="1" />
                </label>
                <label>
                  Sale Start
                  <input v-model="specialFareForm.sale_start" type="datetime-local" />
                </label>
                <label>
                  Sale End
                  <input v-model="specialFareForm.sale_end" type="datetime-local" />
                </label>
              </div>
              <div class="action-row">
                <button @click="submitSpecialFare">{{ editState.specialFareId ? "Save Special Fare" : "Create Special Fare" }}</button>
                <button v-if="editState.specialFareId" class="secondary" @click="resetSpecialFareForm">Cancel Edit</button>
              </div>
              <div class="table-shell scroll-list">
                <table>
                  <thead>
                    <tr>
                      <th>Plan</th>
                      <th>Quota</th>
                      <th>Sale Window</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-if="!specialFares.length">
                      <td colspan="4" class="muted">No special-fare plans found.</td>
                    </tr>
                    <tr v-for="item in specialFares" :key="item.special_fare_id">
                      <td>#{{ item.special_fare_id }} / {{ item.flight_no }} / {{ item.flight_date }} / {{ item.cabin_class }} / {{ item.special_price }}</td>
                      <td>{{ item.quota_used }} / {{ item.quota_total }}</td>
                      <td>{{ formatSpecialFareWindow(item) }}</td>
                      <td>
                        <div class="inline-actions">
                          <button class="ghost" @click="hydrateSpecialFareForm(item)">Edit</button>
                          <button class="ghost danger-text" @click="deleteSpecialFare(item.special_fare_id)">Delete</button>
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section class="panel admin-section">
        <button class="section-toggle" @click="toggleAdminSection('orders')">
          <div>
            <span class="eyebrow">Admin Section</span>
            <h2>All Orders</h2>
          </div>
          <span>{{ adminSections.orders ? "Collapse" : "Expand" }}</span>
        </button>
        <div v-if="adminSections.orders" class="section-content">
          <p class="subcopy">
            Orders and payment records stay masked so the demo can explain privacy protection clearly.
          </p>
          <div class="table-shell scroll-list tall">
            <table>
              <thead>
                <tr>
                  <th>Order</th>
                  <th>Passenger</th>
                  <th>Flight</th>
                  <th>Order Status</th>
                  <th>Payment Status</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="!adminOrders.length">
                  <td colspan="5" class="muted">No orders found.</td>
                </tr>
                <tr v-for="order in adminOrders" :key="order.ticket_no">
                  <td>
                    <strong>{{ order.ticket_no }}</strong>
                    <div class="muted">{{ formatPriceSource(order.price_source) }}</div>
                  </td>
                  <td>{{ order.passenger_name_masked }} / {{ order.passenger_id_card_masked }}</td>
                  <td>{{ order.flight_no }} / {{ order.flight_date }}</td>
                  <td>{{ formatOrderStatus(order.status) }}</td>
                  <td>{{ formatPaymentStatus(order.payment_status) }} / {{ order.payer_account_masked || "-" }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section class="panel admin-section">
        <button class="section-toggle" @click="toggleAdminSection('audits')">
          <div>
            <span class="eyebrow">Admin Section</span>
            <h2>Audit Logs</h2>
          </div>
          <span>{{ adminSections.audits ? "Collapse" : "Expand" }}</span>
        </button>
        <div v-if="adminSections.audits" class="section-content">
          <p class="subcopy">Keep key operations for auditing without writing raw sensitive values.</p>
          <ul class="stack-list audit-list">
            <li v-if="!audits.length">
              <span class="muted">No audit logs found.</span>
            </li>
            <li v-for="audit in audits" :key="audit.audit_id">
              <strong>{{ audit.action }}</strong>
              <span>{{ formatTimestamp(audit.created_at) }}</span>
              <span>{{ audit.entity_type }} / {{ audit.entity_id }}</span>
              <small>Actor: {{ audit.actor_account_id ?? "-" }}</small>
              <small>{{ audit.detail }}</small>
            </li>
          </ul>
        </div>
      </section>
    </template>
  </div>
</template>

