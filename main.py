import os
import re
import asyncio
import aiohttp

M3U_URL = "https://raw.githubusercontent.com/Ramys/Iptv-Brasil-2026/refs/heads/master/CanaisBR01.m3u8"

ADULT_KEYWORDS = ["xxx", "adulto", "porn", "playboy", "sextreme", "redlight", "venus", "hustler", "18+"]
VOD_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.flv')
VOD_PATTERNS = [
    r'\b(19\d{2}|20\d{2})\b',
    r'\bS\d{1,2}\s*E\d{1,2}\b',
    r'\b\d{1,2}x\d{1,2}\b',
    r'\bTEMPORADA\b',
    r'\bEPISODIO\b',
    r'\bDUBLADO\b', r'\bLEGENDADO\b',
    r'\b720P\b', r'\b1080P\b', r'\b4K\b',
    r'\bWEBRIP\b', r'\bWEB-DL\b', r'\bBLURAY\b'
]

# Base pública EPG e Logos
EPG_BASE_URL = "https://epg.best/br.xml"
LOGOS_MAPPING_URL = "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/br.m3u"

async def load_logo_database(session):
    """Baixa um mapeamento público de canais do Brasil com logos."""
    logo_dict = {}
    try:
        async with session.get(LOGOS_MAPPING_URL, timeout=10) as resp:
            if resp.status == 200:
                text = await resp.text()
                for line in text.splitlines():
                    if line.startswith("#EXTINF:"):
                        logo_match = re.search(r'tvg-logo="([^"]+)"', line)
                        name = line.split(",")[-1].strip() if "," in line else ""
                        if logo_match and name:
                            clean_n = clean_channel_name(name).lower()
                            logo_dict[clean_n] = logo_match.group(1)
    except Exception as e:
        print(f"Aviso: Não foi possível carregar base externa de logos: {e}")
    return logo_dict

def clean_channel_name(name):
    """Remove sufixos de qualidade e caracteres para busca de logo e exibição limpa."""
    # Remove termos como 4K, FHD, HD, SD, [RAW], 4K², etc.
    cleaned = re.sub(r'(?i)\b(4k²|4k|fhd|hd|sd|hq|hevc|raw|1080p|720p)\b', '', name)
    cleaned = re.sub(r'[\[\]\(\)\²]', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned if cleaned else name

async def check_stream(session, url, semaphore):
    """Testa se a URL é um fluxo de mídia ativo válido e não um erro mascarado."""
    if not url.startswith("http"):
        return False
    async with semaphore:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        try:
            async with session.get(url, timeout=3.5, headers=headers, allow_redirects=True) as response:
                if response.status != 200:
                    return False
                content_type = response.headers.get('Content-Type', '').lower()
                # Rejeita páginas HTML que fingem ser status 200
                if 'text/html' in content_type:
                    return False
                return True
        except Exception:
            return False

def is_adult(text):
    text_lower = text.lower()
    return any(k in text_lower for k in ADULT_KEYWORDS)

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
        # Carrega base de logos
        logo_db = await load_logo_database(session)

        try:
            async with session.get(M3U_URL) as resp:
                content = await resp.text()
        except Exception as e:
            print(f"Erro no download: {e}")
            return

        channels = parse_m3u(content)
        print(f"Total bruto de itens lidos: {len(channels)}")

        live_channels = []
        for ch in channels:
            classified = classify_channel(ch)
            if classified:
                live_channels.append(classified)

        print(f"Canais de TV Ao Vivo filtrados: {len(live_channels)}")

        print("Iniciando verificação rigorosa de sinal online...")
        semaphore = asyncio.Semaphore(40) # Testes simultâneos para verificação mais precisa
        
        async def verify(ch):
            online = await check_stream(session, ch["url"], semaphore)
            return ch if online else None

        tasks = [verify(ch) for ch in live_channels]
        results = await asyncio.gather(*tasks)
        online_channels = [ch for ch in results if ch is not None]

        print(f"Canais 100% ativos e validados: {len(online_channels)}")

        # Gravando arquivo final M3U
        with open("lista_limpa.m3u", "w", encoding="utf-8") as f:
            f.write(f'#EXTM3U url-tvg="{EPG_BASE_URL}"\n')
            for ch in online_channels:
                clean_name = clean_channel_name(ch["name"])
                clean_key = clean_name.lower()
                
                # Busca logo
                logo_url = logo_db.get(clean_key, "")
                
                extinf = ch["extinf"]
                # Atualiza ou insere group-title
                extinf = re.sub(r'group-title="[^"]+"', f'group-title="{ch["group"]}"', extinf)
                if 'group-title=' not in extinf:
                    extinf = extinf.replace("#EXTINF:-1", f'#EXTINF:-1 group-title="{ch["group"]}"')

                # Injeta a tag tvg-logo
                if logo_url:
                    if 'tvg-logo=' in extinf:
                        extinf = re.sub(r'tvg-logo="[^"]+"', f'tvg-logo="{logo_url}"', extinf)
                    else:
                        extinf = extinf.replace('#EXTINF:-1', f'#EXTINF:-1 tvg-logo="{logo_url}"')

                # Substitui o nome do canal pelo nome limpo
                if "," in extinf:
                    prefix = extinf.rsplit(",", 1)[0]
                    extinf = f"{prefix},{clean_name}"

                f.write(f"{extinf}\n{ch['url']}\n")

        print("Lista 'lista_limpa.m3u' atualizada com sucesso com Logos e Filtro Rigoroso!")

if __name__ == "__main__":
    asyncio.run(main())
