import streamlit as st
import pandas as pd
from datetime import datetime
import time
import plotly.express as px
import json
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURATION ---
st.set_page_config(page_title="ChronoTech Cloud", page_icon="🏭", layout="wide")

TARGET_TIMES = {
    "Débit + Usinage": 12, "Sertissage": 8, "Montage": 15,
    "Ferrage Ouvrant": 10, "Mise en bois": 7, "Vitrage + VR": 20, "Contrôle + Palettisation": 5
}

# --- CONNEXION GOOGLE SHEETS ---
@st.cache_resource
def init_connection():
    # On lit le fichier JSON caché dans les paramètres secrets de Streamlit
    cred_dict = json.loads(st.secrets["gcp_json"])
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(cred_dict, scopes=scopes)
    client = gspread.authorize(creds)
    
    # ⚠️ METTEZ ICI LE NOM EXACT DE VOTRE GOOGLE SHEETS
    return client.open("Base_Chronos_Technal").worksheet("Chronos")

try:
    sheet = init_connection()
except Exception as e:
    st.error(f"⚠️ ERREUR TECHNIQUE EXACTE : {e}")
    st.stop()

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
st.title("🏭 ChronoTech Cloud (Connecté à Google Sheets)")

tabs = st.tabs(["🚀 POSTE DE TRAVAIL", "📊 ANALYSE & REPORTING", "📂 HISTORIQUE EN DIRECT"])

with tabs[0]:
    col_input, col_chrono = st.columns([1, 1.5])

    with col_input:
        with st.expander("📝 INFOS COMMANDE", expanded=True):
            cmd = st.text_input("N° Commande", placeholder="ex: CMD-2024-001")
            op = st.selectbox("Opérateur", ["", "Jordan", "Collaborateur A", "Collaborateur B"])
            qte = st.number_input("Quantité de produits", min_value=1, value=1)
            
        with st.expander("⚙️ CONFIGURATION PRODUIT", expanded=True):
            gamme = st.radio("Gamme", ["Technal", "Askey"], horizontal=True)
            prod = st.selectbox("Type", ["Fixe", "OB1", "OB2", "PF Standard", "PF Seuil", "Combiné"])
            etape = st.selectbox("Étape", list(TARGET_TIMES.keys()))
            com = st.text_input("Commentaire / Aléa")

    with col_chrono:
        st.markdown(f"### ⏱️ Session : {etape}")
        container = st.empty()
        c1, c2, c3 = st.columns(3)
        
        if not st.session_state.running:
            if c1.button("▶️ DÉMARRER", use_container_width=True, type="primary"):
                if not cmd or not op: st.error("Entrez la commande et l'opérateur")
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
                
                # Envoi direct vers Google Sheets
                nouvelle_ligne = [
                    datetime.now().strftime("%Y-%m-%d"), cmd, op, gamme, prod, etape, qte,
                    round(duree_brute, 2), round(pause_totale, 2), round(duree_nette, 2),
                    round(temps_unitaire, 2), obj, round(perf, 1), com
                ]
                
                with st.spinner("Envoi vers Google Sheets..."):
                    sheet.append_row(nouvelle_ligne)
                
                st.success("✅ Enregistré dans Google Sheets !")
                st.balloons()
                st.session_state.running = False
                time.sleep(2)
                st.rerun()

        if st.session_state.running:
            if st.session_state.paused:
                container.warning("⏸️ CHRONO EN PAUSE")
            else:
                heure_depart = st.session_state.start_time.strftime('%H:%M:%S')
                container.info(f"⏳ Tâche en cours... Démarrée à {heure_depart}")
                container.caption("L'application tourne en arrière-plan. Appuyez sur Terminer quand la tâche est finie.")

with tabs[1]:
    st.subheader("📈 Statistiques Google Sheets")
    if st.button("🔄 Actualiser les données"):
        st.rerun()
        
    records = sheet.get_all_records()
    if records:
        df_analysis = pd.DataFrame(records)
        # On convertit les colonnes numériques pour éviter les erreurs
        cols_to_num = ['Quantite', 'Temps_Unitaire', 'Performance', 'Pause_Min']
        for col in cols_to_num:
            df_analysis[col] = pd.to_numeric(df_analysis[col], errors='coerce').fillna(0)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Production Totale", f"{df_analysis['Quantite'].sum()} unités")
        m2.metric("Temps Moyen Unitaire", f"{round(df_analysis['Temps_Unitaire'].mean(), 1)} min")
        avg_perf = df_analysis['Performance'].mean()
        m3.metric("Performance", f"{round(avg_perf, 1)}%", delta=f"{round(avg_perf-100,1)}% vs Obj")
        m4.metric("Temps perdu (Pauses)", f"{round(df_analysis['Pause_Min'].sum(), 1)} min")

        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            fig = px.bar(df_analysis.groupby('Etape')[['Temps_Unitaire', 'Objectif']].mean().reset_index(), 
                         x='Etape', y=['Temps_Unitaire', 'Objectif'], barmode='group')
            st.plotly_chart(fig, use_container_width=True)
            
        with col_chart2:
            fig2 = px.box(df_analysis, x='Gamme', y='Performance', color='Gamme')
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Aucune donnée dans le Google Sheets pour le moment.")

with tabs[2]:
    st.subheader("📄 Registre Google Sheets")
    records = sheet.get_all_records()
    if records:
        df_raw = pd.DataFrame(records)
        st.dataframe(df_raw, use_container_width=True)
