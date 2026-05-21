/**
 * Main application — fullscreen map + floating chat interface.
 *
 * Flow after login:
 *   1. Get user location → call GET /basemap → inject fullscreen Folium map
 *   2. Show floating chat button
 *   3. User opens chat → types query → POST /search
 *   4. Verify RSA signature → update map + show results in chat
 */

const App = {
  _lat: null,
  _lon: null,
  _useGoogle: false,
  _favourites: [],   // list of favourite dicts loaded from server

  init() {
    this._bindAuth();
    if (Auth.isLoggedIn()) {
      this._onLoginSuccess();
    }
  },

  // ── Auth ──────────────────────────────────────────────────────────────────

  _bindAuth() {
    document.getElementById("login-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const errEl = document.getElementById("login-error");
      errEl.textContent = "";
      try {
        await Auth.login(
          document.getElementById("username").value.trim(),
          document.getElementById("password").value
        );
        this._onLoginSuccess();
      } catch (err) {
        errEl.textContent = err.message;
      }
    });

    document.getElementById("logout-btn").addEventListener("click", () => {
      Auth.logout();
      location.reload();
    });

    // Toggle to register panel
    document.getElementById("show-register").addEventListener("click", (e) => {
      e.preventDefault();
      document.getElementById("login-panel").style.display    = "none";
      document.getElementById("register-panel").style.display = "block";
      document.getElementById("login-error").textContent      = "";
    });

    // Toggle back to login panel
    document.getElementById("show-login").addEventListener("click", (e) => {
      e.preventDefault();
      document.getElementById("register-panel").style.display = "none";
      document.getElementById("login-panel").style.display    = "block";
      document.getElementById("register-error").textContent   = "";
      document.getElementById("register-success").style.display = "none";
    });

    // Register form submit
    document.getElementById("register-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const errEl     = document.getElementById("register-error");
      const successEl = document.getElementById("register-success");
      errEl.textContent = "";
      successEl.style.display = "none";

      const username = document.getElementById("reg-username").value.trim();
      const password = document.getElementById("reg-password").value;
      const confirm  = document.getElementById("reg-confirm").value;

      if (password !== confirm) {
        errEl.textContent = "兩次密碼不一致";
        return;
      }
      try {
        await Auth.register(username, password);
        successEl.textContent  = `帳號「${username}」建立成功！正在登入…`;
        successEl.style.display = "block";
        await Auth.login(username, password);
        this._onLoginSuccess();
      } catch (err) {
        errEl.textContent = err.message;
      }
    });
  },

  _onLoginSuccess() {
    document.getElementById("login-overlay").style.display  = "none";
    document.getElementById("logout-btn").style.display     = "inline-flex";
    document.getElementById("chat-toggle").style.display    = "flex";
    document.getElementById("spin-btn").style.display       = "flex";
    document.getElementById("relocate-btn").style.display   = "inline-flex";
    document.getElementById("location-display").style.display = "inline";
    this._bindRelocate();
    this._bindChat();
    this._bindSpinBtn();
    this._bindFavSidebar();
    this._bindAdminBtn();
    this._loadLocation();
    this._loadFavourites();
  },

  // ── Admin users panel ─────────────────────────────────────────────────────

  _bindAdminBtn() {
    const btn     = document.getElementById("admin-btn");
    const overlay = document.getElementById("admin-overlay");
    const closeBtn = document.getElementById("admin-close");

    // Only show admin button for the demo/admin account
    const token = Auth.getToken();
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g,"+").replace(/_/g,"/")));
        if (payload.sub === "demo") btn.style.display = "inline-flex";
      } catch {}
    }

    btn.addEventListener("click", async () => {
      overlay.style.display = "flex";
      const body = document.getElementById("admin-body");
      body.innerHTML = '<div class="spinner" style="margin:1.5rem auto"></div>';
      try {
        const res = await fetch(`${CONFIG.BACKEND_URL}/admin/users`, {
          headers: { "Authorization": `Bearer ${Auth.getToken()}` },
        });
        if (!res.ok) throw new Error((await res.json()).detail || "存取失敗");
        const users = await res.json();
        if (!users.length) {
          body.innerHTML = '<p class="admin-empty">尚無已註冊用戶</p>';
          return;
        }
        body.innerHTML = users.map(u => {
          const initial = u.username.charAt(0).toUpperCase();
          const date = new Date(u.created_at).toLocaleString("zh-TW", {
            year:"numeric", month:"2-digit", day:"2-digit",
            hour:"2-digit", minute:"2-digit",
          });
          return `<div class="admin-user-row">
            <div class="admin-avatar">${initial}</div>
            <span class="admin-username">${u.username}</span>
            <span class="admin-date">${date}</span>
          </div>`;
        }).join("");
      } catch (err) {
        body.innerHTML = `<p class="admin-empty" style="color:#e74c3c">${err.message}</p>`;
      }
    });

    closeBtn.addEventListener("click", () => overlay.style.display = "none");
    overlay.addEventListener("click", (e) => { if (e.target === overlay) overlay.style.display = "none"; });
  },

  // ── Location + base map ───────────────────────────────────────────────────

  _bindRelocate() {
    const row        = document.getElementById("location-input-row");
    const btn        = document.getElementById("relocate-btn");
    const input      = document.getElementById("location-input");
    const searchBtn  = document.getElementById("location-search-btn");
    const gpsBtn     = document.getElementById("location-gps-btn");
    const cancelBtn  = document.getElementById("location-cancel-btn");

    btn.addEventListener("click", () => {
      row.style.display = "flex";
      btn.style.display = "none";
      input.focus();
    });

    cancelBtn.addEventListener("click", () => {
      row.style.display = "none";
      btn.style.display = "inline-flex";
    });

    gpsBtn.addEventListener("click", () => {
      row.style.display = "none";
      btn.style.display = "inline-flex";
      document.getElementById("location-display").textContent = "定位中…";
      this._loadLocation();
    });

    const doSearch = async () => {
      const q = input.value.trim();
      if (!q) return;
      searchBtn.disabled = true;
      searchBtn.textContent = "…";
      const result = await this._geocodeAddress(q);
      searchBtn.disabled = false;
      searchBtn.textContent = "搜尋";
      if (result) {
        input.value = "";
        row.style.display = "none";
        btn.style.display = "inline-flex";
        this._setLocation(result.lat, result.lon, result.name);
      } else {
        input.style.borderColor = "red";
        setTimeout(() => input.style.borderColor = "", 1500);
      }
    };

    searchBtn.addEventListener("click", doSearch);
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") doSearch(); });
  },

  async _geocodeAddress(query) {
    try {
      const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(query)}&format=jsonv2&limit=1&addressdetails=1`;
      const res = await fetch(url, { headers: { "Accept-Language": "zh-TW,zh" } });
      const data = await res.json();
      if (!data.length) return null;
      const place = data[0];
      const addr  = place.address || {};
      const name  = addr.road || addr.suburb || addr.city || place.display_name.split(",")[0];
      return { lat: parseFloat(place.lat), lon: parseFloat(place.lon), name };
    } catch {
      return null;
    }
  },

  _setLocation(lat, lon, label) {
    this._lat = lat;
    this._lon = lon;
    document.getElementById("location-display").textContent =
      label ? `📍 ${label}` : `${lat.toFixed(4)}, ${lon.toFixed(4)}`;
    this._loadBasemap(lat, lon);
  },

  _loadLocation() {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => this._setLocation(pos.coords.latitude, pos.coords.longitude),
        ()    => this._setLocation(CONFIG.DEFAULT_LAT, CONFIG.DEFAULT_LON)
      );
    } else {
      this._setLocation(CONFIG.DEFAULT_LAT, CONFIG.DEFAULT_LON);
    }
  },

  async _loadBasemap(lat, lon) {
    try {
      const token = Auth.getToken();
      const res = await fetch(
        `${CONFIG.BACKEND_URL}/basemap?lat=${lat}&lon=${lon}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!res.ok) return;
      const data = await res.json();
      this._injectMap(data.map_html);
    } catch {
      // silently fall through — map placeholder stays visible
    }
  },

  _injectMap(html) {
    const container = document.getElementById("map-container");
    container.innerHTML = html;
  },

  // ── Favourites sidebar ────────────────────────────────────────────────────

  _favOpen: false,

  _bindFavSidebar() {
    document.getElementById("fav-sidebar").style.display = "block";
    document.getElementById("fav-tab").addEventListener("click", () => this._toggleFavSidebar());
    document.getElementById("fav-show-all-btn").addEventListener("click", async () => {
      const data = await API.getFavouritesMap(
        this._lat ?? CONFIG.DEFAULT_LAT,
        this._lon ?? CONFIG.DEFAULT_LON
      );
      if (data) this._injectMap(data.map_html);
    });
  },

  _toggleFavSidebar() {
    this._favOpen = !this._favOpen;
    document.getElementById("fav-sidebar").classList.toggle("open", this._favOpen);
  },

  async _loadFavourites() {
    this._favourites = await API.getFavourites() || [];
    this._renderFavList();
  },

  _renderFavList() {
    const list = document.getElementById("fav-list");
    if (!this._favourites.length) {
      list.innerHTML = `<div class="fav-empty">尚無最愛餐廳<br>搜尋後點擊 🤍 加入</div>`;
      return;
    }
    list.innerHTML = "";
    this._favourites.forEach(f => {
      const card = document.createElement("div");
      card.className = "fav-card";
      card.innerHTML = `
        <div class="fav-card-name">${this._esc(f.name)}</div>
        <div class="fav-card-addr">📍 ${this._esc(f.address || "")}</div>
        <div class="fav-card-btns">
          <button class="btn-show" data-id="${this._esc(f.id)}">🗺 顯示地圖</button>
          <button class="btn-remove" data-id="${this._esc(f.id)}">🗑 移除</button>
        </div>`;
      card.querySelector(".btn-show").addEventListener("click", async () => {
        const data = await API.getFavouritesMap(
          this._lat ?? CONFIG.DEFAULT_LAT,
          this._lon ?? CONFIG.DEFAULT_LON,
          f.id
        );
        if (data) this._injectMap(data.map_html);
      });
      card.querySelector(".btn-remove").addEventListener("click", async () => {
        await API.removeFavourite(f.id);
        this._favourites = this._favourites.filter(x => x.id !== f.id);
        this._renderFavList();
      });
      list.appendChild(card);
    });
  },

  _isFavourite(id) {
    return this._favourites.some(f => f.id === id);
  },

  async _toggleFavourite(restaurant, btnEl) {
    if (this._isFavourite(restaurant.id)) {
      await API.removeFavourite(restaurant.id);
      this._favourites = this._favourites.filter(f => f.id !== restaurant.id);
      btnEl.textContent = "🤍";
      btnEl.title = "加入最愛";
    } else {
      await API.addFavourite(restaurant);
      this._favourites.push(restaurant);
      btnEl.textContent = "❤️";
      btnEl.title = "移除最愛";
    }
    this._renderFavList();
  },

  // ── Chat ──────────────────────────────────────────────────────────────────

  _chatOpen: false,

  // ── Spin wheel ────────────────────────────────────────────────────────────

  _spinResult: null,

  _bindSpinBtn() {
    document.getElementById("spin-btn").addEventListener("click", () => this._openSpin());
    document.getElementById("spin-cancel-btn").addEventListener("click", () => this._closeSpin());
    document.getElementById("spin-again-btn").addEventListener("click", () => this._startSpin());
    document.getElementById("spin-confirm-btn").addEventListener("click", () => {
      if (!this._spinResult) return;
      this._closeSpin();
      if (!this._chatOpen) this._openChat();
      document.getElementById("chat-input").value = this._spinResult.query;
      this._handleMessage(this._spinResult.query);
    });
  },

  _openSpin() {
    document.getElementById("spin-overlay").style.display = "flex";
    this._startSpin();
  },

  _closeSpin() {
    document.getElementById("spin-overlay").style.display = "none";
  },

  async _startSpin() {
    const slot     = document.getElementById("spin-slot");
    const emojiEl  = document.getElementById("spin-emoji");
    const labelEl  = document.getElementById("spin-label");
    const resultEl = document.getElementById("spin-result");

    resultEl.style.display = "none";
    slot.classList.add("spinning");
    this._spinResult = null;

    // All display options for the animation loop
    const display = [
      {emoji:"🍜",label:"拉麵"}, {emoji:"🍣",label:"壽司"}, {emoji:"🫕",label:"火鍋"},
      {emoji:"🍗",label:"炸雞"}, {emoji:"🥩",label:"牛排"}, {emoji:"🍔",label:"漢堡"},
      {emoji:"🍕",label:"披薩"}, {emoji:"🍰",label:"甜點"}, {emoji:"☕",label:"咖啡廳"},
      {emoji:"🥘",label:"韓式"}, {emoji:"🍱",label:"便當"}, {emoji:"🥞",label:"早午餐"},
      {emoji:"🧋",label:"奶茶"}, {emoji:"🍝",label:"義大利麵"},{emoji:"🔥",label:"烤肉"},
      {emoji:"🥟",label:"鍋貼"},
    ];

    // Fire Python API call immediately
    const apiPromise = API.spin();

    // Animation: cycle fast then slow
    let idx = 0, interval = 80, timer = null;
    const MIN_SPIN_MS = 2000;
    const startTime   = Date.now();
    let apiDone = false, apiData = null;

    const tick = () => {
      idx = (idx + 1) % display.length;
      emojiEl.textContent = display[idx].emoji;
      labelEl.textContent = display[idx].label;

      // Slow down after MIN_SPIN_MS
      const elapsed = Date.now() - startTime;
      if (elapsed > MIN_SPIN_MS && apiDone) {
        interval = Math.min(interval + 40, 350);
      }

      // Stop when slow enough and API is done
      if (interval >= 350 && apiDone) {
        clearTimeout(timer);
        slot.classList.remove("spinning");
        emojiEl.textContent = apiData.emoji;
        labelEl.textContent = apiData.label;
        this._spinResult = apiData;
        resultEl.style.display = "flex";
        return;
      }
      timer = setTimeout(tick, interval);
    };
    timer = setTimeout(tick, interval);

    try {
      apiData = await apiPromise;
      apiDone = true;
    } catch {
      clearTimeout(timer);
      slot.classList.remove("spinning");
      labelEl.textContent = "連線失敗";
    }
  },

  _bindChat() {
    document.getElementById("chat-toggle").addEventListener("click", () => {
      this._toggleChat();
    });
    document.getElementById("chat-close").addEventListener("click", () => {
      this._closeChat();
    });
    document.getElementById("api-toggle").addEventListener("click", () => {
      this._useGoogle = !this._useGoogle;
      const btn   = document.getElementById("api-toggle");
      const label = document.getElementById("api-toggle-label");
      if (this._useGoogle) {
        label.textContent = "🔍 Google";
        btn.classList.add("google-active");
      } else {
        label.textContent = "🗺 Nominatim";
        btn.classList.remove("google-active");
      }
    });
    document.getElementById("chat-form").addEventListener("submit", (e) => {
      e.preventDefault();
      const input = document.getElementById("chat-input");
      const text  = input.value.trim();
      if (!text) return;
      input.value = "";
      this._handleMessage(text);
    });
  },

  _toggleChat() {
    this._chatOpen ? this._closeChat() : this._openChat();
  },

  _openChat() {
    this._chatOpen = true;
    document.body.classList.add("chat-open");
    document.getElementById("chat-panel").style.display  = "flex";
    document.getElementById("chat-toggle").classList.add("open");
    document.getElementById("chat-toggle-icon").textContent = "✕";
    document.getElementById("chat-input").focus();
  },

  _closeChat() {
    this._chatOpen = false;
    document.body.classList.remove("chat-open");
    document.getElementById("chat-panel").style.display    = "none";
    document.getElementById("chat-toggle").classList.remove("open");
    document.getElementById("chat-toggle-icon").textContent = "💬";
  },

  // ── Messaging ─────────────────────────────────────────────────────────────

  _addMsg(role, html) {
    const el = document.createElement("div");
    el.className = `msg ${role}`;
    el.innerHTML = `<span class="msg-bubble">${html}</span>`;
    document.getElementById("chat-messages").appendChild(el);
    el.scrollIntoView({ behavior: "smooth", block: "end" });
    return el;
  },

  _addTyping() {
    return this._addMsg("bot typing", "");
  },

  async _handleMessage(text) {
    this._addMsg("user", this._esc(text));
    const typingEl = this._addTyping();

    try {
      const data = await API.search(
        text,
        this._lat ?? CONFIG.DEFAULT_LAT,
        this._lon ?? CONFIG.DEFAULT_LON,
        this._useGoogle
      );

      typingEl.remove();

      // Verify signature
      const isValid = await SignatureVerifier.verify(data.signed_data, data.signature);
      this._showSignatureBadge(isValid, data.signature.slice(0, 20));

      if (!isValid) {
        this._addMsg("bot", "⚠️ 數位簽章驗證失敗，資料可能遭竄改，已拒絕顯示。");
        return;
      }

      // Update map
      this._injectMap(data.map_html);

      const pq = data.parsed_query;
      const searchTerm = pq.raw_keyword || pq.food;
      const searchTag = `<span class="nlp-tag">🔍 搜尋：${this._esc(searchTerm)} ｜ 步行 ${pq.time} 分鐘內</span>`;

      if (data.restaurants.length === 0) {
        this._addMsg("bot", `${searchTag}<br>找不到符合條件的餐廳，請試試其他描述。`);
        return;
      }

      // Summary message
      this._addMsg("bot", `${searchTag}<br>找到 <strong>${data.restaurants.length}</strong> 間餐廳，地圖已更新 ✅`);

      // Individual result cards
      const favSet = new Set(data.favourite_ids || []);
      data.restaurants.forEach((r, i) => {
        const reason   = data.recommendation_reasons[r.id] || "";
        const isFav    = favSet.has(r.id) || this._isFavourite(r.id);
        const favBadge = isFav ? `<span class="rc-fav-badge">❤️ 最愛</span>` : "";
        const heartIcon = isFav ? "❤️" : "🤍";
        const heartTitle = isFav ? "移除最愛" : "加入最愛";

        const ratingHtml = r.rating
          ? `<span class="rc-rating">⭐ ${r.rating.toFixed(1)} <span class="rc-review-count">(${(r.review_count||0).toLocaleString()})</span></span>`
          : "";

        const reviewsHtml = (r.reviews && r.reviews.length)
          ? `<div class="rc-reviews">
               <button class="rc-reviews-toggle">💬 看更多評論 (${r.reviews.length}) ▾</button>
               <div class="rc-reviews-more" style="display:none">${
                 r.reviews.map((rv, idx) =>
                   `<div class="rc-review-snippet">
                      <span class="rc-review-num">${idx + 1}</span>
                      ${this._esc(rv.slice(0, 120))}${rv.length > 120 ? "…" : ""}
                    </div>`
                 ).join("")
               }</div>
             </div>`
          : "";

        const el = document.createElement("div");
        el.className = "msg bot";
        el.innerHTML = `
          <div class="result-card">
            <div class="rc-header">
              <span class="rc-name">${i + 1}. ${this._esc(r.name)}</span>
              ${favBadge}
              <span class="rc-time">🚶 ${r.walking_minutes}分鐘</span>
              <button class="fav-btn" title="${heartTitle}">${heartIcon}</button>
            </div>
            ${ratingHtml}
            <div class="rc-addr">📍 ${this._esc(r.address)}</div>
            <div class="rc-reason">${this._esc(reason)}</div>
            ${reviewsHtml}
          </div>`;

        const toggleBtn = el.querySelector(".rc-reviews-toggle");
        if (toggleBtn) {
          toggleBtn.addEventListener("click", () => {
            const more = el.querySelector(".rc-reviews-more");
            const open = more.style.display === "none";
            more.style.display = open ? "block" : "none";
            toggleBtn.textContent = open
              ? "收起評論 ▴"
              : `💬 看更多評論 (${r.reviews.length}) ▾`;
          });
        }

        el.querySelector(".fav-btn").addEventListener("click", (e) => {
          const restaurant = {
            id: r.id, name: r.name,
            latitude: r.latitude, longitude: r.longitude, address: r.address,
          };
          this._toggleFavourite(restaurant, e.currentTarget);
        });

        document.getElementById("chat-messages").appendChild(el);
        el.scrollIntoView({ behavior: "smooth", block: "end" });
      });

    } catch (err) {
      typingEl.remove();
      let errHtml = `❌ ${this._esc(err.message)}`;
      if (err.parsedQuery) {
        const pq = err.parsedQuery;
        const searchTerm = pq.raw_keyword || pq.food;
        const tag = `<span class="nlp-tag">🔍 搜尋：${this._esc(searchTerm)} ｜ 步行 ${pq.time} 分鐘內</span>`;
        errHtml = `${tag}<br>${errHtml}`;
      }
      this._addMsg("bot", errHtml);
      if (err.message.includes("登入已過期")) {
        Auth.logout();
        setTimeout(() => location.reload(), 1500);
      }
    }
  },

  _showSignatureBadge(isValid, preview) {
    const el = document.getElementById("signature-badge");
    el.textContent = isValid
      ? `✅ 簽章驗證成功 (${preview}…)`
      : "❌ 簽章驗證失敗！";
    el.className    = isValid ? "badge-valid" : "badge-invalid";
    el.style.display = "block";
  },

  _esc(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  },
};

document.addEventListener("DOMContentLoaded", () => App.init());
