/* LawPlanet - API helper
   Small wrapper around fetch() that attaches the auth token and
   parses JSON responses consistently across all pages. */

const API_BASE = ""; // same origin (Flask serves both frontend and API)

const Auth = {
  getToken() { return localStorage.getItem("lp_token"); },
  setToken(token) { localStorage.setItem("lp_token", token); },
  clearToken() { localStorage.removeItem("lp_token"); },
  getUser() {
    const raw = localStorage.getItem("lp_user");
    return raw ? JSON.parse(raw) : null;
  },
  setUser(user) { localStorage.setItem("lp_user", JSON.stringify(user)); },
  clearUser() { localStorage.removeItem("lp_user"); },
  isLoggedIn() { return !!this.getToken(); },
  logout() {
    this.clearToken();
    this.clearUser();
    window.location.href = "/index.html";
  },
};

async function api(path, { method = "GET", body = null, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth && Auth.getToken()) {
    headers["Authorization"] = `Bearer ${Auth.getToken()}`;
  }
  let response;
  try {
    response = await fetch(API_BASE + path, {
      method,
      headers,
      body: body ? JSON.stringify(body) : null,
    });
  } catch (err) {
    throw new Error("Could not reach the server. Please check that the backend is running.");
  }

  let data = null;
  try {
    data = await response.json();
  } catch (e) {
    data = null;
  }

  if (response.status === 401) {
    Auth.clearToken();
    Auth.clearUser();
    if (!window.location.pathname.endsWith("index.html") && window.location.pathname !== "/") {
      window.location.href = "/index.html";
    }
  }

  if (!response.ok) {
    const message = (data && data.error) || `Request failed (${response.status})`;
    throw new Error(message);
  }
  return data;
}

/* Guard helper: pages that require login call this at the top */
function requireAuth(requiredRole = null) {
  if (!Auth.isLoggedIn()) {
    window.location.href = "/index.html";
    return null;
  }
  const user = Auth.getUser();
  if (requiredRole && user.role !== requiredRole) {
    window.location.href = user.role === "lawyer" ? "/dashboard-lawyer.html" : "/dashboard-client.html";
    return null;
  }
  return user;
}

function timeAgo(isoString) {
  if (!isoString) return "";
  const then = new Date(isoString + (isoString.endsWith("Z") ? "" : "Z"));
  const diffMs = Date.now() - then.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return then.toLocaleDateString();
}

function formatTime(isoString) {
  const d = new Date(isoString + (isoString.endsWith("Z") ? "" : "Z"));
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function initials(name) {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  return (parts[0][0] + (parts[1] ? parts[1][0] : "")).toUpperCase();
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str == null ? "" : str;
  return div.innerHTML;
}
