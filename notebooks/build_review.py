"""Render the extraction review console from review_data.json."""

import json, pathlib

data = json.load(open("notebooks/review_data.json"))

HTML = """<title>Assay Review Console</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Newsreader:opsz,wght@6..72,400;6..72,600&display=swap">
<style>
:root{
  --ground:#EFF1EE; --surface:#FCFCFB; --sunken:#E4E8E2;
  --ink:#141A17; --muted:#5C6862; --faint:#8B958F; --line:#DCE0DA;
  --signal:#1F5F5B; --signal-soft:#1F5F5B1A;
  --pass:#12794E; --hold:#CE7B00; --risk:#A32B52;
  --pass-soft:#12794E22; --hold-soft:#CE7B0022; --risk-soft:#A32B5222;
  --shadow:0 1px 2px #141A170F, 0 8px 24px #141A170A;
}
@media (prefers-color-scheme:dark){ :root:not([data-theme="light"]){
  --ground:#131714; --surface:#1A1F1B; --sunken:#0E120F;
  --ink:#E6EBE6; --muted:#8E9A92; --faint:#6B7671; --line:#29302B;
  --signal:#58A39C; --signal-soft:#58A39C22;
  --pass:#2F9968; --hold:#C68520; --risk:#C74E72;
  --pass-soft:#2F996826; --hold-soft:#C6852026; --risk-soft:#C74E7226;
  --shadow:0 1px 2px #00000040, 0 8px 24px #00000030;
}}
:root[data-theme="dark"]{
  --ground:#131714; --surface:#1A1F1B; --sunken:#0E120F;
  --ink:#E6EBE6; --muted:#8E9A92; --faint:#6B7671; --line:#29302B;
  --signal:#58A39C; --signal-soft:#58A39C22;
  --pass:#2F9968; --hold:#C68520; --risk:#C74E72;
  --pass-soft:#2F996826; --hold-soft:#C6852026; --risk-soft:#C74E7226;
  --shadow:0 1px 2px #00000040, 0 8px 24px #00000030;
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);
  font-family:Archivo,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  font-size:14px;line-height:1.5;-webkit-font-smoothing:antialiased}
.wrap{max-width:1560px;margin:0 auto;padding:28px 24px 56px;display:flex;flex-direction:column;gap:20px}

header{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:16px}
h1{font-family:Newsreader,Georgia,serif;font-weight:600;font-size:30px;line-height:1.15;
  margin:0;letter-spacing:-.015em;text-wrap:balance}
.sub{color:var(--muted);margin:6px 0 0;max-width:62ch}
.meta{display:flex;gap:22px;flex-wrap:wrap;font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:11.5px;color:var(--muted)}
.meta b{display:block;color:var(--ink);font-weight:500;font-size:13px;font-variant-numeric:tabular-nums}

.rail{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:1px;
  background:var(--line);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.tile{background:var(--surface);padding:14px 16px}
.tile .k{font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--faint);font-weight:600}
.tile .v{font-family:"IBM Plex Mono",monospace;font-size:26px;font-weight:500;
  font-variant-numeric:tabular-nums;margin-top:4px;line-height:1.1}
.tile .n{font-size:11.5px;color:var(--muted);margin-top:2px}
.v.pass{color:var(--pass)} .v.hold{color:var(--hold)}

.ctl{display:flex;align-items:center;gap:14px;background:var(--surface);border:1px solid var(--line);
  border-radius:10px;padding:12px 16px;flex-wrap:wrap}
.ctl label{font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--faint);font-weight:600}
input[type=range]{flex:1;min-width:200px;accent-color:var(--signal);height:22px}
.thr{font-family:"IBM Plex Mono",monospace;font-size:16px;font-weight:600;font-variant-numeric:tabular-nums;min-width:56px}
.seg{display:flex;border:1px solid var(--line);border-radius:7px;overflow:hidden}
.seg button{border:0;background:var(--surface);color:var(--muted);font:inherit;font-size:12px;font-weight:500;
  padding:5px 12px;cursor:pointer}
.seg button+button{border-left:1px solid var(--line)}
.seg button[aria-pressed=true]{background:var(--signal);color:var(--surface)}
.seg button:focus-visible,input:focus-visible{outline:2px solid var(--signal);outline-offset:2px}

.panes{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:20px;align-items:start}
@media(max-width:1080px){.panes{grid-template-columns:1fr}}
.pane{background:var(--surface);border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow);overflow:hidden}
.pane>h2{font-family:Newsreader,Georgia,serif;font-size:15px;font-weight:600;margin:0;
  padding:13px 16px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center}
.pane>h2 span{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--faint);font-weight:400}

.page{position:relative;background:var(--sunken);max-height:78vh;overflow:auto}
.page img{display:block;width:100%;height:auto}
.box{position:absolute;border:1.5px solid;border-radius:2px;cursor:pointer;transition:opacity .12s}
.box.pass{border-color:var(--pass);background:var(--pass-soft)}
.box.hold{border-color:var(--hold);background:var(--hold-soft)}
.box.risk{border-color:var(--risk);background:var(--risk-soft)}
.page.sel .box{opacity:.18}
.page.sel .box.on{opacity:1;box-shadow:0 0 0 3px var(--signal-soft)}

.rows{max-height:78vh;overflow:auto}
.row{display:grid;grid-template-columns:1fr auto;gap:4px 12px;padding:11px 16px;
  border-bottom:1px solid var(--line);cursor:pointer;background:none;border-left:3px solid transparent;
  width:100%;text-align:left;font:inherit;color:inherit}
.row:hover{background:var(--signal-soft)}
.row[aria-expanded=true]{background:var(--signal-soft);border-left-color:var(--signal)}
.row.dim{opacity:.34}
.path{font-family:"IBM Plex Mono",monospace;font-size:12px;font-weight:500}
.val{font-family:"IBM Plex Mono",monospace;font-size:12.5px;color:var(--muted);
  grid-column:1;overflow-wrap:anywhere}
.val.null{font-style:italic;color:var(--faint)}
.right{grid-row:1/3;display:flex;flex-direction:column;align-items:flex-end;gap:5px;justify-content:center}
.score{font-family:"IBM Plex Mono",monospace;font-size:14px;font-weight:600;font-variant-numeric:tabular-nums}
.score.pass{color:var(--pass)} .score.hold{color:var(--hold)} .score.risk{color:var(--risk)}
.chip{font-size:9.5px;letter-spacing:.08em;text-transform:uppercase;font-weight:700;padding:2px 7px;border-radius:99px}
.chip.pass{background:var(--pass-soft);color:var(--pass)}
.chip.hold{background:var(--hold-soft);color:var(--hold)}
.chip.risk{background:var(--risk-soft);color:var(--risk)}
.meter{grid-column:1/-1;height:3px;background:var(--sunken);border-radius:99px;overflow:hidden;margin-top:3px}
.meter i{display:block;height:100%;border-radius:99px}
.meter i.pass{background:var(--pass)} .meter i.hold{background:var(--hold)} .meter i.risk{background:var(--risk)}

.detail{padding:0 16px 16px;border-bottom:1px solid var(--line);background:var(--signal-soft)}
.detail h3{font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--faint);
  font-weight:600;margin:0 0 8px}
.why{font-size:12.5px;color:var(--muted);margin:0 0 12px;max-width:60ch}
.why b{color:var(--ink);font-weight:600}
.strip{display:flex;align-items:flex-end;gap:2px;height:62px;padding:6px 8px;background:var(--surface);
  border:1px solid var(--line);border-radius:7px;overflow-x:auto}
.tk{flex:0 0 16px;height:100%;display:flex;flex-direction:column;justify-content:flex-end;position:relative;cursor:default}
.tk i{display:block;border-radius:2px 2px 0 0;min-height:2px}
.tk.free i{background:var(--signal)}
.tk.forced i{background:repeating-linear-gradient(45deg,var(--line),var(--line) 2px,transparent 2px,transparent 4px);
  border:1px solid var(--line);border-bottom:0}
.tk:hover::after{content:attr(data-tip);position:absolute;bottom:calc(100% + 6px);left:50%;transform:translateX(-50%);
  background:var(--ink);color:var(--ground);font-family:"IBM Plex Mono",monospace;font-size:10.5px;
  padding:5px 8px;border-radius:5px;white-space:pre;z-index:5;pointer-events:none;box-shadow:var(--shadow)}
.key{display:flex;gap:16px;margin-top:9px;font-size:11px;color:var(--muted);flex-wrap:wrap}
.key i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px;vertical-align:-1px}
.key i.free{background:var(--signal)}
.key i.forced{background:repeating-linear-gradient(45deg,var(--line),var(--line) 2px,transparent 2px,transparent 4px);border:1px solid var(--line)}

footer{border-top:1px solid var(--line);padding-top:18px;color:var(--muted);font-size:12.5px;max-width:76ch}
footer b{color:var(--ink)}
code{font-family:"IBM Plex Mono",monospace;font-size:.92em;background:var(--sunken);padding:1px 5px;border-radius:4px}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
</style>

<div class="wrap">
<header>
  <div>
    <h1>Extraction review</h1>
    <p class="sub">Every field the model read, ranked by how likely it is to be wrong. Fields below the
    threshold are held for a person instead of being accepted silently.</p>
  </div>
  <div class="meta">
    <div>document<b id="m-doc"></b></div>
    <div>text source<b id="m-src"></b></div>
    <div>words<b id="m-words"></b></div>
    <div>decode<b id="m-time"></b></div>
  </div>
</header>

<div class="rail">
  <div class="tile"><div class="k">Auto-accepted</div><div class="v pass" id="t-acc"></div><div class="n" id="t-accn"></div></div>
  <div class="tile"><div class="k">Held for review</div><div class="v hold" id="t-held"></div><div class="n" id="t-heldn"></div></div>
  <div class="tile"><div class="k">Coverage</div><div class="v" id="t-cov"></div><div class="n">of fields clearing the bar</div></div>
  <div class="tile"><div class="k">Located on page</div><div class="v" id="t-loc"></div><div class="n">value matched to word boxes</div></div>
</div>

<div class="ctl">
  <label for="thr">Gate threshold</label>
  <input type="range" id="thr" min="0" max="100" step="1">
  <div class="thr" id="thrv"></div>
  <div class="seg" role="group" aria-label="Filter fields">
    <button id="f-all" aria-pressed="true">All</button>
    <button id="f-held" aria-pressed="false">Held</button>
    <button id="f-acc" aria-pressed="false">Accepted</button>
  </div>
</div>

<div class="panes">
  <section class="pane">
    <h2>Source document <span id="p-note"></span></h2>
    <div class="page" id="page"><img id="pimg" alt="Rendered invoice page"></div>
  </section>
  <section class="pane">
    <h2>Fields <span>select a row to see its tokens</span></h2>
    <div class="rows" id="rows"></div>
  </section>
</div>

<footer>
  <p>Confidence is the <b>lowest probability among the tokens the model actually chose</b>. Positions where the
  grammar allowed only one continuation are excluded — they report p&nbsp;=&nbsp;1.0 by construction and say nothing
  about the model. In the token strips those draw hollow. The aggregation is provisional: min, mean, and geometric
  mean are all implemented in <code>assay.confidence</code>, and which one is right gets settled by measuring
  calibration, not by argument.</p>
</footer>
</div>

<script type="application/json" id="payload">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById("payload").textContent);
const $ = id => document.getElementById(id);
let thr = D.threshold, filter = "all", sel = null;

const band = s => s >= thr ? "pass" : (s >= thr - 0.25 ? "hold" : "risk");
const pct = v => (v * 100).toFixed(1) + "%";

$("m-doc").textContent = D.doc_id.slice(0, 12) + "…";
$("m-src").textContent = D.source === "pdf" ? "PDF text layer" : "OCR fallback";
$("m-words").textContent = D.words;
$("m-time").textContent = D.elapsed + "s";
$("pimg").src = D.page_png;
$("p-note").textContent = D.fields.filter(f => f.bbox).length + " of " + D.fields.length + " fields located";
$("thr").value = Math.round(D.threshold * 100);

// Provenance overlays, drawn once; class and visibility update with the gate.
const page = $("page");
D.fields.forEach((f, i) => {
  if (!f.bbox) return;
  const b = document.createElement("button");
  b.className = "box";
  b.dataset.i = i;
  b.style.cssText = `left:${f.bbox[0]*100}%;top:${f.bbox[1]*100}%;` +
    `width:${(f.bbox[2]-f.bbox[0])*100}%;height:${(f.bbox[3]-f.bbox[1])*100}%`;
  b.title = f.path + " = " + f.value;
  b.onclick = () => select(i);
  page.appendChild(b);
});

function strip(f) {
  const bars = f.tokens.map(t => {
    const h = Math.max(2, Math.round(t.p * 100));
    const tip = JSON.stringify(t.t) + "\\np = " + t.p.toFixed(4) +
      (t.inf ? "\\nchosen freely" : "\\ngrammar-forced");
    return `<span class="tk ${t.inf ? "free" : "forced"}" data-tip='${tip.replace(/'/g,"&#39;")}'>` +
           `<i style="height:${h}%"></i></span>`;
  }).join("");
  const free = f.tokens.filter(t => t.inf).length;
  const why = f.tokens.length === 1
    ? `A single token decided this field: the model chose between <b>null</b> and opening a string value.`
    : `<b>${free}</b> of ${f.tokens.length} tokens were real choices; the rest were forced by the grammar and excluded from the score.`;
  return `<div class="detail"><h3>Token probabilities</h3><p class="why">${why}</p>` +
    `<div class="strip">${bars}</div>` +
    `<div class="key"><span><i class="free"></i>chosen freely — scored</span>` +
    `<span><i class="forced"></i>grammar-forced — excluded</span></div></div>`;
}

function render() {
  const acc = D.fields.filter(f => f.score >= thr).length;
  const n = D.fields.length;
  $("t-acc").textContent = acc;
  $("t-accn").textContent = "post without review";
  $("t-held").textContent = n - acc;
  $("t-heldn").textContent = "sent to a person";
  $("t-cov").textContent = pct(acc / n);
  $("t-loc").textContent = D.fields.filter(f => f.bbox).length + " / " + n;
  $("thrv").textContent = thr.toFixed(2);

  document.querySelectorAll(".box").forEach(b => {
    const f = D.fields[b.dataset.i];
    b.className = "box " + band(f.score) + (sel === +b.dataset.i ? " on" : "");
  });
  page.classList.toggle("sel", sel !== null);

  $("rows").innerHTML = D.fields.map((f, i) => {
    const bd = band(f.score);
    const shown = filter === "all" || (filter === "held") === (f.score < thr);
    if (!shown) return "";
    const val = f.value === null
      ? `<div class="val null">null — model abstained</div>`
      : `<div class="val">${f.value.replace(/[<>&]/g, c => ({"<":"&lt;",">":"&gt;","&":"&amp;"}[c]))}</div>`;
    return `<button class="row" data-i="${i}" aria-expanded="${sel === i}">
      <div class="path">${f.path}</div>${val}
      <div class="right"><span class="score ${bd}">${f.score.toFixed(3)}</span>
      <span class="chip ${bd}">${f.score >= thr ? "accepted" : "review"}</span></div>
      <div class="meter"><i class="${bd}" style="width:${f.score*100}%"></i></div>
    </button>` + (sel === i ? strip(f) : "");
  }).join("");

  document.querySelectorAll(".row").forEach(r => r.onclick = () => select(+r.dataset.i));
}

function select(i) {
  sel = sel === i ? null : i;
  render();
  if (sel !== null) {
    const b = document.querySelector(`.box.on`);
    if (b) b.scrollIntoView({block: "center", behavior: "smooth"});
  }
}

$("thr").oninput = e => { thr = +e.target.value / 100; render(); };
[["f-all","all"],["f-held","held"],["f-acc","acc"]].forEach(([id, v]) => {
  $(id).onclick = () => {
    filter = v;
    ["f-all","f-held","f-acc"].forEach(o => $(o).setAttribute("aria-pressed", o === id));
    render();
  };
});
render();
</script>
"""

out = pathlib.Path("notebooks/review.html")
out.write_text(HTML.replace("__DATA__", json.dumps(data)))
print(f"wrote {out}  {out.stat().st_size / 1024 / 1024:.2f} MB")
