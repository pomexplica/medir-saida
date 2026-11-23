"""Paginação de posts de página do Facebook sem login (receita do RSSHub, lib/routes/facebook, nov/2026).
Uso: python fb_pag.py <userID> <paginas> [proxy] [--cookie arquivo]"""
import sys, json, secrets, base64, time
from curl_cffi import requests
uid, n = sys.argv[1], int(sys.argv[2]); proxy = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != "-" else None
cookie = open(sys.argv[5]).read().strip() if "--cookie" in sys.argv else None
pv = {}
for l in open("pv.tsv"):
    k, v = l.rstrip("\n").split("\t"); pv[k] = json.loads(v.replace("'", '"'))
lsd = base64.urlsafe_b64encode(secrets.token_bytes(16)).decode().rstrip("=")
jaz = "2" + str(sum(ord(c) for c in lsd))
kw = {"impersonate": "chrome", "timeout": 30}
if proxy: kw["proxy"] = proxy
s = requests.Session(**kw)
H = {"x-fb-lsd": lsd, "accept-language": "en-US", "content-type": "application/x-www-form-urlencoded"}
if cookie: H["cookie"] = cookie
dtsg = None
if cookie:
    t = s.get("https://www.facebook.com/ajax/dtsg/?__a=1", headers={"cookie": cookie}).text
    dtsg = json.loads(t.replace("for (;;);", ""))["payload"]["token"]
def stories(v, acc):
    if isinstance(v, dict):
        if v.get("__typename") == "Story" and v.get("post_id"): acc.append(v); return
        for x in v.values(): stories(x, acc)
    elif isinstance(v, list):
        for x in v: stories(x, acc)
def pinfo(v):
    if isinstance(v, dict):
        if "page_info" in v: return v["page_info"]
        for x in v.values():
            r = pinfo(x)
            if r: return r
    elif isinstance(v, list):
        for x in v:
            r = pinfo(x)
            if r: return r
cur = None; vistos = []
for p in range(n):
    var = dict(pv, id=uid, feedLocation="TIMELINE", feedbackSource=0, omitPinnedPost=True, privacySelectorRenderLocation="COMET_STREAM",
               renderLocation="timeline", run_with_continuation_key=False, stream_count=1, count=3, scale=1, useDefaultActor=False, cursor=cur)
    body = {"lsd": lsd, "jazoest": jaz, "fb_api_req_friendly_name": "ProfileCometTimelineFeedRefetchQuery", "variables": json.dumps(var), "doc_id": "39524813640499646"}
    if dtsg: body["fb_dtsg"] = dtsg
    t0 = time.time(); r = s.post("https://www.facebook.com/api/graphql/", data=body, headers=H)
    linhas = []
    for l in r.text.split("\n"):
        try: linhas.append(json.loads(l))
        except Exception: pass
    acc = []; [stories(x, acc) for x in linhas]
    pi = next((pinfo(x) for x in linhas if pinfo(x)), None)
    ids = [a["post_id"] for a in acc]; novos = [i for i in ids if i not in vistos]; vistos += novos
    datas = [a.get("creation_time") or (a.get("comet_sections", {}).get("timestamp", {}) or {}).get("story", {}).get("creation_time") for a in acc]
    err = (linhas[0].get("errors") or [{}])[0].get("message") if linhas and isinstance(linhas[0], dict) and linhas[0].get("errors") else None
    print(json.dumps({"pagina": p+1, "http": r.status_code, "s": round(time.time()-t0, 2), "bytes": len(r.content), "posts": len(set(ids)), "novos": len(set(novos)),
                      "has_next": pi and pi.get("has_next_page"), "erro": err, "inicio": r.text[:120] if not acc else None}, ensure_ascii=False), flush=True)
    if not pi or not pi.get("has_next_page"): break
    cur = pi["end_cursor"]; time.sleep(2)
print("total posts distintos:", len(vistos))
