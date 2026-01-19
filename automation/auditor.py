import os
import asyncio
import random
import datetime
from playwright.async_api import async_playwright

USER_DATA_DIR = os.path.abspath(os.path.join(os.getcwd(), "navegador_robo"))

def log_terminal(msg, tipo="INFO"):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    colors = {"INFO": "\033[96m", "SUCCESS": "\033[92m", "WARN": "\033[93m", "ERROR": "\033[91m", "DEBUG": "\033[97m"}
    reset = "\033[0m"
    print(f"{colors.get(tipo, '')}[{now}] {msg}{reset}")

async def _auditar_async(lista_vagas, queue):
    context = None
    try:
        log_terminal("=== INICIANDO AUDITORIA (MODO LEITOR HUMANO 📖) ===", "INFO")
        
        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR, 
                headless=False, 
                channel="chrome",
                args=["--start-maximized"]
            )
            
            if len(context.pages) > 0: page = context.pages[0]
            else: page = await context.new_page()

            total = len(lista_vagas)
            
            for i, vaga in enumerate(lista_vagas):
                if asyncio.current_task().cancelled(): raise asyncio.CancelledError()
                
                link = vaga.get('link')
                if not link: continue

                # Pausa humana variável (entre 2s e 5s)
                espera = random.uniform(2.5, 5.5)
                await asyncio.sleep(espera)
                
                await queue.put((None, f"🕵️ [{i+1}/{total}] Visitando: {vaga.get('titulo', 'Vaga')[:30]}..."))
                
                try:
                    await page.goto(link, timeout=20000)
                    
                    # Simula leitura: espera base + variação
                    await asyncio.sleep(random.uniform(1.5, 3.0))
                    
                    # Move o mouse um pouco como se estivesse lendo
                    await page.mouse.move(random.randint(100, 500), random.randint(100, 500), steps=10)
                    
                    body_text = (await page.inner_text("body")).lower()
                    
                    status_detectado = "Não Aplicado ❌"
                    termos_sucesso = ["candidatura enviada", "applied", "você se candidatou", "application submitted", "foi enviada ao anunciante"]
                    
                    if any(termo in body_text for termo in termos_sucesso):
                        status_detectado = "Aplicado ✅"
                        log_terminal(f"Confirmado: {vaga.get('titulo')[:20]} -> APLICADO", "SUCCESS")
                    else:
                        log_terminal(f"Status: {vaga.get('titulo')[:20]} -> Não identificado", "DEBUG")
                    
                    vaga['status'] = status_detectado
                    vaga['data_verificacao'] = datetime.datetime.now().strftime("%d/%m/%Y")
                    
                    await queue.put(([vaga], f"Status: {status_detectado}"))

                except Exception as e:
                    log_terminal(f"Erro ao ler {link}: {e}", "ERROR")
                    vaga['status'] = "Erro Leitura"
                    await queue.put(([vaga], "⚠️ Erro ao acessar link"))

    except asyncio.CancelledError:
        log_terminal("Auditoria interrompida pelo usuário.", "WARN")
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