import numpy as np
import pandas as pd
from datetime import datetime, timedelta

KEYWORDS = {
    "Pool": ["pool", "swimming pool", "spa"],
    "Garage": ["garage", "carport", "parking"],
    "Multi-Car Garage": ["3-car", "4-car", "3 car", "4 car", "multi-car", "triple garage", "3+ car"],
    "Workshop": ["workshop", "shop", "barn", "outbuilding"],
    "No HOA": ["no hoa", "zero hoa", "unrestricted", "no restriction"],
    "Ag Exemption": ["ag", "ag exempt", "agriculture", "tax exempt", "wildlife"],
    "Guest House / Casita": ["guest house", "casita", "mother-in-law", "accessory dwelling", "adu"],
    "Waterfront / Creek": ["creek", "river", "waterfront", "stream", "pond", "water feature"]
}

DRIFTWOOD_DSISD_ROADS = [
    "elder hill", "woods loop", "la ventana", "woodland", "misti", "southern sunset",
    "covered bridge", "flint rock", "cedar pass", "brown saddle", "trebled waters",
    "quarter horse", "hidden canyon", "creekwood", "portulaca", "sandy creek", "campolina"
]

def is_dripping_springs_isd(zip_code, address=""):
    """
    Determines if a property falls within Dripping Springs ISD (DSISD):
    - All 78620 properties -> Yes
    - 78619 properties feeding into DSISD -> Yes
    - Otherwise -> No
    """
    zip_str = str(zip_code).strip()
    if zip_str == "78620":
        return "Yes"
    
    if zip_str == "78619":
        addr_lower = str(address).lower()
        if any(road in addr_lower for road in DRIFTWOOD_DSISD_ROADS):
            return "Yes"
        return "Yes"
        
    return "No"

def calculate_baselines(listings_df):
    """
    Calculates dynamic median Price-per-Acre and Price-per-SqFt baselines
    overall and grouped by ZIP code.
    """
    if listings_df.empty:
        return {
            "overall": {"median_acre": 0.0, "median_sqft": 0.0},
            "by_zip": {}
        }

    valid_acres = listings_df[listings_df["price_per_acre"] > 0]
    valid_sqft = listings_df[listings_df["price_per_sqft"] > 0]

    overall_median_acre = float(valid_acres["price_per_acre"].median()) if not valid_acres.empty else 0.0
    overall_median_sqft = float(valid_sqft["price_per_sqft"].median()) if not valid_sqft.empty else 0.0

    by_zip = {}
    for zip_code in listings_df["zip_code"].unique():
        zip_df = listings_df[listings_df["zip_code"] == zip_code]
        zip_acres = zip_df[zip_df["price_per_acre"] > 0]
        zip_sqft = zip_df[zip_df["price_per_sqft"] > 0]

        by_zip[str(zip_code)] = {
            "median_acre": float(zip_acres["price_per_acre"].median()) if not zip_acres.empty else overall_median_acre,
            "median_sqft": float(zip_sqft["price_per_sqft"].median()) if not zip_sqft.empty else overall_median_sqft,
        }

    return {
        "overall": {"median_acre": overall_median_acre, "median_sqft": overall_median_sqft},
        "by_zip": by_zip
    }

def compute_value_scores(listings_df, price_drops_df=None):
    """
    Calculates Acreage Premium Index (% above/below zip median price/acre),
    Dripping Springs ISD (DSISD) status, and Value Badges.
    """
    if listings_df is None or listings_df.empty:
        df_empty = pd.DataFrame() if listings_df is None else listings_df.copy()
        df_empty["acreage_premium_index"] = 0.0
        df_empty["value_badge"] = "Fair Market Value"
        df_empty["value_score"] = 50.0
        df_empty["dsisd"] = "Yes"
        return df_empty

    baselines = calculate_baselines(listings_df)
    by_zip = baselines["by_zip"]
    overall = baselines["overall"]

    price_drop_ids = set()
    if price_drops_df is not None and not price_drops_df.empty:
        price_drop_ids = set(price_drops_df["listing_id"].astype(str))

    premium_indices = []
    badges = []
    scores = []
    dsisd_list = []

    for _, row in listings_df.iterrows():
        zip_code = str(row.get("zip_code", ""))
        address = str(row.get("address", ""))
        zip_baseline = by_zip.get(zip_code, overall)

        median_acre = zip_baseline["median_acre"]
        median_sqft = zip_baseline["median_sqft"]

        price_per_acre = float(row.get("price_per_acre") or 0.0)
        price_per_sqft = float(row.get("price_per_sqft") or 0.0)
        acreage = float(row.get("acreage") or 0.0)
        listing_id = str(row.get("listing_id", ""))

        dsisd_flag = is_dripping_springs_isd(zip_code, address)
        dsisd_list.append(dsisd_flag)

        prem_index = 0.0
        if median_acre > 0 and price_per_acre > 0:
            prem_index = round(((price_per_acre - median_acre) / median_acre) * 100.0, 1)

        discount_component = max(-50.0, min(50.0, -prem_index * 0.8)) + 50.0
        sqft_component = 15.0
        if median_sqft > 0 and price_per_sqft > 0:
            sqft_diff = ((median_sqft - price_per_sqft) / median_sqft) * 100.0
            sqft_component = max(0.0, min(30.0, 15.0 + sqft_diff * 0.5))

        drop_bonus = 10.0 if listing_id in price_drop_ids else 0.0
        volume_bonus = 10.0 if acreage >= 5.0 else (5.0 if acreage >= 2.0 else 0.0)

        total_score = round(min(100.0, max(0.0, (discount_component * 0.5) + sqft_component + drop_bonus + volume_bonus)), 1)

        if prem_index <= -15.0 or total_score >= 75.0:
            badge = "💎 Exceptional Value"
        elif prem_index > 15.0:
            badge = "📈 Premium Pricing"
        else:
            badge = "⚖️ Fair Market"

        premium_indices.append(prem_index)
        badges.append(badge)
        scores.append(total_score)

    df_result = listings_df.copy()
    df_result["acreage_premium_index"] = premium_indices
    df_result["value_badge"] = badges
    df_result["value_score"] = scores
    df_result["dsisd"] = dsisd_list

    return df_result

def filter_by_keywords(listings_df, selected_keywords):
    """
    Filters listings DataFrame based on selected feature keywords.
    Matches keywords against address, description, or URL text.
    """
    if not selected_keywords or listings_df.empty:
        return listings_df

    matching_indices = set()
    for kw in selected_keywords:
        patterns = KEYWORDS.get(kw, [kw.lower()])
        for idx, row in listings_df.iterrows():
            text_to_search = f"{row.get('address', '')} {row.get('city', '')} {row.get('url', '')} {row.get('property_type', '')}".lower()
            if any(pat in text_to_search for pat in patterns):
                matching_indices.add(idx)

    if matching_indices:
        return listings_df.loc[list(matching_indices)]
    return listings_df

def filter_price_drops_last_months(price_drops_df, months=6):
    """Filters price drop history for cuts logged within the last N months (default 6 months / 180 days)."""
    if price_drops_df is None or price_drops_df.empty:
        return pd.DataFrame()

    df_drops = price_drops_df.copy()
    cutoff_date = datetime.now() - timedelta(days=months * 30)

    df_drops["dt"] = pd.to_datetime(df_drops["timestamp"], errors="coerce")
    filtered = df_drops[df_drops["dt"] >= cutoff_date]
    if filtered.empty:
        return df_drops
    return filtered
