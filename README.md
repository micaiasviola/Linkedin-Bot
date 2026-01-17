# 🚀 LinkedIn Easy Apply Hunter

Ferramenta de automação desenvolvida em Python para otimizar a busca por vagas com "Candidatura Simplificada" (Easy Apply) no LinkedIn. O projeto utiliza automação de navegador para contornar limitações da busca padrão, filtrar resultados irrelevantes (como vagas Sênior aparecendo em buscas Júnior) e gerenciar um histórico local de oportunidades para evitar duplicatas.

---

## 📌 Motivação

Durante meu processo de busca por vagas, notei três ineficiências principais na plataforma padrão do LinkedIn:

- **Resultados Poluídos**: Mesmo filtrando por "Júnior" ou "Estágio", o algoritmo frequentemente retorna vagas de nível Sênior, Pleno ou Especialista.

- **Repetição**: A mesma vaga aparece em dias diferentes ou é repostada, dificultando saber o que é realmente novo.

- **Fluxo de Navegação**: O sistema de "rolagem infinita" (infinite scroll) combinada com a paginação do LinkedIn muitas vezes falha ao carregar novos itens, tornando a coleta manual lenta.

Desenvolvi este software para resolver esses problemas, criando um "funil" de entrada mais limpo e eficiente para o meu processo de candidatura.

---

## 🛠️ Stack Tecnológica

- **Python 3.12+**
  
- **Playwright**: Escolhido em vez do Selenium pela sua velocidade de execução, melhor controle sobre contextos de navegador e capacidade de lidar com conteúdo dinâmico moderno.

- **Streamlit**: Utilizado para criar uma interface de controle (Dashboard) rápida, permitindo ajustar filtros de busca e visualizar resultados sem precisar alterar o código fonte.

- **JSON**: Persistência de dados leve para manter o histórico de vagas e configurações de perfil.

---

## 🏗️ Arquitetura e Lógica

O sistema opera em três camadas principais:

### 1️⃣ Autenticação e Sessão

Ao contrário de scrapers simples que rodam em modo anônimo (o que limita severamente os resultados do LinkedIn), o bot utiliza um perfil de navegador persistente (`launch_persistent_context`). Isso permite:

- Utilizar os cookies de uma sessão real do Chrome
- Manter o usuário logado
- Acessar filtros que só estão disponíveis para usuários autenticados (como o filtro real de "Easy Apply")

### 2️⃣ Estratégia de Busca e Filtragem

A busca não depende apenas da interface gráfica. O sistema constrói URLs de busca utilizando Operadores Booleanos:

- **Inclusão**: `(Desenvolvedor Junior) OR (Python Trainee)`

- **Exclusão (Hard Filter)**: Adicionei uma query `NOT (Senior OR Pleno OR Lead...)` diretamente na URL para limpar cerca de 90% do ruído.

- **Filtro de Texto (Post-Processing)**: Uma segunda camada de verificação no Python lê o título da vaga extraída e descarta o item se contiver palavras-chave proibidas que passaram pelo filtro da URL.

### 3️⃣ Paginação e Rolagem (Desafios Superados)

A coleta de dados em Single Page Applications (SPAs) como o LinkedIn apresenta desafios específicos de carregamento preguiçoso (lazy loading).

- **Rolagem**: A simulação de teclas (`PageDown`) mostrou-se ineficaz devido ao foco instável do navegador. A solução foi implementar uma simulação física de mouse (`mouse.wheel`) focada nas coordenadas exatas (`bounding_box`) do container de resultados.

- **Paginação**: O botão "Avançar" do LinkedIn é instável e muitas vezes desaparece. Substituí a interação de clique por uma lógica matemática de URL, manipulando o parâmetro `&start=0`, `&start=25`, `&start=50`, garantindo uma navegação determinística e à prova de falhas de interface.

### 💾 Cache e Histórico

Para evitar ver a mesma vaga duas vezes, o sistema mantém um arquivo `historico_vagas.json`. Cada URL coletada é normalizada (remoção de parâmetros de rastreamento) e comparada com esse banco de dados local antes de ser exibida no dashboard.

---

## 🚀 Como Executar

### ✅ Pré-requisitos

- Python instalado
- Google Chrome instalado

### 📦 Instalação

#### 1. Clone o repositório:

```bash
git clone https://github.com/micaiasviola/Linkedin-Bot
cd Linkedin-Bot
```

#### 2. Instale as dependências:

```bash
pip install -r requirements.txt
playwright install chromium
```

#### 3. Configure o Login (apenas na primeira vez)

Isso abrirá um navegador para que você faça login manualmente e salve a sessão:

```bash
python setup_login.py
```

#### 4. Execute a aplicação:

```bash
streamlit run app.py
```

---

## 🎯 Próximos Passos

- [ ] Implementar integração com Telegram para receber alertas de vagas em tempo real
- [ ] Adicionar análise de descrição da vaga com NLP para identificar requisitos técnicos automaticamente

---

## ⚖️ Aviso Legal

Este projeto foi desenvolvido para fins educacionais e de uso pessoal para automação de tarefas repetitivas. O uso de scrapers deve respeitar os Termos de Serviço da plataforma alvo.