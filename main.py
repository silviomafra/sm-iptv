import os
import re
import asyncio
import aiohttp

M3U_URL = "https://raw.githubusercontent.com/Ramys/Iptv-Brasil-2026/refs/heads/master/CanaisBR01.m3u8"

# Termos que identificam conteúdo adulto
ADULT_KEYWORDS = ["xxx", "adulto", "porn", "playboy", "sextreme", "redlight", "venus", "hustler", "18+"]

# Expressões regulares e padrões para detectar Filmes e Séries On Demand (VOD)
VOD_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.flv')
VOD_PATTERNS = [
    r'\b(19\d{2}|20\d{2})\b',             # Anos ex: (1999), 2023
    r'\bS\d{1,2}\s*E\d{1,2}\b',           # Padrão S01E01, S1E2
    r'\b\d{1,2}x\d{1,2}\b',               # Padrão 1x01, 02x05
    r'\bTEMPORADA\b',                     # Palavra Temporada
    r'\bEPISODIO\b',                      # Palavra Episodio
    r'\bDUBLADO\b', r'\bLEGENDADO\b',     # Indicadores de arquivo VOD
    r'\b720P\b', r'\b1080P\b', r'\b4K\b', # Resoluções comuns em releases de filmes
    r'\bWEBRIP\b', r'\bWEB-DL\b', r'\bBLURAY\b'
]

EPG_BASE_URL = "https://epg.best/br.xml"

async def check_stream(session, url, semaphore):
    """Testa se o link de streaming está respondendo online."""
    if not url.startswith("http"):
        return False
    async with semaphore:
        try:
            async with session.head(url, timeout=2.5, allow_redirects=True) as response:
                return response.status == 200
        except Exception:
            try:
                async with session.get(url, timeout=2.5, allow_redirects=True) as response:
                    return response.status == 200
            except Exception:
                return False

def is_adult(text):
    text_lower = text.lower()
    return any(k in text_lower for k in ADULT_KEYWORDS)

def is_vod(name, group, url):
    """Detecta se o item é um filme ou série On Demand pela URL ou Nome."""
    url_lower = url.lower()
    name_upper = name.upper()
    group_upper = group.upper()

    # Checagem 1: Extensão do arquivo na URL (.mp4, .mkv, etc)
    if url_lower.endswith(VOD_EXTENSIONS) or "/movie/" in url_lower or "/series/" in url_lower:
        return True

    # Checagem 2: Palavras-chave de VOD na Categoria ou Nome
    if any(k in group_upper for k in ["VOD", "FILMES", "SERIES", "NETFLIX", "PRIME", "HBO MAX"]):
        if "24/7" not in group_upper: # Permite canais 24 horas contínuos
            return True

    # Checagem 3: Padrões de ano, temporada e dublagem no nome do título
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

    # Elimina Conteúdo Adulto ou VODs
    if is_adult(group) or is_adult(name) or is_vod(name, group, url):
        return None

    group_upper = group.upper()
    name_upper = name.upper()

    # Categorização de Canais de TV Ao Vivo
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
        print(f"Total bruto de linhas/itens lidos: {len(channels)}")

        # Filtragem por regras
        live_channels = []
        for ch in channels:
            classified = classify_channel(ch)
            if classified:
                live_channels.append(classified)

        print(f"Canais de TV Ao Vivo restantes após filtro de VOD e Adultos: {len(live_channels)}")

        # Verificação online simultânea
        print("Iniciando testes de sinal online...")
        semaphore = asyncio.Semaphore(100)
        
        async def verify(ch):
            online = await check_stream(session, ch["url"], semaphore)
            return ch if online else None

        tasks = [verify(ch) for ch in live_channels]
        results = await asyncio.gather(*tasks)
        online_channels = [ch for ch in results if ch is not None]

        print(f"Canais 100% ativos salvos: {len(online_channels)}")

        # Gravação da lista M3U limpa
        with open("lista_limpa.m3u", "w", encoding="utf-8") as f:
            f.write(f'#EXTM3U url-tvg="{EPG_BASE_URL}"\n')
            for ch in online_channels:
                extinf = re.sub(r'group-title="[^"]+"', f'group-title="{ch["group"]}"', ch["extinf"])
                if 'group-title=' not in extinf:
                    extinf = extinf.replace("#EXTINF:-1", f'#EXTINF:-1 group-title="{ch["group"]}"')
                f.write(f"{extinf}\n{ch['url']}\n")

        print("Arquivo 'lista_limpa.m3u' gerado com sucesso!")

if __name__ == "__main__":
    asyncio.run(main())
