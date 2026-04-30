import streamlit as st
import pandas as pd
from datetime import datetime
import time
import plotly.express as px
import json
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURATION ---
st.set_page_config(page_title="ChronoTech Elite", page_icon="🏭", layout="wide")

TARGET_TIMES = {
    "Débit + Usinage": 12, "Sertissage": 8, "Montage": 15,
    "Ferrage Ouvrant": 10, "Mise en bois": 7, "Vitrage + VR": 20, "Contrôle + Palettisation": 5
}

# --- CONNEXION GOOGLE SHEETS ---
@st.cache_resource
def init_connection():
    cred_dict = json.loads(st.secrets["gcp_json"])
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(cred_dict, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open("Base_Chronos_Technal").worksheet("Chronos")

sheet = init_connection()

# --- STYLE CSS ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #1f2937; padding: 15px; border-radius: 10px; border: 1px solid #374151; }
    div[data-testid="stExpander"] { border: none !important; box-shadow: none !important; }
    </style>
    """, unsafe_allow_html=True)

# --- LOGIQUE DU CHRONO ---
if 'running' not in st.session_state: st.session_state.running = False
if 'paused' not in st.session_state: st.session_state.paused = False
if 'pause_start' not in st.session_state: st.session_state.pause_start = None
if 'total_pause_duration' not in st.session_state: st.session_state.total_pause_duration = 0

# --- INTERFACE ---
st.title("🏭 ChronoTech Elite v3.0 (Cloud Edition)")
st.caption("Système de suivi de performance industrielle - Connecté en direct à Google Sheets")

tabs = st.tabs(["🚀 POSTE DE TRAVAIL", "📊 ANALYSE & REPORTING", "📂 HISTORIQUE BRUT"])

with tabs[0]:
    col_input, col_chrono = st.columns([1, 1.5])

    with col_input:
        with st.expander("📝 INFOS COMMANDE", expanded=True):
            cmd = st.text_input("N° Commande", placeholder="ex: CMD-2024-001")
            op = st.selectbox("Opérateur", ["Jordan", "Collaborateur A", "Collaborateur B"])
            qte = st.number_input("Quantité de produits", min_value=1, value=1)
            
        with st.expander("⚙️ CONFIGURATION PRODUIT", expanded=True):
            gamme = st.radio("Gamme", ["Technal", "Askey"], horizontal=True)
            prod = st.selectbox("Type", ["Fixe", "OB1", "OB2", "PF Standard", "PF Seuil", "Combiné"])
            etape = st.selectbox("Étape", list(TARGET_TIMES.keys()))
            com = st.text_input("Commentaire / Aléa")

    with col_chrono:
        st.markdown(f"### ⏱️ Session en cours : {etape}")
        
        container = st.empty()
        c1, c2, c3 = st.columns(3)
        
        if not st.session_state.running:
            if c1.button("▶️ DÉMARRER", use_container_width=True, type="primary"):
                if not cmd: st.error("Entrez un n° de commande")
                else:
                    st.session_state.start_time = datetime.now()
                    st.session_state.running = True
                    st.session_state.total_pause_duration = 0
                    st.rerun()
        else:
            if not st.session_state.paused:
                if c2.button("⏸️ PAUSE", use_container_width=True):
                    st.session_state.paused = True
                    st.session_state.pause_start = datetime.now()
                    st.rerun()
            else:
                if c2.button("▶️ REPRENDRE", use_container_width=True):
                    pause_delta = (datetime.now() - st.session_state.pause_start).total_seconds()
                    st.session_state.total_pause_duration += pause_delta
                    st.session_state.paused = False
                    st.rerun()

            if c3.button("⏹️ TERMINER", use_container_width=True):
                end_time = datetime.now()
                duree_brute = (end_time - st.session_state.start_time).total_seconds() / 60
                pause_totale = st.session_state.total_pause_duration / 60
                duree_nette = max(0, duree_brute - pause_totale)
                temps_unitaire = duree_nette / qte
                obj = TARGET_TIMES[etape]
                perf = (obj / temps_unitaire) * 100 if temps_unitaire > 0 else 0
                
                # ENVOI VERS GOOGLE SHEETS
                nouvelle_ligne = [
                    datetime.now().strftime("%Y-%m-%d"), cmd, op, gamme, prod, etape, qte,
                    round(duree_brute, 2), round(pause_totale, 2), round(duree_nette, 2),
                    round(temps_unitaire, 2), obj, round(perf, 1), com
                ]
                with st.spinner("Sauvegarde dans Google Sheets..."):
                    sheet.append_row(nouvelle_ligne)
                
                st.balloons()
                st.session_state.running = False
                st.rerun()

        # LE FAMEUX CHRONO GÉANT VERT QUI DÉFILE
        if st.session_state.running:
            if st.session_state.paused:
                container.metric("STATUT", "EN PAUSE", delta_color="off")
            else:
                elapsed = (datetime.now() - st.session_state.start_time).total_seconds() - st.session_state.total_pause_duration
                minutes, seconds = divmod(int(elapsed), 60)
                container.markdown(f"<h1 style='font-size: 80px; text-align: center; color: #00ff00;'>{minutes:02d}:{seconds:02d}</h1>", unsafe_allow_html=True)
                time.sleep(1)
                st.rerun()

with tabs[1]:
    st.subheader("📈 Analyse de Performance")
    if st.button("🔄 Actualiser les données"):
        st.rerun()
        
    records = sheet.get_all_records()
    if records:
        df_analysis = pd.DataFrame(records)
        df_analysis['Date'] = pd.to_datetime(df_analysis['Date'], errors='coerce')
        
        # Convertir en numérique au cas où Google Sheets renvoie du texte
        cols_to_num = ['Quantite', 'Temps_Unitaire', 'Performance', 'Pause_Min', 'Objectif']
        for col in cols_to_num:
            df_analysis[col] = pd.to_numeric(df_analysis[col], errors='coerce').fillna(0)
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Production Totale", f"{df_analysis['Quantite'].sum()} unités")
        m2.metric("Temps Moyen Unitaire", f"{round(df_analysis['Temps_Unitaire'].mean(), 1)} min")
        avg_perf = df_analysis['Performance'].mean()
        m3.metric("Performance Globale", f"{round(avg_perf, 1)}%", delta=f"{round(avg_perf-100,1)}% vs Objectif")
        m4.metric("Temps perdu (Pauses)", f"{round(df_analysis['Pause_Min'].sum(), 1)} min")

        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            st.write("**Réel vs Objectif par Étape (min)**")
            fig = px.bar(df_analysis.groupby('Etape')[['Temps_Unitaire', 'Objectif']].mean().reset_index(), 
                         x='Etape', y=['Temps_Unitaire', 'Objectif'], barmode='group',
                         color_discrete_sequence=['#3B82F6', '#10B981'])
            st.plotly_chart(fig, use_container_width=True)
            
        with col_chart2:
            st.write("**Performance par Gamme (%)**")
            fig2 = px.box(df_analysis, x='Gamme', y='Performance', color='Gamme')
            st.plotly_chart(fig2, use_container_width=True)
            
        st.write("**Évolution de la productivité journalière**")
        df_trend = df_analysis.groupby('Date')['Performance'].mean().reset_index()
        fig3 = px.line(df_trend, x='Date', y='Performance')
        st.plotly_chart(fig3, use_container_width=True)

    else:
        st.info("Aucune donnée dans Google Sheets pour l'instant. Lancez votre premier chrono !")

with tabs[2]:
    st.subheader("📄 Registre complet (Google Sheets)")
    records = sheet.get_all_records()
    if records:
        df_raw = pd.DataFrame(records)
        st.dataframe(df_raw, use_container_width=True)
        
        if st.button("🗑️ Effacer la dernière ligne (Erreur)"):
            # Si on a 3 enregistrements, ils sont sur les lignes 2, 3, 4 d'Excel.
            # Donc la dernière ligne est la ligne (nombre d'enregistrements + 1)
            derniere_ligne_index = len(records) + 1
            sheet.delete_rows(derniere_ligne_index)
            st.success("Ligne supprimée avec succès !")
            time.sleep(1)
            st.rerun()
