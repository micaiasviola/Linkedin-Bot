import os
import asyncio
import random
import datetime
import re
from playwright.async_api import async_playwright

USER_DATA_DIR = os.path.abspath(os.path.join(os.getcwd(), "navegador_robo"))

def log_terminal(msg, tipo="INFO"):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    colors = {"INFO": "\033[96m", "SUCCESS": "\033[92m", "WARN": "\033[93m", "ERROR": "\033[91m", "DEBUG": "\033[97m"}
    reset = "\033[0m"
    print(f"{colors.get(tipo, '')}[{now}] {msg}{reset}")

# ================= FUNÇÕES DE CAMUFLAGEM =================

async def aplicar_stealth_manual(page):
    """
    Injeta scripts para esconder propriedades que identificam automação (WebDriver).
    Igual ao robô Hunter, garantindo consistência na sessão.
    """
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        window.chrome = { runtime: {} };
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
        );
    """)

# ================= COMPORTAMENTO HUMANO =================

async def human_scroll(page):
    """
    Simula um humano rolando a página para ler a descrição da vaga.
    Faz pausas aleatórias e move o mouse.
    """
    try:
        # Pega a altura total da página
        scroll_height = await page.evaluate("document.body.scrollHeight")
        current_scroll = 0
        
        # Define quantos "tombos" de scroll vamos dar (entre 3 e 7 vezes)
        steps = random.randint(3, 7)
        
        for _ in range(steps):
            if current_scroll >= scroll_height:
                break

            # Define o quanto vai rolar (um pouco aleatório)
            scroll_step = random.randint(300, 600)
            current_scroll += scroll_step
            
            # Rola a página suavemente (Javascript scroll)
            await page.evaluate(f"window.scrollTo({{top: {current_scroll}, behavior: 'smooth'}})")
            
            # Move o mouse aleatoriamente enquanto lê
            try:
                await page.mouse.move(
                    random.randint(100, 800), 
                    random.randint(200, 600), 
                    steps=random.randint(10, 30)
                )
            except: pass
            
            # Pausa para "ler" o trecho (entre 0.8s e 2.5s)
            await asyncio.sleep(random.uniform(0.8, 2.5))
            
    except Exception as e:
        # Se der erro no scroll, não quebra o fluxo, apenas segue
        pass

# ================= CORE DA AUDITORIA =================

async def _auditar_async(lista_vagas, queue):
    context = None
    try:
        log_terminal("=== INICIANDO AUDITORIA (LÓGICA VISUAL CORRIGIDA 👁️) ===", "INFO")
        
        async with async_playwright() as p:
            args_camuflagem = [
                "--start-maximized",
                "--window-size=1920,1080",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--exclude-switches=enable-automation",
                "--disable-extensions",
                "--password-store=basic",
                "--use-mock-keychain",
                "--hide-scrollbars",
            ]

            context = await p.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR, 
                headless=False, 
                channel="chrome",
                args=args_camuflagem,
                viewport=None, 
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                ignore_default_args=["--enable-automation"]
            )
            
            if len(context.pages) > 0: page = context.pages[0]
            else: page = await context.new_page()

            await aplicar_stealth_manual(page)

            total = len(lista_vagas)
            
            for i, vaga in enumerate(lista_vagas):
                if asyncio.current_task().cancelled(): raise asyncio.CancelledError()
                
                link = vaga.get('link')
                if not link: continue

                # Pausa humana
                await asyncio.sleep(random.uniform(3.0, 6.0))
                
                await queue.put((None, f"🕵️ [{i+1}/{total}] Visitando: {vaga.get('titulo', 'Vaga')[:30]}..."))
                
                try:
                    await page.goto(link, timeout=30000)
                    await asyncio.sleep(random.uniform(2.0, 4.0))
                    await human_scroll(page)

                    # ==========================================================
                    #  CORREÇÃO: USO DE .first PARA EVITAR ERRO DE DUPLICIDADE
                    # ==========================================================
                    
                    status_detectado = "Indefinido"

                    # 1. Procura pelos BOTÕES DE AÇÃO (Sinal de que NÃO APLICOU)
                    # Adicionado .first para pegar o primeiro botão caso haja duplicatas na tela
                    
                    tem_botao_easy = await page.locator("button", has_text=re.compile(r"Candidatura simplificada", re.I)).first.is_visible()
                    
                    tem_botao_normal = await page.locator("a.jobs-apply-button", has_text=re.compile(r"Candidatar-se", re.I)).first.is_visible()
                    
                    # Às vezes o botão normal é um <button> e não <a>, verificamos ambos
                    tem_botao_normal_alt = await page.locator("button.jobs-apply-button", has_text=re.compile(r"Candidatar-se", re.I)).first.is_visible()

                    # 2. Procura por SINAIS DE SUCESSO (Passado)
                    texto_sucesso = await page.locator("span", has_text=re.compile(r"(Candidatura enviada|Application submitted)", re.I)).first.is_visible()
                    
                    # Verifica a barra de data de candidatura (topo do card)
                    tem_data_topo = await page.locator(".jobs-s-apply__application-date").first.is_visible()

                    # 3. Procura por VAGA FECHADA
                    vaga_fechada = await page.locator("text=Não aceita mais candidaturas").first.is_visible()

                    # --- DECISÃO LÓGICA ---
                    
                    if tem_data_topo or texto_sucesso:
                        status_detectado = "Aplicado ✅"
                        log_terminal(f"Resultado: {vaga.get('titulo')[:20]} -> JÁ APLICADO", "SUCCESS")
                    
                    elif tem_botao_easy or tem_botao_normal or tem_botao_normal_alt:
                        status_detectado = "Não Aplicado ❌"
                        log_terminal(f"Resultado: {vaga.get('titulo')[:20]} -> DISPONÍVEL", "INFO")
                        
                    elif vaga_fechada:
                        status_detectado = "Vaga Fechada 🔒"
                        log_terminal(f"Resultado: {vaga.get('titulo')[:20]} -> FECHADA", "WARN")
                        
                    else:
                        status_detectado = "Não Aplicado ❌ (Botão não achado)"
                        log_terminal(f"Resultado: {vaga.get('titulo')[:20]} -> Incerto", "DEBUG")

                    vaga['status'] = status_detectado
                    vaga['data_verificacao'] = datetime.datetime.now().strftime("%d/%m/%Y")
                    
                    await queue.put(([vaga], f"Status: {status_detectado}"))

                except Exception as e:
                    log_terminal(f"Erro ao ler {link}: {e}", "ERROR")
                    vaga['status'] = "Erro Leitura"
                    await queue.put(([vaga], "⚠️ Erro ao acessar link"))

    except asyncio.CancelledError:
        log_terminal("Auditoria interrompida.", "WARN")
    except Exception as e:
        log_terminal(f"Erro Crítico Auditor: {e}", "ERROR")
    finally:
        if context:
            try: await context.close()
            except: pass
        await queue.put(None)

def auditar_vagas(lista_alvo):
    queue = asyncio.Queue()
    try: loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
    except: loop = asyncio.get_event_loop()
    
    task = loop.create_task(_auditar_async(lista_alvo, queue))
    
    try:
        while True:
            try:
                dados = loop.run_until_complete(queue.get())
                if dados is None: break
                yield dados
            except RuntimeError: break
    except GeneratorExit:
        log_terminal("Interrompendo auditoria...", "WARN")
        task.cancel()
        try: loop.run_until_complete(task)
        except (asyncio.CancelledError, OSError, RuntimeError, Exception): pass
        raise