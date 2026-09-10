import os
import re
import asyncio
import aiohttp

M3U_URL = "https://raw.githubusercontent.com/Ramys/Iptv-Brasil-2026/refs/heads/master/CanaisBR01.m3u8"

# Palavras-chave para remover conteúdo adulto e arquivos VOD On Demand
ADULT_KEYWORDS = ["xxx", "adulto", "porn", "playboy", "sextreme", "redlight", "venus", "hustler", "18+"]
VOD_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.flv')
VOD_PATTERNS = [
    r'\b(19\d{2}|20\d{2})\b', r'\bS\d{1,2}\s*E\d{1,2}\b', r'\b\d{1,2}x\d{1,2}\b',
    r'\bTEMPORADA\b', r'\bEPISODIO\b', r'\bDUBLADO\b', r'\bLEGENDADO\b',
    r'\b720P\b', r'\b1080P\b', r'\b4K\b', r'\bWEBRIP\b', r'\bWEB-DL\b', r'\bBLURAY\b'
]

# Dicionário de Logos Profissionais em Alta Resolução (HD/PNG)
LOGOS_MAP = {
    # TV ABERTA
    "globo": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c1/TV_Globo_logo_2021.svg/512px-TV_Globo_logo_2021.svg.png",
    "sbt": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d4/SBT_logo_2014.svg/512px-SBT_logo_2014.svg.png",
    "record": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/90/Record_TV_logo_2023.svg/512px-Record_TV_logo_2023.svg.png",
    "band": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d2/Rede_Bandeirantes_logo.svg/512px-Rede_Bandeirantes_logo.svg.png",
    "redetv": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/RedeTV%21_logo.svg/512px-RedeTV%21_logo.svg.png",
    "cultura": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1b/TV_Cultura_logo_2019.svg/512px-TV_Cultura_logo_2019.svg.png",
    "gazeta": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d5/TV_Gazeta_logo.svg/512px-TV_Gazeta_logo.svg.png",

    # ESPORTES
    "sportv 1": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/SporTV_logo_2021.svg/512px-SporTV_logo_2021.svg.png",
    "sportv 2": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/SporTV_logo_2021.svg/512px-SporTV_logo_2021.svg.png",
    "sportv 3": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/SporTV_logo_2021.svg/512px-SporTV_logo_2021.svg.png",
    "sportv": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/SporTV_logo_2021.svg/512px-SporTV_logo_2021.svg.png",
    "espn": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2f/ESPN_wordmark.svg/512px-ESPN_wordmark.svg.png",
    "premiere": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Premiere_logo_2021.svg/512px-Premiere_logo_2021.svg.png",
    "combate": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a9/Canal_Combate_logo.svg/512px-Canal_Combate_logo.svg.png",
    "bandsports": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/db/BandSports_logo.png/512px-BandSports_logo.png",
    "nosso futebol": "https://raw.githubusercontent.com/iptv-org/iptv/master/logos/NossoFutebol.png",

    # CANAIS DE FILMES E SÉRIES
    "telecine premium": "https://raw.githubusercontent.com/iptv-org/iptv/master/logos/TelecinePremium.png",
    "telecine action": "https://raw.githubusercontent.com/iptv-org/iptv/master/logos/TelecineAction.png",
    "telecine touch": "https://raw.githubusercontent.com/iptv-org/iptv/master/logos/TelecineTouch.png",
    "telecine fun": "https://raw.githubusercontent.com/iptv-org/iptv/master/logos/TelecineFun.png",
    "telecine pipoca": "https://raw.githubusercontent.com/iptv-org/iptv/master/logos/TelecinePipoca.png",
    "telecine cult": "https://raw.githubusercontent.com/iptv-org/iptv/master/logos/TelecineCult.png",
    "telecine": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6b/Telecine_logo_2019.svg/512px-Telecine_logo_2019.svg.png",
    "hbo": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/de/HBO_logo.svg/512px-HBO_logo.svg.png",
    "megapix": "https://raw.githubusercontent.com/iptv-org/iptv/master/logos/Megapix.png",
    "tnt": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/07/TNT_Logo_2016.svg/512px-TNT_Logo_2016.svg.png",
    "space": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/Space_Channel_Logo.svg/512px-Space_Channel_Logo.svg.png",
    "axn": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/ca/AXN_logo_2015.svg/512px-AXN_logo_2015.svg.png",
    "warner": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/80/Warner_TV_logo_2021.svg/512px-Warner_TV_logo_2021.svg.png",
    "universal": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/23/Universal_TV_logo.svg/512px-Universal_TV_logo.svg.png",
    "studio universal": "https://raw.githubusercontent.com/iptv-org/iptv/master/logos/StudioUniversal.png",
    "paramount": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Paramount_Network_2018.svg/512px-Paramount_Network_2018.svg.png",
    "a&e": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b2/A%26E_Network_logo.svg/512px-A%26E_Network_logo.svg.png",
    "cinemax": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8b/Cinemax_2011_logo.svg/512px-Cinemax_2011_logo.svg.png",
    "amc": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1d/AMC_logo_2019.svg/512px-AMC_logo_2019.svg.png",

    # INFANTIL
    "cartoon network": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/80/Cartoon_Network_2010_logo.svg/512px-Cartoon_Network_2010_logo.svg.png",
    "discovery kids": "https://raw.githubusercontent.com/iptv-org/iptv/master/logos/DiscoveryKids.png",
    "gloob": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b1/Gloob_logo_2017.svg/512px-Gloob_logo_2017.svg.png",
    "gloobinho": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f7/Gloobinho_logo.svg/512px-Gloobinho_logo.svg.png",
    "nickelodeon": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7a/Nickelodeon_2023_logo.svg/512px-Nickelodeon_2023_logo.svg.png",
    "nick jr": "https://raw.githubusercontent.com/iptv-org/iptv/master/logos/NickJr.png",
    "disney channel": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d2/Disney_Channel_logo.svg/512px-Disney_Channel_logo.svg.png",

    # NOTÍCIAS & DOCUMENTÁRIOS
    "globonews": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/30/GloboNews_logo_2021.svg/512px-GloboNews_logo_2021.svg.png",
    "cnn brasil": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/66/CNN_Brasil_logo.svg/512px-CNN_Brasil_logo.svg.png",
    "bandnews": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c5/BandNews_TV_logo.svg/512px-BandNews_TV_logo.svg.png",
    "jovem pan news": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a2/Jovem_Pan_News_logo.svg/512px-Jovem_Pan_News_logo.svg.png",
    "discovery": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f1/Discovery_Channel_logo_2019.svg/512px-Discovery_Channel_logo_2019.svg.png",
    "history": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f5/History_Logo.svg/512px-History_Logo.svg.png",
    "national geographic": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6a/National_Geographic_logo.svg/512px-National_Geographic_logo.svg.png",
    "animal planet": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/20/Animal_Planet_2018_logo.svg/512px-Animal_Planet_2018_logo.svg.png",

    # VARIEDADES
    "viva": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/90/Canal_Viva_logo_2018.svg/512px-Canal_Viva_logo_2018.svg.png",
    "multishow": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3d/Multishow_logo_2021.svg/512px-Multishow_logo_2021.svg.png",
    "gnt": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7f/GNT_logo_2021.svg/512px-GNT_logo_2021.svg.png",
    "e!": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b8/E%21_Logo.svg/512px-E%21_Logo.svg.png",
}

EPG_BASE_URL = "https://epg.best/br.xml"

def clean_channel_name(name):
    """Limpa identificadores de qualidade e formatos do nome do canal."""
    cleaned = re.sub(r'(?i)\b(4k²|4k|fhd|h265|h\.265|hd²|hd|sd|hq|hevc|raw|1080p|720p)\b', '', name)
    cleaned = re.sub(r'[\[\]\(\)\²]', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned if cleaned else name

def get_logo_url(clean_name):
    """Procura a logo oficial no dicionário mapeado."""
    name_lower = clean_name.lower()
    
    # Busca por correspondência exata ou parcial
    for key, logo_url in LOGOS_MAP.items():
        if key in name_lower:
            return logo_url
            
    # Fallback dinâmico para repositório open-source
    formatted_name = re.sub(r'[^a-zA-Z0-9]', '', clean_name)
    return f"https://raw.githubusercontent.com/iptv-org/iptv/master/logos/{formatted_name}.png"

async def check_stream(session, url, semaphore):
    """Testa a resposta HTTP do servidor usando parâmetros de player real (VLC)."""
    if not url.startswith("http"):
        return False
    async with semaphore:
        headers = {'User-Agent': 'VLC/3.0.18 LibVLC/3.0.18'}
        try:
            # Teste por HEAD (rápido e compatível com IPTV)
            async with session.head(url, timeout=3.5, headers=headers, allow_redirects=True) as response:
                return response.status == 200
        except Exception:
            try:
                # Fallback por GET curto se HEAD falhar
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

        print(f"Canais de TV filtrados (sem adult/vod): {len(live_channels)}")

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
                clean_name = clean_channel_name(ch["name"])
                logo_url = get_logo_url(clean_name)

                # Formata a linha EXTINF profissionalmente com logo e categoria
                new_extinf = f'#EXTINF:-1 tvg-logo="{logo_url}" group-title="{ch["group"]}",{clean_name}'
                f.write(f"{new_extinf}\n{ch['url']}\n")

        print("Nova lista profissional gerada e salva com sucesso!")

if __name__ == "__main__":
    asyncio.run(main())
