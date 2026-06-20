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
  try { await refreshLoadouts(); } catch (e) {}

  setInterval(pollStatus, 250);
  setInterval(autoSaveQueue, 10000);

  document.getElementById('txtLoadoutName').addEventListener('keydown', e => {
    if (e.key === 'Enter') confirmSaveLoadout();
    if (e.key === 'Escape') cancelSaveLoadout();
  });
});

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

    document.getElementById('txtState').textContent = s.state;
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
      el.innerHTML += `<div class="reward-item"><input type="checkbox" id="${id}" checked><label for="${id}">${label}</label></div>`;
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
      <div class="actions">
        <button class="btn-move" onclick="moveTask(${id},-1)">▲</button>
        <button class="btn-move" onclick="moveTask(${id},1)">▼</button>
      </div>
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
    mapSel.innerHTML = '<option>-</option>'; mapSel.disabled = true;
    actSel.innerHTML = '<option>Hidden Danger</option><option>Saiyan Hunt</option><option>Ruler Dragon</option><option>The Ultimate Evil</option>';
    actSel.disabled = false; diffSel.disabled = false;
  } else if (mode === 'Squadron' || mode === 'Story') {
    mapSel.innerHTML = '<option>GT City</option><option>Marine Lobby</option><option>Ninja Village</option>';
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
  } else if (mode === 'Squadron' || mode === 'Story') {
    onTaskMapChange(id);
  }
}

function onTaskMapChange(id) {
  const card = document.getElementById('task_' + id);
  if (!card) return;
  const mode = card.querySelector('.tMode').value;
  if (mode !== 'Squadron' && mode !== 'Story') return;
  const story = card.querySelector('.tMap').value;
  const actSel = card.querySelector('.tAct');
  actSel.innerHTML = '';
  let max = 3;
  if (mode === 'Story') max = 10;
  else if (story === 'Ninja Village') max = 4;
  for (let i = 1; i <= max; i++) actSel.innerHTML += `<option>Chapter ${i}</option>`;
}

function removeTask(id) { const el = document.getElementById('task_'+id); if (el) el.remove(); }
function moveTask(id, dir) {
  const list = document.getElementById('taskList');
  const el = document.getElementById('task_'+id);
  if (!el) return;
  if (dir===-1 && el.previousElementSibling) list.insertBefore(el, el.previousElementSibling);
  if (dir===1 && el.nextElementSibling) list.insertBefore(el.nextElementSibling, el);
}
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
  "Big 3 Secret": {
    tasks: [
      { mode: "Story", repeat: 10, map: "GT City", act: "Chapter 10", diff: "Hard" },
      { mode: "Story", repeat: 10, map: "Marine Lobby", act: "Chapter 10", diff: "Hard" },
      { mode: "Story", repeat: 10, map: "Ninja Village", act: "Chapter 10", diff: "Hard" },
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
    desired_rewards: getSelectedRewards(),
    start_over: document.getElementById('chkStartOver').checked,
  };
  await api().save_webhook(cfg.webhook_url, cfg.webhook_enabled);
  await api().start_queue(tasks, cfg);
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
