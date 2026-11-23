"""Mede cada saída de rede contra as plataformas, pelo conteúdo e não só pelo status.

Mitnick, 23/11/2026. Uma GET por alvo por saída por rodada, com pausa entre alvos.
Uso: python medir_saidas.py --saidas v4,v6,warp --rodadas 1 --pausa 4 --saida-json res.json
Saída "warp" = SOCKS5 do wireproxy em 127.0.0.1:40000; "proxy=<url>" = qualquer proxy.
"""
import argparse, json, re, time, sys
from curl_cffi import requests

ALVOS = {
    # nome: (url, cabeçalhos extras, função que diz se veio o dado)
    "youtube": ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", {},
                lambda s, t: '"playabilityStatus":{"status":"OK"' in t),
    "instagram": ("https://www.instagram.com/natgeo/", {},
                  lambda s, t: s == 200 and bool(re.search(r'content="[\d.,]+[KMkm]? (Followers|seguidores)', t))),
    "tiktok": ("https://www.tiktok.com/@tiktok", {},
               lambda s, t: '"followerCount"' in t),
    "reddit": ("https://old.reddit.com/r/webscraping/new/", {},
               lambda s, t: s == 200 and 'class="thing' in t),
    "linkedin": ("https://www.linkedin.com/company/google", {},
                 lambda s, t: s == 200 and ("followers" in t.lower() or "seguidores" in t.lower()) and "authwall" not in t),
    "threads": ("https://www.threads.com/@zuck", {},
                lambda s, t: s == 200 and ("follower" in t.lower() or "seguidores" in t.lower())),
    "mercadolivre": ("https://lista.mercadolivre.com.br/fone-bluetooth", {},
                     lambda s, t: "poly-component__title" in t or "ui-search-layout" in t),
    "amazon": ("https://www.amazon.com.br/s?k=fone+bluetooth", {},
               lambda s, t: 'data-component-type="s-search-result"' in t),
    "aliexpress": ("https://pt.aliexpress.com/w/wholesale-fone-bluetooth.html", {},
                   lambda s, t: ('"productId"' in t or "productTitle" in t or '"itemList"' in t)
                   and "punish" not in t[:5000]),
}


def sessao(saida):
    kw = {"impersonate": "chrome", "timeout": 25}
    if saida == "v4":
        kw["interface"] = None
        ipv = "4"
    elif saida == "v6":
        ipv = "6"
    elif saida == "warp":
        kw["proxy"] = "socks5h://127.0.0.1:40000"
        ipv = None
    elif saida.startswith("proxy="):
        kw["proxy"] = saida.split("=", 1)[1]
        ipv = None
    else:
        raise SystemExit(f"saída desconhecida: {saida}")
    kw.pop("interface", None)
    return kw, ipv


def medir(saida, nome, url, extra, ok_fn):
    kw, ipv = sessao(saida)
    h = {"accept-language": "pt-BR,pt;q=0.9,en;q=0.8"}
    h.update(extra)
    t0 = time.time()
    try:
        from curl_cffi import CurlOpt
        opts = {}
        if ipv == "4":
            opts[CurlOpt.IPRESOLVE] = 1
        elif ipv == "6":
            opts[CurlOpt.IPRESOLVE] = 2
        r = requests.get(url, headers=h, curl_options=opts, allow_redirects=True, **kw)
        t = r.text
        ok = bool(ok_fn(r.status_code, t))
        dica = ""
        for marca in ("captcha", "account-verification", "authwall", "Please wait", "punish",
                      "Sign in to confirm", "blocked", "challenge", "login"):
            if marca.lower() in t[:200000].lower() or marca.lower() in r.url.lower():
                dica += marca + ";"
        return {"saida": saida, "alvo": nome, "status": r.status_code, "ok": ok,
                "bytes": len(t), "url_final": r.url[:160], "marcas": dica,
                "s": round(time.time() - t0, 2)}
    except Exception as e:
        return {"saida": saida, "alvo": nome, "status": None, "ok": False,
                "erro": str(e)[:160], "s": round(time.time() - t0, 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--saidas", default="v4,v6,warp")
    ap.add_argument("--alvos", default=",".join(ALVOS))
    ap.add_argument("--rodadas", type=int, default=1)
    ap.add_argument("--pausa", type=float, default=4)
    ap.add_argument("--saida-json")
    a = ap.parse_args()
    res = []
    for rod in range(a.rodadas):
        for nome in a.alvos.split(","):
            url, extra, fn = ALVOS[nome]
            for saida in a.saidas.split(","):
                r = medir(saida, nome, url, extra, fn)
                r["rodada"] = rod + 1
                res.append(r)
                print(json.dumps(r, ensure_ascii=False), flush=True)
            time.sleep(a.pausa)
    if a.saida_json:
        json.dump(res, open(a.saida_json, "w"), ensure_ascii=False, indent=1)
    print("\nRESUMO (ok/total por saída e alvo)")
    for saida in a.saidas.split(","):
        linha = []
        for nome in a.alvos.split(","):
            rs = [r for r in res if r["saida"] == saida and r["alvo"] == nome]
            linha.append(f"{nome}={sum(r['ok'] for r in rs)}/{len(rs)}")
        print(saida.ljust(8), " ".join(linha))


if __name__ == "__main__":
    main()
