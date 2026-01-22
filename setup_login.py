import os
import asyncio
from playwright.async_api import async_playwright

# Usa o mesmo caminho absoluto do hunter.py
USER_DATA_DIR = os.path.abspath(os.path.join(os.getcwd(), "navegador_robo"))

async def aplicar_stealth_manual(page):
    """
    Aplica as mesmas máscaras do robô principal para garantir
    que o perfil seja salvo já com as configurações corretas.
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

async def realizar_login():
    # Garante que a pasta existe
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    
    print(f"📂 Pasta de perfil: {USER_DATA_DIR}")
    print("🚀 Abrindo navegador BLINDADO para login manual...")
    print("ℹ️  (A barra de automação deve estar oculta e a tela maximizada)")

    # Mesmos argumentos do hunter.py (sem o --no-sandbox que causava erro)
    args_camuflagem = [
        "--start-maximized",
        "--window-position=0,0",
        "--window-size=1920,1080",
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--exclude-switches=enable-automation",
        "--disable-extensions",
        "--password-store=basic",
        "--use-mock-keychain",
        "--disable-session-crashed-bubble",
        "--hide-scrollbars",
    ]
    
    async with async_playwright() as p:
        # Abre contexto PERSISTENTE com as mesmas configurações do robô
        context = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False,
            channel="chrome", 
            args=args_camuflagem,
            viewport=None, # IMPORTANTE: Para permitir maximizar
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ignore_default_args=["--enable-automation"] # Remove a barra "Controlado por software"
        )
        
        if len(context.pages) > 0: page = context.pages[0]
        else: page = await context.new_page()

        # Aplica o stealth para o LinkedIn não desconfiar nem no login
        await aplicar_stealth_manual(page)
        
        try:
            await page.goto("https://www.linkedin.com/login")
        except:
            print("⚠️ Página demorou para carregar, mas o navegador está aberto.")
        
        print("\n" + "="*50)
        print("⚡ AÇÃO NECESSÁRIA:")
        print("1. Faça login no LinkedIn manualmente.")
        print("2. Se pedir captcha, resolva tranquilamente.")
        print("3. Navegue até aparecer seu feed de notícias.")
        print("4. VOLTE AQUI e aperte ENTER para salvar.")
        print("="*50)
        
        input() # Trava o script aqui esperando você
        
        print("💾 Salvando sessão e fechando...")
        await context.close()
        print("✅ Tudo pronto! Agora pode rodar o robô principal.")

if __name__ == "__main__":
    asyncio.run(realizar_login())