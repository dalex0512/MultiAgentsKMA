/** Admin dashboard — corpus, retrieve test, ops, security, benchmark */
const AdminDash = {
  agents: [],

  toast(msg, type = 'info') {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.className = 'admin-toast admin-toast--' + type;
    el.hidden = false;
    clearTimeout(AdminDash._toastT);
    AdminDash._toastT = setTimeout(() => { el.hidden = true; }, 4500);
  },

  async api(path, options = {}) {
    const res = await AdminAuth.apiFetch(path, options);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || data);
      throw new Error(detail || res.statusText);
    }
    return data;
  },

  fillAgentSelects() {
    const opts = this.agents.map(a =>
      `<option value="${a.id}">${a.name}</option>`
    ).join('');
    const filter = `<option value="">Tất cả</option>` + opts;
    ['upload-agent', 'retrieve-agent', 'doc-filter-agent'].forEach(id => {
      const el = document.getElementById(id);
      if (!el) return;
      if (id === 'doc-filter-agent') el.innerHTML = filter;
      else el.innerHTML = opts;
    });
    const grid = document.getElementById('disabled-agents-checks');
    grid.innerHTML = this.agents.map(a => `
      <label class="admin-check">
        <input type="checkbox" name="dis-agent" value="${a.id}"> ${a.name}
      </label>
    `).join('');
  },

  initNav() {
    document.querySelectorAll('.admin-nav-item').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.admin-nav-item').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.admin-panel').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById('panel-' + btn.dataset.panel).classList.add('active');
      });
    });
  },

  async loadProfile() {
    try {
      const me = await this.api('/admin/me');
      const name = (me.full_name || '').trim();
      document.getElementById('user-meta').textContent =
        name ? ('Xin chào, ' + name) : 'Học viện Kỹ thuật Mật mã';
    } catch {
      document.getElementById('user-meta').textContent = 'Học viện Kỹ thuật Mật mã';
    }
  },

  async loadHealth() {
    const grid = document.getElementById('health-grid');
    const routing = document.getElementById('routing-info');
    try {
      const h = await this.api('/admin/system/health');
      const banner = document.getElementById('config-banner');
      if (h.config_warnings && h.config_warnings.length) {
        banner.hidden = false;
        banner.innerHTML = '<i class="fas fa-triangle-exclamation"></i> ' + h.config_warnings.join(' · ');
      } else banner.hidden = true;

      const pg = h.postgres.ok
        ? '<span class="admin-badge ok">OK</span>'
        : `<span class="admin-badge err">Lỗi</span> ${h.postgres.error || ''}`;
      const qd = h.qdrant.ok
        ? `<span class="admin-badge ok">OK</span> ${h.qdrant.total_points ?? 0} points`
        : `<span class="admin-badge err">${h.qdrant.error || 'Lỗi'}</span>`;

      let agentRows = '';
      if (h.qdrant.per_agent_points) {
        agentRows = this.agents.map(a => {
          const n = h.qdrant.per_agent_points[a.id];
          return `<tr><td>${a.name}</td><td class="num">${n >= 0 ? n : '—'}</td></tr>`;
        }).join('');
      }

      grid.innerHTML = `
        <div class="admin-stat"><span class="label">PostgreSQL</span>${pg}</div>
        <div class="admin-stat"><span class="label">Qdrant (${h.qdrant.collection || ''})</span>${qd}</div>
        <div class="admin-stat admin-stat--wide">
          <span class="label">Chunk theo agent</span>
          <table class="admin-table compact"><tbody>${agentRows}</tbody></table>
        </div>`;

      const r = h.routing;
      routing.innerHTML = `
        <p><strong>Routing:</strong> TOP_K=${r.top_k}, T1=${r.threshold1}, T2=${r.threshold2},
        accuracy=${r.accuracy_mode}, fast=${r.fast_mode}</p>`;
    } catch (e) {
      grid.innerHTML = `<p class="admin-error">${e.message}</p>`;
    }
  },

  async loadDocuments() {
    const wrap = document.getElementById('docs-table-wrap');
    const agent = document.getElementById('doc-filter-agent').value;
    const q = agent ? `?agent_id=${encodeURIComponent(agent)}` : '';
    wrap.innerHTML = '<p class="admin-muted">Đang tải...</p>';
    try {
      const data = await this.api('/admin/documents' + q);
      if (!data.documents.length) {
        wrap.innerHTML = '<p class="admin-muted">Chưa có tài liệu trong thư mục agent.</p>';
        return;
      }
      const rows = data.documents.map(d => `
        <tr>
          <td>${d.agent_name}</td>
          <td><a href="${d.download_url}" target="_blank" rel="noopener">${d.filename}</a></td>
          <td class="num">${d.chunk_count ?? '—'}</td>
          <td class="num">${(d.file_size_bytes / 1024).toFixed(0)} KB</td>
          <td><span class="admin-badge">${d.status}</span></td>
          <td>
            <button type="button" class="admin-btn-danger admin-btn-sm" data-del="${d.agent_id}" data-fn="${encodeURIComponent(d.filename)}">Xóa</button>
          </td>
        </tr>`).join('');
      wrap.innerHTML = `
        <table class="admin-table">
          <thead><tr><th>Agent</th><th>File</th><th>Chunks</th><th>Size</th><th>TT</th><th></th></tr></thead>
          <tbody>${rows}</tbody>
        </table>`;
      wrap.querySelectorAll('[data-del]').forEach(btn => {
        btn.onclick = async () => {
          const aid = btn.dataset.del;
          const fn = decodeURIComponent(btn.dataset.fn);
          if (!confirm(`Xóa "${fn}" và chunk Qdrant?`)) return;
          try {
            await AdminAuth.apiFetch(`/admin/documents/${aid}/${encodeURIComponent(fn)}`, { method: 'DELETE' });
            this.toast('Đã xóa tài liệu', 'ok');
            this.loadDocuments();
          } catch (e) { this.toast(e.message, 'err'); }
        };
      });
    } catch (e) {
      wrap.innerHTML = `<p class="admin-error">${e.message}</p>`;
    }
  },

  async loadNews() {
    const wrap = document.getElementById('news-table-wrap');
    if (!wrap) return;
    wrap.innerHTML = '<p class="admin-muted">Đang tải...</p>';
    try {
      const data = await this.api('/admin/news');
      const items = data.items || [];
      if (!items.length) {
        wrap.innerHTML = '<p class="admin-muted">Chưa có tin mới nào.</p>';
        return;
      }
      wrap.innerHTML = `
        <table class="admin-table">
          <thead><tr><th>Tiêu đề</th><th>File</th><th>Cập nhật</th><th></th></tr></thead>
          <tbody>${items.map(it => `
            <tr>
              <td>
                <strong>${it.title || it.filename}</strong>
                ${it.summary ? `<div class="admin-muted">${it.summary}</div>` : ''}
              </td>
              <td><a href="${it.download_url}" target="_blank" rel="noopener">${it.filename}</a></td>
              <td>${(it.uploaded_at || '').replace('T', ' ').slice(0, 16)}</td>
              <td>
                <button type="button" class="admin-btn-danger admin-btn-sm" data-news-del="${encodeURIComponent(it.filename)}">Xóa</button>
              </td>
            </tr>
          `).join('')}</tbody>
        </table>
      `;
      wrap.querySelectorAll('[data-news-del]').forEach(btn => {
        btn.onclick = async () => {
          const filename = decodeURIComponent(btn.dataset.newsDel || '');
          if (!confirm(`Xóa tin "${filename}"?`)) return;
          try {
            await this.api('/admin/news/' + encodeURIComponent(filename), { method: 'DELETE' });
            this.toast('Đã xóa tin mới', 'ok');
            this.loadNews();
          } catch (e) {
            this.toast(e.message, 'err');
          }
        };
      });
    } catch (e) {
      wrap.innerHTML = `<p class="admin-error">${e.message}</p>`;
    }
  },

  async loadCatalog() {
    const wrap = document.getElementById('catalog-editor');
    try {
      const cat = await this.api('/admin/documents/catalog');
      const keys = Object.keys(cat).sort();
      if (!keys.length) {
        wrap.innerHTML = '<p class="admin-muted">Catalog trống — upload file vào biểu mẫu trước.</p>';
        return;
      }
      wrap.innerHTML = keys.map(fn => {
        const e = cat[fn] || {};
        return `
          <div class="admin-catalog-row" data-fn="${fn}">
            <strong>${fn}</strong>
            <input type="text" class="cat-display" value="${(e.display_name || '').replace(/"/g, '&quot;')}" placeholder="Tên hiển thị">
            <input type="text" class="cat-cat" value="${(e.category || '').replace(/"/g, '&quot;')}" placeholder="Loại">
            <button type="button" class="admin-btn-ghost admin-btn-sm cat-save">Lưu</button>
          </div>`;
      }).join('');
      wrap.querySelectorAll('.cat-save').forEach(btn => {
        btn.onclick = async () => {
          const row = btn.closest('.admin-catalog-row');
          const filename = row.dataset.fn;
          const body = {
            display_name: row.querySelector('.cat-display').value,
            category: row.querySelector('.cat-cat').value,
          };
          try {
            await this.api(`/admin/documents/catalog/${encodeURIComponent(filename)}`, {
              method: 'PUT',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(body),
            });
            this.toast('Đã lưu catalog', 'ok');
          } catch (e) { this.toast(e.message, 'err'); }
        };
      });
    } catch (e) {
      wrap.innerHTML = `<p class="admin-error">${e.message}</p>`;
    }
  },

  async loadAudit() {
    const wrap = document.getElementById('audit-log-wrap');
    try {
      const data = await this.api('/admin/security/audit-logs?limit=40');
      if (!data.logs.length) {
        wrap.innerHTML = '<p class="admin-muted">Chưa có nhật ký.</p>';
        return;
      }
      wrap.innerHTML = `
        <table class="admin-table compact">
          <thead><tr><th>Thời gian</th><th>User</th><th>IP</th><th>Hành động</th><th>OK</th><th>Chi tiết</th></tr></thead>
          <tbody>${data.logs.map(l => `
            <tr>
              <td>${(l.created_at || '').replace('T', ' ').slice(0, 19)}</td>
              <td>${l.username || '—'}</td>
              <td>${l.ip || '—'}</td>
              <td>${l.action}</td>
              <td>${l.success ? '✓' : '✗'}</td>
              <td class="detail">${(l.detail || '').slice(0, 80)}</td>
            </tr>`).join('')}
          </tbody>
        </table>`;
    } catch (e) {
      wrap.innerHTML = `<p class="admin-error">${e.message}</p>`;
    }
  },

  async loadOpsSettings() {
    const s = await this.api('/admin/system/settings');
    document.getElementById('maintenance-msg').value = s.maintenance_message || '';
    document.querySelectorAll('#disabled-agents-checks input').forEach(cb => {
      cb.checked = (s.disabled_agents || []).includes(cb.value);
    });
  },

  async loadAnalytics() {
    const days = parseInt(document.getElementById('analytics-days').value, 10) || 7;
    const sumEl = document.getElementById('analytics-summary');
    const barsEl = document.getElementById('analytics-bars');
    const recentEl = document.getElementById('analytics-recent');
    sumEl.innerHTML = '<p class="admin-muted">Đang tải...</p>';
    try {
      const d = await this.api('/admin/analytics/chat?days=' + days);
      sumEl.innerHTML = `
        <div class="admin-stat"><span class="label">Tổng câu hỏi</span><strong>${d.total_chats}</strong></div>
        <div class="admin-stat"><span class="label">TB thời gian (s)</span><strong>${d.avg_response_sec}</strong></div>
        <div class="admin-stat"><span class="label">Trong phạm vi</span><strong>${d.in_scope_rate}%</strong></div>
        <div class="admin-stat"><span class="label">Dùng stream</span><strong>${d.stream_share}%</strong></div>`;

      const agents = d.by_primary_agent || {};
      const max = Math.max(1, ...Object.values(agents));
      barsEl.innerHTML = Object.entries(agents).map(([k, v]) => `
        <div class="admin-bar-row">
          <span>${k}</span>
          <div class="admin-bar-track"><div class="admin-bar-fill" style="width:${Math.round(100 * v / max)}%"></div></div>
          <span class="num">${v}</span>
        </div>`).join('') || '<p class="admin-muted">Chưa có dữ liệu theo agent.</p>';

      if (!d.recent.length) {
        recentEl.innerHTML = '<p class="admin-muted">Chưa có log.</p>';
        return;
      }
      recentEl.innerHTML = `
        <table class="admin-table compact">
          <thead><tr><th>Thời gian</th><th>Agent</th><th>Pipeline</th><th>s</th><th>Câu hỏi</th></tr></thead>
          <tbody>${d.recent.map(r => `
            <tr>
              <td>${(r.created_at || '').replace('T', ' ').slice(0, 16)}</td>
              <td>${r.primary_agent || '—'}</td>
              <td>${r.pipeline || '—'}</td>
              <td class="num">${r.t_total}</td>
              <td>${r.question_preview}</td>
            </tr>`).join('')}
          </tbody>
        </table>`;
    } catch (e) {
      sumEl.innerHTML = `<p class="admin-error">${e.message}</p>`;
    }
  },

  async loadBenchRuns() {
    const wrap = document.getElementById('bench-runs');
    try {
      const data = await this.api('/admin/benchmark/runs');
      if (!data.runs.length) {
        wrap.innerHTML = '<p class="admin-muted">Chưa có lần chạy.</p>';
        return;
      }
      wrap.innerHTML = `
        <table class="admin-table compact">
          <thead><tr><th>File</th><th>Pass</th><th>Tỷ lệ</th></tr></thead>
          <tbody>${data.runs.map(r => `
            <tr><td>${r.file}</td><td>${r.passed}/${r.total}</td><td>${r.pass_rate}%</td></tr>`).join('')}
          </tbody>
        </table>`;
    } catch (e) {
      wrap.innerHTML = `<p class="admin-error">${e.message}</p>`;
    }
  },

  bindForms() {
    document.getElementById('upload-form').onsubmit = async (e) => {
      e.preventDefault();
      const btn = document.getElementById('upload-btn');
      btn.disabled = true;
      const fd = new FormData();
      fd.append('agent_id', document.getElementById('upload-agent').value);
      fd.append('file', document.getElementById('upload-file').files[0]);
      fd.append('overwrite', document.getElementById('upload-overwrite').checked ? 'true' : 'false');
      try {
        const res = await AdminAuth.apiFetch('/admin/documents/upload', { method: 'POST', body: fd });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Upload thất bại');
        this.toast(`Đã index ${data.chunk_count} chunks — ${data.filename}`, 'ok');
        document.getElementById('upload-file').value = '';
        this.loadDocuments();
        this.loadHealth();
      } catch (err) { this.toast(err.message, 'err'); }
      finally { btn.disabled = false; }
    };

    document.getElementById('docs-refresh').onclick = () => this.loadDocuments();
    document.getElementById('doc-filter-agent').onchange = () => this.loadDocuments();

    document.getElementById('reindex-agent-btn').onclick = async () => {
      const aid = document.getElementById('doc-filter-agent').value || document.getElementById('upload-agent').value;
      if (!aid) { this.toast('Chọn agent để re-index', 'err'); return; }
      if (!confirm(`Re-index toàn bộ file của agent "${aid}"?`)) return;
      try {
        const data = await this.api(`/admin/documents/reindex/${aid}`, { method: 'POST' });
        this.toast(`Re-index: ${data.chunks_indexed} chunks`, 'ok');
        this.loadDocuments();
        this.loadHealth();
      } catch (e) { this.toast(e.message, 'err'); }
    };

    document.getElementById('retrieve-form').onsubmit = async (e) => {
      e.preventDefault();
      const out = document.getElementById('retrieve-results');
      out.innerHTML = '<p class="admin-muted">Đang retrieve...</p>';
      try {
        const data = await this.api('/admin/system/retrieve-test', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query: document.getElementById('retrieve-query').value,
            agent_id: document.getElementById('retrieve-agent').value,
            top_k: 5,
          }),
        });
        if (!data.hits.length) {
          out.innerHTML = '<p class="admin-muted">Không có chunk phù hợp.</p>';
          return;
        }
        out.innerHTML = data.hits.map((h, i) => `
          <article class="admin-hit">
            <header>#${i + 1} score ${h.rank_score} · ${h.source} p.${h.page}</header>
            <p>${h.text_preview}</p>
          </article>`).join('');
      } catch (err) {
        out.innerHTML = `<p class="admin-error">${err.message}</p>`;
      }
    };

    document.getElementById('ops-form').onsubmit = async (e) => {
      e.preventDefault();
      const disabled = [...document.querySelectorAll('#disabled-agents-checks input:checked')].map(cb => cb.value);
      try {
        await this.api('/admin/system/settings', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            maintenance_message: document.getElementById('maintenance-msg').value,
            disabled_agents: disabled,
          }),
        });
        this.toast('Đã lưu cài đặt vận hành', 'ok');
      } catch (err) { this.toast(err.message, 'err'); }
    };

    document.getElementById('password-form').onsubmit = async (e) => {
      e.preventDefault();
      const fd = new FormData();
      fd.append('old_password', document.getElementById('pw-old').value);
      fd.append('new_password', document.getElementById('pw-new').value);
      try {
        await AdminAuth.apiFetch('/admin/security/change-password', { method: 'POST', body: fd });
        this.toast('Đổi mật khẩu thành công', 'ok');
        document.getElementById('password-form').reset();
        this.loadAudit();
      } catch (err) { this.toast(err.message, 'err'); }
    };

    document.getElementById('analytics-refresh').onclick = () => this.loadAnalytics();
    document.getElementById('analytics-days').onchange = () => this.loadAnalytics();

    document.getElementById('revoke-sessions-btn').onclick = async () => {
      if (!confirm('Thu hồi mọi token — bạn sẽ phải đăng nhập lại trên mọi thiết bị. Tiếp tục?')) return;
      try {
        const data = await this.api('/admin/security/revoke-sessions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: '{}',
        });
        this.toast(data.message, 'ok');
        await AdminAuth.logout();
        window.location.href = '/admin/login';
      } catch (e) { this.toast(e.message, 'err'); }
    };

    document.getElementById('bench-form').onsubmit = async (e) => {
      e.preventDefault();
      const jobEl = document.getElementById('bench-job');
      jobEl.textContent = 'Đang khởi chạy...';
      try {
        const start = await this.api('/admin/benchmark/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            tier: document.getElementById('bench-tier').value,
            limit: parseInt(document.getElementById('bench-limit').value, 10) || 3,
            base_url: window.location.origin,
          }),
        });
        const poll = async () => {
          const j = await this.api('/admin/benchmark/jobs/' + start.job_id);
          jobEl.innerHTML = `<p>Trạng thái: <strong>${j.status}</strong></p>`;
          if (j.status === 'running' || j.status === 'queued') {
            setTimeout(poll, 3000);
          } else if (j.summary) {
            jobEl.innerHTML += `<p>Kết quả: ${j.summary.passed}/${j.summary.total} (${j.summary.pass_rate}%)</p>`;
            this.loadBenchRuns();
          } else if (j.error) {
            jobEl.innerHTML += `<p class="admin-error">${j.error}</p>`;
          }
        };
        poll();
      } catch (err) {
        jobEl.innerHTML = `<p class="admin-error">${err.message}</p>`;
      }
    };

    const newsForm = document.getElementById('news-form');
    if (newsForm) {
      newsForm.onsubmit = async (e) => {
        e.preventDefault();
        const btn = document.getElementById('news-upload-btn');
        btn.disabled = true;
        try {
          const fileEl = document.getElementById('news-file');
          const file = (fileEl.files || [])[0];
          if (!file) throw new Error('Chọn file PDF trước khi đăng tin.');
          const fd = new FormData();
          fd.append('file', file);
          fd.append('title', document.getElementById('news-title').value.trim());
          const summary = document.getElementById('news-summary').value.trim();
          if (!summary) throw new Error('Vui lòng nhập mô tả ngắn cho tin mới.');
          fd.append('summary', summary);
          fd.append('overwrite', document.getElementById('news-overwrite').checked ? 'true' : 'false');
          const res = await AdminAuth.apiFetch('/admin/news/upload', { method: 'POST', body: fd });
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || 'Đăng tin thất bại');
          this.toast('Đăng tin mới thành công', 'ok');
          fileEl.value = '';
          document.getElementById('news-summary').value = '';
          this.loadNews();
        } catch (err) {
          this.toast(err.message, 'err');
        } finally {
          btn.disabled = false;
        }
      };
      const newsRefresh = document.getElementById('news-refresh');
      if (newsRefresh) newsRefresh.onclick = () => this.loadNews();
    }
  },

  async init() {
    if (!AdminAuth.requireAuth('/admin/login')) return;
    document.getElementById('logout-btn').onclick = async () => {
      await AdminAuth.logout();
      window.location.href = '/admin/login';
    };
    this.initNav();
    await this.loadProfile();
    const ag = await this.api('/admin/documents/agents');
    this.agents = ag.agents;
    this.fillAgentSelects();
    this.bindForms();
    await Promise.all([
      this.loadHealth(),
      this.loadAnalytics(),
      this.loadDocuments(),
      this.loadOpsSettings(),
      this.loadCatalog(),
      this.loadNews(),
      this.loadAudit(),
      this.loadBenchRuns(),
    ]);
  },
};

document.addEventListener('DOMContentLoaded', () => AdminDash.init());
