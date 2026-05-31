/**
 * CPA mục tiêu — tính từ bảng điểm đã lưu (chỉ môn được chọn).
 */

const CPA_STORAGE_KEY = 'kma_bang_diem_cpa_settings';

const GRADE_LADDER = [
  { letter: 'A+', gpa: 4.0, label: 'A+ (4.0)' },
  { letter: 'A', gpa: 3.8, label: 'A (3.8)' },
  { letter: 'B+', gpa: 3.5, label: 'B+ (3.5)' },
  { letter: 'B', gpa: 3.0, label: 'B (3.0)' },
  { letter: 'C+', gpa: 2.5, label: 'C+ (2.5)' },
  { letter: 'C', gpa: 2.0, label: 'C (2.0)' },
  { letter: 'D+', gpa: 1.5, label: 'D+ (1.5)' },
  { letter: 'D', gpa: 1.0, label: 'D (1.0)' },
  { letter: 'F', gpa: 0, label: 'F (0)' },
];

const SLIDER_GRADES = GRADE_LADDER.filter(g => g.gpa >= 2.0);

function letterToGpa(letter) {
  const l = String(letter || '')
    .trim()
    .toUpperCase()
    .replace(/\*+$/, '');
  if (!l) return null;
  const hit = GRADE_LADDER.find(g => g.letter === l || l.startsWith(g.letter));
  if (hit) return hit.gpa;
  if (l === 'A') return 3.8;
  return null;
}

function scoreToGpa(tk) {
  if (tk == null || tk < 4) return 0;
  if (tk >= 9.5) return 4.0;
  if (tk >= 8.5) return 3.8;
  if (tk >= 8.0) return 3.5;
  if (tk >= 7.0) return 3.0;
  if (tk >= 6.5) return 2.5;
  if (tk >= 5.5) return 2.0;
  if (tk >= 5.0) return 1.5;
  if (tk >= 4.0) return 1.0;
  return 0;
}

function isExcludedFromGpa(name) {
  const k = (typeof cleanCourseName === 'function' ? cleanCourseName(name) : name) || '';
  return (
    k.includes('giao duc the chat') ||
    k.includes('gdtc') ||
    k.includes('the chat') && k.includes('giao duc') ||
    k.includes('thuc hanh vat ly') ||
    (k.includes('vat ly') && k.includes('thuc hanh'))
  );
}

function computeCurrentStats(rows) {
  let points = 0;
  let credits = 0;
  let counted = 0;

  for (const r of rows) {
    if (!r.checked) continue;
    const tc = parseInt(String(r.credits || '').trim(), 10);
    if (!tc || tc < 1) continue;
    if (isExcludedFromGpa(r.name)) continue;

    let gp = letterToGpa(r.letter);
    if (gp == null && r.tkhp != null) gp = scoreToGpa(r.tkhp);
    if (gp == null) continue;

    points += gp * tc;
    credits += tc;
    counted += 1;
  }

  return {
    gpa: credits > 0 ? points / credits : null,
    credits,
    points,
    counted,
  };
}

function calcRequiredGpa(currentGpa, currentCredits, targetCpa, totalCreditsEnd) {
  const remaining = totalCreditsEnd - currentCredits;
  if (remaining <= 0) {
    return { error: 'Tổng tín chỉ cuối khóa phải lớn hơn tín chỉ đã tích lũy (đã chọn).' };
  }
  if (currentGpa == null) {
    return { error: 'Chưa đủ điểm chữ / điểm TK ở các môn đã chọn để tính GPA hiện tại.' };
  }

  const required =
    (targetCpa * totalCreditsEnd - currentGpa * currentCredits) / remaining;

  return {
    remaining,
    requiredGpa: required,
    feasible: required <= 4.05 && required >= 0,
  };
}

/** Phân bổ tín chỉ còn lại theo các mức điểm (>= minGpa). */
function smartDistribute(remainingCredits, requiredGpa, minGpa, weights) {
  const grades = GRADE_LADDER.filter(g => g.gpa >= minGpa && g.gpa > 0);
  if (!grades.length || !weights.length || remainingCredits <= 0) return [];

  const plans = [];

  for (const w of weights) {
    if (w < 1) continue;
    const maxSubjects = Math.floor(remainingCredits / w);
    if (maxSubjects < 1) continue;

    const alloc = allocateSubjects(maxSubjects, w, remainingCredits, requiredGpa, grades);
    if (alloc.length) {
      plans.push({ weight: w, items: alloc, subjectCount: alloc.reduce((s, a) => s + a.count, 0) });
    }
  }

  return plans;
}

function allocateSubjects(nSubjects, weight, totalCredits, targetAvg, grades) {
  const total = nSubjects * weight;
  if (total > totalCredits + 0.01) {
    nSubjects = Math.floor(totalCredits / weight);
  }
  if (nSubjects < 1) return [];

  const sorted = [...grades].sort((a, b) => b.gpa - a.gpa);
  const counts = Object.fromEntries(sorted.map(g => [g.letter, 0]));

  let points = 0;
  let credits = 0;
  let remaining = Math.min(nSubjects * weight, totalCredits);

  for (let i = 0; i < nSubjects && remaining >= weight; i++) {
    const need = targetAvg - (credits ? points / credits : targetAvg);
    let pick = sorted[sorted.length - 1];
    for (const g of sorted) {
      if (g.gpa >= targetAvg - 0.05) {
        pick = g;
        break;
      }
    }
    if (need > 0.4) pick = sorted[0];
    else if (need > 0.15) pick = sorted[Math.min(1, sorted.length - 1)];
    else if (need < -0.15) pick = sorted[sorted.length - 1];

    counts[pick.letter] = (counts[pick.letter] || 0) + 1;
    points += pick.gpa * weight;
    credits += weight;
    remaining -= weight;
  }

  return sorted
    .filter(g => counts[g.letter] > 0)
    .map(g => ({
      ...g,
      count: counts[g.letter],
      credits: counts[g.letter] * weight,
    }));
}

function proposalForGrade(remainingCredits, requiredGpa, gradeGpa, weights) {
  return weights.map(w => {
    const n = remainingCredits / w;
    const exact = Math.abs(n - Math.round(n)) < 0.01;
    const nRound = Math.round(n);
    const ok = exact && gradeGpa >= requiredGpa - 0.02;
    return {
      weight: w,
      subjects: nRound,
      ok,
      message: exact
        ? ok
          ? `Cần tất cả ${nRound} môn ${GRADE_LADDER.find(g => g.gpa === gradeGpa)?.letter || ''} (${w} tín) để đạt CPA mục tiêu.`
          : `Cần tất cả ${nRound} môn (${w} tín) nhưng mức điểm này vẫn chưa đủ — cần điểm cao hơn.`
        : `Không chia hết cho ${w} tín chỉ/môn (còn ${remainingCredits} tín).`,
    };
  });
}

function readCpaSettingsFromDom() {
  const totalEnd = parseNumber(document.getElementById('cpa-total-credits')?.value);
  const target = parseNumber(document.getElementById('cpa-target')?.value);
  const weights = [];
  document.querySelectorAll('.cpa-weight-toggle:checked').forEach(el => {
    weights.push(+el.value);
  });
  const slider = document.getElementById('cpa-ability-slider');
  const abilityIdx = slider ? +slider.value : 3;
  const ability = SLIDER_GRADES[abilityIdx] || SLIDER_GRADES[3];

  return {
    totalCreditsEnd: totalEnd,
    targetCpa: target,
    creditWeights: weights.length ? weights : [2, 3],
    abilityGpa: ability.gpa,
    abilityLetter: ability.letter,
  };
}

function saveCpaSettings(settings) {
  try {
    localStorage.setItem(CPA_STORAGE_KEY, JSON.stringify(settings));
  } catch {
    /* ignore */
  }
}

function loadCpaSettings() {
  try {
    const raw = localStorage.getItem(CPA_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function applyCpaSettingsToDom(settings) {
  if (!settings) return;
  const t = document.getElementById('cpa-total-credits');
  const c = document.getElementById('cpa-target');
  if (t && settings.totalCreditsEnd != null) t.value = settings.totalCreditsEnd;
  if (c && settings.targetCpa != null) c.value = settings.targetCpa;
  document.querySelectorAll('.cpa-weight-toggle').forEach(el => {
    el.checked = (settings.creditWeights || [2, 3]).includes(+el.value);
  });
  const slider = document.getElementById('cpa-ability-slider');
  if (slider && settings.abilityGpa != null) {
    const idx = SLIDER_GRADES.findIndex(g => g.gpa === settings.abilityGpa);
    slider.value = idx >= 0 ? idx : 3;
    updateAbilityLabel();
  }
}

function updateAbilityLabel() {
  const slider = document.getElementById('cpa-ability-slider');
  const label = document.getElementById('cpa-ability-value');
  if (!slider || !label) return;
  const g = SLIDER_GRADES[+slider.value] || SLIDER_GRADES[3];
  label.textContent = `${g.letter} (${g.gpa})`;
}

function fmtGpa(n) {
  if (n == null || !Number.isFinite(n)) return '—';
  return n.toFixed(2);
}

function renderStatsStrip(stats) {
  const gpaEl = document.getElementById('stat-gpa');
  const tcEl = document.getElementById('stat-credits');
  if (gpaEl) gpaEl.textContent = fmtGpa(stats.gpa);
  if (tcEl) tcEl.textContent = stats.credits > 0 ? String(stats.credits) : '—';
  const curG = document.getElementById('cpa-cur-gpa');
  const curC = document.getElementById('cpa-cur-credits');
  if (curG) curG.textContent = `GPA: ${fmtGpa(stats.gpa)}`;
  if (curC) curC.textContent = `Tín chỉ: ${stats.credits > 0 ? stats.credits : '—'}`;
}

function renderCpaResults(result, settings, stats) {
  const wrap = document.getElementById('cpa-results');
  if (!wrap) return;
  wrap.hidden = false;

  if (result.error) {
    wrap.innerHTML = `<div class="cpa-result-error"><i class="fas fa-circle-exclamation"></i> ${result.error}</div>`;
    return;
  }

  const { remaining, requiredGpa, feasible } = result;
  const minGpa = settings.abilityGpa;
  const plans = smartDistribute(remaining, requiredGpa, minGpa, settings.creditWeights);
  const hardcore = proposalForGrade(remaining, requiredGpa, 4.0, settings.creditWeights);
  const chill = proposalForGrade(remaining, requiredGpa, 3.5, settings.creditWeights);

  let plansHtml = '';
  for (const p of plans) {
    const rows = p.items
      .map(
        it =>
          `<li><span class="grade-tag">${it.label}</span> <span>${it.count} môn · ${it.credits} tín chỉ</span></li>`,
      )
      .join('');
    plansHtml += `
      <div class="cpa-plan-block">
        <h5>${p.weight} tín chỉ/môn</h5>
        <ul class="cpa-plan-list">${rows}</ul>
      </div>`;
  }

  const proposalCard = (title, icon, cls, items) => `
    <div class="cpa-proposal ${cls}">
      <div class="cpa-proposal-head"><i class="${icon}"></i> ${title}</div>
      ${items
        .map(
          it => `
        <div class="cpa-proposal-item ${it.ok ? '' : 'warn'}">
          <strong>${it.subjects} môn — ${it.weight} tín chỉ/môn</strong>
          <p><i class="fas fa-circle-info"></i> ${it.message}</p>
        </div>`,
        )
        .join('')}
    </div>`;

  wrap.innerHTML = `
    <div class="cpa-result-hero">
      <div class="cpa-result-metric">
        <span class="lbl">Số tín chỉ còn lại</span>
        <span class="val">${remaining}</span>
      </div>
      <div class="cpa-result-metric highlight">
        <span class="lbl">GPA cần đạt (các môn còn lại)</span>
        <span class="val ${feasible ? 'ok' : 'bad'}">${fmtGpa(requiredGpa)}</span>
      </div>
    </div>
    <p class="cpa-result-note">Để đạt CPA <strong>${settings.targetCpa}</strong>, bạn cần GPA <strong>${fmtGpa(requiredGpa)}</strong> cho <strong>${remaining}</strong> tín chỉ còn lại (GPA hiện tại ${fmtGpa(stats.gpa)} trên ${stats.credits} tín đã chọn).</p>

    <div class="cpa-section-title"><i class="fas fa-brain"></i> Phân bổ thông minh (≥ ${settings.abilityLetter} ${settings.abilityGpa})</div>
    <div class="cpa-plans">${plansHtml || '<p class="cpa-muted">Chọn ít nhất một mức tín chỉ/môn.</p>'}</div>

    <div class="cpa-section-title"><i class="fas fa-lightbulb"></i> Đề xuất học tập</div>
    <div class="cpa-proposals">
      ${proposalCard('Lộ trình điểm cao (A+)', 'fas fa-rocket', 'hardcore', hardcore)}
      ${proposalCard('Lộ trình điểm khá (B+)', 'fas fa-leaf', 'chill', chill)}
    </div>
  `;
}

function runCpaTargetCalculation(rows) {
  const stats = computeCurrentStats(rows);
  renderStatsStrip(stats);

  const settings = readCpaSettingsFromDom();
  saveCpaSettings(settings);

  if (settings.totalCreditsEnd == null || settings.targetCpa == null) {
    const wrap = document.getElementById('cpa-results');
    if (wrap) {
      wrap.hidden = false;
      wrap.innerHTML =
        '<div class="cpa-result-error">Nhập <strong>Tổng tín chỉ cuối khóa</strong> và <strong>CPA mục tiêu</strong> rồi bấm <strong>Tính toán</strong>.</div>';
    }
    return { stats, settings, error: 'Thiếu thông tin mục tiêu' };
  }

  const result = calcRequiredGpa(
    stats.gpa,
    stats.credits,
    settings.targetCpa,
    settings.totalCreditsEnd,
  );

  if (!result.error) {
    renderCpaResults(result, settings, stats);
  } else {
    const wrap = document.getElementById('cpa-results');
    if (wrap) {
      wrap.hidden = false;
      wrap.innerHTML = `<div class="cpa-result-error">${result.error}</div>`;
    }
  }

  return { stats, settings, result };
}

function refreshLiveStats(rows) {
  renderStatsStrip(computeCurrentStats(rows));
}

function openCpaModal(getRows) {
  const modal = document.getElementById('cpa-modal');
  if (!modal) return;

  const rows = typeof getRows === 'function' ? getRows() : [];
  const stats = computeCurrentStats(rows);
  renderStatsStrip(stats);

  const res = document.getElementById('cpa-results');
  if (res) res.hidden = true;

  modal.hidden = false;
  modal.setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden';

  const first = document.getElementById('cpa-total-credits');
  if (first) setTimeout(() => first.focus(), 80);
}

function closeCpaModal() {
  const modal = document.getElementById('cpa-modal');
  if (!modal) return;
  modal.hidden = true;
  modal.setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';
}

function initCpaTargetUi(getRows) {
  const modal = document.getElementById('cpa-modal');
  const btnToggle = document.getElementById('btn-cpa-toggle');
  const btnCalc = document.getElementById('btn-cpa-calc');
  const slider = document.getElementById('cpa-ability-slider');

  applyCpaSettingsToDom(loadCpaSettings());

  const closers = ['cpa-modal-close', 'cpa-modal-cancel'];
  closers.forEach(id => {
    document.getElementById(id)?.addEventListener('click', closeCpaModal);
  });

  modal?.querySelector('.modal-dialog')?.addEventListener('click', e => e.stopPropagation());
  modal?.addEventListener('click', closeCpaModal);

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && modal && !modal.hidden) closeCpaModal();
  });

  btnToggle?.addEventListener('click', () => openCpaModal(getRows));

  btnCalc?.addEventListener('click', () => {
    const rows = typeof getRows === 'function' ? getRows() : [];
    runCpaTargetCalculation(rows);
    saveCpaSettings(readCpaSettingsFromDom());
    const res = document.getElementById('cpa-results');
    if (res) res.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  });

  if (slider) {
    slider.addEventListener('input', updateAbilityLabel);
    updateAbilityLabel();
  }

  return { runCpaTargetCalculation, refreshLiveStats, openCpaModal, closeCpaModal };
}
