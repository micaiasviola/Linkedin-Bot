import os
import asyncio
from playwright.async_api import async_playwright

# Usa o mesmo caminho absoluto do hunter.py
USER_DATA_DIR = os.path.abspath(os.path.join(os.getcwd(), "navegador_robo"))

async def realizar_login():
    print(f"📂 Pasta de perfil: {USER_DATA_DIR}")
    print("🚀 Abrindo navegador para login manual...")
    
    async with async_playwright() as p:
        # Abre contexto PERSISTENTE
        context = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False,
            channel="chrome", # Tenta usar o Chrome real
            args=["--start-maximized"]
        )
        
        page = context.pages[0]
        await page.goto("https://www.linkedin.com/login")
        
        print("\n⚠️  AÇÃO NECESSÁRIA:")
        print("1. Faça login no LinkedIn manualmente no navegador que abriu.")
        print("2. Espere carregar o feed de notícias.")
        print("3. Quando terminar, APERTE ENTER AQUI NO TERMINAL para salvar e fechar.")
        
        input() # Espera você dar Enter
        
        print("💾 Salvando cookies e fechando...")
        await context.close()
        print("✅ Login salvo com sucesso!")

if __name__ == "__main__":
    asyncio.run(realizar_login())