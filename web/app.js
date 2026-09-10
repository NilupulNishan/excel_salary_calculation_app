/* Softvil Salary Slips -- UI logic.
 *
 * The backend (salary_app/api.py) owns all state. This file renders it and
 * sends edits back; it never computes a payroll figure, and never re-formats
 * money itself -- formatted strings come from Python so the form, the preview
 * and the PDF cannot disagree.
 */

const api = () => window.pywebview.api;

const state = {
  employees: [],
  index: -1,
  fieldGroups: [],
  moneyFields: new Set(),
  saveTimer: null,
};

/* ---------- small helpers ---------- */

const $ = (id) => document.getElementById(id);

function show(screenId) {
  document.querySelectorAll('.screen').forEach((s) => s.classList.remove('is-active'));
  $(screenId).classList.add('is-active');
}

let toastTimer = null;
function toast(message, isError = false, ms = 0) {
  const el = $('toast');
  el.textContent = message;
  el.classList.toggle('is-error', isError);
  el.hidden = false;
  clearTimeout(toastTimer);
  const linger = ms || (isError ? 7000 : 3500);
  toastTimer = setTimeout(() => { el.hidden = true; }, linger);
}

/** Every backend call returns {ok, error}. Surface failures instead of
 *  letting them vanish into a rejected promise. */
async function call(fn) {
  try {
    const result = await fn();
    if (result && result.ok === false) {
      toast(result.error || 'Something went wrong', true);
      return null;
    }
    return result;
  } catch (err) {
    toast(String(err), true);
    return null;
  }
}

/* ---------- screen 1: upload ---------- */

function initUpload() {
  const zone = $('dropzone');

  zone.addEventListener('click', browse);
  zone.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); browse(); }
  });

  // pywebview 6.2 has no file-drop event, so a dropped file's path is not
  // available. Read the bytes in the browser and send them across instead.
  ['dragenter', 'dragover'].forEach((type) =>
    zone.addEventListener(type, (e) => {
      e.preventDefault();
      zone.classList.add('is-over');
    }));
  ['dragleave', 'drop'].forEach((type) =>
    zone.addEventListener(type, () => zone.classList.remove('is-over')));

  zone.addEventListener('drop', async (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files && e.dataTransfer.files[0];
    if (!file) return;
    if (!/\.xlsx?$|\.xlsm$/i.test(file.name)) {
      showUploadError('That is not an Excel workbook. Expected .xlsx or .xlsm.');
      return;
    }
    setBusy(true);
    try {
      const b64 = await fileToBase64(file);
      const result = await call(() => api().load_bytes(file.name, b64));
      if (result) onLoaded(result);
    } finally {
      setBusy(false);
    }
  });

  // The whole window should ignore stray drops, or the webview navigates away.
  window.addEventListener('dragover', (e) => e.preventDefault());
  window.addEventListener('drop', (e) => e.preventDefault());
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error);
    reader.onload = () => resolve(String(reader.result).split(',')[1]);
    reader.readAsDataURL(file);
  });
}

async function browse() {
  setBusy(true);
  try {
    const result = await call(() => api().browse());
    if (result && !result.cancelled) onLoaded(result);
  } finally {
    setBusy(false);
  }
}

function setBusy(on) {
  $('upload-busy').hidden = !on;
  if (on) $('upload-error').hidden = true;
}

function showUploadError(message) {
  const el = $('upload-error');
  el.textContent = message;
  el.hidden = false;
}

function onLoaded(result) {
  state.employees = result.employees || [];
  $('list-file').textContent = result.file || '';
  $('list-sheet').textContent =
    `Sheet "${result.sheet}" · header row ${result.headerRow} · ${state.employees.length} employees`;
  renderList();
  show('screen-list');
}

/* ---------- output folder setting ---------- */

/** Reflect the current output folder in the upload screen. */
function showOutputFolder(result) {
  if (!result || !result.folder) return;
  const path = $('output-folder');
  path.textContent = result.folder;
  path.title = result.folder;
  $('output-hint').textContent = result.isDefault
    ? 'Default location. Every payslip you download or export is saved here.'
    : 'Every payslip you download or export is saved here.';
}

async function loadOutputFolder() {
  showOutputFolder(await call(() => api().get_output_folder()));
}

async function chooseOutputFolder() {
  const result = await call(() => api().choose_output_folder());
  if (!result || result.cancelled) return;
  showOutputFolder(result);
  toast(`Payslips will be saved to ${result.folder}`, false, 6000);
}

/* ---------- screen 2: employee list ---------- */

function renderList() {
  const container = $('employee-rows');
  container.textContent = '';

  state.employees.forEach((emp, i) => {
    const row = document.createElement('div');
    row.className = 'row';

    const no = document.createElement('div');
    no.className = 'row-no';
    no.textContent = String(i + 1).padStart(2, '0');

    const main = document.createElement('div');
    main.className = 'row-main';

    const name = document.createElement('div');
    name.className = 'row-name' + (emp.ready ? '' : ' is-missing');
    name.textContent = emp.name;
    if (!emp.ready) name.appendChild(badge('incomplete', 'badge-missing'));
    if (emp.warnings.length) name.appendChild(badge('check figures', 'badge-warn'));

    const sub = document.createElement('div');
    sub.className = 'row-sub';
    sub.textContent = [emp.number && `No ${emp.number}`, emp.designation, emp.sourceRef]
      .filter(Boolean).join('  ·  ');

    main.append(name, sub);

    const net = document.createElement('div');
    net.className = 'row-net';
    net.textContent = emp.net;

    // The whole row opens Review; the button is the row's action.
    row.tabIndex = 0;
    row.setAttribute('role', 'button');
    row.setAttribute('aria-label', `Review ${emp.name}`);
    row.addEventListener('click', () => openReview(i));
    row.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openReview(i); }
    });

    const button = document.createElement('button');
    button.className = 'btn btn-ghost btn-small';
    button.textContent = 'Download PDF';

    if (emp.ready) {
      button.addEventListener('click', (e) => {
        // Without this the row's handler also fires and navigates away
        // mid-download.
        e.stopPropagation();
        downloadFor(i, button);
      });
    } else {
      // Deliberately NOT the disabled attribute: a disabled button swallows
      // the click entirely, so the one row you need to open is the one that
      // ignores you. It looks unavailable, and says why.
      button.classList.add('is-blocked');
      button.setAttribute('aria-disabled', 'true');
      button.title = `Missing: ${emp.missing.join(', ')}`;
      button.addEventListener('click', (e) => {
        e.stopPropagation();
        toast(`Fill in ${emp.missing.join(', ')} first`, true);
        openReview(i);
      });
    }

    const chevron = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    chevron.setAttribute('class', 'row-go');
    chevron.setAttribute('viewBox', '0 0 24 24');
    chevron.setAttribute('aria-hidden', 'true');
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', 'M9 6l6 6-6 6');
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke', 'currentColor');
    path.setAttribute('stroke-width', '2');
    path.setAttribute('stroke-linecap', 'round');
    path.setAttribute('stroke-linejoin', 'round');
    chevron.appendChild(path);

    row.append(no, main, net, button, chevron);
    container.appendChild(row);
  });

  $('list-count').textContent = `${state.employees.length} found`;

  const incomplete = state.employees.filter((e) => !e.ready).length;
  const note = $('list-note');
  if (incomplete) {
    note.textContent =
      `${incomplete} of ${state.employees.length} cannot be exported yet because required ` +
      `fields are blank in the sheet. Open Review to fill them in — Export All skips them.`;
    note.hidden = false;
  } else {
    note.hidden = true;
  }
}

function badge(text, cls) {
  const el = document.createElement('span');
  el.className = `badge ${cls}`;
  el.textContent = text;
  return el;
}

/* ---------- screen 3: review ---------- */

async function openReview(index) {
  const result = await call(() => api().get_slip(index));
  if (!result) return;

  state.index = index;
  state.fieldGroups = result.fields;
  state.moneyFields = new Set(
    result.fields.filter((g) => g.title !== 'Employee')
      .flatMap((g) => g.fields.map((f) => f.name)),
  );

  buildForm(result.slip, result.missing);
  applyResult(result);
  show('screen-review');
}

function buildForm(slip, missing) {
  const form = $('slip-form');
  form.textContent = '';
  const missingSet = new Set(missing || []);

  state.fieldGroups.forEach((group) => {
    const set = document.createElement('fieldset');
    const legend = document.createElement('legend');
    legend.textContent = group.title;
    set.appendChild(legend);

    group.fields.forEach(({ name, label }) => {
      const isMoney = state.moneyFields.has(name);
      const wrap = document.createElement('div');
      wrap.className = 'field' + (isMoney ? ' is-money' : '') +
        (missingSet.has(label) ? ' is-required' : '');

      const el = document.createElement('label');
      el.textContent = label;
      el.htmlFor = `f-${name}`;

      const input = document.createElement('input');
      input.id = `f-${name}`;
      input.name = name;
      input.type = 'text';
      input.value = slip[name] == null ? '' : slip[name];
      input.placeholder = isMoney ? '—' : 'Not in sheet';
      input.addEventListener('input', scheduleSave);
      input.addEventListener('blur', saveNow);

      wrap.append(el, input);
      set.appendChild(wrap);
    });

    form.appendChild(set);
  });
}

/** Debounced so typing does not re-render a PDF on every keystroke. */
function scheduleSave() {
  clearTimeout(state.saveTimer);
  $('preview-busy').hidden = false;
  state.saveTimer = setTimeout(saveNow, 350);
}

async function saveNow() {
  clearTimeout(state.saveTimer);
  if (state.index < 0) return;

  const data = {};
  new FormData($('slip-form')).forEach((value, key) => {
    data[key] = String(value).trim();
  });

  const result = await call(() => api().update_slip(state.index, data));
  $('preview-busy').hidden = true;
  if (!result) return;

  state.employees = result.employees;
  applyResult(result);
}

function applyResult(result) {
  $('preview-img').src = result.preview;

  const slip = result.slip;
  $('review-name').textContent = slip.employee_name || '(no name)';
  $('review-period').textContent =
    [slip.period, slip.display && slip.display.net_salary].filter(Boolean).join('  ·  ');

  const alerts = $('review-alerts');
  alerts.textContent = '';

  if (result.missing && result.missing.length) {
    alerts.appendChild(alertBanner(
      'alert-missing', 'Cannot export yet',
      `Missing: ${result.missing.join(', ')}`));
  }
  (result.warnings || []).forEach((w) => {
    alerts.appendChild(alertBanner('alert-warn', 'Check this figure', w));
  });

  $('btn-download').disabled = Boolean(result.missing && result.missing.length);
}

/* Named `alertBanner`, not `alert`: a top-level `function alert()` does not
 * reliably shadow the built-in `window.alert`, so calls landed on the native
 * dialog and popped a modal reading "alert-missing" instead of rendering the
 * inline banner. Never name a helper after a global. */
function alertBanner(cls, title, body) {
  const el = document.createElement('div');
  el.className = `alert ${cls}`;
  const strong = document.createElement('strong');
  strong.textContent = title;
  el.append(strong, document.createTextNode(body));
  return el;
}

/* ---------- actions ---------- */

/** Export one slip and make the result impossible to miss.
 *
 * Shared by the list row and the review screen so both give the same
 * feedback: a lingering path, then Explorer opened with the file selected.
 */
async function downloadFor(index, button) {
  const label = button ? button.textContent : null;
  if (button) { button.disabled = true; button.textContent = 'Saving…'; }
  try {
    const result = await call(() => api().export_one(index));
    if (!result) return;
    toast(`Saved to ${result.path}`, false, 8000);
    call(() => api().reveal(result.path));
  } finally {
    if (button) { button.disabled = false; button.textContent = label; }
  }
}

async function exportAll() {
  const button = $('btn-export-all');
  button.disabled = true;
  try {
    const result = await call(() => api().export_all());
    if (!result) return;
    const parts = [`Exported ${result.written.length} payslip(s) to ${result.folder}`];
    if (result.skipped.length) {
      parts.push(`Skipped ${result.skipped.length}: ` +
        result.skipped.map((s) => s.name).join(', '));
    }
    toast(parts.join('\n'));
  } finally {
    button.disabled = false;
  }
}

/* ---------- wiring ---------- */

function initEvents() {
  $('btn-change').addEventListener('click', () => show('screen-upload'));
  $('btn-back').addEventListener('click', () => { renderList(); show('screen-list'); });
  $('btn-export-all').addEventListener('click', exportAll);
  $('btn-open-folder').addEventListener('click', () => call(() => api().open_folder()));

  $('btn-download').addEventListener('click', async () => {
    await saveNow();                       // flush any pending form edits
    await downloadFor(state.index, $('btn-download'));
  });

  $('btn-print').addEventListener('click', async () => {
    await saveNow();
    const result = await call(() => api().print_slip(state.index));
    if (result) toast(result.printed ? 'Sent to printer' : 'Opened for printing');
  });
}

window.addEventListener('pywebviewready', () => {
  initUpload();
  initEvents();
  $('btn-choose-folder').addEventListener('click', chooseOutputFolder);
  loadOutputFolder();
});
