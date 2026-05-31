/**
 * Bảng điểm ảo — ghép dữ liệu QLDT + KTDBCL (dán từ clipboard).
 */

function normName(s) {
  return (s || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/\s+/g, ' ')
    .trim();
}

function parseNumber(val) {
  if (val == null) return null;
  const t = String(val).trim().replace(',', '.');
  if (!t || t === '-' || t === '—') return null;
  const n = parseFloat(t);
  return Number.isFinite(n) ? n : null;
}

/** Tín chỉ hợp lệ (1–15); bỏ icon/ký tự lạ khi copy từ web QLĐT. */
function parseCredits(val) {
  if (val == null) return '';
  const t = String(val).trim();
  if (!t || !/^\d{1,2}$/.test(t)) return '';
  const n = parseInt(t, 10);
  return n >= 1 && n <= 15 ? String(n) : '';
}

function parseTsvBlock(text) {
  const lines = text.trim().split(/\r?\n/).map(l => l.trim()).filter(Boolean);
  if (!lines.length) return { headers: [], rows: [] };

  let headerLineIdx = 0;
  for (let i = 0; i < Math.min(lines.length, 8); i++) {
    if (lines[i].includes('\t') && lines[i].split('\t').length >= 4) {
      headerLineIdx = i;
      break;
    }
  }

  const headers = lines[headerLineIdx].split('\t').map(h => h.trim());
  const rows = [];
  for (let i = headerLineIdx + 1; i < lines.length; i++) {
    const cols = lines[i].split('\t');
    if (cols.length < 3) continue;
    const row = {};
    headers.forEach((h, j) => {
      if (h) row[h] = (cols[j] ?? '').trim();
    });
    rows.push(row);
  }
  return { headers, rows };
}

function normalizeCourseLabel(name) {
  return String(name || '')
    .normalize('NFC')
    .replace(/\s+/g, ' ')
    .trim();
}

function cleanCourseName(name) {
  const raw = normalizeCourseLabel(name).replace(/\([^)]*\)/g, ' ');
  return normName(raw);
}

/** Cột mã ngắn (THI, TP1…) — khớp chính xác, tránh nhầm «Lần thi». */
function findColExact(headers, ...candidates) {
  for (const c of candidates) {
    const nc = normName(c);
    const hit = headers.find(h => normName(h) === nc);
    if (hit) return hit;
  }
  return null;
}

function findColFuzzy(headers, ...candidates) {
  for (const c of candidates) {
    const nc = normName(c);
    const hit = headers.find(h => {
      const nh = normName(h);
      if (!nh) return false;
      if (nh === nc) return true;
      if (nc.length >= 4 && (nh.includes(nc) || nc.includes(nh))) return true;
      return false;
    });
    if (hit) return hit;
  }
  return null;
}

/** Cột tín chỉ — khớp chính xác, tránh nhầm cột khác (fuzzy «so tc» ⊂ «ma…»). */
function findColSoTc(headers) {
  return (
    headers.find(h => {
      const nh = normName(h);
      return nh === 'so tc' || nh === 'so tin chi';
    }) || null
  );
}

function findColTenMon(headers) {
  return (
    headers.find(h => normName(h) === 'ten hoc phan') ||
    headers.find(h => {
      const nh = normName(h);
      return nh.includes('ten hoc phan') && !nh.startsWith('ma ');
    }) ||
    null
  );
}

function findColDiemThiQldt(headers) {
  return findColExact(headers, 'THI');
}

function findColDiemThiKtdbcl(headers) {
  return headers.find(h => {
    const nh = normName(h);
    return nh === 'diem thi' || (nh.includes('diem thi') && !nh.startsWith('lan'));
  }) || null;
}

function parseQldt(text) {
  const { headers, rows } = parseTsvBlock(text);
  const colName = findColTenMon(headers);
  const colCode = findColFuzzy(headers, 'Mã học phần', 'Ma hoc phan');
  const colTc = findColSoTc(headers);
  const colTp1 = findColExact(headers, 'TP1');
  const colTp2 = findColExact(headers, 'TP2');
  const colThi = findColDiemThiQldt(headers);
  const colTk = findColExact(headers, 'TKHP') || findColFuzzy(headers, 'TK');
  const colLan = findColLanThiQldt(headers);

  if (!colName) return { error: 'Không nhận dạng được cột «Tên học phần» trong dữ liệu QLDT.' };

  const courses = [];
  for (const r of rows) {
    const name = normalizeCourseLabel(r[colName]);
    if (!name) continue;
    courses.push({
      code: colCode ? r[colCode] : '',
      name,
      nameKey: cleanCourseName(name),
      credits: colTc ? parseCredits(r[colTc]) : '',
      tp1: colTp1 ? parseNumber(r[colTp1]) : null,
      tp2: colTp2 ? parseNumber(r[colTp2]) : null,
      thi: colThi ? parseNumber(r[colThi]) : null,
      tkhp: colTk ? parseNumber(r[colTk]) : null,
      lanThi: colLan ? r[colLan] : '',
      letter: '',
      source: 'qldt',
    });
  }
  return { courses: dedupeQldt(courses) };
}

function findColLanThiQldt(headers) {
  const hit = headers.find(h => normName(h) === 'lan thi');
  if (hit) return hit;
  return headers.find(h => {
    const nh = normName(h);
    return nh.includes('lan thi') && !nh.includes('lan hoc');
  }) || null;
}

function findColLanKtdbcl(headers) {
  const exact = headers.find(h => normName(h) === 'lan');
  if (exact) return exact;
  return findColExact(headers, 'Lần') || null;
}

function formatLanThi(val) {
  if (val == null || val === '') return '—';
  const s = String(val).trim();
  return s || '—';
}

function parseLanThiNum(val) {
  const n = parseInt(String(val ?? '').trim(), 10);
  return Number.isFinite(n) && n > 0 ? n : 0;
}

/** Cùng môn nhiều dòng: giữ lần thi cao nhất (ưu tiên lần 2). */
function pickLatestAttempt(prev, next) {
  const lanP = parseLanThiNum(prev.lanThi);
  const lanN = parseLanThiNum(next.lanThi);
  if (lanN > lanP) return next;
  if (lanN < lanP) return prev;
  return (next.tkhp ?? -1) >= (prev.tkhp ?? -1) ? next : prev;
}

function dedupeQldt(courses) {
  const map = new Map();
  for (const c of courses) {
    const key = c.code || c.nameKey;
    const prev = map.get(key);
    map.set(key, prev ? pickLatestAttempt(prev, c) : c);
  }
  return [...map.values()];
}

function dedupeKtdbclByLatestAttempt(courses) {
  const map = new Map();
  for (const c of courses) {
    const key = c.nameKey;
    const prev = map.get(key);
    map.set(key, prev ? pickLatestAttempt(prev, c) : c);
  }
  return [...map.values()];
}

function parseKtdbcl(text) {
  const { headers, rows } = parseTsvBlock(text);
  const colName = findColExact(headers, 'Môn thi') || findColFuzzy(headers, 'Môn thi', 'Mon thi');
  const colTp1 = findColExact(headers, 'TP1');
  const colTp2 = findColExact(headers, 'TP2');
  const colThi = findColDiemThiKtdbcl(headers);
  const colHp = findColFuzzy(headers, 'Điểm HP', 'Diem HP');
  const colLetter = findColFuzzy(headers, 'Điểm chữ', 'Diem chu');
  const colLan = findColLanKtdbcl(headers);

  if (!colName) return { error: 'Không nhận dạng được cột «Môn thi» trong dữ liệu KTDBCL.' };

  const courses = [];
  for (const r of rows) {
    const name = normalizeCourseLabel(r[colName]);
    if (!name || normName(name) === 'lua chon') continue;
    courses.push({
      name,
      nameKey: cleanCourseName(name),
      tp1: colTp1 ? parseNumber(r[colTp1]) : null,
      tp2: colTp2 ? parseNumber(r[colTp2]) : null,
      thi: colThi ? parseNumber(r[colThi]) : null,
      tkhp: colHp ? parseNumber(r[colHp]) : null,
      letter: colLetter ? (r[colLetter] || '').trim() : '',
      lanThi: colLan ? r[colLan] : '',
      source: 'ktdbcl',
    });
  }
  return { courses: dedupeKtdbclByLatestAttempt(courses) };
}

function rowFromQldt(q, seq) {
  return {
    id: 'r-' + seq,
    code: q.code,
    name: q.name,
    credits: q.credits,
    lanThi: formatLanThi(q.lanThi),
    tp1: q.tp1,
    tp2: q.tp2,
    thi: q.thi,
    tkhp: q.tkhp,
    letter: '',
    checked: true,
  };
}

function rowFromKtdbclOnly(k, seq, m) {
  const q = m?.q ?? null;
  return {
    id: 'r-' + seq,
    code: q?.code || '',
    name: k.name,
    credits: q?.credits || '',
    lanThi: formatLanThi(k.lanThi || q?.lanThi),
    tp1: k.tp1,
    tp2: k.tp2,
    thi: k.thi,
    tkhp: k.tkhp,
    letter: k.letter || '',
    letterEstimated: false,
    hasKtdbcl: true,
    checked: true,
  };
}

/**
 * Gộp QLDT + KTDBCL: mỗi môn một dòng; trùng tên học phần → một dòng (điểm KTDBCL + tín chỉ QLDT).
 */
function mergeGrades(qldtCourses, ktdbclCourses) {
  const qPool = dedupeQldt([...qldtCourses]);
  const kList = dedupeKtdbclByLatestAttempt([...ktdbclCourses]);

  if (!kList.length) {
    return finalizeRows(qPool.map((q, i) => rowFromQldt(q, i)));
  }
  if (!qPool.length) {
    return finalizeRows(kList.map((k, i) => rowFromKtdbclOnly(k, i, null)));
  }

  const qByName = new Map(qPool.map(q => [q.nameKey, q]));
  const usedNames = new Set();
  const merged = [];

  for (const k of kList) {
    const q = qByName.get(k.nameKey);
    const row = rowFromKtdbclOnly(k, merged.length, q ? { q } : null);
    if (q) {
      usedNames.add(k.nameKey);
      row.credits = q.credits || '';
      row.code = q.code || '';
      if (row.lanThi === '—' && q.lanThi) row.lanThi = formatLanThi(q.lanThi);
    }
    merged.push(row);
  }

  for (const q of qPool) {
    if (usedNames.has(q.nameKey)) continue;
    merged.push(rowFromQldt(q, merged.length));
  }

  merged.forEach((r, i) => {
    r.id = 'r-' + i;
  });

  return finalizeRows(merged);
}

/** Đếm môn trùng tên (sau chuẩn hóa) giữa hai nguồn. */
function countNameOverlap(qCourses, kCourses) {
  const qKeys = new Set(qCourses.map(q => q.nameKey));
  let n = 0;
  for (const k of kCourses) {
    if (qKeys.has(k.nameKey)) n += 1;
  }
  return n;
}

/** Bổ sung điểm chữ từ KTDBCL hoặc ước lượng từ điểm TK khi chưa khớp tên môn. */
function finalizeRows(rows) {
  return rows.map(r => {
    const out = { ...r };
    if (!out.letter && out.tkhp != null) {
      out.letter = inferLetter(out.tkhp);
      out.letterEstimated = true;
    }
    return out;
  });
}

function fmtScore(n) {
  if (n == null || n === '') return '—';
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}

function letterGradeClass(letter) {
  const l = (letter || '').trim().toUpperCase();
  if (!l) return '';
  if (l === 'A' || l === 'A+') return 'gl-a';
  if (l.startsWith('B')) return 'gl-b';
  if (l.startsWith('C')) return 'gl-c';
  if (l.startsWith('D')) return 'gl-d';
  if (l === 'F') return 'gl-f';
  return 'gl-other';
}

function scoreClass(kind) {
  if (kind === 'tp') return 'gs-tp';
  if (kind === 'final') return 'gs-final';
  return '';
}

const STORAGE_KEY = 'kma_bang_diem_saved';

function escapeAttr(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;');
}

function fmtInputScore(n) {
  if (n == null || n === '') return '';
  return Number.isInteger(n) ? String(n) : String(n);
}

function readRowsFromDom() {
  const rows = currentRows.map(r => ({ ...r }));
  document.querySelectorAll('#grade-tbody tr').forEach(tr => {
    const idx = +tr.dataset.idx;
    if (!Number.isFinite(idx) || !rows[idx]) return;
    tr.querySelectorAll('.cell-in').forEach(inp => {
      const f = inp.dataset.field;
      const raw = inp.value.trim();
      if (f === 'name' || f === 'credits' || f === 'letter' || f === 'lanThi') {
        rows[idx][f] = raw;
      } else if (f === 'tp1' || f === 'tp2' || f === 'thi' || f === 'tkhp') {
        rows[idx][f] = parseNumber(raw);
      }
    });
    if (rows[idx].letter) rows[idx].letterEstimated = false;
  });
  return rows;
}

/** Đọc bảng, ước lượng điểm chữ, cập nhật GPA và lưu tự động (debounce). */
function syncTableState(options = {}) {
  const { persist = true } = options;
  if (!document.querySelector('#grade-tbody tr')) {
    currentRows = [];
    if (cpaApi) cpaApi.refreshLiveStats([]);
    return [];
  }

  let rows = finalizeRows(readRowsFromDom());
  currentRows = rows;

  document.querySelectorAll('#grade-tbody tr').forEach(tr => {
    const idx = +tr.dataset.idx;
    const row = rows[idx];
    if (!row) return;
    const letterInp = tr.querySelector('.cell-in[data-field="letter"]');
    if (!letterInp) return;
    if (row.letterEstimated) {
      letterInp.value = row.letter || '';
      const td = letterInp.closest('td');
      if (td) {
        td.className = `col-letter ${letterGradeClass(row.letter)}`;
        td.title = 'Ước lượng từ điểm TK';
      }
      updateLetterCellStyle(letterInp);
    }
  });

  if (cpaApi) cpaApi.refreshLiveStats(rows);
  if (persist) scheduleAutoSave();
  return rows;
}

function scheduleAutoSave() {
  clearTimeout(persistDebounceTimer);
  persistDebounceTimer = setTimeout(() => {
    if (!currentRows.length) {
      try {
        localStorage.removeItem(STORAGE_KEY);
      } catch {
        /* ignore */
      }
      return;
    }
    saveGradesToStorage(true);
  }, 500);
}

function scheduleSyncFromInput() {
  clearTimeout(syncDebounceTimer);
  syncDebounceTimer = setTimeout(() => syncTableState(), 280);
}

function updateLetterCellStyle(inp) {
  const td = inp.closest('td');
  if (!td) return;
  td.className = `col-letter ${letterGradeClass(inp.value)}`;
}

function renderTable(rows) {
  const tbody = document.getElementById('grade-tbody');
  const empty = document.getElementById('grade-empty');
  const wrap = document.getElementById('grade-result');
  const btnSave = document.getElementById('btn-save');
  tbody.innerHTML = '';

  if (!rows.length) {
    wrap.hidden = true;
    empty.hidden = false;
    setGradeToolsVisible(false);
    return;
  }

  empty.hidden = true;
  wrap.hidden = false;
  setGradeToolsVisible(true);
  if (cpaApi) cpaApi.refreshLiveStats(rows);

  rows.forEach((row, idx) => {
    const tr = document.createElement('tr');
    tr.dataset.idx = String(idx);
    tr.dataset.id = row.id;
    const est = row.letterEstimated ? ' title="Ước lượng từ điểm TK"' : '';
    tr.innerHTML = `
      <td class="col-check"><input type="checkbox" class="row-check" data-idx="${idx}" ${row.checked ? 'checked' : ''} aria-label="Chọn dòng"></td>
      <td class="col-name"><input type="text" class="cell-in cell-name" data-field="name" value="${escapeAttr(row.name)}" aria-label="Tên môn học"></td>
      <td class="col-tc"><input type="text" class="cell-in cell-tc" data-field="credits" value="${escapeAttr(row.credits || '')}" placeholder="—" inputmode="numeric" aria-label="Tín chỉ"></td>
      <td class="col-lan"><input type="text" class="cell-in cell-lan" data-field="lanThi" value="${escapeAttr(row.lanThi && row.lanThi !== '—' ? row.lanThi : '')}" placeholder="—" inputmode="numeric" aria-label="Lần thi"></td>
      <td class="col-num"><input type="text" class="cell-in cell-num" data-field="tp1" value="${escapeAttr(fmtInputScore(row.tp1))}" inputmode="decimal" aria-label="TP1"></td>
      <td class="col-num"><input type="text" class="cell-in cell-num" data-field="tp2" value="${escapeAttr(fmtInputScore(row.tp2))}" inputmode="decimal" aria-label="TP2"></td>
      <td class="col-num"><input type="text" class="cell-in cell-num" data-field="thi" value="${escapeAttr(fmtInputScore(row.thi))}" inputmode="decimal" aria-label="Điểm thi"></td>
      <td class="col-num"><input type="text" class="cell-in cell-num" data-field="tkhp" value="${escapeAttr(fmtInputScore(row.tkhp))}" inputmode="decimal" aria-label="Điểm TK"></td>
      <td class="col-letter ${letterGradeClass(row.letter)}"${est}><input type="text" class="cell-in cell-letter" data-field="letter" value="${escapeAttr(row.letter || '')}" placeholder="—" maxlength="3" aria-label="Điểm chữ"></td>
      <td class="col-del"><button type="button" class="btn-del" data-idx="${idx}" title="Xóa dòng" aria-label="Xóa môn học"><i class="fas fa-trash-can"></i></button></td>
    `;
    tbody.appendChild(tr);
  });

  bindTableEvents(rows);
  updateSelectAll();
}

function escapeHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

let currentRows = [];
let cpaApi = null;
let manualRowSeq = 0;
let syncDebounceTimer = null;
let persistDebounceTimer = null;

function createEmptyRow() {
  manualRowSeq += 1;
  return {
    id: 'r-manual-' + manualRowSeq,
    code: '',
    name: '',
    credits: '',
    lanThi: '',
    tp1: null,
    tp2: null,
    thi: null,
    tkhp: null,
    letter: '',
    letterEstimated: false,
    checked: true,
  };
}

function addCourseRow() {
  currentRows = document.querySelector('#grade-tbody tr')
    ? readRowsFromDom()
    : [];
  currentRows.push(createEmptyRow());
  renderTable(currentRows);
  scheduleAutoSave();
  requestAnimationFrame(() => {
    const inputs = document.querySelectorAll('#grade-tbody .cell-name');
    const last = inputs[inputs.length - 1];
    last?.focus();
    last?.select();
    const scroller = document.getElementById('grade-table-scroll');
    if (scroller) scroller.scrollTop = scroller.scrollHeight;
  });
}

function setGradeToolsVisible(visible) {
  const ids = ['btn-save', 'btn-cpa-toggle', 'btn-export-excel', 'stats-strip'];
  ids.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.hidden = !visible;
  });
}

function fmtExportScore(n) {
  if (n == null || n === '') return '';
  return Number.isInteger(n) ? n : Number(n.toFixed(1));
}

function exportGradesToExcel() {
  const rows = readRowsFromDom();
  if (!rows.length) {
    showSaveStatus('Không có dữ liệu để xuất Excel.', true);
    return;
  }
  if (typeof XLSX === 'undefined') {
    showSaveStatus('Không tải được thư viện Excel. Kiểm tra mạng và tải lại trang.', true);
    return;
  }

  const sheetRows = rows.map((r, i) => ({
    STT: i + 1,
    'Môn học': r.name || '',
    'Tín chỉ': r.credits || '',
    'Lần thi': r.lanThi && r.lanThi !== '—' ? r.lanThi : '',
    'GK (TP1)': fmtExportScore(r.tp1),
    'CC (TP2)': fmtExportScore(r.tp2),
    'Điểm CK': fmtExportScore(r.thi),
    'Điểm TK': fmtExportScore(r.tkhp),
    'Điểm chữ': (r.letter || '') + (r.letterEstimated ? '*' : ''),
    'Tính GPA': r.checked ? 'Có' : 'Không',
  }));

  const ws = XLSX.utils.json_to_sheet(sheetRows);
  ws['!cols'] = [
    { wch: 5 },
    { wch: 42 },
    { wch: 8 },
    { wch: 8 },
    { wch: 8 },
    { wch: 8 },
    { wch: 8 },
    { wch: 8 },
    { wch: 8 },
    { wch: 10 },
  ];

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Bảng điểm');

  const date = new Date().toISOString().slice(0, 10);
  XLSX.writeFile(wb, `Bang_diem_KMA_${date}.xlsx`);
  showSaveStatus(`Đã xuất ${rows.length} dòng ra file Bang_diem_KMA_${date}.xlsx`);
}

function bindTableEvents(rows) {
  currentRows = rows;
  document.querySelectorAll('.row-check').forEach(cb => {
    cb.addEventListener('change', e => {
      const i = +e.target.dataset.idx;
      if (currentRows[i]) currentRows[i].checked = e.target.checked;
      updateSelectAll();
      syncTableState();
    });
  });
  document.querySelectorAll('.btn-del').forEach(btn => {
    btn.addEventListener('click', e => {
      currentRows = readRowsFromDom();
      const i = +e.currentTarget.dataset.idx;
      currentRows.splice(i, 1);
      renderTable(currentRows);
      syncTableState();
    });
  });
  const scoreFields = new Set(['tp1', 'tp2', 'thi', 'tkhp', 'credits', 'name', 'letter', 'lanThi']);
  document.querySelectorAll('.cell-in').forEach(inp => {
    const field = inp.dataset.field;
    inp.addEventListener('blur', () => syncTableState());
    if (scoreFields.has(field)) {
      inp.addEventListener('input', () => {
        if (field === 'letter') updateLetterCellStyle(inp);
        scheduleSyncFromInput();
      });
    }
  });
}

function showSaveStatus(msg, isError) {
  const el = document.getElementById('save-status');
  if (!el) return;
  el.textContent = msg;
  el.hidden = false;
  el.classList.toggle('is-error', !!isError);
}

function saveGradesToStorage(auto) {
  try {
    const rows = currentRows.length ? currentRows : finalizeRows(readRowsFromDom());
    currentRows = rows;
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ savedAt: new Date().toISOString(), rows }),
    );
    const msg = auto
      ? `Đã tự động lưu ${rows.length} dòng bảng điểm.`
      : `Đã lưu ${rows.length} dòng bảng điểm trên trình duyệt này.`;
    showSaveStatus(msg);
    if (cpaApi) cpaApi.refreshLiveStats(rows);
    return true;
  } catch (e) {
    showSaveStatus('Không lưu được (bộ nhớ trình duyệt đầy hoặc bị chặn).', true);
    return false;
  }
}

function loadGradesFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (!data?.rows?.length) return null;
    return data.rows.map((r, i) => ({
      ...r,
      id: r.id || 'r-' + i,
      checked: r.checked !== false,
    }));
  } catch {
    return null;
  }
}

function updateSelectAll() {
  const all = document.getElementById('check-all');
  const boxes = document.querySelectorAll('.row-check');
  if (!all || !boxes.length) return;
  const checked = [...boxes].filter(b => b.checked).length;
  all.checked = checked === boxes.length;
  all.indeterminate = checked > 0 && checked < boxes.length;
}

function initBangDiem() {
  if (typeof initCpaTargetUi === 'function') {
    cpaApi = initCpaTargetUi(() => {
      if (document.querySelector('#grade-tbody tr')) return readRowsFromDom();
      return currentRows;
    });
  }

  const btn = document.getElementById('btn-merge');
  const qldtEl = document.getElementById('paste-qldt');
  const ktdbclEl = document.getElementById('paste-ktdbcl');
  const errEl = document.getElementById('merge-error');
  const checkAll = document.getElementById('check-all');

  btn.addEventListener('click', () => {
    errEl.hidden = true;
    const qText = qldtEl.value.trim();
    const kText = ktdbclEl.value.trim();

    if (!qText && !kText) {
      errEl.textContent = 'Vui lòng dán ít nhất một trong hai bảng điểm (QLDT hoặc KTDBCL).';
      errEl.hidden = false;
      return;
    }

    let qCourses = [];
    let kCourses = [];

    if (qText) {
      const q = parseQldt(qText);
      if (q.error) {
        errEl.textContent = q.error;
        errEl.hidden = false;
        return;
      }
      qCourses = q.courses;
    }

    if (kText) {
      const k = parseKtdbcl(kText);
      if (k.error) {
        errEl.textContent = k.error;
        errEl.hidden = false;
        return;
      }
      kCourses = k.courses;
    }

    if (!qCourses.length && !kCourses.length) {
      errEl.textContent = 'Không đọc được dòng điểm nào. Kiểm tra lại dữ liệu đã dán.';
      errEl.hidden = false;
      return;
    }

    const merged = mergeGrades(
      qCourses.length ? qCourses : [],
      kCourses.length ? kCourses : [],
    );

    if (qCourses.length && kCourses.length) {
      const overlap = countNameOverlap(qCourses, kCourses);
      const kN = dedupeKtdbclByLatestAttempt(kCourses).length;
      const qN = dedupeQldt(qCourses).length;
      let info =
        `Đã gộp ${merged.length} dòng: ${kN} môn KTDBCL + ${qN} môn QLDT`;
      if (overlap > 0) {
        info += `, ${overlap} môn trùng tên (một dòng, có tín chỉ từ QLDT).`;
      } else {
        info +=
          '. Không có môn trùng tên giữa hai bảng — tín chỉ chỉ hiện ở các dòng chỉ có trên QLDT (cuối bảng).';
      }
      errEl.textContent = info;
      errEl.hidden = false;
      errEl.classList.add('merge-info');
    } else {
      errEl.classList.remove('merge-info');
    }

    renderTable(merged);
    syncTableState();
    const saveSt = document.getElementById('save-status');
    if (saveSt) saveSt.hidden = true;
    const scroller = document.getElementById('grade-table-scroll');
    if (scroller) scroller.scrollTop = 0;
  });

  if (checkAll) {
    checkAll.addEventListener('change', e => {
      document.querySelectorAll('.row-check').forEach(cb => {
        cb.checked = e.target.checked;
        const i = +cb.dataset.idx;
        if (currentRows[i]) currentRows[i].checked = e.target.checked;
      });
      syncTableState();
    });
  }

  document.getElementById('btn-add-row')?.addEventListener('click', addCourseRow);

  document.getElementById('btn-export-excel')?.addEventListener('click', () => {
    currentRows = readRowsFromDom();
    exportGradesToExcel();
  });

  document.getElementById('btn-save')?.addEventListener('click', () => {
    syncTableState({ persist: false });
    if (!currentRows.length) {
      showSaveStatus('Chưa có bảng điểm để lưu.', true);
      return;
    }
    saveGradesToStorage(false);
  });

  document.getElementById('btn-clear')?.addEventListener('click', () => {
    qldtEl.value = '';
    ktdbclEl.value = '';
    currentRows = [];
    document.getElementById('grade-tbody').innerHTML = '';
    document.getElementById('grade-result').hidden = true;
    document.getElementById('grade-empty').hidden = false;
    setGradeToolsVisible(false);
    if (cpaApi?.closeCpaModal) cpaApi.closeCpaModal();
    errEl.hidden = true;
    errEl.classList.remove('merge-info');
    const saveSt = document.getElementById('save-status');
    if (saveSt) saveSt.hidden = true;
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
  });

  const saved = loadGradesFromStorage();
  if (saved?.length) {
    const rows = finalizeRows(saved);
    renderTable(rows);
    if (cpaApi) cpaApi.refreshLiveStats(rows);
    showSaveStatus(
      `Đã khôi phục bản lưu (${saved.length} dòng). Thay đổi được tự động lưu khi bạn sửa bảng.`,
    );
  }
}

/** Ước lượng điểm chữ khi chỉ có KTDBCL (không có QLDT) */
function inferLetter(tk) {
  if (tk == null) return '';
  if (tk >= 9.0) return 'A';
  if (tk >= 8.5) return 'A';
  if (tk >= 8.0) return 'B+';
  if (tk >= 7.0) return 'B';
  if (tk >= 6.5) return 'C+';
  if (tk >= 5.5) return 'C';
  if (tk >= 5.0) return 'D+';
  if (tk >= 4.0) return 'D';
  return 'F';
}

document.addEventListener('DOMContentLoaded', initBangDiem);
