/**
 * JWT authentication module.
 * Stores the access token in sessionStorage (cleared when tab closes).
 *
 * EXTENSION POINT: replace with a persistent user session that stores
 *   a user ID, enabling favourite restaurants and personalised results.
 */
const Auth = {
  TOKEN_KEY: "rf_access_token",

  async login(username, password) {
    const form = new URLSearchParams();
    form.append("username", username);
    form.append("password", password);

    const res = await fetch(`${CONFIG.BACKEND_URL}/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "登入失敗，請檢查帳號密碼");
    }

    const data = await res.json();
    sessionStorage.setItem(this.TOKEN_KEY, data.access_token);
    return true;
  },

  async register(username, password) {
    const res = await fetch(`${CONFIG.BACKEND_URL}/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "註冊失敗，請稍後再試");
    }
    return await res.json();
  },

  logout() {
    sessionStorage.removeItem(this.TOKEN_KEY);
  },

  getToken() {
    return sessionStorage.getItem(this.TOKEN_KEY);
  },

  isLoggedIn() {
    const token = this.getToken();
    if (!token) return false;
    try {
      // Decode JWT payload (base64url) and check expiry client-side (UX only).
      // The server is the authoritative validator.
      const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
      return payload.exp * 1000 > Date.now();
    } catch {
      return false;
    }
  },
};
