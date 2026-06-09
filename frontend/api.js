/**
 * EduPortal — API Client
 * localStorage o'rniga real FastAPI backend bilan ishlaydi
 * 
 * Ishlatish: <script src="api.js"></script>
 * Keyin: const user = await API.login("admin","admin123")
 */

const API_BASE = "https://nedu-beta.vercel.app/api";

// ─── Token boshqaruvi ───────────────────────────────────────
const Auth = {
  getToken:    ()    => localStorage.getItem("edu_token"),
  setToken:    (t)   => localStorage.setItem("edu_token", t),
  removeToken: ()    => localStorage.removeItem("edu_token"),
  getUser:     ()    => JSON.parse(localStorage.getItem("edu_user") || "null"),
  setUser:     (u)   => localStorage.setItem("edu_user", JSON.stringify(u)),
  removeUser:  ()    => localStorage.removeItem("edu_user"),
  clear:       ()    => { Auth.removeToken(); Auth.removeUser(); },
};

// ─── HTTP helper ────────────────────────────────────────────
async function http(method, path, body = null, isForm = false) {
  const headers = {};
  const token = Auth.getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let bodyData = null;
  if (body) {
    if (isForm) {
      bodyData = body; // FormData
    } else {
      headers["Content-Type"] = "application/json";
      bodyData = JSON.stringify(body);
    }
  }

  const resp = await fetch(`${API_BASE}${path}`, { method, headers, body: bodyData });

  if (resp.status === 204) return null;

  const data = await resp.json().catch(() => ({}));

  if (!resp.ok) {
    const msg = data?.detail || `Xato ${resp.status}`;
    throw new Error(Array.isArray(msg) ? msg.map(e => e.msg).join("; ") : msg);
  }
  return data;
}

const get    = (path)        => http("GET",    path);
const post   = (path, body)  => http("POST",   path, body);
const patch  = (path, body)  => http("PATCH",  path, body);
const del    = (path)        => http("DELETE", path);
const postF  = (path, form)  => http("POST",   path, form, true);
const patchF = (path, form)  => http("PATCH",  path, form, true);


// ─── API namespace ──────────────────────────────────────────
const API = {

  // ── AUTH ───────────────────────────────────────────────────
  async login(login, password) {
    const data = await post("/auth/login", { login, password });
    Auth.setToken(data.access_token);
    Auth.setUser(data.user);
    return data.user;
  },

  logout() {
    Auth.clear();
  },

  async me() {
    return get("/auth/me");
  },

  // ── USERS ──────────────────────────────────────────────────
  users: {
    list:   (params = {}) => get("/users/?" + new URLSearchParams(params)),
    get:    (id)          => get(`/users/${id}`),
    create: (body)        => post("/users/", body),
    update: (id, body)    => patch(`/users/${id}`, body),
    delete: (id)          => del(`/users/${id}`),
    stats:  ()            => get("/users/stats"),

    /** Excel import — [{fname,lname,login,password,role,...}] */
    bulk:   (users)       => post("/users/bulk", { users }),
  },

  // ── GROUPS ─────────────────────────────────────────────────
  groups: {
    list:   ()             => get("/groups/"),
    get:    (id)           => get(`/groups/${id}`),
    create: (body)         => post("/groups/", body),
    update: (id, body)     => patch(`/groups/${id}`, body),
    delete: (id)           => del(`/groups/${id}`),
  },

  // ── ASSIGNMENTS ────────────────────────────────────────────
  assignments: {
    list: () => get("/assignments/"),
    get:  (id) => get(`/assignments/${id}`),

    /** Yangi topshiriq — fayl bilan yoki faylsiz */
    create(data, file = null) {
      const form = new FormData();
      form.append("title",       data.title);
      form.append("subject",     data.subject);
      form.append("description", data.description);
      form.append("max_score",   data.max_score ?? 100);
      form.append("due_date",    data.due_date);
      form.append("group_id",    data.group_id);
      if (file) form.append("file", file);
      return postF("/assignments/", form);
    },

    delete: (id) => del(`/assignments/${id}`),
  },

  // ── SUBMISSIONS ────────────────────────────────────────────
  submissions: {
    list: (params = {}) => get("/submissions/?" + new URLSearchParams(params)),
    get:  (id)          => get(`/submissions/${id}`),

    /** Talaba ishi yuboradi — fayl majburiy */
    submit(assignmentId, file, comment = "") {
      const form = new FormData();
      form.append("assignment_id", assignmentId);
      form.append("comment",       comment);
      form.append("file",          file);
      return postF("/submissions/", form);
    },

    /** O'qituvchi baholaydi */
    grade: (id, body) => patch(`/submissions/${id}/grade`, body),
  },
};

// ─── Eksport ────────────────────────────────────────────────
window.API  = API;
window.Auth = Auth;
