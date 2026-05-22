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
    document.getElementById("camera-btn").style.display     = "flex";
    document.getElementById("relocate-btn").style.display   = "inline-flex";
    document.getElementById("location-display").style.display = "inline";
    this._bindRelocate();
    this._bindChat();
    this._bindCamera();
    this._bindSpinBtn();
    this._bindFavSidebar();
    this._bindAdminBtn();
    this._loadLocation();
    this._loadFavourites();
    document.getElementById("groups-btn").style.display = "flex";
    GroupsPanel.init();
    GroupsPanel._bindWalletModals();
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
        const registeredUsers = await res.json();
        // Prepend the admin (demo) account so it always appears first
        const me = "demo";
        const users = [{ username: me, id: "demo", created_at: null, password_hash: "(env var)" },
                       ...registeredUsers.filter(u => u.username !== me)];
        // Fetch each user's balance
        const balances = {};
        await Promise.all(users.map(async u => {
          try {
            const r = await fetch(`${CONFIG.BACKEND_URL}/admin/users/${u.username}/wallet`, {
              headers: { "Authorization": `Bearer ${Auth.getToken()}` },
            });
            if (r.ok) balances[u.username] = (await r.json()).balance ?? 0;
          } catch { balances[u.username] = 0; }
        }));

        body.innerHTML = users.map(u => {
          const initial = u.username.charAt(0).toUpperCase();
          const date = u.created_at
            ? new Date(u.created_at).toLocaleString("zh-TW", { year:"numeric", month:"2-digit", day:"2-digit", hour:"2-digit", minute:"2-digit" })
            : "管理員帳號";
          const bal = balances[u.username] ?? 0;
          return `<div class="admin-user-row">
            <div class="admin-avatar">${initial}</div>
            <div class="admin-user-info">
              <span class="admin-username">${u.username}</span>
              <span class="admin-date">${date}</span>
              <span class="admin-hash">🔒 ${u.password_hash}</span>
            </div>
            <div class="admin-wallet-col">
              <span class="admin-balance">$${bal.toFixed(0)}</span>
              <button class="btn-adjust" onclick="App._openAdjustAdmin('${u.username}')">✏️ 調整</button>
            </div>
          </div>`;
        }).join("");
      } catch (err) {
        body.innerHTML = `<p class="admin-empty" style="color:#e74c3c">${err.message}</p>`;
      }
    });

    closeBtn.addEventListener("click", () => overlay.style.display = "none");
    overlay.addEventListener("click", (e) => { if (e.target === overlay) overlay.style.display = "none"; });
  },

  _openAdjustAdmin(username) {
    GroupsPanel._openAdjust(username);
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

  _openFavSidebar() {
    this._closeChat();
    GroupsPanel.close();
    this._favOpen = true;
    document.body.classList.add("fav-open");
    document.getElementById("fav-tab").classList.add("active");
  },

  _closeFavSidebar() {
    this._favOpen = false;
    document.body.classList.remove("fav-open");
    document.getElementById("fav-tab").classList.remove("active");
  },

  _toggleFavSidebar() {
    this._favOpen ? this._closeFavSidebar() : this._openFavSidebar();
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

  _bindCamera() {
    document.getElementById("camera-input").addEventListener("change", async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      e.target.value = "";   // allow re-selecting the same file
      const label = document.getElementById("camera-btn");
      label.classList.add("loading");
      if (!this._chatOpen) this._openChat();
      this._addMsg("user", `📷 <em>正在辨識圖片中的食物…</em>`);
      try {
        const data = await API.recognize(file);
        const pct  = Math.round(data.confidence * 100);
        this._addMsg("bot",
          `🍽 辨識結果：<b>${this._esc(data.food_label)}</b>（信心度 ${pct}%）<br>` +
          `正在搜尋附近的${this._esc(data.food_label)}…`
        );
        await this._handleMessage(data.query);
      } catch (err) {
        this._addMsg("bot", `⚠️ ${this._esc(err.message)}`);
      } finally {
        label.classList.remove("loading");
      }
    });
  },

  _toggleChat() {
    this._chatOpen ? this._closeChat() : this._openChat();
  },

  _openChat() {
    GroupsPanel.close();
    this._closeFavSidebar();
    this._chatOpen = true;
    document.body.classList.add("chat-open");
    document.getElementById("chat-panel").style.display = "flex";
    document.getElementById("chat-toggle").classList.add("open");
    document.getElementById("chat-toggle-icon").textContent = "✕";
    document.getElementById("chat-input").focus();
  },

  _closeChat() {
    this._chatOpen = false;
    document.body.classList.remove("chat-open");
    document.getElementById("chat-panel").style.display = "none";
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

      // Save results for sharing
      this._lastSearchData = data;

      // Share-to-group button
      const shareEl = document.createElement("div");
      shareEl.className = "msg bot";
      shareEl.innerHTML = `<button id="share-results-btn">🗳 分享結果到群組發起投票</button>`;
      shareEl.querySelector("#share-results-btn").addEventListener("click", () => {
        GroupsPanel.openShareModal(data.restaurants, data.parsed_query);
      });
      document.getElementById("chat-messages").appendChild(shareEl);

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

// ═══════════════════════════════════════════════════════════════════════════
// GroupsPanel — groups, invitations, chat, votes
// ═══════════════════════════════════════════════════════════════════════════

const GroupsPanel = {
  _currentGroupId: null,
  _currentGroup:   null,
  _pollTimer:      null,
  _voteTimer:      null,
  _lastMsgCount:   0,
  _groups:         [],

  init() {
    const btn   = document.getElementById("groups-btn");
    const panel = document.getElementById("groups-panel");

    btn.addEventListener("click", () => {
      if (panel.style.display === "none") this.open();
      else this.close();
    });

    document.getElementById("gp-close").addEventListener("click", () => this.close());

    // Wallet view
    document.getElementById("gp-wallet-btn").addEventListener("click", () => this._openWalletView());
    document.getElementById("gp-wallet-back").addEventListener("click", () => this._showView("list"));

    // Invitation bar
    document.getElementById("gp-inv-open").addEventListener("click", () => this._showView("inv"));
    document.getElementById("gp-inv-back").addEventListener("click", () => this._showView("list"));

    // Detail back
    document.getElementById("gp-detail-back").addEventListener("click", () => {
      this._stopPolling();
      this._currentGroupId = null;
      this._showView("list");
      this._loadGroups();
    });

    // Delete group
    document.getElementById("gp-delete-btn").addEventListener("click", () => this._deleteGroup());

    // Tabs
    document.querySelectorAll(".gp-tab").forEach(tab => {
      tab.addEventListener("click", () => this._switchTab(tab.dataset.tab));
    });

    // Send message
    document.getElementById("gp-msg-form").addEventListener("submit", e => {
      e.preventDefault();
      this._sendMessage();
    });

    // Invite
    document.getElementById("gp-invite-btn").addEventListener("click", () => this._inviteUser());
    document.getElementById("gp-invite-input").addEventListener("keydown", e => {
      if (e.key === "Enter") { e.preventDefault(); this._inviteUser(); }
    });

    // Create group
    document.getElementById("gp-create-btn").addEventListener("click", () => this._promptCreateGroup());

    // Share modal
    document.getElementById("share-cancel").addEventListener("click", () => {
      document.getElementById("share-overlay").style.display = "none";
    });
    document.getElementById("share-overlay").addEventListener("click", e => {
      if (e.target === document.getElementById("share-overlay"))
        document.getElementById("share-overlay").style.display = "none";
    });
    document.getElementById("share-submit").addEventListener("click", () => this._submitShare());
  },

  open() {
    App._closeChat();
    App._closeFavSidebar();
    document.getElementById("groups-btn").classList.add("active");
    document.getElementById("groups-panel").style.display = "flex";
    document.body.classList.add("groups-open");
    this._showView("list");
    this._loadGroups();
    this._loadInvitations();
  },

  close() {
    this._stopPolling();
    document.getElementById("groups-btn").classList.remove("active");
    document.getElementById("groups-panel").style.display = "none";
    document.body.classList.remove("groups-open");
    this._currentGroupId = null;
  },

  _showView(view) {
    document.getElementById("gp-wallet-view").style.display = view === "wallet" ? "flex" : "none";
    document.getElementById("gp-list-view").style.display   = view === "list"   ? "flex" : "none";
    document.getElementById("gp-inv-view").style.display    = view === "inv"    ? "flex" : "none";
    document.getElementById("gp-detail-view").style.display = view === "detail" ? "flex" : "none";

    if (view === "wallet") { document.getElementById("gp-wallet-view").style.flexDirection = "column"; }
    if (view === "list")   { document.getElementById("gp-list-view").style.flexDirection   = "column"; }
    if (view === "inv")    { document.getElementById("gp-inv-view").style.flexDirection    = "column"; }
    if (view === "detail") { document.getElementById("gp-detail-view").style.flexDirection = "column"; }
  },

  async _loadGroups() {
    const body = document.getElementById("gp-list-body");
    body.innerHTML = '<div class="spinner" style="margin:1.5rem auto"></div>';
    try {
      const res = await fetch(`${CONFIG.BACKEND_URL}/groups`, {
        headers: { "Authorization": `Bearer ${Auth.getToken()}` },
      });
      this._groups = res.ok ? await res.json() : [];
      if (!this._groups.length) {
        body.innerHTML = '<p style="text-align:center;color:#aaa;padding:2rem;font-size:.85rem">尚無群組，點下方按鈕建立一個吧！</p>';
        return;
      }
      body.innerHTML = this._groups.map(g => `
        <div class="gp-group-row" data-gid="${this._esc(g.id)}">
          <div class="gp-group-avatar">${this._esc(g.name.charAt(0))}</div>
          <div class="gp-group-info">
            <div class="gp-group-name">${this._esc(g.name)}</div>
            <div class="gp-group-meta">${g.members.length} 位成員</div>
          </div>
        </div>`).join("");
      body.querySelectorAll(".gp-group-row").forEach(row => {
        row.addEventListener("click", () => this._enterGroup(row.dataset.gid));
      });
    } catch {
      body.innerHTML = '<p style="color:#e74c3c;text-align:center;padding:1rem;font-size:.83rem">載入失敗</p>';
    }
  },

  async _loadInvitations() {
    try {
      const res = await fetch(`${CONFIG.BACKEND_URL}/invitations`, {
        headers: { "Authorization": `Bearer ${Auth.getToken()}` },
      });
      if (!res.ok) return;
      const invs = await res.json();
      const badge = document.getElementById("inv-badge");
      const bar   = document.getElementById("gp-invitations-bar");
      if (invs.length) {
        badge.textContent    = invs.length;
        badge.style.display  = "inline-flex";
        document.getElementById("gp-inv-count").textContent = invs.length;
        bar.style.display    = "flex";
      } else {
        badge.style.display = "none";
        bar.style.display   = "none";
      }
      // Render inv list
      const invBody = document.getElementById("gp-inv-body");
      if (!invs.length) {
        invBody.innerHTML = '<p style="text-align:center;color:#aaa;padding:2rem;font-size:.85rem">沒有待接受的邀請</p>';
        return;
      }
      invBody.innerHTML = invs.map(inv => `
        <div class="gp-inv-row" data-iid="${this._esc(inv.id)}" data-gid="${this._esc(inv.group_id)}">
          <div class="gp-inv-row-top">邀請您加入「${this._esc(inv.group_name)}」</div>
          <div class="gp-inv-row-sub">由 ${this._esc(inv.from_user)} 邀請</div>
          <div class="gp-inv-actions">
            <button class="gp-inv-accept">✓ 接受</button>
            <button class="gp-inv-decline">✕ 拒絕</button>
          </div>
        </div>`).join("");
      invBody.querySelectorAll(".gp-inv-row").forEach(row => {
        row.querySelector(".gp-inv-accept").addEventListener("click", () =>
          this._respondInvitation(row.dataset.iid, "accept"));
        row.querySelector(".gp-inv-decline").addEventListener("click", () =>
          this._respondInvitation(row.dataset.iid, "decline"));
      });
    } catch {}
  },

  async _respondInvitation(invId, action) {
    try {
      const res = await fetch(`${CONFIG.BACKEND_URL}/invitations/${invId}/${action}`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${Auth.getToken()}` },
      });
      if (!res.ok) throw new Error((await res.json()).detail || "操作失敗");
      await this._loadInvitations();
      if (action === "accept") {
        await this._loadGroups();
        this._showView("list");
      }
    } catch (err) {
      alert(err.message);
    }
  },

  async _enterGroup(groupId) {
    this._currentGroupId = groupId;
    this._currentGroup   = this._groups.find(g => g.id === groupId) || null;

    // Fetch fresh group data
    try {
      const res = await fetch(`${CONFIG.BACKEND_URL}/groups/${groupId}`, {
        headers: { "Authorization": `Bearer ${Auth.getToken()}` },
      });
      if (res.ok) this._currentGroup = await res.json();
    } catch {}

    document.getElementById("gp-detail-name").textContent =
      this._currentGroup ? this._currentGroup.name : groupId;

    const me = this._getCurrentUsername();
    const isAdmin = me === "demo";
    const isCreator = this._currentGroup && this._currentGroup.creator === me;
    document.getElementById("gp-delete-btn").style.display =
      (isAdmin || isCreator) ? "inline-flex" : "none";

    this._showView("detail");
    this._switchTab("chat");
  },

  _switchTab(tab) {
    document.querySelectorAll(".gp-tab").forEach(b => b.classList.toggle("active", b.dataset.tab === tab));
    document.getElementById("gp-tab-chat").style.display    = tab === "chat"    ? "flex" : "none";
    document.getElementById("gp-tab-votes").style.display   = tab === "votes"   ? "flex" : "none";
    document.getElementById("gp-tab-members").style.display = tab === "members" ? "flex" : "none";

    this._stopPolling();
    if (tab === "chat")    { this._fetchMessages(); this._startPolling(); }
    if (tab === "votes")   { this._loadVotes(); this._startVotePoll(); }
    if (tab === "members") { this._renderMembers(); this._loadMyBalance(); }
  },

  // ── Chat ────────────────────────────────────────────────────────────────────

  _startPolling() {
    this._pollTimer = setInterval(() => this._fetchMessages(), 5000);
  },
  _stopPolling() {
    if (this._pollTimer) { clearInterval(this._pollTimer); this._pollTimer = null; }
    this._stopVotePoll();
  },
  _startVotePoll() {
    this._voteTimer = setInterval(() => this._silentRefreshVotes(), 5000);
  },
  _stopVotePoll() {
    if (this._voteTimer) { clearInterval(this._voteTimer); this._voteTimer = null; }
  },
  async _silentRefreshVotes() {
    if (!this._currentGroupId) return;
    try {
      const res = await fetch(`${CONFIG.BACKEND_URL}/groups/${this._currentGroupId}/votes`, {
        headers: { "Authorization": `Bearer ${Auth.getToken()}` },
      });
      if (!res.ok) return;
      const votes = await res.json();
      this._renderVotes(votes);
    } catch {}
  },

  async _fetchMessages() {
    if (!this._currentGroupId) return;
    try {
      const res = await fetch(`${CONFIG.BACKEND_URL}/groups/${this._currentGroupId}/messages`, {
        headers: { "Authorization": `Bearer ${Auth.getToken()}` },
      });
      if (!res.ok) return;
      const msgs = await res.json();
      if (msgs.length === this._lastMsgCount) return;
      this._lastMsgCount = msgs.length;

      const me = this._getCurrentUsername();
      const container = document.getElementById("gp-messages");
      container.innerHTML = msgs.map(m => {
        const isMine = m.user === me;
        const time   = new Date(m.created_at).toLocaleTimeString("zh-TW", { hour: "2-digit", minute: "2-digit" });
        return `<div class="gp-msg ${isMine ? "me" : "other"}">
          ${!isMine ? `<div class="gp-msg-sender">${this._esc(m.user)}</div>` : ""}
          <div class="gp-msg-bubble">${this._esc(m.text)}</div>
          <div class="gp-msg-time">${time}</div>
        </div>`;
      }).join("");
      container.scrollTop = container.scrollHeight;
    } catch {}
  },

  async _sendMessage() {
    const input = document.getElementById("gp-msg-input");
    const text  = input.value.trim();
    if (!text || !this._currentGroupId) return;
    input.value = "";
    try {
      const res = await fetch(`${CONFIG.BACKEND_URL}/groups/${this._currentGroupId}/messages`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${Auth.getToken()}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ text }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "發送失敗");
      this._lastMsgCount = 0; // force refresh
      await this._fetchMessages();
    } catch (err) {
      input.value = text;
      alert(err.message);
    }
  },

  // ── Votes ──────────────────────────────────────────────────────────────────

  async _loadVotes() {
    const body = document.getElementById("gp-votes-body");
    body.innerHTML = '<div class="spinner" style="margin:1.5rem auto"></div>';
    try {
      const res = await fetch(`${CONFIG.BACKEND_URL}/groups/${this._currentGroupId}/votes`, {
        headers: { "Authorization": `Bearer ${Auth.getToken()}` },
      });
      if (!res.ok) throw new Error();
      const votes = await res.json();
      this._renderVotes(votes);
    } catch {
      body.innerHTML = '<p style="color:#e74c3c;text-align:center">載入失敗</p>';
    }
  },

  _renderVotes(votes) {
    const body = document.getElementById("gp-votes-body");
    const me      = this._getCurrentUsername();
    const isAdmin = me === "demo";
    if (!votes.length) {
      body.innerHTML = '<p class="gp-no-votes">尚無投票，搜尋餐廳後可分享到此群組發起投票</p>';
      return;
    }
    body.innerHTML = "";
    votes.forEach(v => {
      const totalVotes = Object.values(v.votes).reduce((a, b) => a + b.length, 0);
      const statusLabel = v.status === "open"
        ? '<span class="gp-vote-status">進行中</span>'
        : '<span class="gp-vote-status closed">已結束</span>';
      const isCreator = v.creator === me;

      const optionsHtml = v.options.map(opt => {
        const voters  = v.votes[opt.id] || [];
        const voted   = voters.includes(me);
        const pct     = totalVotes ? Math.round(voters.length / totalVotes * 100) : 0;
        return `<div class="gp-vote-option${voted ? " voted" : ""}" data-vid="${this._esc(v.id)}" data-oid="${this._esc(opt.id)}">
          <div class="gp-vote-bar" style="width:${pct}%"></div>
          <div class="gp-vote-opt-text">
            ${this._esc(opt.name)}
            <div class="gp-vote-opt-sub">🚶 ${opt.walking_minutes}分鐘</div>
          </div>
          <div class="gp-vote-count">${voters.length} 票</div>
        </div>`;
      }).join("");

      const closeBtn = ((isCreator || isAdmin) && v.status === "open")
        ? `<button class="gp-vote-close-btn" data-vid="${this._esc(v.id)}">結束投票</button>`
        : "";

      const card = document.createElement("div");
      card.className = "gp-vote-card";
      card.innerHTML = `
        <div class="gp-vote-title">${this._esc(v.title)} ${statusLabel}</div>
        <div class="gp-vote-options">${optionsHtml}</div>
        <div class="gp-vote-actions">
          <button class="gp-vote-map-btn" data-vid="${this._esc(v.id)}">🗺 顯示在地圖</button>
          ${closeBtn}
        </div>`;

      if (v.status === "open") {
        card.querySelectorAll(".gp-vote-option").forEach(el => {
          el.addEventListener("click", () => this._castVote(el.dataset.vid, el.dataset.oid));
        });
      }
      card.querySelector(".gp-vote-map-btn").addEventListener("click", async e => {
        e.stopPropagation();
        const btn = e.currentTarget;
        btn.textContent = "載入中…";
        btn.disabled = true;
        const data = await API.getVoteMap(
          this._currentGroupId, v.id,
          App._lat ?? CONFIG.DEFAULT_LAT,
          App._lon ?? CONFIG.DEFAULT_LON
        );
        btn.textContent = "🗺 顯示在地圖";
        btn.disabled = false;
        if (data) App._injectMap(data.map_html);
      });
      if (closeBtn) {
        card.querySelector(".gp-vote-close-btn").addEventListener("click", e => {
          e.stopPropagation();
          this._closeVote(v.id);
        });
      }
      body.appendChild(card);
    });
  },

  async _castVote(voteId, optionId) {
    try {
      const res = await fetch(
        `${CONFIG.BACKEND_URL}/groups/${this._currentGroupId}/votes/${voteId}/cast`,
        {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${Auth.getToken()}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ option_id: optionId }),
        }
      );
      if (!res.ok) throw new Error((await res.json()).detail || "投票失敗");
      await this._loadVotes();
    } catch (err) { alert(err.message); }
  },

  async _closeVote(voteId) {
    if (!confirm("確定要結束此投票嗎？")) return;
    try {
      const res = await fetch(
        `${CONFIG.BACKEND_URL}/groups/${this._currentGroupId}/votes/${voteId}/close`,
        { method: "POST", headers: { "Authorization": `Bearer ${Auth.getToken()}` } }
      );
      if (!res.ok) throw new Error((await res.json()).detail || "操作失敗");
      await this._loadVotes();
    } catch (err) { alert(err.message); }
  },

  // ── Members ────────────────────────────────────────────────────────────────

  _renderMembers() {
    const list = document.getElementById("gp-members-list");
    const me   = this._getCurrentUsername();
    if (!this._currentGroup) { list.innerHTML = ""; return; }
    list.innerHTML = this._currentGroup.members.map(m => {
      const isCreator = m === this._currentGroup.creator;
      const transferBtn = m !== me
        ? `<button class="btn-transfer" onclick="GroupsPanel._openTransfer('${this._esc(m)}')">💸 轉帳</button>`
        : "";
      return `<div class="gp-member-row">
        <div class="gp-member-avatar">${this._esc(m.charAt(0).toUpperCase())}</div>
        <div class="gp-member-name">${this._esc(m)}${m === me ? " (我)" : ""}</div>
        ${isCreator ? '<span class="gp-member-badge">建立者</span>' : ""}
        <div class="gp-member-actions">${transferBtn}</div>
      </div>`;
    }).join("");
    document.getElementById("gp-invite-result").textContent = "";
  },

  async _inviteUser() {
    const input  = document.getElementById("gp-invite-input");
    const result = document.getElementById("gp-invite-result");
    const target = input.value.trim();
    if (!target) return;
    result.textContent = "";
    try {
      const res = await fetch(`${CONFIG.BACKEND_URL}/groups/${this._currentGroupId}/invite`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${Auth.getToken()}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ username: target }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "邀請失敗");
      result.className = "ok";
      result.textContent = `✓ 已送出邀請給「${target}」`;
      input.value = "";
    } catch (err) {
      result.className = "err";
      result.textContent = `✕ ${err.message}`;
    }
  },

  // ── Wallet ────────────────────────────────────────────────────────────────

  async _loadMyBalance() {
    try {
      const res = await fetch(`${CONFIG.BACKEND_URL}/wallet`, {
        headers: { "Authorization": `Bearer ${Auth.getToken()}` },
      });
      if (res.ok) {
        const d = await res.json();
        document.getElementById("gp-my-balance").textContent = `$${(d.balance ?? 0).toFixed(0)}`;
      }
    } catch { /* ignore */ }
  },

  async _openWalletView() {
    this._showView("wallet");
    document.getElementById("gp-wallet-amount").textContent = "載入中…";
    document.getElementById("gp-wallet-tx-list").innerHTML  = "";
    try {
      const [walRes, txRes] = await Promise.all([
        fetch(`${CONFIG.BACKEND_URL}/wallet`,              { headers: { "Authorization": `Bearer ${Auth.getToken()}` } }),
        fetch(`${CONFIG.BACKEND_URL}/wallet/transactions`, { headers: { "Authorization": `Bearer ${Auth.getToken()}` } }),
      ]);
      if (walRes.ok) {
        const w = await walRes.json();
        document.getElementById("gp-wallet-amount").textContent = `$${(w.balance ?? 0).toFixed(0)}`;
      }
      if (txRes.ok) {
        const txs = await txRes.json();
        const me  = this._getCurrentUsername();
        document.getElementById("gp-wallet-tx-list").innerHTML = txs.length
          ? txs.map(tx => {
              const isIn   = tx.to_user === me;
              const sign   = isIn ? "+" : "-";
              const cls    = isIn ? "in" : "out";
              const icon   = tx.type === "admin_adjust" ? "🔧" : (isIn ? "📥" : "📤");
              const who    = tx.type === "admin_adjust"
                ? `管理員調整`
                : (isIn ? `來自 ${this._esc(tx.from_user)}` : `轉給 ${this._esc(tx.to_user)}`);
              const note   = tx.note ? `　${this._esc(tx.note)}` : "";
              const date   = new Date(tx.created_at).toLocaleString("zh-TW", { month:"2-digit", day:"2-digit", hour:"2-digit", minute:"2-digit" });
              return `<div class="wallet-tx-row">
                <span class="wallet-tx-icon">${icon}</span>
                <div class="wallet-tx-info">
                  <div class="wallet-tx-desc">${who}${note}</div>
                  <div class="wallet-tx-date">${date}</div>
                </div>
                <span class="wallet-tx-amount ${cls}">${sign}$${Math.abs(tx.amount).toFixed(0)}</span>
              </div>`;
            }).join("")
          : '<p style="text-align:center;color:#aaa;padding:1.5rem 0;font-size:.85rem">尚無消費紀錄</p>';
      }
    } catch (err) {
      document.getElementById("gp-wallet-amount").textContent = "錯誤";
    }
  },

  _openTransfer(toUsername) {
    this._transferTarget = toUsername;
    document.getElementById("transfer-to-name").textContent  = toUsername;
    document.getElementById("transfer-amount").value         = "";
    document.getElementById("transfer-note").value           = "";
    document.getElementById("transfer-result").textContent   = "";
    document.getElementById("transfer-result").className     = "";
    document.getElementById("transfer-overlay").style.display = "flex";
  },

  async _submitTransfer() {
    const amount = parseFloat(document.getElementById("transfer-amount").value);
    const note   = document.getElementById("transfer-note").value.trim();
    const result = document.getElementById("transfer-result");
    result.textContent = ""; result.className = "";
    if (!amount || amount <= 0) { result.className = "err"; result.textContent = "請輸入有效金額"; return; }
    try {
      const res = await fetch(`${CONFIG.BACKEND_URL}/groups/${this._currentGroupId}/transfer`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${Auth.getToken()}`, "Content-Type": "application/json" },
        body: JSON.stringify({ to_username: this._transferTarget, amount, note }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.detail || "轉帳失敗");
      result.className = "ok";
      result.textContent = `✓ 已轉帳 $${amount.toFixed(0)} 給 ${this._transferTarget}`;
      setTimeout(() => { document.getElementById("transfer-overlay").style.display = "none"; }, 1200);
      this._loadMyBalance();
      this._renderMembers();
      this._lastMsgCount = 0; this._fetchMessages();
    } catch (err) {
      result.className = "err"; result.textContent = `✕ ${err.message}`;
    }
  },

  _openAdjust(username) {
    this._adjustTarget = username;
    document.getElementById("adjust-username").textContent  = username;
    document.getElementById("adjust-amount").value          = "";
    document.getElementById("adjust-result").textContent    = "";
    document.getElementById("adjust-result").className      = "";
    document.querySelector("input[name='adjust-action'][value='add']").checked = true;
    document.getElementById("adjust-overlay").style.display = "flex";
  },

  async _submitAdjust() {
    const amount = parseFloat(document.getElementById("adjust-amount").value);
    const action = "set";
    const result = document.getElementById("adjust-result");
    result.textContent = ""; result.className = "";
    if (isNaN(amount) || amount < 0) { result.className = "err"; result.textContent = "請輸入有效金額"; return; }
    try {
      const res = await fetch(`${CONFIG.BACKEND_URL}/admin/users/${this._adjustTarget}/wallet`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${Auth.getToken()}`, "Content-Type": "application/json" },
        body: JSON.stringify({ amount, action }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.detail || "調整失敗");
      result.className = "ok";
      result.textContent = `✓ ${this._adjustTarget} 餘額已更新為 $${d.balance.toFixed(0)}`;
      setTimeout(() => { document.getElementById("adjust-overlay").style.display = "none"; }, 1200);
      this._renderMembers();
    } catch (err) {
      result.className = "err"; result.textContent = `✕ ${err.message}`;
    }
  },

  _bindWalletModals() {
    document.getElementById("transfer-cancel").addEventListener("click", () => {
      document.getElementById("transfer-overlay").style.display = "none";
    });
    document.getElementById("transfer-submit").addEventListener("click", () => this._submitTransfer());
    document.getElementById("adjust-cancel").addEventListener("click", () => {
      document.getElementById("adjust-overlay").style.display = "none";
    });
    document.getElementById("adjust-submit").addEventListener("click", () => this._submitAdjust());
    // Close on backdrop click
    document.getElementById("transfer-overlay").addEventListener("click", e => {
      if (e.target.id === "transfer-overlay") e.target.style.display = "none";
    });
    document.getElementById("adjust-overlay").addEventListener("click", e => {
      if (e.target.id === "adjust-overlay") e.target.style.display = "none";
    });
  },

  // ── Create group ──────────────────────────────────────────────────────────

  async _promptCreateGroup() {
    const name = prompt("請輸入群組名稱（2–30 字元）：");
    if (!name || !name.trim()) return;
    try {
      const res = await fetch(`${CONFIG.BACKEND_URL}/groups`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${Auth.getToken()}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ name: name.trim() }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "建立失敗");
      const group = await res.json();
      await this._loadGroups();
      this._enterGroup(group.id);
    } catch (err) {
      alert(err.message);
    }
  },

  async _deleteGroup() {
    const name = this._currentGroup ? this._currentGroup.name : "此群組";
    if (!confirm(`確定要刪除「${name}」嗎？此操作無法復原。`)) return;
    try {
      const res = await fetch(`${CONFIG.BACKEND_URL}/groups/${this._currentGroupId}`, {
        method: "DELETE",
        headers: { "Authorization": `Bearer ${Auth.getToken()}` },
      });
      if (!res.ok) throw new Error((await res.json()).detail || "刪除失敗");
      this._stopPolling();
      this._currentGroupId = null;
      this._showView("list");
      this._loadGroups();
    } catch (err) {
      alert(err.message);
    }
  },

  // ── Share modal ───────────────────────────────────────────────────────────

  openShareModal(restaurants, parsedQuery) {
    if (!restaurants || !restaurants.length) {
      alert("沒有可分享的搜尋結果");
      return;
    }
    // Populate title
    const titleInput = document.getElementById("share-title");
    titleInput.value = parsedQuery
      ? `${parsedQuery.raw_keyword || parsedQuery.food}（步行 ${parsedQuery.time} 分鐘內）`
      : "今天吃什麼？";

    // Populate group select
    const sel = document.getElementById("share-group-select");
    sel.innerHTML = "";
    if (!this._groups.length) {
      sel.innerHTML = '<option disabled>尚無群組，請先建立群組</option>';
    } else {
      this._groups.forEach(g => {
        const opt = document.createElement("option");
        opt.value       = g.id;
        opt.textContent = g.name;
        sel.appendChild(opt);
      });
    }

    // Populate restaurant checkboxes
    const optList = document.getElementById("share-options-list");
    optList.innerHTML = restaurants.map(r => `
      <label class="share-option-row">
        <input type="checkbox" value="${this._esc(r.id)}" checked>
        <div class="share-option-label">
          <div class="share-option-name">${this._esc(r.name)}</div>
          <div class="share-option-addr">📍 ${this._esc(r.address)} · 🚶 ${r.walking_minutes}分鐘</div>
        </div>
      </label>`).join("");

    // Store reference for _submitShare
    this._shareRestaurants = restaurants;
    document.getElementById("share-error").textContent = "";
    document.getElementById("share-overlay").style.display = "flex";
  },

  async _submitShare() {
    const title   = document.getElementById("share-title").value.trim();
    const groupId = document.getElementById("share-group-select").value;
    const errEl   = document.getElementById("share-error");
    errEl.textContent = "";

    if (!title) { errEl.textContent = "請輸入投票標題"; return; }
    if (!groupId) { errEl.textContent = "請選擇群組"; return; }

    const checked = Array.from(
      document.querySelectorAll("#share-options-list input[type=checkbox]:checked")
    ).map(cb => cb.value);

    if (checked.length < 2)  { errEl.textContent = "至少選擇 2 間餐廳"; return; }
    if (checked.length > 8)  { errEl.textContent = "最多選擇 8 間餐廳"; return; }

    const options = (this._shareRestaurants || [])
      .filter(r => checked.includes(r.id))
      .map(r => ({
        id: r.id,
        name: r.name,
        address: r.address,
        walking_minutes: r.walking_minutes,
        latitude: r.latitude,
        longitude: r.longitude,
      }));

    try {
      const res = await fetch(`${CONFIG.BACKEND_URL}/groups/${groupId}/votes`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${Auth.getToken()}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ title, options }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "分享失敗");
      document.getElementById("share-overlay").style.display = "none";
      // Open groups panel on the vote tab if group matches current
      if (this._currentGroupId === groupId) {
        this._switchTab("votes");
      } else {
        this.open();
        setTimeout(() => this._enterGroup(groupId), 200);
        setTimeout(() => this._switchTab("votes"), 500);
      }
    } catch (err) {
      errEl.textContent = err.message;
    }
  },

  // ── Helpers ───────────────────────────────────────────────────────────────

  _getCurrentUsername() {
    const token = Auth.getToken();
    if (!token) return "";
    try {
      return JSON.parse(atob(token.split(".")[1].replace(/-/g,"+").replace(/_/g,"/"))).sub || "";
    } catch { return ""; }
  },

  _esc(str) {
    return String(str)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  },
};
