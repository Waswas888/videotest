import json
import os
import time
from fastapi import FastAPI, Response, Request
from fastapi.responses import PlainTextResponse, RedirectResponse, JSONResponse
import requests

PORTAL_URL = "http://app.ttt5.me/stalker_portal/server/load.php"
PORTAL_BASE = "http://app.ttt5.me"

MAC_BASE = "00:1A:79:67:D2:D4"
SN_BASE = "E64E3F8B8C092"
UID_BASE = "D19D40486081779F90A66F60EB9836A1D2A63ED493961445338D76A01F31F6D4"
DEVICE_ID = "20FB21AA77D58B6DC9200101EED68B82C4350765274BC3373EA9758DC8F3EA9E"

SECRET_KEY = "000"
TELEGRAM_GROUP_URL = "https://t.me/+2lWVU6CKQsVkMWRi"

app = FastAPI()

def create_fresh_session():
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
        "X-User-Agent": "Model: MAG250; Link: WiFi",
        "Referer": "http://app.ttt5.me/stalker_portal/c/index.html",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "close",
        "Pragma": "no-cache",
    }
    session.headers.update(headers)
    session.cookies.set("mac", MAC_BASE, domain="app.ttt5.me")
    session.cookies.set("stb_lang", "en", domain="app.ttt5.me")
    session.cookies.set("timezone", "Europe/London", domain="app.ttt5.me")

    try:
        session.get("http://app.ttt5.me/stalker_portal/c/", timeout=5)
    except Exception:
        pass

    token = ""
    random_val = "4bad200fb83418a95c33ea688d5b3f6e66a8428b"
    try:
        hs_url = "http://app.ttt5.me/stalker_portal/server/load.php?type=stb&action=handshake&token=&JsHttpRequest=1-xml"
        r = session.get(hs_url, timeout=8).json()
        js_data = r.get("js", {})
        token = js_data.get("token", "")
        random_val = js_data.get("random", random_val)
        if token:
            session.cookies.set("token", token, domain="app.ttt5.me")
            session.headers.update({"Authorization": f"Bearer {token}"})
    except Exception:
        pass

    metrics_data = json.dumps({
        "type": "stb", "model": "MAG254", "mac": MAC_BASE, "sn": SN_BASE, "uid": UID_BASE, "random": random_val
    })
    token_param = f"&token={token}" if token else ""
    prof_url = (
        f"{PORTAL_URL}?type=stb&action=get_profile&JsHttpRequest=1-xml&hd=1{token_param}"
        f"&sn={SN_BASE}&stb_type=MAG250&client_type=STB&image_version=218&video_out=hdmi"
        f"&device_id={DEVICE_ID}&device_id2={DEVICE_ID}"
        f"&metrics={metrics_data}&timestamp={int(time.time())}"
    )
    try:
        session.get(prof_url, timeout=8)
    except Exception:
        pass

    return session

def fetch_channels(session):
    channels = []
    try:
        channels_url = f"{PORTAL_URL}?type=itv&action=get_all_channels&JsHttpRequest=1-xml"
        channels_res = session.get(channels_url, timeout=8).json()
        data = channels_res.get("js", {}).get("data", [])
        if isinstance(data, list):
            channels = data
    except Exception:
        pass

    if not channels:
        try:
            list_url = f"{PORTAL_URL}?type=itv&action=get_ordered_list&genre=*&sortby=number&order=asc&hd=0&fav=0&not_my_genres=0&JsHttpRequest=1-xml"
            res = session.get(list_url, timeout=8).json()
            data = res.get("js", {}).get("data", [])
            if not data and isinstance(res.get("js"), list):
                data = res.get("js", [])
            if isinstance(data, list):
                channels = data
        except Exception:
            pass
    return channels

@app.get("/")
def root_redirect():
    return RedirectResponse(url=TELEGRAM_GROUP_URL, status_code=302)

@app.get("/api/pl.m3u8", response_class=PlainTextResponse)
@app.get("/api/playlist.m3u8", response_class=PlainTextResponse)
def download_m3u8(request: Request, key: str = ""):
    headers = {"Content-Disposition": "attachment; filename=playlist.m3u8"}
    base_url = str(request.base_url).rstrip('/')

    if key != SECRET_KEY:
        content = '#EXTM3U\n#EXTINF:-1,Xato kalit\nhttps://github.com/brawltop8599-boop/ads-stub/raw/refs/heads/main/v.mp4'
        return PlainTextResponse(content, headers=headers)

    session = create_fresh_session()
    channels = fetch_channels(session)

    if not channels:
        return PlainTextResponse("#EXTM3U\n# Xatolik: Kanal topilmadi", headers=headers)

    m3u_lines = ["#EXTM3U"]
    for index, ch in enumerate(channels):
        name = ch.get("name", "Kanal")
        cmd = ch.get("cmd", "")
        stream_link = f"{base_url}/api/ch/{index}?key={SECRET_KEY}&cmd={requests.utils.quote(cmd)}"
        m3u_lines.append(f'#EXTINF:-1,{name}')
        m3u_lines.append(stream_link)

    return PlainTextResponse("\n".join(m3u_lines), headers=headers)

@app.get("/api/ch/{index}")
def proxy_stream(index: int, cmd: str = "", key: str = ""):
    if key != SECRET_KEY or not cmd:
        return RedirectResponse(url="https://github.com/brawltop8599-boop/ads-stub/raw/refs/heads/main/v.mp4", status_code=302)

    session = create_fresh_session()
    stream_url = ""

    for attempt in range(2):
        try:
            clean_cmd = cmd
            for prefix in ["ffmpeg ", "ch:ffrt ", "ffrt ", "ch:"]:
                if clean_cmd.startswith(prefix):
                    clean_cmd = clean_cmd[len(prefix):].strip()

            link_url = f"{PORTAL_URL}?type=itv&action=get_link&cmd={requests.utils.quote(clean_cmd)}&JsHttpRequest=1-xml"
            resp = session.get(link_url, timeout=8)
            if not resp.text.strip():
                raise ValueError("Bo'sh javob")

            link_res = resp.json()
            stream_cmd = link_res.get("js", {}).get("cmd")
            if stream_cmd:
                stream_url = stream_cmd
                for prefix in ["ffmpeg ", "ch:ffrt ", "ffrt ", "ch:"]:
                    if stream_url.startswith(prefix):
                        stream_url = stream_url[len(prefix):].strip()
                break
        except Exception:
            if attempt == 0:
                session = create_fresh_session()
                time.sleep(0.3)

    if not stream_url or "://" not in stream_url:
        stream_url = cmd
        for prefix in ["ffmpeg ", "ch:ffrt ", "ffrt ", "ch:"]:
            if stream_url.startswith(prefix):
                stream_url = stream_url[len(prefix):].strip()

    if stream_url.startswith("/"):
        stream_url = f"{PORTAL_BASE}{stream_url}"

    if stream_url and "token=" not in stream_url:
        tkn = session.cookies.get("token")
        if tkn:
            sep = "&" if "?" in stream_url else "?"
            stream_url = f"{stream_url}{sep}token={tkn}"

    if not stream_url:
        return Response("URL yaratib bo'lmadi", status_code=500)

    return RedirectResponse(url=stream_url, status_2=302)
