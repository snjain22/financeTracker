import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import plotly.express as px
import os
import json

# --- Google Sheets setup ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/15DvUPuzkUOIw7JxDx69peorkoVfOff58OMTsllszLYM/edit?usp=sharing"
SCOPE = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive'
]

creds = json.loads(st.secrets["gcp_service_account"])


@st.cache_data
def load_data():
    """Load data from Google Sheets with caching"""
    try:
        # Get the directory where the script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        creds_path = os.path.join(script_dir, 'creds.json')
        
        if not os.path.exists(creds_path):
            return None, f"Credentials file not found at: {creds_path}"
            
        credentials = Credentials.from_service_account_info(creds, scopes=SCOPE)
        client = gspread.authorize(credentials)
        sheet = client.open_by_url(SHEET_URL)
        worksheet = sheet.get_worksheet(0)
        records = worksheet.get_all_records()
        
        df = pd.DataFrame(records)
        
        if df.empty:
            return None, "No data found in the spreadsheet"
        
        # --- Preprocessing ---
        if 'Timestamp' in df.columns:
            df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
        if 'Debit Amount' in df.columns:
            df['Debit Amount'] = pd.to_numeric(df['Debit Amount'], errors='coerce').fillna(0)
        if 'Credit Amount' in df.columns:
            df['Credit Amount'] = pd.to_numeric(df['Credit Amount'], errors='coerce').fillna(0)
        
        return df, None
    except FileNotFoundError as e:
        return None, f"File not found: {e}"
    except Exception as e:
        return None, f"Error loading data: {str(e)}"

# --- Streamlit UI ---
st.title("📊 Financial Tracker Dashboard")

# Load data after UI title is rendered
df, error = load_data()

if df is None:
    st.error(f"❌ {error}")
    st.info("Please check:")
    st.info("1. That `creds.json` exists in the same directory")
    st.info("2. That your Google Sheets credentials are valid")
    st.info("3. That the service account has access to the spreadsheet")
    st.stop()

tab1, tab2, tab3 = st.tabs(["Overview", "Category Spend", "Merchant Analysis"])

with tab1:
    # Summary Stats
    st.header("Summary Statistics")
    total_spent = df['Debit Amount'].sum()
    total_income = df['Credit Amount'].sum()
    st.metric("Total Spent", f"₹{total_spent:,.2f}")
    st.metric("Total Income", f"₹{total_income:,.2f}")
    
    # Time Series Chart
    st.subheader("Balance Over Time")
    df['Balance'] = df['Credit Amount'].cumsum() - df['Debit Amount'].cumsum()
    fig = px.line(df, x='Timestamp', y='Balance', title='Balance Over Time')
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    # Pie chart of spend by category
    st.header("Expense Breakdown by Category")
    exp_df = df[df['Debit Amount'] > 0]
    cat_exp = exp_df.groupby('Category')['Debit Amount'].sum().reset_index()
    fig2 = px.pie(cat_exp, names='Category', values='Debit Amount', title='Spend by Category')
    st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(cat_exp.rename(columns={'Debit Amount': 'Total Spend (₹)'}))

with tab3:
    # Merchant/Business breakdown
    st.header("Spending by Business/Person")
    merch_exp = exp_df.groupby('Business/Person Name')['Debit Amount'].sum().reset_index()
    fig3 = px.bar(merch_exp, x='Business/Person Name', y='Debit Amount', title='Spend by Merchant', text_auto=True)
    st.plotly_chart(fig3, use_container_width=True)
    st.dataframe(merch_exp.rename(columns={'Debit Amount': 'Total Spend (₹)'}))

# --- Optional Filters ---
st.sidebar.header("Filter Transactions")
selected_category = st.sidebar.multiselect("Category", df['Category'].unique())
selected_merchant = st.sidebar.multiselect("Business/Person Name", df['Business/Person Name'].unique())

filtered_df = df.copy()
if selected_category:
    filtered_df = filtered_df[filtered_df['Category'].isin(selected_category)]
if selected_merchant:
    filtered_df = filtered_df[filtered_df['Business/Person Name'].isin(selected_merchant)]

st.sidebar.subheader("Filtered Transactions")
st.sidebar.dataframe(filtered_df)

# --- Data Table ---
st.subheader("All Transactions")
st.dataframe(df)
