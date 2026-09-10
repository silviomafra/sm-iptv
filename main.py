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
    r'\bWEBRIP\b', r'\bWEB-DL\b', r'\bBLURAY\b'
]

# Base de Logos Diretas e Estáveis (PNG transparente sem bloqueios)
DIRECT_LOGOS = {
    # VARIADAS / FILMES / SÉRIES
    "a&e": "https://logodownload.org/wp-content/uploads/2018/03/ae-logo.png",
    "agromais": "https://logodownload.org/wp-content/uploads/2020/06/agromais-logo.png",
    "telecine": "https://logodownload.org/wp-content/uploads/2018/03/telecine-logo.png",
    "hbo": "https://logodownload.org/wp-content/uploads/2015/12/hbo-logo.png",
    "megapix": "https://logodownload.org/wp-content/uploads/2018/03/megapix-logo.png",
    "tnt": "https://logodownload.org/wp-content/uploads/2015/02/tnt-logo.png",
    "space": "https://logodownload.org/wp-content/uploads/2018/03/space-logo.png",
    "axn": "https://logodownload.org/wp-content/uploads/2018/03/axn-logo.png",
    "warner": "https://logodownload.org/wp-content/uploads/2020/11/warner-channel-logo.png",
    "universal": "https://logodownload.org/wp-content/uploads/2018/03/universal-tv-logo.png",
    "paramount": "https://logodownload.org/wp-content/uploads/2020/09/paramount-network-logo.png",
    "cinemax": "https://logodownload.org/wp-content/uploads/2018/03/cinemax-logo.png",

    # TV ABERTA
    "globo": "https://logodownload.org/wp-content/uploads/2014/05/rede-globo-logo.png",
    "sbt": "https://logodownload.org/wp-content/uploads/2014/04/sbt-logo.png",
    "record": "https://logodownload.org/wp-content/uploads/2014/05/record-tv-logo.png",
    "band": "https://logodownload.org/wp-content/uploads/2014/05/band-logo.png",
    "redetv": "https://logodownload.org/wp-content/uploads/2014/05/redetv-logo.png",
    "cultura": "https://logodownload.org/wp-content/uploads/2018/03/tv-cultura-logo.png",

    # ESPORTES
    "sportv": "https://logodownload.org/wp-content/uploads/2017/04/sportv-logo.png",
    "espn": "https://logodownload.org/wp-content/uploads/2015/05/espn-logo.png",
    "premiere": "https://logodownload.org/wp-content/uploads/2018/03/premiere-logo.png",
    "combate": "https://logodownload.org/wp-content/uploads/2018/03/canal-combate-logo.png",
    "bandsports": "https://logodownload.org/wp-content/uploads/2018/03/bandsports-logo.png",

    # INFANTIL
    "cartoon": "https://logodownload.org/wp-content/uploads/2017/08/cartoon-network-logo.png",
    "discovery kids": "https://logodownload.org/wp-content/uploads/2018/03/discovery-kids-logo.png",
    "gloob": "https://logodownload.org/wp-content/uploads/2018/03/gloob-logo.png",
    "nickelodeon": "https://logodownload.org/wp-content/uploads/2017/08/nickelodeon-logo.png",
    "disney": "https://logodownload.org/wp-content/uploads/2017/08/disney-channel-logo.png",

    # NOTÍCIAS & DOCUMENTÁRIOS
    "globonews": "https://logodownload.org/wp-content/uploads/2018/03/globonews-logo.png",
    "cnn brasil": "https://logodownload.org/wp-content/uploads/2020/03/cnn-brasil-logo.png",
    "bandnews": "https://logodownload.org/wp-content/uploads/2018/03/bandnews-tv-logo.png",
    "discovery": "https://logodownload.org/wp-content/uploads/2018/03/discovery-channel-logo.png",
    "history": "https://logodownload.org/wp-content/uploads/2018/03/history-channel-logo.png",
    "national geographic": "https://logodownload.org/wp-content/uploads/2017/09/national-geographic-logo.png",

    # VARIEDADES
    "viva": "https://logodownload.org/wp-content/uploads/2018/03/canal-viva-logo.png",
    "multishow": "https://logodownload.org/wp-content/uploads/2018/03/multishow-logo.png",
    "gnt": "https://logodownload.org/wp-content/uploads/2018/03/gnt-logo.png"
}

EPG_BASE_URL = "https://epg.best/br.xml"

def get_base_name_for_logo(name):
    """Obtém o nome base para cruzamento de logo preservando a marca principal."""
    clean = re.sub(r'(?i)\b(4k²|4k|fhd|h265|h\.265|hd²|hd|sd|hq|hevc|raw|1080p|720p)\b', '', name)
    clean = re.sub(r'[\[\]\(\)\²]', '', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean if clean else name

def get_logo_url(channel_name):
    """Mapeia a URL limpa e direta da logo sem bloqueios de CDN."""
    base_name = get_base_name_for_logo(channel_name).lower()
    
    # 1. Procura na tabela oficial de logos limpas
    for key, logo_url in DIRECT_LOGOS.items():
        if key in base_name:
            return logo_url
            
    # 2. Servidor público secundário de logos em PNG
    formatted_name = re.sub(r'[^a-zA-Z0-9]', '', base_name)
    return f"https://raw.githubusercontent.com/iptv-org/database/master/data/logos/{formatted_name}.png"

async def check_stream(session, url, semaphore):
    """Testa se a URL responde status HTTP 200 de forma rápida."""
    if not url.startswith("http"):
        return False
    async with semaphore:
        headers = {'User-Agent': 'VLC/3.0.18 LibVLC/3.0.18'}
        try:
            async with session.head(url, timeout=3.5, headers=headers, allow_redirects=True) as response:
                return response.status == 200
        except Exception:
            try:
                async with session.get(url, timeout=3.5, headers=headers, allow_redirects=True) as response:
                    return response.status == 200
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
        channel["group"] = "Canais 24/7"
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
    print("Baixando lista M3U original...")
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(M3U_URL) as resp:
                content = await resp.text()
        except Exception as e:
            print(f"Erro ao baixar lista: {e}")
            return

        channels = parse_m3u(content)
        print(f"Total bruto de itens lidos: {len(channels)}")

        live_channels = []
        for ch in channels:
            classified = classify_channel(ch)
            if classified:
                live_channels.append(classified)

        print(f"Canais de TV filtrados: {len(live_channels)}")

        print("Testando sinal online dos canais...")
        semaphore = asyncio.Semaphore(50)
        
        async def verify(ch):
            online = await check_stream(session, ch["url"], semaphore)
            return ch if online else None

        tasks = [verify(ch) for ch in live_channels]
        results = await asyncio.gather(*tasks)
        online_channels = [ch for ch in results if ch is not None]

        print(f"Canais online validados: {len(online_channels)}")

        # Gravando arquivo final M3U
        with open("lista_limpa.m3u", "w", encoding="utf-8") as f:
            f.write(f'#EXTM3U url-tvg="{EPG_BASE_URL}"\n')
            for ch in online_channels:
                original_name = ch["name"]
                logo_url = get_logo_url(original_name)

                # Formatação completa mantendo a qualidade no nome do canal
                new_extinf = f'#EXTINF:-1 tvg-name="{original_name}" tvg-logo="{logo_url}" group-title="{ch["group"]}",{original_name}'
                f.write(f"{new_extinf}\n{ch['url']}\n")

        print("Nova lista gerada com sucesso e com URLs diretas de logos!")

if __name__ == "__main__":
    asyncio.run(main())
