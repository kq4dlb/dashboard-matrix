"use strict";
let slug=document.body.dataset.dashboardSlug||"main", dashboard=null, dashboards=[], pageTimer=null, layoutMode=false, dragged=null, serverDefaultTheme="matrix-dark";
const grid=document.getElementById("dashboard-grid"),title=document.getElementById("dashboard-title"),connectionState=document.getElementById("connection-state"),selector=document.getElementById("dashboard-selector"),timers=new Map(),stationCallsign=document.getElementById("station-callsign"),stationGrid=document.getElementById("station-grid"),titleClockTime=document.getElementById("title-clock-time"),titleClockDate=document.getElementById("title-clock-date");
const dashboardNav=document.getElementById("dashboard-nav"),themeSelector=document.getElementById("theme-selector");
function updateTitleClock(){const n=new Date();titleClockTime.textContent=n.toLocaleTimeString([], {hour:"2-digit",minute:"2-digit",second:"2-digit"});titleClockDate.textContent=n.toLocaleDateString([], {weekday:"short",month:"short",day:"numeric",year:"numeric"})}
async function loadStationSettings(){const r=await fetch('/api/settings/station',{cache:'no-store'});if(!r.ok)return;const d=await r.json();stationCallsign.textContent=d.callsign;stationGrid.textContent=`${d.grid_square} · ${d.latitude}, ${d.longitude}`;serverDefaultTheme=d.default_theme||"matrix-dark";document.title=d.display_name||"Dashboard Matrix"}
function clearTimers(){for(const ids of timers.values())ids.forEach(clearInterval);timers.clear();clearTimeout(pageTimer)}
function setTileState(el,state){el.dataset.state=state;el.querySelector(".tile-state").textContent=state;el.querySelector(".tile-updated").textContent=new Date().toLocaleTimeString()}
function cacheBusted(url){return `${url}${url.includes("?")?"&":"?"}_matrix=${Date.now()}`}
function renderFrame(c,u,e,force=false){c.replaceChildren();const f=document.createElement("iframe");f.loading="eager";f.src=force?cacheBusted(u):u;f.onload=()=>setTileState(e,"ONLINE");f.onerror=()=>setTileState(e,"ERROR");c.append(f)}
function renderImage(c,u,e){c.replaceChildren();const i=document.createElement("img");i.alt=e.querySelector(".tile-title").textContent;i.src=cacheBusted(u);i.onload=()=>setTileState(e,"ONLINE");i.onerror=()=>setTileState(e,"ERROR");c.append(i)}
function renderText(c,t,e){c.innerHTML='<div class="text-tile"></div>';c.firstElementChild.textContent=t||"No text configured";setTileState(e,"ONLINE")}
function renderClock(c,e){c.innerHTML='<div class="clock-tile"><div class="clock-time"></div><div class="clock-date"></div></div>';const u=()=>{const n=new Date();c.querySelector(".clock-time").textContent=n.toLocaleTimeString([], {hour:"2-digit",minute:"2-digit",second:"2-digit"});c.querySelector(".clock-date").textContent=n.toLocaleDateString([], {weekday:"long",month:"long",day:"numeric",year:"numeric"});setTileState(e,"ONLINE")};u();return[setInterval(u,1000)]}
async function renderStatus(c,e){try{const r=await fetch("/api/system/status",{cache:"no-store"});if(!r.ok)throw Error(`HTTP ${r.status}`);const d=await r.json();c.innerHTML=`<div class="status-tile"><table class="status-table"><tr><td>Host</td><td>${d.hostname}</td></tr><tr><td>Python</td><td>${d.python}</td></tr><tr><td>Uptime</td><td>${Math.floor(d.uptime_seconds/60)} min</td></tr><tr><td>Disk used</td><td>${d.disk_percent}%</td></tr></table></div>`;setTileState(e,"ONLINE")}catch(x){c.innerHTML=`<div class="error-box">${x.message}</div>`;setTileState(e,"ERROR")}}
async function renderProvider(c,e,tile){try{const r=await fetch(`/api/providers/${tile.id}`,{cache:"no-store"});if(!r.ok)throw Error((await r.json()).detail||`HTTP ${r.status}`);const d=await r.json();if(d.provider==="nws_forecast")c.innerHTML=`<div class="forecast-grid">${d.periods.map(p=>`<article><strong>${p.name}</strong><span class="forecast-temp">${p.temperature}°${p.unit}</span><span>${p.summary}</span><small>${p.wind}</small></article>`).join("")}</div>`;else if(d.provider==="swpc_scales")c.innerHTML=`<div class="scale-grid">${["R","S","G"].map(k=>`<article><strong>${k}</strong><span>${d.scales[k]}</span><small>${k==="R"?"Radio Blackout":k==="S"?"Solar Radiation":"Geomagnetic"}</small></article>`).join("")}</div>`;else if(d.provider==="swpc_k_index")c.innerHTML=`<div class="kp-tile"><span class="kp-value">${d.kp??"—"}</span><strong>Planetary Kp</strong><small>${d.time_tag||"No timestamp"}</small><div class="kp-bars">${d.history.map(h=>`<i style="height:${Math.max(4,h.kp*10)}%" title="${h.kp}"></i>`).join("")}</div></div>`;else c.textContent=JSON.stringify(d,null,2);setTileState(e,"ONLINE")}catch(x){c.innerHTML=`<div class="error-box">${x.message}</div>`;setTileState(e,"ERROR")}}

function esc(v){return String(v??"").replace(/[&<>"']/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]))}
function conditionClass(value){const v=String(value||"").toLowerCase();if(v.includes("excellent")||v.includes("good")||v.includes("quiet"))return"good";if(v.includes("fair")||v.includes("normal")||v.includes("unsettled"))return"fair";if(v.includes("poor")||v.includes("bad")||v.includes("storm")||v.includes("active"))return"bad";return""}
function renderScriptPayload(c,d){
  if(d.format==="band_conditions"){
    const group=(name,items)=>`<section class="script-band-group"><h4>${name}</h4>${(items||[]).map(b=>`<div><span>${esc(b.name)}</span><strong class="${conditionClass(b.condition)}">${esc(b.condition)}</strong></div>`).join("")}</section>`;
    c.innerHTML=`<div class="script-tile"><div class="script-meta">Updated ${esc(d.updated||"N/A")}${d.stale?" · cached":""}</div><div class="script-band-grid">${group("Day",d.day)}${group("Night",d.night)}</div></div>`;
  } else if(d.format==="metrics"){
    c.innerHTML=`<div class="script-tile"><div class="script-meta">Updated ${esc(d.updated||"N/A")}${d.stale?" · cached":""}</div><div class="script-metrics">${(d.metrics||[]).map(m=>`<article><small>${esc(m.label)}</small><strong>${esc(m.value)}</strong></article>`).join("")}</div></div>`;
  } else if(d.format==="solar_weather"){
    c.innerHTML=`<div class="script-tile solar-script"><div class="script-metrics"><article><small>Kp now</small><strong>${esc(d.kp?.value)}</strong><span>${esc(d.kp?.time)}</span></article><article><small>Kp forecast</small><strong>${esc(d.forecast?.value)}</strong><span>${esc(d.forecast?.time)}</span></article><article><small>Wind speed</small><strong>${esc(d.solar_wind?.speed)} km/s</strong><span>${esc(d.solar_wind?.time)}</span></article><article><small>Density</small><strong>${esc(d.solar_wind?.density)} p/cm³</strong></article><article><small>Bt</small><strong>${esc(d.magnetic?.bt)} nT</strong></article><article><small>Bz GSM</small><strong>${esc(d.magnetic?.bz)} nT</strong></article></div><div class="script-alerts">${(d.alerts||[]).length?(d.alerts||[]).map(a=>`<p>⚠ ${esc(a)}</p>`).join(""):"<p>No recent NOAA alerts.</p>"}</div></div>`;
  } else if(d.format==="message"){
    c.innerHTML=`<div class="error-box">${esc(d.message||"Script message")}</div>`;
  } else if(d.format==="text"){
    renderText(c,d.text||"",c.closest('.tile'));
  } else {
    c.innerHTML=`<pre class="script-json">${esc(JSON.stringify(d.data??d,null,2))}</pre>`;
  }
}
async function renderPlugin(c,e,tile){try{const r=await fetch(`/api/plugins/data/${tile.id}`,{cache:"no-store"});if(!r.ok){let detail=`HTTP ${r.status}`;try{detail=(await r.json()).detail||detail}catch{}throw Error(detail)}const d=await r.json();renderScriptPayload(c,d);setTileState(e,"ONLINE")}catch(x){c.innerHTML=`<div class="error-box">${esc(x.message)}</div>`;setTileState(e,"ERROR")}}
async function renderScript(c,e,tile){try{const r=await fetch(`/api/scripts/${tile.id}`,{cache:"no-store"});if(!r.ok){let detail=`HTTP ${r.status}`;try{detail=(await r.json()).detail||detail}catch{}throw Error(detail)}const d=await r.json();renderScriptPayload(c,d);setTileState(e,"ONLINE")}catch(x){c.innerHTML=`<div class="error-box">${esc(x.message)}</div>`;setTileState(e,"ERROR")}}
function applyGeometry(e){
  const col=Number(e.dataset.col), row=Number(e.dataset.row), w=Number(e.dataset.w), h=Number(e.dataset.h);
  e.style.gridColumn=`${col} / span ${w}`; e.style.gridRow=`${row} / span ${h}`;
}
function rectOf(e){return {id:Number(e.dataset.tileId),col:Number(e.dataset.col),row:Number(e.dataset.row),w:Number(e.dataset.w),h:Number(e.dataset.h),locked:e.dataset.locked==='true'}}
function overlaps(a,b){return a.col<a2(b)&&a2(a)>b.col&&a.row<r2(b)&&r2(a)>b.row} function a2(a){return a.col+a.w} function r2(a){return a.row+a.h}
function allTileElements(){return [...grid.querySelectorAll('.tile')]}
function clampGeometry(g){g.w=Math.max(1,Math.min(Number(dashboard.columns),g.w));g.col=Math.max(1,Math.min(Number(dashboard.columns)-g.w+1,g.col));g.row=Math.max(1,g.row);g.h=Math.max(1,Math.min(24,g.h));return g}
function writeGeometry(e,g){clampGeometry(g);e.dataset.col=g.col;e.dataset.row=g.row;e.dataset.w=g.w;e.dataset.h=g.h;applyGeometry(e)}
function settleCollisions(active){
  const moving=rectOf(active); const others=allTileElements().filter(e=>e!==active).sort((a,b)=>Number(a.dataset.row)-Number(b.dataset.row)||Number(a.dataset.col)-Number(b.dataset.col));
  for(const e of others){let g=rectOf(e);if(overlaps(moving,g)){if(g.locked){moving.row=g.row+g.h;writeGeometry(active,moving)}else{g.row=moving.row+moving.h;writeGeometry(e,g)}}}
  compactLayout(active);
}
function compactLayout(except=null){
  const elements=allTileElements().sort((a,b)=>Number(a.dataset.row)-Number(b.dataset.row)||Number(a.dataset.col)-Number(b.dataset.col));
  for(const e of elements){if(e===except||e.dataset.locked==='true')continue;let g=rectOf(e);while(g.row>1){const candidate={...g,row:g.row-1};const blocked=elements.some(o=>o!==e&&overlaps(candidate,rectOf(o)));if(blocked)break;g.row--;writeGeometry(e,g)}}
}
function cellMetrics(){const style=getComputedStyle(grid),gap=parseFloat(style.columnGap)||10;return {cw:(grid.clientWidth-gap*(dashboard.columns-1))/dashboard.columns,rh:parseFloat(style.getPropertyValue('--row-height'))||100,gap}}
function beginInteraction(ev,e,mode){
  if(!layoutMode||e.dataset.locked==='true'||ev.button!==0)return;ev.preventDefault();ev.stopPropagation();
  const start=rectOf(e), originX=ev.clientX,originY=ev.clientY,{cw,rh,gap}=cellMetrics();e.classList.add('interacting');document.body.classList.add('layout-interacting');
  const move=me=>{const dx=Math.round((me.clientX-originX)/(cw+gap)),dy=Math.round((me.clientY-originY)/(rh+gap));const next={...start};if(mode==='drag'){next.col=start.col+dx;next.row=start.row+dy}else{next.w=start.w+dx;next.h=start.h+dy}writeGeometry(e,next)};
  const done=()=>{document.removeEventListener('pointermove',move);document.removeEventListener('pointerup',done);document.removeEventListener('pointercancel',done);e.classList.remove('interacting');document.body.classList.remove('layout-interacting');settleCollisions(e)};
  document.addEventListener('pointermove',move);document.addEventListener('pointerup',done,{once:true});document.addEventListener('pointercancel',done,{once:true});
}
function buildTile(tile){
  const e=document.getElementById("tile-template").content.firstElementChild.cloneNode(true);e.dataset.tileId=tile.id;e.dataset.col=tile.col_pos;e.dataset.row=tile.row_pos;e.dataset.w=tile.width;e.dataset.h=tile.height;e.dataset.locked=String(Boolean(tile.locked));const showTitle=tile.settings?.show_title;const hideTitle=showTitle===false||(showTitle!==true&&Number(tile.height)===1);e.classList.toggle("title-hidden",hideTitle);applyGeometry(e);
  e.querySelector(".tile-title").textContent=tile.title;const lock=e.querySelector('.tile-lock');const updateLock=()=>{const locked=e.dataset.locked==='true';lock.textContent=locked?'🔒':'🔓';lock.title=locked?'Unlock tile':'Lock tile';e.classList.toggle('locked',locked)};updateLock();
  lock.onclick=ev=>{ev.stopPropagation();if(!layoutMode)return;e.dataset.locked=String(e.dataset.locked!=='true');updateLock()};
  e.querySelector('.tile-header').addEventListener('pointerdown',ev=>{if(ev.target.closest('button'))return;beginInteraction(ev,e,'drag')});e.querySelector('.resize-handle').addEventListener('pointerdown',ev=>beginInteraction(ev,e,'resize'));
  const c=e.querySelector(".tile-content");let idx=0;const local=[];const render=(force=false)=>{const source=tile.sources[idx]||"";if(["iframe","rotation"].includes(tile.tile_type))renderFrame(c,source,e,force);else if(tile.tile_type==="image")renderImage(c,source,e);else if(tile.tile_type==="text")renderText(c,source,e);else if(tile.tile_type==="clock")local.push(...renderClock(c,e));else if(tile.tile_type==="status")renderStatus(c,e);else if(tile.tile_type==="provider")renderProvider(c,e,tile);else if(tile.tile_type==="script")renderScript(c,e,tile);else if(tile.tile_type==="plugin")renderPlugin(c,e,tile)};
  render();if(tile.rotate_seconds>0&&tile.sources.length>1)local.push(setInterval(()=>{idx=(idx+1)%tile.sources.length;render()},tile.rotate_seconds*1000));if(tile.refresh_seconds>0&&!['clock','text'].includes(tile.tile_type))local.push(setInterval(()=>render(true),tile.refresh_seconds*1000));timers.set(tile.id,local);e.ondblclick=()=>{if(!layoutMode)e.requestFullscreen?.()};return e
}
function snapshotLayout(){return allTileElements().map(rectOf)}
function restoreLayout(items){for(const item of items){const e=grid.querySelector(`[data-tile-id="${item.id}"]`);if(e){writeGeometry(e,item);e.dataset.locked=String(Boolean(item.locked));e.classList.toggle('locked',Boolean(item.locked));const b=e.querySelector('.tile-lock');b.textContent=item.locked?'🔒':'🔓'}}}
let originalLayout=[];
async function loadDashboard(){clearTimers();const r=await fetch(`/api/dashboards/${encodeURIComponent(slug)}`,{cache:"no-store"});if(!r.ok)throw Error(`Unable to load dashboard: HTTP ${r.status}`);dashboard=await r.json();title.textContent=dashboard.name;renderDashboardNav();selector.value=slug;grid.style.setProperty('--columns',dashboard.columns);grid.style.gridTemplateColumns=`repeat(${dashboard.columns},minmax(0,1fr))`;grid.replaceChildren(...dashboard.tiles.map(buildTile));originalLayout=snapshotLayout();schedulePageRotation()}
async function loadDashboardList(){const r=await fetch('/api/dashboards',{cache:'no-store'});dashboards=await r.json();selector.replaceChildren(...dashboards.map(d=>{const o=document.createElement('option');o.value=d.slug;o.textContent=d.name;return o}));if(!dashboards.some(d=>d.slug===slug)&&dashboards[0])slug=dashboards[0].slug;renderDashboardNav()}
function renderDashboardNav(){dashboardNav.replaceChildren(...dashboards.map(d=>{const b=document.createElement('button');b.type='button';b.className='nav-dashboard'+(d.slug===slug?' active':'');b.textContent=d.name;b.onclick=()=>{slug=d.slug;history.replaceState(null,'',`/?slug=${encodeURIComponent(slug)}`);setLayoutMode(false);loadDashboard().then(renderDashboardNav).catch(showFatal)};return b}))}
function applyTheme(value){
  document.body.dataset.theme=value;
  localStorage.setItem('dashboard-matrix-theme',value);
  const link=document.getElementById('theme-package');
  if(link)link.href=`/themes/${encodeURIComponent(value)}.css`;
  themeSelector.value=value;
}
async function loadThemes(){
  const response=await fetch('/api/themes',{cache:'no-store'});
  if(!response.ok)return;
  const themes=await response.json();
  const selected=localStorage.getItem('dashboard-matrix-theme')||serverDefaultTheme||'matrix-dark';
  themeSelector.replaceChildren(...themes.map(theme=>{
    const option=document.createElement('option');option.value=theme.id;option.textContent=theme.name;return option;
  }));
  applyTheme(themes.some(theme=>theme.id===selected)?selected:(themes[0]?.id||'matrix-dark'));
}
function schedulePageRotation(){clearTimeout(pageTimer);if(!dashboard||dashboard.rotate_seconds<=0||dashboards.length<2||layoutMode)return;pageTimer=setTimeout(()=>{const i=dashboards.findIndex(d=>d.slug===slug);slug=dashboards[(i+1)%dashboards.length].slug;history.replaceState(null,"",`/?slug=${encodeURIComponent(slug)}`);loadDashboard().catch(showFatal)},dashboard.rotate_seconds*1000)}
function showFatal(x){grid.innerHTML=`<div class="error-box">${esc(x.message)}</div>`}
function setLayoutMode(enabled){layoutMode=enabled;document.body.classList.toggle('layout-mode',enabled);document.querySelectorAll('.tile.title-hidden').forEach(tile=>tile.classList.toggle('layout-title-visible',enabled));document.getElementById('layout-mode').textContent=enabled?'Exit layout':'Layout mode';for(const id of ['save-layout','reset-layout','pack-layout'])document.getElementById(id).hidden=!enabled;document.getElementById('layout-notice').hidden=!enabled;schedulePageRotation()}
selector.onchange=()=>{slug=selector.value;history.replaceState(null,"",`/?slug=${encodeURIComponent(slug)}`);setLayoutMode(false);loadDashboard().catch(showFatal)};
document.getElementById("refresh-all").onclick=()=>loadDashboard().catch(showFatal);
document.getElementById("layout-mode").onclick=()=>setLayoutMode(!layoutMode);
document.getElementById('pack-layout').onclick=()=>compactLayout();
document.getElementById('reset-layout').onclick=()=>restoreLayout(originalLayout);
document.getElementById("save-layout").onclick=async()=>{const payload=snapshotLayout().map(x=>({id:x.id,row_pos:x.row,col_pos:x.col,width:x.w,height:x.h,locked:x.locked}));const r=await fetch('/api/tiles/positions/batch',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});if(r.status===401){alert('Log in to Admin before saving the layout.');location.href='/admin';return}if(!r.ok){alert(`Unable to save layout: HTTP ${r.status}`);return}originalLayout=snapshotLayout();setLayoutMode(false);connectionState.textContent='Layout saved'};
function connectWebSocket(){const p=location.protocol==='https:'?'wss':'ws',s=new WebSocket(`${p}://${location.host}/ws`);s.onopen=()=>{connectionState.textContent='Live connection';s.send('hello')};s.onmessage=e=>{const m=JSON.parse(e.data);if(m.event==='configuration_changed'&&!layoutMode){Promise.all([loadDashboardList(),loadStationSettings()]).then(loadDashboard).catch(showFatal)}};s.onclose=()=>{connectionState.textContent='Reconnecting…';setTimeout(connectWebSocket,3000)}}
themeSelector.onchange=()=>applyTheme(themeSelector.value);
(async()=>{updateTitleClock();setInterval(updateTitleClock,1000);await Promise.all([loadDashboardList(),loadStationSettings(),loadThemes()]);await loadDashboard();connectWebSocket()})().catch(showFatal);
import("/static/js/tile-title-mode.js").catch(error=>console.error("Tile title mode failed to load",error));

/* Dashboard Matrix dashboard rotation pause/resume control */
(() => {
  const STORAGE_KEY = "dashboard-matrix-rotation-paused";
  let rotationPaused = localStorage.getItem(STORAGE_KEY) === "true";

  const originalSchedulePageRotation = schedulePageRotation;
  schedulePageRotation = function schedulePageRotationWithPause() {
    if (rotationPaused) {
      clearTimeout(pageTimer);
      pageTimer = null;
      return;
    }
    originalSchedulePageRotation();
  };

  const refreshButton = document.getElementById("refresh-all");
  if (!refreshButton || document.getElementById("rotation-toggle")) {
    return;
  }

  const toggle = document.createElement("button");
  toggle.id = "rotation-toggle";
  toggle.type = "button";
  toggle.className = refreshButton.className;
  toggle.setAttribute("aria-pressed", String(rotationPaused));

  function renderState() {
    toggle.textContent = rotationPaused ? "▶" : "⏸";
    toggle.title = rotationPaused
      ? "Resume automatic dashboard rotation"
      : "Pause automatic dashboard rotation";
    toggle.setAttribute("aria-label", toggle.title);
    toggle.setAttribute("aria-pressed", String(rotationPaused));
    toggle.classList.toggle("rotation-paused", rotationPaused);
  }

  function setRotationPaused(paused) {
    rotationPaused = Boolean(paused);
    localStorage.setItem(STORAGE_KEY, String(rotationPaused));

    if (rotationPaused) {
      clearTimeout(pageTimer);
      pageTimer = null;
      connectionState.textContent = "Rotation paused";
    } else {
      connectionState.textContent = "Rotation active";
      schedulePageRotation();
    }

    renderState();
  }

  toggle.addEventListener("click", () => {
    setRotationPaused(!rotationPaused);
  });

  refreshButton.parentElement.insertBefore(toggle, refreshButton);
  renderState();

  if (rotationPaused) {
    clearTimeout(pageTimer);
    pageTimer = null;
    connectionState.textContent = "Rotation paused";
  }
})();
