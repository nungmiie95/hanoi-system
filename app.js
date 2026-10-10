/**
 * static/app.js - Client-Side Interactive Engine for Hanoi Lottery Analytics System
 * Compatible with modern ES6+ browsers and mobile WebViews.
 */

// ==============================================================================
// 1. TOAST NOTIFICATION MANAGER
// ==============================================================================

/**
 * Displays a non-intrusive floating toast alert in the bottom-right corner.
 * @param {string} message - Message text to display.
 * @param {'success'|'error'|'info'|'warning'} type - Visual theme of the toast.
 * @param {number} duration - Auto-dismiss timeout in milliseconds (default: 3500ms).
 */
function showToast(message, type = 'info', duration = 3500) {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = 'pointer-events-auto flex items-center p-4 rounded-xl shadow-2xl border text-sm max-w-sm transition-all transform duration-300 translate-y-2 opacity-0';

  let iconSvg = '';
  if (type === 'success') {
    toast.classList.add('bg-slate-900', 'border-emerald-500/50', 'text-emerald-300');
    iconSvg = `<svg class="w-5 h-5 text-emerald-400 mr-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>`;
  } else if (type === 'error') {
    toast.classList.add('bg-slate-900', 'border-rose-500/50', 'text-rose-300');
    iconSvg = `<svg class="w-5 h-5 text-rose-400 mr-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>`;
  } else if (type === 'warning') {
    toast.classList.add('bg-slate-900', 'border-amber-500/50', 'text-amber-300');
    iconSvg = `<svg class="w-5 h-5 text-amber-400 mr-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>`;
  } else {
    toast.classList.add('bg-slate-900', 'border-indigo-500/50', 'text-indigo-300');
    iconSvg = `<svg class="w-5 h-5 text-indigo-400 mr-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>`;
  }

  toast.innerHTML = `
    ${iconSvg}
    <div class="flex-grow font-sans">${message}</div>
    <button type="button" class="ml-3 text-slate-400 hover:text-white" onclick="this.parentElement.remove()">
      <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
    </button>
  `;

  container.appendChild(toast);

  // Trigger enter transition
  requestAnimationFrame(() => {
    toast.classList.remove('translate-y-2', 'opacity-0');
  });

  // Auto-dismiss
  setTimeout(() => {
    toast.classList.add('opacity-0', 'translate-y-2');
    setTimeout(() => toast.remove(), 300);
  }, duration);
}


// ==============================================================================
// 2. LIVE COUNTDOWN TICKER ENGINE
// ==============================================================================

let countdownState = {
  secondsLeft: 0,
  targetTime: '17:30',
  nextRound: 'special',
  intervalId: null
};

/**
 * Initializes countdown ticker by querying /api/countdown.
 */
function initCountdown() {
  const hoursEl = document.getElementById('countdown-hours');
  const minsEl = document.getElementById('countdown-minutes');
  const secsEl = document.getElementById('countdown-seconds');
  if (!hoursEl || !minsEl || !secsEl) return;

  fetchCountdownData();

  // Periodic resync every 60 seconds to avoid client drift
  setInterval(fetchCountdownData, 60000);
}

function fetchCountdownData() {
  fetch('/api/countdown')
    .then(res => res.json())
    .then(data => {
      countdownState.secondsLeft = parseInt(data.seconds_left, 10) || 0;
      countdownState.targetTime = data.target_time || data.time || '17:30';
      countdownState.nextRound = data.next_round || 'special';

      updateRoundLabel();
      startTicker();
    })
    .catch(err => {
      console.warn('Countdown sync error:', err);
    });
}

function updateRoundLabel() {
  const labelEl = document.getElementById('countdown-round-label');
  if (!labelEl) return;

  let thaiName = 'ฮานอยพิเศษ (รอบ 17:30 น.)';
  if (countdownState.nextRound === 'normal') {
    thaiName = 'ฮานอยปกติ (รอบ 18:30 น.)';
  } else if (countdownState.nextRound === 'vip') {
    thaiName = 'ฮานอย VIP (รอบ 19:30 น.)';
  }
  labelEl.textContent = thaiName;
}

function startTicker() {
  if (countdownState.intervalId) {
    clearInterval(countdownState.intervalId);
  }

  renderCountdownUnits(countdownState.secondsLeft);

  countdownState.intervalId = setInterval(() => {
    if (countdownState.secondsLeft > 0) {
      countdownState.secondsLeft--;
      renderCountdownUnits(countdownState.secondsLeft);
    } else {
      renderCountdownUnits(0);
      clearInterval(countdownState.intervalId);
      showToast('ถึงเวลาออกรางวัลแล้ว! ระบบกำลังรอผลงวดใหม่...', 'warning', 5000);
      // Retry sync in 15 seconds
      setTimeout(fetchCountdownData, 15000);
    }
  }, 1000);
}

function renderCountdownUnits(totalSecs) {
  const hoursEl = document.getElementById('countdown-hours');
  const minsEl = document.getElementById('countdown-minutes');
  const secsEl = document.getElementById('countdown-seconds');
  if (!hoursEl || !minsEl || !secsEl) return;

  const h = Math.floor(totalSecs / 3600);
  const m = Math.floor((totalSecs % 3600) / 60);
  const s = totalSecs % 60;

  hoursEl.textContent = String(h).padStart(2, '0');
  minsEl.textContent = String(m).padStart(2, '0');
  secsEl.textContent = String(s).padStart(2, '0');
}


// ==============================================================================
// 3. 1-CLICK CLIPBOARD COPY ENGINE (WITH HTTP FALLBACK)
// ==============================================================================

/**
 * Universal clipboard copy supporting navigator.clipboard with execCommand fallback for HTTP.
 * @param {string} text - Plain text to copy.
 * @returns {Promise<boolean>}
 */
async function copyToClipboard(text) {
  if (!text) {
    showToast('ไม่มีข้อความให้คัดลอก', 'warning');
    return false;
  }

  // 1. Try modern Async Clipboard API (HTTPS & localhost)
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (e) {
      console.warn('navigator.clipboard failed, attempting fallback...', e);
    }
  }

  // 2. Safe Fallback for HTTP / non-secure contexts
  try {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.top = '0';
    textArea.style.left = '0';
    textArea.style.width = '2em';
    textArea.style.height = '2em';
    textArea.style.padding = '0';
    textArea.style.border = 'none';
    textArea.style.outline = 'none';
    textArea.style.boxShadow = 'none';
    textArea.style.background = 'transparent';
    textArea.style.opacity = '0';

    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();

    const success = document.execCommand('copy');
    document.body.removeChild(textArea);
    return success;
  } catch (err) {
    console.error('execCommand copy failed:', err);
    return false;
  }
}

/**
 * Helper to copy arbitrary snippets and show toast.
 */
async function copySnippet(text) {
  const ok = await copyToClipboard(text);
  if (ok) {
    showToast(`คัดลอกแล้ว: "${text}"`, 'success');
  } else {
    showToast('ไม่สามารถคัดลอกได้ กรุณาคัดลอกด้วยตนเอง', 'error');
  }
}

/**
 * Sets up 1-click copy buttons with visual button feedback.
 */
function initCopyButtons() {
  const bindBtn = (btnId, textId) => {
    const btn = document.getElementById(btnId);
    if (!btn) return;

    btn.addEventListener('click', async () => {
      const copyText = btn.getAttribute('data-copy-text');
      const ok = await copyToClipboard(copyText);
      if (ok) {
        const textSpan = document.getElementById(textId);
        const originalText = textSpan ? textSpan.textContent : 'คัดลอกข้อความ';
        if (textSpan) textSpan.textContent = '✓ คัดลอกสำเร็จ!';
        btn.classList.add('bg-emerald-500');

        showToast('คัดลอกข้อความสำเร็จ พร้อมวางลงกลุ่มไลน์/เทเลแกรมแล้ว', 'success', 3000);

        setTimeout(() => {
          if (textSpan) textSpan.textContent = originalText;
          btn.classList.remove('bg-emerald-500');
        }, 2000);
      } else {
        showToast('การคัดลอกล้มเหลว โปรดลองใหม่อีกครั้ง', 'error');
      }
    });
  };

  bindBtn('copy-summary-btn', 'copy-summary-text');
  bindBtn('master-copy-btn', 'master-copy-text');
}


// ==============================================================================
// 4. CHART.JS VISUALIZATION ENGINE (STATS PAGE)
// ==============================================================================

function renderStatsCharts() {
  const dataScript = document.getElementById('stats-data');
  if (!dataScript) return;

  let stats;
  try {
    stats = JSON.parse(dataScript.textContent);
  } catch (e) {
    console.error('Failed to parse stats JSON:', e);
    return;
  }

  const topCounts = stats.top_digits || {};
  const bottomCounts = stats.bottom_digits || {};

  const labels = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'];
  const topData = labels.map(d => topCounts[d] || 0);
  const bottomData = labels.map(d => bottomCounts[d] || 0);

  // Common chart styling for dark theme
  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#0f172a',
        titleColor: '#f8fafc',
        bodyColor: '#e2e8f0',
        borderColor: '#334155',
        borderWidth: 1,
        padding: 10,
        callbacks: {
          label: function(context) {
            return ` ความถี่: ${context.raw} ครั้ง`;
          }
        }
      }
    },
    scales: {
      x: {
        grid: { color: 'rgba(255, 255, 255, 0.05)' },
        ticks: { color: '#94a3b8', font: { family: 'Prompt', size: 12, weight: 'bold' } }
      },
      y: {
        grid: { color: 'rgba(255, 255, 255, 0.05)' },
        ticks: { color: '#94a3b8', font: { family: 'Prompt', size: 11 } },
        beginAtZero: true
      }
    }
  };

  // Top Digits Chart (Emerald)
  const topCanvas = document.getElementById('topDigitsChart');
  if (topCanvas) {
    new Chart(topCanvas.getContext('2d'), {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          data: topData,
          backgroundColor: 'rgba(16, 185, 129, 0.75)',
          hoverBackgroundColor: 'rgba(52, 211, 153, 0.95)',
          borderRadius: 6,
          borderSkipped: false
        }]
      },
      options: chartOptions
    });
  }

  // Bottom Digits Chart (Amber)
  const bottomCanvas = document.getElementById('bottomDigitsChart');
  if (bottomCanvas) {
    new Chart(bottomCanvas.getContext('2d'), {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          data: bottomData,
          backgroundColor: 'rgba(245, 158, 11, 0.75)',
          hoverBackgroundColor: 'rgba(251, 191, 36, 0.95)',
          borderRadius: 6,
          borderSkipped: false
        }]
      },
      options: chartOptions
    });
  }
}


// ==============================================================================
// 5. MOBILE NAVIGATION CONTROLLER
// ==============================================================================

function initMobileMenu() {
  const btn = document.getElementById('mobile-menu-btn');
  const menu = document.getElementById('mobile-menu');
  const iconOpen = document.getElementById('menu-icon-open');
  const iconClose = document.getElementById('menu-icon-close');
  if (!btn || !menu) return;

  btn.addEventListener('click', () => {
    const isClosed = menu.classList.contains('hidden');
    if (isClosed) {
      menu.classList.remove('hidden');
      if (iconOpen) iconOpen.classList.add('hidden');
      if (iconClose) iconClose.classList.remove('hidden');
    } else {
      menu.classList.add('hidden');
      if (iconOpen) iconOpen.classList.remove('hidden');
      if (iconClose) iconClose.classList.add('hidden');
    }
  });
}


// ==============================================================================
// 6. DATA MANAGEMENT CRUD & AUTO-CALCULATION ENGINE (MANAGE PAGE)
// ==============================================================================

/**
 * Automatically derives Top 3 and Top 2 previews as user enters special prize.
 */
function autoDeriveTops(val) {
  const clean = String(val).replace(/\D/g, '');
  const top3El = document.getElementById('preview-top3');
  const top2El = document.getElementById('preview-top2');

  if (clean.length >= 3) {
    if (top3El) top3El.textContent = clean.slice(-3);
  } else {
    if (top3El) top3El.textContent = '-';
  }

  if (clean.length >= 2) {
    if (top2El) top2El.textContent = clean.slice(-2);
  } else {
    if (top2El) top2El.textContent = '-';
  }
}

function openAddModal() {
  const modal = document.getElementById('result-modal');
  const title = document.getElementById('modal-title');
  const form = document.getElementById('result-form');
  if (!modal || !form) return;

  title.textContent = 'เพิ่มผลรางวัล';
  form.reset();
  document.getElementById('form-id').value = '';
  document.getElementById('form-date').valueAsDate = new Date();
  autoDeriveTops('');

  modal.classList.remove('hidden');
}

function openEditModal(record) {
  const modal = document.getElementById('result-modal');
  const title = document.getElementById('modal-title');
  if (!modal || !record) return;

  title.textContent = 'แก้ไขผลรางวัล';
  document.getElementById('form-id').value = record.id;
  document.getElementById('form-date').value = record.draw_date;
  document.getElementById('form-round').value = record.round_type;
  document.getElementById('form-special').value = record.special_prize;
  document.getElementById('form-bottom2').value = record.bottom2;

  autoDeriveTops(record.special_prize);
  modal.classList.remove('hidden');
}

function closeResultModal() {
  const modal = document.getElementById('result-modal');
  if (modal) modal.classList.add('hidden');
}

async function saveResult(e) {
  e.preventDefault();
  const id = document.getElementById('form-id').value;
  const drawDate = document.getElementById('form-date').value;
  const roundType = document.getElementById('form-round').value;
  const specialPrize = document.getElementById('form-special').value;
  const bottom2 = document.getElementById('form-bottom2').value;

  const payload = {
    draw_date: drawDate,
    round_type: roundType,
    special_prize: specialPrize,
    bottom2: bottom2
  };

  const isEdit = !!id;
  const url = isEdit ? `/api/results/${id}` : '/api/results';
  const method = isEdit ? 'PUT' : 'POST';

  try {
    const res = await fetch(url, {
      method: method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      showToast(isEdit ? 'แก้ไขผลรางวัลเรียบร้อย' : 'เพิ่มผลรางวัลสำเร็จ', 'success');
      closeResultModal();
      setTimeout(() => window.location.reload(), 600);
    } else {
      const err = await res.json().catch(() => ({}));
      showToast(err.error || 'บันทึกข้อมูลล้มเหลว', 'error');
    }
  } catch (err) {
    showToast('เกิดข้อผิดพลาดในการเชื่อมต่อ', 'error');
  }
}

async function confirmDelete(id, date, round) {
  if (!confirm(`ยืนยันการลบผลรางวัลงวดวันที่ ${date} (${round})?`)) return;

  try {
    const res = await fetch(`/api/results/${id}`, { method: 'DELETE' });
    if (res.ok) {
      showToast('ลบผลรางวัลสำเร็จ', 'success');
      const row = document.getElementById(`row-${id}`);
      if (row) row.remove();
    } else {
      showToast('ลบผลรางวัลไม่สำเร็จ', 'error');
    }
  } catch (err) {
    showToast('เกิดข้อผิดพลาดในการลบข้อมูล', 'error');
  }
}

async function confirmClearAll() {
  const confirmed = confirm("⚠️ ยืนยันการล้างข้อมูลผลรางวัลทั้งหมดในระบบ?\n\nข้อมูลผลรางวัลทุกงวดจะถูกลบทั้งหมดและไม่สามารถกู้คืนได้ คุณต้องการดำเนินการต่อหรือไม่?");
  if (!confirmed) return;

  try {
    let res = await fetch('/api/clear-all', { method: 'POST' });
    if (res.status === 404) {
      // Fallback: Delete all records iteratively if endpoint not yet deployed
      const listRes = await fetch('/api/results?limit=1000');
      const items = await listRes.json();
      if (Array.isArray(items) && items.length > 0) {
        for (const item of items) {
          await fetch(`/api/results/${item.id}`, { method: 'DELETE' });
        }
        showToast(`ล้างข้อมูลสำเร็จ (ลบออก ${items.length} รายการ)`, 'success');
        setTimeout(() => window.location.reload(), 800);
        return;
      }
    }
    const data = await res.json();
    if (res.ok && data.success) {
      showToast(data.message || `ล้างข้อมูลทั้งหมดสำเร็จ (${data.deleted} รายการ)`, 'success');
      setTimeout(() => window.location.reload(), 800);
    } else {
      showToast(data.error || 'ล้างข้อมูลไม่สำเร็จ', 'error');
    }
  } catch (err) {
    showToast('เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์', 'error');
  }
}

async function triggerFetchLatest() {
  const btn = document.getElementById('fetch-latest-btn');
  const spinner = document.getElementById('fetch-spinner');
  if (spinner) spinner.classList.add('animate-spin');

  try {
    const res = await fetch('/api/fetch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mock: false })
    });
    const data = await res.json();
    if (res.ok && data.success) {
      showToast('ดึงผลรางวัลล่าสุดสำเร็จ!', 'success');
      setTimeout(() => window.location.reload(), 800);
    } else {
      showToast(data.message || 'ไม่พบผลรางวัลใหม่ในขณะนี้', 'info');
    }
  } catch (err) {
    showToast('การดึงผลรางวัลขัดข้อง กำลังใช้โหมดสำรอง', 'warning');
  } finally {
    if (spinner) spinner.classList.remove('animate-spin');
  }
}

function openImportModal() {
  const modal = document.getElementById('import-modal');
  if (modal) modal.classList.remove('hidden');
}

function closeImportModal() {
  const modal = document.getElementById('import-modal');
  if (modal) modal.classList.add('hidden');
}

async function uploadImport(e) {
  e.preventDefault();
  const fileInput = document.getElementById('import-file');
  const skipExisting = document.getElementById('import-skip').checked;

  if (!fileInput.files || fileInput.files.length === 0) {
    showToast('กรุณาเลือกไฟล์ CSV หรือ JSON', 'warning');
    return;
  }

  const file = fileInput.files[0];
  const formData = new FormData();
  formData.append('file', file);
  formData.append('skip_existing', skipExisting);

  const isJson = file.name.endsWith('.json');
  const endpoint = isJson ? '/api/import/json' : '/api/import/csv';

  try {
    const res = await fetch(endpoint, {
      method: 'POST',
      body: formData
    });
    const result = await res.json();
    if (res.ok) {
      showToast(`นำเข้าสำเร็จ: เพิ่มใหม่ ${result.imported || 0} รายการ, ข้าม ${result.skipped || 0} รายการ`, 'success');
      closeImportModal();
      setTimeout(() => window.location.reload(), 1000);
    } else {
      showToast(result.error || 'นำเข้าข้อมูลล้มเหลว', 'error');
    }
  } catch (err) {
    showToast('เกิดข้อผิดพลาดในการอัปโหลดไฟล์', 'error');
  }
}


// ==============================================================================
// LIFECYCLE INITIALIZATION ON DOMContentLoaded
// ==============================================================================

document.addEventListener('DOMContentLoaded', () => {
  initMobileMenu();
  initCountdown();
  initCopyButtons();
  renderStatsCharts();
});
