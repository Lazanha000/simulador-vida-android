// Simulador de Vida Brasileiro — aplicação (telas: título, nova partida, carregar, jogo).
import { $, A, ErroApi, SVG_LUA, SVG_SETA_BAIXO, SVG_SETA_CIMA, SVG_SETA_ESQ, SVG_SOL, SVG_VOLTAR_HIST, api, aplicarTema, barra, campo, confirmar, dialogo, espera, h, iconeSvg, img, lembrar, memoria, rotuloIdade, seg, temaAtual, toast } from './ui.js';
import { abrirMenu, abrirPainel, fecharTodas, fecharTopo, haPainelAberto, iniciarPaineis } from './panels.js';

const app = $('#app'), tela = $('#tela');
const S = {
  tela: 'titulo', est: null, itens: [], mais: false, restantes: 0, maxSeq: -1,
  ocupado: false, bandeja: null, versao: '', ultimaTela: null,
};

// --- texto maior/menor & tema claro/escuro ---
function aplicarTexto(delta = 0) {
  let z = parseFloat(localStorage.getItem('simTexto') || '1');
  z = Math.min(1.4, Math.max(0.85, Math.round((z + delta * 0.1) * 10) / 10));
  localStorage.setItem('simTexto', String(z));
  document.documentElement.style.setProperty('--z', String(z));
  if (delta) toast(`Tamanho do texto: ${Math.round(z * 100)}%`);
}

function alternarTema() {
  const prox = temaAtual() === 'escuro' ? 'claro' : 'escuro';
  aplicarTema(prox);
  atualizarBotaoTema();
  toast(prox === 'escuro' ? 'Modo escuro ativado.' : 'Modo claro ativado.');
}

function atualizarBotaoTema() {
  const escuro = temaAtual() === 'escuro';
  const btn = $('#btn-tema');
  if (btn) {
    btn.replaceChildren(iconeSvg(escuro ? SVG_SOL : SVG_LUA, 16));
    btn.setAttribute('aria-label', escuro ? 'Ativar modo claro' : 'Ativar modo escuro');
    btn.title = escuro ? 'Modo claro' : 'Modo escuro';
  }
}

const mostrar = (cls, ...nos) => {
  const escuro = temaAtual() === 'escuro' ? ' escuro' : '';
  app.className = `app${cls ? ` ${cls}` : ''}${escuro}`;
  tela.replaceChildren(...nos);
  atualizarBotaoTema();
};
const tratar = (e) => { toast(e.message || String(e)); };

// --- última tela visitada (botão 1-clique "voltar pra última tela") ---
function registrarTela(t) {
  if (!t || !t.tipo || !t.id) return;
  S.ultimaTela = { tipo: t.tipo, id: t.id, q: t.q || {}, rotulo: t.rotulo || t.id };
  memoria.gravar('nav.ultima', S.ultimaTela);
  atualizarUltimaTela();
}

function atualizarUltimaTela() {
  const btn = $('#btn-ultima-tela');
  if (!btn) return;
  const u = S.ultimaTela;
  if (!u) {
    btn.hidden = true;
    return;
  }
  btn.hidden = false;
  btn.replaceChildren(iconeSvg(SVG_VOLTAR_HIST, 14), h('span', null, u.rotulo));
  btn.setAttribute('aria-label', `Voltar para última tela: ${u.rotulo}`);
  btn.title = `Voltar para: ${u.rotulo} (Alt+←)`;
}

function abrirUltimaTela() {
  const u = S.ultimaTela;
  if (!u) return;
  if (u.tipo === 'painel') abrirPainel(u.id, u.q || {});
  else abrirModalPorId(u.id);
}

function abrirModalPorId(nome) {
  if (nome === 'estudar') abrirEstudar();
  else if (nome === 'livros') abrirLivros();
  else if (nome === 'formacao') abrirFormacao();
  else if (nome === 'educacao_br') abrirEducacaoBr();
  else if (nome === 'carreiras') abrirCarreiras();
  else if (nome === 'mundo') abrirMundo();
  else if (nome === 'psicologia') abrirPsicologia();
  else if (nome === 'vinculos') abrirVinculos();
  else if (nome === 'encontros') abrirEncontros();
  else if (nome === 'amigos') abrirAmigos();
}

// ====================== título ======================
async function telaTitulo() {
  fecharTodas();
  S.tela = 'titulo'; memoria.escopo('g');
  let saves = { saves: [], ultimo: null, versao: '' };
  try { saves = await api('saves'); } catch (e) { tratar(e); }
  S.versao = saves.versao;
  const ult = saves.ultimo;
  const botoes = [];
  if (ult) botoes.push(h('button', { class: 'btn', type: 'button', onclick: () => carregar(ult.arquivo) }, 'Continuar'));
  botoes.push(h('button', { class: ult ? 'btn p' : 'btn', type: 'button', onclick: telaNova }, 'Novo jogo'));
  if (!ult && saves.saves.length) botoes.push(h('button', { class: 'btn p', type: 'button', onclick: telaCarregar }, 'Carregar jogo'));
  const outras = ult && saves.saves.length > 1 && h('button', { class: 'link', type: 'button', onclick: telaCarregar }, 'Outras partidas…');
  mostrar('titulo', h('section', { class: 'screen' },
    h('div', { class: 'tit-topo-acoes' },
      h('button', {
        class: 'voltar-seta tit-tema', type: 'button', id: 'btn-tema',
        'aria-label': 'Alternar modo escuro', onclick: alternarTema,
      })),
    h('div', { class: 'tit-hero' },
      img(A('ui/icone_app_512.svg'), 'tit-icone'),
      h('div', { class: 'tit-faixa' }, h('b', null, 'Simulador de Vida'), h('i', null, 'Edição Brasileira')),
      h('p', { class: 'tit-desc' }, 'Viva da infância à velhice com família, estudos, carreiras, finanças e decisões marcantes.')),
    h('div', { class: 'tit-panel' },
      ult && h('div', { class: 'tit-ultimo' }, `${ult.nome}${ult.jogador ? ` · ${ult.jogador}` : ''}${ult.data ? ` · ${ult.data}` : ''}`),
      h('div', { class: 'tit-botoes' }, botoes, outras),
      h('div', { class: 'tit-versao' }, `v${saves.versao}`))));
}

// ====================== nova partida ======================
function telaNova() {
  fecharTodas();
  S.tela = 'nova'; memoria.escopo('g');
  const nome = lembrar('nova.nome', h('input', { type: 'text', maxlength: 60, value: 'Minha vida' }));
  const semente = h('input', { type: 'number', placeholder: 'aleatória' });
  const erro = h('div', { class: 'erro' });
  const campos = h('div');
  const modo = seg([['nascer', 'Nascer'], ['avulso', 'Personagem'], ['familia', 'Família']], 'nascer', () => desenhar(), 'nova.modo');
  const f = {
    sobrenome: lembrar('nova.sobrenome', h('input', { type: 'text', maxlength: 30, placeholder: 'aleatório' })),
    primeiro: lembrar('nova.primeiro', h('input', { type: 'text', maxlength: 30, placeholder: 'aleatório' })),
    sexo: seg([['', 'Aleatório'], ['F', 'Feminino'], ['M', 'Masculino']], '', null, 'nova.sexo'),
    irmaos: lembrar('nova.irmaos', h('input', { type: 'number', min: 0, max: 5, value: 1 })),
    idade: lembrar('nova.idade', h('input', { type: 'number', min: 0, max: 110, value: 25 })),
    filhos: lembrar('nova.filhos', h('input', { type: 'number', min: 0, max: 10, value: 2 })),
  };
  const desenhar = () => {
    const m = modo.valor();
    campos.replaceChildren(...[
      h('p', { class: 'dica', style: 'margin:0 0 4px' }, {
        nascer: 'Você nasce agora numa família nova, com pais e irmãos mais velhos, e vive a vida inteira.',
        avulso: 'Um personagem sozinho, de qualquer idade (sem pais na simulação).',
        familia: 'Uma família pronta: mãe, pai e filhos; você joga com o filho mais velho (ou a mãe, se não houver filhos).',
      }[m]),
      m === 'avulso' && h('div', { class: 'duas' }, campo('Idade', f.idade), campo('Nome', f.primeiro)),
      m === 'nascer' && campo('Seu nome', f.primeiro),
      (m === 'nascer' || m === 'avulso') && campo('Sexo', f.sexo),
      campo('Sobrenome da família', f.sobrenome),
      m === 'nascer' && campo('Irmãos mais velhos (0 a 5)', f.irmaos),
      m === 'familia' && campo('Filhos (0 a 10)', f.filhos)].filter(Boolean));
  };
  desenhar();
  const comecar = async (sobrescrever = false) => {
    erro.textContent = '';
    const m = modo.valor();
    const corpo = { nome: nome.value, semente: semente.value, modo: m, sobrenome: f.sobrenome.value, nome_personagem: f.primeiro.value,
      sexo: f.sexo.valor(), irmaos: +f.irmaos.value, idade: +f.idade.value, filhos: +f.filhos.value, sobrescrever };
    const fim = espera('Criando a partida…');
    try { const est = await api('novo', corpo); fim(); memoria.limparTela('nova.'); await entrarNoJogo(est); }
    catch (e) {
      fim();
      if (e.dados?.existe) { if (await confirmar('Partida existente', 'Já existe um save com esse nome. Sobrescrever?', 'Sobrescrever', 'Cancelar')) comecar(true); }
      else erro.textContent = e.message;
    }
  };
  mostrar('', h('section', { class: 'screen' },
    h('div', { class: 'titulo-faixa' },
      h('button', { class: 'voltar-seta', type: 'button', 'aria-label': 'Voltar ao título', onclick: telaTitulo }, iconeSvg(SVG_SETA_ESQ, 20)),
      h('span', { class: 'faixa-centro' }, 'Nova partida'),
      h('span', { class: 'dlg-esp' })),
    h('div', { class: 'corpo' }, campo('Nome da partida', nome), campo('Como começar', modo), campos,
      campo('Semente', semente, 'Mesma semente = mesmo mundo. Deixe vazio para sortear.'), erro),
    h('div', { class: 'rodape' }, h('button', { class: 'btn', type: 'button', onclick: () => comecar() }, 'Começar'),
      h('button', { class: 'btn p', type: 'button', onclick: telaTitulo }, 'Voltar'))));
}

// ====================== carregar ======================
async function telaCarregar() {
  fecharTodas();
  S.tela = 'carregar'; memoria.escopo('g');
  let d;
  try { d = await api('saves'); } catch (e) { tratar(e); return telaTitulo(); }
  const lista = d.saves.length ? d.saves.map((s) => h('button', {
    class: 'save', type: 'button', disabled: !s.legivel, onclick: () => carregar(s.arquivo),
  }, img(A('icones/icone_carregar.svg'), ''), h('span', null, h('div', { class: 'n' }, s.nome),
    h('div', { class: 's' }, s.legivel ? [s.jogador, s.data].filter(Boolean).join(' · ') : 'save ilegível ou de versão não suportada'),
    h('div', { class: 's' }, `salvo em ${new Date(s.mtime * 1000).toLocaleString('pt-BR')}`))))
    : h('div', { class: 'vazio' }, img(A('ui/slot_barra_icone_96.svg'), ''), 'Nenhuma partida salva ainda.');
  mostrar('', h('section', { class: 'screen' },
    h('div', { class: 'titulo-faixa' },
      h('button', { class: 'voltar-seta', type: 'button', 'aria-label': 'Voltar ao título', onclick: telaTitulo }, iconeSvg(SVG_SETA_ESQ, 20)),
      h('span', { class: 'faixa-centro' }, 'Carregar jogo'),
      h('span', { class: 'dlg-esp' })),
    h('div', { class: 'corpo' }, lista),
    h('div', { class: 'rodape' }, h('button', { class: 'btn p', type: 'button', onclick: telaTitulo }, 'Voltar'))));
}

async function carregar(arquivo) {
  const fim = espera('Abrindo a partida…');
  try { const est = await api('carregar', { arquivo }); fim(); await entrarNoJogo(est); }
  catch (e) { fim(); tratar(e); }
}

// ====================== jogo ======================
const NAV = [['escola', 'Escola'], ['bens', 'Bens'], null, ['relacoes', 'Relações'], ['trabalho', 'Trabalho']];

async function entrarNoJogo(est) {
  S.est = est; S.itens = []; S.maxSeq = -1;
  fecharTodas();
  S.tela = 'jogo'; memoria.escopo(`${est.partida.nome}#${est.partida.semente}`);
  const salvaUlt = memoria.ler('nav.ultima', null);
  S.ultimaTela = (salvaUlt && salvaUlt.tipo && salvaUlt.id) ? salvaUlt : null;

  const cab = h('header', { class: 'cab' },
    h('button', { class: 'av', type: 'button', id: 'av', 'aria-label': 'Ficha do personagem', onclick: () => abrirPainel('ficha', { id: S.est.jogador.id }) }),
    h('button', { class: 'id', type: 'button', id: 'idj', onclick: () => abrirPainel('ficha', { id: S.est.jogador.id }) }, h('div', { class: 'nome' }), h('div', { class: 'sub' })),
    h('button', { class: 'placa', type: 'button', id: 'placa', 'aria-label': 'Bens e finanças', onclick: () => abrirPainel('bens') }, h('b'), h('small')));

  const data = h('div', { class: 'datebar' },
    h('span', { id: 'data' }),
    h('span', { class: 'foco-resumo', id: 'foco-resumo' }, 'Foco: Equilibrado'),
    h('div', { class: 'datebar-acoes' },
      h('button', { class: 'chip-voltar', type: 'button', id: 'btn-ultima-tela', hidden: true, onclick: abrirUltimaTela }),
      h('button', { class: 'btn-icone', type: 'button', id: 'btn-tema', onclick: alternarTema })));

  const barras = h('div', { class: 'barras', id: 'barras' });
  const acoesBarra = h('div', { class: 'acoes-barra' },
    h('button', { class: 'acao-btn destaque', type: 'button', id: 'btn-acoes', onclick: abrirAcoes }, 'Ações'),
    h('button', { class: 'acao-btn', type: 'button', id: 'btn-estudar-rap', onclick: abrirEstudar }, 'Estudar'),
    h('button', { class: 'acao-btn', type: 'button', id: 'btn-livros-rap', onclick: abrirLivros }, 'Livros'),
    h('button', { class: 'acao-btn', type: 'button', id: 'foco', onclick: abrirFoco }, 'Foco'),
    h('button', { class: 'acao-btn', type: 'button', id: 'btn-menu', 'aria-label': 'Menu geral', onclick: abrirMenu }, img(A('icones/icone_config.svg'), ''), 'Menu'));

  const nav = h('nav', { class: 'nav' }, NAV.map((n) => n
    ? h('button', { class: 'nb', type: 'button', onclick: () => abrirPainel(n[0]) }, img(A(`icones/icone_${n[0]}.svg`), ''), h('span', null, n[1]))
    : h('div', { class: 'selo-wrap' },
      h('button', { class: 'selo', type: 'button', id: 'selo', 'aria-label': 'Avançar o tempo', onclick: alternarBandeja }, 'Avançar'))));
  const dock = h('div', { class: 'bottom-dock' }, acoesBarra, nav);
  mostrar('', h('section', { class: 'screen' }, cab, data, h('main', { class: 'feed', id: 'feed' }), barras, dock));
  desenharEstado();
  await carregarDiario();
  if (est.decisao) abrirDecisao(est.decisao);
  else if (est.avanco_pendente > 0) retomarAvanco();
}

function desenharEstado() {
  const e = S.est, j = e.jogador;
  app.classList.toggle('luto', !!e.luto);
  app.classList.toggle('escuro', temaAtual() === 'escuro');
  $('#data').textContent = e.partida.data;
  atualizarBotaoTema();
  atualizarUltimaTela();
  if (!j) return;
  $('#av').replaceChildren(img(j.avatar, ''));
  const id = $('#idj');
  id.firstChild.textContent = j.nome; id.lastChild.textContent = `${j.idade} anos · ${j.sub}`;
  const placa = $('#placa');
  placa.classList.toggle('neg', e.dinheiro.negativo);
  placa.firstChild.textContent = e.dinheiro.linha; placa.lastChild.textContent = e.dinheiro.sub;
  $('#barras').replaceChildren(...e.barras.map((b) => h('button', { class: 'bar', type: 'button', onclick: () => abrirPainel(b.painel), 'aria-label': `${b.rotulo}: ${b.valor}` },
    h('span', { class: 'rot' }, b.rotulo), barra(b.valor, b.id), h('i', null, b.valor))));
  const rotFoco = e.foco ? (e.foco.opcoes.find((o) => o.id === e.foco.atual)?.rotulo ?? '') : '';
  const areaFoco = e.foco && e.foco.atual === 'estudar' && e.foco.area !== 'geral' ? ` (${e.foco.areas.find((a) => a.id === e.foco.area)?.rotulo ?? ''})` : '';
  const fr = $('#foco-resumo');
  if (fr && e.foco) fr.textContent = `Foco: ${rotFoco}${areaFoco}`;
  const bf = $('#foco');
  if (bf && e.foco) bf.textContent = rotFoco || 'Foco';
  const bl = $('#btn-livros-rap');
  if (bl) {
    const qLen = (e.livros?.fila || []).length;
    bl.textContent = qLen > 0 ? `Livros (${qLen})` : 'Livros';
  }
  const selo = $('#selo');
  if (selo) selo.disabled = S.ocupado || !e.pode_avancar;
}

// --- diário ---
async function carregarDiario(extra = 0, novosApos = S.maxSeq) {
  try {
    const d = await api(`diario?limite=${Math.max(120, S.itens.length + extra)}`);
    S.itens = d.itens; S.mais = d.mais; S.restantes = d.restantes;
  } catch (e) { tratar(e); return; }
  desenharDiario(novosApos);
}

function desenharDiario(novosApos = S.maxSeq) {
  const feed = $('#feed');
  if (!feed) return;
  const frag = document.createDocumentFragment();
  if (S.mais) frag.append(h('button', { class: 'link mais-antigos', type: 'button', onclick: maisAntigos }, `Ver anos anteriores (${S.restantes} registros)`));
  let ultima = null, k = 0;
  for (const e of S.itens) {
    if (e.idade !== ultima) {
      if (ultima !== null) frag.append(h('div', { class: `divisor d${(k++ % 3) + 1}` }));
      frag.append(h('div', { class: 'faixa-idade' }, rotuloIdade(e.idade)));
      frag.append(entrada(e, true, novosApos));
      ultima = e.idade;
    } else frag.append(entrada(e, false, novosApos));
  }
  if (S.est?.luto) frag.append(h('div', { class: 'luto-faixa' }, `In memoriam`));
  feed.replaceChildren(frag);
  S.maxSeq = S.itens.length ? Math.max(...S.itens.map((e) => e.seq)) : -1;
  feed.scrollTop = feed.scrollHeight;
}

function entrada(e, _primeira, novosApos) {
  return h('article', { class: `ev ${e.tom}${e.seq > novosApos && novosApos >= 0 ? ' novo' : ''}` },
    img(A(e.icone), 'mini'),
    h('div', { class: 'tx' }, h('span', { class: 'dt' }, e.data), e.texto));
}

async function maisAntigos() {
  const feed = $('#feed'), alt = feed.scrollHeight;
  try {
    const d = await api(`diario?limite=${S.itens.length + 120}`);
    S.itens = d.itens; S.mais = d.mais; S.restantes = d.restantes;
  } catch (e) { return tratar(e); }
  const max = S.maxSeq;
  desenharDiario(max + 1e9);
  feed.scrollTop = feed.scrollHeight - alt;
  S.maxSeq = max;
}

// Botão "voltar" do aparelho (Android)
window.__simVoltar = () => {
  const cam = document.getElementById('camadas');
  if (cam.querySelector('.espera')) return true;
  const topos = [...cam.children].filter((el) => el.classList.contains('fundo') || el.classList.contains('sheet'));
  const dlg = topos.filter((el) => el.classList.contains('fundo')).at(-1);
  if (dlg) { dlg.__voltar?.(); return true; }
  if (topos.length) { fecharTopo(); return true; }
  if (S.bandeja) { alternarBandeja(); return true; }
  if (S.tela === 'nova' || S.tela === 'carregar') { telaTitulo(); return true; }
  return false;
};

// --- avanço do tempo ---
function alternarBandeja() {
  if (S.ocupado) return;
  if (S.bandeja) { S.bandeja.remove(); S.bandeja = null; return; }
  const fechar = () => { S.bandeja?.remove(); S.bandeja = null; document.removeEventListener('mousedown', fora, true); };
  const fora = (ev) => { if (S.bandeja && !S.bandeja.contains(ev.target) && !ev.target.closest?.('#selo')) fechar(); };
  const op = [['selo_1mes', 1, '1 mês'], ['selo_6meses', 6, '6 meses'], ['selo_1ano', 12, '1 ano']];
  S.bandeja = h('div', { class: 'bandeja', role: 'menu' }, op.map(([arq, n, rot]) => h('button', {
    type: 'button', role: 'menuitem', onclick: () => { fechar(); avancar(n); },
  }, img(A(`ui/${arq}.svg`), ''), h('span', null, rot))));
  $('.screen').append(S.bandeja);
  document.addEventListener('mousedown', fora, true);
}

async function avancar(meses) {
  if (S.ocupado) return;
  S.ocupado = true; desenharEstado();
  const t = setTimeout(() => { S.fimEspera = espera(meses >= 12 ? 'Um ano se passa…' : meses >= 6 ? 'Meio ano se passa…' : 'O mês passa…'); }, 250);
  try {
    const rel = await api('avancar', { meses });
    S.est = rel.estado;
    await carregarDiario(rel.meus.length, S.maxSeq);
    desenharEstado();
    clearTimeout(t); S.fimEspera?.(); S.fimEspera = null;
    if (rel.decisao) abrirDecisao(rel.decisao, rel); else relatorio(rel);
  } catch (e) { clearTimeout(t); S.fimEspera?.(); S.fimEspera = null; tratar(e); }
  finally { S.ocupado = false; desenharEstado(); }
}

async function retomarAvanco() {
  if (S.ocupado) return;
  S.ocupado = true; desenharEstado();
  const t = setTimeout(() => { S.fimEspera = espera('Completando o período…'); }, 250);
  try {
    const rel = await api('avancar/retomar', {});
    S.est = rel.estado;
    await carregarDiario(rel.meus.length, S.maxSeq);
    desenharEstado();
    clearTimeout(t); S.fimEspera?.(); S.fimEspera = null;
    if (rel.decisao) abrirDecisao(rel.decisao, rel); else relatorio(rel);
  } catch (e) { clearTimeout(t); S.fimEspera?.(); S.fimEspera = null; tratar(e); }
  finally { S.ocupado = false; desenharEstado(); }
}

// ====================== Menu de Ações ======================
function abrirAcoes() {
  let janela = null;
  const qLen = (S.est?.livros?.fila || []).length;
  const itens = [
    ['Estudar, Revisões, Idiomas & Pesquisa', abrirEstudar],
    [`Biblioteca e Lista de Leitura${qLen ? ` (${qLen} na lista)` : ` (${S.est?.livros?.total_catalogo || 205} livros)`}`, abrirLivros],
    ['Redação, Artigos e Filmes', abrirFormacao],
    ['ENEM, faculdade (34 cursos), técnico e pós', abrirEducacaoBr],
    ['Concursos, freelas, empresa e política', abrirCarreiras],
    ['Psicologia, hábitos e metas', abrirPsicologia],
    ['Vínculos, família e rivais', abrirVinculos],
    ['Amigos', abrirAmigos],
    ['Conhecer alguém', conhecerAlguem],
    ['Encontros', abrirEncontros],
    ['Cidade, imóveis, itens e banco', abrirMundo],
    ['Empresas do mercado', () => abrirPainel('empresas')],
    ['Notícias do Brasil', () => abrirPainel('noticias')],
  ];
  janela = dialogo({ titulo: 'Ações', corpo: h('div', { class: 'decisao' }, itens.map(([rotulo, fn]) => h('button', { class: 'btn m opcao', type: 'button',
    onclick: () => { janela.fechar(); fn(); } }, rotulo))) });
}

// ====================== Estudo em lote, Idiomas & Enciclopédia ======================
function abrirEstudar() {
  const iv0 = S.est.intelecto;
  if (!iv0 || !iv0.disponivel) return;
  registrarTela({ tipo: 'modal', id: 'estudar', rotulo: 'Estudar' });
  let janela = null;
  const tabsWrap = h('div');
  const painel = h('div', { class: 'decisao' });
  let aba = memoria.ler('estudar.aba', 'sessoes');
  const trocarAba = (v) => { janela?.salvarRolagem(`estudar.y.${aba}`); aba = v; render(); janela?.restaurarRolagem(`estudar.y.${aba}`); };

  const agir = async (rota, body, msgFn) => {
    try {
      const r = await api(rota, body);
      S.est = r.estado;
      await carregarDiario(2, S.maxSeq);
      desenharEstado();
      toast(msgFn(r.resultado));
      render();
    } catch (x) { tratar(x); }
  };

  const render = () => {
    const ivAtual = S.est.intelecto || iv0;
    const tabs = seg([
      ['sessoes', `Estudo (${ivAtual.estudo_restante})`],
      ['idiomas', `Idiomas (${ivAtual.idioma_restante ?? 0})`],
      ['enciclopedia', `Enciclopédia (${ivAtual.pesquisa_restante ?? 0})`],
    ], aba, trocarAba, 'estudar.aba');
    aba = tabs.valor();
    tabsWrap.replaceChildren(tabs);

    if (aba === 'sessoes') {
      const areaSel = lembrar('estudar.area', h('select', {}, ivAtual.areas_conhecimento.map((a) => h('option', { value: a.id }, `${a.rotulo} (${a.pontos} pts · ${a.retencao}%)`))));
      const modoLoteSel = lembrar('estudar.modo_lote', h('select', {}, ivAtual.modos_estudo.filter((m) => m.pode).map((m) => h('option', { value: m.id }, m.rotulo))));
      painel.replaceChildren(
        h('p', { class: 'nota' }, `Sessões no mês: ${ivAtual.estudo_restante}/${ivAtual.estudo_max} · Bônus anuais: Escola +${ivAtual.bonus_escola} · ENEM +${ivAtual.bonus_enem} · Concurso +${ivAtual.bonus_concurso}`),
        campo('Área / Disciplina', areaSel),
        ivAtual.estudo_restante > 1 && h('div', { class: 'caixa-destaque' },
          h('div', { class: 'livro-sub', style: 'margin-bottom:4px' }, 'Atalho prático (1 clique para todas as sessões restantes):'),
          h('div', { class: 'duas-desigual' },
            modoLoteSel,
            h('button', {
              class: 'btn m', type: 'button',
              onclick: () => agir('intelecto/estudar_lote', { modo: modoLoteSel.value, area: areaSel.value },
                (res) => `${res.mensagem}${(res.ganhos || []).length ? ` (+${res.ganhos.join(', ')})` : ''}`),
            }, `Estudar ${ivAtual.estudo_restante}×`))),
        ...ivAtual.modos_estudo.map((m) => h('button', {
          class: 'btn m opcao', type: 'button', disabled: !m.pode || ivAtual.estudo_restante <= 0,
          onclick: () => agir('intelecto/estudar', { modo: m.id, area: areaSel.value }, (res) => `${res.mensagem}${(res.ganhos || []).length ? ` (+${res.ganhos.join(', ')})` : ''}`),
        }, `${m.rotulo}${m.pode ? '' : ` (≥${m.idade_min} anos)`} — ${m.desc}`)),
        h('div', { class: 'duas' },
          h('button', {
            class: 'btn m opcao', type: 'button', disabled: ivAtual.estudo_restante <= 0,
            onclick: () => agir('intelecto/revisar', { area: areaSel.value }, (res) => `Revisão de ${res.area}: retenção restaurada a 100%!`),
          }, 'Revisão espaçada'),
          h('button', {
            class: 'btn m opcao', type: 'button', disabled: ivAtual.estudo_restante <= 0 || ivAtual.idade < 12,
            onclick: () => agir('intelecto/grupo', { area: areaSel.value }, (res) => `Grupo de estudo em ${res.area} concluído!`),
          }, 'Grupo de estudo')),
        h('button', {
          class: 'btn p m', type: 'button',
          onclick: () => { janela?.fechar(); abrirEducacaoBr(); },
        }, 'Ir para ENEM & Faculdade →'),
      );
    } else if (aba === 'idiomas') {
      painel.replaceChildren(
        h('p', { class: 'nota' }, `Aulas de idioma este mês: ${ivAtual.idioma_restante ?? 0}/${ivAtual.idioma_max ?? 2}. Domínio ≥70% gera bônus salarial e metas.`),
        ...(ivAtual.idiomas || []).map((id) => h('div', { class: 'livro-card' },
          h('div', { class: 'livro-topo' },
            h('div', null, h('div', { class: 'livro-titulo' }, `${id.nome} · ${id.nivel}`), h('div', { class: 'livro-sub' }, id.uso)),
            h('span', { class: 'livro-pags' }, `${Math.round(id.progresso)}%`)),
          barra(id.progresso, 'cognicao'),
          h('button', {
            class: 'btn m opcao', type: 'button', disabled: (ivAtual.idioma_restante ?? 0) <= 0 || ivAtual.idade < 6 || id.progresso >= 100,
            onclick: () => agir('intelecto/idioma', { idioma: id.id }, (res) => `Estudou ${res.idioma}: ${Math.round(res.progresso)}% (${res.nivel}).`),
          }, id.progresso >= 100 ? 'Dominado (100%)' : 'Praticar idioma'))),
      );
    } else {
      const subs = (ivAtual.enciclopedia || []).flatMap((d) => d.subs.map((s) => ({ id: s.id, rotulo: `${d.nome} — ${s.nome} (${s.pontos} pts)` })));
      const subSel = lembrar('estudar.sub', h('select', {}, subs.map((s) => h('option', { value: s.id }, s.rotulo))));
      painel.replaceChildren(
        h('p', { class: 'nota' }, `Pesquisa & publicação neste mês: ${ivAtual.pesquisa_restante ?? 0}/${ivAtual.pesquisa_max ?? 1} (≥15 anos). 16 áreas enciclopédicas e 48 subdisciplinas.`),
        campo('Subdisciplina de pesquisa', subSel),
        h('button', {
          class: 'btn m opcao', type: 'button', disabled: (ivAtual.pesquisa_restante ?? 0) <= 0 || ivAtual.idade < 15,
          onclick: () => agir('intelecto/pesquisar', { sub: subSel.value }, (res) => `Artigo publicado em ${res.disciplina} (${res.subdisciplina})!`),
        }, 'Pesquisar e publicar estudo'),
        ...(ivAtual.enciclopedia || []).map((d) => h('div', { class: 'livro-card' },
          h('div', { class: 'livro-topo' },
            h('div', null, h('div', { class: 'livro-titulo' }, d.nome),
              h('div', { class: 'livro-sub' }, d.subs.map((s) => `${s.nome}: ${s.pontos}`).join(' · '))),
            h('span', { class: 'livro-pags' }, `${d.pontos_raiz} pts · ${Math.round(d.retencao)}%`)))),
      );
    }
  };
  render();
  janela = dialogo({ titulo: 'Estudo, Idiomas & Enciclopédia', corpo: h('div', { class: 'decisao' }, tabsWrap, painel), aoVoltar: abrirAcoes, rolagem: () => `estudar.y.${aba}` });
}

// ====================== Psicologia ======================
function abrirPsicologia() {
  if (!S.est.psicologia?.disponivel) return;
  registrarTela({ tipo: 'modal', id: 'psicologia', rotulo: 'Psicologia' });
  let janela = null;
  const wrap = h('div', { class: 'decisao' });

  const agir = async (rota, body, msgFn) => {
    try {
      const r = await api(rota, body);
      S.est = r.estado;
      await carregarDiario(1, S.maxSeq);
      desenharEstado();
      if (msgFn) toast(msgFn(r.resultado));
      render();
    } catch (e) { tratar(e); }
  };

  const render = () => {
    const ps = S.est.psicologia;
    if (!ps || !ps.disponivel) return;
    const metasDisp = ps.metas_disponiveis || [];
    const metaSel = metasDisp.length
      ? lembrar('psi.meta', h('select', {}, metasDisp.map((m) => h('option', { value: m.id }, `${m.rotulo}${m.pode ? '' : ` (≥${m.idade_min}a)`}`))))
      : null;
    wrap.replaceChildren(...[
      h('div', { class: 'livro-card' },
        h('div', { class: 'livro-titulo' }, 'Valores e receios pessoais'),
        h('div', { class: 'livro-sub' }, `Valores: ${(ps.valores || []).join(' · ')}`),
        h('div', { class: 'livro-sub' }, `Medos: ${(ps.medos || []).join(' · ')}`),
        ps.mostrar_qi && h('div', { class: 'livro-sub' }, `QI estimado (indicador derivado opcional): ${ps.qi}`)),
      h('button', {
        class: 'btn m opcao', type: 'button',
        onclick: () => agir('psicologia/qi', { mostrar: !ps.mostrar_qi }, (res) => res.mostrar_qi ? `Indicador de QI visível (${res.qi}).` : 'Indicador de QI ocultado.'),
      }, ps.mostrar_qi ? 'Ocultar indicador opcional de QI' : 'Exibir indicador opcional de QI'),
      h('div', { class: 'divisor d1' }),
      h('p', { class: 'nota' }, 'Hábitos mensais ativos (efeito contínuo ao avançar meses):'),
      ...(ps.habitos_catalogo || []).map((hb) => h('button', {
        class: 'btn m opcao', type: 'button', disabled: !hb.pode,
        onclick: () => agir('psicologia/habito', { id: hb.id }, (res) => `${res.ativo ? 'Ativou' : 'Pausou'} hábito: ${res.nome}.`),
      }, `${hb.ativo ? '✓ ' : ''}${hb.rotulo}${hb.pode ? '' : ` (≥${hb.idade_min}a)`} — ${hb.desc}`)),
      h('div', { class: 'divisor d2' }),
      h('p', { class: 'nota' }, `Objetivos de vida ativos (${(ps.metas_ativas || []).length}/3):`),
      ...(ps.metas_ativas || []).map((m) => h('div', { class: 'livro-card' },
        h('div', { class: 'livro-topo' },
          h('div', null, h('div', { class: 'livro-titulo' }, m.rotulo), h('div', { class: 'livro-sub' }, m.desc)),
          h('span', { class: 'livro-pags' }, `${m.progresso}%`)),
        barra(m.progresso, 'felicidade'),
        h('button', {
          class: 'btn m opcao', type: 'button',
          onclick: () => agir('psicologia/meta', { id: m.id, adicionar: false }, () => `Objetivo "${m.rotulo}" removido.`),
        }, 'Abandonar objetivo'))),
      metaSel && h('div', { class: 'decisao' },
        campo('Novo objetivo de vida', metaSel),
        h('button', {
          class: 'btn m opcao', type: 'button', disabled: (ps.metas_ativas || []).length >= 3,
          onclick: () => agir('psicologia/meta', { id: metaSel.value, adicionar: true }, () => 'Novo objetivo definido!'),
        }, 'Adicionar objetivo')),
      (ps.metas_concluidas || []).length > 0 && h('p', { class: 'nota' }, `Objetivos concluídos (${ps.metas_concluidas.length}): ${ps.metas_concluidas.map((x) => x.rotulo).join(', ')}.`),
    ].filter(Boolean));
  };
  render();
  janela = dialogo({ titulo: 'Psicologia, Hábitos e Metas', corpo: wrap, aoVoltar: abrirAcoes, rolagem: 'psi.y' });
}

// ====================== Vínculos ======================
function abrirVinculos() {
  registrarTela({ tipo: 'modal', id: 'vinculos', rotulo: 'Vínculos' });
  let janela = null;
  const tabsWrap = h('div');
  const lista = h('div', { class: 'decisao' });
  let aba = memoria.ler('vinculos.aba', 'todos');
  const trocarAba = (v) => { janela?.salvarRolagem(`vinculos.y.${aba}`); aba = v; render(); janela?.restaurarRolagem(`vinculos.y.${aba}`); };

  const agir = async (oid, acaoId) => {
    try {
      const r = await api('vinculos/interagir', { id: oid, acao: acaoId });
      S.est = r.estado;
      await carregarDiario(1, S.maxSeq);
      desenharEstado();
      toast(r.resultado.mensagem);
      render();
    } catch (e) { tratar(e); }
  };

  const render = () => {
    const todos = S.est.vinculos || [];
    const acoes = S.est.acoes_vinculo || [];
    const tabs = seg([
      ['todos', `Todos (${todos.length})`],
      ['familia', 'Família'],
      ['sociais', 'Amigos/Colegas'],
      ['conflitos', 'Rivais/Atritos'],
    ], aba, trocarAba, 'vinculos.aba');
    aba = tabs.valor();
    tabsWrap.replaceChildren(tabs);
    const base = todos.filter((v) => {
      if (aba === 'familia') return !v.eh_amigo && !v.eh_colega && !v.rival && v.relacao !== 'Conhecido(a)';
      if (aba === 'sociais') return v.eh_amigo || v.eh_colega;
      if (aba === 'conflitos') return v.hostilidade >= 30 || v.rival;
      return true;
    });
    lista.replaceChildren(...(base.length ? base.map((v) => h('div', { class: 'livro-card' },
      h('div', { class: 'livro-topo' },
        h('div', null,
          h('div', { class: 'livro-titulo' }, `${v.nome}, ${v.idade} anos`),
          h('div', { class: 'livro-sub' }, `${v.relacao}${v.interagiu_mes ? ' · já interagiu este mês' : ''}`)),
        (v.rival || v.inimigo) && h('span', { class: 'badge-alerta' }, v.inimigo ? 'Inimigo' : 'Rival')),
      h('div', { class: 'tags-conh' },
        h('span', { class: 'tag-conh' }, `Afinidade ${v.afinidade}`),
        h('span', { class: 'tag-conh' }, `Confiança ${v.confianca}`),
        h('span', { class: 'tag-conh' }, `Intimidade ${v.intimidade}`),
        h('span', { class: 'tag-conh' }, `Respeito ${v.respeito}`),
        v.hostilidade >= 15 && h('span', { class: 'tag-conh' }, `Hostilidade ${v.hostilidade}`)),
      v.historico.length > 0 && h('div', { class: 'livro-sub' }, `Memórias: ${v.historico.slice(0, 2).join(' · ')}`),
      h('div', { class: 'duas' }, ...acoes.map((ac) => h('button', {
        class: 'btn m opcao', type: 'button',
        disabled: v.interagiu_mes || (ac.id === 'reconciliar' && v.hostilidade < 15),
        onclick: () => agir(v.id, ac.id),
      }, ac.rotulo))),
    )) : [h('p', { class: 'nota' }, 'Nenhum vínculo nessa categoria.')]));
  };
  render();
  janela = dialogo({ titulo: 'Vínculos, Família e Rivais', corpo: h('div', { class: 'decisao' }, tabsWrap, lista), aoVoltar: abrirAcoes, rolagem: () => `vinculos.y.${aba}` });
}

// ====================== Formação (Redação, Artigos, Filmes) — atualiza no lugar ======================
function abrirFormacao() {
  if (!S.est.intelecto?.disponivel) return;
  registrarTela({ tipo: 'modal', id: 'formacao', rotulo: 'Redação e Filmes' });
  let janela = null;
  const tabsWrap = h('div');
  const painel = h('div', { class: 'decisao' });
  let aba = memoria.ler('formacao.aba', 'ensaio');
  const trocarAba = (v) => { janela?.salvarRolagem(`formacao.y.${aba}`); aba = v; render(); janela?.restaurarRolagem(`formacao.y.${aba}`); };

  const agir = async (rota, body, msgFn) => {
    try {
      const r = await api(rota, body);
      S.est = r.estado;
      await carregarDiario(1, S.maxSeq);
      desenharEstado();
      toast(msgFn(r.resultado));
      render();
    } catch (x) { tratar(x); }
  };

  const render = () => {
    const iv = S.est.intelecto;
    const tabs = seg([
      ['ensaio', `Redação (${iv.ensaio_restante})`],
      ['artigo', `Artigos (${iv.artigo_restante})`],
      ['filme', `Filmes (${iv.filme_restante})`],
      ['conh', 'Conhecimentos'],
    ], aba, trocarAba, 'formacao.aba');
    aba = tabs.valor();
    tabsWrap.replaceChildren(tabs);

    if (aba === 'ensaio') {
      const tipoSel = seg([['redacao', 'Redação (≥10a)'], ['ensaio', 'Ensaio crítico (≥14a)']], 'redacao', null, 'formacao.tipo');
      const temaSel = lembrar('formacao.tema', h('select', {}, iv.temas_ensaio.map((t) => h('option', { value: t.id }, `${t.titulo} [${t.area_nome}]`))));
      painel.replaceChildren(
        h('p', { class: 'nota' }, `Produções disponíveis este mês: ${iv.ensaio_restante} de ${iv.ensaio_max}. Melhora compreensão verbal, abstração e nota do ENEM.`),
        tipoSel,
        campo('Tema', temaSel),
        h('button', {
          class: 'btn p m', type: 'button', disabled: iv.ensaio_restante <= 0,
          onclick: () => agir('intelecto/ensaio', { tema: temaSel.value, tipo: tipoSel.valor() },
            (res) => `${res.tipo === 'redacao' ? 'Redação' : 'Ensaio'} concluído (${res.nota})!`),
        }, 'Escrever agora'),
        ...(iv.ensaios.length ? [h('div', { class: 'divisor d1' }), h('p', { class: 'nota' }, 'Últimos textos produzidos:'),
          ...iv.ensaios.slice(0, 5).map((e) => h('div', { class: 'livro-sub' }, `• [${e.mes}/${e.ano}] ${e.titulo} (${e.nota})`))] : []),
      );
    } else if (aba === 'artigo') {
      painel.replaceChildren(
        h('p', { class: 'nota' }, `Leitura rápida de artigos científicos, econômicos e culturais (${iv.artigo_restante}/${iv.artigo_max} no mês).`),
        ...iv.areas_conhecimento.map((a) => h('button', {
          class: 'btn m opcao', type: 'button', disabled: iv.artigo_restante <= 0 || iv.idade < 10,
          onclick: () => agir('intelecto/artigo', { assunto: a.id }, (res) => `Leu artigo: "${res.titulo}".`),
        }, `Ler artigo sobre ${a.rotulo} (conhecimento atual: ${a.pontos})`)),
      );
    } else if (aba === 'filme') {
      painel.replaceChildren(
        h('p', { class: 'nota' }, `Sessões neste mês: ${iv.filme_restante}/${iv.filme_max}. Desenvolve criatividade, repertório e bem-estar.`),
        ...iv.filmes.map((f) => h('button', {
          class: 'btn m opcao', type: 'button', disabled: !f.pode || iv.filme_restante <= 0,
          onclick: () => agir('intelecto/filme', { id: f.id }, (res) => `Assistiu a "${res.titulo}"!`),
        }, `${f.visto ? '✓ ' : ''}${f.titulo} (${f.genero}, ${f.info}) · ${f.area_nome}${f.pode ? '' : ` [≥${f.idade_min}a]`}`)),
      );
    } else {
      painel.replaceChildren(
        h('p', { class: 'nota' }, 'Seu repertório intelectual acumulado por livros, estudos, redações, artigos e filmes:'),
        ...iv.areas_conhecimento.map((a) => h('div', { class: 'barra-linha' },
          h('div', { class: 'topo' }, h('span', null, a.rotulo), h('span', null, `${a.pontos} pts`)),
          barra(Math.min(100, a.pontos * 4), 'cognicao'))),
      );
    }
  };
  render();
  janela = dialogo({ titulo: 'Redação, Artigos e Filmes', corpo: h('div', { class: 'decisao' }, tabsWrap, painel), aoVoltar: abrirAcoes, rolagem: () => `formacao.y.${aba}` });
}

// ====================== Biblioteca + Lista de Leitura ======================
function abrirLivros() {
  const l0 = S.est.livros || { itens: [], nao_lidos: [], em_andamento: [], lidos: [], fila: [], generos: [], interesses: {}, paginas_mes_total: 0, paginas_mes_restantes: 0 };
  registrarTela({ tipo: 'modal', id: 'livros', rotulo: 'Biblioteca' });
  let janela = null;
  const busca = lembrar('livros.busca', h('input', { type: 'search', placeholder: 'Buscar título ou autor…', 'aria-label': 'Buscar livro' }));
  const gen = lembrar('livros.genero', h('select', { 'aria-label': 'Filtrar por gênero' }, [
    h('option', { value: '' }, 'Todos os gêneros'),
    ...(l0.generos || []).map((g) => h('option', { value: g }, g)),
  ]));
  const ordem = lembrar('livros.ordem', h('select', { 'aria-label': 'Ordenar livros' }, [
    ['padrao', 'Ordem padrão'],
    ['curtos', 'Mais curtos primeiro'],
    ['longos', 'Mais longos primeiro'],
    ['andamento', 'Em andamento primeiro'],
  ].map(([k, rot]) => h('option', { value: k }, rot))));
  const soPode = lembrar('livros.sopode', h('input', { type: 'checkbox' }));
  const capWrap = h('div');
  const tabsWrap = h('div');
  const controlesWrap = h('div', { class: 'decisao' });
  const lista = h('div', { class: 'decisao' });
  let aba = memoria.ler('livros.aba', 'nao_lidos');
  const trocarAba = (v) => { janela?.salvarRolagem(`livros.y.${aba}`); aba = v; render(); janela?.restaurarRolagem(`livros.y.${aba}`); };

  const agir = async (rota, body, msgFn, extraDiario = 1) => {
    try {
      const r = await api(rota, body || {});
      S.est = r.estado;
      if (extraDiario > 0) await carregarDiario(extraDiario, S.maxSeq);
      desenharEstado();
      if (msgFn) toast(msgFn(r));
      render();
    } catch (x) { tratar(x); }
  };

  const renderCard = (i, l) => {
    const progTxt = i.lido
      ? `${i.paginas} págs · concluído`
      : i.progresso > 0
        ? `${i.progresso}/${i.paginas} págs (${i.percentual}%)`
        : `${i.paginas} págs`;
    return h('div', { class: 'livro-card' }, [
      h('div', { class: 'livro-topo' },
        h('div', null,
          h('div', { class: 'livro-titulo' }, `${i.lido ? '✓ ' : ''}${i.titulo}`),
          h('div', { class: 'livro-sub' }, `${i.autor}, ${i.ano} · ${i.genero}`)),
        h('span', { class: 'livro-pags' }, progTxt)),
      (i.conhecimento_rotulos || []).length > 0 && h('div', { class: 'tags-conh' },
        i.conhecimento_rotulos.map((rot) => h('span', { class: 'tag-conh' }, rot))),
      i.em_andamento && barra(i.percentual, 'cognicao'),
      !i.lido && h('div', { class: 'duas-desigual' },
        h('button', {
          class: 'btn m opcao', type: 'button', disabled: !i.pode,
          onclick: () => agir('ler', { id: i.id }, (r) => {
            const info = r.leitura;
            return info.concluido
              ? `Concluiu "${info.titulo}" (${info.total_paginas} págs)! Restam ${info.paginas_restantes_mes} págs.`
              : `Leu ${info.paginas_lidas_agora} págs de "${info.titulo}" (${info.progresso}/${info.total_paginas}).`;
          }),
        }, i.motivo ? i.motivo : (l.paginas_mes_restantes <= 0 ? 'Sem páginas no mês' : (i.em_andamento ? `Continuar (${i.faltam} p.)` : 'Ler agora'))),
        h('button', {
          class: `btn m ${i.na_fila ? 'p' : 'auto'}`, type: 'button',
          'aria-label': i.na_fila ? `Remover ${i.titulo} da lista` : `Adicionar ${i.titulo} à lista de leitura`,
          onclick: () => agir(i.na_fila ? 'livros/fila/remover' : 'livros/fila/adicionar', { id: i.id },
            () => i.na_fila ? `Removido da lista: "${i.titulo}".` : `Adicionado à lista: "${i.titulo}".`, 0),
        }, i.na_fila ? '✓ Na lista' : '+ Lista')),
    ].filter(Boolean));
  };

  const renderFila = (l) => {
    const fila = l.fila || [];
    const chkAuto = h('input', { type: 'checkbox', checked: !!l.auto_ler_fila });
    chkAuto.addEventListener('change', () => agir('livros/fila/auto', { ativar: chkAuto.checked },
      (r) => r.resultado.auto_ler ? 'Leitura automática da lista ativada ao virar o mês.' : 'Leitura automática ao virar o mês desativada.', 0));

    return [
      h('p', { class: 'nota' }, 'Adicione livros na ordem desejada e leia vários de uma vez com 1 clique.'),
      h('div', { class: 'duas-desigual' },
        h('button', {
          class: 'btn m', type: 'button', disabled: !fila.length || (l.paginas_mes_restantes || 0) <= 0,
          onclick: () => agir('livros/ler_fila', {}, (r) => r.resultado.mensagem, Math.max(1, fila.length)),
        }, (l.paginas_mes_restantes || 0) <= 0 ? 'Capacidade do mês esgotada' : `Ler lista agora (${fila.length})`),
        h('button', {
          class: 'btn p m', type: 'button', disabled: !fila.length,
          onclick: () => agir('livros/fila/limpar', {}, () => 'Lista de leitura esvaziada.', 0),
        }, 'Limpar')),
      h('label', { class: 'check-linha' }, chkAuto, h('span', null, 'Ler lista automaticamente ao virar o mês')),
      ...(fila.length ? fila.map((i, idx) => h('div', { class: 'livro-card' },
        h('div', { class: 'livro-topo' },
          h('div', null,
            h('div', { class: 'livro-titulo' }, `${idx + 1}º · ${i.titulo}`),
            h('div', { class: 'livro-sub' }, `${i.autor} · ${i.em_andamento ? `${i.progresso}/${i.paginas}` : i.paginas} págs${i.motivo ? ` · ${i.motivo}` : ''}`)),
          h('span', { class: 'livro-pags' }, `${i.faltam} p.`)),
        (i.conhecimento_rotulos || []).length > 0 && h('div', { class: 'tags-conh' },
          i.conhecimento_rotulos.map((rot) => h('span', { class: 'tag-conh' }, rot))),
        h('div', { class: 'fila-controles' },
          h('button', {
            class: 'fila-btn', type: 'button', disabled: idx === 0, 'aria-label': `Subir ${i.titulo}`, title: 'Subir na fila',
            onclick: () => agir('livros/fila/mover', { id: i.id, delta: -1 }, null, 0),
          }, iconeSvg(SVG_SETA_CIMA, 16)),
          h('button', {
            class: 'fila-btn', type: 'button', disabled: idx === fila.length - 1, 'aria-label': `Descer ${i.titulo}`, title: 'Descer na fila',
            onclick: () => agir('livros/fila/mover', { id: i.id, delta: 1 }, null, 0),
          }, iconeSvg(SVG_SETA_BAIXO, 16)),
          h('button', {
            class: 'btn p m', type: 'button',
            onclick: () => agir('livros/fila/remover', { id: i.id }, () => `Removido "${i.titulo}" da lista.`, 0),
          }, 'Remover')),
      )) : [h('p', { class: 'nota' }, 'Nenhum livro na lista de leitura ainda. Use "+ Lista" na aba "Para ler".')]),
    ];
  };

  const render = () => {
    const l = S.est.livros || l0;
    const capPct = l.paginas_mes_total > 0 ? Math.round(100 * (l.paginas_mes_restantes || 0) / l.paginas_mes_total) : 0;
    const ints = Object.entries(l.interesses || {}).slice(0, 4).map(([k, v]) => `${k} (${v})`).join(', ');
    capWrap.replaceChildren(...[
      h('div', { class: 'barra-linha' },
        h('div', { class: 'topo' },
          h('span', null, 'Capacidade de leitura no mês'),
          h('span', null, `${l.paginas_mes_restantes || 0} / ${l.paginas_mes_total || 0} págs`)),
        barra(capPct, 'patrimonio')),
      ints && h('p', { class: 'nota' }, `Interesses: ${ints}`),
    ].filter(Boolean));

    const tabs = seg([
      ['nao_lidos', `Para ler (${(l.nao_lidos || []).length})`],
      ['fila', `Lista (${(l.fila || []).length})`],
      ['em_andamento', `Lendo (${(l.em_andamento || []).length})`],
      ['lidos', `Lidos (${(l.lidos || []).length})`],
    ], aba, trocarAba, 'livros.aba');
    aba = tabs.valor();
    tabsWrap.replaceChildren(tabs);

    if (aba === 'fila') {
      controlesWrap.replaceChildren();
      lista.replaceChildren(...renderFila(l));
      return;
    }

    controlesWrap.replaceChildren(
      h('div', { class: 'duas' }, busca, gen),
      aba === 'nao_lidos' && campo('Ordenar por', ordem),
      aba !== 'lidos' && h('label', { class: 'check-linha' }, soPode, h('span', null, 'Mostrar só os que já posso ler agora')),
    );

    const termo = busca.value.trim().toLowerCase();
    const gsel = gen.value;
    const base = aba === 'lidos' ? (l.lidos || []) : (aba === 'em_andamento' ? (l.em_andamento || []) : (l.nao_lidos || []));
    let fil = base.filter((i) => {
      if (gsel && i.genero !== gsel) return false;
      if (soPode.checked && aba !== 'lidos' && !i.pode) return false;
      if (termo && !i.titulo.toLowerCase().includes(termo) && !i.autor.toLowerCase().includes(termo)) return false;
      return true;
    });
    if (aba === 'nao_lidos') {
      const ord = ordem.value;
      if (ord === 'curtos') fil = [...fil].sort((a, b) => a.faltam - b.faltam);
      else if (ord === 'longos') fil = [...fil].sort((a, b) => b.faltam - a.faltam);
      else if (ord === 'andamento') fil = [...fil].sort((a, b) => Number(b.em_andamento) - Number(a.em_andamento));
    }
    const vazioMsg = aba === 'lidos'
      ? 'Você ainda não concluiu nenhum livro.'
      : (aba === 'em_andamento' ? 'Nenhum livro em andamento no momento.' : 'Nenhum livro disponível com esse filtro.');
    lista.replaceChildren(...(fil.length ? fil.slice(0, 60).map((item) => renderCard(item, l)) : [h('p', { class: 'nota' }, vazioMsg)]));
  };
  busca.addEventListener('input', render);
  gen.addEventListener('change', render);
  ordem.addEventListener('change', render);
  soPode.addEventListener('change', render);
  render();

  janela = dialogo({
    titulo: `Biblioteca (${l0.total_catalogo || 205} livros)`,
    corpo: h('div', { class: 'decisao' }, capWrap, tabsWrap, controlesWrap, lista),
    aoVoltar: abrirAcoes,
    rolagem: () => `livros.y.${aba}`,
  });
}

function fmtBrl(v) {
  return `R$ ${Number(v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

// ====================== ENEM, Faculdade (34 cursos), Técnico e Pós — atualiza no lugar ======================
function abrirEducacaoBr() {
  const ed0 = S.est.educacao_br;
  if (!ed0) return;
  registrarTela({ tipo: 'modal', id: 'educacao_br', rotulo: 'ENEM / Faculdade' });
  let janela = null;
  const corpoWrap = h('div', { class: 'decisao' });

  const areasCurso = ['Todas', ...new Set((ed0.cursos || []).map((c) => c.area).filter(Boolean))];
  const areaCursoSel = lembrar('educ.area_curso', h('select', { 'aria-label': 'Filtrar área do curso' },
    areasCurso.map((a) => h('option', { value: a === 'Todas' ? '' : a }, a === 'Todas' ? `Todas as áreas (${(ed0.cursos || []).length} cursos)` : a))));
  const buscaCurso = lembrar('educ.busca_curso', h('input', { type: 'search', placeholder: 'Buscar curso (ex.: Filosofia, Letras, Matemática)…' }));

  const agir = (rota, body, msg) => async () => {
    try {
      const r = await api(rota, body || {});
      S.est = r.estado;
      await carregarDiario(1, S.maxSeq);
      desenharEstado();
      toast(typeof msg === 'function' ? msg(r.resultado) : msg);
      render();
    } catch (e) { tratar(e); }
  };

  const render = () => {
    const ed = S.est.educacao_br;
    const mun = S.est.mundo;
    const cidAtual = mun?.cidade?.id || 'bh';
    const uniSel = lembrar('educ.uni', h('select', {}, ed.universidades.map((u) => h('option', { value: u.sigla },
      `${u.sigla} · ${u.nome} [${u.uf === 'BR' ? 'Nacional / EAD' : `${u.cidade_nome}/${u.uf}`} · corte ${u.corte}]`))));

    const areaFil = areaCursoSel.value;
    const termoFil = buscaCurso.value.trim().toLowerCase();
    const cursosFiltrados = ed.cursos.filter((c) => (!areaFil || c.area === areaFil) && (!termoFil || c.nome.toLowerCase().includes(termoFil)));
    const listaCursos = cursosFiltrados.length ? cursosFiltrados : ed.cursos;
    const curSel = lembrar('educ.curso', h('select', {}, listaCursos.map((c) =>
      h('option', { value: c.id }, `${c.nome} [${c.tipo}] (${c.anos}a, ${fmtBrl(c.mensalidade)})`))));

    const modSel = lembrar('educ.modalidade', h('select', {}, [
      ['sisu', 'SISU (pública)'], ['prouni', 'PROUNI (bolsa privada)'],
      ['fies', 'FIES (financiamento)'], ['vestibular', 'Vestibular próprio'],
    ].map(([id, rot]) => h('option', { value: id }, rot))));
    const posSel = lembrar('educ.pos', h('select', {}, ed.pos_opcoes.map((p) => h('option', { value: p.id }, `${p.nome} (${p.meses}m, +${p.bonus}% salário)`))));
    const tecSel = (ed.cursos_tecnicos || []).length
      ? lembrar('educ.tec', h('select', {}, ed.cursos_tecnicos.map((t) => h('option', { value: t.id }, `${t.nome} (${t.meses}m · privada ${fmtBrl(t.mensalidade)}/mês)`))))
      : null;
    const tecPub = lembrar('educ.tec_pub', h('input', { type: 'checkbox', checked: true }));
    const avisoCidade = h('div', { class: 'aviso-cidade' });
    const notaResumo = h('p', { class: 'nota' });
    const chkMudar = lembrar('educ.mudar', h('input', { type: 'checkbox' }));
    const boxMudar = h('label', { class: 'check-linha' }, chkMudar, h('span', null, 'Mudar-me para a cidade da universidade ao ingressar'));

    const atualizarCidadeECorte = () => {
      const u = ed.universidades.find((x) => x.sigla === uniSel.value);
      const cr = ed.cursos.find((x) => x.id === curSel.value);
      if (u && cr) {
        const corteEst = u.corte + cr.ajuste;
        const minha = ed.enem ? ed.enem.media : null;
        notaResumo.textContent = `Corte estimado (${cr.nome} na ${u.sigla}): ${corteEst} pts${minha != null ? ` · Seu ENEM: ${minha} ${minha >= corteEst ? '✓' : `(faltam ${(corteEst - minha).toFixed(1)})`}` : ''}`;
      }
      if (!u || u.uf === 'BR' || u.cidade_id === cidAtual) {
        avisoCidade.className = 'aviso-cidade ok';
        avisoCidade.textContent = u && u.uf === 'BR'
          ? 'Instituição com oferta nacional/regional compatível com sua cidade.'
          : `Você já mora em ${mun?.cidade?.nome || 'sua cidade'}/${mun?.cidade?.uf || ''}. Sem necessidade de mudança.`;
        boxMudar.style.display = 'none';
        chkMudar.checked = false;
      } else {
        avisoCidade.className = 'aviso-cidade';
        const custo = ed.custo_mudanca > 0 ? ` (custo de mudança: ${fmtBrl(ed.custo_mudanca)})` : ' (sem custo para menores de 18 anos)';
        avisoCidade.textContent = `A ${u.sigla} fica em ${u.cidade_nome}/${u.uf}, e você mora em ${mun?.cidade?.nome}/${mun?.cidade?.uf}${custo}.`;
        boxMudar.style.display = 'flex';
      }
    };
    uniSel.addEventListener('change', atualizarCidadeECorte);
    curSel.addEventListener('change', atualizarCidadeECorte);
    atualizarCidadeECorte();

    corpoWrap.replaceChildren(...[
      mun?.cidade && h('p', { class: 'nota' }, `Residência atual: ${mun.cidade.nome}/${mun.cidade.uf}.`),
      ed.enem && h('p', { class: 'nota' }, `ENEM ${ed.enem_ano}: média ${ed.enem.media} (Redação ${ed.enem.redacao}).`),
      ed.uni && h('p', { class: 'nota' }, `Graduação: ${ed.cursos.find((c) => c.id === ed.curso)?.nome || ed.curso} na ${ed.uni} (${String(ed.modalidade || '').toUpperCase()}).`),
      ed.tecnico_atual && h('p', { class: 'nota' }, `Curso técnico em andamento: ${ed.tecnico_atual.id} (${ed.tecnico_atual.meses} meses restantes).`),
      ed.fies_divida > 0 && h('p', { class: 'nota' }, `Dívida FIES: ${fmtBrl(ed.fies_divida)}.`),
      ed.pos_atual && h('p', { class: 'nota' }, `Pós em curso: ${ed.pos_atual.nivel} (${ed.pos_atual.meses} meses restantes).`),
      h('div', { class: 'duas' },
        h('button', { class: 'btn m opcao', type: 'button', onclick: agir('educacao/enem', {}, (r) => `ENEM feito! Média ${r.media}.`) }, 'Fazer ENEM deste ano'),
        h('button', { class: 'btn p m', type: 'button', onclick: () => { janela?.fechar(); abrirEstudar(); } }, 'Estudar p/ ENEM →')),
      h('div', { class: 'divisor d1' }),
      campo('Universidade', uniSel),
      avisoCidade,
      boxMudar,
      h('div', { class: 'duas' }, campo('Área do curso', areaCursoSel), campo('Filtrar curso', buscaCurso)),
      campo(`Curso (${listaCursos.length} disponíveis)`, curSel),
      notaResumo,
      campo('Modalidade', modSel),
      h('button', { class: 'btn m opcao', type: 'button', onclick: () => agir('educacao/ingressar', { uni: uniSel.value, curso: curSel.value, modalidade: modSel.value, mudar_cidade: chkMudar.checked }, (r) => `Ingressou em ${r.curso} (${r.universidade})${r.mudou_para ? ` e mudou-se para ${r.mudou_para}` : ''}!`)() }, 'Ingressar na universidade'),
      h('button', { class: 'btn m opcao', type: 'button', onclick: agir('educacao/ic', {}, 'Iniciação Científica iniciada por 12 meses!') }, 'Iniciar Iniciação Científica (IC)'),
      h('div', { class: 'divisor d2' }),
      tecSel && campo('Curso técnico (≥15 anos, fund. completo)', tecSel),
      tecSel && h('label', { class: 'check-linha' }, tecPub, h('span', null, 'Vaga pública gratuita (Instituto Federal)')),
      tecSel && h('button', { class: 'btn m opcao', type: 'button', onclick: () => agir('educacao/tecnico', { id: tecSel.value, publica: tecPub.checked }, (r) => `Matriculado no ${r.nome}!`)() }, 'Matricular-se em curso técnico'),
      h('div', { class: 'divisor d2' }),
      campo('Pós-graduação', posSel),
      h('button', { class: 'btn m opcao', type: 'button', onclick: () => agir('educacao/pos', { nivel: posSel.value }, (r) => `Iniciou ${r.nivel}!`)() }, 'Iniciar pós-graduação'),
    ].filter(Boolean));
  };
  areaCursoSel.addEventListener('change', render);
  buscaCurso.addEventListener('input', render);
  render();
  janela = dialogo({ titulo: 'ENEM, Faculdade, Técnico e Pós', corpo: corpoWrap, aoVoltar: abrirAcoes, rolagem: 'educ.y' });
}

// ====================== Carreiras, Trabalho, Empresa e Política — atualiza no lugar ======================
function abrirCarreiras() {
  if (!S.est.carreiras) return;
  registrarTela({ tipo: 'modal', id: 'carreiras', rotulo: 'Carreiras' });
  let janela = null;
  const corpoWrap = h('div', { class: 'decisao' });

  const agir = (rota, body, msg) => async () => {
    try {
      const r = await api(rota, body || {});
      S.est = r.estado;
      await carregarDiario(1, S.maxSeq);
      desenharEstado();
      toast(typeof msg === 'function' ? msg(r.resultado) : msg);
      render();
    } catch (e) { tratar(e); }
  };

  const render = () => {
    const cr = S.est.carreiras;
    const concSel = lembrar('carr.concurso', h('select', {}, cr.concursos.map((c) => h('option', { value: c.id }, `${c.cargo} (${c.nivel}, ${fmtBrl(c.salario)})`))));
    const setSel = lembrar('carr.setor', h('select', {}, cr.setores.map((s) => h('option', { value: s }, s))));
    const porSel = lembrar('carr.porte', h('select', {}, [h('option', { value: 'micro' }, 'Microempresa (8 mínimos)'), h('option', { value: 'pequena' }, 'Pequena empresa (22 mínimos)')]));
    const mpArea = lembrar('carr.mparea', h('input', { type: 'text', maxlength: 40, placeholder: 'ex.: Tecnologia, Saúde, Comércio', value: 'Geral' }));
    const freelaAreas = (S.est.intelecto?.areas_conhecimento || []).map((a) => [a.id, a.rotulo]);
    const flSel = lembrar('carr.freela', h('select', {}, freelaAreas.map(([id, rot]) => h('option', { value: id }, rot))));
    const parSel = lembrar('carr.partido', h('select', {}, cr.partidos.map((p) => h('option', { value: p.id }, p.nome))));
    const carSel = lembrar('carr.cargo', h('select', {}, cr.cargos.map((c) => h('option', { value: c.id }, `${c.nome} (≥${c.idade_min}a, ${fmtBrl(c.salario)})`))));
    const movSel = lembrar('carr.mov', h('select', {}, (cr.movimentos || []).map((m) => h('option', { value: m.id }, m.nome))));
    const pauSel = lembrar('carr.pauta', h('select', {}, (cr.pautas || []).map((p) => h('option', { value: p.id }, p.titulo))));
    const pol = cr.politica;
    const exRest = cr.extras_restantes ?? 0;
    const flRest = cr.freelas_restantes ?? 0;

    corpoWrap.replaceChildren(...[
      cr.estavel && h('p', { class: 'nota' }, `Cargo público estável: ${cr.cargo_publico}.`),
      cr.meio_periodo && h('p', { class: 'nota' }, `Estágio / meio período: ${cr.meio_periodo.area}.`),
      cr.empresa && h('p', { class: 'nota' }, `Empresa própria: ${cr.empresa.nome} (${cr.empresa.setor}, ${cr.empresa.porte}).`),
      pol.partido_nome && h('p', { class: 'nota' }, `Partido: ${pol.partido_nome} · Influência ${Math.round(pol.influencia)}${pol.cargo_nome ? ` · ${pol.cargo_nome} (${pol.mandato_meses}m)` : ''}`),
      h('button', {
        class: 'btn m', type: 'button', disabled: exRest <= 0,
        onclick: agir('carreiras/trabalho_extra', {}, (r) => `Hora extra realizada: +${fmtBrl(r.valor)} (+experiência)!`),
      }, `Fazer hora extra / turno adicional (${exRest}/2 no mês)`),
      campo(`Projeto freelancer (${flRest}/2 restantes no mês)`, flSel),
      h('div', { class: flRest > 1 ? 'duas' : '' },
        h('button', { class: 'btn m opcao', type: 'button', disabled: flRest <= 0, onclick: () => agir('carreiras/freela', { area: flSel.value }, (r) => `Freela de ${r.area}: +${fmtBrl(r.valor)}!`)() }, 'Fazer 1 freela'),
        flRest > 1 && h('button', { class: 'btn m', type: 'button', onclick: () => agir('carreiras/freela_lote', { area: flSel.value }, (r) => `${r.quantidade}× freelas de ${r.area}: +${fmtBrl(r.valor)}!`)() }, `Fazer ${flRest}× freelas`)),
      h('div', { class: 'divisor d1' }),
      campo('Concurso público', concSel),
      h('button', { class: 'btn m opcao', type: 'button', onclick: () => agir('carreiras/concurso', { id: concSel.value }, (r) => r.aprovado ? `Aprovado(a) para ${r.cargo}!` : `Não atingiu o corte (${r.nota} < ${r.corte}).`)() }, 'Prestar concurso'),
      !cr.meio_periodo
        ? h('div', { class: 'decisao' }, campo('Estágio / meio período (área)', mpArea),
          h('button', { class: 'btn m opcao', type: 'button', onclick: () => agir('carreiras/meio_periodo', { area: mpArea.value }, (r) => `Iniciou estágio em ${r.area} (${fmtBrl(r.bolsa)}/mês)!`)() }, 'Iniciar estágio / meio período'))
        : h('button', { class: 'btn m opcao', type: 'button', onclick: agir('carreiras/sair_meio_periodo', {}, 'Estágio / meio período encerrado.') }, 'Encerrar estágio / meio período'),
      h('div', { class: 'divisor d1' }),
      !cr.empresa ? h('div', { class: 'decisao' }, campo('Setor da empresa', setSel), campo('Porte', porSel),
        h('button', { class: 'btn m opcao', type: 'button', onclick: () => agir('carreiras/abrir_empresa', { setor: setSel.value, porte: porSel.value }, (r) => `Fundou ${r.nome}!`)() }, 'Abrir empresa própria'))
        : h('div', { class: 'decisao' },
          cr.empresa.pode_expandir && h('button', { class: 'btn m opcao', type: 'button', onclick: agir('carreiras/expandir_empresa', {}, (r) => `${r.nome} expandida para ${r.porte} (+${r.vagas_novas} vagas)!`) }, `Expandir ${cr.empresa.nome} p/ ${cr.empresa.proximo_porte} (${fmtBrl(cr.empresa.custo_expansao)})`),
          h('button', { class: 'btn m opcao', type: 'button', onclick: agir('carreiras/encerrar_empresa', {}, (r) => `Encerrou ${r.nome}.`) }, `Encerrar ${cr.empresa.nome}`)),
      h('div', { class: 'divisor d2' }),
      campo('Sindicato / movimento social', movSel),
      h('button', { class: 'btn m opcao', type: 'button', onclick: () => agir('politica/movimento', { id: movSel.value }, (r) => `Participou de ação no(a) ${r.movimento} (influência ${r.influencia}).`)() }, 'Participar de assembleia / movimento'),
      campo('Partido político', parSel),
      h('button', { class: 'btn m opcao', type: 'button', onclick: () => agir('politica/filiar', { partido: parSel.value }, (r) => `Filiado(a) ao ${r.partido}.`)() }, 'Filiar-se ao partido'),
      h('button', { class: 'btn m opcao', type: 'button', onclick: agir('politica/campanha', {}, (r) => `Campanha feita! Influência: ${r.influencia}.`) }, 'Fazer campanha política'),
      campo('Cargo eletivo', carSel),
      h('button', { class: 'btn m opcao', type: 'button', onclick: () => agir('politica/concorrer', { cargo: carSel.value }, (r) => r.eleito ? `Eleito(a) ${r.cargo}!` : `Não foi eleito(a) (${r.pontos} < ${r.corte}).`)() }, 'Concorrer à eleição'),
      pol.cargo && campo('Pauta legislativa (mandato ativo)', pauSel),
      pol.cargo && h('button', { class: 'btn m opcao', type: 'button', onclick: () => agir('politica/projeto', { pauta: pauSel.value }, (r) => `Projeto "${r.titulo}" aprovado!`)() }, 'Propor projeto de lei'),
    ].filter(Boolean));
  };
  render();
  janela = dialogo({ titulo: 'Carreiras, Trabalho e Política', corpo: corpoWrap, aoVoltar: abrirAcoes, rolagem: 'carr.y' });
}

// ====================== Mundo, Imóveis, Itens e Banco — atualiza no lugar ======================
function abrirMundo() {
  if (!S.est.mundo) return;
  registrarTela({ tipo: 'modal', id: 'mundo', rotulo: 'Cidade & Banco' });
  let janela = null;
  const corpoWrap = h('div', { class: 'decisao' });

  const agir = (rota, body, msg) => async () => {
    try {
      const r = await api(rota, body || {});
      S.est = r.estado;
      await carregarDiario(1, S.maxSeq);
      desenharEstado();
      toast(typeof msg === 'function' ? msg(r.resultado) : msg);
      render();
    } catch (e) { tratar(e); }
  };

  const render = () => {
    const m = S.est.mundo;
    const cidSel = h('select', {}, m.cidades.map((c) => h('option', { value: c.id, selected: c.id === m.cidade.id }, `${c.nome}/${c.uf} (custo ${c.fator.toFixed(2)}×)`)));
    const imSel = lembrar('mundo.imovel', h('select', {}, m.catalogo_imoveis.map((i) => h('option', { value: i.id }, `${i.nome} — ${fmtBrl(i.preco)}`))));
    const veiSel = lembrar('mundo.veiculo', h('select', {}, m.catalogo_veiculos.map((v) => h('option', { value: v.id }, `${v.nome} — ${fmtBrl(v.preco)}`))));
    const invSel = lembrar('mundo.aplicacao', h('select', {}, [['poupanca', 'Poupança'], ['tesouro', 'Tesouro (Renda Fixa)'], ['acoes', 'Ações na Bolsa']].map(([k, r]) => h('option', { value: k }, r))));
    const valInv = lembrar('mundo.valinv', h('input', { type: 'number', min: 100, step: 100, value: 1000 }));
    const valEmp = lembrar('mundo.valemp', h('input', { type: 'number', min: 100, step: 500, value: 5000 }));

    corpoWrap.replaceChildren(...[
      h('p', { class: 'nota' }, `Cidade: ${m.cidade.nome}/${m.cidade.uf} · Poupança ${fmtBrl(m.inv.poupanca)} · Tesouro ${fmtBrl(m.inv.tesouro)} · Ações ${fmtBrl(m.inv.acoes)}`),
      m.emprestimo > 0 && h('p', { class: 'nota' }, `Empréstimo ativo: ${fmtBrl(m.emprestimo)} (${m.parcelas} parcelas).`),
      campo('Cidade de residência', cidSel),
      h('button', { class: 'btn m opcao', type: 'button', onclick: () => agir('mundo/mudar_cidade', { cidade: cidSel.value }, (r) => `Mudou-se para ${r.cidade}.`)() }, 'Mudar de cidade'),
      h('div', { class: 'divisor d1' }),
      campo('Imóveis', imSel),
      h('div', { class: 'duas' },
        h('button', { class: 'btn m opcao', type: 'button', onclick: () => agir('mundo/comprar_imovel', { tipo: imSel.value, alugar: false }, (r) => `Comprou ${r.nome} para moradia!`)() }, 'Comprar p/ morar'),
        h('button', { class: 'btn m opcao', type: 'button', onclick: () => agir('mundo/comprar_imovel', { tipo: imSel.value, alugar: true }, (r) => `Comprou ${r.nome} para alugar!`)() }, 'Comprar p/ alugar')),
      ...m.imoveis.map((im, idx) => h('button', { class: 'btn m opcao', type: 'button', onclick: agir('mundo/vender_imovel', { idx }, (r) => `Vendeu ${r.nome} por ${fmtBrl(r.valor)}.`) }, `Vender ${im.nome} (${im.alugado ? 'alugado' : 'moradia'} · ${fmtBrl(im.valor)})`)),
      campo('Veículo', veiSel),
      !m.veiculo
        ? h('button', { class: 'btn m opcao', type: 'button', onclick: () => agir('mundo/comprar_veiculo', { tipo: veiSel.value }, (r) => `Comprou ${r.nome}!`)() }, 'Comprar veículo')
        : h('button', { class: 'btn m opcao', type: 'button', onclick: agir('mundo/vender_veiculo', {}, (r) => `Vendeu ${r.nome} por ${fmtBrl(r.valor)}.`) }, `Vender ${m.veiculo.nome} (${fmtBrl(m.veiculo.valor)})`),
      h('div', { class: 'divisor d2' }),
      h('p', { class: 'nota' }, 'Equipamentos e plano de saúde:'),
      ...(m.catalogo_equipamentos || []).map((eq) => h('button', {
        class: 'btn m opcao', type: 'button',
        onclick: eq.possui
          ? agir('mundo/vender_equipamento', { id: eq.id }, (r) => `Vendeu ${r.nome} por ${fmtBrl(r.valor)}.`)
          : agir('mundo/comprar_equipamento', { id: eq.id }, (r) => `Adquiriu ${r.nome}!`),
      }, eq.possui ? `✓ ${eq.nome} — Vender` : `${eq.nome} (${fmtBrl(eq.preco)}) — ${eq.desc}`)),
      h('button', {
        class: 'btn m opcao', type: 'button',
        onclick: agir('mundo/plano_saude', { ativar: !m.plano_saude }, (r) => `Plano de saúde ${r.ativo ? 'contratado' : 'cancelado'}!`),
      }, m.plano_saude ? `✓ Plano de saúde ativo (${fmtBrl(m.plano_saude_mensalidade)}/mês) — Cancelar` : `Contratar plano de saúde (${fmtBrl(m.plano_saude_mensalidade)}/mês)`),
      h('div', { class: 'divisor d2' }),
      h('div', { class: 'duas' }, campo('Aplicação', invSel), campo('Valor (R$)', valInv)),
      h('div', { class: 'duas' },
        h('button', { class: 'btn m opcao', type: 'button', onclick: () => agir('mundo/investir', { tipo: invSel.value, valor: +valInv.value }, 'Investimento realizado!')() }, 'Investir'),
        h('button', { class: 'btn m opcao', type: 'button', onclick: () => agir('mundo/resgatar', { tipo: invSel.value, valor: +valInv.value }, 'Resgate realizado!')() }, 'Resgatar')),
      campo(`Empréstimo bancário (limite ${fmtBrl(m.limite_credito)})`, valEmp),
      h('div', { class: 'duas' },
        h('button', { class: 'btn m opcao', type: 'button', onclick: () => agir('mundo/emprestimo', { valor: +valEmp.value }, 'Empréstimo contratado!')() }, 'Pedir empréstimo'),
        h('button', { class: 'btn m opcao', type: 'button', onclick: () => agir('mundo/quitar', { valor: +valEmp.value }, 'Amortização realizada!')() }, 'Quitar parte/total')),
      (m.extrato || []).length > 0 && h('div', { class: 'divisor d1' }),
      (m.extrato || []).length > 0 && h('p', { class: 'nota' }, 'Extrato recente:'),
      ...(m.extrato || []).slice(0, 8).map((x) => h('div', { class: 'extrato-lin' },
        h('span', null, `${String(x.mes).padStart(2, '0')}/${x.ano} · ${x.desc}`),
        h('span', { class: x.tipo === 'entrada' ? 'in' : 'out' }, `${x.tipo === 'entrada' ? '+' : '-'}${fmtBrl(x.valor)}`))),
    ].filter(Boolean));
  };
  render();
  janela = dialogo({ titulo: 'Cidade, Imóveis, Itens e Banco', corpo: corpoWrap, aoVoltar: abrirAcoes, rolagem: 'mundo.y' });
}

// ====================== Encontros & Amigos — atualizam no lugar ======================
function abrirEncontros() {
  registrarTela({ tipo: 'modal', id: 'encontros', rotulo: 'Encontros' });
  let janela = null;
  const wrap = h('div', { class: 'decisao' });

  const render = () => {
    const e = S.est.encontros || {};
    if (e.namoro) {
      const n = e.namoro;
      const agir = (rota, txt) => async () => {
        try { const r = await api(rota, {}); S.est = r.estado; desenharEstado(); toast(txt(r.resultado)); render(); } catch (x) { tratar(x); }
      };
      wrap.replaceChildren(
        h('p', {}, `Você namora ${n.nome}, ${n.idade} anos, há ${n.meses} meses.`),
        h('button', { class: 'btn m opcao', type: 'button', disabled: !n.pode_pedir, onclick: agir('namoro/pedir', (r) => (r.aceitou ? `${r.nome} aceitou! Vocês se casaram.` : `${r.nome} ainda não estava pronto(a).`)) }, n.pode_pedir ? 'Pedir em casamento' : `Pedir em casamento — ${n.motivo}`),
        h('button', { class: 'btn m opcao', type: 'button', onclick: agir('namoro/terminar', (r) => `Você terminou o namoro com ${r.nome}.`) }, 'Terminar o namoro'));
      return;
    }
    const prefSeg = seg([['oposto', 'Sexo oposto'], ['mesmo', 'Mesmo sexo'], ['todos', 'Todos']], e.preferencia || 'oposto', async (v) => {
      try { const r = await api('encontros/preferencia', { pref: v }); S.est = r.estado; render(); } catch (x) { tratar(x); }
    });
    const aviso = h('p', {}, 'Só para maiores de 18 anos.');
    const lista = e.disponivel ? e.candidatos.map((c) => h('button', { class: 'btn m opcao', type: 'button',
      onclick: async () => { try { const r = await api('encontro', { slot: c.slot }); S.est = r.estado; desenharEstado(); toast(`Você começou a namorar ${r.par.nome}.`); render(); } catch (x) { tratar(x); } } },
    `${c.nome}, ${c.idade} anos`)) : [h('p', {}, e.motivo || 'Indisponível.')];
    wrap.replaceChildren(aviso, campo('Preferência afetiva', prefSeg), ...lista);
  };
  render();
  janela = dialogo({ titulo: 'Encontros', aoVoltar: abrirAcoes, rolagem: 'encontros.y', corpo: wrap });
}

function abrirAmigos() {
  registrarTela({ tipo: 'modal', id: 'amigos', rotulo: 'Amigos' });
  let janela = null;
  const wrap = h('div', { class: 'decisao' });

  const agir = (rota, a, txt) => async () => {
    try { const r = await api(rota, { id: a.id }); S.est = r.estado; desenharEstado(); toast(txt(r)); render(); } catch (e) { tratar(e); }
  };

  const render = () => {
    const lista = S.est.amigos || [];
    wrap.replaceChildren(...(lista.length ? lista.flatMap((a) => [
      h('p', {}, `${a.nome}, ${a.idade} anos${a.proximo ? ' — amizade próxima' : a.interacoes ? ` — ${a.interacoes} momento(s) juntos` : ''}${a.conversou ? ' — já passaram um tempo juntos este mês' : ''}`),
      h('div', { class: 'duas' },
        h('button', { class: 'btn m opcao', type: 'button', disabled: a.conversou, onclick: agir('conversar', a, (r) => `Você conversou com ${r.conversa.nome}.`) }, 'Conversar'),
        h('button', { class: 'btn m opcao', type: 'button', disabled: a.conversou, onclick: agir('convidar', a, (r) => `Você saiu com ${r.convite.nome}.`) }, a.custo > 0 ? `Sair (${fmtBrl(a.custo)})` : 'Convidar p/ sair')),
    ]) : [h('p', {}, 'Você ainda não tem amigos. Use "Conhecer".')]));
  };
  render();
  janela = dialogo({ titulo: 'Amigos', corpo: wrap, aoVoltar: abrirAcoes, rolagem: 'amigos.y' });
}

function conhecerAlguem() {
  const locais = S.est.locais || [];
  if (locais.length < 2) { conhecerEm('vizinhanca'); return; }
  let janela = null;
  janela = dialogo({ titulo: 'Onde conhecer?', aoVoltar: abrirAcoes, corpo: h('div', { class: 'decisao' }, locais.map((l) => h('button', { class: 'btn m opcao', type: 'button',
    onclick: () => { janela.fechar(); conhecerEm(l.id); } }, l.rotulo))) });
}
async function conhecerEm(local) {
  try { const r = await api('conhecer', { local }); S.est = r.estado; desenharEstado(); toast(`Você conheceu ${r.novo.nome}, ${r.novo.idade} anos.`); } catch (e) { tratar(e); }
}

function abrirFoco() {
  const f = S.est.foco;
  const dicas = { equilibrado: 'Nada muda.', estudar: 'Notas melhores e cognição cresce aos poucos; cansa um pouco.',
    trabalhar: 'Se empregado, ganha extra; cansa.', socializar: 'Mais chance de fazer amigos.', descansar: 'Recupera a saúde.' };
  let janela = null;
  const corpo = h('div', { class: 'decisao' }, f.opcoes.map((o) => h('button', { class: 'btn m opcao', type: 'button',
    onclick: async () => { try { if (o.id === 'estudar' && f.areas) { janela.fechar(); abrirArea(); return; } S.est = await api('foco', { foco: o.id }); janela.fechar(); desenharEstado(); toast(`Foco: ${o.rotulo}.`); } catch (e) { tratar(e); } } },
  `${o.id === f.atual ? '✓ ' : ''}${o.rotulo} — ${dicas[o.id]}`)));
  janela = dialogo({ titulo: 'Foco do período', corpo });
}

function abrirArea() {
  const f = S.est.foco;
  let janela = null;
  const corpo = h('div', { class: 'decisao' }, f.areas.map((a) => h('button', { class: 'btn m opcao', type: 'button',
    onclick: async () => { try { S.est = await api('foco', { foco: 'estudar', area: a.id }); janela.fechar(); desenharEstado(); toast(`Estudar: ${a.rotulo}.`); } catch (e) { tratar(e); } } },
  `${a.id === f.area ? '✓ ' : ''}${a.rotulo}`)));
  janela = dialogo({ titulo: 'Área de estudo', corpo, aoVoltar: abrirFoco });
}

function abrirDecisao(d, relInfo = null) {
  let janela = null;
  const restInfo = Number(relInfo?.restantes ?? S.est?.avanco_pendente ?? 0);
  const escolher = async (opcao) => {
    if (S.ocupado) return;
    S.ocupado = true;
    try {
      const r = await api('decidir', { opcao });
      S.est = r.estado;
      janela?.fechar();
      await carregarDiario(1, S.maxSeq);
      desenharEstado();
      const rest = Number(r.restantes_avanco || 0);
      const continuar = () => { if (rest > 0) retomarAvanco(); };
      dialogo({
        titulo: d.titulo,
        corpo: h('div', null,
          h('p', { class: 'texto' }, `${r.auto ? 'O destino escolheu: ' : 'Você escolheu: '}${r.rotulo}.`),
          h('p', { class: 'texto' }, r.resultado),
          r.notas.length > 0 && h('p', { class: 'nota' }, r.notas.join(' · '))),
        botoes: [{ rotulo: rest > 0 ? `Continuar (+${plural(rest, 'mês', 'meses')})` : 'Continuar', p: true }],
        aoFechar: continuar,
      });
    } catch (e) { tratar(e); }
    finally { S.ocupado = false; desenharEstado(); }
  };
  const aviso = restInfo > 0 && relInfo?.pedidos
    ? h('p', { class: 'nota' }, `Mês ${relInfo.meses} de ${relInfo.pedidos} — ao decidir, o restante do período continua automaticamente.`)
    : null;
  const corpo = h('div', { class: 'decisao' }, aviso, h('p', { class: 'texto' }, d.texto),
    d.opcoes.map((rot, i) => h('button', { class: 'btn m opcao', type: 'button', onclick: () => escolher(i) }, rot)),
    h('button', { class: 'btn m auto', type: 'button', onclick: () => escolher('auto') }, 'Decidir por mim'));
  janela = dialogo({ titulo: d.titulo, corpo, fechavel: false });
}

function plural(n, um, varios) { return `${n} ${n === 1 ? um : varios}`; }

function relatorio(rel) {
  if (rel.jogador_morreu) return dialogoMorte(rel);
  const mundo = rel.mundo, partes = [];
  if (mundo.nascimentos) partes.push(plural(mundo.nascimentos, 'nascimento', 'nascimentos'));
  if (mundo.mortes) partes.push(plural(mundo.mortes, 'morte', 'mortes'));
  if (mundo.casamentos) partes.push(plural(mundo.casamentos, 'casamento', 'casamentos'));
  if (mundo.divorcios) partes.push(plural(mundo.divorcios, 'divórcio', 'divórcios'));
  if (mundo.namoros) partes.push(plural(mundo.namoros, 'namoro novo', 'namoros novos'));
  if (rel.meses < 6 && !rel.ano_novo) {
    toast(`${rel.data}${rel.meus.length ? ` · ${plural(rel.meus.length, 'acontecimento', 'acontecimentos')} para você` : ' · nada de especial'}`);
    return;
  }
  const an = rel.ano_novo;
  const destaques = rel.meus.filter((e) => e.cat !== 'aniversario' && e.cat !== 'etapa_de_vida');
  const corpo = h('div', null,
    h('div', { class: 'ev' }, img(A('icones/icone_biografia.svg'), 'mini'),
      h('div', { class: 'tx' }, `De ${rel.de} a ${rel.data}: ${plural(rel.meses, 'mês', 'meses')} de vida.`)),
    destaques.length
      ? h('div', null, destaques.slice(0, 8).map((e) => h('div', { class: `ev ${e.tom}` }, img(A(e.icone), 'mini'),
        h('div', { class: 'tx' }, h('span', { class: 'dt' }, e.data), e.texto))),
        destaques.length > 8 && h('p', { class: 'nota' }, `E mais ${destaques.length - 8} no diário.`))
      : h('p', { class: 'nota' }, 'Nada de especial aconteceu com você, além de mais um aniversário.'),
    partes.length > 0 && h('p', { class: 'nota' }, `No mundo: ${partes.join(', ')}.`),
    an && h('div', null, h('div', { class: 'divisor d3' }),
      h('div', { class: 'ev' }, img(A('eventos/evento_ciclo_economico.svg'), 'mini'), h('div', { class: 'tx' }, `Clima econômico de ${an.ano}: ${an.clima}.`)),
      h('div', { class: 'ev' }, img(A('eventos/evento_inflacao.svg'), 'mini'), h('div', { class: 'tx' }, `Inflação do ano passado: ${an.inflacao_anterior_fmt}. Salário mínimo agora: ${an.salario_minimo}.`))),
    rel.salvo && h('p', { class: 'nota' }, 'Partida salva.'));
  dialogo({ topo: an ? h('div', { class: 'faixa-ano' }, `Ano novo · ${an.ano}`) : null, titulo: an ? null : 'Relatório do turno', corpo, botoes: [{ rotulo: 'Continuar' }] });
}

async function dialogoMorte(rel) {
  const j = S.est.jogador;
  let herdeiros = [];
  try { herdeiros = (await api('herdeiros')).itens; } catch { /* segue sem lista */ }
  let janela = null;
  const morte = [...rel.meus].reverse().find((e) => e.cat === 'morte');
  const corpo = h('div', null,
    h('p', { class: 'texto', style: 'text-align:center;margin:2px 0 8px' }, `${j.nome}${morte ? ` — ${morte.texto.replace(/^Faleceu/, 'faleceu')}` : ' faleceu.'}`),
    h('div', { style: 'display:flex;justify-content:center' }, img(j.avatar, '')),
    herdeiros.length
      ? h('div', null, h('h3', { style: 'font-size:16px;font-weight:700;margin:12px 0 6px;text-align:center' }, 'Continuar a história como…'),
        herdeiros.map((p) => h('button', { class: 'pes', type: 'button', onclick: async () => { try { S.est = await api('jogador', { id: p.id }); janela?.fechar(); await entrarNoJogo(S.est); } catch (e) { tratar(e); } } },
          img(p.avatar, ''), h('span', null, h('div', { class: 'n' }, p.nome), h('div', { class: 's' }, p.sub)), h('span', { class: 'rel' }, p.rel))))
      : h('p', { class: 'nota' }, 'Não há parentes vivos para continuar a história. Crie outro personagem ou volte ao título.'));
  janela = dialogo({ topo: h('div', { class: 'faixa-luto' }, 'In memoriam'), corpo, luto: true,
    botoes: herdeiros.length
      ? [{ rotulo: 'Ver biografia', fn: () => abrirPainel('biografia') }, { rotulo: 'Fechar', p: true }]
      : [{ rotulo: 'Novo personagem', p: true, fn: () => abrirPainel('personagens') },
        { rotulo: 'Voltar ao título', fn: () => irParaTitulo() },
        { rotulo: 'Ver biografia', fn: () => abrirPainel('biografia') },
        { rotulo: 'Fechar' }] });
}

// ====================== ações globais usadas pelos painéis ======================
async function salvar() {
  try { const r = await api('salvar', {}); S.est = r.estado; toast(`Partida salva (${r.arquivo}).`); } catch (e) { tratar(e); }
}

async function irParaTitulo() {
  if (S.est?.tem_jogo && S.est.partida.sujo && !S.est.partida.autosave) {
    if (await confirmar('Salvar antes de sair?', 'Há alterações não salvas.', 'Salvar e sair', 'Sair sem salvar')) await salvar();
  }
  try { await api('fechar', {}); } catch (e) { tratar(e); }
  S.est = null;
  await telaTitulo();
}

iniciarPaineis({
  jogar: async (id) => { S.est = await api('jogador', { id }); await entrarNoJogo(S.est); toast(`Agora você joga com ${S.est.jogador.primeiro}.`); },
  salvar,
  carregar: async () => { fecharTodas(); await irParaTitulo().then(telaCarregar); },
  titulo: irParaTitulo,
  texto: aplicarTexto,
  alternarTema,
  registrarTela,
  atualizar: async () => { S.est = await api('estado'); desenharEstado(); },
  abrirModal: (nome) => { fecharTodas(); abrirModalPorId(nome); },
});

document.addEventListener('keydown', (ev) => {
  if (ev.key === 'Escape' && haPainelAberto() && !$('.fundo')) fecharTopo();
  else if (ev.altKey && ev.key === 'ArrowLeft' && S.tela === 'jogo') {
    ev.preventDefault();
    if ($('.fundo')) $('.fundo')?.__voltar?.();
    else if (haPainelAberto()) fecharTopo();
    else abrirUltimaTela();
  }
});

// ====================== início ======================
(async function iniciar() {
  aplicarTexto(0);
  aplicarTema(temaAtual());
  try {
    const est = await api('estado');
    if (est.tem_jogo) await entrarNoJogo(est); else await telaTitulo();
  } catch (e) {
    mostrar('', h('section', { class: 'screen' }, h('div', { class: 'titulo-faixa' }, 'Sem conexão'), h('p', { class: 'erro' }, e instanceof ErroApi ? e.message : String(e))));
  }
})();
