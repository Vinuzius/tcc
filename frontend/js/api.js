/**
 * TCC - API Client (Comunicação com Backend FastAPI e OAuth 2.0)
 */

const API_BASE = window.location.origin;

class TCCApiClient {
  constructor() {
    this.tokenKey = 'tcc_access_token';
  }

  getToken() {
    return localStorage.getItem(this.tokenKey);
  }

  setToken(token) {
    if (token) {
      localStorage.setItem(this.tokenKey, token);
    } else {
      localStorage.removeItem(this.tokenKey);
    }
  }

  isAuthenticated() {
    return Boolean(this.getToken());
  }

  logout() {
    this.setToken(null);
  }

  async request(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const headers = {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    };

    const token = this.getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        let errorMsg = data.detail || `Erro HTTP ${response.status}`;
        if (typeof data.detail === 'object') {
          errorMsg = JSON.stringify(data.detail);
        }
        const error = new Error(errorMsg);
        error.status = response.status;
        error.data = data;
        throw error;
      }

      return data;
    } catch (err) {
      if (err.status === 401 && endpoint !== '/api/auth/login' && endpoint !== '/api/auth/token') {
        // Token expired or invalid
        this.logout();
        window.dispatchEvent(new CustomEvent('auth:expired'));
      }
      throw err;
    }
  }

  // ==========================================
  // AUTHENTICATION (OAuth 2.0)
  // ==========================================

  async login(username, password) {
    const data = await this.request('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });

    if (data.access_token) {
      this.setToken(data.access_token);
    }
    return data;
  }

  async loginOAuthPasswordFlow(username, password) {
    // Form-encoded according to RFC 6749 OAuth 2.0 Password flow
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    const response = await fetch(`${API_BASE}/api/auth/token`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: formData.toString(),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || 'Falha na autenticação OAuth 2.0');
    }

    if (data.access_token) {
      this.setToken(data.access_token);
    }
    return data;
  }

  async register(username, password) {
    const data = await this.request('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });

    if (data.access_token) {
      this.setToken(data.access_token);
    }
    return data;
  }

  async loginOAuthSocial(provider, email = null) {
    const data = await this.request('/api/auth/oauth/login', {
      method: 'POST',
      body: JSON.stringify({
        provider,
        oauth_email: email,
        code: `auth-code-${Date.now()}`,
      }),
    });

    if (data.access_token) {
      this.setToken(data.access_token);
    }
    return data;
  }

  async getMe() {
    return this.request('/api/auth/me');
  }

  // ==========================================
  // SQL QUERY EXECUTION
  // ==========================================

  async executeQuery(sql) {
    return this.request('/api/query', {
      method: 'POST',
      body: JSON.stringify({ sql }),
    });
  }

  // ==========================================
  // PROFILES (SELECT p.name FROM perfil)
  // ==========================================

  async getProfiles() {
    return this.request('/api/profiles');
  }

  // ==========================================
  // ADMIN PANEL
  // ==========================================

  async getAdminUsers() {
    return this.request('/api/admin/users');
  }

  async updateUserProfile(userId, perfilName) {
    return this.request(`/api/admin/users/${userId}/profile`, {
      method: 'PATCH',
      body: JSON.stringify({ perfil_name: perfilName }),
    });
  }

  async createAdminUser(userData) {
    return this.request('/api/admin/users', {
      method: 'POST',
      body: JSON.stringify(userData),
    });
  }

  async updateAdminUser(userId, userData) {
    return this.request(`/api/admin/users/${userId}`, {
      method: 'PUT',
      body: JSON.stringify(userData),
    });
  }

  async deleteAdminUser(userId) {
    return this.request(`/api/admin/users/${userId}`, {
      method: 'DELETE',
    });
  }

  async createProfile(profileData) {
    return this.request('/api/admin/profiles', {
      method: 'POST',
      body: JSON.stringify(profileData),
    });
  }
}

window.API = new TCCApiClient();
