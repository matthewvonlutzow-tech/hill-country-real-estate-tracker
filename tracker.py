import sys
import time
import argparse
import logging
import requests
import pandas as pd
from tabulate import tabulate

import config
import database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("RealEstateTracker")

def fetch_listings_for_zip(zip_code):
    """
    Queries realtyapi.io endpoint for real estate listings in a specific ZIP code.
    Implements error handling for rate limits (429), unauthorized (401), and timeouts.
    """
    if not config.REALTY_API_KEY:
        logger.warning("No REALTY_API_KEY set. Set environment variable or use --mock mode.")
        return []

    headers = {
        "x-realtyapi-key": config.REALTY_API_KEY,
        "Accept": "application/json",
        "User-Agent": "HillCountryRealEstateTracker/1.0"
    }

    params = {
        "zipCode": zip_code,
        "zip": zip_code,
        "limit": 50
    }

    url = config.REALTY_API_SEARCH_ENDPOINT
    logger.info(f"Querying realtyapi.io for ZIP code {zip_code}...")

    retries = 0
    backoff = config.RETRY_BACKOFF

    while retries <= config.MAX_RETRIES:
        try:
            response = requests.get(url, headers=headers, params=params, timeout=config.DEFAULT_TIMEOUT)

            if response.status_code == 200:
                data = response.json()
                listings = data.get("searchResults", data.get("listings", data.get("data", data if isinstance(data, list) else [])))
                logger.info(f"Successfully retrieved {len(listings)} raw listings for {zip_code}.")
                return listings

            elif response.status_code == 429:
                retries += 1
                logger.warning(f"Rate limit hit (429). Retrying in {backoff} seconds... (Attempt {retries}/{config.MAX_RETRIES})")
                time.sleep(backoff)
                backoff *= 2

            elif response.status_code in (401, 403):
                logger.error(f"Authentication failed (HTTP {response.status_code}). Please verify your REALTY_API_KEY in config.py or .env file.")
                return []

            else:
                logger.error(f"API request failed for ZIP {zip_code} with status {response.status_code}: {response.text}")
                return []

        except requests.exceptions.Timeout:
            logger.error(f"Connection timeout while querying ZIP {zip_code}.")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error while querying ZIP {zip_code}: {e}")
            return []

    logger.error(f"Exhausted retries for ZIP {zip_code} due to rate limiting.")
    return []

def generate_mock_listings():
    """
    Generates realistic synthetic data for Dripping Springs (78620) and Driftwood (78619)
    including latitude and longitude coordinates for map visualization.
    """
    return [
        {
            "listing_id": "DS-78620-001",
            "address": "14200 Fitzhugh Rd",
            "city": "Dripping Springs",
            "zip_code": "78620",
            "price": 1450000.0,
            "sqft": 3600.0,
            "acreage": 2.50,
            "status": "Active",
            "url": "https://www.realtor.com/realestateandhomes-detail/14200-Fitzhugh-Rd_Dripping-Springs_TX_78620",
            "latitude": 30.2245,
            "longitude": -98.0531,
            "price_reduced_amount": 50000.0,
            "price_reduced_date": "2026-08-15T10:00:00.000Z"
        },
        {
            "listing_id": "DS-78620-002",
            "address": "850 Bell Springs Rd",
            "city": "Dripping Springs",
            "zip_code": "78620",
            "price": 1250000.0,
            "sqft": 2900.0,
            "acreage": 1.15,
            "status": "Active",
            "url": "https://www.realtor.com/realestateandhomes-detail/850-Bell-Springs-Rd_Dripping-Springs_TX_78620",
            "latitude": 30.2012,
            "longitude": -98.1145,
            "price_reduced_amount": 25000.0,
            "price_reduced_date": "2026-08-10T14:30:00.000Z"
        },
        {
            "listing_id": "DW-78619-001",
            "address": "400 Elder Hill Rd",
            "city": "Driftwood",
            "zip_code": "78619",
            "price": 1680000.0,
            "sqft": 4100.0,
            "acreage": 3.80,
            "status": "Active",
            "url": "https://www.realtor.com/realestateandhomes-detail/400-Elder-Hill-Rd_Driftwood_TX_78619",
            "latitude": 30.1342,
            "longitude": -98.0210,
            "price_reduced_amount": 75000.0,
            "price_reduced_date": "2026-07-25T09:15:00.000Z"
        },
        {
            "listing_id": "DW-78619-002",
            "address": "120 Driftwood Estate Dr",
            "city": "Driftwood",
            "zip_code": "78619",
            "price": 975000.0,
            "sqft": 2400.0,
            "acreage": 0.95,
            "status": "Active",
            "url": "https://www.realtor.com/realestateandhomes-detail/120-Driftwood-Estate-Dr_Driftwood_TX_78619",
            "latitude": 30.1189,
            "longitude": -98.0432,
            "price_reduced_amount": 0.0,
            "price_reduced_date": ""
        }
    ]

def safe_float(val):
    if val is None or val == "":
        return None
    try:
        val_str = str(val).replace("+", "").replace(",", "").strip()
        return float(val_str)
    except Exception:
        return None

def normalize_and_calculate(raw_listing):
    """
    Extracts relevant fields from raw API responses and calculates:
    1. Acreage (derives from lot sqft if explicit acreage is missing)
    2. Price per Square Foot (Price / Living SqFt)
    3. Price per Acre (Price / Acreage)
    4. Latitude & Longitude coordinates for map visualization
    5. Official MLS Price Reduced Amount and Reduced Date
    """
    listing_id = raw_listing.get("listing_id") or raw_listing.get("property_id") or raw_listing.get("id") or raw_listing.get("mlsId")

    address_obj = raw_listing.get("address")
    latitude = None
    longitude = None

    if isinstance(address_obj, dict):
        address = address_obj.get("line") or address_obj.get("formattedAddress") or "Unknown Address"
        city = address_obj.get("city") or "Dripping Springs/Driftwood"
        zip_code = str(address_obj.get("postal_code") or address_obj.get("zip") or "")
        latitude = address_obj.get("latitude") or address_obj.get("lat")
        longitude = address_obj.get("longitude") or address_obj.get("lon") or address_obj.get("lng")
    else:
        address = raw_listing.get("address") or raw_listing.get("formattedAddress") or "Unknown Address"
        city = raw_listing.get("city") or "Dripping Springs/Driftwood"
        zip_code = str(raw_listing.get("zip_code") or raw_listing.get("postalCode") or raw_listing.get("zip") or "")

    if latitude is None:
        latitude = raw_listing.get("latitude") or raw_listing.get("lat")
    if longitude is None:
        longitude = raw_listing.get("longitude") or raw_listing.get("lon") or raw_listing.get("lng")

    # Fallback to approximate zip code center if lat/lon missing
    if latitude is None or longitude is None or safe_float(latitude) is None or safe_float(latitude) == 0:
        if "78619" in str(zip_code):
            latitude, longitude = 30.1325, -98.0285
        else:
            latitude, longitude = 30.1910, -98.0864

    price = safe_float(raw_listing.get("list_price") or raw_listing.get("price")) or 0.0
    sqft = safe_float(raw_listing.get("sqft") or raw_listing.get("buildingSize") or raw_listing.get("livingArea")) or 0.0

    # Acreage determination logic
    acreage = 0.0
    if raw_listing.get("acreage") is not None and raw_listing.get("acreage") != "":
        acreage = safe_float(raw_listing["acreage"]) or 0.0
    elif raw_listing.get("lot_acres") is not None and raw_listing.get("lot_acres") != "":
        acreage = safe_float(raw_listing["lot_acres"]) or 0.0
    elif raw_listing.get("lot_sqft") is not None and raw_listing.get("lot_sqft") != "":
        acreage = (safe_float(raw_listing["lot_sqft"]) or 0.0) / config.SQFT_PER_ACRE
    elif raw_listing.get("lotSizeSqFt") is not None and raw_listing.get("lotSizeSqFt") != "":
        acreage = (safe_float(raw_listing["lotSizeSqFt"]) or 0.0) / config.SQFT_PER_ACRE

    price_per_sqft = round(price / sqft, 2) if sqft > 0 else 0.0
    price_per_acre = round(price / acreage, 2) if acreage > 0 else 0.0

    beds = safe_float(raw_listing.get("beds"))
    baths = safe_float(raw_listing.get("baths"))
    property_type = str(raw_listing.get("property_type") or "single_family")
    county = str(raw_listing.get("county") or "Hays")

    price_reduced_amount = safe_float(raw_listing.get("price_reduced_amount")) or 0.0
    price_reduced_date = str(raw_listing.get("price_reduced_date") or "")

    return {
        "listing_id": str(listing_id),
        "address": address,
        "city": city,
        "zip_code": zip_code,
        "price": price,
        "sqft": sqft,
        "acreage": round(acreage, 2),
        "price_per_sqft": price_per_sqft,
        "price_per_acre": price_per_acre,
        "beds": beds,
        "baths": baths,
        "property_type": property_type,
        "county": county,
        "price_reduced_amount": price_reduced_amount,
        "price_reduced_date": price_reduced_date,
        "status": raw_listing.get("status", "Active"),
        "url": raw_listing.get("href") or raw_listing.get("url") or "",
        "latitude": safe_float(latitude) or 30.1910,
        "longitude": safe_float(longitude) or -98.0864
    }


def filter_listings(listings):
    """
    Applies custom domain filters:
    1. Target Locations: Zip code in 78620 or 78619
    2. Price Range: <= Max Price ($1,700,000)
    3. Minimum Lot Size: >= 0.75 Acres
    """
    filtered = []
    for item in listings:
        price_ok = item["price"] <= config.MAX_PRICE
        lot_ok = item["acreage"] >= config.MIN_ACRES

        if price_ok and lot_ok:
            filtered.append(item)
    return filtered

def print_summary_table(processed_records):
    """
    Formats and prints a clean ASCII terminal summary table of processed listings.
    """
    if not processed_records:
        print("\n[!] No listings matched the search and filter criteria.\n")
        return

    if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    table_data = []
    for r in processed_records:
        status_tag = r["change_status"]
        if status_tag == "PRICE_DROP" or r.get("price_reduced_amount", 0) > 0:
            status_display = "[PRICE DROP]"
            drop_amt = abs(r['price_delta']) if r.get('price_delta') else r.get("price_reduced_amount", 0)
            price_display = f"${r['price']:,.0f} (DROP -${drop_amt:,.0f})"
        elif status_tag == "NEW":
            status_display = "[NEW]"
            price_display = f"${r['price']:,.0f}"
        elif status_tag == "PRICE_INCREASE":
            status_display = "[PRICE INC]"
            price_display = f"${r['price']:,.0f} (INC +${r['price_delta']:,.0f})"
        else:
            status_display = "[UNCHANGED]"
            price_display = f"${r['price']:,.0f}"

        table_data.append({
            "Status": status_display,
            "Address": r["address"],
            "City": r["city"],
            "ZIP": r["zip_code"],
            "Price": price_display,
            "SqFt": f"{r['sqft']:,.0f}" if r["sqft"] > 0 else "N/A",
            "Acres": f"{r['acreage']:.2f}",
            "$/SqFt": f"${r['price_per_sqft']:,.2f}" if r["price_per_sqft"] > 0 else "N/A",
            "$/Acre": f"${r['price_per_acre']:,.2f}" if r["price_per_acre"] > 0 else "N/A",
        })

    df = pd.DataFrame(table_data)
    print("\n" + "=" * 105)
    print(" HILL COUNTRY REAL ESTATE TRACKER -- DRIPPING SPRINGS (78620) & DRIFTWOOD (78619)")
    print(f" Filters: Price <= ${config.MAX_PRICE:,.0f} | Min Lot Size >= {config.MIN_ACRES} Acres")
    print("=" * 105)
    print(tabulate(df, headers="keys", tablefmt="grid", showindex=False))
    print("=" * 105 + "\n")

def run_tracker(use_mock=False):
    """
    Main execution pipeline:
    1. Initializes database tables.
    2. Queries realtyapi.io for 78620 and 78619 (or loads mock data if specified/no API key).
    3. Normalizes metrics, calculates Price/SqFt & Price/Acre & coordinates.
    4. Filters listings by price buffer and acreage threshold.
    5. Saves records to SQLite DB and detects historical price drop events.
    6. Automatically regenerates dashboard.
    """
    logger.info("Initializing database...")
    database.init_db()

    raw_listings = []

    if use_mock or not config.REALTY_API_KEY:
        if not use_mock and not config.REALTY_API_KEY:
            logger.info("REALTY_API_KEY not found in environment. Running in DEMO/MOCK mode.")
        else:
            logger.info("Running in explicit DEMO/MOCK mode.")
        raw_listings = generate_mock_listings()
    else:
        for zip_code in config.TARGET_ZIP_CODES:
            zip_listings = fetch_listings_for_zip(zip_code)
            raw_listings.extend(zip_listings)

    logger.info(f"Retrieved total of {len(raw_listings)} raw listings.")

    normalized_listings = [normalize_and_calculate(item) for item in raw_listings]
    filtered_listings = filter_listings(normalized_listings)
    logger.info(f"{len(filtered_listings)} listings passed price and acreage criteria.")

    processed_records = []
    price_drops_count = 0
    new_listings_count = 0

    for item in filtered_listings:
        record = database.process_listing(item)
        processed_records.append(record)

        if record["change_status"] == "PRICE_DROP" or record.get("price_reduced_amount", 0) > 0:
            price_drops_count += 1
            logger.info(f"PRICE DROP FLAGGED! {record['address']}: New ${record['price']:,.0f}")
        elif record["change_status"] == "NEW":
            new_listings_count += 1

    logger.info(f"Database update complete: {new_listings_count} New Listings, {price_drops_count} Price Drops.")
    print_summary_table(processed_records)

    try:
        import build_dashboard
        build_dashboard.generate_dashboard_html()
    except Exception as e:
        logger.warning(f"Could not generate HTML dashboard: {e}")

    return processed_records

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Real Estate Tracker for Dripping Springs (78620) & Driftwood (78619)")
    parser.add_argument("--mock", action="store_true", help="Run with mock sample data for testing")
    args = parser.parse_args()

    run_tracker(use_mock=args.mock)
