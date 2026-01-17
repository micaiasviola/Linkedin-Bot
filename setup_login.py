import os
import time
import shutil
from playwright.sync_api import sync_playwright

# Define o caminho da pasta
USER_DATA_DIR = os.path.join(os.getcwd(), "navegador_robo")

def fazer_login():
    # Garante que a pasta antiga foi removida para evitar conflitos
    if os.path.exists(USER_DATA_DIR):
        try:
            shutil.rmtree(USER_DATA_DIR)
            print("🧹 Pasta antiga limpa com sucesso.")
        except:
            print("⚠️ Não consegui apagar a pasta automaticamente. Se der erro, apague 'navegador_robo' manualmente.")

    print("🚀 Abrindo Navegador Genérico para Login...")
    print("1. Digite seu email e senha.")
    print("2. IMPORTANTE: Marque a caixa 'Lembrar de mim'.")
    print("3. Espere carregar o feed e FECHE a janela.")

    with sync_playwright() as p:
        # Abre sem apontar para executable_path (usa o interno do Playwright)
        browser = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False,
            args=["--start-maximized", "--no-sandbox", "--disable-infobars"]
        )
        
        page = browser.pages[0]
        try:
            page.goto("https://www.linkedin.com/login", timeout=60000)
        except:
            pass
        
        # Mantém aberto até você fechar
        print("⏳ Aguardando você fechar o navegador...")
        try:
            while True:
                time.sleep(1)
                # Se não houver mais páginas abertas, sai do loop
                if not browser.pages:
                    break
        except:
            pass
            
        print("✅ Novo perfil salvo em 'navegador_robo'!")

if __name__ == "__main__":
    fazer_login()