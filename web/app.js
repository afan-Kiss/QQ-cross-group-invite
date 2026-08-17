const API = "";

const $ = (id) => document.getElementById(id);

const els = {
  target: $("target"),
  source: $("source"),
  count: $("count"),
  interval: $("interval"),
  filter: $("filter"),
  btnLoad: $("btnLoad"),
  btnStart: $("btnStart"),
  btnStop: $("btnStop"),
  statusPill: $("statusPill"),
  statusText: $("statusText"),
  hint: $("hint"),
  progressFill: $("progressFill"),
  statLine: $("statLine"),
  memberBody: $("memberBody"),
  memberCount: $("memberCount"),
  logBox: $("logBox"),
  frequentBox: $("frequentBox"),
  errorBox: $("errorBox"),
  toast: $("toast"),
};

let members = [];
let loading = false;

function toast(msg) {
  els.toast.textContent = msg;
  els.toast.classList.add("show");
  setTimeout(() => els.toast.classList.remove("show"), 2600);
}

async function api(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `����ʧ�� ${res.status}`);
  return data;
}

function roleLabel(r) {
  return { owner: "Ⱥ��", admin: "����Ա", member: "��Ա" }[r] || "δ֪";
}

function renderMembers() {
  els.memberBody.innerHTML = members
    .map(
      (m) =>
        `<tr><td>${m.qq}</td><td>${escapeHtml(m.nickname)}</td><td>${roleLabel(m.role)}</td></tr>`
    )
    .join("");
  els.memberCount.textContent = `�� ${members.length} ��`;
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function setBusy(running, loadDisabled = false) {
  els.btnStart.disabled = running || loading;
  els.btnStop.disabled = !running;
  els.btnLoad.disabled = loading || running;
}

async function loadConfig() {
  try {
    const cfg = await api("/config");
    els.target.value = cfg.target_group_id || "";
    els.source.value = cfg.source_group_id || "";
    els.count.value = cfg.batch_count || "10";
    els.interval.value = cfg.interval_ms || "2000";
    els.filter.checked = !!cfg.filter_staff;
  } catch (_) {}
}

async function saveConfig(extra = {}) {
  await api("/config", {
    method: "POST",
    body: JSON.stringify({
      target_group_id: els.target.value.trim(),
      source_group_id: els.source.value.trim(),
      batch_count: els.count.value.trim(),
      interval_ms: els.interval.value.trim(),
      filter_staff: els.filter.checked,
      ...extra,
    }),
  });
}

async function checkHealth() {
  try {
    await api("/health");
    els.statusPill.className = "status-pill online";
    els.statusText.textContent = "��̨������";
    return true;
  } catch {
    els.statusPill.className = "status-pill offline";
    els.statusText.textContent = "��̨δ����";
    return false;
  }
}

async function onLoad() {
  if (loading) return;
  const source = parseInt(els.source.value.trim(), 10);
  if (!source) return toast("����д��ԴȺ��");
  if (!(await checkHealth())) return toast("����������̨����");

  loading = true;
  setBusy(false, true);
  els.hint.textContent = "���ڼ��س�Ա...";
  try {
    await saveConfig();
    const data = await api("/members/load", {
      method: "POST",
      body: JSON.stringify({
        source_group_id: source,
        filter_staff: els.filter.checked,
      }),
    });
    members = data.members || [];
    renderMembers();
    if (!members.length) {
      toast("û�м��ص��������Ա������Ⱥ��");
      els.hint.textContent = "������ɣ���û�п������Ա";
    } else {
      toast(`�Ѽ��� ${members.length} ��`);
      els.hint.textContent = `�Ѽ��� ${members.length} �ˣ����Կ�ʼ����`;
    }
  } catch (e) {
    toast(e.message);
    els.hint.textContent = "����ʧ��";
  } finally {
    loading = false;
    setBusy(false, false);
  }
}

async function onStart() {
  const target = parseInt(els.target.value.trim(), 10);
  const source = parseInt(els.source.value.trim(), 10);
  let count = parseInt(els.count.value.trim(), 10);
  const interval = parseInt(els.interval.value.trim(), 10);

  if (!target || !source) return toast("����д����Ⱥ��");
  if (target === source) return toast("Ŀ��Ⱥ����ԴȺ������ͬ");
  if (!(await checkHealth())) return toast("����������̨����");

  if (!count) count = members.length;
  if (!count) return toast("���ȼ��س�Ա�б�");

  setBusy(true);
  els.hint.textContent = "������������...";
  try {
    await saveConfig();
    await api("/invite/start", {
      method: "POST",
      body: JSON.stringify({
        target_group_id: target,
        source_group_id: source,
        count,
        interval_ms: interval || 2000,
        filter_staff: els.filter.checked,
      }),
    });
    toast("�ѿ�ʼ����");
  } catch (e) {
    toast(e.message);
    setBusy(false);
    els.hint.textContent = "����ʧ��";
  }
}

async function onStop() {
  try {
    await api("/invite/stop", { method: "POST", body: "{}" });
    toast("�ѷ���ֹͣ����");
  } catch (e) {
    toast(e.message);
  }
}

function renderStatus(st) {
  const total = st.total || 0;
  const done = st.done || 0;
  const pct = total > 0 ? Math.min(100, Math.round((done / total) * 100)) : st.running ? 8 : 0;
  els.progressFill.style.width = `${pct}%`;

  els.statLine.textContent = `${st.message || "�ȴ���ʼ"}  |  ����� ${done}/${total}  �ɹ� ${st.success || 0}  Ƶ�� ${(st.frequent || []).length}  ʧ�� ${(st.errors || []).length}`;

  if (st.running) {
    els.hint.textContent = `�������룺${st.current_nickname || ""}��QQ ${st.current_qq || ""}��`;
    setBusy(true);
  } else {
    setBusy(false);
    if (st.message) els.hint.textContent = st.message;
  }

  if (st.logs && st.logs.length) {
    els.logBox.textContent = st.logs.join("\n");
    els.logBox.scrollTop = els.logBox.scrollHeight;
  }

  els.frequentBox.innerHTML = (st.frequent || [])
    .map((r) => `<div class="list-item warn">${r.qq}  ${escapeHtml(r.nickname)}  ��  ${escapeHtml(r.reason)}</div>`)
    .join("") || '<div class="list-item">���޼�¼</div>';

  els.errorBox.innerHTML = (st.errors || [])
    .map((r) => `<div class="list-item error">${r.qq}  ${escapeHtml(r.nickname)}  ��  ${escapeHtml(r.reason)}</div>`)
    .join("") || '<div class="list-item">���޼�¼</div>';
}

async function poll() {
  await checkHealth();
  try {
    const st = await api("/status");
    renderStatus(st);
  } catch (_) {}
}

function initTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      $(`panel-${tab.dataset.tab}`).classList.add("active");
    });
  });
}

els.btnLoad.addEventListener("click", onLoad);
els.btnStart.addEventListener("click", onStart);
els.btnStop.addEventListener("click", onStop);

initTabs();
loadConfig();
poll();
setInterval(poll, 450);
