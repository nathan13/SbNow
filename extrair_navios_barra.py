#!/usr/bin/env python3
"""Extrai da página pública os navios 'Na barra' de 'TECON SANTOS'.

Usa navegador Playwright (sem Pomerado e sem API autenticada). Não supõe
identidade dos navios, nem usa dados estáticos de demonstração. Pode exigir
ajuste caso o site mude sua estrutura. Evita publicar resultado não confirmado.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.sync_api import Error as PlaywrightError, sync_playwright

URL = 'https://www.santosbrasil.com.br/app/tcs/atracacao.asp#/app/_jx/lst.asp?lista=atracacao'
BASE = Path(__file__).resolve().parent
DESTINO = BASE / 'site' / 'dados' / 'navios_na_barra.json'
DESTINO_EXTRA = BASE / 'santos_brasil_atracacoes.json'
DIAGNOSTICO = BASE / 'diagnostico'
FUSO = ZoneInfo('America/Sao_Paulo')

# Executado em cada frame da página. Lê apenas linhas visíveis da tabela.
LEITURA_DOM = r"""() => {
  const tx = e => (e.innerText || e.textContent || '').replace(/\s+/g,' ').trim();
  const vis = e => !!(e.getClientRects().length) && getComputedStyle(e).visibility !== 'hidden';
  const rxData = /\b\d{2}\/\d{2}\/\d{4}(?:\s+\d{1,2}:\d{2})?\b/;
  const tabelas = [...document.querySelectorAll('table')];
  const candidatas = tabelas.filter(t => {
    const primeira = tx(t).substring(0, 260).toLowerCase();
    return primeira.includes('navio') && (primeira.includes('atrac') || primeira.includes('prevista'));
  });
  const raizes = candidatas.length ? candidatas : [document];
  const encontrados = [];
  for (const raiz of raizes) {
    for (const tr of raiz.querySelectorAll('tr')) {
      if (!vis(tr)) continue;
      const cels = [...tr.children].filter(e => /^(TD|TH)$/i.test(e.tagName));
      if (cels.length < 2) continue;
      const vals = cels.map(tx);
      const indice = vals.findIndex((v, i) => i > 0 && rxData.test(v));
      if (indice < 1) continue;
      const nome = vals[0];
      const data = vals[indice].match(rxData)?.[0] || '';
      if (!nome || nome.length > 130 || /^(navio|embar(c|ç)ac|total|data\s)/i.test(nome)) continue;
      encontrados.push({navio:nome, data_atracacao_prevista_efetiva:data});
    }
  }
  const seletores = [...document.querySelectorAll('select')].map(s => ({
    selecionado: s.selectedOptions.length ? tx(s.selectedOptions[0]) : '',
    opcoes: [...s.options].map(o => tx(o)).filter(Boolean).slice(0,40)
  }));
  const linhasExemplo = [...document.querySelectorAll('tr')]
    .filter(vis).slice(0,16).map(tr=>tx(tr).slice(0,170));
  return {encontrados, seletores, linhasExemplo};
}"""


def normalizar(s: str) -> str:
    decomposto = unicodedata.normalize('NFKD', str(s or ''))
    return ' '.join(''.join(c for c in decomposto if not unicodedata.combining(c)).lower().split())


def corresponde_opcao(titulo: str, desejado: str) -> bool:
    t, d = normalizar(titulo), normalizar(desejado)
    return t == d or (d == 'na barra' and t == 'navios na barra')


def obter_frames(page):
    return list(page.frames)


def selecionar_option(page, label: str, limite=15) -> bool:
    fim = time.monotonic() + limite
    while time.monotonic() < fim:
        for frame in obter_frames(page):
            try:
                selects = frame.locator('select')
                for i in range(selects.count()):
                    loc = selects.nth(i)
                    opts = loc.evaluate('(s) => [...s.options].map(o=>({texto:(o.textContent||"").trim(),valor:o.value}))')
                    opc = next((o for o in opts if corresponde_opcao(o['texto'], label)), None)
                    if opc is not None:
                        selecionado = loc.evaluate('(s) => (s.selectedOptions[0]?.textContent||"").trim()')
                        if not corresponde_opcao(selecionado, label):
                            loc.select_option(value=opc['valor'], timeout=7000)
                        print('Filtro selecionado:', label)
                        return True
            except PlaywrightError:
                # O frame pode recarregar depois do primeiro filtro.
                pass
        time.sleep(0.5)
    print('Não encontrei automaticamente a opção:', label)
    return False


def ler_tela(page):
    itens, sel, amostras = [], [], []
    for frame in obter_frames(page):
        try:
            d = frame.evaluate(LEITURA_DOM)
            itens.extend(d['encontrados'])
            sel.extend(d['seletores'])
            amostras.extend(d['linhasExemplo'])
        except PlaywrightError:
            continue
    vistos, unicos = set(), []
    for r in itens:
        ch = (normalizar(r['navio']), r['data_atracacao_prevista_efetiva'])
        if ch not in vistos:
            unicos.append(r)
            vistos.add(ch)
    selecionados = [s['selecionado'] for s in sel]
    terminal_ok = any(corresponde_opcao(x, 'TECON SANTOS') for x in selecionados)
    situacao_ok = any(corresponde_opcao(x, 'Na barra') for x in selecionados)
    return unicos, terminal_ok, situacao_ok, sel, amostras


def esperar_dados(page, segundos=18):
    fim = time.monotonic()+segundos
    ultimo = ([], False, False, [], [])
    while time.monotonic() < fim:
        ultimo = ler_tela(page)
        if ultimo[1] and ultimo[2] and ultimo[0]:
            return ultimo
        time.sleep(1)
    return ultimo


def gravar_atomico(caminho, dados):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    provisorio = caminho.with_name(caminho.name + '.tmp')
    provisorio.write_text(json.dumps(dados, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    # Garantir que está legível antes da substituição.
    with provisorio.open(encoding='utf-8') as f:
        json.load(f)
    provisorio.replace(caminho)


def detectar_bloqueio(page, resposta=None):
    """Identifica a resposta de acesso negado, sem tentar contornar a restrição."""
    try:
        texto = page.locator('body').inner_text(timeout=3000).lower()
    except PlaywrightError:
        texto = ''
    html_negado = ('access denied' in texto and
                   ('permission to access' in texto or 'edgesuite.net' in texto))
    codigo_negado = resposta is not None and resposta.status in (401, 403, 429)
    return bool(html_negado or codigo_negado)


def conferir_terminal(page, limite=20):
    """Espera o carregamento do terminal padrão sem alterar o seu valor."""
    fim = time.monotonic() + limite
    while time.monotonic() < fim:
        _, confirmado, _, _, _ = ler_tela(page)
        if confirmado:
            print('Terminal padrão confirmado: TECON SANTOS')
            return True
        if detectar_bloqueio(page):
            return False
        time.sleep(0.5)
    return False


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manual', action='store_true', help='Selecione somente Na barra manualmente; TECON SANTOS já vem selecionado.')
    parser.add_argument('--headless', action='store_true', help='Executa sem mostrar o navegador (o site pode negar esse acesso).')
    args=parser.parse_args()
    if args.manual and args.headless:
        parser.error('--manual e --headless não podem ser usados juntos.')
    DIAGNOSTICO.mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser=p.chromium.launch(headless=args.headless)
        page=browser.new_page(viewport={'width':1440,'height':900},locale='pt-BR',timezone_id='America/Sao_Paulo')
        try:
            print('Abrindo:', URL)
            resposta = page.goto(URL, wait_until='domcontentloaded', timeout=60000)
            page.wait_for_timeout(1800)
            if detectar_bloqueio(page, resposta):
                raise RuntimeError('A Santos Brasil recusou a consulta (Access Denied). '
                                   'Não foram obtidos dados e nenhum JSON foi alterado. '
                                   'Se ocorreu com --headless, teste o modo normal, '
                                   'que mostra o navegador, sem --headless. '
                                   'Se persistir, procure acesso autorizado junto à Santos Brasil.')
            if args.manual:
                if not sys.stdin.isatty():
                    raise RuntimeError('O modo manual requer um terminal interativo.')
                input('No navegador, mantenha TECON SANTOS, selecione apenas Na barra '
                      'e espere a lista carregar. Depois pressione Enter aqui... ')
            else:
                # A URL já abre no TECON SANTOS. Não precisamos alterar o terminal.
                if not conferir_terminal(page):
                    if not args.headless and sys.stdin.isatty():
                        print('Não consegui confirmar o terminal padrão. Não vou alterá-lo automaticamente.')
                        input('Confira se TECON SANTOS aparece no primeiro menu e pressione Enter... ')
                    else:
                        raise RuntimeError('Não consegui confirmar TECON SANTOS na tela.')
                ok_situacao = selecionar_option(page, 'Na barra')
                if not ok_situacao and not args.headless and sys.stdin.isatty():
                    input('Não consegui selecionar Na barra. Escolha somente esse filtro '
                          'no navegador e pressione Enter... ')

            if detectar_bloqueio(page):
                raise RuntimeError('A página passou a mostrar Access Denied. Consulta interrompida.')
            navios, ok_terminal, ok_situacao, selects, amostra = esperar_dados(page)
            diagnostico = {
                'url_atual': page.url.split('#', 1)[0],
                'pagina_bloqueada': detectar_bloqueio(page),
                'terminal_confirmado': ok_terminal,
                'situacao_confirmada': ok_situacao,
                'contagem_linhas_encontradas': len(navios),
                'combos': selects,
                'amostras_de_linhas_visiveis': amostra[:20],
            }
            gravar_atomico(DIAGNOSTICO / 'estrutura_tela.json', diagnostico)
            if not ok_terminal or not ok_situacao:
                raise RuntimeError('A tela não confirmou TECON SANTOS e Na barra. Veja diagnostico/estrutura_tela.json.')
            if not navios:
                raise RuntimeError('Não encontrei linhas de navio e data na tabela. Não vou publicar JSON vazio sem confirmação.')

            agora=datetime.now(FUSO).isoformat(timespec='seconds')
            saida = {
                'fonte': 'Santos Brasil — página pública',
                'fonte_url': URL,
                'terminal': 'TECON SANTOS',
                'situacao': 'Na barra',
                'consultado_em': agora,
                'total': len(navios),
                'navios': [
                    {'navio': r['navio'],
                     'data_atracacao_prevista_efetiva': r['data_atracacao_prevista_efetiva'],
                     'viagem': None, 'armador': None, 'situacao': 'Na barra'}
                    for r in navios
                ],
                'nota': 'A data é a exibida na coluna DATA ATRACACAO PREVISTA / EFETIVA, não necessariamente o ETA.',
            }
            gravar_atomico(DESTINO, saida)
            gravar_atomico(DESTINO_EXTRA, saida)
            print('\nSUCESSO: foram extraídos', len(navios), 'navios')
            for n in navios:
                print('  -', n['navio'], '|', n['data_atracacao_prevista_efetiva'])
            print('JSON do site:', DESTINO)
            print('JSON adicional:', DESTINO_EXTRA)
            return 0
        except (PlaywrightError, RuntimeError) as exc:
            try:
                page.screenshot(path=str(DIAGNOSTICO/'erro_tela.png'), full_page=True, timeout=10000)
            except PlaywrightError:
                pass
            print('\nERRO:', exc, file=sys.stderr)
            print('Se persistir, envie diagnostico/estrutura_tela.json e diagnostico/erro_tela.png.',file=sys.stderr)
            print('O arquivo anterior, se existir, foi preservado.',file=sys.stderr)
            return 1
        finally:
            browser.close()


if __name__ == '__main__':
    sys.exit(main())
