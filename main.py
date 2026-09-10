import os
import re
import urllib.parse
import asyncio
import aiohttp

# URL do banco de dados oficial do autor que contém TODAS as logos exatas do tjtor8411.com
LOGOS_M3U_URL = "https://raw.githubusercontent.com/Ramys/Iptv-Brasil-2026/refs/heads/master/CanaisBR03.m3u8"
# URL principal dos canais
MAIN_M3U_URL = "https://raw.githubusercontent.com/Ramys/Iptv-Brasil-2026/refs/heads/master/CanaisBR01.m3u8"

ADULT_KEYWORDS = ["xxx", "adulto", "porn", "playboy", "sextreme", "redlight", "venus", "hustler", "18+"]
VOD_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.flv')
VOD_PATTERNS = [
    r'\b(19\d{2}|20\d{2})\b', r'\bS\d{1,2}\s*E\d{1,2}\b', r'\b\d{1,2}x\d{1,2}\b',
    r'\bTEMPORADA\b', r'\bEPISODIO\b', r'\bDUBLADO\b', r'\bLEGENDADO\b',
    r'\bWEBRIP\b', r'\bWEB-DL\b', r'\bBLURAY\b'
]

EPG_BASE_URL = "https://epg.best/br.xml"
TJTOR_BASE_LOGO = "http://tjtor8411.com/static/logos/canais/"

def get_base_channel_name(name):
    """Extrai a marca principal do canal ignorando sufixos para batimento de nome."""
    clean = re.sub(r'(?i)\b(4k²|4k|fhd|h265|h\.265|hd²|hd|sd|hq|hevc|raw|1080p|720p|24/7)\b', '', name)
    clean = re.sub(r'[\[\]\(\)\²|]', '', clean)
    clean = re.sub(r'\s+', ' ', clean).strip().lower()
    return clean if clean else name.lower()

async def load_tjtor_logo_database(session):
    """Lê a lista oficial CanaisBR03 e extrai 100% dos links de logos do tjtor8411.com"""
    logo_map = {}
    print("Baixando mapeamento oficial de logos do tjtor8411.com...")
    try:
        async with session.get(LOGOS_M3U_URL, timeout=15) as resp:
            if resp.status == 200:
                text = await resp.text()
                for line in text.splitlines():
                    if line.startswith("#EXTINF:"):
                        logo_match = re.search(r'tvg-logo="([^"]+)"', line)
                        name = line.split(",")[-1].strip() if "," in line else ""
                        if logo_match and name:
                            logo_url = logo_match.group(1)
                            base_name = get_base_channel_name(name)
                            logo_map[base_name] = logo_url
                print(f"Mapeamento carregado com sucesso! {len(logo_map)} logos oficiais encontradas.")
    except Exception as e:
        print(f"Aviso ao carregar banco de logos: {e}")
    return logo_map

def get_logo_for_channel(channel_name, logo_db):
    """Obtém a logo do banco de dados oficial ou gera no padrão exato do servidor tjtor8411."""
    base_name = get_base_channel_name(channel_name)

    # 1. Busca exata no banco de dados extraído do CanaisBR03
    if base_name in logo_db:
        return logo_db[base_name]

    # 2. Busca parcial (ex: "globo sp" encontra a logo de "globo")
    for db_name, logo_url in logo_db.items():
        if db_name in base_name or base_name in db_name:
            return logo_url

    # 3. Fallback no padrão do servidor tjtor8411 (converte espaços em sublinhado e codifica caracteres especiais como &)
    formatted_filename = base_name.replace(" ", "_")
    encoded_filename = urllib.parse.quote(formatted_filename)
    return f"{TJTOR_BASE_LOGO}{encoded_filename}.png"

async def check_stream(session, url, semaphore):
    """Testa se a URL do canal responde status 200."""
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
        # 1. Carrega o banco de dados oficial de logos do tjtor8411.com
        logo_db = await load_tjtor_logo_database(session)

        print("Baixando lista de canais...")
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

        # 2. Grava o arquivo final M3U cruzando com as logos exatas do tjtor8411.com
        with open("lista_limpa.m3u", "w", encoding="utf-8") as f:
            f.write(f'#EXTM3U url-tvg="{EPG_BASE_URL}"\n')
            for ch in online_channels:
                original_name = ch["name"]
                logo_url = get_logo_for_channel(original_name, logo_db)

                new_extinf = f'#EXTINF:-1 tvg-name="{original_name}" tvg-logo="{logo_url}" group-title="{ch["group"]}",{original_name}'
                f.write(f"{new_extinf}\n{ch['url']}\n")

        print("Lista gerada com sucesso e cruzada com os links reais do tjtor8411.com!")

if __name__ == "__main__":
    asyncio.run(main())
