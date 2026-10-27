"""Confere integridade da coleta antes de publicar no GitHub Pages."""
import json
from datetime import datetime
from pathlib import Path

path = Path('site/dados/navios_na_barra.json')
if not path.is_file():
    raise SystemExit('ERRO: arquivo JSON nao foi criado')
with path.open(encoding='utf-8') as f:
    dados = json.load(f)
if dados.get('terminal') != 'TECON SANTOS' or dados.get('situacao') != 'Na barra':
    raise SystemExit('ERRO: filtros nao confirmados')
navios = dados.get('navios')
if not isinstance(navios, list) or dados.get('total') != len(navios):
    raise SystemExit('ERRO: total nao bate com os registros')
if not navios:
    raise SystemExit('ERRO: nenhuma linha confirmada; nao publicar vazio')
if any(not isinstance(n,dict) or not n.get('navio') for n in navios):
    raise SystemExit('ERRO: navio sem nome')
for navio in navios:
    d=navio.get('prev_mov_descarga')
    e=navio.get('prev_mov_embarque')
    total=navio.get('total_movimentos')
    if any(type(v) is not int or v<0 for v in (d,e,total)) or total != d+e:
        raise SystemExit('ERRO: movimentos ausentes ou inconsistentes: '+navio['navio'])
try:
    dt = datetime.fromisoformat(dados['consultado_em'])
    if dt.tzinfo is None:
        raise ValueError('sem fuso')
except (KeyError, ValueError):
    raise SystemExit('ERRO: data de consulta invalida')
print(f'OK: {len(navios)} navios com movimentos validados; coletado em {dt.isoformat()}')
