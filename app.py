const PORTAL_URL = "http://tv.infomir.com.ua/stalker_portal/server/load.php";
const MAC = "00:1A:79:01:B7:F2";
const SN = "10F04CA4A203D";
const UID = "C634CD32DABEE9478F7451F40762195D1A7C31FA92B8232D099563C494438E6";
const RANDOM = "d369892c2bef39532a486936fd14e38b1b55c88d";

// Ссылки для неавторизованных пользователей
const TELEGRAM_GROUP = "https://t.me/+2lWVU6CKQsVkMWRi";
const FALLBACK_VIDEO = "https://github.com/brawltop8599-boop/ads-stub/raw/refs/heads/main/v.mp4?password=TvZaTak";

let cachedChannels = [];
let lastUpdate = "Hali yangilanmagan";

async function createStalkerSession() {
    const headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
        "X-User-Agent": "Model: MAG250; Link: WiFi",
        "Referer": "http://tv.infomir.com.ua/stalker_portal/c/index.html",
        "Accept": "*/*",
        "Pragma": "no-cache",
        "Cookie": `mac=${MAC}; stb_lang=en; timezone=Europe/London`
    };

    let token = "";
    try {
        const hsUrl = `${PORTAL_URL}?type=stb&action=handshake&token=&JsHttpRequest=1-xml`;
        const hsRes = await fetch(hsUrl, { headers, cf: { cacheTtl: 0 } });
        const text = await hsRes.text();
        
        let hsData = {};
        try { hsData = JSON.parse(text); } catch (err) {}
        
        token = hsData.js?.token || "";

        if (token) {
            headers["Authorization"] = `Bearer ${token}`;
            headers["Cookie"] += `; token=${token}`;
        }

        const timestamp = Math.floor(Date.now() / 1000);
        const metrics = JSON.stringify({ type: "stb", model: "MAG254", mac: MAC, sn: SN, uid: UID, random: RANDOM });
        const tokenParam = token ? `&token=${token}` : "";
        
        const profUrl = `${PORTAL_URL}?type=stb&action=get_profile&JsHttpRequest=1-xml&hd=1${tokenParam}&ver=ImageDescription: 0.2.18-r23-250; PORTAL version: 5.3.0&sn=${SN}&stb_type=MAG250&client_type=STB&image_version=218&video_out=hdmi&device_id=26C76ACC431FE84F89FCC263B6C5EFAC6EB7979F57DAA31B5C5D331281CC53C7&device_id2=26C76ACC431FE84F89FCC263B6C5EFAC6EB7979F57DAA31B5C5D331281CC53C7&signature=0D6BF04AEEEC15250D32BD26AD91ECEBF2ED012D20FBB2092445DDC3D7AEB1A8&auth_second_step=1&hw_version=1.7-BD-008&metrics=${encodeURIComponent(metrics)}&hw_version_2=5abd8d44284f3e647983712847d7cab787fda6d9&timestamp=${timestamp}&api_signature=262&prehash=12ac94036712bcd703594edd6d22030b3203b5b7`;
        
        await fetch(profUrl, { headers, cf: { cacheTtl: 0 } });
    } catch (e) {}
    return { headers, token };
}

async function updateChannelsList() {
    try {
        const { headers } = await createStalkerSession();
        const channelsUrls = [
            `${PORTAL_URL}?type=itv&action=get_all_channels&JsHttpRequest=1-xml`,
            `${PORTAL_URL}?type=itv&action=get_all_channels&genre=*&JsHttpRequest=1-xml`
        ];

        let rawChannels = [];
        for (const url of channelsUrls) {
            try {
                const res = await fetch(url, { headers, cf: { cacheTtl: 0 } });
                const text = await res.text();
                let data = {};
                try { data = JSON.parse(text); } catch(err) { continue; }
                
                const jsData = data.js;
                if (Array.isArray(jsData)) {
                    rawChannels = jsData;
                } else if (jsData?.data) {
                    rawChannels = jsData.data;
                }
                if (rawChannels.length > 0) break;
            } catch (e) {
                continue;
            }
        }

        const seen = new Set();
        const newChannels = [];
        for (const ch of rawChannels) {
            const cmd = ch.cmd;
            if (cmd && !seen.has(cmd)) {
                seen.add(cmd);
                newChannels.push({
                    name: ch.name || "Kanal",
                    cmd: cmd,
                    timeshift: ch.timeshift || 0
                });
            }
        }

        if (newChannels.length > 0) {
            cachedChannels = newChannels;
            lastUpdate = new Date().toISOString().replace('T', ' ').substring(0, 19);
        }
    } catch (e) {}
}

export default {
    async fetch(request, env, ctx) {
        try {
            const url = new URL(request.url);
            const baseUrl = `${url.protocol}//${url.host}`;

            if (cachedChannels.length === 0) {
                await updateChannelsList();
            }

            // 1. Главная страница: если зашли просто так без параметров — сразу кидаем в Telegram-группу (или на заглушку FALLBACK_VIDEO)
            if (url.pathname === "/") {
                return Response.redirect(TELEGRAM_GROUP, 302);
            }

            // Проверка пароля для плейлистов и каналов
            const userKey = url.searchParams.get("key") || url.searchParams.get("password");
            if (userKey !== "000") {
                return Response.redirect(FALLBACK_VIDEO, 302);
            }

            // 2. Скачивание JSON плейлиста
            if (url.pathname === "/playlist.json") {
                const result = cachedChannels.map((ch, idx) => ({
                    name: ch.name,
                    url: `${baseUrl}/stream/${idx}?key=TvZaTak`
                }));
                return new Response(JSON.stringify(result, null, 2), {
                    headers: { "Content-Type": "application/json; charset=utf-8" }
                });
            }

            // 3. Скачивание M3U плейлиста
            if (url.pathname === "/pl.m3u8") {
                let m3u = ["#EXTM3U"];
                cachedChannels.forEach((ch, idx) => {
                    const shift = ch.timeshift ? ` tvg-shift="${ch.timeshift}" catchup="default" catchup-days="3"` : "";
                    m3u.push(`#EXTINF:-1${shift},${ch.name}`);
                    m3u.push(`${baseUrl}/stream/${idx}?key=TvZaTak`);
                });
                return new Response(m3u.join("\n"), {
                    headers: { "Content-Type": "audio/x-mpegurl; charset=utf-8" }
                });
            }

            // 4. Запуск конкретного канала
            if (url.pathname.startsWith("/stream/")) {
                const idx = parseInt(url.pathname.split("/")[2]);
                if (isNaN(idx) || !cachedChannels[idx]) {
                    return Response.redirect(FALLBACK_VIDEO, 302);
                }

                const target = cachedChannels[idx];
                let streamUrl = "";

                try {
                    const { headers, token } = await createStalkerSession();
                    const linkUrl = `${PORTAL_URL}?type=itv&action=create_link&cmd=${encodeURIComponent(target.cmd)}&JsHttpRequest=1-xml`;
                    const linkRes = await fetch(linkUrl, { headers, cf: { cacheTtl: 0 } });
                    const text = await linkRes.text();
                    
                    let linkData = {};
                    try { linkData = JSON.parse(text); } catch(err) {}
                    
                    let streamCmd = linkData.js?.cmd || linkData.js?.url || "";

                    for (const prefix of ["ffmpeg ", "ch:ffrt ", "ffrt ", "ch:"]) {
                        if (streamCmd.startsWith(prefix)) {
                            streamCmd = streamCmd.slice(prefix.length).trim();
                        }
                    }

                    if (streamCmd.startsWith("http://") || streamCmd.startsWith("https://")) {
                        streamUrl = streamCmd;
                    } else if (streamCmd.startsWith("/")) {
                        const portalObj = new URL(PORTAL_URL);
                        streamUrl = `${portalObj.protocol}//${portalObj.host}${streamCmd}`;
                    }

                    if (streamUrl && !streamUrl.includes("token=") && token) {
                        const sep = streamUrl.includes("?") ? "&" : "?";
                        streamUrl = `${streamUrl}${sep}token=${token}`;
                    }
                } catch (e) {}

                if (!streamUrl) {
                    return Response.redirect(FALLBACK_VIDEO, 302);
                }

                return Response.redirect(streamUrl, 302);
            }

            return new Response("Sahifa topilmadi", { status: 404 });

        } catch (err) {
            return Response.redirect(TELEGRAM_GROUP, 302);
        }
    }
};
