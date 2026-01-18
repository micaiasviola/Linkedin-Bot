import os
import json
import re
import time
import urllib.parse
import asyncio
import datetime
import random  # Import essencial para a "humanização" do bot (Jitter)
from playwright.async_api import async_playwright

# ================= CONFIGURAÇÕES GERAIS =================
# Caminho absoluto pra garantir que funcione no Windows sem dor de cabeça
USER_DATA_DIR = os.path.abspath(os.path.join(os.getcwd(), "navegador_robo"))
CAMINHO_HISTORICO = os.path.join(os.getcwd(), "data", "historico_vagas.json")

RESULTADOS_POR_PAGINA = 25
MAX_PAGINAS_SEM_NOVIDADE = 2  # Se passar 2 páginas só com vaga velha, a gente para pra não perder tempo

# --- SISTEMA DE RANKING (A IA DO PENTE FINO) ---
# Se tiver isso no título, ganha ponto
KEYWORDS_POSITIVAS = [
    "python", "django", "flask", "fastapi", "pandas", 
    "junior", "júnior", "jr", "estagio", "estágio", "trainee", "entry level"
]

# Se tiver isso, perde ponto (mas não é eliminado na hora)
KEYWORDS_NEGATIVAS = [
    "senior", "pleno" 
]

# --- O FILTRO "ANTI-SÊNIOR" ---
# Regex parruda pra barrar vaga que pede Tech Lead pagando de Jr.
BLACKLIST_RE = re.compile(
    r"(senior|sênior|sr\.?|pleno|lead|tech lead|líder|principal|staff|head|manager|gerente|gestor|coordenador|expert|architect|arquiteto|\biii\b|\biv\b|\bv\b)",
    re.I
)

# Pega o ID numérico da vaga na URL
JOB_ID_RE = re.compile(r"/jobs/view/(\d+)")

# ================= LOGGING (FICA BONITO NO TERMINAL) =================
def log_terminal(msg, tipo="INFO"):
    """
    Funçãozinha pra colorir o terminal. Ajuda muito no debug visual
    enquanto o Streamlit tá rodando no navegador.
    """
    now = datetime.datetime.now().strftime("%H:%M:%S")
    # Códigos ANSI para cores
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

# ================= GERENCIAMENTO DE ESTADO (JSON) =================
def carregar_historico_global():
    # Se não tiver arquivo, começa do zero
    if not os.path.exists(CAMINHO_HISTORICO): return set()
    try:
        with open(CAMINHO_HISTORICO, "r", encoding="utf-8") as f:
            dados = json.load(f)
            # Garante que retorna um set pra busca ser O(1)
            if isinstance(dados, list): return {l.rstrip("/") for l in dados}
            return set()
    except: return set()

def salvar_historico_global(historico: set):
    # Cria a pasta data se o usuário deletou sem querer
    os.makedirs(os.path.dirname(CAMINHO_HISTORICO), exist_ok=True)
    with open(CAMINHO_HISTORICO, "w", encoding="utf-8") as f:
        # Salva ordenado pra ficar fácil de ler se abrir no bloco de notas
        json.dump(sorted(list(historico)), f, indent=2)

# ================= LÓGICA DE SCORE =================
def calcular_score_detalhado(titulo):
    """
    Aqui a gente define se a vaga é 'Quente' ou 'Fria'.
    Retorna a nota (0-100) e o motivo pra exibir na UI.
    """
    score = 50 # Começa neutro
    detalhes = []
    titulo_lower = titulo.lower()
    
    # Bonificação
    for word in KEYWORDS_POSITIVAS:
        if word in titulo_lower: 
            score += 15
            detalhes.append(f"{word}")
            
    # Penalização
    for word in KEYWORDS_NEGATIVAS:
        if word in titulo_lower: 
            score -= 20
            detalhes.append(f"-{word}")
            
    # Trava entre 0 e 100 pra não quebrar o CSS depois
    final_score = max(0, min(100, score))
    motivo_str = ", ".join(detalhes) if detalhes else "Base(50)"
    return final_score, motivo_str

def normalizar_link(href: str):
    # Limpa aquelas URLs sujas do LinkedIn cheias de tracking params
    if not href: return None
    match = JOB_ID_RE.search(href)
    if not match: return None
    return f"https://www.linkedin.com/jobs/view/{match.group(1)}"

# ================= CORE DO ROBÔ (ASYNC) =================
async def _buscar_vagas_async(historico, termo_usuario, filtro_tempo, max_paginas, salvar_historico, queue, ordenar_por_data=False):
    context = None # Inicializa vazio pra evitar erro no finally
    try:
        query = termo_usuario or "Desenvolvedor Junior"
        # O pulo do gato: já filtra Senior na query pro LinkedIn nem trazer lixo
        q = urllib.parse.quote(f"{query} NOT (Senior OR Pleno OR Lead)")
        
        log_terminal(f"=== INICIANDO HUNTER PRO (MODO HUMANIZADO) ===", "INFO")
        
        paginas_sem_novidade = 0
        novos_links_sessao = set()

        async with async_playwright() as p:
            log_terminal("Abrindo navegador...", "INFO")
            # Usa contexto persistente pra manter cookies e sessão logada (menos chance de captcha)
            context = await p.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR, headless=False, channel="chrome",
                args=["--start-maximized", "--disable-blink-features=AutomationControlled"], viewport=None
            )
            
            # Reutiliza a aba aberta se tiver, senão cria nova
            if len(context.pages) > 0: page = context.pages[0]
            else: page = await context.new_page()

            for pagina in range(max_paginas):
                # Se o usuário clicou em Parar no App, isso aqui levanta exceção e mata o loop
                if asyncio.current_task().cancelled(): raise asyncio.CancelledError()

                # --- ESTRATÉGIA ANTI-BAN (HUMANIZAÇÃO) ---
                # Robô não clica na pág 2 em 0.1ms. A gente espera um pouco.
                if pagina > 0:
                    pausa = random.uniform(2.1, 4.5)
                    log_terminal(f"Lendo página {pagina}... (Pausa humana de {pausa:.1f}s)", "DEBUG")
                    await asyncio.sleep(pausa)

                offset = pagina * RESULTADOS_POR_PAGINA
                base_url = f"https://www.linkedin.com/jobs/search?keywords={q}&location=Brazil&geoId=106057199&f_AL=true&f_TPR={filtro_tempo}&start={offset}"
                
                # Se o usuário quer novidade, força ordenação por DATA (fura o algoritmo de relevância)
                if ordenar_por_data: base_url += "&sortBy=DD"
                
                log_terminal(f"--- Processando PÁGINA {pagina + 1} ---", "INFO")
                # Manda aviso pra UI
                await queue.put(([], f"🔄 Lendo página {pagina + 1}..."))
                
                try:
                    await page.goto(base_url, timeout=30000)
                    
                    # --- SCROLL IMPERFEITO (HUMANIZAÇÃO PT. 2) ---
                    # Nada de rolar fixo. Varia a quantidade e o tempo pra parecer uma pessoa lendo.
                    steps = random.randint(3, 5)
                    for _ in range(steps): 
                        scroll_amount = random.randint(700, 1200)
                        await page.mouse.wheel(0, scroll_amount)
                        await asyncio.sleep(random.uniform(0.5, 1.2))
                        
                except Exception as e:
                    log_terminal(f"Erro navegação: {e}", "ERROR")
                    await queue.put(([], f"⚠️ Erro navegação: {e}"))
                    continue

                # Seleciona todas as vagas visíveis
                links_el = await page.locator("a[href*='/jobs/view/']").all()
                total_encontrados = len(links_el)
                log_terminal(f"Links na página: {total_encontrados}", "DEBUG")

                # Se achou pouco link, provavelmente o LinkedIn bloqueou ou acabou a lista
                if total_encontrados < 2:
                    log_terminal("Fim da lista detectado.", "WARN")
                    await queue.put(([], f"⚠️ Fim da lista detectado."))
                    break

                novas = []
                count_sucesso = 0
                
                # Processa cada vaga encontrada
                for el in links_el:
                    href = await el.get_attribute("href")
                    titulo = (await el.inner_text() or "Vaga sem titulo").strip()
                    link = normalizar_link(href)
                    
                    if not link: continue
                    
                    # Já vimos essa? Pula.
                    if link in historico: continue
                    
                    # Passou no filtro anti-sênior?
                    if BLACKLIST_RE.search(f"{titulo} {link.lower()}"): continue

                    score, motivo = calcular_score_detalhado(titulo)

                    historico.add(link)
                    novos_links_sessao.add(link)
                    novas.append({"titulo": titulo, "link": link, "score": score, "motivo": motivo})
                    count_sucesso += 1

                log_terminal(f"Resumo Pág {pagina+1}: {count_sucesso} Novas", "SUCCESS" if count_sucesso else "INFO")

                if novas:
                    # Ordena as da página atual antes de mandar
                    novas.sort(key=lambda x: x['score'], reverse=True)
                    await queue.put((novas, f"✅ Pág {pagina+1}: +{len(novas)} vagas"))
                    paginas_sem_novidade = 0
                else:
                    await queue.put(([], f"⚪ Pág {pagina+1}: Sem novidades"))
                    paginas_sem_novidade += 1

                # Proteção pra não ficar rodando infinito se não tiver nada novo
                if paginas_sem_novidade >= MAX_PAGINAS_SEM_NOVIDADE:
                    log_terminal("Parando busca (Sem novidades).", "WARN")
                    await queue.put(([], f"✋ Parando (Sem novidades)."))
                    break
            
        # Salva tudo no final se o usuário deixou
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
        # BLINDAGEM: Garante que o navegador fecha de qualquer jeito
        if context:
            try: await context.close()
            except: pass
        # Manda sinal de fim pra UI não ficar travada
        await queue.put(None)

# ================= PONTE SYNC -> ASYNC =================
def buscar_vagas_em_lote(links_ja_vistos, termo, tempo, salvar, max_pg=10, ordenar_por_data=False):
    """
    Essa função é o wrapper pro Streamlit (que é síncrono) conseguir
    conversar com o Playwright (que é assíncrono).
    """
    historico = carregar_historico_global()
    historico.update(links_ja_vistos)
    
    queue = asyncio.Queue()
    
    # Gambiarra padrão pra pegar o loop no Windows/Streamlit
    try: loop = asyncio.get_event_loop()
    except RuntimeError: loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)

    # Dispara o robô em background
    task = loop.create_task(_buscar_vagas_async(historico, termo, tempo, max_pg, salvar, queue, ordenar_por_data))

    try:
        while True:
            # Fica ouvindo a fila. O run_until_complete faz a ponte sync.
            dados = loop.run_until_complete(queue.get())
            if dados is None: break
            yield dados
    except GeneratorExit:
        # Se o usuário clicar em PARAR no app.py, o loop quebra e cai aqui.
        # A gente cancela a tarefa pra fechar o navegador imediatamente.
        log_terminal("Interrompendo tarefa assíncrona...", "WARN")
        task.cancel()
        loop.run_until_complete(task)
        raise