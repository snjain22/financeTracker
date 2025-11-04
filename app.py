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
creds = json.loads(st.secrets["gcp_service_account"])

def load_data_live():
    try:
        credentials = Credentials.from_service_account_info(creds, scopes=SCOPE)
        client = gspread.authorize(credentials)
        sheet = client.open_by_url(SHEET_URL)
        worksheet = sheet.get_worksheet(0)
        records = worksheet.get_all_records()
        df = pd.DataFrame(records)
        if df.empty:
            return None, "No data found in the spreadsheet"
        if 'Timestamp' in df.columns:
            df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
        if 'Debit Amount' in df.columns:
            df['Debit Amount'] = pd.to_numeric(df['Debit Amount'], errors='coerce').fillna(0)
        if 'Credit Amount' in df.columns:
            df['Credit Amount'] = pd.to_numeric(df['Credit Amount'], errors='coerce').fillna(0)
        df['Month'] = df['Timestamp'].dt.to_period('M').astype(str)
        return df, None
    except Exception as e:
        return None, f"Error loading data: {str(e)}"

df, error = load_data_live()

if df is None:
    st.error(f"❌ {error}")
    st.info("Check your Streamlit secrets for a valid 'gcp_service_account'.")
    st.stop()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Overview", "Month-on-Month Trends", "Budgeting per Category", "Category Spend", "Merchant Analysis"
])

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
    st.header("Month-on-Month Trends")
    month_stats = df.groupby('Month').agg(
        Total_Spent=('Debit Amount', 'sum'),
        Total_Income=('Credit Amount', 'sum')
    ).reset_index()
    fig_mo_spent = px.bar(month_stats, x='Month', y='Total_Spent', title='Month-on-Month Spend',
                          labels={'Total_Spent':'Spend (₹)'}, color='Total_Spent', color_continuous_scale='Reds')
    fig_mo_income = px.bar(month_stats, x='Month', y='Total_Income', title='Month-on-Month Income',
                           labels={'Total_Income':'Income (₹)'}, color='Total_Income', color_continuous_scale='Greens')
    fig_mo_line = px.line(month_stats, x='Month', y=['Total_Spent','Total_Income'],
                          title='Month-on-Month Spend (Red) vs Income (Green)')
    st.plotly_chart(fig_mo_line, use_container_width=True)
    st.plotly_chart(fig_mo_spent, use_container_width=True)
    st.plotly_chart(fig_mo_income, use_container_width=True)
    st.dataframe(month_stats)

with tab3:
    st.header("Budget vs Actual Spend per Category")
    st.info("Set your monthly category budgets below. See how your actuals compare.")
    # User sets budget for each category with sliders
    categories = df['Category'].unique()
    budgets = {}
    for cat in categories:
        budgets[cat] = st.number_input(f"Budget for {cat}", min_value=0, max_value=99999, value=1000)

    # Aggregate actual spend per category, current month only
    curr_month = df['Month'].max()
    cat_spend = df[df['Month']==curr_month].groupby('Category')['Debit Amount'].sum().reset_index()
    cat_spend['Budget'] = cat_spend['Category'].map(budgets)
    cat_spend['Budget'] = cat_spend['Budget'].fillna(0)
    cat_spend['Over_Budget'] = cat_spend['Debit Amount'] > cat_spend['Budget']

    fig_bud = px.bar(cat_spend, x='Category', y='Debit Amount', color='Over_Budget',
                     title=f'Actual vs Budgeted Spend for {curr_month}',
                     labels={'Debit Amount':'Spent','Over_Budget':'Over Budget'})
    fig_bud.add_scatter(x=cat_spend['Category'], y=cat_spend['Budget'], mode='markers+lines',
                        name='Budgeted', marker=dict(color='blue', size=8, symbol='diamond'))

    st.plotly_chart(fig_bud, use_container_width=True)
    st.dataframe(cat_spend)

with tab4:
    st.header("Expense Breakdown by Category")
    exp_df = df[df['Debit Amount'] > 0]
    cat_exp = exp_df.groupby('Category')['Debit Amount'].sum().reset_index()
    fig2 = px.pie(cat_exp, names='Category', values='Debit Amount', title='Spend by Category')
    st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(cat_exp.rename(columns={'Debit Amount': 'Total Spend (₹)'}))

    st.subheader("Monthly Spend by Category")
    monthly_cat = exp_df.groupby(['Month','Category'])['Debit Amount'].sum().reset_index()
    fig4 = px.bar(monthly_cat, x='Month', y='Debit Amount', color='Category',
                  title='Monthly Spend by Category',
                  labels={'Debit Amount':'Spend (₹)'})
    st.plotly_chart(fig4, use_container_width=True)

with tab5:
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
