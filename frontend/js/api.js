/**
 * Backend API client.
 * All requests to the Python FastAPI backend go through this module.
 *
 * EXTENSION POINT: add endpoints for saving/retrieving user favourites
 *   (e.g., POST /favourites, GET /favourites) once a user-account system exists.
 */
const API = {
  async search(query, latitude, longitude, use_google = false) {
    const token = Auth.getToken();
    if (!token) throw new Error("尚未登入");

    const res = await fetch(`${CONFIG.BACKEND_URL}/search`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`,
      },
      body: JSON.stringify({ query, latitude, longitude, use_google }),
    });

    if (res.status === 401) {
      Auth.logout();
      throw new Error("登入已過期，請重新登入");
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      const detail = body.detail || {};
      const error = new Error(
        typeof detail === "string" ? detail : detail.message || `搜尋失敗 (HTTP ${res.status})`
      );
      error.parsedQuery = typeof detail === "object" ? detail.parsed_query : null;
      throw error;
    }

    return res.json();
  },

  async getFavourites() {
    const token = Auth.getToken();
    if (!token) return [];
    const res = await fetch(`${CONFIG.BACKEND_URL}/favourites`, {
      headers: { "Authorization": `Bearer ${token}` },
    });
    return res.ok ? res.json() : [];
  },

  async addFavourite(restaurant) {
    const token = Auth.getToken();
    const res = await fetch(`${CONFIG.BACKEND_URL}/favourites`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
      body: JSON.stringify(restaurant),
    });
    return res.ok ? res.json() : null;
  },

  async getFavouritesMap(lat, lon, favId = null) {
    const token = Auth.getToken();
    let url = `${CONFIG.BACKEND_URL}/favourites/map?lat=${lat}&lon=${lon}`;
    if (favId) url += `&fav_id=${encodeURIComponent(favId)}`;
    const res = await fetch(url, { headers: { "Authorization": `Bearer ${token}` } });
    return res.ok ? res.json() : null;
  },

  async spin() {
    const token = Auth.getToken();
    if (!token) throw new Error("尚未登入");
    const res = await fetch(`${CONFIG.BACKEND_URL}/spin`, {
      headers: { "Authorization": `Bearer ${token}` },
    });
    if (!res.ok) throw new Error("無法連線");
    return res.json();
  },

  async removeFavourite(restaurantId) {
    const token = Auth.getToken();
    const res = await fetch(`${CONFIG.BACKEND_URL}/favourites/${encodeURIComponent(restaurantId)}`, {
      method: "DELETE",
      headers: { "Authorization": `Bearer ${token}` },
    });
    return res.ok ? res.json() : null;
  },
};
