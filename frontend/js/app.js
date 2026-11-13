/**
 * TCC - Aplicação Frontend Principal (Interações, Estado e Renderização)
 */

(function () {
  'use strict';

  // Application State
  const state = {
    currentUser: null,
    profiles: [],
    lastQueryResult: null,
  };

  // DOM Elements Cache
  const elements = {
    authSection: document.getElementById('auth-section'),
    userSession: document.getElementById('user-session'),
    appNav: document.getElementById('app-nav'),
    navUsername: document.getElementById('nav-username'),
    navProfileBadge: document.getElementById('nav-profile-badge'),
    navRoleBadge: document.getElementById('nav-role-badge'),
    navTabAdmin: document.getElementById('nav-tab-admin'),
    btnLogout: document.getElementById('btn-logout'),

    // Auth forms
    btnShowLogin: document.getElementById('btn-show-login'),
    btnShowRegister: document.getElementById('btn-show-register'),
    formLogin: document.getElementById('form-login'),
    formRegister: document.getElementById('form-register'),
    loginUsernameInput: document.getElementById('login-username'),
    loginPasswordInput: document.getElementById('login-password'),
    regUsernameInput: document.getElementById('reg-username'),
    regPasswordInput: document.getElementById('reg-password'),
    regConfirmPasswordInput: document.getElementById('reg-confirm-password'),

    // Tabs
    tabs: document.querySelectorAll('.app-tab-content'),
    navTabButtons: document.querySelectorAll('.nav-tab'),

    // Query Runner
    sqlInput: document.getElementById('sql-input'),
    btnRunQuery: document.getElementById('btn-run-query'),
    btnClearQuery: document.getElementById('btn-clear-query'),
    queryActiveProfile: document.getElementById('query-active-profile'),
    queryError: document.getElementById('query-error'),
    queryErrorText: document.getElementById('query-error-text'),
    queryResultsWrapper: document.getElementById('query-results-wrapper'),
    queryEmptyState: document.getElementById('query-empty-state'),
    resultsTable: document.getElementById('results-table'),
    resultsThead: document.getElementById('results-thead'),
    resultsTbody: document.getElementById('results-tbody'),
    metricRows: document.getElementById('metric-rows'),
    metricCols: document.getElementById('metric-cols'),
    metricTime: document.getElementById('metric-time'),
    filterResults: document.getElementById('filter-results'),
    btnExportCsv: document.getElementById('btn-export-csv'),

    // Admin Panel
    adminUsersTable: document.getElementById('admin-users-table'),
    adminUsersTbody: document.getElementById('admin-users-tbody'),
    btnRefreshUsers: document.getElementById('btn-refresh-users'),
    formAdminCreateUser: document.getElementById('form-admin-create-user'),
    adminNewUsername: document.getElementById('admin-new-username'),
    adminNewPassword: document.getElementById('admin-new-password'),
    adminNewProfileSelect: document.getElementById('admin-new-profile-select'),
    adminNewIsAdmin: document.getElementById('admin-new-is-admin'),

    // Profiles Catalog
    profilesCatalogTbody: document.getElementById('profiles-catalog-tbody'),
    profilesCountBadge: document.getElementById('profiles-count-badge'),
    adminAddProfileContainer: document.getElementById('admin-add-profile-container'),
    formCreateProfile: document.getElementById('form-create-profile'),
    profileNameInput: document.getElementById('profile-name'),
    profileDescInput: document.getElementById('profile-desc'),

    // Toasts
    toastContainer: document.getElementById('toast-container'),
  };

  // ==========================================
  // TOAST NOTIFICATIONS
  // ==========================================

  function showToast(message, type = 'info') {
    const icons = {
      info: 'ℹ️',
      success: '✅',
      danger: '⚠️',
      warning: '🔔',
    };

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
      <span class="toast-icon">${icons[type] || 'ℹ️'}</span>
      <span class="toast-msg">${message}</span>
    `;

    elements.toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(40px)';
      setTimeout(() => toast.remove(), 250);
    }, 4000);
  }

  // ==========================================
  // AUTHENTICATION & SESSION
  // ==========================================

  async function checkInitialAuth() {
    if (!window.API.isAuthenticated()) {
      renderUnauthenticated();
      return;
    }

    try {
      const user = await window.API.getMe();
      state.currentUser = user;
      renderAuthenticated(user);
      await loadProfiles();
      switchTab('tab-query');
    } catch (err) {
      console.warn('Sessão expirada ou inválida:', err);
      window.API.logout();
      renderUnauthenticated();
    }
  }

  function renderAuthenticated(user) {
    elements.authSection.classList.add('hidden');
    elements.userSession.classList.remove('hidden');
    elements.appNav.classList.remove('hidden');

    elements.navUsername.textContent = user.username;
    const profileName = user.perfil?.name || 'Sem perfil';
    elements.navProfileBadge.textContent = `Perfil: ${profileName}`;
    elements.queryActiveProfile.textContent = profileName;

    if (user.is_admin) {
      elements.navRoleBadge.textContent = 'Administrador';
      elements.navRoleBadge.className = 'badge badge-admin';
      elements.navTabAdmin.style.display = 'inline-flex';
      elements.adminAddProfileContainer.style.display = 'block';
    } else {
      elements.navRoleBadge.textContent = 'Usuário Comum';
      elements.navRoleBadge.className = 'badge badge-user';
      elements.navTabAdmin.style.display = 'none';
      elements.adminAddProfileContainer.style.display = 'none';
    }
  }

  function renderUnauthenticated() {
    state.currentUser = null;
    elements.authSection.classList.remove('hidden');
    elements.userSession.classList.add('hidden');
    elements.appNav.classList.add('hidden');

    elements.tabs.forEach((tab) => tab.classList.remove('active'));
    elements.loginUsernameInput.value = '';
    elements.loginPasswordInput.value = '';
  }

  // ==========================================
  // TAB NAVIGATION
  // ==========================================

  function switchTab(targetTabId) {
    elements.tabs.forEach((tab) => {
      if (tab.id === targetTabId) {
        tab.classList.add('active');
      } else {
        tab.classList.remove('active');
      }
    });

    elements.navTabButtons.forEach((btn) => {
      if (btn.getAttribute('data-tab') === targetTabId) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });

    if (targetTabId === 'tab-admin') {
      loadAdminUsers();
    } else if (targetTabId === 'tab-profiles') {
      renderProfilesCatalog();
    }
  }

  // ==========================================
  // PROFILES (SELECT p.name FROM perfil)
  // ==========================================

  async function loadProfiles() {
    try {
      state.profiles = await window.API.getProfiles();
      populateAdminProfileSelect();
      renderProfilesCatalog();
    } catch (err) {
      console.error('Erro ao carregar perfis:', err);
    }
  }

  function populateAdminProfileSelect() {
    const select = elements.adminNewProfileSelect;
    if (!select) return;

    select.innerHTML = '';
    state.profiles.forEach((p) => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = p.name;
      select.appendChild(opt);
    });
  }

  function renderProfilesCatalog() {
    const tbody = elements.profilesCatalogTbody;
    if (!tbody) return;

    tbody.innerHTML = '';
    elements.profilesCountBadge.textContent = `${state.profiles.length} perfis cadastrados`;

    if (!state.profiles.length) {
      tbody.innerHTML = '<tr><td colspan="4" class="text-center py-4">Nenhum perfil encontrado na base.</td></tr>';
      return;
    }

    state.profiles.forEach((p) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong>#${p.id}</strong></td>
        <td><span class="badge badge-profile">${escapeHtml(p.name)}</span></td>
        <td>${escapeHtml(p.description || 'Sem descrição')}</td>
        <td><code>${escapeHtml(p.created_at || 'Sistema')}</code></td>
      `;
      tbody.appendChild(tr);
    });
  }

  // ==========================================
  // SQL QUERY RUNNER
  // ==========================================

  async function executeSqlQuery() {
    const sql = elements.sqlInput.value.trim();
    if (!sql) {
      showToast('Por favor, informe uma instrução SQL para executar.', 'warning');
      return;
    }

    elements.btnRunQuery.disabled = true;
    elements.btnRunQuery.innerHTML = '<span class="btn-icon">⏳</span> Executando...';
    elements.queryError.classList.add('hidden');

    try {
      const result = await window.API.executeQuery(sql);
      state.lastQueryResult = result;

      // Update metrics
      elements.metricRows.textContent = result.row_count;
      elements.metricCols.textContent = result.columns.length;
      elements.metricTime.textContent = result.execution_time_ms;

      // Render Table
      renderQueryTable(result.columns, result.rows);

      elements.queryEmptyState.classList.add('hidden');
      elements.queryResultsWrapper.classList.remove('hidden');

      showToast(`Consulta executada com sucesso! (${result.row_count} registros em ${result.execution_time_ms}ms)`, 'success');
    } catch (err) {
      elements.queryErrorText.textContent = err.message || 'Erro ao processar consulta SQL.';
      elements.queryError.classList.remove('hidden');
      showToast(err.message || 'Erro na consulta SQL', 'danger');
    } finally {
      elements.btnRunQuery.disabled = false;
      elements.btnRunQuery.innerHTML = '<span class="btn-icon">▶</span> <span class="btn-text">Executar Consulta SQL</span>';
    }
  }

  function renderQueryTable(columns, rows) {
    const thead = elements.resultsThead;
    const tbody = elements.resultsTbody;

    thead.innerHTML = '';
    tbody.innerHTML = '';

    if (!columns.length || !rows.length) {
      tbody.innerHTML = `<tr><td class="text-center py-4">Consulta executada com sucesso, mas nenhum registro foi retornado.</td></tr>`;
      return;
    }

    // Header row
    const trHead = document.createElement('tr');
    columns.forEach((col) => {
      const th = document.createElement('th');
      th.textContent = col;
      trHead.appendChild(th);
    });
    thead.appendChild(trHead);

    // Body rows
    rows.forEach((row) => {
      const tr = document.createElement('tr');
      columns.forEach((col) => {
        const td = document.createElement('td');
        const val = row[col];
        if (val === null || val === undefined) {
          td.innerHTML = '<em style="color: #94a3b8;">NULL</em>';
        } else {
          td.textContent = String(val);
        }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
  }

  function filterTableResults(searchTerm) {
    const tbody = elements.resultsTbody;
    const trs = tbody.querySelectorAll('tr');
    const term = searchTerm.toLowerCase().trim();

    trs.forEach((tr) => {
      const text = tr.textContent.toLowerCase();
      if (!term || text.includes(term)) {
        tr.style.display = '';
      } else {
        tr.style.display = 'none';
      }
    });
  }

  function exportTableToCsv() {
    if (!state.lastQueryResult || !state.lastQueryResult.rows.length) {
      showToast('Nenhum dado disponível para exportação.', 'warning');
      return;
    }

    const { columns, rows } = state.lastQueryResult;
    const csvLines = [];

    // Header line
    csvLines.push(columns.map((col) => `"${col.replace(/"/g, '""')}"`).join(','));

    // Row lines
    rows.forEach((row) => {
      const line = columns.map((col) => {
        const val = row[col];
        if (val === null || val === undefined) return '""';
        return `"${String(val).replace(/"/g, '""')}"`;
      });
      csvLines.push(line.join(','));
    });

    const blob = new Blob([csvLines.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `consulta_sql_${Date.now()}.csv`;
    link.click();
    showToast('Download do arquivo CSV iniciado!', 'success');
  }

  // ==========================================
  // ADMIN PANEL (USERS & PROFILE MODIFICATION)
  // ==========================================

  async function loadAdminUsers() {
    if (!state.currentUser?.is_admin) return;

    elements.adminUsersTbody.innerHTML = `<tr><td colspan="6" class="text-center py-4">Carregando usuários...</td></tr>`;

    try {
      // Ensure profiles are loaded so dropdown has items from (select p.name from perfil)
      await loadProfiles();
      const users = await window.API.getAdminUsers();
      renderAdminUsersTable(users);
    } catch (err) {
      showToast(err.message || 'Erro ao carregar usuários.', 'danger');
    }
  }

  function renderAdminUsersTable(users) {
    const tbody = elements.adminUsersTbody;
    tbody.innerHTML = '';

    if (!users.length) {
      tbody.innerHTML = `<tr><td colspan="6" class="text-center py-4">Nenhum usuário cadastrado.</td></tr>`;
      return;
    }

    users.forEach((u) => {
      const tr = document.createElement('tr');

      // Profile modifier select: filled with results of (SELECT p.name FROM perfil)
      let optionsHtml = '';
      state.profiles.forEach((p) => {
        const isSelected = p.name === u.perfil_name ? 'selected' : '';
        optionsHtml += `<option value="${escapeHtml(p.name)}" ${isSelected}>${escapeHtml(p.name)}</option>`;
      });

      const roleBadge = u.is_admin
        ? `<span class="badge badge-admin">👑 Admin</span>`
        : `<span class="badge badge-user">👤 Comum</span>`;

      const currentProfileBadge = u.perfil_name
        ? `<span class="badge badge-profile">${escapeHtml(u.perfil_name)}</span>`
        : `<span class="badge badge-neutral">Nenhum</span>`;

      tr.innerHTML = `
        <td><strong>#${u.id}</strong></td>
        <td><strong>${escapeHtml(u.username)}</strong></td>
        <td>${roleBadge}</td>
        <td>${currentProfileBadge}</td>
        <td>
          <div style="display: flex; gap: 0.5rem; align-items: center;">
            <select class="form-control form-control-sm profile-select" id="select-user-profile-${u.id}">
              ${optionsHtml}
            </select>
            <button class="btn btn-primary btn-sm" onclick="window.TCCApp.saveUserProfile(${u.id})">
              💾 Salvar
            </button>
          </div>
        </td>
        <td style="text-align: right;">
          <div class="user-action-group">
            <button class="btn btn-secondary btn-sm" onclick="window.TCCApp.toggleAdminRole(${u.id}, ${!u.is_admin})" title="Alternar status de administrador">
              ${u.is_admin ? 'Tornar Comum' : 'Promover Admin'}
            </button>
            <button class="btn btn-danger btn-sm" onclick="window.TCCApp.deleteUser(${u.id}, '${escapeHtml(u.username)}')" title="Excluir Usuário" ${u.id === state.currentUser.id ? 'disabled' : ''}>
              🗑️
            </button>
          </div>
        </td>
      `;

      tbody.appendChild(tr);
    });
  }

  async function saveUserProfile(userId) {
    const select = document.getElementById(`select-user-profile-${userId}`);
    if (!select) return;

    const selectedProfileName = select.value;

    try {
      const res = await window.API.updateUserProfile(userId, selectedProfileName);
      showToast(res.message || 'Perfil do usuário atualizado com sucesso!', 'success');
      await loadAdminUsers();

      // If updating current user's profile, update the nav badge
      if (userId === state.currentUser?.id) {
        state.currentUser.perfil_name = selectedProfileName;
        elements.navProfileBadge.textContent = `Perfil: ${selectedProfileName}`;
        elements.queryActiveProfile.textContent = selectedProfileName;
      }
    } catch (err) {
      showToast(err.message || 'Erro ao alterar perfil do usuário.', 'danger');
    }
  }

  async function toggleAdminRole(userId, newAdminStatus) {
    if (userId === state.currentUser?.id && !newAdminStatus) {
      if (!confirm('Você está prestes a remover seu próprio status de administrador. Continuar?')) {
        return;
      }
    }

    try {
      await window.API.updateAdminUser(userId, { is_admin: newAdminStatus });
      showToast('Permissão de administrador alterada com sucesso!', 'success');
      await loadAdminUsers();
    } catch (err) {
      showToast(err.message || 'Erro ao atualizar permissão de admin.', 'danger');
    }
  }

  async function deleteUser(userId, username) {
    if (!confirm(`Tem certeza que deseja excluir o usuário "${username}"?`)) {
      return;
    }

    try {
      await window.API.deleteAdminUser(userId);
      showToast(`Usuário "${username}" foi excluído com sucesso.`, 'success');
      await loadAdminUsers();
    } catch (err) {
      showToast(err.message || 'Erro ao excluir usuário.', 'danger');
    }
  }

  // ==========================================
  // EVENT LISTENERS & SETUP
  // ==========================================

  function setupEventListeners() {
    // Auth Tab switching
    elements.btnShowLogin.addEventListener('click', () => {
      elements.btnShowLogin.classList.add('active');
      elements.btnShowRegister.classList.remove('active');
      elements.formLogin.classList.add('active');
      elements.formRegister.classList.remove('active');
    });

    elements.btnShowRegister.addEventListener('click', () => {
      elements.btnShowRegister.classList.add('active');
      elements.btnShowLogin.classList.remove('active');
      elements.formRegister.classList.add('active');
      elements.formLogin.classList.remove('active');
    });

    // Form: Login
    elements.formLogin.addEventListener('submit', async (e) => {
      e.preventDefault();
      const username = elements.loginUsernameInput.value.trim();
      const password = elements.loginPasswordInput.value;

      if (!username || !password) return;

      const submitBtn = document.getElementById('btn-submit-login');
      submitBtn.disabled = true;
      submitBtn.innerHTML = 'Autenticando via OAuth 2.0...';

      try {
        const data = await window.API.login(username, password);
        state.currentUser = data.user;
        renderAuthenticated(data.user);
        await loadProfiles();
        switchTab('tab-query');
        showToast(`Bem-vindo(a), ${data.user.username}!`, 'success');
      } catch (err) {
        showToast(err.message || 'Falha na autenticação.', 'danger');
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span class="btn-text">Entrar no Sistema</span>';
      }
    });

    // Form: Register
    elements.formRegister.addEventListener('submit', async (e) => {
      e.preventDefault();
      const username = elements.regUsernameInput.value.trim();
      const password = elements.regPasswordInput.value;
      const confirmPassword = elements.regConfirmPasswordInput.value;

      if (password !== confirmPassword) {
        showToast('As senhas digitadas não coincidem.', 'warning');
        return;
      }

      const submitBtn = document.getElementById('btn-submit-register');
      submitBtn.disabled = true;
      submitBtn.innerHTML = 'Cadastrando...';

      try {
        const data = await window.API.register(username, password);
        state.currentUser = data.user;
        renderAuthenticated(data.user);
        await loadProfiles();
        switchTab('tab-query');
        showToast('Cadastro realizado com sucesso com perfil padrão!', 'success');
      } catch (err) {
        showToast(err.message || 'Erro no cadastro de usuário.', 'danger');
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span class="btn-text">Confirmar Cadastro</span>';
      }
    });

    // Logout
    elements.btnLogout.addEventListener('click', () => {
      window.API.logout();
      renderUnauthenticated();
      showToast('Sessão encerrada com sucesso.', 'info');
    });

    // Nav tabs
    elements.navTabButtons.forEach((btn) => {
      btn.addEventListener('click', () => {
        const tabId = btn.getAttribute('data-tab');
        switchTab(tabId);
      });
    });

    // Query Run
    elements.btnRunQuery.addEventListener('click', executeSqlQuery);
    elements.btnClearQuery.addEventListener('click', () => {
      elements.sqlInput.value = '';
      elements.sqlInput.focus();
    });

    // Ctrl+Enter / Cmd+Enter shortcut
    elements.sqlInput.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        executeSqlQuery();
      }
    });

    // Result Filter & CSV Export
    elements.filterResults.addEventListener('input', (e) => {
      filterTableResults(e.target.value);
    });
    elements.btnExportCsv.addEventListener('click', exportTableToCsv);

    // Admin Refresh
    elements.btnRefreshUsers.addEventListener('click', loadAdminUsers);

    // Admin Create User Form
    elements.formAdminCreateUser.addEventListener('submit', async (e) => {
      e.preventDefault();
      const username = elements.adminNewUsername.value.trim();
      const password = elements.adminNewPassword.value;
      const perfilId = parseInt(elements.adminNewProfileSelect.value, 10);
      const isAdmin = elements.adminNewIsAdmin.checked;

      try {
        await window.API.createAdminUser({
          username,
          password,
          perfil_id: perfilId,
          is_admin: isAdmin,
        });

        showToast(`Usuário "${username}" criado com sucesso!`, 'success');
        elements.formAdminCreateUser.reset();
        await loadAdminUsers();
      } catch (err) {
        showToast(err.message || 'Erro ao criar usuário.', 'danger');
      }
    });

    // Admin Create Profile Form
    elements.formCreateProfile.addEventListener('submit', async (e) => {
      e.preventDefault();
      const name = elements.profileNameInput.value.trim();
      const description = elements.profileDescInput.value.trim();

      try {
        await window.API.createProfile({ name, description });
        showToast(`Perfil "${name}" criado com sucesso!`, 'success');
        elements.formCreateProfile.reset();
        await loadProfiles();
      } catch (err) {
        showToast(err.message || 'Erro ao criar perfil.', 'danger');
      }
    });

    // Expired auth listener
    window.addEventListener('auth:expired', () => {
      renderUnauthenticated();
      showToast('Sua sessão expirou. Por favor, entre novamente.', 'warning');
    });
  }

  // ==========================================
  // HELPER FUNCTIONS & GLOBAL EXPORTS
  // ==========================================

  function escapeHtml(text) {
    if (!text) return '';
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  window.TCCApp = {
    fillCredentials(user, pass) {
      elements.loginUsernameInput.value = user;
      elements.loginPasswordInput.value = pass;
      elements.loginUsernameInput.focus();
    },

    async loginOAuth(provider) {
      try {
        const dummyEmail = provider === 'google' ? 'aluno.tcc@google.com' : 'dev.tcc@github.com';
        const res = await window.API.loginOAuthSocial(provider, dummyEmail);
        state.currentUser = res.user;
        renderAuthenticated(res.user);
        await loadProfiles();
        switchTab('tab-query');
        showToast(`Autenticado com sucesso via ${provider.toUpperCase()} (OAuth 2.0)!`, 'success');
      } catch (err) {
        showToast(err.message || 'Falha no login OAuth 2.0', 'danger');
      }
    },

    setQuery(querySql) {
      elements.sqlInput.value = querySql;
      executeSqlQuery();
    },

    saveUserProfile(userId) {
      saveUserProfile(userId);
    },

    toggleAdminRole(userId, newAdmin) {
      toggleAdminRole(userId, newAdmin);
    },

    deleteUser(userId, username) {
      deleteUser(userId, username);
    },
  };

  // Initialize
  document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    checkInitialAuth();
  });
})();
