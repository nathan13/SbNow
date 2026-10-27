"""Extração de movimentos previstos da ficha pública de cada navio."""
import re
import time
import unicodedata
from playwright.sync_api import Error as PlaywrightError

def sem_acentos(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(c))

def valores(texto):
    texto=sem_acentos(texto).replace("\u00a0"," ")
    resultado={}
    for label, campo in [("descarga","prev_mov_descarga"),("embarque","prev_mov_embarque")]:
        regex=r"\bprev\s*\.?\s*mov\s*\.?\s*(?:de\s+)?"+label+r"\s*[:\-]?\s*(\d+(?:[. ,]\d{3})*)\b"
        valores=[]
        for m in re.finditer(regex,texto,re.I):
            v=m.group(1)
            if re.fullmatch(r"\d+(?:[. ,]\d{3})*",v):
                valores.append(int(re.sub(r"\D","",v)))
        resultado[campo]=valores[0] if valores and len(set(valores))==1 else None
    d,e=resultado["prev_mov_descarga"],resultado["prev_mov_embarque"]
    resultado["total_movimentos"]=d+e if d is not None and e is not None else None
    return resultado

def textos_visiveis(page):
    fontes=[page]+[p for p in page.context.pages if p is not page and not p.is_closed()]
    saida=[]
    for janela in fontes:
        for frame in list(janela.frames):
            try:
                texto=frame.locator("body").inner_text(timeout=900)
                if texto.strip():
                    saida.append((janela.url,frame.url,texto))
            except PlaywrightError:
                pass
    return saida

def clicar_navio(page,nome):
    objetivo=" ".join(nome.split()).casefold()
    for frame in list(page.frames):
        try:
            rows=frame.locator("tr")
            for i in range(min(rows.count(),150)):
                row=rows.nth(i)
                cels=row.locator("td")
                if cels.count()<2:continue
                texto=" ".join(cels.first.inner_text(timeout=750).split()).casefold()
                if texto!=objetivo:continue
                link=cels.first.locator('a, button, [onclick], [role="button"]')
                if link.count():
                    link.first.click(timeout=4500)
                else:
                    cels.first.click(timeout=4500)
                return True
        except PlaywrightError:
            continue
    return False

def ler_ficha(page,nome,espera=12):
    antes=set((u,f,t) for u,f,t in textos_visiveis(page))
    if not clicar_navio(page,nome):
        return valores(""),{"navio":nome,"erro":"Navio nao clicavel"}
    fim=time.monotonic()+espera
    melhor=valores("")
    trechos=[]
    while time.monotonic()<fim:
        for url,frame,txt in textos_visiveis(page):
            if (url,frame,txt) in antes:continue
            m=valores(txt)
            if m["total_movimentos"] is not None:
                return m,{"navio":nome,"origem":url,"frame":frame,"confirmado":True}
            if m["prev_mov_descarga"] is not None or m["prev_mov_embarque"] is not None:
                melhor=m
            simples=sem_acentos(txt)
            pos=simples.lower().find("prev")
            if pos>=0 and "mov" in simples.lower():
                trecho=re.sub(r"\s+"," ",simples[max(0,pos-120):pos+280])
                if trecho and trecho not in trechos:trechos.append(trecho)
        time.sleep(0.5)
    return melhor,{"navio":nome,"campos_incompletos":True,"exemplos_visiveis":trechos[:3]}
