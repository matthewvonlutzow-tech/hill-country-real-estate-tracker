# 🏡 Hill Country Real Estate Tracker & Analytics Dashboard

An interactive, visual real estate tracking application built with Python and Streamlit, targeting **Dripping Springs, TX (78620)** and **Driftwood, TX (78619)**.

Powered by live MLS data via `realtyapi.io` and SQLite database tracking.

---

## ✨ Features

- **🏡 Active Inventory & DSISD Matrix**: Filter listings by price, acreage, ZIP codes (`78620`, `78619`), Dripping Springs ISD (DSISD) status, and property amenities (*Pool, Garage, Multi-Car Garage, Workshop, No HOA, Ag Exemption, Guest House, Waterfront*).
- **📉 6-Month MLS Price Reduction Log**: Live feed tracking official Realtor.com price reductions logged over the last 6 months, displaying previous price, new price, dollar savings delta, and percentage saved ($\%$).
- **🗺️ Hill Country Property Value Map**: Interactive Plotly map color-coded by Value Tier (*Emerald Green for Exceptional Value, Sapphire Blue for Fair Market, Royal Purple for Premium Pricing*) with map overlays marking **Dripping Springs ISD Schools** and **Hospitals/ER Facilities**.
- **💎 Bang-For-Your-Buck Scoring**: Computes price-per-acre and price-per-sqft baselines vs hyper-local ZIP medians.

---

## 🚀 Deploying to Streamlit Community Cloud (Free 24/7 Hosting)

Follow these steps to host your application live on the web for free:

### 1. Push Code to GitHub
1. Create a new repository on [GitHub.com](https://github.com/new) named `hill-country-real-estate-tracker`.
2. Push your local files to GitHub:
   ```bash
   git init
   git add .
   git commit -m "Initial commit of Hill Country Real Estate Tracker"
   git branch -M main
   git remote add origin https://github.com/matthewvonlutzow-tech/hill-country-real-estate-tracker.git
   git push -u origin main
   ```

### 2. Connect to Streamlit Community Cloud
1. Go to [share.streamlit.io](https://share.streamlit.io) and log in with your GitHub account.
2. Click **"New app"**.
3. Select your repository: `matthewvonlutzow-tech/hill-country-real-estate-tracker`.
4. Main file path: `app.py`.
5. Click **"Advanced settings..."** and paste your API key under **Secrets**:
   ```toml
   REALTY_API_KEY = "rt_x711Bq0tPHBq43V7RESuUeEj"
   REALTY_API_BASE_URL = "https://realtor.realtyapi.io"
   ```
6. Click **"Deploy!"**. Your app will be live on a custom `.streamlit.app` URL!

---

## 🛠️ Local Installation & Setup

1. **Clone repository**:
   ```bash
   git clone https://github.com/YOUR_GITHUB_USERNAME/hill-country-real-estate-tracker.git
   cd hill-country-real-estate-tracker
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**:
   Create a `.env` file in the root directory:
   ```env
   REALTY_API_KEY=rt_x711Bq0tPHBq43V7RESuUeEj
   REALTY_API_BASE_URL=https://realtor.realtyapi.io
   ```

4. **Run Streamlit app locally**:
   ```bash
   streamlit run app.py
   ```

---

## 📁 Project Structure

```
├── app.py                 # Main Streamlit UI & tab layout
├── analytics.py           # Value scoring, DSISD logic, keyword feature search
├── database.py            # SQLite interface (listings & price_history tables)
├── tracker.py             # API fetching, data normalization, CLI tracking
├── config.py              # Configuration settings & environment variables
├── requirements.txt       # Python dependencies
└── README.md              # Project documentation
```
