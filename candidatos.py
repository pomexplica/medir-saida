"""Testa os 9 candidatos de robo-proximos-3 numa saída de rede, pelo conteúdo.
Uso: python candidatos.py --saida direto|socks5h://host:porta --json res.json [--so a,b]
Uma ou duas chamadas por site, 3 s entre sites."""
import argparse, json, re, socket, struct, time, sys
from curl_cffi import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

def ads_body(adv, regiao, token=None):
    d = {"2": 40, "3": {"12": {"1": "", "2": True}, "13": {"1": [adv]}}, "7": {"1": 1, "2": 30, "3": regiao}}
    if token: d["4"] = token
    return "f.req=" + requests.utils.quote(json.dumps(d, separators=(",", ":"))) if hasattr(requests, "utils") else None

from urllib.parse import quote
def fr(d): return "f.req=" + quote(json.dumps(d, separators=(",", ":")))

ALVOS = [
 ("facebook", "GET", "https://www.facebook.com/NASA", None,
   lambda s,t: s==200 and '"post_id"' in t and 'end_cursor' in t, "post_id + end_cursor na 1ª página"),
 ("indeed", "GET", "https://www.indeed.com/jobs?q=python&l=remote", None,
   lambda s,t: s==200 and ('jobkey' in t or 'mosaic-provider-jobcards' in t), "lista de vagas (jobkey)"),
 ("indeed_br", "GET", "https://br.indeed.com/jobs?q=python&l=", None,
   lambda s,t: s==200 and ('jobkey' in t or 'mosaic-provider-jobcards' in t), "lista de vagas (jobkey)"),
 ("google_ads", "POST", "https://adstransparency.google.com/anji/_/rpc/SearchService/SearchCreatives?authuser=0",
   fr({"2":40,"3":{"12":{"1":"","2":True},"13":{"1":["AR17616181786180583425"]}},"7":{"1":1,"2":30,"3":2076}}),
   lambda s,t: s==200 and t.count('"CR') >= 10, "40 anúncios (ids CR...)"),
 ("ebay_vendidos", "GET", "https://www.ebay.com/sch/i.html?_nkw=iphone+13&LH_Sold=1&LH_Complete=1", None,
   lambda s,t: s==200 and ('s-item__title' in t or 's-card__title' in t or 'su-card-container' in t), "cards de vendidos"),
 ("youtube_canal", "GET", "https://www.youtube.com/@ManualdoMundo/about", None,
   lambda s,t: s==200 and 'aboutChannelViewModel' in t, "aboutChannelViewModel"),
 ("amazon_dp", "GET", "https://www.amazon.com/dp/B0BSHF7WHW", None,
   lambda s,t: s==200 and 'data-hook="review"' in t, "avaliações (data-hook=review) na página do produto"),
 ("amazon_reviews", "GET", "https://www.amazon.com/product-reviews/B0BSHF7WHW/?pageNumber=2", None,
   lambda s,t: s==200 and 'data-hook="review"' in t, "página 2 de avaliações"),
 ("telegram", "GET", "https://t.me/s/durov", None,
   lambda s,t: s==200 and t.count('tgme_widget_message ') >= 5, "mensagens do canal"),
 ("trustpilot", "GET", "https://www.trustpilot.com/review/www.amazon.com", None,
   lambda s,t: s==200 and ('"reviewBody"' in t or '"reviews":[' in t), "avaliações no __NEXT_DATA__"),
]

def socks_connect(proxy, host, port, timeout=15):
    m = re.match(r"socks5h?://([^:]+):(\d+)", proxy)
    s = socket.create_connection((m.group(1), int(m.group(2))), timeout=timeout)
    s.sendall(b"\x05\x01\x00"); r = s.recv(2)
    if r != b"\x05\x00": raise OSError(f"socks greet {r!r}")
    hb = host.encode(); s.sendall(b"\x05\x01\x00\x03" + bytes([len(hb)]) + hb + struct.pack(">H", port))
    r = s.recv(4)
    if len(r) < 2 or r[1] != 0: raise OSError(f"socks connect falhou, codigo {r[1] if len(r)>1 else r!r}")
    atyp = r[3]; s.recv({1:4,4:16}.get(atyp, 0) + 2 if atyp != 3 else s.recv(1)[0] + 2)
    return s

def smtp(saida):
    t0 = time.time(); out = {}
    try:
        host = "gmail-smtp-in.l.google.com"
        s = socks_connect(saida, host, 25) if saida != "direto" else socket.create_connection((host, 25), timeout=15)
        s.settimeout(15); f = s.makefile("rb")
        def rd():
            lines = []
            while True:
                l = f.readline().decode(errors="replace"); lines.append(l.strip())
                if len(l) < 4 or l[3] != "-": break
            return lines[-1]
        def cmd(c): s.sendall((c + "\r\n").encode()); return rd()
        out["banner"] = rd()[:60]
        cmd("EHLO verificador.local"); cmd("MAIL FROM:<>")
        out["real"] = cmd("RCPT TO:<pomexplica@gmail.com>")[:40]
        out["inventado"] = cmd("RCPT TO:<zz9q8w7e6r5t4y3u2i1o0p@gmail.com>")[:40]
        cmd("QUIT"); s.close()
        ok = out["real"].startswith("250") and out["inventado"].startswith("550")
        return {"nome": "email_smtp25", "ok": ok, "status": out["real"][:3], "tempo": round(time.time()-t0,2), "bytes": None, "nota": json.dumps(out, ensure_ascii=False)}
    except Exception as e:
        return {"nome": "email_smtp25", "ok": False, "status": None, "tempo": round(time.time()-t0,2), "bytes": None, "nota": f"{type(e).__name__}: {e}"[:150]}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--saida", default="direto"); ap.add_argument("--json"); ap.add_argument("--so", default="")
    a = ap.parse_args(); so = set(x for x in a.so.split(",") if x)
    kw = {"impersonate": "chrome", "timeout": 30}
    if a.saida != "direto": kw["proxy"] = a.saida
    res = []
    try:
        ip = requests.get("https://ipinfo.io/json", **kw).json(); res.append({"nome": "_ip", "nota": f'{ip.get("ip")} {ip.get("org")} {ip.get("city")}'})
    except Exception as e:
        res.append({"nome": "_ip", "nota": f"erro {e}"})
    print(res[0], flush=True)
    for nome, met, url, body, okf, oque in ALVOS:
        if so and nome not in so: continue
        h = {"accept-language": "en-US,en;q=0.9,pt-BR;q=0.8"}
        if met == "POST": h["content-type"] = "application/x-www-form-urlencoded"
        t0 = time.time()
        try:
            r = requests.request(met, url, data=body, headers=h, **kw); t = r.text
            ok = okf(r.status_code, t)
            tit = re.search(r"<title[^>]*>([^<]{0,80})", t); 
            d = {"nome": nome, "ok": ok, "status": r.status_code, "tempo": round(time.time()-t0,2), "bytes": len(r.content),
                 "nota": (oque if ok else "sem o dado; título: " + (tit.group(1).strip() if tit else t[:80].replace("\n"," "))), "url_final": r.url[:120]}
        except Exception as e:
            d = {"nome": nome, "ok": False, "status": None, "tempo": round(time.time()-t0,2), "bytes": None, "nota": f"{type(e).__name__}: {str(e)[:120]}"}
        res.append(d); print(json.dumps(d, ensure_ascii=False), flush=True); time.sleep(3)
    if not so or "email_smtp25" in so:
        d = smtp(a.saida); res.append(d); print(json.dumps(d, ensure_ascii=False), flush=True)
    if a.json: json.dump(res, open(a.json, "w"), ensure_ascii=False, indent=1)

if __name__ == "__main__": main()
