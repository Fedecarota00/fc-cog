# === IMPORTS ===
import streamlit as st
import pandas as pd
import requests
import time
from io import BytesIO
import zipfile
import os
import openai
from translations import TEXTS
from jobpositions import JOB_KEYWORDS

# === STREAMLIT CONFIG ===
st.set_page_config(page_title="Lead Qualifier", layout="wide")

# === LANGUAGE SELECTION ===
st.sidebar.image("ecr_logo_resized.png", width=120)
language = st.sidebar.selectbox("🌍 Choose your language:", list(TEXTS.keys()))
TEXT = TEXTS[language]

# === TITLE & INTRO SECTION ===
st.markdown(f"""
    <div style="background-color: #1565c0; padding: 1rem 1.5rem; border-radius: 0.5rem; margin-bottom: 1rem;">
        <h2 style="margin: 0; color: white;"> FC Lead Qualification App</h2>
    </div>
""", unsafe_allow_html=True)

with st.expander("ℹ️ What is this tool?"):
    st.markdown("""
        **ECR Lead Qualification App** is a smart assistant that helps identify the most relevant financial professionals at a company.

        You simply provide a company domain (e.g., `ing.com`) or upload a list, and the app:

        - Uses **Hunter.io** to find verified email addresses.
        - Filters contacts based on **job titles** that match financial decision-makers.
        - Lets you **preview and generate** personalized LinkedIn messages with AI.
        - Exports results into Excel or CSV for your outreach campaigns.

        Built by Federico Carota as part of his thesis at HU University of Applied Sciences 🎓
    """)

# === API CONFIG ===
HUNTER_API_KEY = st.secrets["HUNTER_API_KEY"]
openai.api_key = st.secrets["OPENAI_API_KEY"]
PUBLIC_DOMAINS = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com"]

# === FUNCTIONS ===
def is_public_email(email):
    return email.split('@')[-1].lower() in PUBLIC_DOMAINS

def job_matches(position):
    if not position:
        return False
    position = position.lower()
    return any(set(keyword.lower().split()).issubset(set(position.split())) for keyword in JOB_KEYWORDS)

def get_leads_from_hunter(domain):
    url = f"https://api.hunter.io/v2/domain-search?domain={domain}&api_key={HUNTER_API_KEY}&limit=10"
    response = requests.get(url)
    if response.status_code != 200:
        try:
            error_text = response.json().get("errors", [{}])[0].get("details", "Unknown error")
        except:
            error_text = response.text
        return [], f"Error fetching domain {domain}: {response.status_code} – {error_text}"
    data = response.json()
    emails = data.get("data", {}).get("emails", [])
    company = data.get("data", {}).get("organization")
    for email in emails:
        email["company"] = company
    return emails, None

def filter_leads(leads):
    qualified = []
    for lead in leads:
        email = lead.get("value")
        position = lead.get("position")
        linkedin = lead.get("linkedin") or lead.get("linkedin_url")
        company = lead.get("company", "N/A")
        if not email or is_public_email(email):
            continue
        if job_matches(position):
            qualified.append({
                "Email": email,
                "Full Name": (lead.get("first_name") or "") + " " + (lead.get("last_name") or ""),
                "Position": position,
                "LinkedIn": linkedin,
                "Company": company,
                "Company Domain": lead.get("domain")
            })
    return qualified

def split_full_name(full_name):
    parts = full_name.strip().split()
    return (parts[0], " ".join(parts[1:])) if parts else ("", "")

def generate_ai_message(first_name, position, company):
    prompt = (
        f"You're creating a short, professional LinkedIn connection message for a person named {first_name}, "
        f"who is a {position} at {company}. The sender wants to offer macroeconomic research insights.\n"
        f"Keep it friendly, specific to the role, and under 250 characters. Avoid generic phrases."
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a LinkedIn outreach assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.9,
            max_tokens=100
        )
        return response['choices'][0]['message']['content'].strip()
    except:
        return f"Hi {first_name}, I’d love to connect regarding insights relevant to {position} at {company}."

# === PAGE LAYOUT ===
st.markdown("### 🔢 Step 1 – Upload or Enter Domains")
option = st.radio(TEXT['input_method'], (TEXT['manual_entry'], TEXT['upload_file']))

domains = []
if option == TEXT['manual_entry']:
    st.markdown(f"**{TEXT['enter_domain']}**")
    domain_input = st.text_input("e.g. ing.com")
    if domain_input:
        domains.append(domain_input.strip())
elif option == TEXT['upload_file']:
    uploaded_file = st.file_uploader(TEXT['upload_instruction'], type="xlsx")
    if uploaded_file:
        df_uploaded = pd.read_excel(uploaded_file)
        domains = df_uploaded.iloc[:, 1].dropna().unique().tolist()
        st.success(TEXT['uploaded_success'].format(n=len(domains)))

# === AI MESSAGE GENERATION ===
st.markdown("### 🤖 Step 2 – Preview an AI Message")
col1, col2 = st.columns(2)
with col1:
    test_first_name = st.text_input(TEXT["first_name"], value="Alex")
    test_position = st.text_input(TEXT["job_title"], value="Chief Financial Officer")
    test_company = st.text_input(TEXT["company"], value="ING Bank")
with col2:
    tone = st.radio(TEXT["message_tone"], ["Friendly", "Formal", "Data-driven", "Short & Punchy"])
    custom_instruction = st.text_input(TEXT["custom_instruction"], placeholder="e.g. Mention we are macro research providers")

if st.button(TEXT["generate_message"]):
    tone_instructions = {
        "Friendly": "Write in a warm, conversational tone.",
        "Formal": "Use a professional and respectful tone.",
        "Data-driven": "Use language that emphasizes insights and value.",
        "Short & Punchy": "Be concise, bold, and impactful."
    }
    preview_prompt = (
        f"You're writing a LinkedIn connection request to {test_first_name}, "
        f"who is a {test_position} at {test_company}. "
        f"{tone_instructions[tone]} {custom_instruction if custom_instruction else ''} Keep it under 250 characters."
    )
    ai_msg = generate_ai_message(test_first_name, test_position, test_company)
    st.success(TEXT["ai_result"])
    st.info(ai_msg)

# === RUN QUALIFICATION ===
st.markdown("### 🚀 Step 3 – Run Lead Qualification")
if st.button(TEXT["run_button"]) and domains:
    all_qualified = []
    with st.spinner(TEXT['processing']):
        for idx, domain in enumerate(domains):
            st.write(f"[{idx+1}/{len(domains)}] Processing domain: `{domain}`")
            leads, error = get_leads_from_hunter(domain)
            if error:
                st.error(error)
                continue
            qualified = filter_leads(leads)
            st.success(TEXT["qualified_count"].format(domain=domain, count=len(qualified)))
            all_qualified.extend(qualified)
            time.sleep(1.5)

    if all_qualified:
        df_qualified = pd.DataFrame(all_qualified)
        records = []
        first_example = None
        for lead in all_qualified:
            first_name, last_name = split_full_name(lead["Full Name"])
            company = lead["Company"]
            position = lead["Position"]
            message = generate_ai_message(first_name, position, company)
            if first_example is None:
                first_example = f"**{first_name}** ({position} at {company}):\n\n> {message}"
            records.append({
                "First Name": first_name,
                "Last Name": last_name,
                "LinkedIn URL": lead["LinkedIn"],
                "Company": company,
                "Job Title": position,
                "Personalized Message": message
            })

        if first_example:
            st.markdown(TEXT["example_message"])
            st.info(first_example)

        # Show editable messages
        first_name = records[0]['First Name']
        position = records[0]['Job Title']
        company = records[0]['Company']
        preview_message = generate_ai_message(first_name, position, company)

        st.markdown("### ✏️ Step 4 – Edit Your Message Template")
        st.markdown("Use placeholders like `{first_name}`, `{position}`, `{company}` to personalize.")

        default_template = preview_message.replace(first_name, "{first_name}").replace(position, "{position}").replace(company, "{company}")
        final_template = st.text_area("Your message template:", value=default_template)

        # Apply to all leads
        for record in records:
            record["Personalized Message"] = final_template.format(
                first_name=record["First Name"],
                position=record["Job Title"],
                company=record["Company"]
            )

        df_salesflow = pd.DataFrame(records)

        buffer_xlsx = BytesIO()
        df_qualified.to_excel(buffer_xlsx, index=False)
        buffer_csv = BytesIO()
        df_salesflow.to_csv(buffer_csv, index=False, encoding="utf-8-sig")
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zipf:
            zipf.writestr("qualified_leads.xlsx", buffer_xlsx.getvalue())
            zipf.writestr("salesflow_leads.csv", buffer_csv.getvalue())

        st.markdown("### 📥 Step 5 – Export Results")
        st.dataframe(df_qualified, use_container_width=True)
        st.download_button(TEXT["download_xlsx"], data=buffer_xlsx.getvalue(), file_name="qualified_leads.xlsx")
        st.download_button(TEXT["download_csv"], data=buffer_csv.getvalue(), file_name="salesflow_leads.csv")
        st.download_button(TEXT["download_zip"], data=zip_buffer.getvalue(), file_name="lead_outputs.zip")
    else:
        st.warning(TEXT["no_results"])











