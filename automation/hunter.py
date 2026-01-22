import os
import json
import re
import time
import urllib.parse
import asyncio
import datetime
import random
from playwright.async_api import async_playwright

# ================= CONFIGURAÇÕES =================
USER_DATA_DIR = os.path.abspath(os.path.join(os.getcwd(), "navegador_robo"))
CAMINHO_HISTORICO = os.path.join(os.getcwd(), "data", "historico_vagas.json")
RESULTADOS_POR_PAGINA = 25
MAX_PAGINAS_SEM_NOVIDADE = 2

KEYWORDS_POSITIVAS = [
    # Níveis e Vínculos
    "python", "django", "flask", "fastapi", "pandas", "junior", "júnior", "jr", 
    "estagio", "estágio", "trainee", "entry level", "desenvolvedor", "developer", 
    "software", "associate", "analista", "vaga", "oportunidade", "remoto", "remote",
    
    # Backend e Linguagens Complementares
    "backend", "back-end", "fullstack", "full-stack", "node", "nodejs", "javascript", 
    "js", "typescript", "ts", "java", "spring", "c#", "dotnet", "net core", "go", "golang",
    
    # APIs e Integrações
    "api", "rest", "restful", "graphql", "soap", "json", "webhooks", "microserviços", 
    "microservices", "serverless",
    
    # Bancos de Dados
    "sql", "postgresql", "postgres", "mysql", "mariadb", "sqlite", "mongodb", "nosql", 
    "redis", "elasticsearch", "orm", "sqlalchemy", "prisma",
    
    # DevOps e Nuvem
    "docker", "docker-compose", "kubernetes", "k8s", "aws", "amazon web services", 
    "azure", "gcp", "google cloud", "cloud", "devops", "ci/cd", "jenkins", 
    "github actions", "terraform", "linux", "bash", "unix",
    
    # Ferramentas e Versão
    "git", "github", "gitlab", "bitbucket", "svn", "versionamento", "jira", "trello",
    
    # Testes e Qualidade
    "qa", "testes", "testing", "pytest", "unittest", "tdd", "bdd", "selenium", 
    "cypress", "clean code", "solid", "dry", "design patterns",
    
    # Metodologias e Soft Skills
    "agile", "agil", "scrum", "kanban", "lean", "prazos", "documentação", 
    "code review", "refatoração", "refactoring"]

KEYWORDS_NEGATIVAS = ["senior", "pleno", "sr", "lead", "tech lead"]

# --- FILTRO 1: BLACKLIST DE PALAVRAS (Busca Geral) ---
BLACKLIST_RE = re.compile(r"(senior|sênior|sr\.?|pleno|lead|tech lead|líder|principal|staff|head|manager|gerente|gestor|coordenador|expert|architect|arquiteto|\biii\b|\biv\b|\bv\b)", re.I)

# --- FILTRO 2: BLACKLIST DE CARGOS IRRELEVANTES (O Pente Fino Real) ---
BLACKLIST_TITULOS_IRRELEVANTES = [
    "vendas", "sales", "vendedor", "consultor", "executivo", "sdr", "closer", "comercial", 
    "civil", "elétrica", "mecânica", "produção", "química", "ambiental", 
    "sap", "erp", "totvs", "protheus", "winthor", 
    "suporte", "support", "help desk", "service desk", 
    "recrutador", "recruiter", "rh", "talent", "human resources", 
    "marketing", "design", "designer", "social media", "conteúdo", 
    "administrativo", "assistente", "auxiliar", "recepcionista", 
    "comprador", "banco de talentos", "banco de currículos", "vaga afirmativa"
]

JOB_ID_RE = re.compile(r"/jobs/view/(\d+)")

def log_terminal(msg, tipo="INFO"):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    colors = {"INFO": "\033[96m", "SUCCESS": "\033[92m", "WARN": "\033[93m", "ERROR": "\033[91m", "DEBUG": "\033[97m"}
    reset = "\033[0m"
    print(f"{colors.get(tipo, '')}[{now}] {msg}{reset}")

# ================= FUNÇÕES DE CAMUFLAGEM E VISUAIS =================

async def aplicar_stealth_manual(page):
    """
    Injeta scripts para esconder propriedades que identificam automação (WebDriver).
    Substitui a necessidade da biblioteca externa playwright-stealth.
    """
    await page.add_init_script("""
        // 1. Esconder navigator.webdriver (O mais importante)
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });

        // 2. Emular plugins (robôs geralmente têm lista vazia)
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });

        // 3. Emular window.chrome
        window.chrome = { runtime: {} };

        // 4. Mascarar permissões
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
        );
    """)

async def instalar_cursor_vermelho(page):
    await page.add_init_script("""
        const box = document.createElement('div');
        box.classList.add('mouse-helper');
        const styleElement = document.createElement('style');
        styleElement.innerHTML = `
            .mouse-helper {
                pointer-events: none;
                position: absolute;
                top: 0;
                left: 0;
                width: 20px;
                height: 20px;
                background: rgba(255, 0, 0, 0.4);
                border: 1px solid white;
                border-radius: 50%;
                margin-left: -10px;
                margin-top: -10px;
                transition: background .2s, border-radius .2s, border-color .2s;
                z-index: 999999;
            }
        `;
        document.head.appendChild(styleElement);
        document.body.appendChild(box);
        document.addEventListener('mousemove', event => {
            box.style.left = event.pageX + 'px';
            box.style.top = event.pageY + 'px';
        }, true);
    """)

async def human_scroll(page):
    try:
        await page.mouse.move(random.randint(300, 800), random.randint(300, 600), steps=10)
        for _ in range(random.randint(2, 4)):
            await page.keyboard.press("PageDown")
            await asyncio.sleep(random.uniform(1.0, 2.0))
            await page.mouse.wheel(0, random.randint(300, 600))
            await asyncio.sleep(random.uniform(0.5, 1.0))
            if random.random() < 0.3:
                await page.mouse.wheel(0, -random.randint(100, 200))
                await asyncio.sleep(0.5)
    except: pass

async def human_mouse_move(page):
    try:
        width = page.viewport_size['width']
        height = page.viewport_size['height']
        for _ in range(random.randint(3, 5)):
            x = random.randint(100, width - 100)
            y = random.randint(100, height - 100)
            await page.mouse.move(x, y, steps=random.randint(20, 50)) 
            await asyncio.sleep(random.uniform(0.1, 0.3))
    except: pass

# ================= DADOS =================
def carregar_historico_completo():
    if not os.path.exists(CAMINHO_HISTORICO): return []
    try:
        with open(CAMINHO_HISTORICO, "r", encoding="utf-8") as f:
            dados = json.load(f)
            lista_final = []
            for item in dados:
                if isinstance(item, str): 
                    lista_final.append({"titulo": "Vaga Antiga", "link": item, "score": 0, "status": "Pendente"})
                elif isinstance(item, dict):
                    lista_final.append(item)
            return lista_final
    except: return []

def salvar_historico_completo(lista_vagas):
    os.makedirs(os.path.dirname(CAMINHO_HISTORICO), exist_ok=True)
    with open(CAMINHO_HISTORICO, "w", encoding="utf-8") as f:
        seen = set()
        unique = []
        for d in lista_vagas:
            if d['link'] not in seen:
                seen.add(d['link'])
                unique.append(d)
        json.dump(unique, f, indent=2)

def carregar_historico_global():
    return {v['link'] for v in carregar_historico_completo()}

def calcular_score_detalhado(titulo):
    score, detalhes = 50, []
    t = titulo.lower()
    for w in KEYWORDS_POSITIVAS: 
        if w in t: score += 15; detalhes.append(w)
    for w in KEYWORDS_NEGATIVAS: 
        if w in t: score -= 20; detalhes.append(f"-{w}")
    return max(0, min(100, score)), ", ".join(detalhes) if detalhes else "Base(50)"

def normalizar_link(href):
    m = JOB_ID_RE.search(href or "")
    return f"https://www.linkedin.com/jobs/view/{m.group(1)}" if m else None

# ================= CORE BUSCADOR (BLINDADO) =================
async def _buscar_vagas_async(historico_links, termo_usuario, filtro_tempo, max_paginas, salvar_historico, queue, ordenar_por_data=False):
    context = None
    try:
        # Se o usuário não usar title:, injetamos um filtro básico
        query = termo_usuario or "Desenvolvedor Junior"
        q = urllib.parse.quote(query) if "title:" in query else urllib.parse.quote(f"{query} NOT (Senior OR Pleno)")
        
        log_terminal(f"=== INICIANDO HUNTER PRO (MODE: STEALTH MANUAL) ===", "INFO")
        
        paginas_sem_novidade = 0
        novos_links_sessao = []

        async with async_playwright() as p:
            log_terminal("Abrindo navegador camuflado...", "INFO")
            
            # --- Argumentos de Camuflagem Pesada ---
            args_camuflagem = [
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--exclude-switches=enable-automation",
                "--disable-extensions",
                "--password-store=basic",
                "--use-mock-keychain",
                "--disable-session-crashed-bubble", 
                "--hide-scrollbars", 
            ]

            context = await p.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR,
                headless=False,
                channel="chrome",
                args=args_camuflagem,
                # --- Viewport None para maximização real (EVITA DETECÇÃO) ---
                viewport=None,
                ignore_default_args=["--enable-automation"],
                # User Agent forçado (Windows 10/Chrome 120) para garantir consistência
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            if len(context.pages) > 0: page = context.pages[0]
            else: page = await context.new_page()

            # --- APLICAÇÃO MANUAL DO STEALTH ---
            await aplicar_stealth_manual(page)
            
            await instalar_cursor_vermelho(page)

            for pagina in range(max_paginas):
                if asyncio.current_task().cancelled(): raise asyncio.CancelledError()

                if pagina > 0:
                    pausa = random.uniform(4.0, 8.0)
                    log_terminal(f"Trocando página... (Aguardando {pausa:.1f}s)", "DEBUG")
                    await asyncio.sleep(pausa)

                offset = pagina * RESULTADOS_POR_PAGINA
                base_url = f"https://www.linkedin.com/jobs/search?keywords={q}&location=Brazil&geoId=106057199&f_AL=true&f_TPR={filtro_tempo}&start={offset}"
                if ordenar_por_data: base_url += "&sortBy=DD"
                
                log_terminal(f"--- Processando PÁGINA {pagina + 1} ---", "INFO")
                await queue.put(([], f"🔄 Lendo página {pagina + 1}..."))
                
                try:
                    await page.goto(base_url, timeout=30000, wait_until='domcontentloaded')
                    
                    # Movimento humano antes de processar
                    await human_mouse_move(page) 
                    await human_scroll(page)
                except Exception as e:
                    await queue.put(([], f"⚠️ Erro navegação: {e}"))
                    continue

                try: await page.wait_for_selector("a[href*='/jobs/view/']", timeout=5000)
                except: pass

                links_el = await page.locator("a[href*='/jobs/view/']").all()
                
                if len(links_el) < 2:
                    # Espera extra caso o LinkedIn esteja lento
                    await asyncio.sleep(2)
                    links_el = await page.locator("a[href*='/jobs/view/']").all()

                if len(links_el) < 2:
                    await queue.put(([], f"⚠️ Fim da lista ou Bloqueio detectado."))
                    break

                novas_na_pagina = [] 
                
                for el in links_el:
                    href = await el.get_attribute("href")
                    titulo = (await el.inner_text() or "Vaga sem titulo").strip()
                    link = normalizar_link(href)
                    
                    if not link: continue
                    if link in historico_links: continue
                    
                    titulo_lower = titulo.lower()
                    
                    # 1. Filtro de Sênior/Pleno
                    if BLACKLIST_RE.search(f"{titulo} {link.lower()}"): continue
                    
                    # 2. Filtro de Áreas Irrelevantes
                    if any(bad_word in titulo_lower for bad_word in BLACKLIST_TITULOS_IRRELEVANTES):
                        continue

                    score, motivo = calcular_score_detalhado(titulo)
                    
                    vaga_obj = {
                        "titulo": titulo, 
                        "link": link, 
                        "score": score, 
                        "motivo": motivo,
                        "status": "Pendente",
                        "data_encontro": datetime.datetime.now().strftime("%d/%m/%Y")
                    }

                    historico_links.add(link)
                    novos_links_sessao.append(vaga_obj)
                    novas_na_pagina.append(vaga_obj)

                if novas_na_pagina:
                    novas_na_pagina.sort(key=lambda x: x['score'], reverse=True)
                    await queue.put((novas_na_pagina, f"✅ Pág {pagina+1}: +{len(novas_na_pagina)} vagas"))
                    paginas_sem_novidade = 0
                else:
                    await queue.put(([], f"⚪ Pág {pagina+1}: Sem novidades"))
                    paginas_sem_novidade += 1

                if paginas_sem_novidade >= MAX_PAGINAS_SEM_NOVIDADE:
                    await queue.put(([], f"✋ Parando (Sem novidades)."))
                    break
            
        if salvar_historico and novos_links_sessao:
            todos_dados = carregar_historico_completo()
            todos_dados.extend(novos_links_sessao)
            salvar_historico_completo(todos_dados)
            log_terminal(f"Salvo +{len(novos_links_sessao)} vagas no disco.", "SUCCESS")
            await queue.put(([], "💾 Salvo no disco."))

    except asyncio.CancelledError: log_terminal("Tarefa cancelada!", "WARN")
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
            try:
                dados = loop.run_until_complete(queue.get())
                if dados is None: break
                yield dados
            except RuntimeError: break
    except GeneratorExit:
        log_terminal("Interrompendo...", "WARN")
        task.cancel()
        try: loop.run_until_complete(task)
        except (asyncio.CancelledError, OSError, RuntimeError, Exception): pass
        raise