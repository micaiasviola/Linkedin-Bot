import sys
import os
import asyncio
import streamlit as st
import json
import time

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from automation.hunter import buscar_vagas_em_lote, carregar_historico_global

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Job Hunter Pro", page_icon="🎯", layout="wide", initial_sidebar_state="expanded")

# --- CSS PERSONALIZADO ---
st.markdown("""
    <style>
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #171923;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 15px;
        border: 1px solid #2D3748;
    }
    .stButton button { width: 100%; border-radius: 8px; font-weight: bold; }
    
    /* Estilo para o botão de Parar (Vermelho) */
    div[data-testid="stButton"] button[kind="secondary"] {
        border-color: #FC8181;
        color: #FC8181;
    }
    div[data-testid="stButton"] button[kind="secondary"]:hover {
        border-color: #F56565;
        color: #F56565;
        background-color: #2D3748;
    }
    </style>
""", unsafe_allow_html=True)

# --- MEMÓRIA ---
if 'vagas_encontradas' not in st.session_state:
    st.session_state.vagas_encontradas = []
if 'historico_links' not in st.session_state:
    st.session_state.historico_links = set()

# --- SIDEBAR ---
with st.sidebar:
    st.header("🎯 Job Hunter")
    st.divider()
    st.metric("Vagas na Tela", len(st.session_state.vagas_encontradas))
    
    if st.session_state.vagas_encontradas:
        if st.button("🗑️ Limpar Lista"):
            st.session_state.vagas_encontradas = []
            st.rerun()
        st.divider()
        for i, link in enumerate(st.session_state.vagas_encontradas):
            st.markdown(f"🔗 [Vaga #{i+1}]({link})")
    
    st.markdown("---")
    total_db = len(carregar_historico_global())
    st.caption(f"💾 Banco de Dados: {total_db} vagas.")

# --- ÁREA PRINCIPAL ---
st.title("Painel de Controle")

with st.container(border=True):
    col1, col2 = st.columns([3, 1])
    with col1:
        termo = st.text_input("Cargo", placeholder="Ex: Desenvolvedor Python...")
    with col2:
        periodo = st.selectbox("Período", ["Hoje (24h)", "Semana", "Mês"], index=1)
        mapa_tempo = {"Hoje (24h)": "r86400", "Semana": "r604800", "Mês": "r2592000"}

    st.divider()
    
    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        max_pg = st.slider("Máximo de Páginas", 1, 100, 10)
    with col_opt2:
        usar_memoria = st.toggle("💾 Salvar Histórico?", value=True)

    # --- BOTÃO DE INÍCIO ---
    # Usamos um container vazio para colocar o botão de parar depois
    placeholder_botao = st.empty()
    iniciar = placeholder_botao.button("🚀 Iniciar Varredura", type="primary")

    if iniciar:
        # Substitui o botão de Iniciar por um aviso ou botão de parar
        placeholder_botao.warning("⚠️ Para interromper, clique no botão abaixo (pode demorar alguns segundos).")
        
        # Área reservada para o botão de STOP dinâmico
        stop_placeholder = st.empty()
        
        status_box = st.status("Iniciando...", expanded=True)
        
        # Chama o Generator
        hunter_iter = buscar_vagas_em_lote(
            st.session_state.historico_links,
            termo_usuario=termo,
            filtro_tempo=mapa_tempo[periodo],
            salvar_historico=usar_memoria,
            max_paginas=max_pg
        )
        
        vagas_novas_sessao = 0
        loop_index = 0
        
        # Loop Principal
        for lote_vagas, log_msg in hunter_iter:
            
            # --- LÓGICA DO BOTÃO PARAR ---
            # Renderizamos um botão novo a cada ciclo para checar o clique
            # Usamos loop_index para garantir chaves únicas
            if stop_placeholder.button(f"⛔ INTERROMPER BUSCA AGORA", key=f"stop_{loop_index}"):
                status_box.update(label="🛑 Busca Interrompida pelo Usuário!", state="error")
                st.toast("Busca parada! Seus dados foram salvos.")
                break # Quebra o loop
            
            status_box.write(log_msg)
            
            if lote_vagas:
                for v in lote_vagas:
                    if v not in st.session_state.historico_links:
                        st.session_state.historico_links.add(v)
                        st.session_state.vagas_encontradas.append(v)
                        vagas_novas_sessao += 1
            
            loop_index += 1
            
        # Limpa o botão de parar no final
        stop_placeholder.empty()
        
        # Restaura o botão de iniciar (ou pede rerun)
        if vagas_novas_sessao > 0:
            status_box.update(label=f"Finalizado! {vagas_novas_sessao} novas vagas.", state="complete", expanded=False)
            st.success("Processo concluído.")
        else:
            status_box.update(label="Finalizado.", state="complete", expanded=False)

# --- GRID DE RESULTADOS ---
if st.session_state.vagas_encontradas:
    st.divider()
    st.subheader("Novas Oportunidades")
    cols = st.columns(2)
    for i, link in enumerate(st.session_state.vagas_encontradas):
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(f"**Vaga #{i+1}**")
                st.link_button("Aplicar Agora", link, use_container_width=True)