import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import plotly.express as px
import json
import time

# --- AUTO-REFRESH: 5 SEC ---
if 'autorefresh_last_run' not in st.session_state:
    st.session_state['autorefresh_last_run'] = time.time()
if time.time() - st.session_state['autorefresh_last_run'] > 5:
    st.session_state['autorefresh_last_run'] = time.time()
    st.experimental_rerun()

# --- Manual Refresh ---
st.title("📊 Financial Tracker Dashboard")
if st.button('🔄 Manual Refresh (Click anytime)'):
    st.session_state['manual_refresh'] = st.session_state.get('manual_refresh', 0) + 1
    st.experimental_rerun()

# --- Google Sheets setup ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/15DvUPuzkUOIw7JxDx69peorkoVfOff58OMTsllszLYM/edit?usp=sharing"
SCOPE = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive'
]

# Read JSON creds via Streamlit secrets manager
creds = json.loads(st.secrets["gcp_service_account"])

def load_data_live():
    """Always get the freshest data from Google Sheets."""
    try:
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
    except Exception as e:
        return None, f"Error loading data: {str(e)}"

df, error = load_data_live()

if df is None:
    st.error(f"❌ {error}")
    st.info("Please check that your Streamlit secrets contains a valid 'gcp_service_account'.")
    st.info("Secrets must match the full Google service account JSON for Sheets access.")
    st.stop()

tab1, tab2, tab3 = st.tabs(["Overview", "Category Spend", "Merchant Analysis"])

with tab1:
    st.header("Summary Statistics")
    total_spent = df['Debit Amount'].sum()
    total_income = df['Credit Amount'].sum()
    st.metric("Total Spent", f"₹{total_spent:,.2f}")
    st.metric("Total Income", f"₹{total_income:,.2f}")
    st.subheader("Balance Over Time")
    df['Balance'] = df['Credit Amount'].cumsum() - df['Debit Amount'].cumsum()
    fig = px.line(df, x='Timestamp', y='Balance', title='Balance Over Time')
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.header("Expense Breakdown by Category")
    exp_df = df[df['Debit Amount'] > 0]
    cat_exp = exp_df.groupby('Category')['Debit Amount'].sum().reset_index()
    fig2 = px.pie(cat_exp, names='Category', values='Debit Amount', title='Spend by Category')
    st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(cat_exp.rename(columns={'Debit Amount': 'Total Spend (₹)'}))

with tab3:
    st.header("Spending by Business/Person")
    merch_exp = exp_df.groupby('Business/Person Name')['Debit Amount'].sum().reset_index()
    fig3 = px.bar(merch_exp, x='Business/Person Name', y='Debit Amount', title='Spend by Merchant', text_auto=True)
    st.plotly_chart(fig3, use_container_width=True)
    st.dataframe(merch_exp.rename(columns={'Debit Amount': 'Total Spend (₹)'}))

# --- Optional Sidebar Filters ---
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
