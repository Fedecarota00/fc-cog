import streamlit as st
import pandas as pd
import requests
import time
from io import BytesIO
import zipfile
from PIL import Image
import os

# === CONFIGURATION ===
HUNTER_API_KEY = "f68566d43791af9b30911bc0fe8a65a89908d4fe"
SCORE_THRESHOLD = 50
PUBLIC_DOMAINS = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com"]

JOB_KEYWORDS = ["Chief Executive Officer", "CEO", "Chief Financial Officer", "CFO", "Chief Operating Officer", "COO",
    "Chief Investment Officer", "CIO", "Chief Risk Officer", "CRO", "Chief Compliance Officer", "CCO", "Chief Accounting Officer", "CAO",
    "Head of Treasury", "Treasury Director", "Treasury Manager", "Treasury Analyst", "Cash Manager", "Liquidity Manager",
    "Asset Liability Management Manager", "ALM Manager", "Head of Finance", "Finance Director", "Financial Controller", "FC",
    "Accounting Manager", "Financial Reporting Manager", "Financial Analyst", "FA", "Management Accountant", "Regulatory Reporting Analyst",
    "Financial Planning and Analysis Manager", "FP&A Manager", "Portfolio Manager", "PM", "Investment Director", "Fund Manager",
    "Buy-Side Analyst", "Sell-Side Analyst", "Investment Analyst", "Wealth Manager", "Private Banker", "Risk Manager",
    "Credit Risk Analyst", "Operational Risk Officer", "Market Risk Manager", "Compliance Officer", "Regulatory Affairs Manager",
    "Head of Strategy", "Strategy Director", "Corporate Development Manager", "Mergers and Acquisitions Analyst", "M&A Analyst",
    "M&A Manager", "Business Development Director", "BDD", "Relationship Manager", "RM", "Corporate Banker", "SME Banker",
    "Credit Analyst", "Loan Officer", "Branch Manager", "Head of Trading", "Trader", "FX Trader", "Equity Trader",
    "Fixed Income Trader", "Sales and Trading Analyst", "Market Analyst", "Internal Auditor", "Financial Crime Officer",
    "IT Risk Manager", "Data Analyst", "Financial Technology Manager", "Chief Actuary", "Actuary", "Underwriter",
    "Risk Pricing Analyst", "Claims Manager", "Claims Adjuster", "Operations Manager", "Policy Administration Officer",
    "Insurance Product Manager", "Broker Relations Manager", "Insurance Sales Manager", "Business Development Executive",
    "Reinsurance Analyst", "Reinsurance Manager", "Regulatory Compliance Officer", "Head of Finance Transformation",
    "Head of Digital Banking", "Fintech Manager", "ESG Finance Lead", "Financial Risk and Control Manager",
    "Data Governance Manager", "Procurement and Vendor Risk Manager", "Vice President of Finance", "VP Finance",
    "Director of Finance", "Director of Treasury", "Director of Risk", "Director of Compliance", "Head of Function",
    "VP of Function", "Director of Function", "Investment Manager", "Investment Assistant", "Head of Portfolio Management",
    "Head of Fund Management", "Fund Assistant", "Head of Multi-Asset Equity", "Head of Fixed Income", "Chief Strategist",
    "Strategist (Market/Financial)", "Chief Economist", "Head of Research", "Economist", "Chief Analyst", "Analyst (Fund or Other)",
    "Head of Asset Management", "Asset Manager", "Head of Wealth Management", "Wealth Adviser", "Chief Dealer",
    "Head of Money Markets", "Head of Capital Markets", "Chief Stockbroker", "Head of Private Banking", "Head of Client Advisory",
    "Head of Client Assets", "Client Portfolio Manager", "Head of HNWI", "Head of FX", "Head of Cash Management",
    "Head of Pensions", "Chief Investment Strategist", "Executive Director Investment Risk", "Chief Of Investment Execution",
    "Head Of M&A", "Liquidity Management & Financing", "Treasury", "Portfolio", "Asset", "Multi-asset", "Multi Asset"]

# === FUNCTIONS ===
def is_public_email(email):
    domain = email.split('@')[-1]
    return domain.lower() in PUBLIC_DOMAINS

def job_matches(position):
    if not position:
        return False

    position_lower = position.lower()
    for keyword in JOB_KEYWORDS:
        if keyword.lower() in position_lower:
            return True
    return False

def get_leads_from_hunter(domain):
    url = f"https://api.hunter.io/v2/domain-search?domain={domain}&api_key={HUNTER_API_KEY}&limit=100&emails_type=all"
    response = requests.get(url)
    if response.status_code != 200:
        return [], f"Error fetching domain {domain}: {response.status_code}"
    data = response.json()
    emails = data.get("data", {}).get("emails", [])
    company = data.get("data", {}).get("organization")

    # Debug: Print all retrieved emails
    for email in emails:
        st.text(f"RAW: {email.get('first_name')} {email.get('last_name')} | {email.get('value')} | {email.get('position')} | Score: {email.get('confidence')}")

    for email in emails:
        email["company"] = company
    return emails, None

def filter_leads(leads):
    qualified = []
    for lead in leads:
        email = lead.get("value")
        position = lead.get("position")
        score = lead.get("confidence", 0)
        linkedin = lead.get("linkedin") or lead.get("linkedin_url")
        company = lead.get("company", "N/A")

        # Debug reasons for skipping
        if not email:
            st.info("Skipped: No email")
            continue
        if is_public_email(email):
            st.info(f"Skipped: Public email – {email}")
            continue
        if score < SCORE_THRESHOLD:
            st.info(f"Skipped: Low score ({score}) – {email}")
            continue
        if not job_matches(position):
            st.info(f"Skipped: No match on title – {position}")
            continue

        qualified.append({
            "Email": email,
            "Full Name": (lead.get("first_name") or "") + " " + (lead.get("last_name") or ""),
            "Position": position,
            "Confidence Score": score,
            "LinkedIn": linkedin,
            "Company": company,
            "Company Domain": lead.get("domain")
        })
    return qualified

def split_full_name(full_name):
    parts = full_name.strip().split()
    if len(parts) == 0:
        return "", ""
    elif len(parts) == 1:
        return parts[0], ""
    else:
        return parts[0], " ".join(parts[1:])

def generate_salesflow_data(qualified_leads):
    records = []
    for lead in qualified_leads:
        first_name, last_name = split_full_name(lead["Full Name"])
        message = f"Hi {first_name}, I came across your profile as {lead['Position']} at {lead['Company']} – I'd love to connect!"
        records.append({
            "First Name": first_name,
            "Last Name": last_name,
            "LinkedIn URL": lead["LinkedIn"],
            "Company": lead["Company"],
            "Job Title": lead["Position"],
            "Personalized Message": message
        })
    return pd.DataFrame(records)

# === STREAMLIT UI ===
st.set_page_config(page_title="Lead Qualifier", layout="centered")

# === LOGO ===
logo_path = "ecr_logo_resized.png"
if os.path.exists(logo_path):
    st.image(logo_path, width=120)

st.markdown("""
<h2 style='text-align: center; color: #ffffff; background-color: #001F54; padding: 15px; border-radius: 10px;'>
    🔍 ECR Lead Qualification App
</h2>
<div style='background-color:#f0f4ff;padding:20px 25px;border-left:6px solid #003366;border-radius:6px;margin:20px 0 30px 0;'>
  <p style='font-size:16px;line-height:1.5;color:#333333;font-family:"Times New Roman",serif;font-weight:bold;'>
    This application was developed by Federico Carota as part of his graduation thesis project at HU of Applied Sciences, with the objective of supporting lead qualification processes at <b>ECR Research</b>.
    <br><br>
    Combining verified email scoring, job title matching, and LinkedIn integration, the tool automates the identification of key financial decision-makers using smart filtering logic.
    <br><br>
    It is designed to streamline outreach workflows and increase the relevance of targeted leads.
  </p>
</div>
""", unsafe_allow_html=True)

# === LANGUAGE SELECTION ===
language = st.selectbox("Choose your language:", ["English", "Italian", "Dutch", "German", "French", "Spanish"])

# === TRANSLATION TEXTS ===
TEXTS = {
    "English": {
        "input_method": "Choose input method:",
        "manual_entry": "Manual domain entry",
        "upload_file": "Upload Excel file",
        "enter_domain": "Enter a domain to search leads for:",
        "run_button": "🚀 Run Lead Qualification",
        "uploaded_success": "Loaded {n} domain(s) from file.",
        "processing": "Working through the domains and filtering qualified leads...",
        "qualified_count": "✅ Qualified leads from {domain}: {count}",
        "preview_header": "📋 Preview of Qualified Leads",
        "download_section": "🎉 Export Your Results:",
        "no_results": "No qualified leads found. Try a different domain or file.",
        "upload_instruction": "Upload an .xlsx file with domains in column B:"
    },
    "Italian": {
        "input_method": "Scegli il metodo di inserimento:",
        "manual_entry": "Inserimento manuale del dominio",
        "upload_file": "Carica file Excel",
        "enter_domain": "Inserisci un dominio per cercare contatti:",
        "run_button": "🚀 Avvia Qualificazione Contatti",
        "uploaded_success": "Caricati {n} domini dal file.",
        "processing": "Elaborazione domini e filtraggio contatti qualificati...",
        "qualified_count": "✅ Contatti qualificati da {domain}: {count}",
        "preview_header": "📋 Anteprima Contatti Qualificati",
        "download_section": "🎉 Esporta i tuoi risultati:",
        "no_results": "Nessun contatto qualificato trovato. Prova con un altro dominio o file.",
        "upload_instruction": "Carica un file .xlsx con domini nella colonna B:"
    },
    "Dutch": {
        "input_method": "Kies invoermethode:",
        "manual_entry": "Handmatige domeininvoer",
        "upload_file": "Upload Excel-bestand",
        "enter_domain": "Voer een domein in om leads te zoeken:",
        "run_button": "🚀 Start Leadkwalificatie",
        "uploaded_success": "{n} domeinen geladen uit bestand.",
        "processing": "Bezig met verwerken van domeinen en filteren van gekwalificeerde leads...",
        "qualified_count": "✅ Gekwalificeerde leads van {domain}: {count}",
        "preview_header": "📋 Voorbeeld van Gekwalificeerde Leads",
        "download_section": "🎉 Exporteer je resultaten:",
        "no_results": "Geen gekwalificeerde leads gevonden. Probeer een ander domein of bestand.",
        "upload_instruction": "Upload een .xlsx-bestand met domeinen in kolom B:"
    },
    "German": {
        "input_method": "Wählen Sie die Eingabemethode:",
        "manual_entry": "Manuelle Domain-Eingabe",
        "upload_file": "Excel-Datei hochladen",
        "enter_domain": "Geben Sie eine Domain zur Lead-Suche ein:",
        "run_button": "🚀 Lead-Qualifizierung starten",
        "uploaded_success": "{n} Domains aus Datei geladen.",
        "processing": "Verarbeite Domains und filtere qualifizierte Leads...",
        "qualified_count": "✅ Qualifizierte Leads von {domain}: {count}",
        "preview_header": "📋 Vorschau Qualifizierter Leads",
        "download_section": "🎉 Ergebnisse exportieren:",
        "no_results": "Keine qualifizierten Leads gefunden. Versuchen Sie es mit einer anderen Domain oder Datei.",
        "upload_instruction": "Laden Sie eine .xlsx-Datei mit Domains in Spalte B hoch:"
    },
    "French": {
        "input_method": "Choisissez la méthode de saisie :",
        "manual_entry": "Saisie manuelle du domaine",
        "upload_file": "Télécharger un fichier Excel",
        "enter_domain": "Entrez un domaine pour rechercher des contacts :",
        "run_button": "🚀 Lancer la qualification des leads",
        "uploaded_success": "{n} domaines chargés depuis le fichier.",
        "processing": "Traitement des domaines et filtrage des leads qualifiés...",
        "qualified_count": "✅ Leads qualifiés pour {domain} : {count}",
        "preview_header": "📋 Aperçu des leads qualifiés",
        "download_section": "🎉 Exportez vos résultats :",
        "no_results": "Aucun lead qualifié trouvé. Essayez un autre domaine ou fichier.",
        "upload_instruction": "Téléversez un fichier .xlsx avec les domaines dans la colonne B :"
    },
    "Spanish": {
        "input_method": "Elige el método de entrada:",
        "manual_entry": "Entrada manual del dominio",
        "upload_file": "Subir archivo Excel",
        "enter_domain": "Introduce un dominio para buscar contactos:",
        "run_button": "🚀 Ejecutar Calificación de Leads",
        "uploaded_success": "{n} dominios cargados desde el archivo.",
        "processing": "Procesando dominios y filtrando leads calificados...",
        "qualified_count": "✅ Leads calificados de {domain}: {count}",
        "preview_header": "📋 Vista previa de leads calificados",
        "download_section": "🎉 Exporta tus resultados:",
        "no_results": "No se encontraron leads calificados. Prueba con otro dominio o archivo.",
        "upload_instruction": "Sube un archivo .xlsx con dominios en la columna B:"
    }
}

TEXT = TEXTS[language]

option = st.radio(TEXT['input_method'], (TEXT['manual_entry'], TEXT['upload_file']))

st.markdown("""<hr style='border:1px solid #cccccc'>""", unsafe_allow_html=True)

domains = []

if option == TEXT['manual_entry']:
    st.markdown("**Enter a domain to search leads for:**")
    domain_input = st.text_input("e.g. ing.com")
    if domain_input:
        domains.append(domain_input.strip())

elif option == TEXT['upload_file']:
    uploaded_file = st.file_uploader("Upload an .xlsx file with domains in column B:", type="xlsx")
    if uploaded_file:
        df_uploaded = pd.read_excel(uploaded_file)
        domains = df_uploaded.iloc[:, 1].dropna().unique().tolist()
        st.success(f"Loaded {len(domains)} domain(s) from file.")

st.markdown("""<br><hr style='border:1px solid #cccccc'>""", unsafe_allow_html=True)

if st.button("🚀 Run Lead Qualification") and domains:
    all_qualified = []
    with st.spinner("Working through the domains and filtering qualified leads..."):
        for idx, domain in enumerate(domains):
            st.write(f"[{idx+1}/{len(domains)}] Processing domain: `{domain}`")
            leads, error = get_leads_from_hunter(domain)
            if error:
                st.error(error)
                continue
            qualified = filter_leads(leads)
            st.success(f"✅ Qualified leads from {domain}: {len(qualified)}")
            all_qualified.extend(qualified)
            time.sleep(1.5)

    if all_qualified:
        df_qualified = pd.DataFrame(all_qualified)
        df_salesflow = generate_salesflow_data(all_qualified)

        buffer_xlsx = BytesIO()
        df_qualified.to_excel(buffer_xlsx, index=False)

        buffer_csv = BytesIO()
        df_salesflow.to_csv(buffer_csv, index=False, encoding="utf-8-sig", sep=',')

        st.markdown("""
<div style='background-color:#f0f4ff;padding:20px 25px;border-left:6px solid #003366;border-radius:6px;margin-top:25px;'>
  <h4 style='color:#003366;'>📋 Preview of Qualified Leads</h4>
</div>
""", unsafe_allow_html=True)

        st.dataframe(df_qualified, use_container_width=True)

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zipf:
            zipf.writestr("qualified_leads.xlsx", buffer_xlsx.getvalue())
            zipf.writestr("salesflow_leads.csv", buffer_csv.getvalue())

        st.markdown("""
        <div style='background-color:#E3F2FD;padding:20px;border-radius:10px;'>
            <h4 style='color:#0d47a1;'>🎉 Export Your Results:</h4>
        </div>
        """, unsafe_allow_html=True)

        st.download_button("⬇️ Download Qualified Leads (.xlsx)", data=buffer_xlsx.getvalue(), file_name="qualified_leads.xlsx")
        st.download_button("⬇️ Download Salesflow CSV", data=buffer_csv.getvalue(), file_name="salesflow_leads.csv")
        st.download_button("⬇️ Download All as ZIP", data=zip_buffer.getvalue(), file_name="lead_outputs.zip")

    else:
        st.warning("No qualified leads found. Try a different domain or file.")


