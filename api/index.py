import hashlib
import json
import os
import threading
import time
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
import requests

PORTAL_URL = "http://tv.infomir.com.ua/stalker_portal/server/load.php"
BASE_PORTAL_ROOT = "http://tv.infomir.com.ua/stalker_portal/c/"
MAC_BASE = "00:1A:79:4B:2B:58"

app = FastAPI()

status_data = {
    "last_update": "Hali yangilanmagan",
    "total_channels": 0,
    "status": "Ishga tushmoqda...",
}

def get_session():
    print("get_session: сессия yaratilmoqda...")
    session = requests.Session()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like"
            " Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3"
        ),
        "X-User-Agent": "Model: MAG250; Link: WiFi",
        "Referer": "http://tv.infomir.com.ua/stalker_portal/c/index.html",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "close",
        "Pragma": "no-cache",
    }
    session.headers.update(headers)
    session.cookies.set("mac", MAC_BASE, domain="tv.infomir.com.ua")
    session.cookies.set("stb_lang", "en", domain="tv.infomir.com.ua")
    session.cookies.set("timezone", "Europe/London", domain="tv.infomir.com.ua")
    
    try:
        session.get("http://tv.infomir.com.ua/stalker_portal/c/", timeout=5)
        session.get("http://tv.infomir.com.ua/stalker_portal/c/xpcom.common.js", timeout=5)
        session.get("http://tv.infomir.com.ua/stalker_portal/c/version.js", timeout=5)
    except Exception:
        pass
        
    token = ""
    try:
        hs_url = f"{PORTAL_URL}?type=stb&action=handshake&token=&JsHttpRequest=1-xml"
        resp = session.get(hs_url, timeout=10)
        r = resp.json()
        token = r.get("js", {}).get("token", "")
        if token:
            session.cookies.set("token", token, domain="tv.infomir.com.ua")
            session.headers.update({"Authorization": f"Bearer {token}"})
            print(f"Handshake token olindi: {token}")
    except Exception as e:
        print(f"Handshake xatolik: {e}")
        
    metrics_data = json.dumps({
        "type": "stb",
        "model": "MAG254",
        "mac": MAC_BASE,
        "sn": "60975EB0B96B5",
        "uid": "F756469D36297E47B3D824E2401349951A7C7B2FEAF8EA0A4E189F3D486409C7",
        "random": "55d73479dcdee1da6b75ae413d56294d4112c3b2",
    })
    token_param = f"&token={token}" if token else ""
    prof_url = (
        f"{PORTAL_URL}?type=stb&action=get_profile&JsHttpRequest=1-xml&hd=1"
        f"{token_param}"
        "&ver=ImageDescription: 0.2.18-r23-250; ImageDate: Thu Sep 13 11:31:16 EEST 2018; PORTAL version: 5.3.0; API Version: JS API version: 343; STB API version: 146; Player Engine version: 0x58c"
        "&num_banks=2&sn=60975EB0B96B5&stb_type=MAG250&client_type=STB&image_version=218&video_out=hdmi"
        "&device_id=92C835BDAF9B3CB295615E79573FE0D16CBCD80F263B2FF9B3E5ABA34642959A"
        "&device_id2=92C835BDAF9B3CB295615E79573FE0D16CBCD80F263B2FF9B3E5ABA34642959A"
        "&signature=4C9E44B09FB8F6CBA62D251E676C0CE3DC8C2AF76A735935B44F2A043104534C"
        "&auth_second_step=1&hw_version=1.7-BD-00&not_valid_token=0"
        f"&metrics={metrics_data}"
        f"&hw_version_2=4cb1eea65ce8c612eddbf35e90b36519320c06df&timestamp={int(time.time())}&api_signature=262&prehash=30e4e07f76490d7a9fc88fae3347adc336cb6bee"
    )
    try:
        session.get(prof_url, timeout=10)
        session.get(f"{PORTAL_URL}?type=account_info&action=get_main_info&JsHttpRequest=1-xml", timeout=10)
    except Exception as e:
        print(f"Profile/Account xatolik: {e}")
        
    return session

def update_playlist():
    global status_data
    print("--- UPDATE_PLAYLIST BOSHLANDI ---")
    status_data["status"] = "Yangilanmoqda..."
    
    session = get_session()
    channels = []
    seen_cmds = set()

    channels_urls = [
        f"{PORTAL_URL}?type=itv&action=get_all_channels&JsHttpRequest=1-xml",
        f"{PORTAL_URL}?type=itv&action=get_all_channels&genre=*&JsHttpRequest=1-xml",
        f"{PORTAL_URL}?type=itv&action=get_all_channels&genre=0&JsHttpRequest=1-xml"
    ]

    for channels_url in channels_urls:
        try:
            print(f"So'rov yuborilmoqda: {channels_url}")
            channels_resp = session.get(channels_url, timeout=10)
            res_json = channels_resp.json()
            
            js_data = res_json.get("js", {})
            data = []
            
            if isinstance(js_data, list):
                data = js_data
            elif isinstance(js_data, dict):
                data = js_data.get("data", [])
                if not data and "channels" in js_data:
                    data = js_data.get("channels", [])
            
            if isinstance(data, list) and len(data) > 0:
                for ch in data:
                    cmd = ch.get("cmd", "")
                    if cmd and cmd not in seen_cmds:
                        seen_cmds.add(cmd)
                        channels.append(ch)
                if channels:
                    break
        except Exception as e:
            print(f"URL xatoligi ({channels_url}): {e}")

    print(f"Жами топилган уникал каналлар сони: {len(channels)}")

    channels_list = []
    for target_channel in channels:
        ch_name = target_channel.get("name", "Kanal")
        cmd = target_channel.get("cmd", "")
        timeshift = target_channel.get("timeshift", 0)
        if cmd:
            channels_list.append({
                "name": ch_name,
                "cmd": cmd,
                "timeshift": timeshift
            })

    temp_file = "playlist.tmp"
    final_file = "playlist.json"
    
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(channels_list, f, ensure_ascii=False, indent=4)
        
    if os.path.exists(final_file):
        os.remove(final_file)
    os.rename(temp_file, final_file)
    
    status_data["last_update"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    status_data["total_channels"] = len(channels_list)
    status_data["status"] = "Muvaffaqiyatli ishlayapti ✅" if len(channels_list) > 0 else "Kanal topilmadi ⚠️"
    print("--- UPDATE_PLAYLIST TUGADI ---")

def background_worker():
    while True:
        try:
            update_playlist()
        except Exception as e:
            print(f"BACKGROUND WORKER XATOLIGI: {e}")
        time.sleep(300)

@app.on_event("startup")
def startup_event():
    t = threading.Thread(target=background_worker, daemon=True)
    t.start()

@app.get("/", response_class=HTMLResponse)
def admin_panel():
    return f"""
    <!DOCTYPE html>
    <html lang="uz">
    <head>
        <meta charset="UTF-8">
        <title>IPTV Admin Panel</title>
        <style>
            body {{ font-family: Arial, sans-serif; background: #0f172a; color: #f8fafc; text-align: center; padding: 50px; }}
            .card {{ background: #1e293b; padding: 35px; border-radius: 12px; display: inline-block; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }}
            .badge {{ background: #22c55e; color: white; padding: 5px 12px; border-radius: 20px; font-weight: bold; }}
            a {{ color: #38bdf8; text-decoration: none; display: block; margin-top: 15px; font-size: 18px; }}
            a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>🚀 Infomir Stalker Proxy</h2>
            <p>Holati: <span class="badge">{status_data["status"]}</span></p>
            <p><b>Kanallar soni:</b> {status_data["total_channels"]} ta</p>
            <p><b>Oxirgi yangilangan vaqt:</b> {status_data["last_update"]}</p>
            <hr style="border: 0.5px solid #334155; margin: 20px 0;">
            <a href="/pl.m3u8" target="_blank">📥 M3U Playlist (/pl.m3u8)</a>
            <a href="/playlist.json" target="_blank" style="color: #94a3b8; font-size: 14px;">📄 JSON ni ko'rish (/playlist.json)</a>
        </div>
    </body>
    </html>
    """

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/playlist.json")
def download_json(request: Request):
    if os.path.exists("playlist.json"):
        with open("playlist.json", "r", encoding="utf-8") as f:
            channels = json.load(f)
        
        base_url = str(request.base_url).rstrip('/')
        result = []
        for index, ch in enumerate(channels):
            result.append({
                "name": ch["name"],
                "url": f"{base_url}/stream/{index}"
            })
        return result
    return {"error": "Hali playlist tayyor emas!"}, 404

@app.get("/pl.m3u8", response_class=PlainTextResponse)
def download_m3u8(request: Request):
    if not os.path.exists("playlist.json"):
        return "#EXTM3U\n# Xatolik: Playlist hali tayyorlanmadi"
    try:
        with open("playlist.json", "r", encoding="utf-8") as f:
            channels = json.load(f)
    except Exception:
        return "#EXTM3U\n# Xatolik: Playlistni o'qib bo'lmadi"
        
    base_url = str(request.base_url).rstrip('/')
    m3u_lines = ["#EXTM3U"]
    for index, ch in enumerate(channels):
        name = ch.get("name", "Kanal")
        timeshift = ch.get("timeshift", 0)
        stream_link = f"{base_url}/stream/{index}"
        
        tvg_shift_attr = f' tvg-shift="{timeshift}"' if timeshift else ''
        catchup_attr = ' catchup="default" catchup-days="3"' if timeshift else ''
        
        m3u_lines.append(f"#EXTINF:-1{tvg_shift_attr}{catchup_attr},{name}")
        m3u_lines.append(stream_link)
    return "\n".join(m3u_lines)

@app.get("/stream/{index}")
def proxy_stream(index: int):
    print(f"--- STREAM SO'ROVI KELDI: индекс {index} ---")
    if not os.path.exists("playlist.json"):
        return Response("Playlist topilmadi", status_code=404)
    
    try:
        with open("playlist.json", "r", encoding="utf-8") as f:
            channels = json.load(f)
        target = channels[index]
        cmd = target["cmd"]
    except Exception as e:
        return Response(f"Kanal topilmadi: {e}", status_code=404)

    session = get_session()
    stream_url = ""
    
    try:
        clean_cmd = cmd
        for prefix in ["ffmpeg ", "ch:ffrt ", "ffrt ", "ch:"]:
            if clean_cmd.startswith(prefix):
                clean_cmd = clean_cmd[len(prefix):].strip()
                
        link_url = f"{PORTAL_URL}?type=itv&action=create_link&cmd={requests.utils.quote(clean_cmd)}&JsHttpRequest=1-xml"
        link_res = session.get(link_url, timeout=10).json()
        
        stream_cmd = link_res.get("js", {}).get("cmd")
        if stream_cmd:
            stream_url = stream_cmd
            for prefix in ["ffmpeg ", "ch:ffrt ", "ffrt ", "ch:"]:
                if stream_url.startswith(prefix):
                    stream_url = stream_url[len(prefix):].strip()
    except Exception as e:
        print(f"Create link xatolik (stream): {e}")

    if not stream_url and "http" in cmd:
        stream_url = cmd
        for prefix in ["ffmpeg ", "ch:ffrt ", "ffrt ", "ch:"]:
            if stream_url.startswith(prefix):
                stream_url = stream_url[len(prefix):].strip()

    if stream_url and "token=" not in stream_url:
        session_token = session.cookies.get("token")
        if session_token:
            separator = "&" if "?" in stream_url else "?"
            stream_url = f"{stream_url}{separator}token={session_token}"

    print(f"Йўналтирилаётган янги тоза ссылка: {stream_url}")
    
    if not stream_url:
        return Response("Stream URL яратиб бўлмади", status_code=500)

    return RedirectResponse(url=stream_url, status_code=302)
