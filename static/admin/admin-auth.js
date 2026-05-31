/** Admin JWT + refresh token */
const AdminAuth = {
  tokenKey: 'kma_admin_token',
  refreshKey: 'kma_admin_refresh',
  userKey: 'kma_admin_user',
  _refreshing: null,

  getToken() {
    return localStorage.getItem(this.tokenKey);
  },

  getRefreshToken() {
    return localStorage.getItem(this.refreshKey);
  },

  getUser() {
    const raw = localStorage.getItem(this.userKey);
    if (!raw) return null;
    try { return JSON.parse(raw); } catch { return null; }
  },

  login(accessToken, refreshToken, user) {
    localStorage.setItem(this.tokenKey, accessToken);
    if (refreshToken) localStorage.setItem(this.refreshKey, refreshToken);
    localStorage.setItem(this.userKey, JSON.stringify(user));
  },

  async logout() {
    const refresh = this.getRefreshToken();
    const token = this.getToken();
    try {
      await fetch('/auth/logout', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: 'Bearer ' + token } : {}),
        },
        body: JSON.stringify({ refresh_token: refresh || null }),
      });
    } catch (_) {}
    localStorage.removeItem(this.tokenKey);
    localStorage.removeItem(this.refreshKey);
    localStorage.removeItem(this.userKey);
    sessionStorage.removeItem('otp_username');
    sessionStorage.removeItem('otp_emailHint');
    sessionStorage.removeItem('otp_message');
  },

  isAuthenticated() {
    return !!this.getToken();
  },

  requireAuth(redirectTo) {
    if (!this.isAuthenticated()) {
      window.location.href = redirectTo || '/admin/login';
      return false;
    }
    return true;
  },

  async refreshAccessToken() {
    const refresh = this.getRefreshToken();
    if (!refresh) throw new Error('No refresh token');
    if (this._refreshing) return this._refreshing;

    this._refreshing = (async () => {
      const res = await fetch('/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refresh }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || 'Refresh failed');
      const user = this.getUser() || { username: '', role: data.role };
      this.login(data.access_token, data.refresh_token, user);
      return data.access_token;
    })();

    try {
      return await this._refreshing;
    } finally {
      this._refreshing = null;
    }
  },

  async apiFetch(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    const token = this.getToken();
    if (token) headers['Authorization'] = 'Bearer ' + token;

    let res = await fetch(path, { ...options, headers });

    if (res.status === 401 && this.getRefreshToken()) {
      try {
        await this.refreshAccessToken();
        headers['Authorization'] = 'Bearer ' + this.getToken();
        res = await fetch(path, { ...options, headers });
      } catch {
        await this.logout();
        window.location.href = '/admin/login';
        throw new Error('Unauthorized');
      }
    }

    if (res.status === 401) {
      await this.logout();
      window.location.href = '/admin/login';
      throw new Error('Unauthorized');
    }
    return res;
  },
};
