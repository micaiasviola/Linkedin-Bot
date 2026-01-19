import sys
import os
import streamlit as st
import time
import asyncio
import json
import pandas as pd

# Configuração para Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# --- IMPORTS CORRIGIDOS ---
# Hunter: Busca e Manipulação de Arquivo
from automation.hunter import buscar_vagas_em_lote, carregar_historico_global, carregar_historico_completo, salvar_historico_completo
# Auditor: Verificação de Candidatura
from automation.auditor import auditar_vagas

st.set_page_config(page_title="Job Hunter Pro", page_icon="⚡", layout="wide")

# ================= DESIGN SYSTEM (CSS) =================
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; }
    
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

    /* Tipografia */
    .job-title {
        font-size: 1rem;
        font-weight: 700;
        color: #F7FAFC;
        margin-bottom: 10px;
        line-height: 1.4;
        display: -webkit-box;
        -webkit-line-clamp: 3;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    
    .job-meta { margin-bottom: 16px; display: flex; flex-wrap: wrap; gap: 6px; }

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
    .badge-tag { background-color: rgba(255,255,255,0.05); color: #CBD5E0; font-weight: normal; border: 1px solid rgba(255,255,255,0.1); }

    .apply-container { margin-top: auto; }
    .apply-btn {
        display: block; width: 100%; text-align: center; background-color: #3182CE; color: white !important;
        padding: 10px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 0.9rem;
        transition: background-color 0.2s;
    }
    .apply-btn:hover { background-color: #2B6CB0; text-decoration: none; }
    
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 12px; border: 1px solid #2D3748; background-color: #171923;
    }
    </style>
""", unsafe_allow_html=True)

# ================= HELPER FUNCTIONS =================
def render_job_card(vaga, is_top_pick=False):
    css_class = "job-card top-pick" if is_top_pick else "job-card"
    score_class = "badge-score-high" if vaga.get('score', 0) >= 70 else "badge-score-low"
    
    tags_html = ""
    motivos = vaga.get('motivo', '').split(', ')
    for m in motivos[:4]: 
        if m and m != "Base(50)":
            clean_m = m.replace('(+15)', '').replace('(-20)', '').strip()
            tags_html += f'<span class="badge badge-tag">{clean_m}</span>'

    html = f"""
    <div class="{css_class}">
        <div>
            <div style="margin-bottom: 10px; display: flex; align-items: center; gap: 8px;">
                <span class="badge {score_class}">{vaga.get('score', 0)} pts</span>
            </div>
            <div class="job-title" title="{vaga.get('titulo', 'Sem Título')}">{vaga.get('titulo', 'Sem Título')}</div>
            <div class="job-meta">{tags_html}</div>
        </div>
        <div class="apply-container">
            <a href="{vaga['link']}" target="_blank" class="apply-btn">Ver Vaga</a>
        </div>
    </div>
    """
    return html.replace("\n", "").strip()

def carregar_dados_formatados():
    """Lê o JSON e converte para DataFrame do Pandas."""
    dados = carregar_historico_completo()
    if not dados: return pd.DataFrame()
    return pd.DataFrame(dados)

# ================= SIDEBAR & NAVEGAÇÃO =================
if 'vagas_encontradas' not in st.session_state: st.session_state.vagas_encontradas = [] 
if 'historico_links' not in st.session_state: st.session_state.historico_links = carregar_historico_global()

with st.sidebar:
    st.title("⚡ Hunter Pro")
    pagina = st.radio("Navegação", ["🔍 Buscador", "📂 Banco de Dados"], index=0)
    st.divider()

    if pagina == "🔍 Buscador":
        st.markdown(f"**{len(st.session_state.vagas_encontradas)}** vagas na tela")
        if st.session_state.vagas_encontradas:
            if st.button("🗑️ Limpar Resultados", use_container_width=True):
                st.session_state.vagas_encontradas = []
                st.rerun()
        st.caption("Filtros: Anti-Sênior, Python Stack")

# ================= PÁGINA 1: BUSCADOR (HUNTER) =================
if pagina == "🔍 Buscador":
    st.header("Painel de Controle")

    with st.container(border=True):
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1: 
            default_query = "title:(Python OR Django) AND (Junior OR Jr) NOT (Senior OR Pleno OR Java OR .NET)"
            termo = st.text_input("Cargo / Boolean Search", value=default_query)
        with c2: 
            periodo = st.selectbox("Período", ["Última Hora", "Hoje (24h)", "Semana", "Mês"], index=1)
            mapa_tempo = {"Última Hora": "r3600", "Hoje (24h)": "r86400", "Semana": "r604800", "Mês": "r2592000"}
        with c3: max_pg = st.number_input("Máx. Páginas", min_value=1, max_value=50, value=5)

        c4, c5, c6 = st.columns(3)
        with c4: salvar = st.checkbox("💾 Salvar histórico", value=True)
        with c5: ordenar_recente = st.checkbox("📅 Ordenar por Data", value=False)
        with c6: st.write("")

        placeholder_botao = st.empty()
        iniciar = placeholder_botao.button("🚀 Iniciar Busca", type="primary", use_container_width=True)

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
        
        if not parou_manual: status_msg.success(f"Finalizado! {total_novas} vagas novas.")
        else: status_msg.warning("Busca interrompida.")
        
        time.sleep(1.5)
        st.rerun()

    # Grid de Vagas
    if st.session_state.vagas_encontradas:
        st.divider()
        st.session_state.vagas_encontradas.sort(key=lambda x: x.get('score', 0), reverse=True)
        top_picks = [v for v in st.session_state.vagas_encontradas if v.get('score', 0) >= 70]
        outras = [v for v in st.session_state.vagas_encontradas if v.get('score', 0) < 70]

        if top_picks:
            st.subheader(f"🔥 Top Picks ({len(top_picks)})")
            cols = st.columns(3)
            for i, vaga in enumerate(top_picks):
                with cols[i % 3]: st.markdown(render_job_card(vaga, True), unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

        if outras:
            st.subheader(f"📋 Outras Oportunidades ({len(outras)})")
            cols = st.columns(4)
            for i, vaga in enumerate(outras):
                with cols[i % 4]: st.markdown(render_job_card(vaga, False), unsafe_allow_html=True)

# ================= PÁGINA 2: BANCO DE DADOS (CORRIGIDA) =================
elif pagina == "📂 Banco de Dados":
    st.header("📂 Histórico de Vagas")
    
    # Recarrega os dados completos do disco
    dados_brutos = carregar_historico_completo()
    
    if dados_brutos:
        df = pd.DataFrame(dados_brutos)
        
        # Garante que as colunas de controle existam
        if 'status' not in df.columns: df['status'] = "Pendente"
        if 'data_verificacao' not in df.columns: df['data_verificacao'] = None
        
        # Filtros Visuais (Para você ver a tabela)
        c1, c2 = st.columns([3, 1])
        with c1: txt_busca = st.text_input("Filtrar título", placeholder="Ex: Django")
        with c2: filtro_status = st.selectbox("Status", ["Todos", "Pendente", "Aplicado ✅", "Não Aplicado ❌"])

        # Aplica Filtros no DataFrame VISUAL
        df_visual = df.copy()
        if txt_busca:
            df_visual = df_visual[df_visual['titulo'].str.contains(txt_busca, case=False, na=False)]
        if filtro_status != "Todos":
            df_visual = df_visual[df_visual['status'] == filtro_status]

        st.divider()
        st.subheader("🕵️ Auditor de Candidaturas")
        
        col_aud1, col_aud2 = st.columns([1, 2])
        with col_aud1:
            qtd_auditar = st.number_input("Verificar quantas vagas?", min_value=1, max_value=20, value=5)
        with col_aud2:
            st.write("") # Spacer
            # Botão agora usa lógica de fila inteligente
            if st.button("▶️ Iniciar Verificação", type="secondary"):
                
                # --- LÓGICA DE FILA INTELIGENTE ---
                # 1. Pega o dataframe filtrado pelo usuário (respeita se ele escolheu só "Pendente")
                # 2. Ordena: Quem tem data_verificacao vazia (NaN) aparece PRIMEIRO ('first').
                #    Se todos tiverem data, ordena pela data antiga (ascending=True).
                df_processamento = df_visual.sort_values(by="data_verificacao", ascending=True, na_position="first")
                
                # Agora sim pegamos o topo, que garantidamente são os "mais urgentes"
                vagas_para_auditar = df_processamento.head(qtd_auditar).to_dict('records')
                
                if not vagas_para_auditar:
                    st.warning("Nenhuma vaga encontrada com os filtros atuais.")
                else:
                    status_box = st.status(f"Auditando {len(vagas_para_auditar)} vagas (Prioridade: Não verificadas)...", expanded=True)
                    prog_bar = st.progress(0)
                    
                    # Roda o Auditor
                    auditor_iter = auditar_vagas(vagas_para_auditar)
                    
                    idx = 0
                    for dados_vaga, msg in auditor_iter:
                        status_box.write(msg)
                        
                        if dados_vaga: # Se retornou atualização
                            vaga_atualizada = dados_vaga[0]
                            
                            # Atualiza na lista principal bruta (Memória Global)
                            # REVERTEMOS A EXCLUSÃO: Agora apenas atualizamos o status
                            for i, v in enumerate(dados_brutos):
                                if v['link'] == vaga_atualizada['link']:
                                    dados_brutos[i] = vaga_atualizada
                                    dados_brutos[i]['data_verificacao'] = time.strftime("%Y-%m-%d %H:%M:%S") # Carimbo de tempo para ir pro fim da fila
                                    break
                            
                            # Salva no disco
                            salvar_historico_completo(dados_brutos)
                            
                            idx += 1
                            prog_bar.progress(min(idx / qtd_auditar, 1.0))
                    
                    status_box.update(label="Ciclo finalizado!", state="complete", expanded=False)
                    time.sleep(2)
                    st.rerun() # Recarrega a tabela

        # --- TABELA DE DADOS ---
        st.divider()
        st.dataframe(
            df_visual, 
            use_container_width=True,
            column_config={
                "link": st.column_config.LinkColumn("Link"),
                "score": st.column_config.ProgressColumn("Score", format="%d"),
                "status": st.column_config.TextColumn("Status"),
                "titulo": "Cargo",
                "data_verificacao": st.column_config.TextColumn("Última Checagem")
            },
            hide_index=True
        )
        
        st.download_button(
            label="📥 Baixar CSV",
            data=df_visual.to_csv(index=False).encode('utf-8'),
            file_name='vagas_historico.csv',
            mime='text/csv',
        )
    else:
        st.info("Banco de dados vazio.")