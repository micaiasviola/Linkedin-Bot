import sys
import os
import streamlit as st
import time
import asyncio

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from automation.hunter import buscar_vagas_em_lote, carregar_historico_global

st.set_page_config(page_title="Job Hunter Pro", page_icon="⚡", layout="wide")

# ================= DESIGN SYSTEM (CSS CORRIGIDO) =================
st.markdown("""
    <style>
    /* Reset e Fundo */
    .stApp {
        background-color: #0E1117;
    }
    
    /* Cartão de Vaga */
    .job-card {
        background-color: #1A202C;
        border: 1px solid #2D3748;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 16px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        /* Altura mínima garante alinhamento no grid */
        min-height: 220px; 
        transition: transform 0.2s, border-color 0.2s;
    }
    
    .job-card:hover {
        border-color: #4FD1C5;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
    }
    
    /* Destaque Top Pick */
    .top-pick {
        border: 1px solid #48BB78;
        background: linear-gradient(180deg, rgba(72,187,120,0.05) 0%, rgba(26,32,44,1) 100%);
    }

    /* Título */
    .job-title {
        font-size: 1rem;
        font-weight: 700;
        color: #F7FAFC;
        margin-bottom: 10px;
        line-height: 1.4;
        /* Limita a 3 linhas para não quebrar o layout */
        display: -webkit-box;
        -webkit-line-clamp: 3;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    
    /* Área de Tags/Badges */
    .job-meta {
        margin-bottom: 16px;
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
    }

    /* Badges */
    .badge {
        display: inline-flex;
        align-items: center;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.02em;
    }
    .badge-score-high { background-color: #2F855A; color: #F0FFF4; border: 1px solid #48BB78; }
    .badge-score-low { background-color: #2D3748; color: #A0AEC0; border: 1px solid #4A5568; }
    
    .badge-tag { 
        background-color: rgba(255,255,255,0.05); 
        color: #CBD5E0; 
        font-weight: normal; 
        border: 1px solid rgba(255,255,255,0.1); 
    }

    /* Botão */
    .apply-container {
        margin-top: auto; /* Empurra para o fundo do card */
    }
    .apply-btn {
        display: block;
        width: 100%;
        text-align: center;
        background-color: #3182CE;
        color: white !important;
        padding: 10px;
        border-radius: 8px;
        text-decoration: none;
        font-weight: 600;
        font-size: 0.9rem;
        transition: background-color 0.2s;
    }
    .apply-btn:hover {
        background-color: #2B6CB0;
        text-decoration: none;
    }
    
    /* Ajustes Gerais */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 12px;
        border: 1px solid #2D3748;
        background-color: #171923;
    }
    </style>
""", unsafe_allow_html=True)

# ================= FUNÇÃO RENDERIZAÇÃO (CORRIGIDA E BLINDADA) =================
def render_job_card(vaga, is_top_pick=False):
    css_class = "job-card top-pick" if is_top_pick else "job-card"
    score_class = "badge-score-high" if vaga['score'] >= 70 else "badge-score-low"
    
    tags_html = ""
    motivos = vaga.get('motivo', '').split(', ')
    # Pega apenas os 4 primeiros motivos para não poluir
    for m in motivos[:4]: 
        if m and m != "Base(50)":
            clean_m = m.replace('(+15)', '').replace('(-20)', '').strip()
            tags_html += f'<span class="badge badge-tag">{clean_m}</span>'

    # Removemos a indentação visual aqui no código para garantir,
    # mas o .replace('\n', '') no return é o verdadeiro segredo.
    html = f"""
    <div class="{css_class}">
        <div>
            <div style="margin-bottom: 10px; display: flex; align-items: center; gap: 8px;">
                <span class="badge {score_class}">{vaga['score']} pts</span>
            </div>
            <div class="job-title" title="{vaga['titulo']}">{vaga['titulo']}</div>
            <div class="job-meta">
                {tags_html}
            </div>
        </div>
        <div class="apply-container">
            <a href="{vaga['link']}" target="_blank" class="apply-btn">Ver Vaga</a>
        </div>
    </div>
    """
    
    # TRUQUE DE MESTRE: Removemos quebras de linha para o Streamlit não achar que é código
    return html.replace("\n", "").strip()

# ================= ESTADO & SIDEBAR =================
if 'vagas_encontradas' not in st.session_state: st.session_state.vagas_encontradas = [] 
if 'historico_links' not in st.session_state: st.session_state.historico_links = carregar_historico_global()

with st.sidebar:
    st.title("⚡ Hunter Pro")
    st.markdown(f"**{len(st.session_state.vagas_encontradas)}** vagas encontradas")
    
    if st.session_state.vagas_encontradas:
        if st.button("🗑️ Limpar Resultados", use_container_width=True):
            st.session_state.vagas_encontradas = []
            st.rerun()
    
    st.divider()
    st.caption("Filtros: Anti-Sênior, Python Stack, Ranking IA")

# ================= MAIN LAYOUT =================
st.header("Painel de Controle")

with st.container(border=True):
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        termo = st.text_input("Cargo / Keywords", value="Desenvolvedor Python Júnior")
    with c2:
        periodo = st.selectbox("Período", ["Última Hora", "Hoje (24h)", "Semana", "Mês"], index=1)
        mapa_tempo = {"Última Hora": "r3600", "Hoje (24h)": "r86400", "Semana": "r604800", "Mês": "r2592000"}
    with c3:
        max_pg = st.number_input("Máx. Páginas", min_value=1, max_value=50, value=5)

    c4, c5, c6 = st.columns(3)
    with c4: salvar = st.checkbox("💾 Salvar histórico", value=True)
    with c5: ordenar_recente = st.checkbox("📅 Ordenar por Data", value=False)
    with c6: st.write("") # Spacer

    placeholder_botao = st.empty()
    iniciar = placeholder_botao.button("🚀 Iniciar Busca", type="primary", use_container_width=True)

# Lógica de Execução
if iniciar:
    placeholder_botao.warning("⏳ Buscando vagas... Clique abaixo para parar.")
    stop_btn = st.empty()
    status_msg = st.empty()
    progress_bar = st.progress(0)
    
    total_novas = 0
    parou_manual = False
    
    hunter_iter = buscar_vagas_em_lote(
        st.session_state.historico_links, termo, mapa_tempo[periodo], salvar, max_pg, ordenar_recente
    )
    
    idx = 0
    for lote, msg in hunter_iter:
        if stop_btn.button("⛔ PARAR AGORA", key=f"stop_{idx}", type="secondary", use_container_width=True):
            status_msg.error("🛑 Parando...")
            parou_manual = True
            break 
        
        status_msg.info(msg)
        progress_bar.progress(min((idx + 1) * 5, 100))
        
        if lote:
            for v in lote:
                if not any(e['link'] == v['link'] for e in st.session_state.vagas_encontradas):
                    st.session_state.vagas_encontradas.append(v)
                    st.session_state.historico_links.add(v['link'])
            total_novas += len(lote)
        idx += 1

    stop_btn.empty()
    progress_bar.empty()
    
    if not parou_manual:
        status_msg.success(f"Finalizado! {total_novas} vagas novas.")
    else:
        status_msg.warning("Busca interrompida.")
    
    time.sleep(1.5)
    st.rerun()

# ================= GRID DE VAGAS =================
if st.session_state.vagas_encontradas:
    st.divider()
    
    # Ordenação
    st.session_state.vagas_encontradas.sort(key=lambda x: x['score'], reverse=True)
    
    top_picks = [v for v in st.session_state.vagas_encontradas if v['score'] >= 70]
    outras = [v for v in st.session_state.vagas_encontradas if v['score'] < 70]

    if top_picks:
        st.subheader(f"🔥 Top Picks ({len(top_picks)})")
        cols = st.columns(3) # 3 colunas para destaques
        for i, vaga in enumerate(top_picks):
            with cols[i % 3]:
                st.markdown(render_job_card(vaga, is_top_pick=True), unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

    if outras:
        st.subheader(f"📋 Outras Oportunidades ({len(outras)})")
        cols = st.columns(4) # 4 colunas para normais
        for i, vaga in enumerate(outras):
            with cols[i % 4]:
                st.markdown(render_job_card(vaga, is_top_pick=False), unsafe_allow_html=True)