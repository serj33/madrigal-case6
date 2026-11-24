const $ = id => document.getElementById(id);
const text = $("text");
let busy = false;

function setStatus(message) { $("status").textContent = message; }
function clearResult() {
  $("player").pause();
  $("player").removeAttribute("src");
  $("result").hidden = true;
}
text.oninput = () => {
  $("counter").textContent = `${text.value.length} / 2000`;
  clearResult();
};

async function synthesize(mode) {
  if (busy) return;
  if (!text.value.trim()) return setStatus("Введите текст.");
  busy = true;
  $("base").disabled = true;
  $("auto").disabled = true;
  setStatus(mode === "base" ? "Синтез исходного текста…" : "AUTO анализирует и подготавливает текст…");
  try {
    const response = await fetch("/api/synthesize", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({text: text.value, mode})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Не удалось выполнить синтез.");
    $("result").hidden = false;
    $("player").src = data.audio_url;
    $("download").href = data.audio_url;
    $("metrics").textContent = `${data.mode.toUpperCase()}: ${data.duration_seconds.toFixed(2)} с; генерация ${data.generation_seconds.toFixed(2)} с`;
    $("text-used").textContent = data.text_used;
    const decisions = $("auto-decisions");
    decisions.replaceChildren();
    (data.auto_decisions || []).forEach(item => {
      const p = document.createElement("p");
      p.textContent = `${item.word} → ${item.option_id}; уверенность: ${item.confidence}`;
      decisions.append(p);
    });
    $("warnings").textContent = (data.warnings || []).join(" ");
    setStatus("Готово.");
  } catch (error) {
    setStatus(error.message || "Ошибка синтеза.");
  } finally {
    busy = false;
    $("base").disabled = false;
    $("auto").disabled = false;
  }
}
$("base").onclick = () => synthesize("base");
$("auto").onclick = () => synthesize("auto");
