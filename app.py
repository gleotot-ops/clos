import streamlit as st
import pandas as pd
from fpdf import FPDF
import re
from io import BytesIO

st.set_page_config(page_title="Le Clos Wine List Generator", layout="wide")
st.title("🍷 Le Clos Wine List Generator")
st.caption("Upload Revel CSV → Click Generate → Download PDF")

# Section order from your divider
SECTION_ORDER = [
    "SPIRITS",
    "WINE BY THE GLASS",
    "MAGNUMS",
    "CHAMPAGNES",
    "ROSÉ WINES",
    "WHITE WINES FRANCE",
    "WHITE WINES REST OF THE WORLD",
    "RED WINES FRANCE",
    "RED WINES REST OF THE WORLD",
    "SWEET & FORTIFIED WINES"
]

# Keywords to map regions to sections
SECTION_KEYWORDS = {
    "CHAMPAGNES": ["champagne", "sparkling", "cremant", "spkg"],
    "ROSÉ WINES": ["rosé", "rose", "provence"],
    "MAGNUMS": ["magnum", "1.5l", "jumbo", "large format"],
    "WHITE WINES FRANCE": ["france - burgundy - white", "france - loire", "france - alsace", 
                           "france - rhone valley - white", "france - bordeaux - white",
                           "france - jura", "france - savoie", "france - chablis", "france - corsica"],
    "RED WINES FRANCE": ["france - burgundy - red", "france - bordeaux - red",
                         "france - rhone valley - red", "france - loire valley - red",
                         "france - beaujolais", "france - languedoc", "france - provence", "france - corsica - red"],
    "WHITE WINES REST OF THE WORLD": ["italy - white", "spain - white", "australia - white",
                                      "new zealand - white", "usa - white", "germany - white",
                                      "austria - white", "portugal - white", "japan - white", "south africa - white"],
    "RED WINES REST OF THE WORLD": ["italy - red", "spain - red", "australia - red",
                                    "new zealand - red", "usa - red", "argentina - red",
                                    "chile - red", "south africa - red", "portugal - red"],
    "SWEET & FORTIFIED WINES": ["sauternes", "barsac", "port", "sherry", "sweet", "fortified", "demi-sec"],
    "WINE BY THE GLASS": ["by the glass", "glass wine"],
    "SPIRITS": ["spirits", "gin", "vodka", "whisky", "rum", "tequila", "cognac", "armagnac"]
}

def get_section_from_region(region, name):
    """Map region/name to section"""
    if pd.isna(region):
        region = ""
    text = f"{region} {name}".lower()
    
    for section, keywords in SECTION_KEYWORDS.items():
        if any(k in text for k in keywords):
            return section
    
    # Default based on common patterns
    if "white" in text:
        return "WHITE WINES FRANCE" if "france" in text else "WHITE WINES REST OF THE WORLD"
    elif "red" in text:
        return "RED WINES FRANCE" if "france" in text else "RED WINES REST OF THE WORLD"
    
    return "RED WINES FRANCE"  # Default

def extract_vintage(name):
    """Extract vintage year from wine name"""
    if pd.isna(name):
        return 0
    match = re.search(r'\b(19|20)\d{2}\b', str(name))
    return int(match.group()) if match else 0

def clean_wine_name(name):
    """Remove vintage from name for cleaner display"""
    if pd.isna(name):
        return ""
    return re.sub(r'\s*(19|20)\d{2}\s*$', '', str(name)).strip()

# File upload
uploaded_file = st.file_uploader("Upload Revel Inventory (CSV or Excel)", type=["csv", "xlsx"])

if uploaded_file is not None:
    try:
        # Load file
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        st.success(f"✅ Loaded {len(df)} items")
        
        # Show available columns for debugging
        with st.expander("📋 View detected columns"):
            st.write("Available columns:", list(df.columns))
            st.write("First 3 rows:")
            st.dataframe(df.head(3))
        
        # Auto-detect columns (case-insensitive)
        col_map = {}
        df_columns_lower = {col.lower().strip(): col for col in df.columns}
        
        # Map common column names
        for lower_col, orig_col in df_columns_lower.items():
            if 'sku' in lower_col or 'productcode' in lower_col or 'barcode' in lower_col:
                if 'sku' not in col_map:
                    col_map['sku'] = orig_col
            if 'name' in lower_col and 'product' not in lower_col:
                if 'name' not in col_map:
                    col_map['name'] = orig_col
            if 'retail' in lower_col and 'price' in lower_col:
                if 'price' not in col_map:
                    col_map['price'] = orig_col
            if 'quantity in hand' in lower_col or 'qty' in lower_col or 'inventory' in lower_col:
                if 'qty' not in col_map:
                    col_map['qty'] = orig_col
            if 'category' in lower_col or 'group' in lower_col:
                if 'category' not in col_map:
                    col_map['category'] = orig_col
            if 'region' in lower_col or 'additionalattribute6' in lower_col:
                if 'region' not in col_map:
                    col_map['region'] = orig_col
        
        st.write("🗺️ Column mapping:", col_map)
        
        # Check required columns
        required = ['name', 'price']
        missing = [r for r in required if r not in col_map]
        if missing:
            st.error(f"⚠️ Missing required columns: {', '.join(missing)}")
            st.info("💡 Please ensure your Revel export has columns for wine Name and Price")
            st.stop()
        
        # Rename columns to standard names
        df = df.rename(columns=col_map)
        
        # Keep only needed columns if they exist
        keep_cols = ['sku', 'name', 'price', 'qty', 'category', 'region']
        available_cols = [c for c in keep_cols if c in df.columns]
        df = df[available_cols].copy()
        
        # Ensure name and price exist
        if 'name' not in df.columns or 'price' not in df.columns:
            st.error("❌ Critical error: Name or Price column not found after mapping")
            st.stop()
        
        # Filter wines only (if Category column exists)
        if 'category' in df.columns:
            df = df[df['category'].str.lower().str.contains('wine', na=True)]
        
        # Clean data
        df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0).round(0).astype(int)
        if 'qty' in df.columns:
            df['qty'] = pd.to_numeric(df['qty'], errors='coerce').fillna(0).astype(int)
        else:
            df['qty'] = 0
        
        # Extract data
        df['section'] = df.apply(lambda r: get_section_from_region(
            r.get('region', ''), r.get('name', '')
        ), axis=1)
        
        df['vintage'] = df['name'].apply(extract_vintage)
        df['clean_name'] = df['name'].apply(clean_wine_name)
        
        # Sort by section order, then vintage (newest first), then name
        df['section_rank'] = df['section'].map({s: i for i, s in enumerate(SECTION_ORDER)})
        df = df.sort_values(['section_rank', 'vintage', 'clean_name'], 
                           ascending=[True, False, True])
        
        # Preview
        st.write("### Preview (first 20 items)")
        preview_cols = ['section', 'clean_name', 'vintage', 'price']
        if 'qty' in df.columns:
            preview_cols.append('qty')
        st.dataframe(df[preview_cols].head(20))
        
        # Generate PDF button
        if st.button("🖨️ Generate & Download PDF", type="primary"):
            with st.spinner("Generating PDF..."):
                pdf = FPDF()
                pdf.add_page()
                pdf.set_auto_page_break(auto=True, margin=15)
                
                # Title
                pdf.set_font("Helvetica", "B", 24)
                pdf.set_text_color(90, 45, 12)
                pdf.cell(0, 20, "LE CLOS WINE LIST", ln=True, align="C")
                pdf.ln(5)
                
                current_section = ""
                for _, row in df.iterrows():
                    # Section header
                    if row['section'] != current_section:
                        current_section = row['section']
                        pdf.ln(8)
                        pdf.set_font("Helvetica", "B", 14)
                        pdf.set_text_color(0, 0, 0)
                        pdf.set_fill_color(240, 240, 240)
                        pdf.cell(0, 10, current_section, ln=True, fill=True)
                        pdf.ln(3)
                    
                    # Wine entry
                    pdf.set_font("Helvetica", "", 10)
                    pdf.set_text_color(0, 0, 0)
                    
                    vintage = f"{row['vintage']} " if row['vintage'] > 0 else ""
                    oos = " (OOS)" if row.get('qty', 0) <= 0 else ""
                    
                    line = f"{vintage}{row['clean_name']} | ${row['price']} | {row.get('qty', 0)} bottles{oos}"
                    pdf.multi_cell(0, 6, line)
                
                # Output
                pdf_bytes = pdf.output(dest='S').encode('latin-1')
                
                st.download_button(
                    label="⬇️ Download Wine List PDF",
                    data=pdf_bytes,
                    file_name=f"Le_Clos_Wine_List.pdf",
                    mime="application/pdf"
                )
                st.success("✅ PDF ready for download!")
    
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        st.exception(e)

else:
    st.info("👆 Upload your Revel inventory export to get started")
    
    st.markdown("""
    ### How to use:
    1. Export inventory from Revel as CSV or Excel
    2. Upload the file above
    3. Click "Generate & Download PDF"
    4. Your professionally formatted wine list will be ready!
    
    **Required columns:** Name, Retail Price  
    **Optional columns:** SKU, Quantity in Hand, Category/Region
    """)
