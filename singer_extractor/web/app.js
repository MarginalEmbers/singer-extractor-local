import { AudioTransport, clamp, formatTime, isCovered, selectionBetween, visibleWindow } from "./timeline.mjs?v=0.2.0";

const $ = (id) => document.getElementById(id);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));
const player = new AudioTransport();
const state = {
  project: null, buffers: {}, position: 0, start: 0, end: 1,
  referenceStart: 0, referenceSource: "song", monitor: "original",
  zoom: 1, viewStart: 0, busy: false, job: null, referencePlaying: false,
};
let animation = null, dragging = null;

function status(text, error = false) {
  $("status").textContent = text;
  $("status").classList.toggle("error", error);
  $("global-status").textContent = error ? text : "";
}

async function api(path, options = {}) {
  const headers = { "X-Singer-Client": "timeline", ...(options.headers || {}) };
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(options.body);
  }
  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
    let message = "请求失败：" + response.status;
    try {
      const data = await response.json();
      message = typeof data.detail === "string" ? data.detail : "参数无效，请检查选区和参考时间。";
    } catch { /* Keep the HTTP status. */ }
    throw new Error(message);
  }
  return response.json();
}

function persist() {
  if (!state.project) return;
  try {
    localStorage.setItem("singer-timeline-v2", JSON.stringify({
      id: state.project.id, start: state.start, end: state.end,
      referenceStart: state.referenceStart, referenceSource: state.referenceSource,
      monitor: state.monitor,
    }));
  } catch { /* Storage may be disabled; audio processing still works. */ }
}

function duration() { return state.project?.duration || 1; }
function view() { return visibleWindow(duration(), state.zoom, state.viewStart); }
function referenceDuration() {
  return state.referenceSource === "reference" ? state.project.reference.duration : duration();
}
function referenceBuffer() {
  return state.referenceSource === "reference" ? state.buffers.reference : state.buffers.original;
}

function pause() {
  const wasPlaying = player.playing;
  const position = player.pause();
  if (wasPlaying && !state.referencePlaying) state.position = position;
  state.referencePlaying = false;
  if (animation !== null) cancelAnimationFrame(animation);
  animation = null;
  renderTransport();
}

function renderTransport() {
  $("clock").textContent = (state.referencePlaying ? "参考 " : "") + formatTime(
    state.referencePlaying ? player.position() : state.position, true,
  );
  $("seek").value = state.position;
  $("play").textContent = player.playing && !state.referencePlaying ? "暂停" : "播放";
  $("play").setAttribute("aria-pressed", String(player.playing && !state.referencePlaying));
  $("hear-reference").textContent = state.referencePlaying ? "停止参考试听" : "循环试听这 3 秒";
  const window = view();
  $$(".playhead").forEach((element) => {
    const percent = (state.position - window.start) / window.span * 100;
    element.hidden = percent < 0 || percent > 100;
    element.style.left = percent + "%";
  });
}

function animate() {
  if (!player.playing) { renderTransport(); animation = null; return; }
  if (!state.referencePlaying) state.position = player.position();
  renderTransport();
  animation = requestAnimationFrame(animate);
}
function startAnimation() {
  if (animation !== null) cancelAnimationFrame(animation);
  animation = requestAnimationFrame(animate);
}
player.onEnded = () => {
  if (!state.referencePlaying) state.position = player.position();
  state.referencePlaying = false;
  renderTransport();
};

async function play() {
  if (!state.project || !state.buffers[state.monitor]) return;
  if (player.playing && !state.referencePlaying) { pause(); return; }
  pause();
  const loop = $("loop").checked;
  let end = loop ? state.end : duration();
  if (state.monitor !== "original" && !state.project.complete) end = state.end;
  let begin = state.position;
  if (begin >= end || (loop && begin < state.start)) begin = state.start;
  state.position = begin;
  await player.play(state.buffers[state.monitor], begin, end, loop, state.start);
  startAnimation();
}

async function hearReference() {
  if (state.referencePlaying) { pause(); return; }
  pause();
  state.referencePlaying = true;
  await player.play(referenceBuffer(), state.referenceStart, state.referenceStart + 3, true, state.referenceStart);
  renderTransport(); startAnimation();
}

async function monitor(track) {
  if (!state.project) return;
  if (track !== "original" && !state.project.coverage.length) {
    status("目标音轨尚未处理，请先提取一个片段。"); return;
  }
  if (state.referencePlaying) pause();
  state.monitor = track;
  const position = state.position;
  if (player.playing) state.position = await player.switchBuffer(state.buffers[track]);
  else { player.offset = position; state.position = position; }
  render(); persist();
}

async function seek(position) {
  const wasPlaying = player.playing && !state.referencePlaying;
  const oldEnd = player.end, oldLoop = player.loop, loopStart = player.loopStart;
  pause();
  state.position = clamp(position, 0, duration());
  player.offset = state.position;
  if (wasPlaying && state.position < oldEnd) {
    await player.play(state.buffers[state.monitor], state.position, oldEnd, oldLoop, loopStart);
    startAnimation();
  }
  renderTransport();
}

function updateVolume() {
  player.setVolume(Number($("volume").value) / 100 / (state.project?.playback_peak || 1));
}

function renderSelection() {
  if (!state.project) return;
  const window = view();
  const apply = (element, start, end) => {
    const left = clamp((start - window.start) / window.span, 0, 1);
    const right = clamp((end - window.start) / window.span, 0, 1);
    element.hidden = right <= left;
    element.style.left = left * 100 + "%";
    element.style.width = (right - left) * 100 + "%";
  };
  $$(".selection-overlay").forEach((element) => apply(element, state.start, state.end));
  $$(".reference-overlay").forEach((element) => {
    apply(element, state.referenceStart, state.referenceStart + 3);
    if (state.referenceSource !== "song") element.hidden = true;
  });
  $("selection-readout").textContent = formatTime(state.start, true) + "–" + formatTime(state.end, true);
  $("selection-duration").textContent = (state.end - state.start).toFixed(2) + " 秒 · 只重做这段，其他结果保持不变";
  $("selection-start").value = state.start.toFixed(2);
  $("selection-end").value = state.end.toFixed(2);
  $("reference-range").textContent = formatTime(state.referenceStart, true) + "–" + formatTime(state.referenceStart + 3, true);
  $("reference-start").value = state.referenceStart.toFixed(2);
  $("reference-slider").value = state.referenceStart;
  $("reference-start").max = referenceDuration() - 3;
  $("reference-slider").max = referenceDuration() - 3;
  updateButtons();
}

function updateButtons() {
  const project = state.project;
  const disabled = state.busy || !project;
  [
    "import-first", "import-next", "demo", "import-reference",
    "extract-selection", "extract-full", "mute",
  ].forEach((id) => { $(id).disabled = state.busy; });
  $("undo").disabled = disabled || !project.undo_available;
  $("export-selection").disabled = disabled || !isCovered(project.coverage, state.start, state.end, 1 / project.sample_rate);
  $("export-full").disabled = disabled || !project.complete;
  ["reference-source", "reference-start", "reference-slider", "device", "embedding-rate"].forEach((id) => { $(id).disabled = disabled; });
  $$("[data-monitor]").forEach((button) => {
    button.disabled = !project || (button.dataset.monitor !== "original" && !project.coverage.length);
  });
}

function canvasContext(canvas) {
  const rect = canvas.getBoundingClientRect(), ratio = window.devicePixelRatio || 1;
  const width = Math.max(1, Math.round(rect.width)), height = Math.max(1, Math.round(rect.height));
  canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
  const context = canvas.getContext("2d");
  context.scale(ratio, ratio);
  return { context, width, height };
}

function draw() {
  if (!state.project) return;
  const styles = getComputedStyle(document.documentElement);
  const color = (token) => styles.getPropertyValue(token).trim();
  // Resolve light-dark() tokens through the browser before sending them to Canvas.
  const colors = {};
  for (const token of ["--muted", "--line", "--wave", "--accent", "--unprocessed"]) {
    const probe = document.createElement("span");
    probe.style.color = color(token); probe.hidden = true;
    document.body.append(probe); colors[token] = getComputedStyle(probe).color; probe.remove();
  }
  const window = view();
  const scale = state.project.playback_peak;
  $$(".wave-wrap").forEach((element) => {
    const track = element.dataset.track;
    const { context: ctx, width, height } = canvasContext(element.querySelector("canvas"));
    const peaks = state.project.waveforms[track];
    if (track !== "original") {
      ctx.fillStyle = colors["--unprocessed"]; ctx.fillRect(0, 0, width, height);
      for (const [begin, end] of state.project.coverage) {
        const x1 = (begin - window.start) / window.span * width;
        const x2 = (end - window.start) / window.span * width;
        ctx.clearRect(x1, 0, x2 - x1, height);
      }
      if (!state.project.coverage.length) {
        ctx.fillStyle = colors["--muted"]; ctx.font = "12px system-ui"; ctx.textAlign = "center";
        ctx.fillText("尚未处理", width / 2, height / 2 + 4); return;
      }
    }
    ctx.strokeStyle = colors["--line"]; ctx.lineWidth = 0.5; ctx.beginPath();
    ctx.moveTo(0, height / 2); ctx.lineTo(width, height / 2); ctx.stroke();
    ctx.fillStyle = track === "target" ? colors["--accent"] : colors["--wave"];
    ctx.globalAlpha = track === "residual" ? 0.7 : 1;
    for (let x = 0; x < width; x += 2) {
      const t0 = window.start + x / width * window.span;
      const t1 = window.start + (x + 2) / width * window.span;
      if (track !== "original" && !state.project.coverage.some(([a, b]) => t1 >= a && t0 <= b)) continue;
      const begin = clamp(Math.floor(t0 / duration() * peaks.length), 0, peaks.length - 1);
      const end = clamp(Math.ceil(t1 / duration() * peaks.length), begin + 1, peaks.length);
      let low = 0, high = 0;
      for (let i = begin; i < end; i++) { low = Math.min(low, peaks[i][0]); high = Math.max(high, peaks[i][1]); }
      const top = height / 2 - high / scale * height * .44;
      const bottom = height / 2 - low / scale * height * .44;
      ctx.fillRect(x, top, 1.4, Math.max(1, bottom - top));
    }
  });
  const { context: ctx, width, height } = canvasContext($("ruler"));
  ctx.font = "11px system-ui"; ctx.fillStyle = colors["--muted"]; ctx.strokeStyle = colors["--line"];
  const count = Math.max(2, Math.floor(width / 85));
  for (let i = 0; i <= count; i++) {
    const x = i / count * width;
    ctx.textAlign = i === 0 ? "left" : i === count ? "right" : "center";
    ctx.fillText(formatTime(window.start + i / count * window.span), x, 14);
    ctx.beginPath(); ctx.moveTo(x, height - 6); ctx.lineTo(x, height); ctx.stroke();
  }
  renderSelection(); renderTransport();
}

function render() {
  if (!state.project) return;
  const project = state.project, window = view();
  $("empty").hidden = true; $("workspace").hidden = false;
  $("song-name").textContent = project.name;
  $("song-meta").textContent = formatTime(project.duration, true) + " · " + project.sample_rate.toLocaleString() + " Hz · 输出单声道";
  $("total-time").textContent = formatTime(project.duration);
  $("demo-notice").hidden = !project.demo;
  $("seek").max = project.duration;
  $("zoom-value").textContent = state.zoom + "×";
  $("pan").max = Math.max(0, project.duration - window.span); $("pan").value = window.start;
  $("pan").disabled = state.zoom === 1;
  $("view-range").textContent = formatTime(window.start) + "–" + formatTime(window.start + window.span);
  const percentage = project.coverage.reduce((sum, [a, b]) => sum + b - a, 0) / project.duration * 100;
  $("coverage-label").textContent = "已处理或手动静音：" + percentage.toFixed(1) + "%";
  $("target-state").textContent = project.complete ? "全曲已处理" : percentage ? percentage.toFixed(1) + "% 已处理" : "尚未处理";
  $("reference-source").value = state.referenceSource;
  $("reference-source").querySelector('[value="reference"]').disabled = !project.reference;
  $("reference-name").textContent = state.referenceSource === "reference"
    ? project.reference.name : "选只有 A 演唱的片段，尽量避免 B 和明显干扰。";
  $$("[data-monitor]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.monitor === state.monitor)));
  $$(".wave-wrap").forEach((element) => element.classList.toggle("listening", element.dataset.track === state.monitor));
  $("monitor-label").textContent = "正在试听：" + { original: "原曲", target: "目标 A", residual: "残差" }[state.monitor];
  renderSelection(); draw(); updateVolume();
}

async function loadAudio(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error("音频载入失败，请重新导入歌曲。");
  return player.getContext().decodeAudioData(await response.arrayBuffer());
}

async function installProject(project, fresh = false) {
  pause();
  const previousId = state.project?.id;
  const nextBuffers = { ...state.buffers };
  const tasks = ["target", "residual"];
  if (fresh || previousId !== project.id || !nextBuffers.original) tasks.push("original");
  if (project.reference) tasks.push("reference");
  await Promise.all(tasks.map(async (name) => { nextBuffers[name] = await loadAudio(project.audio[name]); }));
  state.project = project;
  state.buffers = nextBuffers;
  if (fresh || previousId !== project.id) {
    state.position = 0; state.start = 0; state.end = Math.min(30, project.duration);
    state.referenceStart = 0; state.referenceSource = "song";
    state.monitor = "original"; state.zoom = 1; state.viewStart = 0; $("zoom").value = 1;
    $("downloads").replaceChildren();
  }
  if (!project.coverage.length) state.monitor = "original";
  render(); persist();
}

async function operation(action) {
  if (state.busy) return;
  state.busy = true; updateButtons();
  try { await action(); }
  catch (error) { status(error.message, true); }
  finally { state.busy = false; updateButtons(); }
}

async function importSong(file) {
  if (!file) return;
  await operation(async () => {
    pause(); status("正在导入并生成波形…");
    const form = new FormData(); form.append("file", file);
    const project = await api("/api/projects", { method: "POST", body: form });
    await installProject(project, true);
    status("先找到 A 独唱的片段，切换“参考 3 秒”工具后在波形上选取。");
  });
}

async function extract(whole) {
  await operation(async () => {
    pause();
    const job = await api("/api/projects/" + state.project.id + "/extract", {
      method: "POST", body: {
        start: state.start, end: state.end, whole,
        reference_start: state.referenceStart, reference_source: state.referenceSource,
        device: $("device").value, embedding_rate: Number($("embedding-rate").value),
      },
    });
    await watchJob(job);
  });
}

async function watchJob(job) {
  state.job = job.id;
  $("cancel").hidden = false; $("cancel").disabled = false;
  $("job-progress").hidden = false;
  try {
    let current = job;
    while (["queued", "running"].includes(current.status)) {
      $("job-progress").value = current.progress;
      status(current.message + " · " + formatTime(current.start) + "–" + formatTime(current.end) + " · " + Math.round(current.progress * 100) + "%");
      await new Promise((resolve) => setTimeout(resolve, 650));
      current = await api("/api/jobs/" + job.id);
    }
    const project = await api("/api/projects/" + job.project_id);
    await installProject(project);
    if (current.status === "completed") {
      state.monitor = "target"; state.position = current.start;
      $("job-progress").value = 1;
      status("处理完成。切换原曲 / 目标 A 试听；灰色区域仍未处理。");
      render(); persist();
    } else if (current.status === "failed") throw new Error(current.message);
    else status(current.message);
  } finally {
    state.job = null; $("cancel").hidden = true; $("job-progress").hidden = true;
  }
}

async function exportAudio(whole) {
  await operation(async () => {
    status("正在写入 WAV 和处理记录…");
    const result = await api("/api/projects/" + state.project.id + "/export", {
      method: "POST", body: { start: state.start, end: state.end, whole },
    });
    $("downloads").replaceChildren();
    const labels = { "stems.zip": "打包下载", "target.wav": "目标 A", "residual.wav": "残差", "report.json": "处理记录" };
    for (const name of ["stems.zip", "target.wav", "residual.wav", "report.json"]) {
      const link = document.createElement("a");
      link.href = result.files[name]; link.download = name; link.textContent = labels[name];
      $("downloads").append(link);
    }
    status("已导出 " + formatTime(result.duration, true) + "；文件也保存在项目 outputs 文件夹中。");
  });
}

function catchAsync(action) {
  return (...args) => Promise.resolve(action(...args)).catch((error) => status(error.message, true));
}
["import-first", "import-next"].forEach((id) => { $(id).onclick = () => $("song-file").click(); });
$("song-file").onchange = () => { importSong($("song-file").files[0]); $("song-file").value = ""; };
$("demo").onclick = () => operation(async () => {
  status("正在生成自检音频…");
  await installProject(await api("/api/projects/demo", { method: "POST" }), true);
  status("已载入合成自检音；它可以测试操作流程，不用于判断歌声分离质量。");
});
$("import-reference").onclick = () => $("reference-file").click();
$("reference-file").onchange = () => {
  const file = $("reference-file").files[0]; $("reference-file").value = "";
  if (!file) return;
  operation(async () => {
    const form = new FormData(); form.append("file", file);
    const project = await api("/api/projects/" + state.project.id + "/reference", { method: "POST", body: form });
    await installProject(project); state.referenceSource = "reference"; state.referenceStart = 0;
    render(); persist(); status("已导入独立参考，请试听确认这 3 秒。");
  });
};
$("play").onclick = catchAsync(play);
$("hear-reference").onclick = catchAsync(hearReference);
$$("[data-monitor]").forEach((button) => { button.onclick = catchAsync(() => monitor(button.dataset.monitor)); });
$("seek").oninput = catchAsync(() => seek(Number($("seek").value)));
$("volume").oninput = updateVolume;
$("loop").onchange = () => { if (player.playing) pause(); };
$("reference-source").onchange = () => {
  pause(); state.referenceSource = $("reference-source").value; state.referenceStart = 0; render(); persist();
};
function changeReference(value) {
  if (!state.project || state.busy || !Number.isFinite(value)) return;
  if (state.referencePlaying) pause();
  state.referenceStart = clamp(value, 0, referenceDuration() - 3); renderSelection(); persist();
}
$("reference-start").onchange = () => changeReference(Number($("reference-start").value));
$("reference-slider").oninput = () => changeReference(Number($("reference-slider").value));
$("tool").onchange = () => {
  if ($("tool").value === "reference" && !state.busy) {
    state.referenceSource = "song"; state.referenceStart = clamp(state.referenceStart, 0, duration() - 3);
    render(); persist();
  }
};
$("selection-start").onchange = () => {
  const value = Number($("selection-start").value);
  if (Number.isFinite(value)) state.start = clamp(value, 0, state.end - 1 / state.project.sample_rate);
  renderSelection(); persist();
};
$("selection-end").onchange = () => {
  const value = Number($("selection-end").value);
  if (Number.isFinite(value)) state.end = clamp(value, state.start + 1 / state.project.sample_rate, duration());
  renderSelection(); persist();
};
$("zoom").oninput = () => {
  state.zoom = Number($("zoom").value);
  const span = duration() / state.zoom;
  state.viewStart = clamp(state.position - span * .25, 0, duration() - span); render();
};
$("pan").oninput = () => { state.viewStart = Number($("pan").value); render(); };
$("fit").onclick = () => { state.zoom = 1; state.viewStart = 0; $("zoom").value = 1; render(); };
$("extract-selection").onclick = () => extract(false);
$("extract-full").onclick = () => extract(true);
$("cancel").onclick = catchAsync(async () => {
  if (state.job) { $("cancel").disabled = true; const job = await api("/api/jobs/" + state.job + "/cancel", { method: "POST" }); status(job.message); }
});
$("mute").onclick = () => operation(async () => {
  pause();
  await installProject(await api("/api/projects/" + state.project.id + "/mute", {
    method: "POST", body: { start: state.start, end: state.end },
  }));
  status("已将选区中的目标输出设为静音，可撤销。");
});
async function undo() {
  if (!state.project?.undo_available) return;
  await operation(async () => {
    pause(); await installProject(await api("/api/projects/" + state.project.id + "/undo", { method: "POST" }));
    status("已恢复上一步操作前的音频和处理范围。");
  });
}
$("undo").onclick = undo;
$("export-selection").onclick = () => exportAudio(false);
$("export-full").onclick = () => exportAudio(true);

function pointerTime(event, element) {
  const rect = element.getBoundingClientRect(), window = view();
  return clamp(window.start + (event.clientX - rect.left) / rect.width * window.span, 0, duration());
}
$$(".wave-wrap").forEach((element) => {
  element.addEventListener("pointerdown", (event) => {
    if (!state.project || event.button !== 0) return;
    const time = pointerTime(event, element);
    dragging = { anchor: time, x: event.clientX, moved: false, element };
    element.setPointerCapture(event.pointerId);
    if ($("tool").value === "reference" && element.dataset.track === "original" && !state.busy) {
      state.referenceSource = "song"; changeReference(time); render();
    }
  });
  element.addEventListener("pointermove", (event) => {
    if (!dragging || dragging.element !== element) return;
    if (Math.abs(event.clientX - dragging.x) > 3) dragging.moved = true;
    const time = pointerTime(event, element);
    if ($("tool").value === "reference" && element.dataset.track === "original" && !state.busy) changeReference(time);
    else if ($("tool").value === "selection" && element.dataset.track === "original" && dragging.moved) {
      [state.start, state.end] = selectionBetween(dragging.anchor, time, duration(), 1 / state.project.sample_rate);
      renderSelection();
    }
  });
  element.addEventListener("pointerup", catchAsync(async (event) => {
    if (!dragging || dragging.element !== element) return;
    const active = dragging; dragging = null; element.releasePointerCapture(event.pointerId);
    if ($("tool").value === "seek" || !active.moved && $("tool").value !== "reference" || element.dataset.track !== "original") {
      await seek(pointerTime(event, element));
    }
    persist();
  }));
  element.addEventListener("pointercancel", () => { dragging = null; });
});
const resize = new ResizeObserver(() => { if (state.project) draw(); });
resize.observe($("source-wave"));
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", draw);
document.addEventListener("keydown", catchAsync(async (event) => {
  if (!state.project || /^(INPUT|SELECT|TEXTAREA|BUTTON|SUMMARY|A)$/.test(event.target.tagName)) return;
  const key = event.key.toLowerCase();
  if (event.code === "Space") { event.preventDefault(); await play(); }
  else if (key === "a" && !event.ctrlKey) await monitor("original");
  else if (key === "b" && !event.ctrlKey) await monitor("target");
  else if (key === "i") { state.start = Math.min(state.position, state.end - 1 / state.project.sample_rate); renderSelection(); persist(); }
  else if (key === "o") { state.end = Math.max(state.position, state.start + 1 / state.project.sample_rate); renderSelection(); persist(); }
  else if (key === "z" && (event.ctrlKey || event.metaKey)) { event.preventDefault(); await undo(); }
}));
const drop = $("drop-zone");
drop.ondragover = (event) => { event.preventDefault(); drop.classList.add("dragging"); };
drop.ondragleave = (event) => { if (!drop.contains(event.relatedTarget)) drop.classList.remove("dragging"); };
drop.ondrop = (event) => { event.preventDefault(); drop.classList.remove("dragging"); importSong(event.dataTransfer.files[0]); };
window.addEventListener("beforeunload", () => { player.pause(); });

async function init() {
  try {
    const health = await api("/api/health");
    $("health").textContent = health.weights === "ready" ? "模型已就绪" : "需要准备模型";
    $("health").classList.toggle("error", health.weights !== "ready");
    if (health.weights !== "ready") status(health.weights, true);
  } catch (error) { $("health").textContent = "服务连接失败"; status(error.message, true); }
  let saved;
  try { saved = JSON.parse(localStorage.getItem("singer-timeline-v2")); } catch { /* No saved project. */ }
  if (saved?.id) {
    try {
      const project = await api("/api/projects/" + saved.id);
      await installProject(project, true);
      if (Number.isFinite(saved.start) && Number.isFinite(saved.end)) [state.start, state.end] = selectionBetween(saved.start, saved.end, duration(), 1 / project.sample_rate);
      state.referenceSource = saved.referenceSource === "reference" && project.reference ? "reference" : "song";
      state.referenceStart = clamp(Number(saved.referenceStart) || 0, 0, referenceDuration() - 3);
      if (["original", "target", "residual"].includes(saved.monitor) && project.coverage.length) state.monitor = saved.monitor;
      render(); persist();
      if (project.busy) await operation(async () => watchJob(await api("/api/jobs/" + project.busy)));
    } catch { try { localStorage.removeItem("singer-timeline-v2"); } catch { /* No storage. */ } }
  }
}
init();
