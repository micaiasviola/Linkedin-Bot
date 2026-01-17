import os
import json
import re
import time
import urllib.parse
import asyncio
from playwright.async_api import async_playwright

# ================= CONFIG =================
# Caminho absoluto para evitar erros
USER_DATA_DIR = os.path.abspath(os.path.join(os.getcwd(), "navegador_robo"))
CAMINHO_HISTORICO = os.path.join(os.getcwd(), "data", "historico_vagas.json")

RESULTADOS_POR_PAGINA = 25
MAX_PAGINAS_SEM_NOVIDADE = 2

BLACKLIST_RE = re.compile(
    r"(senior|sênior|sr\.?|pleno|lead|tech lead|líder|principal|staff|head|manager|gerente|gestor|coordenador|especialista|specialist|expert|architect|arquiteto|\biii\b|\biv\b|\bv\b)",
    re.I
)

JOB_ID_RE = re.compile(r"/jobs/view/(\d+)")

# ================= HISTÓRICO =================
def carregar_historico_global():
    if not os.path.exists(CAMINHO_HISTORICO):
        return set()
    try:
        with open(CAMINHO_HISTORICO, "r", encoding="utf-8") as f:
            dados = json.load(f)
            if isinstance(dados, list):
                return {l.rstrip("/") for l in dados}
            return set()
    except:
        return set()

def salvar_historico_global(historico: set):
    os.makedirs(os.path.dirname(CAMINHO_HISTORICO), exist_ok=True)
    with open(CAMINHO_HISTORICO, "w", encoding="utf-8") as f:
        json.dump(sorted(list(historico)), f, indent=2)

# ================= HELPERS =================
def normalizar_link(href: str):
    if not href:
        return None
    match = JOB_ID_RE.search(href)
    if not match:
        return None
    return f"https://www.linkedin.com/jobs/view/{match.group(1)}"

# ================= CORE ASYNC =================
async def _buscar_vagas_async(
    historico: set,
    termo_usuario: str | None,
    filtro_tempo: str,
    max_paginas: int,
    salvar_historico: bool,
    queue: asyncio.Queue
):
    try:
        query = termo_usuario or "Desenvolvedor Junior"
        # Filtro negativo na query
        q = urllib.parse.quote(f"{query} NOT (Senior OR Pleno OR Lead)")

        paginas_sem_novidade = 0
        novos_links_sessao = set()

        async with async_playwright() as p:
            # Contexto Persistente para manter o Login
            context = await p.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR,
                headless=False,
                channel="chrome", 
                args=["--start-maximized", "--disable-blink-features=AutomationControlled"],
                viewport=None
            )
            
            if len(context.pages) > 0:
                page = context.pages[0]
            else:
                page = await context.new_page()

            for pagina in range(max_paginas):
                offset = pagina * RESULTADOS_POR_PAGINA
                url = (
                    f"https://www.linkedin.com/jobs/search?"
                    f"keywords={q}&location=Brazil&geoId=106057199"
                    f"&f_AL=true&f_TPR={filtro_tempo}&start={offset}"
                )

                t0 = time.perf_counter()
                await queue.put(([], f"🔄 Carregando página {pagina + 1}..."))
                
                try:
                    await page.goto(url, timeout=30000)
                    # Scroll
                    for _ in range(3):
                        await page.mouse.wheel(0, 1000)
                        await asyncio.sleep(0.5)
                except Exception as e:
                    await queue.put(([], f"⚠️ Erro ao carregar página: {e}"))
                    continue

                links = await page.locator("a[href*='/jobs/view/']").all()
                
                if len(links) < 2:
                    await queue.put(([], "⚠️ Fim dos resultados."))
                    break

                novas = []
                for el in links:
                    href = await el.get_attribute("href")
                    titulo = (await el.inner_text() or "").lower()
                    link = normalizar_link(href)
                    
                    if not link or link in historico: continue
                    if BLACKLIST_RE.search(f"{titulo} {link.lower()}"): continue

                    historico.add(link)
                    novos_links_sessao.add(link)
                    novas.append(link)

                dt = time.perf_counter() - t0
                
                if novas:
                    await queue.put((novas, f"✅ Pág {pagina+1}: +{len(novas)} vagas ({dt:.2f}s)"))
                    paginas_sem_novidade = 0
                else:
                    await queue.put(([], f"⚪ Pág {pagina+1}: Sem novidades."))
                    paginas_sem_novidade += 1

                if paginas_sem_novidade >= MAX_PAGINAS_SEM_NOVIDADE:
                    await queue.put(([], "✋ Parando por falta de novidades."))
                    break
            
            await context.close()

        if salvar_historico and novos_links_sessao:
            salvar_historico_global(historico)
            await queue.put(([], "💾 Histórico salvo no disco."))

    except Exception as e:
        await queue.put(([], f"❌ Erro Crítico: {str(e)}"))
    finally:
        await queue.put(None)

# ================= PONTE SÍNCRONA (CORRIGIDA) =================
# Aqui estava o erro: os nomes dos argumentos precisam ser IDÊNTICOS aos usados no app.py
def buscar_vagas_em_lote(
    links_ja_vistos_sessao: set,
    termo_usuario=None,
    filtro_tempo="r86400",
    salvar_historico=True,
    max_paginas=10
):
    historico = carregar_historico_global()
    historico.update(links_ja_vistos_sessao)
    
    queue = asyncio.Queue()

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Passamos as variáveis corretas para a função interna
    task = loop.create_task(
        _buscar_vagas_async(
            historico,
            termo_usuario,
            filtro_tempo,
            max_paginas,
            salvar_historico,
            queue
        )
    )

    while True:
        dados = loop.run_until_complete(queue.get())
        if dados is None: break
        yield dados