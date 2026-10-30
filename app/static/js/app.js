const saved = {
  get(key, session = false) { try { return JSON.parse((session ? sessionStorage : localStorage).getItem(key)); } catch { return null; } },
  set(key, value, session = false) { try { (session ? sessionStorage : localStorage).setItem(key, JSON.stringify(value)); return true; } catch { return false; } },
  remove(key, session = false) { try { (session ? sessionStorage : localStorage).removeItem(key); } catch {} },
};
const $ = (s) => document.querySelector(s);
const node = (tag, text, className) => {const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(className)n.className=className;return n;};
async function api(path, body, extraHeaders = {}) {
  const response=await fetch('/api'+path,{method:body?'POST':'GET',headers:{...(body?{'Content-Type':'application/json'}:{}),...extraHeaders},body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(15000)});
  const data=await response.json();
  if(!response.ok) {
    const error = new Error(typeof data.detail==='string'?data.detail:'Revisa los campos e inténtalo de nuevo.');
    error.status = response.status; throw error;
  }
  return data;
}
function message(selector,text,error=false){const el=$(selector);el.textContent=text;el.className=error?'error':'success';}
function circuitTicket(token, restart) {
  const ticket = node('section', undefined, 'circuit-ticket');
  ticket.setAttribute('aria-label', 'Ticket de Circuito');
  ticket.append(node('span', 'TICKET DE CIRCUITO', 'eyebrow'),
    node('h3', '¡Reto completado!'),
    node('p', 'Muestra este token al staff para recibir tu bocadillo.'),
    node('code', token, 'token reward-token'));
  const status = node('p');
  status.setAttribute('role', 'status');
  const copy = node('button', 'Copiar Token', 'button');
  copy.type = 'button';
  copy.onclick = async () => {
    try {
      await navigator.clipboard.writeText(token);
      status.textContent = 'Token copiado ✓';
    } catch {
      status.textContent = 'No se pudo copiar. Mantén presionado el token para seleccionarlo o toma una captura.';
    }
  };
  const again = node(restart ? 'button' : 'a', 'Jugar de nuevo', 'button light');
  if (restart) { again.type = 'button'; again.onclick = restart; }
  else again.href = '/#game';
  const actions = node('div', undefined, 'ticket-actions');
  actions.append(copy, again);
  ticket.append(actions, status, node('p', 'Muestra este ticket al staff. Un canje por token.', 'muted'));
  return ticket;
}
if (document.body.dataset.page === 'game') {
  let session, answers = [], index = 0, busy = false;
  const content = $('#game-content');
  function focusHeading() {
    const heading = content.querySelector('h3');
    if (heading) { heading.tabIndex = -1; heading.focus({preventScroll: true}); }
  }
  function setProgress() {
    $('#game-progress').value = index;
    $('#game-progress').textContent = `${index} de 3`;
    $('#game-progress').setAttribute('aria-valuetext', `${index} de 3 retos completados`);
    const steps = $('#game-steps');
    if (steps) steps.querySelectorAll('li').forEach((step, i) => {
      step.className = i < index ? 'step-done' : i === index ? 'step-current' : '';
    });
  }
  async function start() {
    if (busy) return;
    busy = true;
    const button = content.querySelector('button');
    if (button) button.disabled = true;
    message('#game-message', 'Preparando circuito…');
    try {
      session = await api('/trivia/start', {});
      answers = []; index = 0;
      message('#game-message', '');
      render();
      focusHeading();
    } catch (e) {
      message('#game-message', e.message, true);
      if (button) button.disabled = false;
    } finally { busy = false; }
  }
  function render() {
    content.replaceChildren(); setProgress();
    message('#game-message', 'Elige una opción. Puedes reintentar si lo necesitas.');
    $('#step').textContent = `RETO ${index + 1} DE 3`;
    content.append(node('h3', session.questions[index].prompt));
    const hint = node('p', undefined, 'question-hint');
    hint.append(node('strong', 'Pista: '), node('span', session.questions[index].hint));
    hint.id = 'question-hint';
    content.append(hint);
    const options = node('div', undefined, 'options');
    options.setAttribute('role', 'group');
    options.setAttribute('aria-label', 'Elige una respuesta');
    session.questions[index].options.forEach((text, i) => {
      const button = node('button', undefined, 'option');
      const key = node('span', String.fromCharCode(65 + i), 'option-key');
      key.setAttribute('aria-hidden', 'true');
      const label = node('span', text.replace(/^\[[A-C]\]\s*/, ''), 'option-label');
      const state = node('span', '', 'option-state');
      button.append(key, label, state);
      button.type = 'button';
      button.setAttribute('aria-pressed', 'false');
      button.setAttribute('aria-describedby', 'question-hint');
      button.onclick = () => choose(i, button, options);
      options.append(button);
    });
    content.append(options);
  }
  async function choose(answer, selected, options) {
    if (busy) return;
    busy = true;
    const buttons = [...options.querySelectorAll('button')];
    for (const button of buttons) {
      button.disabled = true;
      button.classList.remove('is-wrong', 'is-correct', 'is-selected');
      button.querySelector('.option-state').textContent = '';
      button.setAttribute('aria-pressed', String(button === selected));
    }
    // Highlight the tap immediately; correctness still comes from the server.
    selected.classList.add('is-selected');
    selected.querySelector('.option-state').textContent = 'Comprobando…';
    content.setAttribute('aria-busy', 'true');
    message('#game-message', '');
    try {
      const result = await api(`/trivia/${session.session_id}/answer`, {question_index: index, answer});
      selected.classList.add(result.correct ? 'is-correct' : 'is-wrong');
      selected.querySelector('.option-state').textContent = result.correct ? 'Correcto' : 'Intenta otra vez';
      message('#game-message', result.feedback, !result.correct);
      if (!result.correct) {
        for (const button of buttons) button.disabled = false;
        busy = false;
        return;
      }
      answers[index] = answer;
      index++; setProgress();
      // Keep the successful state visible briefly, then move on without an extra tap.
      setTimeout(() => {
        busy = false;
        if (index < 3) { render(); focusHeading(); }
        else finish();
      }, 450);
    } catch (e) {
      message('#game-message', e.message + ' Puedes volver a tocar la respuesta.', true);
      for (const button of buttons) button.disabled = false;
      selected.classList.remove('is-selected');
      selected.setAttribute('aria-pressed', 'false');
      selected.querySelector('.option-state').textContent = '';
      busy = false;
    } finally { content.setAttribute('aria-busy', 'false'); }
  }
  async function finish() {
    if (busy) return;
    busy = true;
    content.replaceChildren(node('p', 'Preparando tu Ticket de Circuito…'));
    try {
      const result = await api(`/trivia/${session.session_id}/submit`, {answers});
      if (!result.passed) throw new Error('Revisa las respuestas antes de completar el circuito.');
      $('#step').textContent = '3 DE 3 · ¡LO LOGRASTE!';
      message('#game-message', '');
      const stored = saved.set('bitverde-ticket', result.token);
      content.replaceChildren(circuitTicket(result.token, start));
      if (!stored) message('#game-message', 'Guarda una captura del ticket: este navegador no permite conservarlo.');
      focusHeading();
    } catch (e) {
      message('#game-message', e.message, true);
      const retry = node('button', 'Recuperar mi ticket', 'button');
      retry.onclick = finish;
      content.replaceChildren(node('p', 'Tus respuestas siguen aquí. Reintentar recupera el mismo token.'), retry);
    } finally { busy = false; }
  }
  $('#start').onclick = start;
  const recovered = saved.get('bitverde-ticket');
  if (typeof recovered === 'string' && /^#BIT-[A-F0-9]{16}$/.test(recovered)) {
    $('#step').textContent = 'TU ÚLTIMO TICKET';
    content.replaceChildren(circuitTicket(recovered, start));
    message('#game-message', 'Ticket recuperado en este navegador. El staff comprobará si ya fue canjeado.');
  }
}
if(document.body.dataset.page==='registration'){
 const pendingKey = 'bitverde-pending-donation';
 let pendingDonation = saved.get(pendingKey, true);
 const form = $('#donation-form');
 function lockPending() {
   if (!pendingDonation) return;
   for (const [key, value] of Object.entries(pendingDonation.body)) {
     const field = form.elements.namedItem(key); field.value = value;
     if (field.tagName.toLowerCase() === 'select') field.disabled = true;
     else field.readOnly = true;
   }
 }
 if (pendingDonation && pendingDonation.body) {
   lockPending();
   message('#form-message', 'Hay una entrega pendiente. Reintenta para recuperar el mismo comprobante.');
 }

 $('#donation-form').onsubmit=async event=>{event.preventDefault();const button=event.target.querySelector('button');button.disabled=true;message('#form-message','Registrando entrega…');const body=Object.fromEntries(new FormData(event.target));body.quantity=Number(body.quantity);try{
 if (!pendingDonation) {
   const key = globalThis.crypto?.randomUUID?.() || (globalThis.crypto?.getRandomValues
     ? Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, '0')).join('') : null);
   if (!key) throw new Error('Este navegador no permite preparar la entrega. Prueba con un navegador actualizado.');
   pendingDonation = {key, body};
   if (!saved.set(pendingKey, pendingDonation, true)) { pendingDonation = null; throw new Error('Habilita el almacenamiento del navegador para registrar la entrega con recuperación segura.'); }
 }
 lockPending();
 const data=await api('/donations',pendingDonation.body, {'Idempotency-Key':pendingDonation.key});
 saved.set('bitverde-ticket', data.token);
 saved.remove(pendingKey, true); pendingDonation = null;
event.target.hidden=true;message('#form-message','¡Entrega registrada! Guarda tu comprobante.');const receipt=$('#receipt');receipt.hidden=false;receipt.replaceChildren(circuitTicket(data.token),node('h3','Comprobante de entrega'),node('code',data.ticket,'receipt-id'));for(const text of [`Participante: ${data.alias}`,`Categoría: ${data.category}`,`${data.quantity} piezas · ${data.weight_kg} kg estimados`,`Fecha: ${new Date(data.created_at).toLocaleString('es-SV')}`])receipt.append(node('p',text));const details=node('details');details.append(node('summary','Ver payload UTF-8 en bytes (representación educativa)'),node('pre','HEX: '+data.payload_hex+'\n\nBIN: '+data.payload_binary));const print=node('button','Guardar / imprimir comprobante','button');print.onclick=()=>window.print();const another=node('a','Registrar otra entrega →','text-link');another.href='/registro';receipt.append(details,print,another);}catch(e){
 if (e.status === 422 || e.status === 403) {
   saved.remove(pendingKey, true); pendingDonation = null;
   for (const field of form.querySelectorAll('input, select')) {field.disabled = false; field.readOnly = false;}
 }
 message('#form-message',e.message+(pendingDonation?' Reintenta para recuperar la entrega original sin duplicarla.':''),true);
}finally{button.disabled=false;}};
}
if(document.body.dataset.page==='dashboard'){
 let flowPage = 0;
 const flowSize = () => matchMedia('(min-width:901px) and (max-height:650px)').matches ? 1 : 2;
 async function refresh() {
   try {
     const data = await api('/metrics');
     $('#items').textContent = data.items;
     $('#registrations').textContent = data.registrations;
     $('#weight-total').textContent = data.weight_kg.toLocaleString('es-SV', {maximumFractionDigits:3});
     $('#repaired').textContent = data.repaired;
     const pageSize = flowSize();
     const start = (flowPage++ % Math.max(1, Math.ceil(data.recent.length / pageSize))) * pageSize;
     $('#data-flow').replaceChildren(...data.recent.slice(start, start + pageSize).map(row => {
       const el = node('div', undefined, 'flow-row');
       el.append(node('strong', row.hex), node('code', row.binary));
       return el;
     }));
     if (!data.recent.length) $('#data-flow').append(node('p', 'La primera entrega inicia el flujo.'));
     message('#connection', '● En vivo · actualizado ' + new Date().toLocaleTimeString('es-SV'));
   } catch {
     message('#connection', 'Sin conexión · se conservan los últimos datos. Reintentando…', true);
   } finally { setTimeout(refresh, 5000); }
 }
 const ecoTechFrame = $('#eco-tech-frame');
 const ecoTechStatsUrl = ecoTechFrame.src;
 function refreshEcoTech() {
   // Navegar a la URL oficial vuelve a consultar los resultados sin leer su DOM.
   ecoTechFrame.src = ecoTechStatsUrl;
   setTimeout(refreshEcoTech, 30000);
 }
 setTimeout(refreshEcoTech, 30000);
 refresh();$('#fullscreen').onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}catch{message('#connection','El navegador no permite activar pantalla completa.',true);}};
}
if (document.body.dataset.page === 'staff') {
  let verifiedToken = null, redeeming = false, refreshing = false;
  const pending = new Set();
  $('#token').oninput = () => {
    verifiedToken = null; $('#redeem').hidden = true; $('#token-result').textContent = '';
  };
  $('#token-form').onsubmit = async event => {
    event.preventDefault(); verifiedToken = null; $('#redeem').hidden = true;
    const entered = $('#token').value;
    try {
      const data = await api('/staff/token?token=' + encodeURIComponent(entered));
      if ($('#token').value !== entered) return;
      message('#token-result', data.canjeado ? 'Este token ya fue canjeado.' : 'Token válido. Confirma el canje al entregar la recompensa.', data.canjeado);
      if (!data.canjeado) { verifiedToken = data.token; $('#redeem').hidden = false; }
    } catch (e) { message('#token-result', e.message, true); }
  };
  async function markRedeemed(token, button, status) {
    if (pending.has(token)) return;
    pending.add(token); button.disabled = true;
    try {
      await api('/staff/redeem', {token});
      message(status, token + ' · CANJEADO ✓ Entrega el bocadillo.');
      if (verifiedToken === token) { verifiedToken = null; $('#redeem').hidden = true; }
      await refreshTokens();
    } catch (e) {
      message(status, token + ' · ' + e.message, true);
      await refreshTokens();
    } finally { pending.delete(token); button.disabled = false; }
  }
  $('#redeem').onclick = async () => {
    if (!verifiedToken || redeeming) return;
    redeeming = true;
    try { await markRedeemed(verifiedToken, $('#redeem'), '#token-result'); }
    finally { redeeming = false; }
  };
  async function refreshTokens() {
    if (refreshing) return;
    refreshing = true;
    try {
      const data = await api('/staff/tokens');
      const active = document.activeElement;
      const focusedToken = active && active.dataset.redeemToken;
      const rows = data.tokens.map(row => {
        const item = node('li', undefined, 'staff-token-row');
        const info = node('div');
        info.append(node('code', row.token, 'staff-token-code'),
          node('small', (row.source === 'donation' ? 'Entrega RAEE' : 'Trivia') + ' · ' + new Date(row.created_at).toLocaleTimeString('es-SV')));
        item.append(info);
        if (row.canjeado) item.append(node('span', 'CANJEADO ✓', 'redeemed-badge'));
        else {
          const button = node('button', 'Marcar Canjeado', 'button');
          button.dataset.redeemToken = row.token;
          button.setAttribute('aria-label', 'Marcar Canjeado ' + row.token);
          button.disabled = pending.has(row.token);
          button.onclick = () => markRedeemed(row.token, button, '#staff-action');
          item.append(button);
        }
        return item;
      });
      $('#recent-tokens').replaceChildren(...rows);
      if (!rows.length) $('#recent-tokens').append(node('li', 'Los nuevos tokens aparecerán aquí.'));
      if (focusedToken) {
        const replacement = [...$('#recent-tokens').querySelectorAll('button')].find(button => button.dataset.redeemToken === focusedToken);
        if (replacement) replacement.focus({preventScroll: true});
      }
      message('#staff-connection', '● En vivo · actualizado ' + new Date().toLocaleTimeString('es-SV'));
    } catch (e) { message('#staff-connection', 'Sin actualizar: ' + e.message + '. Reintentando…', true); }
    finally { refreshing = false; }
  }
  async function poll() { await refreshTokens(); setTimeout(poll, 3000); }
  poll();
}
