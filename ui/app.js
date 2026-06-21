let running = false;
let taskIdCounter = 0;

function api() { return window.pywebview.api; }

window.addEventListener('pywebviewready', async () => {
  try {
    await loadRewards();
  } catch (e) { console.error('loadRewards', e); }

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
  } catch (e) { console.error('loadSettings', e); }

  try { await api().start_roblox_poll(); } catch (e) {}

  try {
    const ver = await api().get_version();
    document.getElementById('versionLabel').textContent = 'v' + ver;
  } catch (e) {}

  try { checkForUpdate(); } catch (e) {}
  try { await refreshLoadouts(); await refreshAppendList(); } catch (e) {}

  setInterval(pollStatus, 250);
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
    running = s.running;
    document.getElementById('btnStart').disabled = running;
    document.getElementById('btnStop').disabled = !running;

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
    if (s.use_task_queue && s.task_count > 0) {
      document.getElementById('txtStats').textContent =
        `Task ${s.current_task_index}/${s.task_count}  |  Run ${s.task_run_count}/${s.task_run_target}  |  V:${s.victory_count}  D:${s.defeat_count}`;
    } else {
      document.getElementById('txtStats').textContent =
        `Runs: ${s.run_count}  |  V: ${s.victory_count}  |  D: ${s.defeat_count}`;
    }
  } catch (e) {}
}

// ── Rewards ──
async function loadRewards() {
  const el = document.getElementById('rewardList');
  try {
    const files = await api().get_reward_files();
    if (!files || files.length === 0) {
      el.innerHTML = '<span class="muted">No reward PNGs found</span>';
      return;
    }
    el.innerHTML = '';
    for (const f of files) {
      const label = f.replace('.png', '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
      const id = 'rwd_' + f;
      el.innerHTML += `<div class="reward-item"><input type="checkbox" id="${id}"><label for="${id}">${label}</label></div>`;
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

  div.innerHTML = `
    <div class="task-row-top">
      <select class="tMode" onchange="onTaskModeChange(${id})">
        <option ${mode==='Challenge'?'selected':''}>Challenge</option>
        <option ${mode==='Raid'?'selected':''}>Raid</option>
        <option ${mode==='Squadron'?'selected':''}>Squadron</option>
        <option ${mode==='Story'?'selected':''}>Story</option>
        <option ${mode==='Aizen'?'selected':''}>Aizen</option>
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
  `;
  document.getElementById('taskList').appendChild(div);
  onTaskModeChange(id, preset);
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
}

function onTaskModeChange(id, preset) {
  const card = document.getElementById('task_' + id);
  if (!card) return;
  const mode = card.querySelector('.tMode').value;
  const mapSel = card.querySelector('.tMap');
  const actSel = card.querySelector('.tAct');
  const diffSel = card.querySelector('.tDiff');
  mapSel.onchange = null;

  if (mode === 'Raid') {
    mapSel.innerHTML = '<option>GT</option><option>Eclipse</option>';
    mapSel.disabled = false; mapSel.onchange = () => onTaskMapChange(id);
    diffSel.disabled = false;
  } else if (mode === 'Squadron' || mode === 'Story') {
    mapSel.innerHTML = '<option>GT City</option><option>Marine Lobby</option><option>Ninja Village</option><option>Eclipse</option>';
    mapSel.disabled = false; mapSel.onchange = () => onTaskMapChange(id);
    diffSel.disabled = false;
  } else if (mode === 'Aizen') {
    mapSel.innerHTML = '<option>-</option>'; mapSel.disabled = true;
    actSel.innerHTML = '<option>-</option>'; actSel.disabled = true;
    diffSel.disabled = false;
  } else {
    mapSel.innerHTML = '<option>-</option>'; mapSel.disabled = true;
    actSel.innerHTML = '<option>-</option>'; actSel.disabled = true;
    diffSel.disabled = true;
  }

  if (preset) {
    applyPreset(id, preset);
  } else if (mode === 'Raid' || mode === 'Squadron' || mode === 'Story') {
    onTaskMapChange(id);
  }
}

const RAID_ACTS = {
  'GT': ['Hidden Danger', 'Saiyan Hunt', 'Ruler Dragon', 'The Ultimate Evil'],
  'Eclipse': ['Golden Age', 'Golden Age 2', 'Golden Age 3', 'The Eclipse'],
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
  } else if (mode === 'Squadron' || mode === 'Story') {
    actSel.disabled = false;
    let max = 3;
    if (mode === 'Story') max = 10;
    else if (map === 'Ninja Village' || map === 'Eclipse') max = 4;
    for (let i = 1; i <= max; i++) actSel.innerHTML += `<option>Chapter ${i}</option>`;
  }
}

function removeTask(id) { const el = document.getElementById('task_'+id); if (el) el.remove(); }

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
  "Secret Mats": {
    tasks: [
      { mode: "Story", repeat: 15, map: "GT City", act: "Chapter 10", diff: "Hard" },
      { mode: "Story", repeat: 15, map: "Marine Lobby", act: "Chapter 10", diff: "Hard" },
      { mode: "Story", repeat: 15, map: "Ninja Village", act: "Chapter 10", diff: "Hard" },
    ],
    settings: { loop: true },
  },
  "Mythic Mats": {
    tasks: [
      { mode: "Story", repeat: 10, map: "GT City", act: "Chapter 8", diff: "Hard" },
      { mode: "Story", repeat: 10, map: "Marine Lobby", act: "Chapter 8", diff: "Hard" },
      { mode: "Story", repeat: 10, map: "Ninja Village", act: "Chapter 8", diff: "Hard" },
    ],
    settings: { loop: true },
  },
  "Legendary Mats": {
    tasks: [
      { mode: "Story", repeat: 10, map: "GT City", act: "Chapter 6", diff: "Hard" },
      { mode: "Story", repeat: 10, map: "Marine Lobby", act: "Chapter 6", diff: "Hard" },
      { mode: "Story", repeat: 10, map: "Ninja Village", act: "Chapter 6", diff: "Hard" },
    ],
    settings: { loop: true },
  },
  "Epic Mats": {
    tasks: [
      { mode: "Story", repeat: 10, map: "GT City", act: "Chapter 4", diff: "Hard" },
      { mode: "Story", repeat: 10, map: "Marine Lobby", act: "Chapter 4", diff: "Hard" },
      { mode: "Story", repeat: 10, map: "Ninja Village", act: "Chapter 4", diff: "Hard" },
    ],
    settings: { loop: true },
  },
  "Rare Mats": {
    tasks: [
      { mode: "Story", repeat: 10, map: "GT City", act: "Chapter 2", diff: "Hard" },
      { mode: "Story", repeat: 10, map: "Marine Lobby", act: "Chapter 2", diff: "Hard" },
      { mode: "Story", repeat: 10, map: "Ninja Village", act: "Chapter 2", diff: "Hard" },
    ],
    settings: { loop: true },
  },
};

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

async function startQueue() {
  if (running) return;
  const tasks = getQueueTasks();
  if (tasks.length === 0) return;
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

async function stopMacro() { await api().stop_macro(); }
async function positionRoblox() { await api().position_roblox(); }
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
    await api().do_update(pendingUpdateUrl);
  } catch (e) {
    document.getElementById('btnUpdate').textContent = 'Failed';
    document.getElementById('btnUpdate').disabled = false;
  }
}
