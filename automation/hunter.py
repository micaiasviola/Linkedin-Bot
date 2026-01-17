import urllib.parse
import os
import time
import json
import datetime
from playwright.sync_api import sync_playwright

# --- CONFIGURAÇÕES DE AMBIENTE ---
USER_DATA_DIR = os.path.join(os.getcwd(), "navegador_robo")
CAMINHO_HISTORICO = os.path.join(os.getcwd(), "data", "historico_vagas.json")
CAMINHO_PERFIL = os.path.join(os.getcwd(), "data", "perfil.json")

# --- LISTA NEGRA (O PORTEIRO) ---
# Termos que indicam que a vaga NÃO é para Júnior
BLACKLIST = [
    "senior", "sênior", "sr.", " sr ", "sr-", 
    "pleno", "pl ", " pl ", 
    "lead", "tech lead", "lider", "líder",
    "principal", "staff", "head",
    "manager", "gerente", "gestor", "coordenador",
    "especialista", "specialist", "expert",
    "architect", "arquiteto",
    "iii", "iv", " v "
]

# --- SISTEMA DE LOGS ---
def log(msg, nivel="INFO"):
    """Gera logs com timestamp para acompanhar o processo."""
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    # Traduzindo os níveis para ficar mais visual
    icone = "! "
    if nivel == "WARN": icone = " "
    if nivel == "ERROR": icone = " "
    if nivel == "SUCCESS": icone = " "
    
    print(f"[{timestamp}] [{nivel}] {icone} {msg}")

def carregar_termos_busca():
    try:
        with open(CAMINHO_PERFIL, "r", encoding="utf-8") as f:
            dados = json.load(f)
            return dados.get("termos_busca", ["Desenvolvedor Junior"])
    except:
        return ["Desenvolvedor Junior"]

def carregar_historico_global():
    if not os.path.exists(CAMINHO_HISTORICO):
        return set()
    try:
        with open(CAMINHO_HISTORICO, "r", encoding="utf-8") as f:
            lista = json.load(f)
            return {link.rstrip("/") for link in lista}
    except:
        return set()

def salvar_historico_global(novos_links):
    historico_atual = carregar_historico_global()
    novos_limpos = {link.rstrip("/") for link in novos_links}
    historico_atual.update(novos_limpos)
    
    try:
        os.makedirs(os.path.dirname(CAMINHO_HISTORICO), exist_ok=True)
        with open(CAMINHO_HISTORICO, "w", encoding="utf-8") as f:
            json.dump(list(historico_atual), f, indent=2)
            log(f"Banco de dados atualizado! Total de vagas únicas salvas: {len(historico_atual)}", "SUCCESS")
    except Exception as e:
        log(f"Deu ruim ao salvar o histórico: {e}", "ERROR")

def buscar_vagas_em_lote(links_ja_vistos_sessao, termo_usuario=None, filtro_tempo="r86400"):
    log("Iniciando os motores do Robô (Modo Anti-Sênior)...", "INFO")
    
    historico_global = carregar_historico_global()
    if links_ja_vistos_sessao:
        sessao_limpa = {l.rstrip("/") for l in links_ja_vistos_sessao}
        historico_global.update(sessao_limpa)
    
    # Prepara a Query
    termos = [termo_usuario] if termo_usuario else carregar_termos_busca()
    query_positiva = " OR ".join([f"({t})" for t in termos])
    # O filtro negativo ajuda a limpar a sujeira do LinkedIn antes mesmo de baixar
    query_negativa = "NOT (Senior OR Sênior OR Sr OR Pleno OR Lead OR Principal OR Especialista)"
    query_final = f"{query_positiva} {query_negativa}"
    
    log(f"Estratégia de busca definida: {query_final}", "INFO")
    
    novas_vagas = []

    with sync_playwright() as p:
        try:
            log("Abrindo o navegador...", "INFO")
            context = p.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR,
                headless=False, 
                args=["--start-maximized", "--no-sandbox", "--disable-blink-features=AutomationControlled"],
                viewport=None 
            )
        except Exception as e:
            return [], f"Erro crítico ao abrir navegador: {e}"

        page = context.pages[0] if context.pages else context.new_page()
        
        try:
            q = urllib.parse.quote(query_final)
            
            pagina_atual = 0
            RESULTADOS_POR_PAGINA = 25
            LIMITE_SEGURANCA_PAGINAS = 50 
            
            while pagina_atual < LIMITE_SEGURANCA_PAGINAS:
                
                offset = pagina_atual * RESULTADOS_POR_PAGINA
                log(f"--- LENDO PÁGINA {pagina_atual + 1} (Start={offset}) ---", "INFO")
                
                url = f"https://www.linkedin.com/jobs/search?keywords={q}&location=Brazil&geoId=106057199&f_AL=true&f_TPR={filtro_tempo}&start={offset}"
                
                page.goto(url, timeout=30000)
                
                # --- SCROLL HUMANO ---
                try:
                    page.mouse.click(200, 200) # Tira o foco da URL
                    time.sleep(0.5)

                    primeiro_card = page.locator(".job-card-container").first
                    try:
                        primeiro_card.wait_for(timeout=5000)
                        
                        box = primeiro_card.bounding_box()
                        if box:
                            target_x = box["x"] + (box["width"] / 2)
                            target_y = box["y"] + (box["height"] / 2)
                            
                            # Move o mouse para a lista
                            page.mouse.move(target_x, target_y)
                            page.mouse.click(target_x, target_y)
                            
                            # Rola a página
                            for scroll in range(15): 
                                page.mouse.wheel(0, 4000)
                                time.sleep(0.6)
                                if scroll % 4 == 0: 
                                    page.mouse.move(target_x, target_y + 50) # Mexe o mouse pra não dormir
                    except:
                        log("A lista de vagas parece vazia ou não carregou.", "WARN")
                        break 

                except Exception as e:
                    log(f"Erro na rotina de scroll: {e}", "WARN")

                # --- EXTRAÇÃO E FILTRAGEM ---
                links_brutos = page.locator("a[href*='/jobs/view/']").all()
                total_encontrados_pagina = len(links_brutos)
                
                if total_encontrados_pagina < 3:
                    log("Chegamos ao fim dos resultados relevantes.", "WARN")
                    break

                count_novas = 0
                count_banidas = 0
                
                for link_el in links_brutos:
                    try:
                        href = link_el.get_attribute("href")
                        # Pega o título para verificar se é Senior disfarçado
                        titulo_vaga = link_el.inner_text().lower().strip() 
                        
                        if not href: continue
                        
                        # Limpeza da URL
                        link_limpo = href.split("?")[0].rstrip("/")
                        if "currentJobId" in href:
                            import re
                            match = re.search(r"currentJobId=(\d+)", href)
                            if match: link_limpo = f"https://www.linkedin.com/jobs/view/{match.group(1)}"
                        if link_limpo.startswith("/"): link_limpo = f"https://www.linkedin.com{link_limpo}"
                        if not link_limpo.startswith("http"): link_limpo = f"https://www.linkedin.com/jobs/view/{link_limpo}"
                        link_limpo = link_limpo.rstrip("/")

                        # --- O FILTRO DE FERRO (Verificação Manual) ---
                        texto_analise = f"{titulo_vaga} {link_limpo.lower()}"
                        
                        motivo_ban = None
                        for palavra in BLACKLIST:
                            if palavra in texto_analise:
                                motivo_ban = palavra
                                break
                        
                        if motivo_ban:
                            # Se quiser ver o que está bloqueando, descomente:
                            # log(f"    Vaga '{titulo_vaga}' bloqueada (Filtro: {motivo_ban})", "WARN")
                            count_banidas += 1
                            continue

                        # Verifica se já temos essa vaga
                        if link_limpo not in historico_global and "/jobs/view/" in link_limpo:
                            novas_vagas.append(link_limpo)
                            historico_global.add(link_limpo)
                            count_novas += 1
                            
                    except: continue
                
                log(f"Resumo da Página: {count_novas} coletadas | {count_banidas} removidas (nível alto) | O resto é duplicada", "SUCCESS")
                
                pagina_atual += 1
                time.sleep(2) 
            
            log(f"Missão cumprida! Total de vagas inéditas encontradas: {len(novas_vagas)}", "SUCCESS")
            
            if novas_vagas:
                salvar_historico_global(novas_vagas)

            return novas_vagas, None

        except Exception as e:
            log(f"Erro Crítico no Sistema: {str(e)}", "ERROR")
            return [], f"Erro técnico: {str(e)}"
        finally:
            try: page.close()
            except: pass