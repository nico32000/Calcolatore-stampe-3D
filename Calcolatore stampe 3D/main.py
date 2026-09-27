import streamlit as st
from streamlit_option_menu import option_menu
import sqlite3
import pandas as pd
from datetime import date
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from io import BytesIO
import base64
import fitz

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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimenti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT,
            descrizione TEXT,
            importo REAL,
            data TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clienti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE,
            email TEXT,
            telefono TEXT,
            data_creazione TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS preventivi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_cliente INTEGER,
            numero_preventivo TEXT UNIQUE,
            descrizione TEXT,
            data_creazione TEXT,
            stato TEXT,
            prezzo_totale REAL,
            costo_totale REAL,
            margine_percentuale REAL,
            FOREIGN KEY (id_cliente) REFERENCES clienti(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS preventivi_filamenti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_preventivo INTEGER,
            id_filamento INTEGER,
            quantita_grammi REAL,
            prezzo_grammo REAL,
            FOREIGN KEY (id_preventivo) REFERENCES preventivi(id),
            FOREIGN KEY (id_filamento) REFERENCES filamenti(id)
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

def get_filamento_by_id(id_filamento):
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM filamenti WHERE id = ?", conn, params=(id_filamento,))
    conn.close()
    return df

def aggiorna_filamento(id_filamento, nome, marca, materiale, peso_totale, peso_bobina_vuota, peso_netto, ultima_essiccazione):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE filamenti 
        SET nome = ?, marca = ?, materiale = ?, peso_totale = ?, peso_bobina_vuota = ?, peso_netto = ?, ultima_essiccazione = ?
        WHERE id = ?
    """, (nome, marca, materiale, peso_totale, peso_bobina_vuota, peso_netto, str(ultima_essiccazione), id_filamento))
    conn.commit()
    conn.close()

def salva_movimento(tipo, descrizione, importo, data):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO movimenti (tipo, descrizione, importo, data)
        VALUES (?, ?, ?, ?)
    """, (tipo, descrizione, importo, str(data)))
    conn.commit()
    conn.close()

def carica_movimenti():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM movimenti ORDER BY data DESC", conn)
    conn.close()
    return df

def elimina_movimento(id_movimento):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM movimenti WHERE id = ?", (id_movimento,))
    conn.commit()
    conn.close()

def calcola_bilancio():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM movimenti", conn)
    conn.close()

    if df.empty:
        return 0, 0, 0

    guadagni = df[df['tipo'] == 'Guadagno']['importo'].sum()
    spese = df[df['tipo'] == 'Spesa']['importo'].sum()
    totale = guadagni - spese

    return guadagni, spese, totale

# --- Funzioni per Clienti ---
def salva_cliente(nome, email, telefono):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO clienti (nome, email, telefono, data_creazione)
            VALUES (?, ?, ?, ?)
        """, (nome, email, telefono, str(date.today())))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

def carica_clienti():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM clienti", conn)
    conn.close()
    return df

def get_cliente_by_id(id_cliente):
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM clienti WHERE id = ?", conn, params=(id_cliente,))
    conn.close()
    return df

def elimina_cliente(id_cliente):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM clienti WHERE id = ?", (id_cliente,))
    conn.commit()
    conn.close()

# --- Funzioni per Preventivi ---
def salva_preventivo(id_cliente, numero_preventivo, descrizione, data_creazione, prezzo_totale, costo_totale):
    conn = get_connection()
    cursor = conn.cursor()

    if costo_totale > 0:
        margine_percentuale = ((prezzo_totale - costo_totale) / costo_totale) * 100
    else:
        margine_percentuale = 0

    try:
        cursor.execute("""
            INSERT INTO preventivi (id_cliente, numero_preventivo, descrizione, data_creazione, stato, prezzo_totale, costo_totale, margine_percentuale)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (id_cliente, numero_preventivo, descrizione, str(data_creazione), "Bozza", prezzo_totale, costo_totale, margine_percentuale))
        conn.commit()
        preventivo_id = cursor.lastrowid
        conn.close()
        return preventivo_id
    except sqlite3.IntegrityError:
        conn.close()
        return None

def carica_preventivi():
    conn = get_connection()
    df = pd.read_sql_query("SELECT p.*, c.nome as cliente FROM preventivi p JOIN clienti c ON p.id_cliente = c.id", conn)
    conn.close()
    return df

def carica_preventivi_cliente(id_cliente):
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM preventivi WHERE id_cliente = ?", conn, params=(id_cliente,))
    conn.close()
    return df

def get_preventivo_by_id(id_preventivo):
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM preventivi WHERE id = ?", conn, params=(id_preventivo,))
    conn.close()
    return df

def aggiungi_filamento_preventivo(id_preventivo, id_filamento, quantita_grammi, prezzo_al_chilo):
    conn = get_connection()
    cursor = conn.cursor()
    # Converti prezzo al chilo a prezzo al grammo
    prezzo_grammo = prezzo_al_chilo / 1000
    cursor.execute("""
        INSERT INTO preventivi_filamenti (id_preventivo, id_filamento, quantita_grammi, prezzo_grammo)
        VALUES (?, ?, ?, ?)
    """, (id_preventivo, id_filamento, quantita_grammi, prezzo_grammo))
    conn.commit()
    conn.close()

def carica_filamenti_preventivo(id_preventivo):
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT pf.*, f.nome as nome_filamento 
        FROM preventivi_filamenti pf 
        JOIN filamenti f ON pf.id_filamento = f.id 
        WHERE pf.id_preventivo = ?
    """, conn, params=(id_preventivo,))
    conn.close()
    return df

def elimina_filamento_preventivo(id_filamento_preventivo):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM preventivi_filamenti WHERE id = ?", (id_filamento_preventivo,))
    conn.commit()
    conn.close()

def elimina_preventivo(id_preventivo):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM preventivi_filamenti WHERE id_preventivo = ?", (id_preventivo,))
    cursor.execute("DELETE FROM preventivi WHERE id = ?", (id_preventivo,))
    conn.commit()
    conn.close()

def genera_numero_preventivo():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM preventivi")
    count = cursor.fetchone()[0] + 1
    conn.close()
    return f"PREV-{count:04d}"

def calcola_costi_spese():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM movimenti WHERE tipo = 'Spesa'", conn)
    conn.close()
    if df.empty:
        return 0
    return df['importo'].sum()

def genera_pdf_preventivo(id_preventivo, nome_cliente):
    preventivo = get_preventivo_by_id(id_preventivo)
    if preventivo.empty:
        return None

    preventivo = preventivo.iloc[0]
    filamenti = carica_filamenti_preventivo(id_preventivo)

    # Crea il PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    elements = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1f4788'),
        spaceAfter=30,
        alignment=1
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#333333'),
        spaceAfter=10
    )

    # Titolo
    elements.append(Paragraph("PREVENTIVO", title_style))
    elements.append(Spacer(1, 0.2*inch))

    # Informazioni preventivo
    info_data = [
        ['Numero Preventivo:', preventivo['numero_preventivo']],
        ['Cliente:', nome_cliente],
        ['Data:', preventivo['data_creazione']],
        ['Stato:', preventivo['stato']],
    ]

    info_table = Table(info_data, colWidths=[2*inch, 4*inch])
    info_table.setStyle(TableStyle([
        ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 10),
        ('FONT', (1, 0), (1, -1), 'Helvetica', 10),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.3*inch))

    # Tabella filamenti
    elements.append(Paragraph("ARTICOLI", heading_style))

    table_data = [['Filamento', 'Quantità (g)', 'Prezzo Unitario (€)', 'Totale (€)']]

    for idx, row in filamenti.iterrows():
        prezzo_totale_riga = row['quantita_grammi'] * row['prezzo_grammo']
        table_data.append([
            row['nome_filamento'],
            f"{row['quantita_grammi']:.2f}",
            f"{row['prezzo_grammo']:.4f}",
            f"{prezzo_totale_riga:.2f}"
        ])

    # Aggiungi riga totale
    table_data.append(['', '', 'TOTALE:', f"{preventivo['prezzo_totale']:.2f}"])

    table = Table(table_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f0f0f0')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 11),
        ('TOPPADDING', (0, -1), (-1, -1), 12),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f9f9f9')]),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.3*inch))

    # Footer
    elements.append(Paragraph("Grazie per la fiducia! 🙏", styles['Normal']))

    doc.build(elements)
    buffer.seek(0)
    return buffer

init_db()

# --- UI ---
st.title("Dashboard NicoPrint.ch")
with st.sidebar:
    selected = option_menu("Menu", ["Home", 'Storage filamenti', "Bliancio", "Preventivi"])

if selected == "Home":
    st.header("Home")
    st.write("Bentornato alla NicoPrint.ch dashboard!")
    st.columns(2)
    column1, column2 = st.columns(2)
    with column1:
        st.header("Filamenti salvati")
        df_filamenti = carica_filamenti()
        st.dataframe(df_filamenti)
    with column2:
        st.header("Clienti salvati")
        df_clienti = carica_clienti()
        st.dataframe(df_clienti)

    st.header("Bilancio")
    guadagni_totali, spese_totali, utile_netto = calcola_bilancio()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Guadagni totali", f"€ {guadagni_totali:.2f}")

    with col2:
        st.metric("Spese totali", f"€ {spese_totali:.2f}")

    with col3:
        if utile_netto >= 0:
            st.metric("Utile netto", f"€ {utile_netto:.2f}", delta=f"+€ {utile_netto:.2f}", delta_color="normal")
        else:
            st.metric("Utile netto", f"€ {utile_netto:.2f}", delta=f"€ {utile_netto:.2f}", delta_color="inverse")



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
    with st.expander("Visualizza filamenti"):
            df_filamenti = carica_filamenti()
            if not df_filamenti.empty:
                st.dataframe(df_filamenti)
                id_da_eliminare = st.number_input("ID del filamento da eliminare", min_value=1, step=1)
                if st.button("Elimina filamento"):
                    elimina_filamento(id_da_eliminare)
                    st.success(f"Filamento con ID {id_da_eliminare} eliminato!")
                    st.rerun()

                st.divider()
                st.subheader("Modifica filamento")
                id_da_modificare = st.number_input("ID del filamento da modificare", min_value=1, step=1)

                if st.button("Carica filamento"):
                    df_filamento = get_filamento_by_id(id_da_modificare)
                    if not df_filamento.empty:
                        st.session_state['filamento_selezionato'] = df_filamento.iloc[0].to_dict()
                    else:
                        st.error(f"Filamento con ID {id_da_modificare} non trovato!")

                if 'filamento_selezionato' in st.session_state:
                    filamento = st.session_state['filamento_selezionato']
                    st.subheader(f"Modifica: {filamento['nome']}")

                    nome_mod = st.text_input("Nome filamento", value=filamento['nome'])
                    marca_mod = st.text_input("Marca filamento", value=filamento['marca'])
                    materiale_mod = st.text_input("Materiale filamento", value=filamento['materiale'])
                    peso_totale_mod = st.number_input("Peso filamento totale (g)", value=float(filamento['peso_totale']), min_value=0.0)
                    peso_bobina_vuota_mod = st.number_input("Peso bobina vuota (g)", value=float(filamento['peso_bobina_vuota']), min_value=0.0)
                    peso_netto_mod = peso_totale_mod - peso_bobina_vuota_mod
                    st.write(f"Peso netto calcolato: {peso_netto_mod} g")
                    ultima_essicazione_mod = st.date_input("Ultima essiccazione filamento", value=pd.to_datetime(filamento['ultima_essiccazione']).date())

                    if st.button("Salva modifiche"):
                        aggiorna_filamento(
                            id_da_modificare,
                            nome_mod,
                            marca_mod,
                            materiale_mod,
                            peso_totale_mod,
                            peso_bobina_vuota_mod,
                            peso_netto_mod,
                            ultima_essicazione_mod
                        )
                        st.success(f"Filamento '{nome_mod}' aggiornato!")
                        if 'filamento_selezionato' in st.session_state:
                            del st.session_state['filamento_selezionato']
                        st.rerun()

            else:
                st.write("Nessun filamento salvato.")


if selected == "Bliancio":
    st.header("Bilancio")

    # Calcola i totali
    guadagni_totali, spese_totali, utile_netto = calcola_bilancio()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Guadagni totali", f"€ {guadagni_totali:.2f}")

    with col2:
        st.metric("Spese totali", f"€ {spese_totali:.2f}")

    with col3:
        if utile_netto >= 0:
            st.metric("Utile netto", f"€ {utile_netto:.2f}", delta=f"+€ {utile_netto:.2f}", delta_color="normal")
        else:
            st.metric("Utile netto", f"€ {utile_netto:.2f}", delta=f"€ {utile_netto:.2f}", delta_color="inverse")

    st.divider()

    # Tab per aggiungere movimenti e visualizzare
    tab1, tab2 = st.tabs(["Aggiungi movimento", "Visualizza movimenti"])

    with tab1:
        st.subheader("Aggiungi guadagno o spesa")

        col1, col2 = st.columns(2)
        with col1:
            tipo_movimento = st.selectbox("Tipo di movimento", ["Guadagno", "Spesa"])

        with col2:
            importo = st.number_input("Importo (€)", min_value=0.0, step=0.01)

        descrizione = st.text_input("Descrizione")
        data_movimento = st.date_input("Data")

        if st.button("Salva movimento"):
            if descrizione:
                salva_movimento(tipo_movimento, descrizione, importo, data_movimento)
                st.success(f"{tipo_movimento} di € {importo:.2f} salvato!")
                st.rerun()
            else:
                st.error("Inserisci una descrizione!")

    with tab2:
        st.subheader("Elenco movimenti")

        df_movimenti = carica_movimenti()

        if not df_movimenti.empty:
            # Colora le righe in base al tipo
            def colora_riga(row):
                if row['tipo'] == 'Guadagno':
                    return ['background-color: #20f553'] * len(row)
                else:
                    return ['background-color: #fa283b'] * len(row)

            st.dataframe(df_movimenti.style.apply(colora_riga, axis=1), use_container_width=True)

            st.divider()
            st.subheader("Elimina movimento")
            id_da_eliminare = st.number_input("ID del movimento da eliminare", min_value=1, step=1)

            if st.button("Elimina movimento"):
                elimina_movimento(id_da_eliminare)
                st.success(f"Movimento con ID {id_da_eliminare} eliminato!")
                st.rerun()
        else:
            st.write("Nessun movimento salvato.")
if  selected == "Preventivi":
    st.header("Preventivi")
    st.write("Gestisci i tuoi preventivi qui!")

    # Tabs per gestire clienti e preventivi
    tab_clienti, tab_preventivi = st.tabs(["Clienti", "Preventivi"])

    with tab_clienti:
        st.subheader("Gestione Clienti")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Aggiungi cliente")
            nome_cliente = st.text_input("Nome cliente")
            email_cliente = st.text_input("Email cliente")
            telefono_cliente = st.text_input("Telefono cliente")

            if st.button("Aggiungi cliente"):
                if nome_cliente:
                    if salva_cliente(nome_cliente, email_cliente, telefono_cliente):
                        st.success(f"Cliente '{nome_cliente}' aggiunto!")
                        st.rerun()
                    else:
                        st.error(f"Cliente '{nome_cliente}' esiste già!")
                else:
                    st.error("Inserisci il nome del cliente!")

        with col2:
            st.subheader("Visualizza clienti")
            df_clienti = carica_clienti()

            if not df_clienti.empty:
                st.dataframe(df_clienti[['id', 'nome', 'email', 'telefono']], use_container_width=True)

                st.divider()
                id_cliente_elimina = st.number_input("ID cliente da eliminare", min_value=1, step=1, key="elimina_cliente")
                if st.button("Elimina cliente"):
                    elimina_cliente(id_cliente_elimina)
                    st.success(f"Cliente con ID {id_cliente_elimina} eliminato!")
                    st.rerun()
            else:
                st.write("Nessun cliente salvato.")

    with tab_preventivi:
        st.subheader("Gestione Preventivi")

        # Sezione per creare nuovo preventivo
        with st.expander("Crea nuovo preventivo"):
            st.subheader("Nuovo preventivo")

            df_clienti = carica_clienti()
            if df_clienti.empty:
                st.error("Aggiungi almeno un cliente prima di creare preventivi!")
            else:
                clienti_dict = dict(zip(df_clienti['nome'], df_clienti['id']))
                cliente_selezionato = st.selectbox("Seleziona cliente", options=df_clienti['nome'].tolist())
                id_cliente_preventivo = clienti_dict[cliente_selezionato]

                descrizione_preventivo = st.text_area("Descrizione preventivo")

                st.subheader("Aggiungi filamenti al preventivo")

                # Session state per gestire i filamenti nel preventivo
                if 'filamenti_preventivo' not in st.session_state:
                    st.session_state['filamenti_preventivo'] = []

                col1, col2, col3 = st.columns(3)

                df_filamenti = carica_filamenti()
                if not df_filamenti.empty:
                    filamenti_dict = dict(zip(df_filamenti['nome'], df_filamenti['id']))

                    with col1:
                        filamento_sel = st.selectbox("Filamento", options=df_filamenti['nome'].tolist(), key="filamento_sel_prev")
                    with col2:
                        quantita_grammi = st.number_input("Quantità (g)", min_value=0.0, step=0.1, key="quantita_prev")
                    with col3:
                        prezzo_chilo = st.number_input("Prezzo al chilo (€/kg)", min_value=0.0, step=0.01, key="prezzo_prev")

                    if st.button("Aggiungi filamento al preventivo"):
                        if filamento_sel and quantita_grammi > 0:
                            prezzo_grammo = prezzo_chilo / 1000
                            st.session_state['filamenti_preventivo'].append({
                                'nome': filamento_sel,
                                'id': filamenti_dict[filamento_sel],
                                'quantita': quantita_grammi,
                                'prezzo_chilo': prezzo_chilo,
                                'prezzo_grammo': prezzo_grammo,
                                'totale': quantita_grammi * prezzo_grammo
                            })
                            st.success(f"Filamento '{filamento_sel}' aggiunto al preventivo!")
                            st.rerun()

                if st.session_state['filamenti_preventivo']:
                    st.divider()
                    st.subheader("Filamenti nel preventivo")

                    filamenti_tabella = []
                    costo_totale = 0

                    for idx, filamento in enumerate(st.session_state['filamenti_preventivo']):
                        filamenti_tabella.append([
                            filamento['nome'],
                            f"{filamento['quantita']:.2f}",
                            f"{filamento['prezzo_chilo']:.2f}",
                            f"{filamento['totale']:.2f}",
                            idx
                        ])
                        costo_totale += filamento['totale']

                    df_filamenti_prev = pd.DataFrame(filamenti_tabella, columns=['Filamento', 'Quantità (g)', 'Prezzo €/kg', 'Totale (€)', 'Indice'])
                    st.dataframe(df_filamenti_prev[['Filamento', 'Quantità (g)', 'Prezzo €/kg', 'Totale (€)']], use_container_width=True)

                    st.write(f"**Costo totale filamenti: € {costo_totale:.2f}**")

                    # Calcola costi aggiuntivi
                    spese_totali = calcola_costi_spese()
                    st.write(f"**Spese generali aziendali: € {spese_totali:.2f}**")

                    # Spesa di progettazione
                    st.divider()
                    st.subheader("Spesa di progettazione")
                    ore_progettazione = st.number_input("Ore di progettazione", min_value=0.0, step=0.5, value=0.0, key="ore_prog")
                    prezzo_orario = 5.0
                    costo_progettazione = ore_progettazione * prezzo_orario
                    st.write(f"**Costo progettazione: {ore_progettazione} ore × € {prezzo_orario}/ora = € {costo_progettazione:.2f}**")

                    # Margine di guadagno
                    st.divider()
                    st.subheader("Calcolo prezzo finale")
                    margine_percentuale = st.slider("Margine di guadagno (%)", min_value=0, max_value=500, value=30, step=5)

                    # Calcola costo totale incluso progettazione e spese
                    costo_totale_con_spese = costo_totale + spese_totali + costo_progettazione
                    prezzo_finale = costo_totale_con_spese * (1 + margine_percentuale / 100)

                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Costo filamenti", f"€ {costo_totale:.2f}")
                    with col2:
                        st.metric("Spese generali", f"€ {spese_totali:.2f}")
                    with col3:
                        st.metric("Progettazione", f"€ {costo_progettazione:.2f}")
                    with col4:
                        st.metric("Margine", f"{margine_percentuale}%")

                    st.write(f"**Costo totale: € {costo_totale_con_spese:.2f}**")
                    st.write(f"**Prezzo finale cliente: € {prezzo_finale:.2f}**")

                    if st.button("Salva preventivo"):
                        numero_preventivo = genera_numero_preventivo()
                        id_preventivo = salva_preventivo(
                            id_cliente_preventivo,
                            numero_preventivo,
                            descrizione_preventivo,
                            date.today(),
                            prezzo_finale,
                            costo_totale_con_spese
                        )

                        if id_preventivo:
                            for filamento in st.session_state['filamenti_preventivo']:
                                aggiungi_filamento_preventivo(
                                    id_preventivo,
                                    filamento['id'],
                                    filamento['quantita'],
                                    filamento['prezzo_chilo']
                                )

                            st.success(f"Preventivo {numero_preventivo} creato con successo!")
                            st.session_state['filamenti_preventivo'] = []
                            st.rerun()
                        else:
                            st.error("Errore nel salvataggio del preventivo!")

        st.divider()
        st.subheader("Preventivi salvati")

        df_preventivi = carica_preventivi()

        if not df_preventivi.empty:
            # Visualizza preventivi per cliente
            clienti_unici = df_preventivi['cliente'].unique()
            cliente_filtro = st.selectbox("Filtra per cliente", options=["Tutti"] + list(clienti_unici))

            if cliente_filtro == "Tutti":
                df_visualizza = df_preventivi
            else:
                df_visualizza = df_preventivi[df_preventivi['cliente'] == cliente_filtro]

            st.dataframe(df_visualizza[['id', 'numero_preventivo', 'cliente', 'descrizione', 'data_creazione', 'prezzo_totale', 'margine_percentuale', 'stato']], use_container_width=True)

            st.divider()
            st.subheader("Visualizza e scarica preventivo")

            id_preventivo = st.number_input("ID preventivo", min_value=1, step=1, key="id_prev_viz")

            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button("Visualizza dettagli", key="btn_dettagli"):
                    st.session_state['mostra_dettagli'] = True

            with col2:
                if st.button("Anteprima PDF", key="btn_anteprima"):
                    st.session_state['mostra_pdf'] = True

            with col3:
                if st.button("Elimina preventivo", key="btn_elimina"):
                    st.session_state['elimina_conf'] = True

            # Visualizza dettagli
            if st.session_state.get('mostra_dettagli', False):
                st.divider()
                st.subheader("Dettagli Preventivo")
                preventivo = get_preventivo_by_id(id_preventivo)

                if preventivo.empty:
                    st.error(f"❌ Preventivo con ID {id_preventivo} non trovato!")
                    st.write(f"Debug: Controllare se l'ID {id_preventivo} esiste nel database")
                else:
                    prev = preventivo.iloc[0]
                    col_d1, col_d2 = st.columns(2)
                    with col_d1:
                        st.write(f"**Numero:** {prev['numero_preventivo']}")
                        st.write(f"**Cliente ID:** {prev['id_cliente']}")
                        st.write(f"**Data:** {prev['data_creazione']}")
                        st.write(f"**Descrizione:** {prev['descrizione']}")
                    with col_d2:
                        st.write(f"**Prezzo totale:** € {prev['prezzo_totale']:.2f}")
                        st.write(f"**Costo totale:** € {prev['costo_totale']:.2f}")
                        st.write(f"**Margine guadagno:** {prev['margine_percentuale']:.2f}%")
                        st.write(f"**Stato:** {prev['stato']}")

                    st.subheader("Filamenti inclusi")
                    df_filamenti_prev = carica_filamenti_preventivo(id_preventivo)
                    if not df_filamenti_prev.empty:
                        st.dataframe(df_filamenti_prev[['nome_filamento', 'quantita_grammi', 'prezzo_grammo']], use_container_width=True)
                    else:
                        st.info("Nessun filamento incluso in questo preventivo")

                    if st.button("Chiudi dettagli", key="btn_chiudi_dettagli"):
                        st.session_state['mostra_dettagli'] = False
                        st.rerun()

            # Visualizza PDF
            if st.session_state.get('mostra_pdf', False):
                st.divider()
                st.subheader("Anteprima PDF")
                preventivo = get_preventivo_by_id(id_preventivo)

                if preventivo.empty:
                    st.error(f"❌ Preventivo con ID {id_preventivo} non trovato!")
                else:
                    prev = preventivo.iloc[0]
                    try:
                        # Prova a prendere il nome del cliente dal database
                        cliente = get_cliente_by_id(prev['id_cliente'])
                        if not cliente.empty:
                            nome_cliente = cliente.iloc[0]['nome']
                        else:
                            # Se il cliente non esiste, usa l'ID come fallback
                            nome_cliente = f"Cliente ID {prev['id_cliente']}"

                        pdf_buffer = genera_pdf_preventivo(id_preventivo, nome_cliente)
                        if pdf_buffer:
                            pdf_buffer.seek(0)
                            base64_pdf = base64.b64encode(pdf_buffer.read()).decode('utf-8')
                            pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="900px"></iframe>'
                            st.markdown(pdf_display, unsafe_allow_html=True)

                            st.divider()
                            pdf_buffer.seek(0)
                            st.download_button(
                                label="📥 Scarica PDF",
                                data=pdf_buffer.getvalue(),
                                file_name=f"{prev['numero_preventivo']}.pdf",
                                mime="application/pdf",
                                key="btn_download"
                            )

                            if st.button("Chiudi anteprima", key="btn_chiudi_pdf"):
                                st.session_state['mostra_pdf'] = False
                                st.rerun()
                        else:
                            st.error("Errore nella generazione del PDF")
                    except Exception as e:
                        st.error(f"Errore nella generazione del PDF: {str(e)}")
                        st.write(f"Dettagli errore: {str(e)}")

            # Conferma eliminazione
            if st.session_state.get('elimina_conf', False):
                st.divider()
                st.warning(f"⚠️ Sei sicuro di voler eliminare il preventivo con ID {id_preventivo}?")
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    if st.button("✅ Sì, elimina", key="btn_elimina_si"):
                        elimina_preventivo(id_preventivo)
                        st.session_state['elimina_conf'] = False
                        st.success(f"Preventivo con ID {id_preventivo} eliminato!")
                        st.rerun()
                with col_e2:
                    if st.button("❌ Annulla", key="btn_elimina_no"):
                        st.session_state['elimina_conf'] = False
                        st.rerun()
        else:
            st.write("Nessun preventivo salvato.")


