#!/usr/bin/env python3
"""B.LEAGUE公式の日程JSONから、終了した試合（FINAL）のスコアとティップオフ時刻を
index.html に埋め込まれた DATA へ反映する。設定は update_config.json。
標準ライブラリのみ。変更がなければファイルに触らない。"""
import json, re, sys, time, urllib.request
from datetime import datetime, timedelta, timezone

HERE = sys.argv[1] if len(sys.argv) > 1 else "."
CONF = json.load(open(f"{HERE}/update_config.json", encoding="utf-8"))
HTML = f"{HERE}/index.html"
URL = ("https://www.bleague.jp/schedule/?data_format=json&year={year}&mon=all&day=all"
       "&event={event}&club={club}&tab={tab}&ha=&fb=&index={index}")

def fetch(**kw):
    req = urllib.request.Request(URL.format(**kw), headers={"User-Agent": "Mozilla/5.0"})
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if i == 2: raise
            time.sleep(3)

def parse(topic):
    gid = re.search(r'<li class="list-item" id="(\d+)"', topic)
    if not gid: return None
    teams = re.findall(r'<span class="team-name">([^<]*)</span>', topic)
    hs = re.search(r'class="number home-score[^"]*"><span>(\d+)</span>', topic)
    as_ = re.search(r'class="number away-score[^"]*"><span>(\d+)</span>', topic)
    state = re.search(r'class="info-scorestate"><span>([^<]*)</span>', topic)
    arena = re.search(r'<div class="info-arena">(.*?)</div>', topic, re.S)
    spans = re.findall(r'<span>([^<]*)</span>', arena.group(1)) if arena else []
    tip = next((s.strip() for s in spans if re.fullmatch(r'\d{1,2}:\d{2}', s.strip())), "")
    return {"id": gid.group(1), "home": teams[0] if teams else "", "away": teams[1] if len(teams) > 1 else "",
            "hs": int(hs.group(1)) if hs else None, "as": int(as_.group(1)) if as_ else None,
            "final": bool(state and state.group(1).strip().upper() == "FINAL"), "t": tip}

def club_games(c):
    out, idx, seen = {}, 0, set()
    while True:
        d = fetch(year=CONF["year"], event=c["event"], club=c["club"], tab=c["tab"], index=idx)
        for tp in d.get("topics", []):
            g = parse(tp)
            if g and g["id"] not in seen:
                seen.add(g["id"]); out[g["id"]] = g
        nxt = d.get("index")
        if not d.get("topics") or not nxt or int(nxt) <= idx: break
        idx = int(nxt); time.sleep(0.3)
    return out

html = open(HTML, encoding="utf-8").read()
m = re.search(r'const DATA=(\{.*?\});\nconst JP=', html, re.S)
DATA = json.loads(m.group(1))
changes = []
for name, c in CONF["clubs"].items():
    if name not in DATA: continue
    live = club_games(c)
    short = DATA[name]["short"]
    for g in DATA[name]["games"]:
        L = live.get(g.get("id") or "")
        if not L: continue
        if L["t"] and L["t"] != g.get("t"):
            changes.append(f'{short} {g["d"]} vs {g["opp"]}: 時刻 {g.get("t") or "未定"} → {L["t"]}')
            g["t"] = L["t"]
        if L["final"] and L["hs"] is not None and L["as"] is not None:
            mine, opp = (L["hs"], L["as"]) if L["home"] == short else (L["as"], L["hs"])
            sc = f"{mine}-{opp}"; r = "W" if mine > opp else ("L" if mine < opp else "D")
            if g.get("sc") != sc:
                changes.append(f'{short} {g["d"]} vs {g["opp"]}: {"○" if r=="W" else "●" if r=="L" else "△"} {sc}')
                g["sc"], g["r"] = sc, r
                g.setdefault("rn", "")

if not changes:
    print("変更なし"); sys.exit(0)
html = html[:m.start(1)] + json.dumps(DATA, ensure_ascii=False) + html[m.end(1):]
jst = datetime.now(timezone(timedelta(hours=9)))
html = re.sub(r'結果更新日：\d{4}年\d{1,2}月\d{1,2}日', f'結果更新日：{jst.year}年{jst.month}月{jst.day}日', html, count=1)
open(HTML, "w", encoding="utf-8").write(html)
print(f"{len(changes)}件の変更"); print("\n".join(changes))
