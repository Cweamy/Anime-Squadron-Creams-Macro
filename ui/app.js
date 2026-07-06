let running = false;
let taskIdCounter = 0;

function api() { return window.pywebview.api; }

window.addEventListener('pywebviewready', async () => {
  // Fire-and-forget: shows the consent prompt if needed, but must never
  // block the rest of startup — reads (load_settings, get_loadouts, etc.)
  // work fine on defaults with no consent yet, and writes are already
  // gated server-side until consent is granted.
  ensureStorageConsent().catch(e => console.error('storageConsent', e));

  try {
    await loadRewards();
  } catch (e) { console.error('loadRewards', e); }

  try {
    traitStageData = await api().get_trait_state();
  } catch (e) { console.error('loadTraitState', e); }

  try {
    const s = await api().load_settings();
    if (s.webhook_url) {
      document.getElementById('txtWebhook').value = s.webhook_url;
      updateWebhookDot(s.webhook_url);
    }
    if (s.webhook_enabled === false) document.getElementById('chkWebhook').checked = false;
    if (s.webhook_silent) document.getElementById('chkSilent').checked = true;
    if (s.loop) document.getElementById('chkStartOver').checked = true;
    if (s.check_challenges) document.getElementById('chkChallenges').checked = true;
    if (s.challenge_priority) document.getElementById('chkPriority').checked = true;
    if (s.screenshot_mode) document.getElementById('selScreenshot').value = s.screenshot_mode;
    if (s.desired_rewards && s.desired_rewards.length > 0) {
      document.querySelectorAll('#rewardList input[type="checkbox"]').forEach(el => {
        el.checked = s.desired_rewards.includes(el.id.replace('rwd_', ''));
      });
    }
    if (s.queue && s.queue.length > 0) {
      for (const t of s.queue) addTask(t);
    }
    if (!s.tutorial_seen) openTutorialModal();
  } catch (e) { console.error('loadSettings', e); }

  try { await api().start_roblox_poll(); } catch (e) {}

  try {
    const ver = await api().get_version();
    document.getElementById('verBadge').textContent = 'v' + ver;
  } catch (e) {}

  try { checkForUpdate(); } catch (e) {}
  try { await refreshLoadouts(); await refreshAppendList(); } catch (e) {}
  try { await loadHotkeys(); } catch (e) {}

  setInterval(pollStatus, 250);
  setInterval(pollLogs, 2000);
  setInterval(pollTraitData, 2000);
  setInterval(autoSaveQueue, 10000);

  document.getElementById('txtLoadoutName').addEventListener('keydown', e => {
    if (e.key === 'Enter') confirmSaveLoadout();
    if (e.key === 'Escape') cancelSaveLoadout();
  });
});

// ── Scramble Text ──
let _scrambleAnim = null;
let _lastState = '';
const CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%&*';

function scrambleText(el, newText) {
  if (_scrambleAnim) cancelAnimationFrame(_scrambleAnim);
  const len = newText.length;
  let frame = 0;
  const totalFrames = len * 3;

  function step() {
    let out = '';
    for (let i = 0; i < len; i++) {
      const reveal = frame - i * 2;
      if (reveal >= 3) {
        out += newText[i];
      } else if (reveal >= 0) {
        out += CHARS[Math.floor(Math.random() * CHARS.length)];
      } else {
        out += CHARS[Math.floor(Math.random() * CHARS.length)];
      }
    }
    el.textContent = out;
    frame++;
    if (frame <= totalFrames) {
      _scrambleAnim = requestAnimationFrame(step);
    } else {
      el.textContent = newText;
      _scrambleAnim = null;
    }
  }
  step();
}

// ── Idle Fun ──
let _idleFun = null;
let _idleShowing = false;
const IDLE_MSGS = [
  'Made with ♥ by Cweamya',
  'Happy grinding!',
  'Press Start when ready',
  'AFK farming made easy',
  'Cream\'s Macro v' + '♥',
];

function startIdleFun() {
  if (_idleFun) return;
  function tick() {
    const delay = (9 + Math.random() * 6) * 1000;
    _idleFun = setTimeout(() => {
      if (_lastState !== 'Idle') return;
      const msg = IDLE_MSGS[Math.floor(Math.random() * IDLE_MSGS.length)];
      _idleShowing = true;
      scrambleText(document.getElementById('txtState'), msg);
      _idleFun = setTimeout(() => {
        if (_lastState !== 'Idle') return;
        _idleShowing = false;
        scrambleText(document.getElementById('txtState'), 'Idle');
        tick();
      }, 3000);
    }, delay);
  }
  tick();
}

function stopIdleFun() {
  if (_idleFun) { clearTimeout(_idleFun); _idleFun = null; }
  _idleShowing = false;
}

// ── Status ──
async function pollStatus() {
  try {
    const s = await api().get_status();
    const wasRunning = running;
    running = s.running;
    const btn = document.getElementById('btnToggle');
    btn.querySelector('.icon-play').style.display = running ? 'none' : '';
    btn.querySelector('.icon-stop').style.display = running ? '' : 'none';
    btn.className = running ? 'btn btn-stop' : 'btn btn-start';
    const label = btn.querySelector('span');
    const newText = running ? 'Stop (F2)' : 'Start';
    if (wasRunning !== running) {
      scrambleText(label, newText);
    } else if (label.textContent !== newText) {
      label.textContent = newText;
    }

    const pauseBtn = document.getElementById('btnPause');
    pauseBtn.style.display = running ? '' : 'none';
    pauseBtn.querySelector('.icon-pause').style.display = s.paused ? 'none' : '';
    pauseBtn.querySelector('.icon-resume').style.display = s.paused ? '' : 'none';
    pauseBtn.title = s.paused ? 'Resume (F3)' : 'Pause (F3)';
    if (s.paused) pauseBtn.classList.add('btn-pause-active');
    else pauseBtn.classList.remove('btn-pause-active');

    const overlay = document.getElementById('waitingOverlay');
    if (s.roblox_found) {
      overlay.classList.add('hidden');
      document.body.classList.add('docked');
    } else if (!running) {
      overlay.classList.remove('hidden');
      document.body.classList.remove('docked');
    }

    if (s.state !== _lastState) {
      _lastState = s.state;
      if (!_idleFun) scrambleText(document.getElementById('txtState'), s.state);
      if (s.state === 'Idle') startIdleFun(); else stopIdleFun();
    }

    document.getElementById('statWinRate').textContent = s.win_rate + '%';
    document.getElementById('statRuns').textContent = s.run_count;
    document.getElementById('statVD').innerHTML =
      `<span class="stat-v">${s.victory_count}</span>/<span class="stat-d">${s.defeat_count}</span>`;
    document.getElementById('statChallenge').textContent = s.challenge_runs || 0;

    const ss = s.session_s || 0;
    const hh = Math.floor(ss / 3600);
    const mm = Math.floor((ss % 3600) / 60);
    const sec = ss % 60;
    document.getElementById('statTime').textContent =
      hh > 0 ? `${hh}:${String(mm).padStart(2,'0')}:${String(sec).padStart(2,'0')}`
             : `${mm}:${String(sec).padStart(2,'0')}`;

    const pRow = document.getElementById('taskProgressRow');
    if (s.use_task_queue && s.task_count > 0 && running) {
      pRow.style.display = '';
      document.getElementById('taskProgressText').textContent = `Task ${s.current_task_index}/${s.task_count}`;
      document.getElementById('taskRunText').textContent = `Run ${s.task_run_count}/${s.task_run_target}`;
      const pct = s.task_run_target > 0 ? Math.min(100, Math.round(s.task_run_count / s.task_run_target * 100)) : 0;
      document.getElementById('taskProgressFill').style.width = pct + '%';
    } else {
      pRow.style.display = 'none';
    }

    const traitRow = document.getElementById('traitInlineRow');
    if (s.trait_tracking && running) {
      traitRow.style.display = 'flex';
      document.getElementById('traitInlineText').textContent =
        `${s.trait_stage}: ${s.trait_count}/${s.trait_limit}`;
    } else {
      traitRow.style.display = 'none';
    }
  } catch (e) {}
}

// ── Log Viewer ──
async function pollLogs() {
  const el = document.getElementById('logViewer');
  if (!el || el.closest('.collapsed')) return;
  try {
    const lines = await api().get_logs();
    if (!lines || lines.length === 0) {
      el.innerHTML = '<span class="muted">No logs yet</span>';
      return;
    }
    el.innerHTML = lines.map(l => {
      const esc = l.replace(/&/g,'&amp;').replace(/</g,'&lt;');
      return `<div class="log-line">${esc}</div>`;
    }).join('');
    el.scrollTop = el.scrollHeight;
  } catch (e) {}
}

// ── Rewards ──
async function loadRewards() {
  const el = document.getElementById('rewardList');
  try {
    const files = await api().get_reward_files();
    if (!files || files.length === 0) {
      el.innerHTML = '<span class="muted">No rewards found</span>';
      return;
    }
    let icons = {};
    try { icons = await api().get_reward_icons(); } catch (e) {}
    el.innerHTML = '';
    for (const f of files) {
      const label = f.replace('.png', '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
      const id = 'rwd_' + f;
      const b64 = icons[f];
      const img = b64
        ? `<img class="reward-icon" src="data:image/png;base64,${b64}" alt="${label}">`
        : '';
      el.innerHTML += `
        <label class="reward-card" for="${id}">
          <input type="checkbox" id="${id}">
          ${img}
          <span class="reward-name">${label}</span>
        </label>`;
    }
  } catch (e) {
    el.innerHTML = '<span class="muted">Failed to load rewards</span>';
    console.error('loadRewards error', e);
  }
}

function getSelectedRewards() {
  const items = document.querySelectorAll('#rewardList input[type="checkbox"]');
  const sel = [];
  items.forEach(el => { if (el.checked) sel.push(el.id.replace('rwd_', '')); });
  return sel;
}

// ── Webhook ──
async function pasteWebhook() {
  try {
    const text = await navigator.clipboard.readText();
    const url = text.trim();
    const result = await api().validate_webhook(url);
    if (result.valid) {
      document.getElementById('txtWebhook').value = url;
      await api().save_webhook(url, document.getElementById('chkWebhook').checked);
    }
    updateWebhookDot(result.valid ? url : '', result);
  } catch (e) {
    updateWebhookDot('', { valid: false });
  }
}

function clearWebhook() {
  document.getElementById('txtWebhook').value = '';
  updateWebhookDot('');
  api().save_webhook('', document.getElementById('chkWebhook').checked);
}

function updateWebhookDot(url, result) {
  const dot = document.getElementById('webhookDot');
  const label = document.getElementById('webhookLabel');
  if (!url) {
    dot.className = 'wh-dot dot-none';
    label.className = 'wh-label';
    label.textContent = 'Not set';
  } else if (result && !result.valid) {
    dot.className = 'wh-dot dot-invalid';
    label.className = 'wh-label bad';
    label.textContent = 'Invalid URL';
  } else {
    dot.className = 'wh-dot dot-valid';
    label.className = 'wh-label set';
    label.textContent = 'Connected';
  }
}

// ── Task Cards ──
function addTask(preset) {
  taskIdCounter++;
  const id = taskIdCounter;
  const div = document.createElement('div');
  div.className = 'task-card';
  div.id = 'task_' + id;

  const mode = preset ? preset.mode : 'Raid';
  const rep  = preset ? preset.repeat : 10;
  const diff = preset ? preset.diff : 'Normal';
  const trackTrait = preset && preset.track_trait ? 'checked' : '';

  div.innerHTML = `
    <div class="task-row-top">
      <select class="tMode" onchange="onTaskModeChange(${id})">
        <option ${mode==='Challenge'?'selected':''}>Challenge</option>
        <option ${mode==='Raid'?'selected':''}>Raid</option>
        <option ${mode==='Invasion'?'selected':''}>Invasion</option>
        <option ${mode==='Squadron'?'selected':''}>Squadron</option>
        <option ${mode==='Story'?'selected':''}>Story</option>
      </select>
      <div class="rep-group">
        ×<input type="number" class="tRep" value="${rep}" min="1">
      </div>
      <select class="tDiff">
        <option ${diff==='Normal'?'selected':''}>Normal</option>
        <option ${diff==='Hard'?'selected':''}>Hard</option>
      </select>
      <button class="btn-remove" onclick="removeTask(${id})">✕</button>
    </div>
    <div class="task-row-bottom">
      <select class="tMap"><option>-</option></select>
      <select class="tAct"><option>-</option></select>
      <div class="drag-handle" title="Drag to reorder">⠿</div>
    </div>
    <div class="task-row-trait">
      <label class="toggle" title="Skip this stage entirely once its daily trait limit is hit">
        <input type="checkbox" class="tTraitTrack" ${trackTrait}>
        <span class="toggle-track"></span>
        Track Trait
      </label>
      <div class="trait-count-group">
        <input type="number" class="tTraitCount" min="0" value="0" onchange="onTaskTraitCountChange(${id})">
        <span class="tTraitLimitLabel">/ 100</span>
      </div>
      <button type="button" class="btn-trait-reset" onclick="onTaskTraitReset(${id})" title="Reset this stage's count to 0">↺</button>
    </div>
  `;
  document.getElementById('taskList').appendChild(div);
  onTaskModeChange(id, preset);
  updateTraitRow(id);
}

function applyPreset(id, preset) {
  if (!preset) return;
  const card = document.getElementById('task_' + id);
  if (!card) return;
  if (preset.map && preset.map !== '-') {
    card.querySelector('.tMap').value = preset.map;
  }
  onTaskMapChange(id);
  if (preset.act && preset.act !== '-') {
    card.querySelector('.tAct').value = preset.act;
  }
  updateTraitRow(id);
}

function onTaskModeChange(id, preset) {
  const card = document.getElementById('task_' + id);
  if (!card) return;
  const mode = card.querySelector('.tMode').value;
  const mapSel = card.querySelector('.tMap');
  const actSel = card.querySelector('.tAct');
  const diffSel = card.querySelector('.tDiff');
  mapSel.onchange = null;
  actSel.onchange = null;

  if (mode === 'Challenge') {
    mapSel.innerHTML = '<option>Regular</option><option>Aizen</option><option>Garou</option>';
    mapSel.disabled = false;
    mapSel.onchange = () => updateTraitRow(id);
    actSel.innerHTML = '<option>-</option>'; actSel.disabled = true;
    diffSel.disabled = false;
  } else if (mode === 'Raid') {
    mapSel.innerHTML = '<option>GT</option><option>Eclipse</option>';
    mapSel.disabled = false; mapSel.onchange = () => onTaskMapChange(id);
    actSel.onchange = () => updateTraitRow(id);
    diffSel.disabled = false;
  } else if (mode === 'Invasion') {
    mapSel.innerHTML = '<option>The Lava Continent</option>';
    mapSel.disabled = false; mapSel.onchange = () => onTaskMapChange(id);
    diffSel.disabled = false;
  } else if (mode === 'Squadron' || mode === 'Story') {
    mapSel.innerHTML = '<option>GT City</option><option>Marine Lobby</option><option>Ninja Village</option><option>Eclipse</option>'
      + (mode === 'Story' ? '<option>The Ice Continent</option>' : '');
    mapSel.disabled = false; mapSel.onchange = () => onTaskMapChange(id);
    diffSel.disabled = false;
  } else {
    mapSel.innerHTML = '<option>-</option>'; mapSel.disabled = true;
    actSel.innerHTML = '<option>-</option>'; actSel.disabled = true;
    diffSel.disabled = true;
  }

  if (preset) {
    applyPreset(id, preset);
  } else if (mode === 'Raid' || mode === 'Invasion' || mode === 'Squadron' || mode === 'Story') {
    onTaskMapChange(id);
  }
  updateTraitRow(id);
}

const RAID_ACTS = {
  'GT': ['Hidden Danger', 'Saiyan Hunt', 'Ruler Dragon', 'The Ultimate Evil'],
  'Eclipse': ['Golden Age', 'Golden Age 2', 'Golden Age 3', 'The Eclipse'],
};

const INVASION_ACTS = {
  'The Lava Continent': ['Ashfall Continent', 'Infernal Landmass', 'Magma Rift', 'Scorched Horizon'],
};

function onTaskMapChange(id) {
  const card = document.getElementById('task_' + id);
  if (!card) return;
  const mode = card.querySelector('.tMode').value;
  const map = card.querySelector('.tMap').value;
  const actSel = card.querySelector('.tAct');
  actSel.innerHTML = '';

  if (mode === 'Raid') {
    const acts = RAID_ACTS[map] || RAID_ACTS['GT'];
    for (const a of acts) actSel.innerHTML += `<option>${a}</option>`;
    actSel.disabled = false;
  } else if (mode === 'Invasion') {
    const acts = INVASION_ACTS[map] || INVASION_ACTS['The Lava Continent'];
    for (const a of acts) actSel.innerHTML += `<option>${a}</option>`;
    actSel.disabled = false;
  } else if (mode === 'Squadron' || mode === 'Story') {
    actSel.disabled = false;
    let max = 3;
    if (mode === 'Story') max = 10;
    else if (map === 'Ninja Village' || map === 'Eclipse') max = 4;
    for (let i = 1; i <= max; i++) actSel.innerHTML += `<option>Chapter ${i}</option>`;
  }
  updateTraitRow(id);
}

function removeTask(id) { const el = document.getElementById('task_'+id); if (el) el.remove(); }

// ── Trait Farm (per-task option) ──
let traitStageData = { stages: {}, last_reset: '' };

function traitStageInfo(mode, map, act) {
  if (mode === 'Challenge') {
    if (map === 'Garou') return { key: 'Garou', limit: 30 };
    if (map === 'Aizen') return { key: 'Aizen', limit: 100 };
  } else if (mode === 'Raid') {
    if (map === 'GT' && act === 'The Ultimate Evil') return { key: 'GT — The Ultimate Evil', limit: 100 };
    if (map === 'Eclipse' && act === 'The Eclipse') return { key: 'Eclipse — The Eclipse', limit: 100 };
  }
  return null;
}

function updateTraitRow(id) {
  const card = document.getElementById('task_' + id);
  if (!card) return;
  const row = card.querySelector('.task-row-trait');
  if (!row) return;
  const mode = card.querySelector('.tMode').value;
  const map = card.querySelector('.tMap').value;
  const act = card.querySelector('.tAct').value;
  const info = traitStageInfo(mode, map, act);

  if (!info) {
    row.style.display = 'none';
    delete card.dataset.traitKey;
    return;
  }

  row.style.display = 'flex';
  card.dataset.traitKey = info.key;
  const countInput = card.querySelector('.tTraitCount');
  const limitLabel = card.querySelector('.tTraitLimitLabel');
  const stageData = traitStageData.stages[info.key];
  if (document.activeElement !== countInput) {
    countInput.value = stageData ? stageData.count : 0;
  }
  limitLabel.textContent = '/ ' + info.limit;
}

async function onTaskTraitCountChange(id) {
  const card = document.getElementById('task_' + id);
  if (!card || !card.dataset.traitKey) return;
  const val = parseInt(card.querySelector('.tTraitCount').value) || 0;
  await api().set_trait_count(card.dataset.traitKey, val);
}

async function onTaskTraitReset(id) {
  const card = document.getElementById('task_' + id);
  if (!card || !card.dataset.traitKey) return;
  await api().set_trait_count(card.dataset.traitKey, 0);
  card.querySelector('.tTraitCount').value = 0;
}

async function pollTraitData() {
  try {
    traitStageData = await api().get_trait_state();
    document.querySelectorAll('#taskList .task-card').forEach(card => {
      updateTraitRow(card.id.replace('task_', ''));
    });
  } catch (e) {}
}

// ── Drag & Drop ──
(function() {
  let dragCard = null;
  let ghost = null;
  let indicator = null;
  let offsetY = 0;
  let startY = 0;

  function getLabel(card) {
    const mode = card.querySelector('.tMode')?.value || '?';
    const map = card.querySelector('.tMap')?.value || '';
    const act = card.querySelector('.tAct')?.value || '';
    let s = mode;
    if (map && map !== '-') s += ' — ' + map;
    if (act && act !== '-') s += ' ' + act;
    return s;
  }

  function getDropTarget(y) {
    const list = document.getElementById('taskList');
    const cards = [...list.children].filter(c => c !== dragCard && c.classList.contains('task-card'));
    for (const c of cards) {
      const r = c.getBoundingClientRect();
      if (y < r.top + r.height / 2) return { before: c };
    }
    return { before: null };
  }

  function showIndicator(target) {
    if (!indicator) {
      indicator = document.createElement('div');
      indicator.className = 'drop-indicator';
    }
    const list = document.getElementById('taskList');
    if (target.before) {
      list.insertBefore(indicator, target.before);
    } else {
      list.appendChild(indicator);
    }
  }

  document.addEventListener('mousedown', (e) => {
    const handle = e.target.closest('.drag-handle');
    if (!handle) return;
    e.preventDefault();
    dragCard = handle.closest('.task-card');
    if (!dragCard) return;

    const rect = dragCard.getBoundingClientRect();
    offsetY = e.clientY - rect.top;
    startY = e.clientY;

    ghost = document.createElement('div');
    ghost.className = 'drag-ghost';
    ghost.textContent = getLabel(dragCard);
    document.body.appendChild(ghost);
    ghost.style.left = rect.left + 'px';
    ghost.style.top = (e.clientY - 14) + 'px';
    ghost.style.width = rect.width + 'px';

    dragCard.classList.add('dragging');
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'grabbing';
  });

  document.addEventListener('mousemove', (e) => {
    if (!dragCard || !ghost) return;
    ghost.style.top = (e.clientY - 14) + 'px';
    const target = getDropTarget(e.clientY);
    showIndicator(target);
  });

  document.addEventListener('mouseup', (e) => {
    if (!dragCard) return;
    const list = document.getElementById('taskList');
    const target = getDropTarget(e.clientY);

    if (indicator && indicator.parentNode) {
      list.insertBefore(dragCard, indicator);
      indicator.remove();
    }

    dragCard.classList.remove('dragging');
    if (ghost) ghost.remove();
    ghost = null;
    indicator = null;
    dragCard = null;
    document.body.style.userSelect = '';
    document.body.style.cursor = '';
  });
})();
function clearQueue(keepLoadout) {
  document.getElementById('taskList').innerHTML = '';
  taskIdCounter = 0;
  if (!keepLoadout) {
    document.getElementById('selLoadout').value = '';
    updateDeleteBtn();
  }
}

function getQueueTasks() {
  const tasks = [];
  document.querySelectorAll('#taskList .task-card').forEach(card => {
    tasks.push({
      mode: card.querySelector('.tMode').value,
      repeat: parseInt(card.querySelector('.tRep').value) || 1,
      map: card.querySelector('.tMap').value,
      act: card.querySelector('.tAct').value,
      diff: card.querySelector('.tDiff').value,
      track_trait: card.querySelector('.tTraitTrack').checked,
    });
  });
  return tasks;
}

async function autoSaveQueue() {
  const tasks = getQueueTasks();
  try {
    await api().save_settings_full({
      webhook_url: document.getElementById('txtWebhook').value.trim(),
      webhook_enabled: document.getElementById('chkWebhook').checked,
      webhook_silent: document.getElementById('chkSilent').checked,
      loop: document.getElementById('chkStartOver').checked,
      check_challenges: document.getElementById('chkChallenges').checked,
      challenge_priority: document.getElementById('chkPriority').checked,
      screenshot_mode: document.getElementById('selScreenshot').value,
      desired_rewards: getSelectedRewards(),
      queue: tasks,
    });
    const sel = document.getElementById('selLoadout').value;
    if (sel.startsWith('user:') && tasks.length > 0) {
      await api().save_loadout(sel.replace('user:', ''), tasks);
    }
  } catch (e) {}
}

// ── Loadouts ──
const PRESETS = {
  "Gold & Trait Farm": {
    tasks: [
      { mode: "Squadron", repeat: 999, map: "GT City", act: "Chapter 1", diff: "Normal" },
    ],
    settings: { check_challenges: true, loop: true, rewards: ["trait_reroll.png"] },
  },
};

// ── Quick Loadout: auto-build a Story material farm queue for one map ──
const QUICK_MATERIAL_CHAPTERS = [2, 4, 6, 8, 10];

function quickMaterialFarm() {
  const map = document.getElementById('selQuickMap').value;
  for (const ch of QUICK_MATERIAL_CHAPTERS) {
    addTask({ mode: "Story", repeat: 15, map, act: "Chapter " + ch, diff: "Hard" });
  }
  document.getElementById('chkStartOver').checked = true;
  document.getElementById('selLoadout').value = '';
  updateDeleteBtn();
  showToast('Quick Material Farm — ' + map + ' (Ch. 2/4/6/8/10)');
}

async function refreshLoadouts() {
  const sel = document.getElementById('selLoadout');
  const prev = sel.value;
  sel.innerHTML = '<option value="">-- Loadouts --</option>';

  const newOpt = document.createElement('option');
  newOpt.value = 'new';
  newOpt.textContent = '+ New Loadout';
  sel.appendChild(newOpt);

  const presetGroup = document.createElement('optgroup');
  presetGroup.label = 'Presets';
  for (const name of Object.keys(PRESETS)) {
    const opt = document.createElement('option');
    opt.value = 'preset:' + name;
    opt.textContent = name;
    presetGroup.appendChild(opt);
  }
  sel.appendChild(presetGroup);

  try {
    const loadouts = await api().get_loadouts();
    const keys = Object.keys(loadouts).sort();
    if (keys.length > 0) {
      const userGroup = document.createElement('optgroup');
      userGroup.label = 'My Loadouts';
      for (const name of keys) {
        const opt = document.createElement('option');
        opt.value = 'user:' + name;
        opt.textContent = name;
        userGroup.appendChild(opt);
      }
      sel.appendChild(userGroup);
    }
    if (prev && prev !== 'new') sel.value = prev;
  } catch (e) {}
  updateDeleteBtn();
}

function updateDeleteBtn() {
  const val = document.getElementById('selLoadout').value;
  document.getElementById('btnDelLoadout').style.display = val.startsWith('user:') ? '' : 'none';
}

function showNameInput() {
  document.getElementById('loadoutNameRow').style.display = 'flex';
  const input = document.getElementById('txtLoadoutName');
  input.value = '';
  input.focus();
}

function cancelSaveLoadout() {
  document.getElementById('loadoutNameRow').style.display = 'none';
  document.getElementById('selLoadout').value = '';
}

async function confirmSaveLoadout() {
  const name = document.getElementById('txtLoadoutName').value.trim();
  if (!name) return;
  const tasks = getQueueTasks();
  if (tasks.length === 0) return;
  try {
    await api().save_loadout(name, tasks);
  } catch (e) { return; }
  document.getElementById('loadoutNameRow').style.display = 'none';
  await refreshLoadouts();
  await refreshAppendList();
  document.getElementById('selLoadout').value = 'user:' + name;
  updateDeleteBtn();
}

function applyPresetSettings(settings) {
  if (settings.check_challenges !== undefined) {
    document.getElementById('chkChallenges').checked = settings.check_challenges;
  }
  if (settings.loop !== undefined) {
    document.getElementById('chkStartOver').checked = settings.loop;
  }
  if (settings.rewards) {
    document.querySelectorAll('#rewardList input[type="checkbox"]').forEach(el => {
      el.checked = settings.rewards.includes(el.id.replace('rwd_', ''));
    });
  }
}

async function onLoadoutSelect() {
  const sel = document.getElementById('selLoadout');
  const val = sel.value;
  updateDeleteBtn();

  if (val === 'new') {
    showNameInput();
    return;
  }

  document.getElementById('loadoutNameRow').style.display = 'none';
  if (!val) return;

  if (val.startsWith('preset:')) {
    const name = val.replace('preset:', '');
    const preset = PRESETS[name];
    if (!preset) return;
    clearQueue(true);
    for (const t of preset.tasks) addTask(t);
    if (preset.settings) applyPresetSettings(preset.settings);
    return;
  }

  if (val.startsWith('user:')) {
    const name = val.replace('user:', '');
    try {
      const loadouts = await api().get_loadouts();
      const tasks = loadouts[name];
      if (!tasks) return;
      clearQueue(true);
      for (const t of tasks) addTask(t);
    } catch (e) {}
  }
}

async function refreshAppendList() {
  const sel = document.getElementById('selAppend');
  sel.innerHTML = '<option value="">+</option>';
  for (const name of Object.keys(PRESETS)) {
    const opt = document.createElement('option');
    opt.value = 'preset:' + name;
    opt.textContent = '+ ' + name;
    sel.appendChild(opt);
  }
  try {
    const loadouts = await api().get_loadouts();
    for (const name of Object.keys(loadouts).sort()) {
      const opt = document.createElement('option');
      opt.value = 'user:' + name;
      opt.textContent = '+ ' + name;
      sel.appendChild(opt);
    }
  } catch (e) {}
}

async function onAppendSelect() {
  const sel = document.getElementById('selAppend');
  const val = sel.value;
  sel.value = '';
  if (!val) return;

  let tasks = [], name = '';
  if (val.startsWith('preset:')) {
    name = val.replace('preset:', '');
    const preset = PRESETS[name];
    if (preset) tasks = preset.tasks;
  } else if (val.startsWith('user:')) {
    name = val.replace('user:', '');
    try {
      const loadouts = await api().get_loadouts();
      tasks = loadouts[name] || [];
    } catch (e) {}
  }

  if (tasks.length > 0) {
    for (const t of tasks) addTask(t);
    showToast('+ ' + name + ' (' + tasks.length + ' tasks)');
  }
}

function showToast(msg) {
  let toast = document.getElementById('toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'toast';
    toast.className = 'toast';
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 2000);
}

async function deleteLoadout() {
  const sel = document.getElementById('selLoadout');
  const val = sel.value;
  if (!val || !val.startsWith('user:')) return;
  const name = val.replace('user:', '');
  try {
    await api().delete_loadout(name);
  } catch (e) { return; }
  sel.value = '';
  await refreshLoadouts();
  await refreshAppendList();
}

async function exportLoadout() {
  const tasks = getQueueTasks();
  if (tasks.length === 0) {
    showToast('Nothing to export');
    return;
  }
  const sel = document.getElementById('selLoadout').value;
  let name = 'My Loadout';
  if (sel.startsWith('user:')) name = sel.replace('user:', '');
  else if (sel.startsWith('preset:')) name = sel.replace('preset:', '');
  try {
    const res = await api().export_loadout(name, tasks);
    if (res && res.ok) showToast('Exported ' + name);
  } catch (e) {}
}

async function importLoadout() {
  try {
    const res = await api().import_loadout();
    if (!res || !res.ok) {
      showToast('Import cancelled');
      return;
    }
    await refreshLoadouts();
    await refreshAppendList();
    document.getElementById('selLoadout').value = 'user:' + res.name;
    updateDeleteBtn();
    showToast('Imported ' + res.name + ' (' + res.tasks.length + ' tasks)');
  } catch (e) {}
}

async function startQueue() {
  if (running) return;
  const tasks = getQueueTasks();
  if (tasks.length === 0) {
    showToast('Add a task to the queue before starting');
    const addBtn = document.querySelector('.btn-add');
    if (addBtn) {
      addBtn.classList.remove('btn-attention');
      void addBtn.offsetWidth; // restart animation if already playing
      addBtn.classList.add('btn-attention');
      addBtn.addEventListener('animationend', () => addBtn.classList.remove('btn-attention'), { once: true });
    }
    return;
  }
  const cfg = {
    webhook_url: document.getElementById('txtWebhook').value.trim(),
    webhook_enabled: document.getElementById('chkWebhook').checked,
    webhook_silent: document.getElementById('chkSilent').checked,
    screenshot_mode: document.getElementById('selScreenshot').value,
    check_challenges: document.getElementById('chkChallenges').checked,
    challenge_priority: document.getElementById('chkPriority').checked,
    desired_rewards: getSelectedRewards(),
    start_over: document.getElementById('chkStartOver').checked,
  };
  await api().save_webhook(cfg.webhook_url, cfg.webhook_enabled);
  await api().start_queue(tasks, cfg);
}

function toggleSection(legend) {
  legend.parentElement.classList.toggle('collapsed');
}

async function toggleMacro() {
  if (running) { await api().stop_macro(); }
  else { await startQueue(); }
}
async function stopMacro() { await api().stop_macro(); }
async function positionRoblox() { await api().position_roblox(); }
async function togglePause() {
  const s = await api().get_status();
  if (s.paused) await api().resume_macro();
  else await api().pause_macro();
}
async function launchRoblox() { await api().launch_roblox(); }
async function rejoinGame() { await api().rejoin_game(); }

// ── Auto Update ──
let pendingUpdateUrl = null;

async function checkForUpdate() {
  try {
    const info = await api().check_update();
    if (info && info.version) {
      pendingUpdateUrl = info.download_url;
      document.getElementById('updateText').textContent = `Update v${info.version} available!`;
      document.getElementById('updateBanner').classList.remove('hidden');
      const badge = document.getElementById('verBadge');
      const cur = badge.textContent;
      badge.textContent = `${cur} → v${info.version}`;
      badge.classList.add('ver-badge-update');
      badge.onclick = () => document.getElementById('updateBanner').scrollIntoView({ behavior: 'smooth' });
    }
  } catch (e) {}
}

function onUpdateProgress(pct) {
  document.getElementById('btnUpdate').textContent = pct + '%';
}

async function doUpdate() {
  if (!pendingUpdateUrl) return;
  document.getElementById('btnUpdate').disabled = true;
  document.getElementById('btnUpdate').textContent = '0%';
  try {
    const res = await api().do_update(pendingUpdateUrl);
    if (res && !res.ok) throw new Error('update failed');
  } catch (e) {
    document.getElementById('btnUpdate').textContent = 'Open GitHub';
    document.getElementById('btnUpdate').disabled = false;
    document.getElementById('btnUpdate').onclick = () => api().open_github();
  }
}

// ── Hotkeys / Settings Modal ──
let hotkeys = { stop: 'f2', pause: 'f3', hide: 'f4' };
let rebindingAction = null;

function fmtKeyLabel(key) {
  return (key || '').split('+').map(p => p.length <= 2 ? p.toUpperCase() : p[0].toUpperCase() + p.slice(1)).join('+');
}

async function loadHotkeys() {
  hotkeys = await api().get_hotkeys();
  for (const action of Object.keys(hotkeys)) {
    const btn = document.getElementById('hkBtn_' + action);
    if (btn) btn.textContent = fmtKeyLabel(hotkeys[action]);
  }
}

async function resetHotkey(action) {
  if (rebindingAction) cancelRebind();
  const res = await api().reset_hotkey(action);
  if (res && res.ok) {
    hotkeys[action] = res.key;
    const btn = document.getElementById('hkBtn_' + action);
    if (btn) btn.textContent = fmtKeyLabel(res.key);
  }
}

function openSettingsModal() {
  document.getElementById('settingsModal').classList.remove('hidden');
}

function closeSettingsModal() {
  cancelRebind();
  document.getElementById('settingsModal').classList.add('hidden');
}

function beginRebind(action) {
  if (rebindingAction) cancelRebind();
  rebindingAction = action;
  const btn = document.getElementById('hkBtn_' + action);
  btn.classList.add('listening');
  btn.textContent = 'Press key...';
}

function cancelRebind() {
  if (!rebindingAction) return;
  const btn = document.getElementById('hkBtn_' + rebindingAction);
  if (btn) {
    btn.classList.remove('listening');
    btn.textContent = fmtKeyLabel(hotkeys[rebindingAction]);
  }
  rebindingAction = null;
}

const IGNORED_KEYS = new Set(['Control', 'Shift', 'Alt', 'Meta', 'OS']);
const KEY_NAME_MAP = {
  ' ': 'space', 'arrowup': 'up', 'arrowdown': 'down', 'arrowleft': 'left', 'arrowright': 'right',
  'escape': 'esc', 'delete': 'delete', 'backspace': 'backspace', 'enter': 'enter', 'tab': 'tab',
};

document.addEventListener('keydown', async (e) => {
  if (!rebindingAction) return;
  e.preventDefault();
  e.stopPropagation();

  if (e.key === 'Escape') {
    cancelRebind();
    return;
  }
  if (IGNORED_KEYS.has(e.key)) return;

  const parts = [];
  if (e.ctrlKey) parts.push('ctrl');
  if (e.altKey) parts.push('alt');
  if (e.shiftKey) parts.push('shift');
  const lowerKey = e.key.toLowerCase();
  parts.push(KEY_NAME_MAP[lowerKey] || lowerKey);
  const combo = parts.join('+');

  const action = rebindingAction;
  rebindingAction = null;
  const btn = document.getElementById('hkBtn_' + action);
  btn.classList.remove('listening');

  try {
    const res = await api().set_hotkey(action, combo);
    if (res && res.ok) {
      hotkeys[action] = combo;
      btn.textContent = fmtKeyLabel(combo);
    } else {
      btn.textContent = fmtKeyLabel(hotkeys[action]);
    }
  } catch (err) {
    btn.textContent = fmtKeyLabel(hotkeys[action]);
  }
}, true);

// ── Panel hide/show (F4) ──
window.__hideMacroPanel = function () {
  closeSettingsModal();
  document.getElementById('mainPanel').classList.add('panel-hidden');
};
window.__showMacroPanel = function () {
  document.getElementById('mainPanel').classList.remove('panel-hidden');
};

// ── Tutorial / How to Use ──
let tutorialStep = 0;

function tutorialStepEls() {
  return document.querySelectorAll('#tutorialModal .tutorial-step');
}

function renderTutorialStep() {
  const steps = tutorialStepEls();
  steps.forEach((el, i) => el.classList.toggle('hidden', i !== tutorialStep));

  const dots = document.getElementById('tutorialDots');
  dots.innerHTML = '';
  steps.forEach((_, i) => {
    const dot = document.createElement('span');
    dot.className = 'tutorial-dot' + (i === tutorialStep ? ' active' : '');
    dots.appendChild(dot);
  });

  document.getElementById('btnTutorialBack').style.visibility = tutorialStep === 0 ? 'hidden' : 'visible';
  document.getElementById('btnTutorialNext').textContent = tutorialStep === steps.length - 1 ? 'Done' : 'Next';
}

function tutorialNext() {
  const steps = tutorialStepEls();
  if (tutorialStep >= steps.length - 1) {
    closeTutorialModal();
    return;
  }
  tutorialStep++;
  renderTutorialStep();
}

function tutorialBack() {
  if (tutorialStep === 0) return;
  tutorialStep--;
  renderTutorialStep();
}

function openTutorialModal() {
  tutorialStep = 0;
  renderTutorialStep();
  document.getElementById('tutorialModal').classList.remove('hidden');
}

function closeTutorialModal() {
  document.getElementById('tutorialModal').classList.add('hidden');
  api().save_settings_full({ tutorial_seen: true }).catch(() => {});
}

// ── First-run storage consent ──
let _resolveStorageConsent = null;

function ensureStorageConsent() {
  return new Promise(async (resolve) => {
    let needs = false;
    try { needs = await api().needs_storage_consent(); } catch (e) {}
    if (!needs) { resolve(); return; }
    _resolveStorageConsent = resolve;
    document.getElementById('consentModal').classList.remove('hidden');
  });
}

async function answerStorageConsent(allow) {
  document.getElementById('consentModal').classList.add('hidden');
  if (allow) {
    try { await api().grant_storage_consent(); } catch (e) {}
  }
  if (_resolveStorageConsent) {
    const resolve = _resolveStorageConsent;
    _resolveStorageConsent = null;
    resolve();
  }
}
