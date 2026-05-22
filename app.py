import os
from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd
import requests
import streamlit as st


# =========================================================
# CONFIG
# =========================================================

st.set_page_config(
    page_title="Israel-Gaza War Dashboard",
    page_icon="🇵🇸",
    layout="wide"
)

DATA_URL = "https://data.techforpalestine.org/api/v2/casualties_daily.json"
CSV_FILE = "War.csv"


# =========================================================
# DATA LOADING
# =========================================================

@st.cache_data(ttl=3600)
def load_data():
    """
    Load data from API.
    If API fails, fallback to local CSV.
    """

    try:
        response = requests.get(DATA_URL, timeout=15)
        response.raise_for_status()

        json_data = response.json()

        if not isinstance(json_data, list):
            st.error("Unexpected API response format.")
            return None

        df = pd.json_normalize(json_data)

        df.to_csv(CSV_FILE, index=False, encoding="utf-8")

        return df

    except Exception as e:

        st.warning(f"API unavailable. Using local data.\n\n{e}")

        if os.path.exists(CSV_FILE):
            try:
                return pd.read_csv(CSV_FILE)
            except Exception as csv_error:
                st.error(f"Failed reading local CSV:\n{csv_error}")
                return None

        st.error("No local backup file found.")
        return None


# =========================================================
# DATA PROCESSING
# =========================================================

def process_data(df):
    """
    Clean and process dataset.
    """

    df = df.copy()

    df.fillna(0, inplace=True)
    df.drop_duplicates(inplace=True)

    # Convert date column
    if "report_date" in df.columns:
        df["report_date"] = pd.to_datetime(df["report_date"])

    # Generate daily columns from cumulative columns
    cumulative_columns = [col for col in df.columns if col.endswith("_cum")]

    for col in cumulative_columns:

        daily_col = col.replace("_cum", "_daily")

        try:
            df[daily_col] = df[col].diff().fillna(df[col])

            df[daily_col] = df[daily_col].apply(
                lambda x: x if x >= 0 else 0
            )

        except Exception:
            pass

    # Men killed calculation
    required_cols = [
        "ext_killed_daily",
        "ext_killed_women_daily",
        "ext_killed_children_daily"
    ]

    if all(col in df.columns for col in required_cols):

        df["men_killed_daily"] = (
            df["ext_killed_daily"]
            - df["ext_killed_women_daily"]
            - df["ext_killed_children_daily"]
        )

        df["men_killed_daily"] = df["men_killed_daily"].apply(
            lambda x: x if x >= 0 else 0
        )

    return df


# =========================================================
# SAFE COLUMN ACCESS
# =========================================================

def safe_sum(df, column):
    if column in df.columns:
        return df[column].sum()
    return 0


def safe_mean(df, column):
    if column in df.columns:
        return df[column].mean()
    return 0


def safe_group(df, column):
    if column in df.columns:
        return df.groupby("report_date")[column].sum()
    return pd.Series(dtype=float)


# =========================================================
# MAIN APP
# =========================================================

data = load_data()

if data is None:
    st.stop()

data = process_data(data)


# =========================================================
# HEADER
# =========================================================

st.title("🇵🇸 Israel-Gaza War Dashboard")

st.subheader("Live Casualties & Humanitarian Statistics")

st.markdown("---")


# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title("Dashboard Information")

war_days = len(data)

st.sidebar.metric("War Days", war_days)

if "report_date" in data.columns:

    latest_date = data["report_date"].max()

    today = datetime.now()

    days_ago = (today - latest_date).days

    st.sidebar.write(
        f"Last Update: {latest_date.strftime('%Y-%m-%d')}"
    )

    st.sidebar.write(
        f"Data Delay: {days_ago} day(s)"
    )


# =========================================================
# CASUALTIES SUMMARY
# =========================================================

summary_data = {
    "Total Killed":
        safe_sum(data, "ext_killed_daily"),

    "Total Injured":
        safe_sum(data, "ext_injured_daily"),

    "Children Killed":
        safe_sum(data, "ext_killed_children_daily"),

    "Women Killed":
        safe_sum(data, "ext_killed_women_daily"),

    "Men Killed":
        safe_sum(data, "men_killed_daily"),

    "Medical Personnel Killed":
        safe_sum(data, "ext_med_killed_daily"),

    "Journalists Killed":
        safe_sum(data, "ext_press_killed_daily"),
}

summary_df = pd.DataFrame(
    summary_data.items(),
    columns=["Category", "Count"]
)

st.sidebar.subheader("Casualties Summary")
st.sidebar.dataframe(summary_df, use_container_width=True)


# =========================================================
# LAST 10 DAYS
# =========================================================

last10 = pd.DataFrame({
    "Metric": [
        "Killed",
        "Injured",
        "Children Killed",
        "Women Killed",
        "Men Killed"
    ],
    "Value": [
        data["ext_killed_daily"].tail(10).sum()
        if "ext_killed_daily" in data.columns else 0,

        data["ext_injured_daily"].tail(10).sum()
        if "ext_injured_daily" in data.columns else 0,

        data["ext_killed_children_daily"].tail(10).sum()
        if "ext_killed_children_daily" in data.columns else 0,

        data["ext_killed_women_daily"].tail(10).sum()
        if "ext_killed_women_daily" in data.columns else 0,

        data["men_killed_daily"].tail(10).sum()
        if "men_killed_daily" in data.columns else 0,
    ]
})

st.sidebar.subheader("Last 10 Days")
st.sidebar.dataframe(last10, use_container_width=True)


# =========================================================
# RAW DATA
# =========================================================

st.header("Dataset Preview")

tab1, tab2 = st.tabs(["First 5 Days", "Last 5 Days"])

with tab1:
    st.dataframe(data.head(), use_container_width=True)

with tab2:
    st.dataframe(data.tail(), use_container_width=True)


# =========================================================
# LINE CHARTS
# =========================================================

st.header("Daily Statistics")

col1, col2 = st.columns(2)

with col1:

    killed_series = safe_group(data, "ext_killed_daily")

    st.subheader("Daily Killed")

    if not killed_series.empty:
        st.line_chart(killed_series)
    else:
        st.warning("Killed data unavailable.")


with col2:

    injured_series = safe_group(data, "ext_injured_daily")

    st.subheader("Daily Injured")

    if not injured_series.empty:
        st.line_chart(injured_series)
    else:
        st.warning("Injured data unavailable.")


# =========================================================
# MASSACRES + CUMULATIVE
# =========================================================

col1, col2 = st.columns(2)

with col1:

    massacre_series = safe_group(data, "massacres_daily")

    st.subheader("Daily Massacres")

    if not massacre_series.empty:
        st.line_chart(massacre_series)
    else:
        st.warning("Massacres data unavailable.")


with col2:

    if "killed_cum" in data.columns:

        st.subheader("Cumulative Killed")

        st.line_chart(data["killed_cum"])

    else:
        st.warning("Cumulative data unavailable.")


# =========================================================
# PIE CHART
# =========================================================

st.header("Casualties Distribution")

children_total = safe_sum(data, "ext_killed_children_daily")
women_total = safe_sum(data, "ext_killed_women_daily")
men_total = safe_sum(data, "men_killed_daily")

fig1, ax1 = plt.subplots(figsize=(8, 8))

ax1.pie(
    [children_total, women_total, men_total],
    labels=[
        "Children",
        "Women",
        "Men"
    ],
    autopct="%1.1f%%",
    startangle=90
)

st.pyplot(fig1)


# =========================================================
# BAR CHART
# =========================================================

st.header("Casualty Categories")

bar_data = {
    "Women": women_total,
    "Children": children_total,
    "Men": men_total,
    "Medical Staff": safe_sum(data, "ext_med_killed_daily"),
    "Journalists": safe_sum(data, "ext_press_killed_daily")
}

fig2, ax2 = plt.subplots(figsize=(8, 5))

ax2.bar(bar_data.keys(), bar_data.values())

ax2.set_ylabel("Count")

plt.xticks(rotation=15)

st.pyplot(fig2)


# =========================================================
# PERCENTAGES
# =========================================================

st.header("Percentage Analysis")

total_killed = safe_sum(data, "ext_killed_daily")

if total_killed > 0:

    st.markdown(
        f"### Women: {(women_total / total_killed) * 100:.2f}%"
    )

    st.markdown(
        f"### Children: {(children_total / total_killed) * 100:.2f}%"
    )

    st.markdown(
        f"### Men: {(men_total / total_killed) * 100:.2f}%"
    )


# =========================================================
# AVERAGES
# =========================================================

st.header("Daily Average Statistics")

avg_people = safe_mean(data, "ext_killed_daily")
avg_women = safe_mean(data, "ext_killed_women_daily")
avg_children = safe_mean(data, "ext_killed_children_daily")
avg_men = safe_mean(data, "men_killed_daily")

st.markdown(f"### People Killed Daily: {avg_people:.2f}")
st.markdown(f"### Women Killed Daily: {avg_women:.2f}")
st.markdown(f"### Children Killed Daily: {avg_children:.2f}")
st.markdown(f"### Men Killed Daily: {avg_men:.2f}")


# =========================================================
# FOOTER
# =========================================================

st.markdown("---")

st.caption("Dashboard Version 2.0")
