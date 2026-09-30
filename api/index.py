import hashlib
import json
import os
import threading
import time
from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
import requests
PORTAL_URL = "http://tv.redmax.tv/stalker_portal/server/load.php"
BASE_PORTAL_ROOT = "http://tv.redmax.tv/stalker_portal/c/"
STREAM_BASE_HOST = "http://stream.redmax.tv/"
MAC_BASE = "00:1A:79:00:02:FE"
BASE_PROXY_URL = "https://stream-tv-digital.hf.space"
app = FastAPI()
status_data = {
    "last_update": "Hali yangilanmagan",
    "total_channels": 0,
    "status": "Ishga tushmoqda...",
}
def get_session():
    session = requests.Session()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like"
            " Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3"
        ),
        "X-User-Agent": "Model: MAG250; Link: WiFi",
        "Referer": "http://tv.redmax.tv/stalker_portal/c/index.html",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "close",
        "Pragma": "no-cache",
    }
    session.headers.update(headers)
    session.cookies.set("mac", MAC_BASE, domain="tv.redmax.tv")
    session.cookies.set("stb_lang", "en", domain="tv.redmax.tv")
    session.cookies.set("timezone", "Europe/London", domain="tv.redmax.tv")    
    try:
        session.get("http://tv.redmax.tv/stalker_portal/c/", timeout=5)
        session.get("http://tv.redmax.tv/stalker_portal/c/version.js", timeout=5)
    except Exception:
        pass        
    token = ""
    try:
        hs_url = f"{PORTAL_URL}?type=stb&action=handshake&token=&JsHttpRequest=1-xml"
        resp = session.get(hs_url, timeout=10)
        r = resp.json()
        token = r.get("js", {}).get("token", "")
        if token:
            session.cookies.set("token", token, domain="tv.redmax.tv")
            session.headers.update({"Authorization": f"Bearer {token}"})
    except Exception:
        pass        
    metrics_data = json.dumps({
        "type": "stb",
        "model": "MAG254",
        "mac": MAC_BASE,
        "sn": "AFDDBB900DAC7",
        "uid": "1790027FB626094E452F3A04C2527AC60571CEE93E1FD5DE5C4991BA634128C6",
        "random": "",
    })
    token_param = f"&token={token}" if token else ""
    prof_url = (
        f"{PORTAL_URL}?type=stb&action=get_profile&JsHttpRequest=1-xml&hd=1"
        f"{token_param}"
        "&ver=ImageDescription: 0.2.18-r23-250; ImageDate: Thu Sep 13 11:31:16 EEST 2018; PORTAL version: 5.3.0; API Version: JS API version: 343; STB API version: 146; Player Engine version: 0x58c"
        "&num_banks=2&sn=AFDDBB900DAC7&stb_type=MAG250&client_type=STB&image_version=218&video_out=hdmi"
        "&device_id=99C6BE2AE772CC6660BE59B7AA0CD132C1463315C7FB1611518D6C3CCD4F0CE2"
        "&device_id2=99C6BE2AE772CC6660BE59B7AA0CD132C1463315C7FB1611518D6C3CCD4F0CE2"
        "&signature=F815A102A114ACF1890EF21CAB0D11451C5732B6FE3A253AC4A26239C0CBD9AF"
        "&auth_second_step=1&hw_version=1.7-BD-00&not_valid_token=0"
        f"&metrics={metrics_data}"
        f"&hw_version_2=aa9eff686503b38e40ac84c5a469d92cf15adee3&timestamp={int(time.time())}&api_signature=262&prehash=d9b973e8083c84bd1a68a33147cdae39b605acc7"
    )
    try:
        session.get(prof_url, timeout=10)
        session.get(f"{PORTAL_URL}?type=account_info&action=get_main_info&JsHttpRequest=1-xml", timeout=10)
    except Exception:
        pass        
    return session
def update_playlist():
    global status_data
    status_data["status"] = "Yangilanmoqda..."    
    session = get_session()
    channels = []
    seen_cmds = set()
    genres = ["" , "*", "0"] 
    try:
        genres_url = f"{PORTAL_URL}?type=itv&action=get_genres&JsHttpRequest=1-xml"
        genres_resp = session.get(genres_url, timeout=10)
        genres_json = genres_resp.json()
        js_genres = genres_json.get("js", [])
        if isinstance(js_genres, list):
            for g in js_genres:
                g_id = g.get("id")
                if g_id is not None and str(g_id) not in [str(x) for x in genres]:
                    genres.append(str(g_id))
    except Exception:
        pass
    for genre in genres:
        channels_urls = [
            f"{PORTAL_URL}?type=itv&action=get_all_channels&genre={genre}&JsHttpRequest=1-xml",
            f"{PORTAL_URL}?type=itv&action=get_all_channels&genre={genre}&p=1&JsHttpRequest=1-xml"
        ]        
        for channels_url in channels_urls:
            try:
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
                    added_count = 0
                    for ch in data:
                        cmd = ch.get("cmd", "")
                        if cmd and cmd not in seen_cmds:
                            seen_cmds.add(cmd)
                            channels.append(ch)
                            added_count += 1
                    if added_count > 0:
                        break
            except Exception:
                continue
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
    status_data["status"] = "Muvaffaqiyatli" if len(channels_list) > 0 else "Kopilmadi"
    print(f"Pangilandi: {len(channels_list)} topildi.")    
def background_worker():
    while True:
        try:
            update_playlist()
        except Exception as e:
            print(f"Background worker xatoligi: {e}")
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
        <title>Admin Panel</title>
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
            <h2>Admin Panel</h2>
            <p>Holati: <span class="badge">{status_data["status"]}</span></p>
            <p><b>Kanallar soni:</b> {status_data["total_channels"]} ta</p>
            <p><b>Oxirgi yangilangan vaqt:</b> {status_data["last_update"]}</p>
            <hr style="border: 0.5px solid #334155; margin: 20px 0;">
            <a href="https://stream-tv-new-kino.hf.space" target="_blank">ADMIN VXOD</a>
        </div>
    </body>
    </html>
    """
@app.get("/health")
def health_check():
    return {"status": "ok"}
@app.get("/playlist.json")
def download_json():
    if os.path.exists("playlist.json"):
        with open("playlist.json", "r", encoding="utf-8") as f:
            channels = json.load(f)
        result = []
        for index, ch in enumerate(channels):
            result.append({
                "name": ch["name"],
                "url": f"{BASE_PROXY_URL}/stream/{index}"
            })
        return result
    return {"error": "Hali playlist tayyor emas!"}, 404
@app.get("/pl.m3u8", response_class=PlainTextResponse)
def download_m3u8():
    if not os.path.exists("playlist.json"):
        return "#EXTM3U\n# Xatolik: Playlist hali tayyorlanmadi"
    try:
        with open("playlist.json", "r", encoding="utf-8") as f:
            channels = json.load(f)
    except Exception:
        return "#EXTM3U\n# Xatolik: Playlistni o'qib bo'lmadi"       
    m3u_lines = ["#EXTM3U"]
    for index, ch in enumerate(channels):
        name = ch.get("name", "Kanal")
        timeshift = ch.get("timeshift", 0)
        stream_link = f"{BASE_PROXY_URL}/stream/{index}"        
        tvg_shift_attr = f' tvg-shift="{timeshift}"' if timeshift else ''
        catchup_attr = ' catchup="default" catchup-days="3"' if timeshift else ''        
        m3u_lines.append(f"#EXTINF:-1{tvg_shift_attr}{catchup_attr},{name}")
        m3u_lines.append(stream_link)
    return "\n".join(m3u_lines)
@app.get("/stream/{index}")
def proxy_stream(index: int):
    if not os.path.exists("playlist.json"):
        return Response("Playlist topilmadi", status_code=404)    
    try:
        with open("playlist.json", "r", encoding="utf-8") as f:
            channels = json.load(f)
        target = channels[index]
        cmd = target["cmd"]
    except Exception as e:
        return Response(f"Kopilmadi: {e}", status_code=404)
    session = get_session()
    stream_url = ""    
    try:
        clean_cmd = cmd
        for prefix in ["ffmpeg ", "ch:ffrt ", "ffrt ", "ch:"]:
            if clean_cmd.startswith(prefix):
                clean_cmd = clean_cmd[len(prefix):].strip()                
        link_url = f"{PORTAL_URL}?type=itv&action=create_link&cmd={requests.utils.quote(clean_cmd)}&JsHttpRequest=1-xml"
        link_res = session.get(link_url, timeout=10).json()        
        stream_cmd = link_res.get("js", {}).get("cmd") or link_res.get("js", {}).get("url") or link_res.get("cmd", "")        
        for prefix in ["ffrt3 ", "ffrt2 ", "ffrt ", "ffmpeg ", "ch:ffrt ", "ch:"]:
            if stream_cmd.startswith(prefix):
                stream_cmd = stream_cmd[len(prefix):].strip()
        if "http://" in stream_cmd[7:]:
            stream_cmd = stream_cmd.split("http://")[-1]
            stream_cmd = "http://" + stream_cmd
        elif "https://" in stream_cmd[8:]:
            stream_cmd = stream_cmd.split("https://")[-1]
            stream_cmd = "https://" + stream_cmd
        if stream_cmd and not stream_cmd.startswith("http://") and not stream_cmd.startswith("https://"):
            if stream_cmd.startswith("/"):
                stream_cmd = stream_cmd[1:]
            stream_url = STREAM_BASE_HOST + stream_cmd
        elif stream_cmd.startswith("http://") or stream_cmd.startswith("https://"):
            stream_url = stream_cmd
    except Exception:
        pass
    if not stream_url and "http" in cmd:
        stream_url = cmd
        for prefix in ["ffmpeg ", "ch:ffrt ", "ffrt ", "ch:"]:
            if stream_url.startswith(prefix):
                stream_url = stream_url[len(prefix):].strip()   
    if not stream_url:
        return Response("яратиб бўлмади", status_code=500)        
    return RedirectResponse(url=stream_url, status_code=302)
