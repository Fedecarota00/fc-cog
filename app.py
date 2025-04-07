SCORE_THRESHOLD = st.slider("Minimum confidence score", min_value=0, max_value=100, value=50)

st.markdown("Insert here the SalesFlow message you would like to send to each lead in the campaign:")
use_ai = st.checkbox("✨ Use AI to generate personalized messages", value=True)
default_template = "Hi {first_name}, I came across your profile as {position} at {company} – I'd love to connect!"
user_template = st.text_area("Message Template (you can use {first_name}, {position}, {company})", value=default_template)

option = st.radio("Choose input method:", ("Manual domain entry", "Upload Excel file"))
domains = []

if option == "Manual domain entry":
    domain_input = st.text_input("Enter a domain to search leads for (e.g. ing.com):")
    if domain_input:
        domains.append(domain_input.strip())
else:
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
            qualified = filter_leads(leads, SCORE_THRESHOLD)
            st.success(f"✅ Qualified leads from {domain}: {len(qualified)}")
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

            message = generate_ai_message(first_name, position, company) if use_ai else user_template.format(
                first_name=first_name,
                last_name=last_name,
                company=company,
                position=position
            )

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

        df_salesflow = pd.DataFrame(records)

        if first_example:
            st.markdown("### 📄 Example AI-Generated Message")
            st.info(first_example)

        buffer_xlsx = BytesIO()
        df_qualified.to_excel(buffer_xlsx, index=False)

        buffer_csv = BytesIO()
        df_salesflow.to_csv(buffer_csv, index=False, encoding="utf-8-sig", sep=',')

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zipf:
            zipf.writestr("qualified_leads.xlsx", buffer_xlsx.getvalue())
            zipf.writestr("salesflow_leads.csv", buffer_csv.getvalue())

        st.dataframe(df_qualified, use_container_width=True)

        st.download_button("⬇️ Download Qualified Leads (.xlsx)", data=buffer_xlsx.getvalue(), file_name="qualified_leads.xlsx")
        st.download_button("⬇️ Download Salesflow CSV", data=buffer_csv.getvalue(), file_name="salesflow_leads.csv")
        st.download_button("⬇️ Download All as ZIP", data=zip_buffer.getvalue(), file_name="lead_outputs.zip")
    else:
        st.warning("No qualified leads found. Try a different domain or file.")
















