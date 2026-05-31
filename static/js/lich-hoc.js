/**
 * Lịch học — dán bảng từ QLĐT, xuất bảng theo dõi & thời khóa biểu.
 */

const STORAGE_KEY = 'kma-lich-hoc-v1';
const DAY_LABELS = { 2: 'Thứ 2', 3: 'Thứ 3', 4: 'Thứ 4', 5: 'Thứ 5', 6: 'Thứ 6', 7: 'Thứ 7', 8: 'Chủ nhật' };
const MAX_PERIOD = 16;

const RE_WEEK = /^Từ\s+(\d{2}\/\d{2}\/\d{4})\s+đến\s+(\d{2}\/\d{2}\/\d{4}):\s*\((\d+)\)/i;
const RE_SLOT = /Thứ\s+(\d)\s+tiết\s+([\d,]+)\s*\((LT|TH)\)/gi;
const RE_ROW_START = /^(\d+)\t(.+)/;
const RE_STATS_TAIL = /\t+(\d+)\s*\t+(\d+)\s*\t+(\d+)\s*$/;
const RE_LOCATION = /^\d{3}[-_][A-Za-z0-9]+|^\d{3}_[A-Za-z0-9]+|^\(\d/;

function parsePeriods(raw) {
  return String(raw || '')
    .split(',')
    .map(s => parseInt(s.trim(), 10))
    .filter(n => Number.isFinite(n) && n >= 1 && n <= MAX_PERIOD);
}

function shortClassName(full) {
  const m = String(full || '').match(/^(.+?)\s*\([^)]+\)\s*$/);
  return m ? m[1].trim() : String(full || '').trim();
}

function classCode(full) {
  const m = String(full || '').match(/\(([^)]+)\)\s*$/);
  return m ? m[1].trim() : '';
}

function splitRowBlocks(text) {
  const lines = String(text || '').replace(/\r\n/g, '\n').split('\n');
  const blocks = [];
  let cur = null;

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    if (/^tổng\b/i.test(trimmed) || /^\s*tổng\t/i.test(line)) continue;

    const m = line.match(RE_ROW_START);
    if (m) {
      const stt = parseInt(m[1], 10);
      if (stt >= 1 && stt <= 99) {
        if (cur) blocks.push(cur);
        cur = { stt, lines: [line] };
        continue;
      }
    }
    if (cur) cur.lines.push(line);
  }
  if (cur) blocks.push(cur);
  return blocks;
}

function extractTail(scheduleAndTail) {
  const lines = scheduleAndTail.split('\n');
  let tailIdx = -1;
  for (let i = lines.length - 1; i >= 0; i--) {
    if (RE_STATS_TAIL.test(lines[i])) {
      tailIdx = i;
      break;
    }
  }
  if (tailIdx < 0) {
    return { scheduleText: scheduleAndTail.trim(), tailLines: [] };
  }
  return {
    scheduleText: lines.slice(0, tailIdx).join('\n').trim(),
    tailLines: lines.slice(tailIdx),
  };
}

function parseTailLines(tailLines) {
  const locationParts = [];
  let lecturer = '';
  let capacity = '';
  let enrolled = '';
  let credits = '';
  let note = '';

  if (!tailLines.length) {
    return { location: '', locationDetail: '', lecturer, capacity, enrolled, credits, note };
  }

  const last = tailLines[tailLines.length - 1];
  const cols = last.split('\t').map(c => c.trim());

  const numIdx = cols.findIndex((c, i) => {
    if (!/^\d+$/.test(c)) return false;
    return cols.slice(i, i + 3).every(x => /^\d+$/.test(x));
  });

  if (numIdx >= 0) {
    capacity = cols[numIdx] || '';
    enrolled = cols[numIdx + 1] || '';
    credits = cols[numIdx + 2] || '';
    note = cols.slice(numIdx + 3).filter(Boolean).join(' ');
    const before = cols.slice(0, numIdx).filter(Boolean);
    if (before.length >= 2 && !RE_LOCATION.test(before[0])) {
      lecturer = before[before.length - 1];
      locationParts.push(...before.slice(0, -1));
    } else if (before.length === 1) {
      if (RE_LOCATION.test(before[0]) || /ta\d/i.test(before[0])) {
        locationParts.push(before[0]);
      } else {
        lecturer = before[0];
      }
    } else if (before.length) {
      locationParts.push(...before);
    }
  }

  for (let i = 0; i < tailLines.length - 1; i++) {
    const t = tailLines[i].trim();
    if (t) locationParts.push(t);
  }

  const location = locationParts.filter(l => RE_LOCATION.test(l) || /ta\d/i.test(l)).join(' · ') || locationParts[0] || '';
  const locationDetail = locationParts.join('\n');

  return { location, locationDetail, lecturer, capacity, enrolled, credits, note };
}

function parseWeekBlocks(scheduleText) {
  const weeks = [];
  const chunks = scheduleText.split(/(?=Từ\s+\d{2}\/\d{2}\/\d{4})/i).filter(Boolean);

  for (const chunk of chunks) {
    const header = chunk.match(RE_WEEK);
    if (!header) continue;
    const slots = [];
    let sm;
    const body = chunk.slice(header.index + header[0].length);
    RE_SLOT.lastIndex = 0;
    while ((sm = RE_SLOT.exec(body)) !== null) {
      slots.push({
        day: parseInt(sm[1], 10),
        periods: parsePeriods(sm[2]),
        type: sm[3].toUpperCase(),
      });
    }
    weeks.push({
      weekNo: parseInt(header[3], 10),
      from: header[1],
      to: header[2],
      slots,
    });
  }
  return weeks;
}

function summarizeSlots(weeks) {
  const map = new Map();
  for (const w of weeks) {
    for (const s of w.slots) {
      const key = `${s.day}|${s.periods.join(',')}|${s.type}`;
      map.set(key, (map.get(key) || 0) + 1);
    }
  }
  const entries = [...map.entries()].sort((a, b) => b[1] - a[1]);
  return entries.map(([key, count]) => {
    const [day, periods, type] = key.split('|');
    return {
      day: parseInt(day, 10),
      periods: periods.split(',').map(Number),
      type,
      count,
    };
  });
}

function parseRowBlock(block) {
  const first = block.lines[0];
  const cols = first.split('\t');
  if (cols.length < 3) return null;

  const className = (cols[1] || '').trim();
  const courseCode = (cols[2] || '').trim();
  let scheduleStart = cols.slice(3).join('\t');
  const rest = block.lines.slice(1).join('\n');
  const combined = [scheduleStart, rest].filter(Boolean).join('\n');

  const { scheduleText, tailLines } = extractTail(combined);
  const tail = parseTailLines(tailLines);
  const weeks = parseWeekBlocks(scheduleText);
  const summary = summarizeSlots(weeks);

  return {
    stt: block.stt,
    className,
    shortName: shortClassName(className),
    sectionCode: classCode(className),
    courseCode,
    weeks,
    summary,
    ...tail,
  };
}

function parseSchedulePaste(text) {
  const blocks = splitRowBlocks(text);
  const courses = [];
  const errors = [];

  for (const b of blocks) {
    try {
      const row = parseRowBlock(b);
      if (row && row.weeks.length) courses.push(row);
      else if (row) errors.push(`Dòng ${row.stt}: không đọc được khung giờ «Thời gian».`);
    } catch (e) {
      errors.push(`Dòng ${b.stt}: ${e.message}`);
    }
  }

  return { courses, errors };
}

const MONTH_HEADERS = ['CN', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7'];

function parseVnDate(str) {
  const [d, m, y] = String(str || '').split('/').map(Number);
  if (!d || !m || !y) return null;
  return new Date(y, m - 1, d);
}

function formatVnDate(date) {
  const d = date.getDate();
  const m = date.getMonth() + 1;
  const y = date.getFullYear();
  return `${String(d).padStart(2, '0')}/${String(m).padStart(2, '0')}/${y}`;
}

function formatVnDateShort(date) {
  const d = date.getDate();
  const m = date.getMonth() + 1;
  return `${String(d).padStart(2, '0')}/${String(m).padStart(2, '0')}`;
}

/** JS getDay() → Thứ VN (2=Thứ 2 … 7=Thứ 7, 8=CN). */
function jsDayToThu(jsDay) {
  if (jsDay === 0) return 8;
  return jsDay + 1;
}

function enumerateWeekDays(fromStr, toStr) {
  const start = parseVnDate(fromStr);
  const end = parseVnDate(toStr);
  if (!start || !end || start > end) return [];

  const days = [];
  const cur = new Date(start);
  while (cur <= end) {
    const thu = jsDayToThu(cur.getDay());
    days.push({
      thu,
      label: DAY_LABELS[thu] || `Thứ ${thu}`,
      date: new Date(cur),
      dateKey: formatVnDate(cur),
      dateShort: formatVnDateShort(cur),
    });
    cur.setDate(cur.getDate() + 1);
  }
  return days;
}

function dateForThuInWeek(fromStr, toStr, thu) {
  const days = enumerateWeekDays(fromStr, toStr);
  return days.find(d => d.thu === thu) || null;
}

function buildAllEventsByDate(courses) {
  const map = new Map();

  for (const c of courses) {
    for (const w of c.weeks) {
      for (const s of w.slots) {
        const dayInfo = dateForThuInWeek(w.from, w.to, s.day);
        if (!dayInfo) continue;
        if (!map.has(dayInfo.dateKey)) map.set(dayInfo.dateKey, []);
        map.get(dayInfo.dateKey).push({
          shortName: c.shortName,
          courseCode: c.courseCode,
          type: s.type,
          periods: s.periods,
          sortKey: Math.min(...s.periods),
          location: c.location,
          lecturer: c.lecturer,
        });
      }
    }
  }

  for (const list of map.values()) {
    list.sort((a, b) => a.sortKey - b.sortKey || a.shortName.localeCompare(b.shortName, 'vi'));
  }
  return map;
}

function firstMonthWithEvents(eventsMap) {
  const keys = [...eventsMap.keys()].sort();
  if (!keys.length) return null;
  const d = parseVnDate(keys[0]);
  return d ? { year: d.getFullYear(), month: d.getMonth() } : null;
}

function getMonthCells(year, month) {
  const cells = [];
  const first = new Date(year, month, 1);
  const last = new Date(year, month + 1, 0);
  const padStart = first.getDay();

  const prevLast = new Date(year, month, 0).getDate();
  for (let i = padStart - 1; i >= 0; i--) {
    const d = prevLast - i;
    cells.push({ date: new Date(year, month - 1, d), inMonth: false });
  }
  for (let d = 1; d <= last.getDate(); d++) {
    cells.push({ date: new Date(year, month, d), inMonth: true });
  }
  let nextDay = 1;
  while (cells.length % 7 !== 0 || cells.length < 42) {
    cells.push({ date: new Date(year, month + 1, nextDay), inMonth: false });
    nextDay += 1;
    if (cells.length >= 42 && cells.length % 7 === 0) break;
  }
  return cells;
}

function truncateText(s, max) {
  const t = String(s || '');
  return t.length > max ? t.slice(0, max - 1) + '…' : t;
}

function escapeHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function formatSummaryLine(s) {
  const day = DAY_LABELS[s.day] || `Thứ ${s.day}`;
  const periods = s.periods.join(',');
  return `${day} tiết ${periods} (${s.type})`;
}

function renderCourseTable(courses) {
  const tbody = document.getElementById('course-tbody');
  tbody.innerHTML = courses.map(c => {
    const slots = c.summary.map(formatSummaryLine).join('; ') || '—';
    return `<tr>
      <td class="col-stt">${c.stt}</td>
      <td class="col-name"><strong>${escapeHtml(c.shortName)}</strong>
        <span class="sub">${escapeHtml(c.sectionCode)} · ${escapeHtml(c.courseCode)}</span></td>
      <td>${escapeHtml(slots)}</td>
      <td>${escapeHtml(c.location || '—')}</td>
      <td>${escapeHtml(c.lecturer || '—')}</td>
      <td class="col-num">${escapeHtml(c.credits || '—')}</td>
    </tr>`;
  }).join('');
}

function renderMonthEvent(ev) {
  const typeCls = ev.type === 'TH' ? 'type-th' : 'type-lt';
  const title = `${ev.shortName} · Tiết ${ev.periods.join(',')} (${ev.type})`;
  return `<div class="month-ev ${typeCls}" title="${escapeHtml(title)}">
    <span class="month-ev-name">${escapeHtml(truncateText(ev.shortName, 20))}</span>
    <span class="month-ev-t">T${escapeHtml(ev.periods.join(','))}</span>
  </div>`;
}

function updateSelectedLabel() {
  const el = document.getElementById('cal-selected-label');
  if (!el || !selectedDateKey) return;
  const d = parseVnDate(selectedDateKey);
  if (!d) return;
  const thu = jsDayToThu(d.getDay());
  const dow = DAY_LABELS[thu] || '';
  el.textContent = `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()} ${dow}`;
}

function renderMonthCalendar() {
  const grid = document.getElementById('month-cal-grid');
  const titleEl = document.getElementById('cal-month-title');
  if (!grid || !titleEl) return;

  titleEl.textContent = `Tháng ${viewMonth + 1}/${viewYear}`;
  const todayKey = formatVnDate(new Date());
  const cells = getMonthCells(viewYear, viewMonth);

  grid.innerHTML = cells.map(cell => {
    const dateKey = formatVnDate(cell.date);
    const events = eventsByDate.get(dateKey) || [];
    const isToday = dateKey === todayKey;
    const isSelected = dateKey === selectedDateKey;
    const dayNum = cell.date.getDate();
    const maxShow = 3;
    const shown = events.slice(0, maxShow);
    const more = events.length - maxShow;

    let eventsHtml = shown.map(renderMonthEvent).join('');
    if (more > 0) eventsHtml += `<div class="month-ev-more">+${more} môn</div>`;

    const cls = [
      'month-cell',
      cell.inMonth ? '' : 'other-month',
      isToday ? 'is-today' : '',
      isSelected ? 'is-selected' : '',
      events.length ? 'has-events' : '',
    ].filter(Boolean).join(' ');

    return `<div class="${cls}" data-date="${dateKey}" role="gridcell" tabindex="0">
      <span class="month-cell-num">${dayNum}</span>
      <div class="month-cell-events">${eventsHtml}</div>
    </div>`;
  }).join('');

  updateSelectedLabel();
}

function initCalendarView(courses) {
  eventsByDate = buildAllEventsByDate(courses);
  const today = new Date();
  const todayKey = formatVnDate(today);
  selectedDateKey = eventsByDate.has(todayKey) ? todayKey : [...eventsByDate.keys()].sort()[0] || todayKey;

  const first = firstMonthWithEvents(eventsByDate);
  if (first && !eventsByDate.has(todayKey)) {
    viewYear = first.year;
    viewMonth = first.month;
  } else {
    viewYear = today.getFullYear();
    viewMonth = today.getMonth();
  }
  renderMonthCalendar();
}

function shiftMonth(delta) {
  viewMonth += delta;
  if (viewMonth < 0) {
    viewMonth = 11;
    viewYear -= 1;
  } else if (viewMonth > 11) {
    viewMonth = 0;
    viewYear += 1;
  }
  renderMonthCalendar();
}

function onMonthCellClick(dateKey) {
  selectedDateKey = dateKey;
  renderMonthCalendar();
}

function showResults(courses) {
  document.getElementById('schedule-empty').hidden = true;
  document.getElementById('schedule-result').hidden = false;
  document.getElementById('stat-courses').textContent = String(courses.length);
  const totalTc = courses.reduce((s, c) => s + (parseInt(c.credits, 10) || 0), 0);
  document.getElementById('stat-credits').textContent = totalTc ? String(totalTc) : '—';

  renderCourseTable(courses);
  initCalendarView(courses);

  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ paste: document.getElementById('paste-schedule').value }));
  } catch {
    /* ignore */
  }
}

function showError(msg) {
  const el = document.getElementById('parse-error');
  if (!msg) {
    el.hidden = true;
    el.textContent = '';
    return;
  }
  el.hidden = false;
  el.textContent = msg;
}

let currentCourses = [];
let eventsByDate = new Map();
let viewYear = new Date().getFullYear();
let viewMonth = new Date().getMonth();
let selectedDateKey = '';

function runParse() {
  const text = document.getElementById('paste-schedule').value.trim();
  showError('');
  if (!text) {
    showError('Vui lòng dán lịch học từ hệ thống quản lý đào tạo.');
    return;
  }

  const { courses, errors } = parseSchedulePaste(text);
  if (!courses.length) {
    showError(errors[0] || 'Không nhận dạng được dòng học phần. Hãy copy cả bảng (gồm dòng tiêu đề STT, Lớp học phần…).');
    return;
  }
  if (errors.length) {
    showError('Đã đọc ' + courses.length + ' môn. Cảnh báo: ' + errors.join(' '));
  }
  currentCourses = courses;
  showResults(courses);
}

function loadFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const data = JSON.parse(raw);
    if (data.paste) {
      document.getElementById('paste-schedule').value = data.paste;
      runParse();
    }
  } catch {
    /* ignore */
  }
}

function clearAll() {
  document.getElementById('paste-schedule').value = '';
  currentCourses = [];
  eventsByDate = new Map();
  showError('');
  document.getElementById('schedule-empty').hidden = false;
  document.getElementById('schedule-result').hidden = true;
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

if (typeof document !== 'undefined') {
  document.getElementById('btn-parse').addEventListener('click', runParse);
  document.getElementById('btn-clear').addEventListener('click', clearAll);
  document.getElementById('btn-cal-prev').addEventListener('click', () => shiftMonth(-1));
  document.getElementById('btn-cal-next').addEventListener('click', () => shiftMonth(1));
  document.getElementById('btn-cal-today').addEventListener('click', () => {
    const t = new Date();
    viewYear = t.getFullYear();
    viewMonth = t.getMonth();
    selectedDateKey = formatVnDate(t);
    renderMonthCalendar();
  });
  document.getElementById('month-cal-grid').addEventListener('click', e => {
    const cell = e.target.closest('.month-cell');
    if (!cell?.dataset.date) return;
    onMonthCellClick(cell.dataset.date);
  });
  loadFromStorage();
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    parseSchedulePaste,
    buildAllEventsByDate,
    getMonthCells,
    enumerateWeekDays,
  };
}
