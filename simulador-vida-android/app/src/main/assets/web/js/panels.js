// Painéis de detalhe: folhas empilhadas, menu em grade e renderizador genérico dos blocos enviados por sim/panels.py.
import { $, A, SVG_SETA_ESQ, api, barra, campo, dialogo, h, iconeSvg, img, memoria, qs, seg, temaAtual, toast } from './ui.js';

const pilha = [];      // folhas abertas: { el, nome, q }
let ctx = {};          // callbacks do app: jogar(id), salvar(), titulo(), texto(delta), atualizar(), abrirModal(m), registrarTela(t), alternarTema()
export const iniciarPaineis = (c) => { ctx = c; };

const camadas = () => document.getElementById('camadas');
const MENU = [
  ['escola', 'Escola'], ['bens', 'Bens'], ['relacoes', 'Relações'], ['trabalho', 'Trabalho'], ['saude', 'Saúde'],
  ['cognicao', 'Mente'], ['social', 'Social'], ['familia', 'Família'], ['biografia', 'Biografia'], ['arvore', 'Árvore'],
  ['empresas', 'Empresas'], ['panorama', 'Panorama'], ['impostos', 'Impostos'], ['seguro', 'Proteção'], ['noticias', 'Notícias'],
  ['salvar', 'Salvar'], ['carregar', 'Carregar'], ['config', 'Ajustes'],
];

export const haPainelAberto = () => pilha.length > 0;

export function fecharTopo() {
  const f = pilha.pop();
  if (f) { salvarFolha(f); f.largar?.(); f.el.remove(); }
}

const chaveFolha = (nome, q) => (q && q.id != null ? null : `painel.${nome}`);
function salvarFolha(f) {
  if (!f.k) return;
  memoria.gravar(`${f.k}.y`, f.corpo.scrollTop);
  if (f.carregada) memoria.gravar(`${f.k}.q`, f.q);
}
export function fecharTodas() { while (pilha.length) fecharTopo(); }

function criarFolha(nome, q) {
  const corpo = h('div', { class: 'corpo' });
  const topo = h('div', { class: 'titulo-faixa' }, '…');
  const el = h('section', { class: 'sheet', 'aria-label': nome },
    topo, corpo, h('div', { class: 'rodape' }, h('button', { class: 'btn p', type: 'button', onclick: fecharTopo }, 'Voltar')));
  camadas().append(el);
  const f = { el, nome, q, corpo, topo, k: chaveFolha(nome, q), carregada: false };
  f.largar = memoria.registrar(() => salvarFolha(f));
  pilha.push(f);
  return f;
}

function titulo(f, icone, texto) {
  f.topo.classList.toggle('longo', String(texto).length > 14);
  const btnVoltar = h('button', {
    class: 'voltar-seta', type: 'button', 'aria-label': 'Voltar', title: 'Voltar (Esc)', onclick: fecharTopo,
  }, iconeSvg(SVG_SETA_ESQ, 20));
  const centro = h('span', { class: 'faixa-centro' }, icone && img(A(icone), ''), h('span', null, texto));
  f.topo.replaceChildren(btnVoltar, centro, h('span', { class: 'dlg-esp' }));
}

export async function abrirPainel(nome, q = {}, { substituir = false, lembrado = false } = {}) {
  const topo = pilha.at(-1);
  const reaproveita = substituir && topo && topo.nome === nome;
  let restaurou = false;
  if (!reaproveita && !lembrado && !Object.keys(q).length) {
    const k = chaveFolha(nome, q);
    const salvo = k && memoria.ler(`${k}.q`, null);
    if (salvo && typeof salvo === 'object' && Object.keys(salvo).length) { q = salvo; restaurou = true; }
  }
  const f = reaproveita ? topo : criarFolha(nome, q);
  f.q = q;
  const rolagem = f.corpo.scrollTop;
  try {
    const d = await api(`painel/${nome}${qs(q)}`);
    titulo(f, d.icone, d.titulo);
    f.corpo.replaceChildren(renderBlocos(d.blocos, f));
    f.carregada = true;
    f.corpo.scrollTop = reaproveita ? rolagem : (f.k ? Number(memoria.ler(`${f.k}.y`, 0)) || 0 : 0);
    if (f.k) memoria.gravar(`${f.k}.q`, q);
    if (nome !== 'ficha' && nome !== 'menu') {
      ctx.registrarTela?.({ tipo: 'painel', id: nome, q, rotulo: d.titulo || nome });
    }
  } catch (e) {
    if (pilha.includes(f)) { pilha.splice(pilha.indexOf(f), 1); f.largar?.(); f.el.remove(); }
    if (restaurou) {
      memoria.gravar(`${chaveFolha(nome, {})}.q`, {});
      return abrirPainel(nome, {}, { lembrado: true });
    }
    toast(e.message);
  }
}

export function abrirMenu() {
  const f = criarFolha('menu', {});
  titulo(f, 'ui/icone_app_512.svg', 'Menu');
  const grade = h('div', { class: 'grade' }, MENU.map(([id, rot]) => h('button', {
    type: 'button',
    onclick: async () => {
      if (id === 'salvar') { await ctx.salvar(); return; }
      if (id === 'carregar') { await ctx.carregar(); return; }
      abrirPainel(id);
    },
  }, img(A(`icones/icone_${id}.svg`), ''), h('span', null, rot))));
  f.corpo.append(grade);
}

// --- renderizador de blocos ---
function renderBlocos(blocos, folha) {
  const frag = document.createDocumentFragment();
  let primeiroTexto = true, d = 0;
  for (const b of blocos) {
    const fn = RENDER[b.t];
    if (!fn) continue;
    const el = fn(b, folha, { primeiroTexto, ornamento: ++d % 3 + 1 });
    if (b.t === 'texto') primeiroTexto = false;
    if (el) frag.append(el);
  }
  return frag;
}

const bloco = (tit, ...kids) => h('section', { class: 'bloco' }, tit && h('h3', null, tit), ...kids);

function linhaEvento(e, comQuem) {
  return h('div', { class: `ev ${e.tom || ''}` }, img(A(e.icone), 'mini'),
    h('div', { class: 'tx' }, h('span', { class: 'dt' }, `${e.data}${e.idade != null ? ` · ${e.idade} anos` : ''}${comQuem && e.quem ? ` · ${e.quem}` : ''}`), e.texto));
}

function linhaPessoa(p) {
  return h('button', { class: `pes${p.jogador ? ' eu' : ''}`, type: 'button', onclick: () => abrirPainel('ficha', { id: p.id }) },
    img(p.avatar, ''), h('span', null, h('div', { class: 'n' }, p.nome), h('div', { class: 's' }, p.sub)),
    p.rel && h('span', { class: 'rel' }, p.rel));
}

function rotuloAcaoConfig(a) {
  if (a.acao === 'lembrar') return `Lembrar onde eu estava: ${memoria.ligada() ? 'ligado' : 'desligado'}`;
  if (a.acao === 'tema') return `Aparência: ${temaAtual() === 'escuro' ? 'Modo escuro 🌙' : 'Modo claro ☀'} (alternar)`;
  return a.rotulo;
}

const RENDER = {
  linhas: (b) => bloco(b.titulo, b.itens.map((i) => h('div', { class: 'lin' }, h('span', { class: 'r' }, i.r),
    h('span', { class: 'v' }, i.i && img(A(i.i), ''), i.v)))),

  barras: (b) => bloco(b.titulo, b.itens.map((i) => h('div', { class: 'barra-linha' },
    h('div', { class: 'topo' }, h('span', null, i.r), h('span', null, i.x ? `${i.v} · ${i.x}` : String(i.v))), barra(i.v, i.cor)))),

  pessoas: (b) => bloco(b.titulo, b.itens.length
    ? b.itens.map(linhaPessoa)
    : h('div', { class: 'vazio' }, img(A('ui/slot_barra_icone_96.svg'), ''), b.vazio)),

  geracoes: (b) => bloco(b.titulo, b.linhas.map((l) => h('div', { class: 'ger' }, h('h4', null, l.titulo),
    h('div', { class: 'fila' }, l.itens.map((p) => h('button', { class: 'cartao', type: 'button', onclick: () => abrirPainel('ficha', { id: p.id }) },
      img(p.avatar, ''), p.primeiro, h('i', null, p.vivo ? `${p.idade} anos` : '†'))))))),

  eventos: (b) => bloco(b.titulo, b.itens.length ? b.itens.map((e) => linhaEvento(e, true))
    : h('div', { class: 'vazio' }, img(A('ui/slot_barra_icone_96.svg'), ''), b.vazio)),

  lista: (b, f) => bloco(b.titulo, b.itens.map((i) => h('div', { class: 'item-lista' }, i.i && img(A(i.i), ''),
    h('div', null, h('b', null, i.titulo), h('span', null, i.texto)))),
    b.mais && h('button', { class: 'btn p m', type: 'button', onclick: () => executar(b.mais, f) }, b.mais.rotulo)),

  texto: (b, f, o) => {
    const orn = h('div', { class: `divisor d${o.ornamento}` });
    if (!o.primeiroTexto) return h('div', null, orn, h('p', { class: 'nota' }, b.texto));
    return h('div', { class: 'bloco' }, h('p', { class: 'texto', style: 'margin:0' }, b.texto));
  },

  retrato: (b) => h('section', { class: 'bloco retrato' }, img(b.pessoa.avatar, ''),
    h('div', null, h('div', { class: 'nome' }, b.pessoa.nome), h('i', null, b.legenda), h('i', null, b.pessoa.vivo ? 'vivo(a)' : 'falecido(a)'))),

  acoes: (b, f) => h('section', { class: 'bloco' }, b.itens.map((a) => h('button', {
    class: 'btn p m', type: 'button', onclick: () => executar(a, f),
  }, rotuloAcaoConfig(a)))),

  filtros: (b) => {
    const cat = h('select', { 'aria-label': 'Categoria' }, b.categorias.map((c) => h('option', { value: c.id, selected: c.id === b.cat }, c.rotulo)));
    const de = h('input', { type: 'number', placeholder: 'ano', value: b.de ?? '', 'aria-label': 'Ano inicial' });
    const ate = h('input', { type: 'number', placeholder: 'ano', value: b.ate ?? '', 'aria-label': 'Ano final' });
    const aplicar = (todos) => abrirPainel('biografia', { cat: cat.value, de: de.value, ate: ate.value, todos: todos ? '1' : '0' }, { substituir: true });
    const escopo = seg([[false, 'Só eu'], [true, 'Todo o mundo']], b.todos, aplicar);
    for (const e of [cat, de, ate]) e.addEventListener('change', () => aplicar(escopo.valor()));
    return h('section', { class: 'bloco' }, escopo, campo('Categoria', cat), h('div', { class: 'duas' }, campo('Do ano', de), campo('Até o ano', ate)));
  },

  busca: (b) => {
    const i = h('input', { type: 'search', placeholder: 'Buscar por nome', value: b.valor, 'aria-label': 'Buscar personagem' });
    const ir = () => abrirPainel(b.painel, { busca: i.value, pag: 0 }, { substituir: true });
    i.addEventListener('keydown', (ev) => { if (ev.key === 'Enter') ir(); });
    return h('section', { class: 'bloco' }, i);
  },
};

async function executar(a, folha) {
  try {
    if (a.acao === 'jogar') { await ctx.jogar(a.id); fecharTodas(); }
    else if (a.acao === 'painel') await abrirPainel(a.nome, a.q || {}, { substituir: a.nome === folha?.nome });
    else if (a.acao === 'abrir_modal') { ctx.abrirModal?.(a.modal); }
    else if (a.acao === 'criar_personagem') formPersonagem(folha);
    else if (a.acao === 'criar_familia') formFamilia(folha);
    else if (a.acao === 'autosave') { await api('ajustes', { autosave: a.valor }); await ctx.atualizar(); await abrirPainel(folha.nome, folha.q, { substituir: true }); }
    else if (a.acao === 'qi') { await api('psicologia/qi', { mostrar: a.valor }); await ctx.atualizar(); await abrirPainel(folha.nome, folha.q, { substituir: true }); }
    else if (a.acao === 'pref_afetiva') { await api('encontros/preferencia', { pref: a.valor }); await ctx.atualizar(); await abrirPainel(folha.nome, folha.q, { substituir: true }); }
    else if (a.acao === 'salvar') { await ctx.salvar(); await abrirPainel(folha.nome, folha.q, { substituir: true }); }
    else if (a.acao === 'texto') { ctx.texto(a.delta); }
    else if (a.acao === 'tema') { ctx.alternarTema?.(); await abrirPainel(folha.nome, folha.q, { substituir: true }); }
    else if (a.acao === 'lembrar') {
      memoria.ligar(!memoria.ligada());
      toast(memoria.ligada() ? 'O jogo vai lembrar onde você estava (buscas, filtros, abas e rolagem).' : 'Memória desligada e apagada.');
      await abrirPainel(folha.nome, folha.q, { substituir: true });
    }
    else if (a.acao === 'titulo') { await ctx.titulo(); }
  } catch (e) { toast(e.message); }
}

function formPersonagem(folha) {
  const idade = h('input', { type: 'number', min: 0, max: 110, value: 0 });
  const sexo = seg([['', 'Aleatório'], ['F', 'Feminino'], ['M', 'Masculino']], '');
  const nome = h('input', { type: 'text', maxlength: 30, placeholder: 'aleatório' });
  const sobrenome = h('input', { type: 'text', maxlength: 30, placeholder: 'aleatório' });
  const erro = h('div', { class: 'erro' });
  dialogo({
    titulo: 'Criar personagem', corpo: h('div', null, campo('Idade (0 a 110)', idade, 'Fica sem pais na simulação, como na versão de texto.'),
      campo('Sexo', sexo), campo('Nome', nome), campo('Sobrenome', sobrenome), erro),
    botoes: [{ rotulo: 'Criar', fechar: false, fn: async function () {
      try {
        const r = await api('criar/personagem', { idade: +idade.value, sexo: sexo.valor(), nome: nome.value, sobrenome: sobrenome.value });
        document.querySelector('.fundo')?.remove();
        toast(`Criado: ${r.criado.nome}.`);
        await ctx.atualizar();
        await abrirPainel('personagens', {}, { substituir: folha?.nome === 'personagens' });
      } catch (e) { erro.textContent = e.message; }
    } }, { rotulo: 'Cancelar' }],
  });
}

function formFamilia(folha) {
  const sobrenome = h('input', { type: 'text', maxlength: 30, placeholder: 'aleatório' });
  const filhos = h('input', { type: 'number', min: 0, max: 10, value: 2 });
  const erro = h('div', { class: 'erro' });
  dialogo({
    titulo: 'Criar família', corpo: h('div', null, campo('Sobrenome', sobrenome), campo('Filhos (0 a 10)', filhos), erro),
    botoes: [{ rotulo: 'Criar', fechar: false, fn: async () => {
      try {
        const r = await api('criar/familia', { sobrenome: sobrenome.value, filhos: +filhos.value });
        document.querySelector('.fundo')?.remove();
        toast(`Criada a ${r.criada} (${r.membros} pessoas).`);
        await ctx.atualizar();
        await abrirPainel('personagens', {}, { substituir: folha?.nome === 'personagens' });
      } catch (e) { erro.textContent = e.message; }
    } }, { rotulo: 'Cancelar' }],
  });
}

export { $ };
