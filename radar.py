"""Hourly news radar: RSS -> category -> similar past events -> real BTC reactions -> docs/data.json"""
import json, os, re, sys, time, datetime as dt
import feedparser, pandas as pd, requests

FEEDS = [  # (name, url) - failures are skipped, edit freely
 ("Cointelegraph", "https://cointelegraph.com/rss"),
 ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
 ("CryptoWave", "https://cryptowave.co.id/feed"),
 ("Google News: Iran/Hormuz", "https://news.google.com/rss/search?q=Iran+Hormuz+oil+tankers&hl=en-US&gl=US&ceid=US:en"),
 ("Google News: Fed/CPI", "https://news.google.com/rss/search?q=Federal+Reserve+interest+rate+CPI&hl=en-US&gl=US&ceid=US:en"),
 ("Google News: Trump crypto", "https://news.google.com/rss/search?q=Trump+bitcoin+tariff&hl=en-US&gl=US&ceid=US:en"),
]
CATS = {  # category -> (Persian label, keywords)
 "geopolitics": ("ژئوپلیتیک و جنگ", r"iran|hormuz|israel|missile|blockade|tanker|war |ukraine|russia|strike|sanction|perang|iran"),
 "fed_rates": ("نرخ بهره و فدرال رزرو", r"federal reserve|\bfed\b|fomc|powell|interest rate|rate cut|rate hike|suku bunga"),
 "inflation_cpi": ("تورم و CPI", r"\bcpi\b|inflation|\bpce\b|inflasi"),
 "trump_policy": ("سیاست‌های ترامپ", r"trump|tariff|white house|executive order|tarif"),
 "crypto_regulation": ("قانون‌گذاری کریپتو", r"\bsec\b|etf|regulat|ban |lawsuit|cftc|stablecoin bill|regulasi"),
 "crypto_crisis": ("بحران و هک", r"hack|exploit|collapse|bankrupt|insolven|liquidat|crash|bank run|peretasan"),
 "oil_opec": ("نفت و اوپک", r"opec|brent|crude|oil price|minyak"),
}
OUT = os.path.join(os.path.dirname(__file__), "docs")
STATE = os.path.join(OUT, "data.json")

def classify(title):
    key = os.getenv("ANTHROPIC_API_KEY")
    if key:  # optional AI classification, falls back to keywords on any error
        try:
            r = requests.post("https://api.anthropic.com/v1/messages", timeout=30,
              headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
              json={"model": "claude-sonnet-5-5", "max_tokens": 20, "messages": [{"role": "user", "content":
              f"Classify this headline into exactly one of: {', '.join(CATS)}, or none. Reply with the word only.\n{title}"}]})
            w = r.json()["content"][0]["text"].strip().lower()
            if w in CATS: return w
            if w == "none": return None
        except Exception as e:
            print("claude classify failed:", e, file=sys.stderr)
    for c, (_, rx) in CATS.items():
        if re.search(rx, title.lower()): return c
    return None

def prices():
    import yfinance as yf
    df = yf.download("BTC-USD", start="2014-09-01", progress=False, auto_adjust=True)
    s = df["Close"]
    if isinstance(s, pd.DataFrame): s = s.iloc[:, 0]
    s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
    return s.dropna()

def reactions(px, events):
    """base = close of day before event; r1 = close on event day; r7 = close 6 days later"""
    out = []
    for d, title in events:
        t = pd.Timestamp(d)
        try:
            base = px[:t - pd.Timedelta(days=1)].iloc[-1]
            if px.index[0] > t: continue
            r1 = px[:t].iloc[-1] / base - 1
            e7 = px[:t + pd.Timedelta(days=6)]
            r7 = e7.iloc[-1] / base - 1 if e7.index[-1] >= t + pd.Timedelta(days=5) else None
        except Exception:
            continue
        out.append({"d": d, "t": title, "r1": round(float(r1) * 100, 2), "r7": None if r7 is None else round(float(r7) * 100, 2)})
    return out

def stats(ev):
    a = pd.Series([e["r1"] for e in ev]); b = pd.Series([e["r7"] for e in ev if e["r7"] is not None])
    if a.empty: return None
    return {"n": int(a.size), "up1": round(float((a > 0).mean()) * 100), "m1": round(float(a.mean()), 2),
            "m7": round(float(b.mean()), 2) if not b.empty else None,
            "q25": round(float(a.quantile(.25)), 2), "q75": round(float(a.quantile(.75)), 2)}

def main():
    os.makedirs(OUT, exist_ok=True)
    old = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {"news": []}
    seen = {n["u"] for n in old["news"]}
    news = list(old["news"])
    for name, url in FEEDS:
        try:
            for e in feedparser.parse(url).entries[:25]:
                u, ti = e.get("link"), re.sub(r"\s+", " ", e.get("title", "")).strip()
                if not u or not ti or u in seen: continue
                seen.add(u)
                ts = e.get("published_parsed") or e.get("updated_parsed")
                iso = dt.datetime(*ts[:6]).isoformat() + "Z" if ts else dt.datetime.utcnow().isoformat() + "Z"
                news.append({"s": name, "ti": ti, "u": u, "z": iso, "c": classify(ti)})
        except Exception as ex:
            print("feed failed", name, ex, file=sys.stderr)
    news.sort(key=lambda n: n["z"], reverse=True)
    news = news[:300]
    ev_all = json.load(open(os.path.join(os.path.dirname(__file__), "events.json"), encoding="utf-8"))
    px = prices()
    cats = {}
    for c, (label, _) in CATS.items():
        ev = reactions(px, ev_all.get(c, []))
        cats[c] = {"label": label, "events": ev, "stats": stats(ev)}
    data = {"updated": dt.datetime.utcnow().isoformat() + "Z", "btc_last": round(float(px.iloc[-1]), 2), "cats": cats, "news": news}
    json.dump(data, open(STATE, "w", encoding="utf-8"), ensure_ascii=False)
    tg(news, old)
    print("ok", len(news), "news")

def tg(news, old):  # optional Telegram alert for new categorised headlines
    tok, chat = os.getenv("TELEGRAM_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (tok and chat): return
    oldu = {n["u"] for n in old["news"]}
    for n in [n for n in news if n["u"] not in oldu and n["c"]][:5]:
        requests.post(f"https://api.telegram.org/bot{tok}/sendMessage", timeout=20,
            json={"chat_id": chat, "text": f"{CATS[n['c']][0]}\n{n['ti']}\n{n['u']}"})

if __name__ == "__main__": main()
