#!/usr/bin/env python3
"""Recolecta voces de Reddit sobre Adviento/diciembre y Hallow para el research VoC.

Uso:  python3 reddit_voc.py            (solo librería estándar, Python 3.8+)
Salida: reddit_voc.csv  (una fila por post o comentario, con link exacto)

Usa los endpoints JSON públicos de Reddit, con pausa entre llamadas para no
saturar el servicio. Tarda unos 10-15 minutos.
"""
import csv
import json
import re
import time
import urllib.parse
import urllib.request

UA = "jp-research/1.0 (VoC Adviento; contacto: investigacion personal)"
PAUSA = 2.0          # segundos entre llamadas
POSTS_POR_BUSQUEDA = 25
COMENTARIOS_MIN_PALABRAS = 8

SUBS_EN = ["Catholicism", "Catholic", "TrueChristian", "CatholicMemes"]
SUBS_ES = ["catolicos", "mexico", "Colombia", "argentina", "askspain", "spain",
           "AskLatinAmerica", "Mujico", "MexicoFinanciero"]

QUERIES_EN = [
    "advent busy", "advent guilt", "advent lonely", "advent grief",
    "advent prayer routine", "advent struggling", "advent dry prayer",
    "christmas alone catholic", "christmas grief faith", "advent overwhelmed",
    "Hallow app", "Hallow advent", "Hallow pray25", "Hallow subscription",
]
QUERIES_ES = [
    "adviento", "novena de aguinaldos", "posadas", "rezar diciembre",
    "navidad solo", "navidad duelo", "navidad lejos de mi familia",
    "aguinaldo deudas", "navidad depresion", "virgen de guadalupe",
    "noche de velitas", "Hallow", "app para rezar", "rezar rosario app",
]

PAIS_POR_SUB = {"mexico": "MX", "Mujico": "MX", "MexicoFinanciero": "MX",
                "Colombia": "CO", "argentina": "AR", "askspain": "ES", "spain": "ES"}

# Palabras que hacen relevante un comentario (en minúsculas, sin acentos)
CLAVES = [
    "advent", "adviento", "christmas", "navidad", "diciembre", "december",
    "novena", "posada", "aguinaldo", "velitas", "guadalupe", "hallow",
    "pray", "rezar", "oracion", "oración", "prayer", "rosario", "rosary",
    "lonely", "solo", "sola", "soledad", "grief", "duelo", "falta",
    "guilt", "culpa", "busy", "tiempo", "cansad", "tired", "stress", "estres",
    "deuda", "dinero", "money", "familia", "family", "subscription", "suscrip",
    "precio", "price", "paywall", "trial", "prueba",
]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for intento in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:  # 429 u otros: esperar y reintentar
            espera = PAUSA * (2 ** (intento + 1))
            print(f"  ! {e} -> reintento en {espera:.0f}s")
            time.sleep(espera)
    return None


def relevante(texto):
    t = texto.lower()
    return any(k in t for k in CLAVES)


def limpiar(texto):
    return re.sub(r"\s+", " ", texto or "").strip()


def recorrer_comentarios(nodos, base, filas, sub, titulo):
    for n in nodos:
        if n.get("kind") != "t1":
            continue
        d = n["data"]
        cuerpo = limpiar(d.get("body"))
        if (len(cuerpo.split()) >= COMENTARIOS_MIN_PALABRAS
                and cuerpo not in ("[deleted]", "[removed]") and relevante(cuerpo)):
            filas.append({
                "tipo": "comentario", "sub": sub,
                "pais_inferido": PAIS_POR_SUB.get(sub, ""),
                "hilo": titulo, "score": d.get("score", 0),
                "fecha_utc": time.strftime("%Y-%m-%d", time.gmtime(d.get("created_utc", 0))),
                "texto": cuerpo,
                "url": "https://www.reddit.com" + d.get("permalink", ""),
            })
        rep = d.get("replies")
        if isinstance(rep, dict):
            recorrer_comentarios(rep["data"]["children"], base, filas, sub, titulo)


def main():
    vistos, filas = set(), []
    planes = [(s, q) for s in SUBS_EN for q in QUERIES_EN] + \
             [(s, q) for s in SUBS_ES for q in QUERIES_ES]
    for sub, q in planes:
        url = (f"https://www.reddit.com/r/{sub}/search.json?"
               + urllib.parse.urlencode({"q": q, "restrict_sr": 1, "sort": "relevance",
                                         "t": "all", "limit": POSTS_POR_BUSQUEDA}))
        print(f"r/{sub} :: {q}")
        data = get(url)
        time.sleep(PAUSA)
        if not data:
            continue
        for p in data["data"]["children"]:
            d = p["data"]
            if d["id"] in vistos:
                continue
            vistos.add(d["id"])
            titulo = limpiar(d.get("title"))
            cuerpo = limpiar(d.get("selftext"))
            if not relevante(titulo + " " + cuerpo):
                continue
            filas.append({
                "tipo": "post", "sub": sub, "pais_inferido": PAIS_POR_SUB.get(sub, ""),
                "hilo": titulo, "score": d.get("score", 0),
                "fecha_utc": time.strftime("%Y-%m-%d", time.gmtime(d.get("created_utc", 0))),
                "texto": cuerpo or titulo,
                "url": "https://www.reddit.com" + d["permalink"],
            })
            if d.get("num_comments", 0) == 0:
                continue
            hilo = get(f"https://www.reddit.com{d['permalink']}.json?limit=200&sort=top")
            time.sleep(PAUSA)
            if hilo and len(hilo) > 1:
                recorrer_comentarios(hilo[1]["data"]["children"], d["permalink"],
                                     filas, sub, titulo)
        print(f"  acumulado: {len(filas)} filas")

    with open("reddit_voc.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["tipo", "sub", "pais_inferido", "hilo", "score",
                                          "fecha_utc", "texto", "url"])
        w.writeheader()
        w.writerows(filas)
    print(f"\nListo: reddit_voc.csv con {len(filas)} filas")


if __name__ == "__main__":
    main()
