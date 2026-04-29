const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

function parseResponseBody(text) {
  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function formatErrorMessage(data) {
  if (Array.isArray(data?.detail)) {
    return data.detail
      .map((item) => {
        const path = Array.isArray(item.loc)
          ? item.loc.filter((part) => part !== "body").join(".")
          : "";
        return path ? `${path}: ${item.msg}` : item.msg;
      })
      .join("；");
  }

  if (typeof data?.detail === "string") {
    return data.detail;
  }

  if (typeof data === "string" && data.trim()) {
    return data.trim();
  }

  return "请求失败";
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
      ...(options.headers || {})
    },
    method: options.method || "GET",
    body: options.body ? JSON.stringify(options.body) : undefined
  });

  if (response.status === 204) {
    return null;
  }

  const text = await response.text();
  const data = parseResponseBody(text);

  if (!response.ok) {
    throw new Error(formatErrorMessage(data));
  }

  return data;
}

function buildSearchParams(params) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && `${value}` !== "") {
      search.set(key, value);
    }
  });
  return search.toString();
}

export function createInventoryEventSource(token) {
  const search = new URLSearchParams({ access_token: token });
  return new EventSource(`${API_BASE_URL}/flights/stream/inventory?${search.toString()}`);
}

export const api = {
  login(login_identifier, password) {
    return request("/auth/login", {
      method: "POST",
      body: { login_identifier, password }
    });
  },
  me(token) {
    return request("/auth/me", { token });
  },
  meSensitive(token) {
    return request("/auth/me/sensitive", { token });
  },
  listReferenceCities() {
    return request("/reference/cities");
  },
  searchFlights(token, params) {
    return request(`/flights/search?${buildSearchParams(params)}`, { token });
  },
  searchFlightsRange(token, params) {
    return request(`/flights/search/range?${buildSearchParams(params)}`, { token });
  },
  purchaseTicket(token, payload) {
    return request("/tickets/purchase", {
      method: "POST",
      token,
      body: payload
    });
  },
  confirmPayment(token, paymentId, payload) {
    return request(`/payments/${paymentId}/confirm`, {
      method: "POST",
      token,
      body: payload
    });
  },
  refundTicket(token, ticketNo) {
    return request(`/tickets/${ticketNo}/refund`, {
      method: "POST",
      token
    });
  },
  cancelPendingTicket(token, ticketNo) {
    return request(`/tickets/${ticketNo}/cancel`, {
      method: "POST",
      token
    });
  },
  listMyOrders(token) {
    return request("/me/orders", { token });
  },
  listMyWaitlists(token) {
    return request("/me/waitlists", { token });
  },
  createWaitlist(token, payload) {
    return request("/waitlists", {
      method: "POST",
      token,
      body: payload
    });
  },
  listCities(token) {
    return request("/admin/cities", { token });
  },
  createCity(token, payload) {
    return request("/admin/cities", {
      method: "POST",
      token,
      body: payload
    });
  },
  updateCity(token, cityCode, payload) {
    return request(`/admin/cities/${cityCode}`, {
      method: "PUT",
      token,
      body: payload
    });
  },
  deleteCity(token, cityCode) {
    return request(`/admin/cities/${cityCode}`, {
      method: "DELETE",
      token
    });
  },
  listAirports(token) {
    return request("/admin/airports", { token });
  },
  createAirport(token, payload) {
    return request("/admin/airports", {
      method: "POST",
      token,
      body: payload
    });
  },
  updateAirport(token, airportCode, payload) {
    return request(`/admin/airports/${airportCode}`, {
      method: "PUT",
      token,
      body: payload
    });
  },
  deleteAirport(token, airportCode) {
    return request(`/admin/airports/${airportCode}`, {
      method: "DELETE",
      token
    });
  },
  listAirplanes(token) {
    return request("/admin/airplanes", { token });
  },
  createAirplane(token, payload) {
    return request("/admin/airplanes", {
      method: "POST",
      token,
      body: payload
    });
  },
  updateAirplane(token, airplaneId, payload) {
    return request(`/admin/airplanes/${airplaneId}`, {
      method: "PUT",
      token,
      body: payload
    });
  },
  deleteAirplane(token, airplaneId) {
    return request(`/admin/airplanes/${airplaneId}`, {
      method: "DELETE",
      token
    });
  },
  listRoutes(token) {
    return request("/admin/routes", { token });
  },
  createRoute(token, payload) {
    return request("/admin/routes", {
      method: "POST",
      token,
      body: payload
    });
  },
  updateRoute(token, routeId, payload) {
    return request(`/admin/routes/${routeId}`, {
      method: "PUT",
      token,
      body: payload
    });
  },
  deleteRoute(token, routeId) {
    return request(`/admin/routes/${routeId}`, {
      method: "DELETE",
      token
    });
  },
  listTemplates(token) {
    return request("/admin/flight-templates", { token });
  },
  createTemplate(token, payload) {
    return request("/admin/flight-templates", {
      method: "POST",
      token,
      body: payload
    });
  },
  updateTemplate(token, templateId, payload) {
    return request(`/admin/flight-templates/${templateId}`, {
      method: "PUT",
      token,
      body: payload
    });
  },
  deleteTemplate(token, templateId) {
    return request(`/admin/flight-templates/${templateId}`, {
      method: "DELETE",
      token
    });
  },
  listSpecialFares(token) {
    return request("/admin/special-fares", { token });
  },
  createSpecialFare(token, payload) {
    return request("/admin/special-fares", {
      method: "POST",
      token,
      body: payload
    });
  },
  updateSpecialFare(token, specialFareId, payload) {
    return request(`/admin/special-fares/${specialFareId}`, {
      method: "PUT",
      token,
      body: payload
    });
  },
  deleteSpecialFare(token, specialFareId) {
    return request(`/admin/special-fares/${specialFareId}`, {
      method: "DELETE",
      token
    });
  },
  generateSchedules(token, payload) {
    return request("/admin/schedules/generate", {
      method: "POST",
      token,
      body: payload
    });
  },
  cancelSchedule(token, flightNo, flightDate) {
    return request(`/admin/schedules/${flightNo}/${flightDate}/cancel`, {
      method: "POST",
      token
    });
  },
  listAdminOrders(token) {
    return request("/admin/orders", { token });
  },
  listAudits(token) {
    return request("/admin/audits", { token });
  }
};
