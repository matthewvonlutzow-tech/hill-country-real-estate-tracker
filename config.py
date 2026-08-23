import os
from pathlib import Path
from dotenv import load_dotenv
import streamlit as st

# Load environment variables from .env file if available
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

def get_secret(key, default=""):
    try:
        if hasattr(st, "secrets") and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key, default)

# API Configuration
REALTY_API_KEY = get_secret("REALTY_API_KEY", "rt_x711Bq0tPHBq43V7RESuUeEj")
REALTY_API_BASE_URL = get_secret("REALTY_API_BASE_URL", "https://realtor.realtyapi.io")
REALTY_API_SEARCH_ENDPOINT = f"{REALTY_API_BASE_URL}/search/byzip"

# Target Geographic Criteria
# 78620: Dripping Springs, TX
# 78619: Driftwood, TX
TARGET_ZIP_CODES = ["78620", "78619"]
TARGET_LOCATIONS = ["Dripping Springs, TX", "Driftwood, TX"]

# Search & Filter Thresholds
# Max price: $1,600,000 baseline + $100,000 buffer = $1,700,000
MAX_PRICE = 1_700_000
MIN_ACRES = 0.75
SQFT_PER_ACRE = 43560.0  # Constant for converting lot sqft to acreage

# Database Configuration
DB_NAME = "hill_country_real_estate.db"

# API Request Options
DEFAULT_TIMEOUT = 15  # seconds
MAX_RETRIES = 3       # retries on rate limiting (429) or transient errors
RETRY_BACKOFF = 2.0   # seconds backoff multiplier
