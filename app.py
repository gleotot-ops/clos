import streamlit as st
import pandas as pd
from fpdf import FPDF
import re

st.set_page_config(page_title="Le Clos Wine List Generator", layout="wide")
st.title("🍷 Le Clos Wine List Generator")
st.caption("Upload Revel Inventory → Auto-Categorize → Download PDF")

# Exact divider order from your PDF
SECTION_ORDER = [
    "CHAMPAGNES",
    "ROSÉ WINES",
    "MAGNUMS",
    "WHITE WINES FRANCE",
    "WHITE WINES REST OF THE WORLD",
    "RED WINES FRANCE",
    "RED WINES REST OF THE WORLD",
    "SWEET & FORTIFIED WINES",
    "WINE BY THE GLASS",
    "SPIRITS"
]

# Smart categorization keywords tailored to Revel exports
SECTION_KEYWORDS = {
    "CHAMPAGNES": ["champagne", "sp", "sparkling", "cremant", "brut nature", "blanc de blancs", "blanc de noirs"],
    "ROSÉ WINES": ["rosé", "rose ", "provence rose"],
    "MAGNUMS": ["magnum", "1.5l", "1,5l", "jumbo"],
    "WHITE WINES FRANCE": ["france - burgundy - white", "france - loire", "france - alsace", "france - rhone valley - white",
                           "france - bordeaux - white", "france - jura", "france - savoie", "france - chablis", "france - corsica",
                           "white", "blanc", "chardonnay", "sauvignon", "riesling", "chenin", "sancerre", "pouilly", "vouvray"],
    "RED WINES FRANCE": ["france - burgundy - red", "france - bordeaux - red", "france - rhone valley - red", "france - loire valley - red",
                         "france - beaujolais", "france - languedoc", "france - provence", "france - corsica - red",
                         "red", "rouge", "pinot noir", "syrah", "grenache", "merlot", "cabernet", "gamay", "chinon", "bordeaux", "burgundy"],
    "WHITE WINES REST OF THE WORLD": ["italy - white", "spain - white", "australia - white", "new zealand - white", "usa - white",
                                      "germany - white", "austria - white", "portugal - white", "japan - white", "south africa - white"],
    "RED WINES REST OF THE WORLD": ["italy - red", "spain - red", "australia - red", "new zealand - red", "usa - red", "argentina - red",
                                    "chile - red", "south africa - red", "portugal - red", "red", "rouge"],
    "SWEET & FORTIFIED WINES": ["sauternes", "barsac", "port", "sherry", "sweet", "fortified", "demi-sec", "moelleux", "tokaji", "vin doux"],
    "WINE BY THE GLASS": ["by the glass", "glass wine"],
    "SPIRITS": ["spirits", "gin", "vodka", "whisky", "rum", "tequila", "cognac", "armagnac", "liqueur", "vermouth"]
}

def get_section(name, sku):
    text = f"{name} {sku}".lower()
    # Priority checks
    if any(k in text for k in SECTION_KEYWORDS["MAGNUMS"]): return "MAGNUMS"
    if any(k in text for k in SECTION_KEYWORDS["CHAMPAGNES"]): return "CHAMPAGNES"
    if any(k in text for k in SECTION_KEYWORDS["ROSÉ WINES"]): return "ROSÉ WINES"
    if any(k in text for k in SECTION_KEYWORDS["SWEET & FORTIFIED WINES"]): return "SWEET & FORTIFIED WINES"
    
    # France vs Rest of World logic
    is_france = any(k in text for k in ["france", "bourgogne", "bordeaux", "loire", "rhone", "alsace", "chablis", "beaujolais", "jura", "savoie", "corsica", "provence", "languedoc"])
    is_white = any(k in text for k in ["white", "blanc", "chardonnay", "sauvignon", "riesling", "chenin", "aligoté", "viognier"])
    is_red = any(k in text for k in ["red", "rouge", "pinot noir", "syrah", "grenache", "merlot", "cabernet", "gamay", "mouvedre", "carignan"])
    
    if is_white: return "WHITE WINES FRANCE" if is_france else "WHITE WINES REST OF THE WORLD"
    if is_red: return "RED WINES FRANCE" if is_france else "RED WINES REST OF THE WORLD"
    
    return "RED WINES FRANCE"  # Safe default

def extract_vintage(name):
    match = re.search(r'\b(19|20)\d{2}\b', str(name))
    return int(match.group()) if match else 0

def clean_name(name):
    name = re.sub(r'\s*(19|20)\d{2}\s*$', '', str(name))
    name = re.sub(r'\s*\(Red\)|\(White\)', '', name, flags=re.IGNORECASE)
    return name.strip()

# File Upload
uploaded_file = st.file_uploader("Upload Revel Inventory (Excel or CSV)", type=["xlsx", "csv"])

if uploaded_file:
    try:
        # Load data
        df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('.xlsx') else pd.read_csv(uploaded_file)
        st.success(f"✅ Loaded {len(df)} items from Revel")
        
        # Auto-map Revel columns (handles capitalization/spaces)
        col_map = {}
        for col in df.columns:
            c = col.lower().strip()
            if 'name' in c: col_map['name'] = col
            if 'price' in c and 'cost' not in c and 'retail ex' not in c: col_map['price'] = col
            if 'quantity in hand' in c or 'qty' in c: col_map['qty'] = col
            if 'sku' in c: col_map['sku'] = col
            
        if 'name' not in col_map or 'price' not in col_map:
            st.error("❌ Missing 'Name' or 'Price' columns. Please ensure this is a standard Revel inventory export.")
            st.stop()
            
        df = df.rename(columns=col_map)
        df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0).round(0).astype(int)
        df['qty'] = pd.to_numeric(df.get('qty', pd.Series([0]*len(df))), errors='coerce').fillna(0).astype(int)
        df['sku'] = df.get('sku', pd.Series(['']*len(df))).fillna('').astype(str)
        
        # Filter out obvious non-wines (coffee, tea, spirits, etc.)
        wine_keywords = ['wine', 'champagne', 'rose', 'brut', 'cru', 'domaine', 'chateau', 'clos', 'vin', 'sancerre', 'bordeaux', 'burgundy']
        exclude_keywords = ['spritz', 'coffee', 'tea', 'juice', 'water', 'soda', 'beer', 'cider', 'spirit', 'gin', 'vodka', 'whisky', 'rum', 'tequila', 'liqueur', 'vermouth', 'aperol']
        
        keep_mask = df['name'].str.lower().str.contains('|'.join(wine_keywords), na=False) | \
                    (~df['name'].str.lower().str.contains('|'.join(exclude_keywords), na=False))
        df = df[keep_mask].copy()
        
        # Process
        df['section'] = df.apply(lambda r: get_section(r['name'], r['sku']), axis=1)
        df['vintage'] = df['name'].apply(extract_vintage)
        df['clean_name'] = df['name'].apply(clean_name)
        
        # Sort: Section Order → Vintage (Newest) → Name (A-Z)
        df['section_rank'] = df['section'].map({s: i for i, s in enumerate(SECTION_ORDER)})
        df = df.sort_values(['section_rank', 'vintage', 'clean_name'], ascending=[True, False, True])
        
        # Preview
        st.write("### 📋 Live Preview (First 15)")
        st.dataframe(df[['section', 'clean_name', 'vintage', 'price', 'qty']].head(15))
        
        # PDF Generation
        if st.button("🖨️ Generate & Download PDF", type="primary"):
            with st.spinner("Formatting wine list..."):
                pdf = FPDF()
                pdf.add_page()
                pdf.set_auto_page_break(auto=True, margin=15)
                
                # Header
                pdf.set_font("Helvetica", "B", 22)
                pdf.set_text_color(70, 35, 15)
                pdf.cell(0, 12, "LE CLOS", ln=True, align="C")
                pdf.set_font("Helvetica", "", 11)
                pdf.cell(0, 6, "WINE LIST", ln=True, align="C")
                pdf.ln(4)
                
                current_sec = ""
                for _, row in df.iterrows():
                    if row['section'] != current_sec:
                        current_sec = row['section']
                        pdf.ln(6)
                        pdf.set_font("Helvetica", "B", 11)
                        pdf.set_text_color(0, 0, 0)
                        pdf.set_fill_color(240, 240, 240)
                        pdf.cell(0, 7, current_sec, ln=True, fill=True)
                        pdf.ln(2)
                        
                    pdf.set_font("Helvetica", "", 9.5)
                    pdf.set_text_color(0, 0, 0)
                    vintage = f"{row['vintage']} " if row['vintage'] > 0 else ""
                    oos = " (OOS)" if row['qty'] <= 0 else ""
                    line = f"{vintage}{row['clean_name']} | ${row['price']} | {row['qty']} bottles{oos}"
                    pdf.multi_cell(0, 5.5, line)
                    
                pdf_bytes = pdf.output(dest='S').encode('latin-1')
                st.download_button("⬇️ Download Wine List PDF", data=pdf_bytes, file_name="Le_Clos_Wine_List.pdf", mime="application/pdf")
                st.success("✅ PDF generated successfully!")
                
    except Exception as e:
        st.error(f"❌ Processing Error: {str(e)}")
        st.exception(e)
else:
    st.info("👆 Upload your Revel inventory file to start")
    st.markdown("""
    **How it works:**
    1. Export from Revel → `Product Inventory`
    2. Upload the `.xlsx` or `.csv` file
    3. App auto-detects columns, filters non-wines, categorizes by region/color
    4. Click `Generate & Download PDF` for your formatted list
    """)
