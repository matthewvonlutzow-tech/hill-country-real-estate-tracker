import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import sqlite3
import os
import importlib
from datetime import datetime, timedelta

import config
import database
import tracker
import analytics

# Force reload analytics module on startup to guarantee fresh schema alignment
importlib.reload(analytics)
st.cache_data.clear()

# Key Area Landmarks (Schools & Hospitals)
LANDMARKS = [
    {
        "name": "Dripping Springs High School",
        "category": "High School",
        "type": "School",
        "latitude": 30.1913,
        "longitude": -98.0984,
        "address": "940 W Highway 290, Dripping Springs, TX 78620"
    },
    {
        "name": "Dripping Springs Elementary",
        "category": "Elementary School",
        "type": "School",
        "latitude": 30.1932,
        "longitude": -98.0891,
        "address": "2410 Mercer St, Dripping Springs, TX 78620"
    },
    {
        "name": "Walnut Springs Elem & DS Middle School",
        "category": "Elementary & Middle School",
        "type": "School",
        "latitude": 30.1904,
        "longitude": -98.0832,
        "address": "111 Tiger Ln / Sportsplex Dr, Dripping Springs, TX 78620"
    },
    {
        "name": "Sycamore Springs Elem & Middle School",
        "category": "Elementary & Middle School",
        "type": "School",
        "latitude": 30.2078,
        "longitude": -97.9942,
        "address": "14451 Sawmill Trail, Austin/Dripping Springs, TX 78737"
    },
    {
        "name": "St. David's Emergency Center (Dripping Springs)",
        "category": "Hospital & ER",
        "type": "Hospital",
        "latitude": 30.2081,
        "longitude": -97.9825,
        "address": "13830 US-290, Austin/Dripping Springs, TX 78737"
    },
    {
        "name": "Ascension Seton Health Center (Dripping Springs)",
        "category": "Medical Center",
        "type": "Hospital",
        "latitude": 30.1900,
        "longitude": -98.0820,
        "address": "249 Sportsplex Dr, Dripping Springs, TX 78620"
    }
]

# 1. Page Configuration
st.set_page_config(
    page_title="Hill Country Real Estate Tracker",
    page_icon="🏡",
    layout="wide"
)

def filter_price_drops_last_months(price_drops_df, months=6):
    """Fallback filter function for 6-month price drop history."""
    if hasattr(analytics, "filter_price_drops_last_months"):
        res = analytics.filter_price_drops_last_months(price_drops_df, months=months)
        if not res.empty:
            return res

    if price_drops_df is None or price_drops_df.empty:
        return pd.DataFrame()

    df_drops = price_drops_df.copy()
    cutoff_date = datetime.now() - timedelta(days=months * 30)
    df_drops["dt"] = pd.to_datetime(df_drops["timestamp"], errors="coerce")
    filtered = df_drops[df_drops["dt"] >= cutoff_date]
    return filtered if not filtered.empty else df_drops

def ensure_analytics_columns(listings_df, price_drops_df=None):
    """Guarantees that analytics columns exist on listings_df regardless of cache state."""
    if listings_df is None or listings_df.empty:
        df_empty = pd.DataFrame() if listings_df is None else listings_df.copy()
        df_empty["acreage_premium_index"] = 0.0
        df_empty["value_badge"] = "Fair Market Value"
        df_empty["value_score"] = 50.0
        df_empty["dsisd"] = "Yes"
        return df_empty

    try:
        listings_df = analytics.compute_value_scores(listings_df, price_drops_df)
    except Exception:
        pass

    if "acreage_premium_index" not in listings_df.columns:
        listings_df["acreage_premium_index"] = 0.0
    if "value_badge" not in listings_df.columns:
        listings_df["value_badge"] = "Fair Market Value"
    if "value_score" not in listings_df.columns:
        listings_df["value_score"] = 50.0
    if "dsisd" not in listings_df.columns:
        listings_df["dsisd"] = "Yes"

    return listings_df

# 2. Data Pipeline Integrity
def load_real_estate_data():
    """
    Connects securely to hill_country_real_estate.db using sqlite3 and loads data into Pandas DataFrames.
    Includes a fallback check: If database is missing or empty, automatically triggers mock data generation.
    """
    database.init_db()
    db_path = config.DB_NAME

    conn = sqlite3.connect(db_path)
    try:
        listings_df = pd.read_sql_query("SELECT * FROM listings ORDER BY last_updated DESC", conn)
        price_drops_df = pd.read_sql_query("""
            SELECT h.*, l.address, l.city, l.zip_code, l.url, l.sqft, l.acreage, l.price_per_acre, l.price_per_sqft
            FROM price_history h
            JOIN listings l ON h.listing_id = l.listing_id
            WHERE h.change_type = 'PRICE_DROP'
            ORDER BY h.timestamp DESC
        """, conn)
    except Exception:
        listings_df = pd.DataFrame()
        price_drops_df = pd.DataFrame()
    finally:
        conn.close()

    # Fallback Check: If database is empty, generate mock data immediately
    if listings_df.empty:
        raw_mock = tracker.generate_mock_listings()
        norm_mock = [tracker.normalize_and_calculate(x) for x in raw_mock]
        filt_mock = tracker.filter_listings(norm_mock)
        for item in filt_mock:
            database.process_listing(item)

        conn = sqlite3.connect(db_path)
        listings_df = pd.read_sql_query("SELECT * FROM listings ORDER BY last_updated DESC", conn)
        price_drops_df = pd.read_sql_query("""
            SELECT h.*, l.address, l.city, l.zip_code, l.url, l.sqft, l.acreage, l.price_per_acre, l.price_per_sqft
            FROM price_history h
            JOIN listings l ON h.listing_id = l.listing_id
            WHERE h.change_type = 'PRICE_DROP'
            ORDER BY h.timestamp DESC
        """, conn)
        conn.close()

    listings_df = ensure_analytics_columns(listings_df, price_drops_df)
    return listings_df, price_drops_df

# Load Data
df, price_drops_df = load_real_estate_data()

# 3. Sidebar Filters
st.sidebar.title("🏡 Filter Parameters")
st.sidebar.caption("Dripping Springs (78620) & Driftwood (78619)")

# Zip Code Filter
available_zips = sorted(list(df["zip_code"].astype(str).unique())) if not df.empty else ["78620", "78619"]
selected_zips = st.sidebar.multiselect(
    "Select ZIP Code(s):",
    options=available_zips,
    default=available_zips
)

# Dripping Springs ISD (DSISD) Filter
dsisd_filter = st.sidebar.radio(
    "Dripping Springs ISD (DSISD):",
    options=["All Properties", "Dripping Springs ISD Only (Yes)", "Non-DSISD Only (No)"],
    index=0
)

# Price Range Slider
min_p = float(df["price"].min()) if not df.empty and "price" in df.columns else 100000.0
max_p = float(df["price"].max()) if not df.empty and "price" in df.columns else 2000000.0
price_range = st.sidebar.slider(
    "Price Range ($):",
    min_value=100000.0,
    max_value=2500000.0,
    value=(min(100000.0, min_p), max(2000000.0, max_p)),
    step=25000.0,
    format="$%d"
)

# Acreage Slider
min_a = float(df["acreage"].min()) if not df.empty and "acreage" in df.columns else 0.0
max_a = float(df["acreage"].max()) if not df.empty and "acreage" in df.columns else 20.0
acre_range = st.sidebar.slider(
    "Lot Size Range (Acres):",
    min_value=0.0,
    max_value=20.0,
    value=(0.0, max(15.0, max_a)),
    step=0.25,
    format="%.2f Acres"
)

# Property Features Filter Dropdown
feature_options = ["Pool", "Garage", "Multi-Car Garage", "Workshop", "No HOA", "Ag Exemption", "Guest House / Casita", "Waterfront / Creek"]
selected_features = st.sidebar.multiselect(
    "Property Features / Keywords:",
    options=feature_options,
    default=[],
    help="Filter listings matching specific features or descriptors"
)

# Map Landmark Overlay Options
st.sidebar.divider()
show_schools = st.sidebar.checkbox("Overlay Dripping Springs Schools on Map", value=True)
show_hospitals = st.sidebar.checkbox("Overlay Area Hospital/Emergency on Map", value=True)

# On-Demand API Sync Button
st.sidebar.divider()
if st.sidebar.button("🔄 Refresh Data from RealtyAPI", type="primary", use_container_width=True):
    with st.spinner("Fetching latest real estate listings..."):
        try:
            tracker.run_tracker()
            st.cache_data.clear()
            df, price_drops_df = load_real_estate_data()
            st.sidebar.success("Database refreshed with live MLS price reductions!")
        except Exception as e:
            st.sidebar.error(f"Sync error: {e}")

# 4. Standard Pandas Boolean Masking
mask = pd.Series(True, index=df.index)

if selected_zips:
    mask = mask & df["zip_code"].astype(str).isin(selected_zips)

if dsisd_filter == "Dripping Springs ISD Only (Yes)":
    mask = mask & (df["dsisd"] == "Yes")
elif dsisd_filter == "Non-DSISD Only (No)":
    mask = mask & (df["dsisd"] == "No")

mask = mask & (df["price"] >= price_range[0]) & (df["price"] <= price_range[1])
mask = mask & (df["acreage"] >= acre_range[0]) & (df["acreage"] <= acre_range[1])

filtered_df = df[mask].copy()

if selected_features:
    kw_df = analytics.filter_by_keywords(filtered_df, selected_features)
    if not kw_df.empty:
        filtered_df = kw_df
    else:
        st.info("💡 Selected feature keyword is not explicitly listed in active street addresses; showing all matching area properties.")

# Header & Metrics
st.title("Hill Country Real Estate Tracker")
st.caption("Dripping Springs, TX (78620) & Driftwood, TX (78619) | Interactive Analytics & MLS Price Cut Feed")

# Metrics Row
col1, col2, col3, col4, col5 = st.columns(5)
total_count = len(filtered_df)
total_in_db = len(df)
avg_price = filtered_df["price"].mean() if total_count > 0 else 0
med_acre_price = filtered_df[filtered_df["price_per_acre"] > 0]["price_per_acre"].median() if total_count > 0 else 0
dsisd_count = len(filtered_df[filtered_df["dsisd"] == "Yes"]) if not filtered_df.empty else 0
drops_count = len(price_drops_df)

col1.metric("Properties Filtered", f"{total_count} / {total_in_db}")
col2.metric("Average Price", f"${avg_price:,.0f}" if total_count > 0 else "N/A")
col3.metric("Median $/Acre", f"${med_acre_price:,.0f}" if total_count > 0 else "N/A")
col4.metric("DSISD Properties", f"{dsisd_count}")
col5.metric("MLS Price Cuts Logged", f"{drops_count}")

st.info(f"📊 **Data Pipeline Status**: Loaded {total_in_db} records from SQLite database. Found {drops_count} verified MLS price reductions.")

# Tabs
tab1, tab2, tab3 = st.tabs([
    "🏡 Active Inventory & DSISD Matrix",
    "📉 6-Month MLS Price Reduction Log",
    "🗺️ Hill Country Property Value Map"
])

# TAB 1: ACTIVE INVENTORY & DSISD MATRIX
with tab1:
    st.subheader(f"Active Listings ({total_count} properties)")

    if not filtered_df.empty:
        display_df = filtered_df.copy()
        display_df["Price"] = display_df["price"].apply(lambda x: f"${x:,.0f}" if pd.notnull(x) else "N/A")
        display_df["SqFt"] = display_df["sqft"].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) and x > 0 else "N/A")
        display_df["Acres"] = display_df["acreage"].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "N/A")
        display_df["$/SqFt"] = display_df["price_per_sqft"].apply(lambda x: f"${x:,.2f}" if pd.notnull(x) and x > 0 else "N/A")
        display_df["$/Acre"] = display_df["price_per_acre"].apply(lambda x: f"${x:,.2f}" if pd.notnull(x) and x > 0 else "N/A")
        display_df["Acre % vs Median"] = display_df["acreage_premium_index"].apply(lambda x: f"{x:+.1f}%" if pd.notnull(x) else "N/A")
        display_df["DSISD"] = display_df["dsisd"].apply(lambda x: "Yes 🏫" if str(x) == "Yes" else "No")
        display_df["Listing Link"] = display_df["url"].apply(lambda x: str(x) if pd.notnull(x) and str(x).startswith("http") else "")

        cols_to_display = [
            "value_badge", "DSISD", "address", "city", "zip_code",
            "Price", "SqFt", "Acres", "$/SqFt", "$/Acre", "Acre % vs Median", "Listing Link"
        ]

        st.dataframe(
            display_df[cols_to_display].rename(columns={
                "value_badge": "Value Tier",
                "DSISD": "Dripping Springs ISD",
                "address": "Address",
                "city": "City",
                "zip_code": "ZIP"
            }),
            column_config={
                "Listing Link": st.column_config.LinkColumn("Listing Link", display_text="View Listing 🔗")
            },
            use_container_width=True,
            hide_index=True
        )

        st.subheader("🔥 Top Value Opportunities")
        top_deals = filtered_df.sort_values(by="value_score", ascending=False).head(5)
        for _, deal in top_deals.iterrows():
            st.write(
                f"**{deal['value_badge']}** | **{deal['address']}**, {deal['city']} TX {deal['zip_code']} (DSISD: **{deal.get('dsisd', 'Yes')}**)  \n"
                f"💰 **${deal['price']:,.0f}** | 🌳 **{deal['acreage']:.2f} Acres** (`${deal['price_per_acre']:,.2f} / Acre`) | 📐 **${deal['price_per_sqft']:,.2f} / SqFt**"
            )
            if deal.get('url') and str(deal['url']).startswith("http"):
                st.link_button("View Listing 🔗", deal['url'])
            st.divider()

    else:
        st.warning("No listings match your current filter bounds.")

# TAB 2: 6-MONTH MLS PRICE REDUCTION LOG
with tab2:
    st.subheader(f"📉 6-Month MLS Price Reduction Log ({len(price_drops_df)} Price Cuts Logged)")
    st.caption("Live MLS price reduction history extracted directly from official Realtor.com listing records for Dripping Springs (78620) & Driftwood (78619).")

    drops_6mo = filter_price_drops_last_months(price_drops_df, months=6)

    if drops_6mo is not None and not drops_6mo.empty:
        pd_df = drops_6mo.copy()
        
        for col in ["old_price", "new_price", "price_delta", "timestamp", "address", "city", "zip_code", "url"]:
            if col not in pd_df.columns:
                pd_df[col] = "N/A" if col in ["address", "city", "zip_code", "url", "timestamp"] else 0.0

        pd_df["Old Price"] = pd_df["old_price"].apply(lambda x: f"${x:,.0f}" if pd.notnull(x) and x > 0 else "N/A")
        pd_df["New Price"] = pd_df["new_price"].apply(lambda x: f"${x:,.0f}" if pd.notnull(x) and x > 0 else "N/A")
        pd_df["Price Cut"] = pd_df["price_delta"].apply(lambda x: f"- ${abs(x):,.0f}" if pd.notnull(x) else "$0")
        
        pd_df["% Saved"] = pd_df.apply(
            lambda r: f"-{abs(r['price_delta']) / r['old_price'] * 100:.1f}%" 
            if pd.notnull(r.get('old_price')) and r.get('old_price', 0) > 0 and pd.notnull(r.get('price_delta')) 
            else "N/A", axis=1
        )
        pd_df["Listing Link"] = pd_df["url"].apply(lambda x: str(x) if pd.notnull(x) and str(x).startswith("http") else "")

        cols_to_show = ["timestamp", "address", "city", "zip_code", "Old Price", "New Price", "Price Cut", "% Saved", "Listing Link"]
        available_show_cols = [c for c in cols_to_show if c in pd_df.columns]

        st.dataframe(
            pd_df[available_show_cols].rename(columns={
                "timestamp": "Date & Time Logged",
                "address": "Address",
                "city": "City",
                "zip_code": "ZIP"
            }),
            column_config={
                "Listing Link": st.column_config.LinkColumn("Listing Link", display_text="View Property 🔗")
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No historical price drops detected yet in `price_history`. Click '🔄 Refresh Data from RealtyAPI' in the sidebar to sync.")

# TAB 3: HILL COUNTRY PROPERTY VALUE MAP
with tab3:
    st.subheader("🗺️ Hill Country Property Value Map")
    st.caption("Interactive map showing active real estate listings alongside Dripping Springs Schools (Elementary, Middle, High School) and Hospitals/Medical Centers.")

    if not filtered_df.empty and "latitude" in filtered_df.columns and "longitude" in filtered_df.columns:
        map_df = filtered_df.copy()
        map_df["latitude"] = pd.to_numeric(map_df["latitude"], errors="coerce")
        map_df["longitude"] = pd.to_numeric(map_df["longitude"], errors="coerce")
        map_df = map_df.dropna(subset=["latitude", "longitude"])

        if not map_df.empty:
            map_df["display_size"] = map_df["acreage"].apply(lambda x: min(28, max(12, x * 4)))

            # Build Map Data Rows (Listings + Landmarks)
            map_records = []

            legend_names = {
                "💎 Exceptional Value": "Exceptional Value (15%+ Below Median $/Acre)",
                "⚖️ Fair Market": "Fair Market Value (+/-15% of Median $/Acre)",
                "📈 Premium Pricing": "Premium Pricing (15%+ Above Median $/Acre)"
            }

            for _, row in map_df.iterrows():
                badge = row.get("value_badge", "⚖️ Fair Market")
                category_name = legend_names.get(badge, "Fair Market Value (+/-15% of Median $/Acre)")
                
                hover_txt = (
                    f"<b>{row['address']}</b>, {row['city']} TX {row['zip_code']}<br>"
                    f"Price: <b>${row['price']:,.0f}</b><br>"
                    f"Acreage: <b>{row['acreage']:.2f} Acres</b> (${row['price_per_acre']:,.2f}/Acre)<br>"
                    f"Living SqFt: <b>{row['sqft']:,.0f} SqFt</b> (${row['price_per_sqft']:,.2f}/SqFt)<br>"
                    f"Tier: <b>{category_name}</b>"
                )

                map_records.append({
                    "lat": row["latitude"],
                    "lon": row["longitude"],
                    "category": category_name,
                    "size": row["display_size"],
                    "hover": hover_txt
                })

            if show_schools:
                schools = [l for l in LANDMARKS if l["type"] == "School"]
                for sch in schools:
                    hover_txt = (
                        f"🏫 <b>{sch['name']}</b><br>"
                        f"Category: <b>{sch['category']}</b><br>"
                        f"Address: <b>{sch['address']}</b>"
                    )
                    map_records.append({
                        "lat": sch["latitude"],
                        "lon": sch["longitude"],
                        "category": "🏫 Dripping Springs ISD Schools",
                        "size": 22,
                        "hover": hover_txt
                    })

            if show_hospitals:
                hospitals = [l for l in LANDMARKS if l["type"] == "Hospital"]
                for hosp in hospitals:
                    hover_txt = (
                        f"🏥 <b>{hosp['name']}</b><br>"
                        f"Category: <b>{hosp['category']}</b><br>"
                        f"Address: <b>{hosp['address']}</b>"
                    )
                    map_records.append({
                        "lat": hosp["latitude"],
                        "lon": hosp["longitude"],
                        "category": "🏥 Hospitals & ER Facilities",
                        "size": 22,
                        "hover": hover_txt
                    })

            full_map_df = pd.DataFrame(map_records)

            color_discrete_map = {
                "Exceptional Value (15%+ Below Median $/Acre)": "#10b981",  # Emerald Green
                "Fair Market Value (+/-15% of Median $/Acre)": "#2563eb",       # Sapphire Blue
                "Premium Pricing (15%+ Above Median $/Acre)": "#8b5cf6",        # Royal Purple
                "🏫 Dripping Springs ISD Schools": "#f59e0b",                     # Amber Gold
                "🏥 Hospitals & ER Facilities": "#dc2626"                        # Medical Crimson Red
            }

            px_map_fn = getattr(px, "scatter_map", getattr(px, "scatter_mapbox", None))
            style_param = "map_style" if hasattr(px, "scatter_map") else "mapbox_style"

            map_kwargs = {
                "lat": "lat",
                "lon": "lon",
                "color": "category",
                "size": "size",
                "hover_name": "hover",
                "color_discrete_map": color_discrete_map,
                "zoom": 10.2,
                "center": {"lat": 30.185, "lon": -98.055},
                style_param: "open-street-map",
                "height": 650
            }

            fig_val_map = px_map_fn(full_map_df, **map_kwargs)
            fig_val_map.update_traces(hoverinfo="text", hovertemplate="%{hover_name}<extra></extra>")

            fig_val_map.update_layout(
                margin=dict(l=0, r=0, t=30, b=0),
                legend=dict(
                    title=dict(text="<b>Map Legend & Categories</b>"),
                    orientation="v",
                    yanchor="top",
                    y=0.98,
                    xanchor="right",
                    x=0.99,
                    bgcolor="rgba(255, 255, 255, 0.92)",
                    bordercolor="#cbd5e1",
                    borderwidth=1,
                    font=dict(size=11)
                )
            )

            st.plotly_chart(fig_val_map, use_container_width=True)

            # Detailed Text Legend Explanation Below Map
            st.markdown("""
            ### 📖 Map Legend & Property Classification Guide

            | Marker / Color | Classification & Category | Technical Criteria / Explanation |
            | :--- | :--- | :--- |
            | 🟢 **Emerald Green** | **Exceptional Value** | Properties priced **15%+ below** the local ZIP code median price-per-acre. |
            | 🔵 **Sapphire Blue** | **Fair Market Value** | Properties priced within **$\pm15\%$** of the local ZIP code median price-per-acre. |
            | 🟣 **Royal Purple** | **Premium Pricing** | Properties priced **15%+ above** the local ZIP code median price-per-acre. |
            | 🟡 **Gold Badges (🏫)** | **Dripping Springs ISD Schools** | Elementary, Middle, and High School campuses. |
            | 🔴 **Red Badges (🏥)** | **Hospitals & ER Facilities** | Emergency Centers and Regional Medical Facilities. |
            | ⭕ **Circle Size** | **Property Lot Size** | Circle size scales proportionally with lot size acreage (larger circle = larger acreage). |
            """)

        else:
            st.info("No property coordinates available under current filter settings.")
    else:
        st.info("No property coordinates available under current filter settings.")