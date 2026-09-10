import os
import re
import asyncio
import aiohttp

M3U_URL = "https://raw.githubusercontent.com/Ramys/Iptv-Brasil-2026/refs/heads/master/CanaisBR01.m3u8"

ADULT_KEYWORDS = ["xxx", "adulto", "porn", "playboy", "sextreme", "redlight", "venus", "hustler", "18+"]
VOD_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.flv')
VOD_PATTERNS = [
    r'\b(19\d{2}|20\d{2})\b', r'\bS\d{1,2}\s*E\d{1,2}\b', r'\b\d{1,2}x\d{1,2}\b',
    r'\bTEMPORADA\b', r'\bEPISODIO\b', r'\bDUBLADO\b', r'\bLEGENDADO\b',
    r'\b720P\b', r'\b1080P\b', r'\b4K\b', r'\bWEBRIP\b', r'\bWEB-DL\b', r'\bBLURAY\b'
]

# Base de Logos Diretas para Canais Populares do Brasil
DIRECT_LOGOS = {
    "a&e": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b2/A%26E_Network_logo.svg/320px-A%26E_Network_logo.svg.png",
    "globo": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c1/TV_Globo_logo_2021.svg/320px-TV_Globo_logo_2021.svg.png",
    "sbt": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d4/SBT_logo_2014.svg/320px-SBT_logo_2014.svg.png",
    "record": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/90/Record_TV_logo_2023.svg/320px-Record_TV_logo_2023.svg.png",
    "band": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d2/Rede_Bandeirantes_logo.svg/320px-Rede_Bandeirantes_logo.svg.png",
    "redetv": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/RedeTV%21_logo.svg/320px-RedeTV%21_logo.svg.png",
    "sportv": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/SporTV_logo_2021.svg/320px-SporTV_logo_2021.svg.png",
    "espn": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2f/ESPN_wordmark.svg/320px-ESPN_wordmark.svg.png",
    "premiere": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Premiere_logo_2021.svg/320px-Premiere_logo_2021.svg.png",
    "combate": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a9/Canal_Combate_logo.svg/320px-Canal_Combate_logo.svg.png",
    "cartoon network": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/80/Cartoon_Network_2010_logo.svg/320px-Cartoon_Network_2010_logo.svg.png",
    "discovery": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f1/Discovery_Channel_logo_2019.svg/320px-Discovery_Channel_logo_2019.svg.png",
    "history": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f5/History_Logo.svg/320px-History_Logo.svg.png",
    "cnn brasil": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/66/CNN_Brasil_logo.svg/320px-CNN_Brasil_logo.svg.png",
    "globonews": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/30/GloboNews_logo_2021.svg/320px-GloboNews_logo_2021.svg.png"
}

EPG_BASE_URL = "https://epg.best/br.xml"

def clean_channel_name(name):
    """Limpa termos como 4K², FHD, H265, HD, etc."""
    cleaned = re.sub(r'(?i)\b(4k²|4k|fhd|h265|h\.265|hd²|hd|sd|hq|hevc|raw|1080p|720p)\b', '', name)
    cleaned = re.sub(r'[\[\]\(\)\²]', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned if cleaned else name

def get_logo_url(clean_name):
    """Busca o link da logo baseado no nome do canal."""
    name_lower = clean_name.lower()
    for key, logo in DIRECT_LOGOS.items():
        if key in name_lower:
            return logo
    return f"https://raw.githubusercontent.com/iptv-org/iptv/master/logos/{name_lower.replace(' ', '')}.png"

async def check_stream(session, url, semaphore):
    """Lê os primeiros bytes de streaming para garantir que o canal está realmente transmitindo."""
    if not url.startswith("http"):
        return False
    async with semaphore:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        try:
            async with session.get(url, timeout=4.0, headers=headers, allow_redirects=True) as response:
                if response.status != 200:
                    return False
                content_type = response.headers.get('Content-Type', '').lower()
                if 'text/html' in content_type:
                    return False
                
                # Tenta ler 1024 bytes do fluxo real para provar que está online
                chunk = await response.content.read(1024)
                return len(chunk) > 0
        except Exception:
            return False

def is_adult(text):
    return any(k in text.lower() for k in ADULT_KEYWORDS)

def is_vod(name, group, url):
    url_lower = url.lower()
    name_upper = name.upper()
    group_upper = group.upper()

    if url_lower.endswith(VOD_EXTENSIONS) or "/movie/" in url_lower or "/series/" in url_lower:
        return True
    if any(k in group_upper for k in ["VOD", "FILMES", "SERIES", "NETFLIX", "PRIME", "HBO MAX"]):
        if "24/7" not in group_upper:
            return True
    for pattern in VOD_PATTERNS:
        if re.search(pattern, name_upper):
            return True
    return False

def parse_m3u(content):
    lines = content.splitlines()
    channels = []
    current_channel = {}

    for line in lines:
        line = line.strip()
        if line.startswith("#EXTINF:"):
            current_channel = {"extinf": line, "url": ""}
            group_match = re.search(r'group-title="([^"]+)"', line)
            group = group_match.group(1) if group_match else "Variedades"
            name = line.split(",")[-1].strip() if "," in line else "Sem Nome"
            
            current_channel["name"] = name
            current_channel["group"] = group
        elif line and not line.startswith("#") and current_channel:
            current_channel["url"] = line
            channels.append(current_channel)
            current_channel = {}

    return channels

def classify_channel(channel):
    name = channel["name"]
    group = channel["group"]
    url = channel["url"]

    if is_adult(group) or is_adult(name) or is_vod(name, group, url):
        return None

    group_upper = group.upper()
    name_upper = name.upper()

    if "24/7" in group_upper or "24/7" in name_upper:
        channel["group"] = "Canais 24/7 (Séries & Programas)"
    elif any(k in group_upper or k in name_upper for k in ["ESPORTE", "SPORT", "PREMIERE", "ESPN", "BANDSPORTS", "COMBATE"]):
        channel["group"] = "Esportes"
    elif any(k in group_upper or k in name_upper for k in ["INFANTIL", "KIDS", "DESENHO", "CARTOON", "NICK", "DISNEY", "GLOOB"]):
        channel["group"] = "Infantil & Desenhos"
    elif any(k in group_upper or k in name_upper for k in ["NOTICIA", "NEWS", "CNN", "BANDNEWS", "RECORD NEWS", "GLOBONEWS"]):
        channel["group"] = "Notícias"
    elif any(k in group_upper or k in name_upper for k in ["DOC", "DOCUMENTARIO", "DISCOVERY", "NATIONAL", "GEOGRAPHIC", "HISTORY"]):
        channel["group"] = "Documentários & Ciência"
    elif any(k in group_upper or k in name_upper for k in ["RELIGIOSO", "GOSPEL", "CATOLICO", "EVANGELICO"]):
        channel["group"] = "Religiosos"
    elif any(k in group_upper or k in name_upper for k in ["GLOBO", "SBT", "RECORD", "BAND", "REDETV", "CULTURA"]):
        channel["group"] = "TV Aberta"
    else:
        channel["group"] = "Variedades & Entretenimento"

    return channel

async def main():
    print("Baixando lista M3U...")
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(M3U_URL) as resp:
                content = await resp.text()
        except Exception as e:
            print(f"Erro no download: {e}")
            return

        channels = parse_m3u(content)
        print(f"Total bruto de itens: {len(channels)}")

        live_channels = []
        for ch in channels:
            classified = classify_channel(ch)
            if classified:
                live_channels.append(classified)

        print(f"Canais filtrados (sem adult/vod): {len(live_channels)}")

        print("Testando fluxo real de dados de vídeo...")
        semaphore = asyncio.Semaphore(30)
        
        async def verify(ch):
            online = await check_stream(session, ch["url"], semaphore)
            return ch if online else None

        tasks = [verify(ch) for ch in live_channels]
        results = await asyncio.gather(*tasks)
        online_channels = [ch for ch in results if ch is not None]

        print(f"Canais com fluxo ativo real: {len(online_channels)}")

        # Gravando arquivo final M3U
        with open("lista_limpa.m3u", "w", encoding="utf-8") as f:
            f.write(f'#EXTM3U url-tvg="{EPG_BASE_URL}"\n')
            for ch in online_channels:
                clean_name = clean_channel_name(ch["name"])
                logo_url = get_logo_url(clean_name)

                # Monta a nova linha EXTINF já com a logo injetada e categoria
                new_extinf = f'#EXTINF:-1 tvg-logo="{logo_url}" group-title="{ch["group"]}",{clean_name}'
                f.write(f"{new_extinf}\n{ch['url']}\n")

        print("Nova lista gerada e salva com sucesso!")

if __name__ == "__main__":
    asyncio.run(main())
