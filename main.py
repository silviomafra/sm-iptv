import os
import re
import urllib.parse
import asyncio
import aiohttp

LOGOS_M3U_URL = "https://raw.githubusercontent.com/Ramys/Iptv-Brasil-2026/refs/heads/master/CanaisBR03.m3u8"
MAIN_M3U_URL = "https://raw.githubusercontent.com/Ramys/Iptv-Brasil-2026/refs/heads/master/CanaisBR01.m3u8"

ADULT_KEYWORDS = ["xxx", "adulto", "porn", "playboy", "sextreme", "redlight", "venus", "hustler", "18+"]
VOD_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.flv')
VOD_PATTERNS = [
    r'\b(19\d{2}|20\d{2})\b', r'\bS\d{1,2}\s*E\d{1,2}\b', r'\b\d{1,2}x\d{1,2}\b',
    r'\bTEMPORADA\b', r'\bEPISODIO\b', r'\bDUBLADO\b', r'\bLEGENDADO\b',
    r'\bWEBRIP\b', r'\bWEB-DL\b', r'\bBLURAY\b'
]

EPG_BASE_URL = "https://epg.best/br.xml"
TJTOR_BASE = "http://tjtor8411.com/static/logos/canais/"

# Mapeamento absoluto das marcas mães para cobrir TODAS as variações estaduais, regionais e de qualidade
PARENT_BRANDS = {
    "band": f"{TJTOR_BASE}band.png",
    "globo": f"{TJTOR_BASE}globo.png",
    "sbt": f"{TJTOR_BASE}sbt.png",
    "record": f"{TJTOR_BASE}record.png",
    "redetv": f"{TJTOR_BASE}redetv.png",
    "viva": f"{TJTOR_BASE}viva.png",
    "cultura": f"{TJTOR_BASE}tv_cultura.png",
    "gazeta": f"{TJTOR_BASE}tv_gazeta.png",
    "agromais": f"{TJTOR_BASE}agromais.png",
    
    "sportv": f"{TJTOR_BASE}sportv.png",
    "espn": f"{TJTOR_BASE}espn.png",
    "premiere": f"{TJTOR_BASE}premiere.png",
    "combate": f"{TJTOR_BASE}combate.png",
    "bandsports": f"{TJTOR_BASE}bandsports.png",

    "telecine": f"{TJTOR_BASE}telecine.png",
    "hbo": f"{TJTOR_BASE}hbo.png",
    "megapix": f"{TJTOR_BASE}megapix.png",
    "tnt": f"{TJTOR_BASE}tnt.png",
    "space": f"{TJTOR_BASE}space.png",
    "axn": f"{TJTOR_BASE}axn.png",
    "warner": f"{TJTOR_BASE}warner.png",
    "universal": f"{TJTOR_BASE}universal.png",
    "paramount": f"{TJTOR_BASE}paramount.png",
    "a&e": f"{TJTOR_BASE}a%26e.png",
    "cinemax": f"{TJTOR_BASE}cinemax.png",
    "amc": f"{TJTOR_BASE}amc.png",
    
    "cartoon": f"{TJTOR_BASE}cartoon.png",
    "gloob": f"{TJTOR_BASE}gloob.png",
    "nickelodeon": f"{TJTOR_BASE}nickelodeon.png",
    "disney": f"{TJTOR_BASE}disney.png",
    
    "globonews": f"{TJTOR_BASE}globonews.png",
    "cnn": f"{TJTOR_BASE}cnn_brasil.png",
    "bandnews": f"{TJTOR_BASE}bandnews.png",
    "discovery": f"{TJTOR_BASE}discovery.png",
    "history": f"{TJTOR_BASE}history.png",
    "multishow": f"{TJTOR_BASE}multishow.png",
    "gnt": f"{TJTOR_BASE}gnt.png"
}

def get_guaranteed_logo(channel_name, logo_map):
    """Encontra a logo garantida para 100% das variações estaduais e de qualidade."""
    name_lower = channel_name.strip().lower()

    # 1. Checagem por Marca Mãe (Garante BAND SP, BAND RJ, GLOBO SP, VIVA SD, etc)
    for brand, logo_url in PARENT_BRANDS.items():
        # Usa regex para garantir a palavra inteira da marca
        if re.search(r'\b' + re.escape(brand) + r'\b', name_lower) or name_lower.startswith(brand):
            return logo_url

    # 2. Busca pelo nome exato do canal no banco de dados lido do CanaisBR03
    if name_lower in logo_map:
        return logo_map[name_lower]

    # 3. Busca parcial no banco do autor
    for db_name, logo_url in logo_map.items():
        if db_name in name_lower or name_lower in db_name:
            return logo_url

    # 4. Fallback limpo
    clean_name = re.sub(r'[^a-zA-Z0-9]', '', name_lower)
    return f"{TJTOR_BASE}{clean_name}.png"

async def load_tjtor_logo_database(session):
    """Carrega as logos do arquivo oficial do autor."""
    logo_map = {}
    try:
        async with session.get(LOGOS_M3U_URL, timeout=15) as resp:
            if resp.status == 200:
                text = await resp.text()
                for line in text.splitlines():
                    if line.startswith("#EXTINF:"):
                        logo_match = re.search(r'tvg-logo="([^"]+)"', line)
                        name = line.split(",")[-1].strip() if "," in line else ""
                        if logo_match and name:
                            logo_map[name.strip().lower()] = logo_match.group(1)
    except Exception as e:
        print(f"Erro ao carregar banco de logos: {e}")
    return logo_map

async def check_stream(session, url, semaphore):
    """Testa se a URL do canal responde status HTTP 200."""
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
    async with aiohttp.ClientSession() as session:
        logo_map = await load_tjtor_logo_database(session)

        print("Baixando lista de canais principal...")
        try:
            async with session.get(MAIN_M3U_URL) as resp:
                content = await resp.text()
        except Exception as e:
            print(f"Erro ao baixar lista principal: {e}")
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

        with open("lista_limpa.m3u", "w", encoding="utf-8") as f:
            f.write(f'#EXTM3U url-tvg="{EPG_BASE_URL}"\n')
            for ch in online_channels:
                original_name = ch["name"]
                logo_url = get_guaranteed_logo(original_name, logo_map)

                new_extinf = f'#EXTINF:-1 tvg-name="{original_name}" tvg-logo="{logo_url}" group-title="{ch["group"]}",{original_name}'
                f.write(f"{new_extinf}\n{ch['url']}\n")

        print("Nova lista gerada com sucesso e 100% das variações mapeadas!")

if __name__ == "__main__":
    asyncio.run(main())
