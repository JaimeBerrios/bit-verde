// Comprobaciones de interacción sin dependencias ni navegador: no miden el diseño visual.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const vm = require('node:vm');

class Element {
  constructor(tag) {
    this.tagName = tag; this.children = []; this.attributes = {};
    this.className = ''; this.dataset = {}; this.disabled = false; this.hidden = false;
    this.classList = {
      add: (...values) => {this.className = [...new Set([...this.className.split(' ').filter(Boolean), ...values])].join(' ');},
      remove: (...values) => {this.className = this.className.split(' ').filter(value => !values.includes(value)).join(' ');},
      contains: value => this.className.split(' ').includes(value),
    };
  }
  set textContent(value) {this._text = value; this.children = [];}
  get textContent() {return String(this._text || '') + this.children.map(child => child.textContent).join('');}
  append(...items) {this.children.push(...items);}
  replaceChildren(...items) {this._text = ''; this.children = items;}
  setAttribute(key, value) {this.attributes[key] = value;}
  focus() {this.owner.activeElement = this;}
  querySelectorAll(selector) {
    return this.children.flatMap(child => [child, ...child.querySelectorAll('*')])
      .filter(child => selector === '*' || (selector.startsWith('#') ? child.id === selector.slice(1) : selector.startsWith('.') ? child.classList.contains(selector.slice(1)) : child.tagName === selector));
  }
  querySelector(selector) {return this.querySelectorAll(selector)[0] || null;}
}
function setup(page, initialIds, responder) {
  const body = new Element('body'); body.dataset.page = page;
  const document = {body, activeElement:null, querySelector: selector => body.querySelector(selector),
    createElement: tag => {const el = new Element(tag); el.owner = document; return el;}};
  body.owner = document;
  for (const [id, tag, parent] of initialIds) {
    const el = document.createElement(tag); el.id = id;
    (parent ? document.querySelector('#' + parent) : body).append(el);
  }
  const timers = [], requests = [], copied = [];
  const context = vm.createContext({document, console, AbortSignal,
    navigator:{clipboard:{writeText: async text => copied.push(text)}},
    setTimeout: (callback, ms) => {timers.push({callback, ms});},
    fetch: async (url, init) => {
      const data = init.body ? JSON.parse(init.body) : undefined;
      requests.push({url, data});
      return {ok:true, json:async () => responder(url, data)};
    },
  });
  vm.runInContext(readFileSync('app/static/js/app.js', 'utf8'), context);
  return {document, context, timers, requests, copied, $: selector => document.querySelector(selector)};
}
const flush = () => new Promise(resolve => setImmediate(resolve));

test('Trivia: error, reintento sin reiniciar, progreso, cupón, copia y nueva ronda', async () => {
  const ui = setup('game', [['game-content','div'],['start','button','game-content'],
    ['step','span'],['game-progress','progress'],['game-message','p']], (url, body) => {
    if (url.endsWith('/start')) return {session_id:'round',questions:Array.from({length:3},()=>({prompt:'Pregunta cotidiana',hint:'Una pista',options:['Sí','No']}))};
    if (url.endsWith('/answer')) return {correct:body.answer === 0, feedback:body.answer === 0 ? '¡Bien!' : 'Prueba otra vez'};
    if (url.endsWith('/submit')) return {passed:true,token:'#BIT-TEST',score:3};
    throw new Error('Ruta inesperada: ' + url);
  });
  await ui.$('#start').onclick();
  assert.equal(ui.$('#step').textContent, 'RETO 1 DE 3');
  let buttons = ui.$('#game-content').querySelectorAll('button');
  assert(buttons.every(button => !button.classList.contains('is-correct') && button.querySelector('.option-state').textContent === ''));
  assert.equal(buttons[0].querySelector('.option-key').textContent, 'A');
  await buttons[1].onclick();
  assert(buttons[1].classList.contains('is-wrong'));
  assert.equal(buttons[1].querySelector('.option-state').textContent, 'Intenta otra vez');
  assert.equal(buttons[1].attributes['aria-pressed'], 'true');
  assert(buttons.every(button => !button.disabled));
  assert.equal(ui.$('#step').textContent, 'RETO 1 DE 3');
  for (let i = 0; i < 3; i++) {
    buttons = ui.$('#game-content').querySelectorAll('button');
    await buttons[0].onclick();
    assert(buttons[0].classList.contains('is-correct'));
    assert.equal(buttons[0].querySelector('.option-state').textContent, 'Correcto');
    assert(buttons.every(button => button.disabled));
    assert.equal(ui.$('#game-progress').value, i + 1);
    ui.timers.find(timer => timer.ms === 450).callback();
    ui.timers.splice(ui.timers.findIndex(timer => timer.ms === 450), 1);
    await flush();
  }
  assert(ui.$('#game-content').textContent.includes('¡Circuito Optimizado!'));
  const copy = ui.$('#game-content').querySelectorAll('button').find(button => button.textContent === 'Copiar Token');
  await copy.onclick();
  assert.deepEqual(ui.copied, ['#BIT-TEST']);
  const again = ui.$('#game-content').querySelectorAll('button').find(button => button.textContent === 'Jugar de nuevo');
  await again.onclick();
  assert.equal(ui.$('#game-progress').value, 0);
  assert.equal(ui.$('#step').textContent, 'RETO 1 DE 3');
  assert.equal(ui.requests.filter(request => request.url.endsWith('/start')).length, 2);
});

test('Ticket compartido: enlace para jugar y alternativa si falla el portapapeles', async () => {
  const ui = setup('', [], () => ({}));
  const ticket = vm.runInContext("circuitTicket('#BIT-RAEE')", ui.context);
  assert.equal(ticket.querySelector('a').href, '/#game');
  vm.runInContext('navigator.clipboard = undefined', ui.context);
  await ticket.querySelector('button').onclick();
  assert(ticket.textContent.includes('No se pudo copiar'));
  assert(ticket.textContent.includes('#BIT-RAEE'));
});

test('Staff: lista privada, canje con un clic y actualización de estado', async () => {
  let redeemed = false;
  const ui = setup('staff', [['token','input'],['token-form','form'],['redeem','button'],
    ['token-result','p'],['staff-connection','p'],['staff-action','p'],['recent-tokens','ul']], (url, body) => {
    if (url === '/api/staff/tokens') return {tokens:[{token:'#BIT-TEST',source:'donation',created_at:'2026-10-28T10:00:00Z',canjeado:redeemed}]};
    if (url === '/api/staff/redeem') {assert.equal(body.token, '#BIT-TEST'); redeemed = true; return {canjeado:true};}
    throw new Error('Ruta inesperada: ' + url);
  });
  await flush();
  assert(ui.$('#recent-tokens').textContent.includes('Entrega RAEE'));
  const button = ui.$('#recent-tokens').querySelector('button');
  assert.equal(button.textContent, 'Marcar Canjeado');
  await button.onclick();
  assert.equal(redeemed, true);
  assert(ui.$('#recent-tokens').textContent.includes('CANJEADO ✓'));
  assert.equal(ui.$('#recent-tokens').querySelector('button'), null);
  assert(ui.timers.some(timer => timer.ms === 3000));
});
