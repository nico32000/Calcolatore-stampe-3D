import streamlit as st
from streamlit_option_menu import option_menu
import sqlite3
import pandas as pd
from datetime import date

# --- Database setup ---
def get_connection():
    return sqlite3.connect("nicoprint.db", check_same_thread=False)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS filamenti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            marca TEXT,
            materiale TEXT,
            peso_totale REAL,
            peso_bobina_vuota REAL,
            peso_netto REAL,
            ultima_essiccazione TEXT
        )
    """)
    conn.commit()
    conn.close()

def salva_filamento(nome, marca, materiale, peso_totale, peso_bobina_vuota, peso_netto, ultima_essiccazione):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO filamenti (nome, marca, materiale, peso_totale, peso_bobina_vuota, peso_netto, ultima_essiccazione)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (nome, marca, materiale, peso_totale, peso_bobina_vuota, peso_netto, str(ultima_essiccazione)))
    conn.commit()
    conn.close()

def carica_filamenti():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM filamenti", conn)
    conn.close()
    return df

def elimina_filamento(id_filamento):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM filamenti WHERE id = ?", (id_filamento,))
    conn.commit()
    conn.close()

init_db()

# --- UI ---
st.title("Dashboard NicoPrint.ch")
with st.sidebar:
    selected = option_menu("Menu", ["Home", 'Storage filamenti', "Bliancio", "Preventivi"])

if selected == "Home":
    st.header("Home")
    st.write("Bentornato alla NicoPrint.ch dashboard!")

if selected == "Storage filamenti":
    st.header("Storage filamenti")
    st.write("Gestisci i tuoi filamenti qui!")

    with st.expander("Aggiungi filamento"):
        filamento_da_aggiungere = st.text_input("Nome filamento")
        peso_da_aggiungere = st.number_input("Peso filamento totale (g)", min_value=0)
        peso_bobina_vuota = st.number_input("Peso bobina vuota (g)", min_value=0)
        marca_da_aggiungere = st.text_input("Marca filamento")
        materiale_da_aggiungere = st.text_input("Materiale filamento")
        ultima_essicazione_da_aggiungere = st.date_input("Ultima essiccazione filamento")
        peso_netto_da_aggiungere = peso_da_aggiungere - peso_bobina_vuota

        st.write(f"Peso netto calcolato: {peso_netto_da_aggiungere} g")

        if st.button("Salva filamento"):
            if filamento_da_aggiungere:
                salva_filamento(
                    filamento_da_aggiungere,
                    marca_da_aggiungere,
                    materiale_da_aggiungere,
                    peso_da_aggiungere,
                    peso_bobina_vuota,
                    peso_netto_da_aggiungere,
                    ultima_essicazione_da_aggiungere
                )
                st.success(f"Filamento '{filamento_da_aggiungere}' salvato!")
                st.rerun()
            else:
                st.error("Inserisci almeno il nome del filamento.")

    st.subheader("Filamenti salvati")