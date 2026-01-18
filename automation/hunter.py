import os
import json
import re
import time
import urllib.parse
import asyncio
import datetime
import random  # <--- NOVA IMPORTAÇÃO ESSENCIAL
from playwright.async_api import async_playwright

# ================= CONFIG =================
USER_DATA_DIR = os.path.abspath(os.path.join(os.getcwd(), "navegador_robo"))
CAMINHO_HISTORICO = os.path.join(os.getcwd(), "data", "historico_vagas.json")

RESULTADOS_POR_PAGINA = 25
MAX_PAGINAS_SEM_NOVIDADE = 2

# --- CONFIGURAÇÃO DE RANKING ---
KEYWORDS_POSITIVAS = [
    "python", "django", "flask", "fastapi", "pandas", 
    "junior", "júnior", "jr", "estagio", "estágio", "trainee", "entry level"
]

KEYWORDS_NEGATIVAS = [
    "java", "c#", ".net", "php", "ruby", "senior", "pleno" 
]

BLACKLIST_RE = re.compile(
    r"(senior|sênior|sr\.?|pleno|lead|tech lead|líder|principal|staff|head|manager|gerente|gestor|coordenador|especialista|specialist|expert|architect|arquiteto|\biii\b|\biv\b|\bv\b)",
    re.I
)

JOB_ID_RE = re.compile(r"/jobs/view/(\d+)")

# ================= LOGGING DETALHADO =================
def log_terminal(msg, tipo="INFO"):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    
    prefix = f"{BOLD}[{now}]{RESET}"
    if tipo == "INFO": print(f"{prefix} {CYAN}ℹ️  {msg}{RESET}")
    elif tipo == "SUCCESS": print(f"{prefix} {GREEN}✅ {msg}{RESET}")
    elif tipo == "WARN": print(f"{prefix} {YELLOW}⚠️  {msg}{RESET}")
    elif tipo == "ERROR": print(f"{prefix} {RED}❌ {msg}{RESET}")
    elif tipo == "DEBUG": print(f"{prefix} {WHITE}🔧 {msg}{RESET}")

# ================= HISTÓRICO & SCORE =================
def carregar_historico_global():
    if not os.path.exists(CAMINHO_HISTORICO): return set()
    try:
        with open(CAMINHO_HISTORICO, "r", encoding="utf-8") as f:
            dados = json.load(f)
            if isinstance(dados, list): return {l.rstrip("/") for l in dados}
            return set()
    except: return set()

def salvar_historico_global(historico: set):
    os.makedirs(os.path.dirname(CAMINHO_HISTORICO), exist_ok=True)
    with open(CAMINHO_HISTORICO, "w", encoding="utf-8") as f:
        json.dump(sorted(list(historico)), f, indent=2)

def calcular_score_detalhado(titulo):
    score = 50
    detalhes = []
    titulo_lower = titulo.lower()
    
    for word in KEYWORDS_POSITIVAS:
        if word in titulo_lower: 
            score += 15
            detalhes.append(f"{word}")
            
    for word in KEYWORDS_NEGATIVAS:
        if word in titulo_lower: 
            score -= 20
            detalhes.append(f"-{word}")
            
    final_score = max(0, min(100, score))
    motivo_str = ", ".join(detalhes) if detalhes else "Base(50)"
    return final_score, motivo_str

def normalizar_link(href: str):
    if not href: return None
    match = JOB_ID_RE.search(href)
    if not match: return None
    return f"https://www.linkedin.com/jobs/view/{match.group(1)}"

# ================= CORE ASYNC (HUMANIZADO) =================
async def _buscar_vagas_async(historico, termo_usuario, filtro_tempo, max_paginas, salvar_historico, queue, ordenar_por_data=False):
    context = None
    try:
        query = termo_usuario or "Desenvolvedor Junior"
        q = urllib.parse.quote(f"{query} NOT (Senior OR Pleno OR Lead)")
        
        log_terminal(f"=== INICIANDO HUNTER PRO (MODO HUMANIZADO) ===", "INFO")
        
        paginas_sem_novidade = 0
        novos_links_sessao = set()

        async with async_playwright() as p:
            log_terminal("Abrindo navegador...", "INFO")
            context = await p.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR, headless=False, channel="chrome",
                args=["--start-maximized", "--disable-blink-features=AutomationControlled"], viewport=None
            )
            
            if len(context.pages) > 0: page = context.pages[0]
            else: page = await context.new_page()

            for pagina in range(max_paginas):
                if asyncio.current_task().cancelled(): raise asyncio.CancelledError()

                # --- NOVO: Pausa aleatória entre páginas (Humanização) ---
                if pagina > 0:
                    pausa = random.uniform(2.1, 4.5)
                    log_terminal(f"Lendo página {pagina}... (Pausa humana de {pausa:.1f}s)", "DEBUG")
                    await asyncio.sleep(pausa)

                offset = pagina * RESULTADOS_POR_PAGINA
                base_url = f"https://www.linkedin.com/jobs/search?keywords={q}&location=Brazil&geoId=106057199&f_AL=true&f_TPR={filtro_tempo}&start={offset}"
                if ordenar_por_data: base_url += "&sortBy=DD"
                
                log_terminal(f"--- Processando PÁGINA {pagina + 1} ---", "INFO")
                await queue.put(([], f"🔄 Lendo página {pagina + 1}..."))
                
                try:
                    await page.goto(base_url, timeout=30000)
                    
                    # --- NOVO: Scroll "Imperfeito" (Humanização) ---
                    # Em vez de rolar 3 vezes fixas, rola entre 3 e 5 vezes com tempos variados
                    steps = random.randint(3, 5)
                    for _ in range(steps): 
                        # Rola uma quantidade aleatória de pixels
                        scroll_amount = random.randint(700, 1200)
                        await page.mouse.wheel(0, scroll_amount)
                        # Espera um tempo aleatório
                        await asyncio.sleep(random.uniform(0.5, 1.2))
                        
                except Exception as e:
                    log_terminal(f"Erro navegação: {e}", "ERROR")
                    await queue.put(([], f"⚠️ Erro navegação: {e}"))
                    continue

                links_el = await page.locator("a[href*='/jobs/view/']").all()
                total_encontrados = len(links_el)
                log_terminal(f"Links na página: {total_encontrados}", "DEBUG")

                if total_encontrados < 2:
                    log_terminal("Fim da lista detectado.", "WARN")
                    await queue.put(([], f"⚠️ Fim da lista detectado."))
                    break

                novas = []
                count_blacklist = 0
                count_historico = 0
                count_sucesso = 0
                
                for el in links_el:
                    href = await el.get_attribute("href")
                    titulo = (await el.inner_text() or "Vaga sem titulo").strip()
                    link = normalizar_link(href)
                    
                    if not link: continue
                    if link in historico: 
                        count_historico += 1
                        continue
                    if BLACKLIST_RE.search(f"{titulo} {link.lower()}"): 
                        count_blacklist += 1
                        continue

                    score, motivo = calcular_score_detalhado(titulo)

                    historico.add(link)
                    novos_links_sessao.add(link)
                    novas.append({"titulo": titulo, "link": link, "score": score, "motivo": motivo})
                    count_sucesso += 1

                log_terminal(f"Resumo Pág {pagina+1}: {count_sucesso} Novas | {count_historico} Repetidas", "SUCCESS" if count_sucesso else "INFO")

                if novas:
                    novas.sort(key=lambda x: x['score'], reverse=True)
                    await queue.put((novas, f"✅ Pág {pagina+1}: +{len(novas)} vagas"))
                    paginas_sem_novidade = 0
                else:
                    await queue.put(([], f"⚪ Pág {pagina+1}: Sem novidades"))
                    paginas_sem_novidade += 1

                if paginas_sem_novidade >= MAX_PAGINAS_SEM_NOVIDADE:
                    log_terminal("Parando busca (Sem novidades).", "WARN")
                    await queue.put(([], f"✋ Parando (Sem novidades)."))
                    break
            
        if salvar_historico and novos_links_sessao:
            salvar_historico_global(historico)
            log_terminal(f"Banco de dados atualizado (+{len(novos_links_sessao)} vagas).", "SUCCESS")
            await queue.put(([], "💾 Salvo no disco."))

    except asyncio.CancelledError:
        log_terminal("Tarefa cancelada pelo usuário!", "WARN")
    except Exception as e:
        log_terminal(f"Erro Crítico: {str(e)}", "ERROR")
        await queue.put(([], f"❌ Erro: {str(e)}"))
    finally:
        if context:
            try: await context.close()
            except: pass
        await queue.put(None)

def buscar_vagas_em_lote(links_ja_vistos, termo, tempo, salvar, max_pg=10, ordenar_por_data=False):
    historico = carregar_historico_global()
    historico.update(links_ja_vistos)
    
    queue = asyncio.Queue()
    try: loop = asyncio.get_event_loop()
    except RuntimeError: loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)

    task = loop.create_task(_buscar_vagas_async(historico, termo, tempo, max_pg, salvar, queue, ordenar_por_data))

    try:
        while True:
            dados = loop.run_until_complete(queue.get())
            if dados is None: break
            yield dados
    except GeneratorExit:
        log_terminal("Interrompendo tarefa assíncrona...", "WARN")
        task.cancel()
        loop.run_until_complete(task)
        raise