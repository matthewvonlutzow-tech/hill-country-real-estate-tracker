import sqlite3
from datetime import datetime
import config

def get_db_connection(db_path=config.DB_NAME):
    """Establishes and returns a connection to the SQLite database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path=config.DB_NAME):
    """
    Initializes the SQLite database tables if they do not exist.
    Creates 'listings' and 'price_history' tables with price reduction fields.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Table for storing current property listings state
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS listings (
            listing_id TEXT PRIMARY KEY,
            address TEXT NOT NULL,
            city TEXT NOT NULL,
            zip_code TEXT NOT NULL,
            price REAL NOT NULL,
            sqft REAL,
            acreage REAL,
            price_per_sqft REAL,
            price_per_acre REAL,
            beds REAL,
            baths REAL,
            property_type TEXT,
            county TEXT,
            price_reduced_amount REAL,
            price_reduced_date TEXT,
            status TEXT DEFAULT 'Active',
            url TEXT,
            latitude REAL,
            longitude REAL,
            first_seen DATETIME NOT NULL,
            last_updated DATETIME NOT NULL
        );
    """)

    # Ensure schema migrations for existing SQLite databases
    cursor.execute("PRAGMA table_info(listings)")
    existing_cols = [col[1] for col in cursor.fetchall()]
    
    migrations = [
        ("latitude", "REAL"),
        ("longitude", "REAL"),
        ("beds", "REAL"),
        ("baths", "REAL"),
        ("property_type", "TEXT"),
        ("county", "TEXT"),
        ("price_reduced_amount", "REAL"),
        ("price_reduced_date", "TEXT")
    ]
    for col_name, col_type in migrations:
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE listings ADD COLUMN {col_name} {col_type}")

    # Table for tracking historical price changes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id TEXT NOT NULL,
            old_price REAL NOT NULL,
            new_price REAL NOT NULL,
            price_delta REAL NOT NULL,
            change_type TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            FOREIGN KEY (listing_id) REFERENCES listings (listing_id)
        );
    """)

    conn.commit()
    conn.close()

def process_listing(listing_data, db_path=config.DB_NAME):
    """
    Processes a scraped listing against stored database records.
    - Captures MLS official price_reduced_amount & price_reduced_date.
    - Records price reduction events into price_history.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    listing_id = str(listing_data["listing_id"])
    new_price = float(listing_data["price"])
    sqft = float(listing_data.get("sqft") or 0.0)
    acreage = float(listing_data.get("acreage") or 0.0)
    price_per_sqft = float(listing_data.get("price_per_sqft") or 0.0)
    price_per_acre = float(listing_data.get("price_per_acre") or 0.0)
    beds = float(listing_data["beds"]) if listing_data.get("beds") is not None else None
    baths = float(listing_data["baths"]) if listing_data.get("baths") is not None else None
    property_type = str(listing_data.get("property_type") or "single_family")
    county = str(listing_data.get("county") or "Hays")

    price_reduced_amount = float(listing_data.get("price_reduced_amount") or 0.0)
    price_reduced_date = str(listing_data.get("price_reduced_date") or "")

    latitude = float(listing_data.get("latitude")) if listing_data.get("latitude") is not None else None
    longitude = float(listing_data.get("longitude")) if listing_data.get("longitude") is not None else None

    # Check if property already exists in DB
    cursor.execute("SELECT price, first_seen FROM listings WHERE listing_id = ?", (listing_id,))
    row = cursor.fetchone()

    result_status = "UNCHANGED"
    price_delta = 0.0
    old_price = None

    if row is None:
        result_status = "NEW"
        cursor.execute("""
            INSERT INTO listings (
                listing_id, address, city, zip_code, price, sqft, acreage,
                price_per_sqft, price_per_acre, beds, baths, property_type, county,
                price_reduced_amount, price_reduced_date,
                status, url, latitude, longitude, first_seen, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            listing_id,
            listing_data.get("address", "N/A"),
            listing_data.get("city", "N/A"),
            listing_data.get("zip_code", "N/A"),
            new_price,
            sqft,
            acreage,
            price_per_sqft,
            price_per_acre,
            beds,
            baths,
            property_type,
            county,
            price_reduced_amount,
            price_reduced_date,
            listing_data.get("status", "Active"),
            listing_data.get("url", ""),
            latitude,
            longitude,
            now_str,
            now_str
        ))

        # Log price reduction into price_history if MLS reports a price reduction
        if price_reduced_amount > 0:
            old_p = new_price + price_reduced_amount
            drop_time = price_reduced_date if price_reduced_date else now_str
            # Reformat ISO string to standard date
            if "T" in drop_time:
                drop_time = drop_time.split("T")[0] + " " + drop_time.split("T")[1].split(".")[0]

            cursor.execute("""
                INSERT INTO price_history (listing_id, old_price, new_price, price_delta, change_type, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (listing_id, old_p, new_price, -price_reduced_amount, "PRICE_DROP", drop_time))
        else:
            cursor.execute("""
                INSERT INTO price_history (listing_id, old_price, new_price, price_delta, change_type, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (listing_id, 0.0, new_price, new_price, "NEW_LISTING", now_str))

    else:
        old_price = float(row["price"])
        price_delta = new_price - old_price

        if new_price < old_price:
            result_status = "PRICE_DROP"
            change_type = "PRICE_DROP"
        elif new_price > old_price:
            result_status = "PRICE_INCREASE"
            change_type = "PRICE_INCREASE"
        else:
            result_status = "UNCHANGED"
            change_type = "UNCHANGED"

        cursor.execute("""
            UPDATE listings SET
                price = ?,
                sqft = ?,
                acreage = ?,
                price_per_sqft = ?,
                price_per_acre = ?,
                beds = ?,
                baths = ?,
                property_type = ?,
                county = ?,
                price_reduced_amount = ?,
                price_reduced_date = ?,
                status = ?,
                url = ?,
                latitude = ?,
                longitude = ?,
                last_updated = ?
            WHERE listing_id = ?
        """, (
            new_price, sqft, acreage, price_per_sqft, price_per_acre,
            beds, baths, property_type, county,
            price_reduced_amount, price_reduced_date,
            listing_data.get("status", "Active"), listing_data.get("url", ""),
            latitude, longitude, now_str, listing_id
        ))

        if result_status in ("PRICE_DROP", "PRICE_INCREASE"):
            cursor.execute("""
                INSERT INTO price_history (listing_id, old_price, new_price, price_delta, change_type, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (listing_id, old_price, new_price, price_delta, change_type, now_str))
        elif price_reduced_amount > 0:
            # Also record MLS price reduction if not yet present
            cursor.execute("SELECT id FROM price_history WHERE listing_id = ? AND change_type = 'PRICE_DROP'", (listing_id,))
            if cursor.fetchone() is None:
                old_p = new_price + price_reduced_amount
                drop_time = price_reduced_date if price_reduced_date else now_str
                if "T" in drop_time:
                    drop_time = drop_time.split("T")[0] + " " + drop_time.split("T")[1].split(".")[0]
                cursor.execute("""
                    INSERT INTO price_history (listing_id, old_price, new_price, price_delta, change_type, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (listing_id, old_p, new_price, -price_reduced_amount, "PRICE_DROP", drop_time))

    conn.commit()
    conn.close()

    processed_record = dict(listing_data)
    processed_record["change_status"] = result_status
    processed_record["price_delta"] = price_delta
    processed_record["old_price"] = old_price
    return processed_record

def get_all_listings(db_path=config.DB_NAME):
    """Retrieves all stored listings from database as list of dicts."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM listings ORDER BY last_updated DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_price_drop_history(db_path=config.DB_NAME):
    """Retrieves all price drop events recorded in price_history."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT h.*, l.address, l.city, l.zip_code, l.url, l.sqft, l.acreage, l.price_per_acre, l.price_per_sqft
        FROM price_history h
        JOIN listings l ON h.listing_id = l.listing_id
        WHERE h.change_type = 'PRICE_DROP'
        ORDER BY h.timestamp DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
