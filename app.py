import sys
import os
import asyncio
import streamlit as st
import json
import time

# Correção Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from automation.hunter import buscar_vagas_em_lote, carregar_historico_global

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Job Hunter Pro", 
    page_icon="🎯", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- BIBLIOTECA DE ÍCONES (SVG CLEAN - ESTILO LUCIDE) ---
# Definimos a cor principal (#00B4D8) direto no SVG para combinar com o tema
PRIMARY_COLOR = "#00B4D8"
TEXT_COLOR = "#FAFAFA"

def get_icon(name, color=TEXT_COLOR, size=24):
    icons = {
        "briefcase": f"""<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="14" x="2" y="7" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>""",
        "search": f"""<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>""",
        "clock": f"""<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>""",
        "target": f"""<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>""",
        "shield": f"""<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/></svg>""",
        "trash": f"""<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>""",
        "link": f"""<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>""",
        "rocket": f"""<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.1 4-1 4-1s.38 2.38-1 4z"/><path d="M12 15v5s3.03-.55 4-2c1.1-1.62 1-4 1-4s-2.38-.38-4 1z"/></svg>"""
    }
    return icons.get(name, "")

# Função auxiliar para renderizar texto com ícone alinhado
def render_header(icon_name, text, level=2, color=PRIMARY_COLOR):
    icon_svg = get_icon(icon_name, color=color, size=28)
    st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
            {icon_svg}
            <h{level} style="margin: 0; padding: 0; color: #FAFAFA;">{text}</h{level}>
        </div>
    """, unsafe_allow_html=True)

# --- ESTILOS CSS PERSONALIZADOS ---
st.markdown("""
    <style>
    /* Limpeza geral */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Card da Vaga */
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #171923; /* Fundo mais escuro e elegante */
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 15px;
        border: 1px solid #2D3748; /* Borda sutil */
        transition: transform 0.2s;
    }
    
    /* Botões */
    div.stButton > button {
        border-radius: 8px;
        font-weight: 600;
        border: none;
    }
    
    div.stButton > button:hover {
        opacity: 0.9;
    }

    /* Ajuste de métricas */
    [data-testid="stMetricValue"] {
        font-size: 24px;
        color: #00B4D8;
    }
    </style>
""", unsafe_allow_html=True)

# --- MEMÓRIA ---
if 'vagas_encontradas' not in st.session_state:
    st.session_state.vagas_encontradas = []
if 'historico_links' not in st.session_state:
    st.session_state.historico_links = set()

total_ignorado = len(carregar_historico_global())

# --- BARRA LATERAL ---
with st.sidebar:
    # Título com Ícone SVG
    render_header("briefcase", "Minhas Vagas", level=2)
    
    st.markdown(f"<div style='color: #A0AEC0; margin-bottom: 20px;'><b>{len(st.session_state.vagas_encontradas)}</b> oportunidades na fila</div>", unsafe_allow_html=True)

    if not st.session_state.vagas_encontradas:
        st.info("Lista vazia. Inicie uma busca.")
    else:
        if st.button("Limpar lista", type="secondary"):
            st.session_state.vagas_encontradas = []
            st.rerun()
            
        st.markdown("---")
        for i, link in enumerate(st.session_state.vagas_encontradas):
            # Renderiza um mini-item
            icon = get_icon("link", size=16, color="#00B4D8")
            st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px; font-size: 14px;">
                {icon} <a href="{link}" target="_blank" style="text-decoration: none; color: #FAFAFA;">Vaga #{i+1}</a>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")
    
    # Rodapé da sidebar com ícone
    shield_icon = get_icon("shield", size=16, color="#718096")
    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 8px; color: #718096; font-size: 12px;">
        {shield_icon} <span>Histórico: {total_ignorado} vagas ignoradas</span>
    </div>
    """, unsafe_allow_html=True)

# --- ÁREA PRINCIPAL ---

# Cabeçalho Principal
st.markdown(f"<h1 style='color: {TEXT_COLOR};'>Olá, Micaías!</h1>", unsafe_allow_html=True)
st.markdown("<p style='color: #A0AEC0; font-size: 18px;'>Pronto para dominar o mercado hoje?</p>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Card de Configuração
with st.container(border=True):
    render_header("search", "Configurar Busca", level=4, color=PRIMARY_COLOR)
    
    col_input, col_time = st.columns([3, 1])
    
    with col_input:
        termo_busca = st.text_input(
            "Cargo ou Palavras-chave", 
            placeholder="Ex: Desenvolvedor Python...",
            label_visibility="collapsed"
        )
        if not termo_busca:
            st.caption("Utilizando preferências salvas em perfil.json")
        
    with col_time:
        opcoes_tempo = {
            "Agora (1h)": "r3600",
            "Hoje (24h)": "r86400",
            "Esta Semana": "r604800",
            "Este Mês": "r2592000"
        }
        escolha = st.selectbox("Período", list(opcoes_tempo.keys()), index=1, label_visibility="collapsed")
        codigo_tempo = opcoes_tempo[escolha]

    st.markdown("<br>", unsafe_allow_html=True)
    
    # Botão de Ação
    if st.button("Encontrar Oportunidades", type="primary", use_container_width=True):
        with st.status("Iniciando varredura...", expanded=True) as status:
            st.write("Conectando ao LinkedIn...")
            
            novas, erro = buscar_vagas_em_lote(
                st.session_state.historico_links, 
                termo_usuario=termo_busca,
                filtro_tempo=codigo_tempo
            )
            
            if novas:
                qtd = len(novas)
                status.write(f"Sucesso! {qtd} vagas encontradas.")
                for v in novas:
                    st.session_state.historico_links.add(v)
                    st.session_state.vagas_encontradas.append(v)
                time.sleep(1)
                status.update(label="Busca Completa", state="complete", expanded=False)
                st.rerun()
            else:
                if erro:
                    status.update(label="Erro", state="error")
                    st.error(erro)
                else:
                    status.update(label="Sem resultados", state="complete")
                    st.warning("Nenhuma vaga nova encontrada.")

# --- GRID DE VAGAS ---
if st.session_state.vagas_encontradas:
    st.markdown("<br>", unsafe_allow_html=True)
    render_header("rocket", "Vagas Disponíveis", level=3)
    
    col_a, col_b = st.columns(2)
    
    for i, link in enumerate(st.session_state.vagas_encontradas):
        col_atual = col_a if i % 2 == 0 else col_b
        
        with col_atual:
            with st.container(border=True):
                # Cabeçalho do Card
                st.markdown(f"""
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <span style="font-weight: bold; color: {PRIMARY_COLOR};">Vaga #{i+1}</span>
                    <span style="font-size: 12px; background: #2D3748; padding: 2px 8px; border-radius: 10px;">Easy Apply</span>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown("Candidatura simplificada disponível.")
                st.markdown("<br>", unsafe_allow_html=True)
                
                # Botão Link
                st.link_button("Aplicar Agora", link, use_container_width=True)