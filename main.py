import hashlib
import json
import os
import threading
import time
from urllib.parse import urlparse, quote, unquote
from fastapi import FastAPI, Response, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
import requests

# ==============================================================================
# НАСТРОЙКИ ПОДКЛЮЧЕНИЯ И УСТРОЙСТВА
# ==============================================================================
PORTAL_BASE = "http://91.215.188.161"
PORTAL_URL = f"{PORTAL_BASE}/stalker_portal/server/load.php"

MAC_BASE = "00:1A:79:39:80:9C"
SN_BASE = "420428156A9E4"
UID_BASE = "30DAC1D60AD80CA2303756C2B420BA2C1D3614520B7CA5D2AA00241598AE9055"
DEVICE_ID = "C6E50B24774620673221A09FDF75789A8B76E581A06073166E126D0AE3F804E6"

SECRET_KEY = "000"
TELEGRAM_GROUP_URL = "https://t.me/+2lWVU6CKQsVkMWRi"  
STUB_VIDEO_URL = "https://raw.githubusercontent.com/Waswas777/video2/refs/heads/main/playlist.m3u8"

PORTAL_DOMAIN = urlparse(PORTAL_BASE).netloc

# ==============================================================================
# СПИСКИ БЛОКИРОВОК (BANNED IP / PREFIXES)
# ==============================================================================
BANNED_IPS = {        
    "5.253.66.62", "23.106.253.18", "23.106.249.56", "31.3.156.64", "38.180.180.126", "46.150.71.146", "91.214.82.125", "109.86.19.135", "217.12.223.190", "188.233.60.20",
    "91.195.172.249", "149.102.240.138", "91.194.168.20", "91.195.172.241", "91.195.172.240", "88.218.92.126", "46.150.71.235", "194.44.26.199", "130.0.235.254",
    "46.96.27.147", "194.44.46.82", "213.109.230.149", "77.239.161.129", "192.162.33.80", "192.162.33.73", "46.150.74.185", "195.64.183.231", "62.233.43.122",
    "176.108.27.175", "91.123.158.251", "46.172.86.196", "213.5.196.234", "217.196.164.251", "195.64.183.237", "37.214.2.184", "176.105.213.173", "176.105.213.129",    
    "91.194.168.40", "159.194.214.13", "217.107.106.106", "91.195.172.250", "78.111.155.199", "95.83.134.76", "178.120.4.234", "46.53.134.27", "178.150.186.100", 
    "46.150.94.187", "45.12.26.251", "80.91.179.217", "85.198.107.131", "176.119.83.194", "46.150.90.146", "85.249.245.196", "176.105.213.137", "77.120.163.216",  
    "109.172.30.88", "178.137.26.58", "143.244.45.242", "194.44.57.68", "143.244.46.242", "188.239.94.135", "82.208.115.42", "88.65.191.89", "212.66.41.73",
    "178.207.19.26", "158.173.154.155", "89.125.113.17", "46.150.71.243", "94.231.176.6", "176.210.26.190", "178.91.18.50"
}

BANNED_PREFIXES = (
    "2a09:bac5:", "2a02:3032:", "2a09:bac1:", "2a12:bec4:", "2a01:e5c0:", "2a02:2378:",
    "2a02:4780:", "2001:49f0:", "2a14:a087:", "2001:4f8:", "2001:ac8:", "2a03:d000:",
    "2001:16b8:", "2a0e:d604:", "2a06:98c0:", "2001:4f9:", "51.158.201.", "149.154.161.",
    "94.158.58.", "81.19.141.", "93.152.224.", "80.66.72.", "91.92.33.", "5.255."
)

def is_ip_banned(request: Request) -> bool:
    client_ip = request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for")
    if not client_ip and request.client:
        client_ip = request.client.host    
    if not client_ip:
        return False        
    client_ip = client_ip.split(",")[0].strip()
    if client_ip in BANNED_IPS or client_ip.startswith(BANNED_PREFIXES):
        return True        
    return False

app = FastAPI()

status_data = {
    "last_update": "Hali yangilanmagan",
    "total_channels": 0,
    "status": "Ishga tushmoqda...",
}

global_session = None
session_created_time = 0

def get_session(force_new=False):
    global global_session, session_created_time    
    if not force_new and global_session and (time.time() - session_created_time) < 300:
        return global_session
        
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
        "X-User-Agent": "Model: MAG250; Link: WiFi",
        "Referer": f"{PORTAL_BASE}/stalker_portal/c/index.html",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "close",
        "Pragma": "no-cache",
    }
    session.headers.update(headers)
    session.cookies.set("mac", MAC_BASE, domain=PORTAL_DOMAIN)
    session.cookies.set("stb_lang", "en", domain=PORTAL_DOMAIN)
    session.cookies.set("timezone", "Europe/London", domain=PORTAL_DOMAIN)
    
    try:
        session.get(f"{PORTAL_BASE}/stalker_portal/c/", timeout=5)
    except Exception:
        pass

    token = ""
    random_val = "42013928bec8c82be1b0d20a86bfaeedc52e4e68"
    try:
        hs_url = f"{PORTAL_URL}?type=stb&action=handshake&token=&JsHttpRequest=1-xml"
        r = session.get(hs_url, timeout=10).json()
        js_data = r.get("js", {})
        token = js_data.get("token", "")
        random_val = js_data.get("random", random_val)        
        if token:
            session.cookies.set("token", token, domain=PORTAL_DOMAIN)
            session.headers.update({"Authorization": f"Bearer {token}"})
    except Exception:
        pass

    metrics_data = json.dumps({
        "type": "stb",
        "model": "MAG254",
        "mac": MAC_BASE,
        "sn": SN_BASE,
        "uid": UID_BASE,
        "random": random_val,
    })
    
    token_param = f"&token={token}" if token else ""
    prof_url = (
        f"{PORTAL_URL}?type=stb&action=get_profile&JsHttpRequest=1-xml&hd=1"
        f"{token_param}"
        "&ver=ImageDescription: 0.2.18-r23-250; ImageDate: Thu Sep 13 11:31:16 EEST 2018; PORTAL version: 5.3.0; API Version: JS API version: 343; STB API version: 146; Player Engine version: 0x58c"
        f"&num_banks=2&sn={SN_BASE}&stb_type=MAG250&client_type=STB&image_version=218&video_out=hdmi"
        f"&device_id={DEVICE_ID}"
        f"&device_id2={DEVICE_ID}"
        "&signature=8093B01764649C3D8B202489B8F72CB47BA2D7B1CCAE5988013AEE59820B5689"
        "&auth_second_step=1&hw_version=1.7-BD-00&not_valid_token=0"
        f"&metrics={metrics_data}"
        f"&hw_version_2=61c3ee11415738e10b26e47bd195df7e23f8b1a0&timestamp={int(time.time())}&api_signature=262&prehash=501706164d318322b9196c8038c76d3233468725"
    )
    
    try:
        session.get(prof_url, timeout=10)
    except Exception:
        pass

    global_session = session
    session_created_time = time.time()
    return session

def fetch_channels_data(session):
    genres_map = {}
    try:
        genres_url = f"{PORTAL_URL}?type=itv&action=get_genres&JsHttpRequest=1-xml"
        g_resp = session.get(genres_url, timeout=10).json()
        g_data = g_resp.get("js", [])
        if isinstance(g_data, list):
            for g in g_data:
                gid = g.get("id")
                gtitle = g.get("title", "Boshqa")
                if gid is not None:
                    genres_map[str(gid)] = gtitle
    except Exception:
        pass

    channels = []
    seen_cmds = set()

    try:
        channels_url = f"{PORTAL_URL}?type=itv&action=get_all_channels&JsHttpRequest=1-xml"
        channels_res = session.get(channels_url, timeout=10).json()
        data = channels_res.get("js", {}).get("data", [])
        if isinstance(data, list):
            for ch in data:
                cmd = ch.get("cmd", "")
                if cmd and cmd not in seen_cmds:
                    seen_cmds.add(cmd)
                    channels.append(ch)
    except Exception:
        pass

    if genres_map:
        for gid in genres_map.keys():
            page = 1
            while True:
                sub_url = (
                    f"{PORTAL_URL}?type=itv&action=get_ordered_list"
                    f"&genre={gid}&sortby=number&order=asc&hd=0&fav=0&not_my_genres=0"
                    f"&p={page}&JsHttpRequest=1-xml"
                )
                try:
                    sub_resp = session.get(sub_url, timeout=5).json()
                    js_content = sub_resp.get("js", {})
                    sub_data = js_content.get("data", []) if isinstance(js_content, dict) else (js_content if isinstance(js_content, list) else [])
                    if not sub_data:
                        break
                    added = 0
                    for ch in sub_data:
                        cmd = ch.get("cmd", "")
                        if cmd and cmd not in seen_cmds:
                            seen_cmds.add(cmd)
                            channels.append(ch)
                            added += 1
                    if len(sub_data) < 10 or added == 0 or page > 50:
                        break
                    page += 1
                except Exception:
                    break

    return channels, genres_map

def update_playlist():
    global status_data
    status_data["status"] = "Yangilanmoqda..."
    session = get_session(force_new=False)
    channels, genres_map = fetch_channels_data(session)
    
    if not channels:
        session = get_session(force_new=True)
        channels, genres_map = fetch_channels_data(session)

    channels_list = []
    for ch in channels:
        ch_name = ch.get("name", "Kanal")
        cmd = ch.get("cmd", "")        
        logo = ch.get("logo", "")
        if logo and not logo.startswith("http"):
            logo = f"{PORTAL_BASE}/stalker_portal/misc/logos/{logo}"
        genre_id = str(ch.get("tv_genre_id", ch.get("genre_id", "")))
        group_title = genres_map.get(genre_id, "Umumiy")
        if cmd:
            channels_list.append({
                "name": ch_name,
                "cmd": cmd,
                "group": group_title,
                "logo": logo
            })

    if channels_list:
        with open("playlist.json", "w", encoding="utf-8") as f:
            json.dump(channels_list, f, ensure_ascii=False, indent=4)

    status_data["last_update"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    status_data["total_channels"] = len(channels_list)
    status_data["status"] = "Muvaffaqiyatli"

def get_or_create_playlist():
    if not os.path.exists("playlist.json") or (time.time() - os.path.getmtime("playlist.json") > 86400):
        try:
            update_playlist()
        except Exception:
            pass
            
    if os.path.exists("playlist.json"):
        try:
            with open("playlist.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

@app.get("/", response_class=RedirectResponse)
def root_redirect(request: Request):
    if is_ip_banned(request):
        return RedirectResponse(url=STUB_VIDEO_URL, status_code=302)
    return RedirectResponse(url=TELEGRAM_GROUP_URL, status_code=302)

@app.get("/playlist.json")
def download_json(request: Request, key: str = ""):
    if is_ip_banned(request) or key != SECRET_KEY:
        return [{"name": "Reklama", "group": "Stub", "logo": "", "url": STUB_VIDEO_URL}]

    base_url = str(request.base_url).rstrip('/')
    channels = get_or_create_playlist()
    
    result = []
    for ch in channels:
        cmd_encoded = quote(ch["cmd"], safe="")
        result.append({
            "name": ch["name"],
            "group": ch.get("group", "Umumiy"),
            "logo": ch.get("logo", ""),
            "url": f"{base_url}/play?cmd={cmd_encoded}&key={SECRET_KEY}"
        })
    return result

@app.get("/pl.m3u8", response_class=PlainTextResponse)
@app.get("/playlist.m3u8", response_class=PlainTextResponse)
def download_m3u8(request: Request, key: str = ""):
    headers = {"Content-Disposition": "attachment; filename=playlist.m3u8"}    
    if is_ip_banned(request) or key != SECRET_KEY:
        content = f"#EXTM3U\n#EXTINF:-1 tvg-name=\"Reklama\" group-title=\"Stub\",Reklama\n{STUB_VIDEO_URL}"
        return PlainTextResponse(content, headers=headers)

    base_url = str(request.base_url).rstrip('/')
    channels = get_or_create_playlist()

    m3u_lines = ["#EXTM3U"]
    for ch in channels:
        name = ch.get("name", "Kanal")
        group = ch.get("group", "Umumiy")
        cmd_encoded = quote(ch.get("cmd", ""), safe="")
        stream_link = f"{base_url}/play?cmd={cmd_encoded}&key={SECRET_KEY}"        
        m3u_lines.append(f"#EXTINF:-1 tvg-name=\"{name}\" group-title=\"{group}\",{name}")
        m3u_lines.append(stream_link)

    return PlainTextResponse("\n".join(m3u_lines), headers=headers)

@app.get("/play")
def play_stream(cmd: str, request: Request, key: str = ""):
    if is_ip_banned(request) or key != SECRET_KEY:
        return RedirectResponse(url=STUB_VIDEO_URL, status_code=302)

    session = get_session(force_new=True)
    stream_url = ""    

    # Очищаем префиксы из команды
    clean_cmd = cmd
    for prefix in ["ffmpeg ", "ch:ffrt ", "ffrt ", "ch:"]:
        if clean_cmd.startswith(prefix):
            clean_cmd = clean_cmd[len(prefix):].strip()

    # Извлекаем числовой ID из виртуальных путей типа http:///ch/1277
    channel_id = ""
    if "/ch/" in clean_cmd:
        parts = clean_cmd.split("/ch/")
        if len(parts) > 1:
            channel_id = parts[-1].strip()

    # Формируем список вариантов для запроса к create_link (порталы бывают капризными к формату)
    cmds_to_try = [clean_cmd]
    if channel_id:
        cmds_to_try.insert(0, channel_id)  # Пробуем чистый ID в первую очередь
        cmds_to_try.append(f"ch:{channel_id}")
        cmds_to_try.append(f"http:///ch/{channel_id}")

    # Перебираем варианты, пока портал не отдаст реальный адрес потока
    for test_cmd in cmds_to_try:
        for attempt in range(2):
            try:
                link_url = f"{PORTAL_URL}?type=itv&action=create_link&cmd={requests.utils.quote(test_cmd)}&JsHttpRequest=1-xml"
                resp = session.get(link_url, timeout=10)
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
                    session = get_session(force_new=True)
                    time.sleep(0.5)
        
        # Если нашли нормальную ссылку, прекращаем перебор
        if stream_url and not stream_url.startswith("http:///ch/") and "://" in stream_url:
            break

    # Исправляем формат, если ссылка начинается с усеченного http:///
    if stream_url.startswith("http:///"):
        stream_url = stream_url.replace("http:///", f"{PORTAL_BASE}/")
    elif stream_url.startswith("/"):
        stream_url = f"{PORTAL_BASE}{stream_url}"

    # Если портал не вернул ссылку через create_link, пробуем использовать чистый URL если он есть
    if not stream_url or "://" not in stream_url or stream_url.startswith("http:///ch/"):
        if "://" in clean_cmd and not clean_cmd.startswith("http:///ch/"):
            stream_url = clean_cmd

    # Добавляем свежий токен сессии к ссылке медиасервера
    if stream_url and "token=" not in stream_url:
        session_token = session.cookies.get("token")
        if session_token:
            separator = "&" if "?" in stream_url else "?"
            stream_url = f"{stream_url}{separator}token={session_token}"

    if not stream_url or stream_url.startswith("http:///ch/"):
        return Response("Kanalni ochib bo'lmadi: медиасервер не вернул ссылку", status_code=500)

    return RedirectResponse(url=stream_url, status_code=302)
