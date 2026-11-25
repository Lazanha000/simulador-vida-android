// Helpers de interface. Todo texto entra por textContent/createTextNode (nomes digitados nunca viram HTML).
export const $ = (s, r = document) => r.querySelector(s);
export const A = (p) => `arte/${p}`;   // caminho de um arquivo do kit de arte

// --- memória de "onde eu estava" (v0.19.0) ---
// Guarda buscas, filtros, abas, seleções e posição de rolagem de cada tela, por partida (escopo), em localStorage.
// Tudo em try/catch: sem armazenamento o jogo funciona igual, só não lembra. Ligada/desligada em Ajustes.
const MEM_CHAVE = 'simMemoria', MEM_LIGADA = 'simMemoriaLigada', MEM_MAX = 500;
let _mem = {}, _escopo = 'g', _on = true, _tim = null;
const _salvadores = new Set();
try { _mem = JSON.parse(localStorage.getItem(MEM_CHAVE) || '{}') || {}; } catch { _mem = {}; }
try { _on = localStorage.getItem(MEM_LIGADA) !== '0'; } catch { _on = true; }
const _grava = () => { clearTimeout(_tim); _tim = null; try { localStorage.setItem(MEM_CHAVE, JSON.stringify(_mem)); } catch { /* sem armazenamento */ } };
export const memoria = {
  ligada: () => _on,
  ligar(v) { _on = !!v; try { localStorage.setItem(MEM_LIGADA, _on ? '1' : '0'); } catch { /* ignora */ } if (!_on) { _mem = {}; _grava(); } },
  escopo(e) { _escopo = String(e || 'g'); },
  ler(k, padrao) { const c = `${_escopo}|${k}`; return _on && c in _mem ? _mem[c] : padrao; },
  gravar(k, v) {
    if (!_on) return;
    _mem[`${_escopo}|${k}`] = v;
    const ks = Object.keys(_mem);
    if (ks.length > MEM_MAX) for (const x of ks.slice(0, ks.length - MEM_MAX)) delete _mem[x];   // descarta as mais antigas
    if (!_tim) _tim = setTimeout(_grava, 300);
  },
  limparTela(prefixo) { for (const c of Object.keys(_mem)) if (c.startsWith(`${_escopo}|${prefixo}`)) delete _mem[c]; if (!_tim) _tim = setTimeout(_grava, 300); },
  // Telas abertas registram um "salvador" (grava rolagem etc.); roda ao sair do app/aba para não perder a posição.
  registrar(fn) { _salvadores.add(fn); return () => _salvadores.delete(fn); },
};
const _aoSair = () => { if (document.visibilityState === 'hidden') { for (const f of _salvadores) { try { f(); } catch { /* ignora */ } } if (_tim) _grava(); } };
document.addEventListener('visibilitychange', _aoSair);
window.addEventListener('pagehide', () => { for (const f of _salvadores) { try { f(); } catch { /* ignora */ } } if (_tim) _grava(); });

// Faz um campo (select, input, checkbox) lembrar o valor; só aplica o valor salvo se ele ainda for válido.
export function lembrar(chave, el) {
  const salvo = memoria.ler(chave);
  if (salvo !== undefined) {
    if (el.type === 'checkbox') el.checked = !!salvo;
    else if (el.tagName === 'SELECT') { if ([...el.options].some((o) => o.value === String(salvo))) el.value = String(salvo); }
    else el.value = String(salvo);
  }
  el.addEventListener(el.tagName === 'SELECT' || el.type === 'checkbox' ? 'change' : 'input',
    () => memoria.gravar(chave, el.type === 'checkbox' ? el.checked : el.value));
  return el;
}

export function h(tag, props, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') e.className = v;
    else if (k === 'style') e.style.cssText = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2).toLowerCase(), v);
    else e.setAttribute(k, v === true ? '' : v);
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid != null && kid !== false) e.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return e;
}

export const img = (src, cls, alt = '') => h('img', { src, class: cls, alt, draggable: 'false' });

export class ErroApi extends Error {
  constructor(msg, status, dados) { super(msg); this.status = status; this.dados = dados || {}; }
}

export async function api(caminho, corpo) {
  const opt = corpo === undefined ? {} : {
    method: 'POST', headers: { 'X-Sim': '1', 'Content-Type': 'application/json' }, body: JSON.stringify(corpo),
  };
  let r;
  try { r = await fetch(`/api/${caminho}`, opt); }
  catch { throw new ErroApi('Sem conexão com o jogo. O servidor foi encerrado? Reabra o programa e recarregue a página.', 0); }
  const d = await r.json().catch(() => ({ erro: 'Resposta inválida do servidor.' }));
  if (!r.ok) throw new ErroApi(d.erro || 'Erro desconhecido.', r.status, d);
  return d;
}

export const qs = (o) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(o || {})) if (v !== '' && v != null) p.set(k, v);
  const s = p.toString();
  return s ? `?${s}` : '';
};

// --- camadas (toast, diálogo, espera) ---
const camadas = () => document.getElementById('camadas');

export function toast(msg) {
  const t = h('div', { class: 'toast', role: 'status' }, msg);
  camadas().append(t);
  setTimeout(() => t.remove(), 3700);
}

export function espera(texto = 'Passando o tempo…') {
  const e = h('div', { class: 'espera', role: 'alert' }, texto);
  camadas().append(e);
  return () => e.remove();
}

// dialogo({ topo, titulo, corpo, botoes:[{rotulo, fn, p}], luto, fechavel, aoFechar, aoVoltar, rolagem }) -> { fechar, voltar, dlg, ... }
// O fn de um botão roda ANTES de o diálogo fechar (síncrono); se devolver uma promessa, ela é aguardada depois.
// Sem `botoes` (e fechável), ganha um botão "Voltar" fixo no rodapé: fecha e, se houver `aoVoltar`, abre a tela anterior.
// `rolagem` (texto ou função que devolve o texto) = chave onde a posição de rolagem é lembrada; salva ao fechar e restaura ao abrir.
export function dialogo({ topo, titulo, corpo, botoes = [], luto = false, fechavel = true, aoFechar, aoVoltar, rolagem }) {
  const fundo = h('div', { class: 'fundo', role: 'dialog', 'aria-modal': 'true' });
  let aberto = true;
  const chaveRol = () => (typeof rolagem === 'function' ? rolagem() : rolagem);
  const salvarRolagem = (k = chaveRol()) => { if (k && aberto) memoria.gravar(k, dlg.scrollTop); };
  const restaurarRolagem = (k = chaveRol()) => {
    const y = k ? Number(memoria.ler(k, 0)) || 0 : 0;
    dlg.scrollTop = y;
    requestAnimationFrame(() => { if (aberto) dlg.scrollTop = y; });
  };
  const largar = memoria.registrar(() => salvarRolagem());
  const fechar = () => {
    if (!aberto) return;
    salvarRolagem();
    aberto = false; largar(); fundo.remove(); document.removeEventListener('keydown', tecla); if (aoFechar) aoFechar();
  };
  const voltar = () => {
    if (!aberto || !fechavel) return false;
    fechar();
    if (aoVoltar) aoVoltar();
    return true;
  };
  const tecla = (ev) => { if (ev.key === 'Escape' && fechavel && camadas().lastElementChild === fundo) voltar(); };
  const comVoltar = fechavel && botoes.length === 0;
  const lista = comVoltar ? [{ rotulo: 'Voltar', p: true, voltar: true }] : botoes;
  const dlg = h('div', { class: `dlg${luto ? ' luto' : ''}` },
    topo, titulo && h('h2', null, titulo), corpo,
    h('div', { class: `acoes${comVoltar ? ' fixa' : ''}` }, lista.map((b) => h('button', {
      class: `btn${b.p ? ' p' : ''} m`, type: 'button',
      onclick: async () => {
        if (b.voltar) { voltar(); return; }
        const r = b.fn ? b.fn() : undefined;
        if (b.fechar !== false) fechar();
        await r;
      },
    }, b.rotulo))));
  fundo.__voltar = voltar;     // botão físico "voltar" do Android (ver window.__simVoltar em app.js)
  fundo.append(dlg);
  if (fechavel) fundo.addEventListener('mousedown', (ev) => { if (ev.target === fundo) fechar(); });
  document.addEventListener('keydown', tecla);
  camadas().append(fundo);
  dlg.querySelector('button')?.focus({ preventScroll: true });
  if (chaveRol()) restaurarRolagem();
  return { fechar, voltar, dlg, salvarRolagem, restaurarRolagem };
}

// Pergunta sim/não; fechar por Esc ou clique fora conta como "não".
export function confirmar(titulo, texto, rotuloSim = 'Sim', rotuloNao = 'Não') {
  return new Promise((res) => {
    let r = false;
    dialogo({ titulo, corpo: h('p', { class: 'texto' }, texto), aoFechar: () => res(r),
      botoes: [{ rotulo: rotuloSim, fn: () => { r = true; } }, { rotulo: rotuloNao }] });
  });
}

// --- componentes do kit ---
export const rotuloIdade = (n) => (n === 0 ? 'Ao nascer' : n === 1 ? '1 ano' : `${n} anos`);

export function barra(valor, cor) {
  return h('span', { class: 'track' }, h('span', { class: `fill ${cor}`, style: `--v:${Math.max(0, Math.min(100, valor))}%` }));
}

export const brl = (n) => n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });

// --- formulários ---
export function campo(rotulo, entrada, dica) {
  return h('label', { class: 'campo' }, h('span', null, rotulo), entrada, dica && h('small', { class: 'dica' }, dica));
}

// Controle segmentado: opcoes = [[valor, rótulo], ...]; el.valor() devolve o escolhido.
// Com `chave`, lembra a opção escolhida (se ela ainda existir).
export function seg(opcoes, inicial, aoMudar, chave) {
  let v = inicial;
  if (chave) {
    const salvo = memoria.ler(chave);
    const achou = salvo === undefined ? undefined : opcoes.find(([val]) => String(val) === String(salvo));
    if (achou) v = achou[0];
  }
  const el = h('div', { class: 'seg', role: 'group' });
  const desenhar = () => el.replaceChildren(...opcoes.map(([val, rot]) => h('button', {
    type: 'button', class: val === v ? 'on' : '', 'aria-pressed': String(val === v),
    onclick: () => { v = val; if (chave) memoria.gravar(chave, val); desenhar(); if (aoMudar) aoMudar(v); },
  }, rot)));
  desenhar();
  el.valor = () => v;
  return el;
}
