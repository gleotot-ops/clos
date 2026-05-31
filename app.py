import streamlit as st
import pandas as pd
import io
from weasyprint import HTML
import re

st.set_page_config(page_title="Le Clos Wine List Generator", layout="wide")
st.title("🍷 Le Clos Wine List Generator")
st.caption("Upload Revel CSV → Click Generate → Download PDF")

# 1. Upload Revel Export
uploaded_file = st.file_uploader("Upload Revel Inventory (CSV)", type=["csv"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)

    # Auto-detect common Revel columns
    col_map = {}
    for col in df.columns:
        c = col.lower().strip()
        if 'sku' in c: col_map['sku'] = col
        elif 'name' in c: col_map['name'] = col
        elif 'price' in c: col_map['price'] = col
        elif 'quantity in hand' in c or 'qty' in c: col_map['qty'] = col

    if not all(k in col_map for k in ['sku', 'name', 'price', 'qty']):
        st.error("⚠️ Could not find required columns: SKU, Name, Price, Quantity in Hand. Please check your CSV.")
        st.stop()

    df = df.rename(columns=col_map)[['sku', 'name', 'price', 'qty']]
    df = df[df['sku'].notna()]
    df['qty'] = pd.to_numeric(df['qty'], errors='coerce').fillna(0).astype(int)
    df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0).round(0).astype(int)

    # 2. Smart Section Mapping (Keyword-based fallback)
    SECTION_KEYWORDS = {
        "CHAMPAGNE": ["champagne", "sp", "sparkling"],
        "BURGUNDY": ["burgundy", "bourgogne", "chablis", "meursault", "puligny", "volnay", "corton"],
        "LOIRE VALLEY": ["loire", "sancerre", "chinon", "bourgueil", "saumur", "pouilly"],
        "RHÔNE VALLEY": ["rhone", "chateauneuf", "cote-rotie", "condrieu", "hermitage", "vacqueyras"],
        "LANGUEDOC-ROUSSILLON": ["languedoc", "roussillon", "bandol", "fitou", "corbieres"],
        "BORDEAUX": ["bordeaux", "pauillac", "margaux", "pomerol", "st-emilion", "saint-emilion", "haut-medoc"],
        "ROSÉ": ["rose", "rosé", "provence"],
        "REST OF THE WORLD": ["italy", "spain", "australia", "new zealand", "usa", "california", "oregon", "austria", "germany", "chile", "argentina", "corsica", "south africa"],
        "SWEET/FORTIFIED": ["sauternes", "barsac", "port", "sherry", "vin doux", "passito", "moscato"]
    }

    def get_section(sku, name):
        text = f"{sku} {name}".lower()
        for sec, keywords in SECTION_KEYWORDS.items():
            if any(k in text for k in keywords):
                return sec
        return "UNCATEGORIZED"

    df['section'] = df.apply(lambda r: get_section(r['sku'], r['name']), axis=1)

    # 3. Extract Vintage & Clean Name
    df['vintage'] = df['name'].str.extract(r'(\d{4})').fillna(0).astype(int)
    df['clean_name'] = df['name'].str.replace(r'\s*(\d{4})\s*$', '', regex=True).str.strip()

    # 4. Sort: Section Order → Vintage (Newest) → Name (A-Z)
    section_order = list(SECTION_KEYWORDS.keys()) + ["UNCATEGORIZED"]
    df['sec_rank'] = df['section'].map({s: i for i, s in enumerate(section_order)})
    df = df.sort_values(['sec_rank', 'vintage', 'clean_name'], ascending=[True, False, True])

    # 5. Generate HTML with CSS Dividers & Page Breaks
    html = """
    <style>
      body { font-family: 'Helvetica Neue', Arial, sans-serif; color: #222; margin: 40px; }
      h1 { text-align: center; color: #5a2d0c; margin-bottom: 30px; }
      .section { page-break-before: always; margin-top: 40px; border-top: 2px solid #8b5a2b; padding-top: 10px; }
      .section:first-child { page-break-before: avoid; }
      .wine { margin: 8px 0; padding: 6px 0; border-bottom: 1px dashed #ccc; display: flex; justify-content: space-between; }
      .wine span:first-child { font-weight: 500; }
      .oos { color: #c0392b; font-weight: bold; }
    </style>
    <h1>LE CLOS WINE LIST</h1>
    """

    current_sec = ""
    for _, row in df.iterrows():
        if row['section'] != current_sec:
            current_sec = row['section']
            html += f'<div class="section"><h2>{current_sec}</h2>'
        
        oos_tag = '<span class="oos">(OOS)</span>' if row['qty'] <= 0 else ''
        qty_text = f"{row['qty']} bottles {oos_tag}"
        vintage = f"{row['vintage']} " if row['vintage'] > 0 else ""
        html += f'<div class="wine"><span>{vintage}{row["clean_name"]}</span><span>${row["price"]} | {qty_text}</span></div>'

    html += "</div>" * (len(set(df['section'])))  # Close remaining sections

    # 6. Convert to PDF & Download
    if st.button("🖨️ Generate & Download PDF", type="primary"):
        with st.spinner("Generating PDF..."):
            pdf_bytes = HTML(string=html).write_pdf()
            st.download_button(
                label="⬇️ Download Wine List PDF",
                data=pdf_bytes,
                file_name="Le_Clos_Wine_List.pdf",
                mime="application/pdf"
            )
        st.success("✅ PDF generated successfully!")
