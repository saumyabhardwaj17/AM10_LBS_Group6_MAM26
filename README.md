# Interactive Data Dashboards: Elections & Global Energy Trends

This project provides interactive dashboards for visualizing US presidential election results and global energy, CO₂ emissions, and GDP trends using Streamlit.

## Features

- **US County-Level Election Map (2024):** Choropleth map showing county-level margins for the 2024 US presidential election.
- **GOP Vote Shifts (2020 vs 2024):** Scatter plot comparing Republican vote margins by county between 2020 and 2024.
- **Global Electricity, CO₂ & GDP Dashboard:** Interactive visualization of global energy and economic data.

## Files

- `app.py`: Main Streamlit app with dashboard tabs.
- `visualization3_dark.py`: Contains logic for the global energy/GDP visualization.
- `data/`: Folder for default CSV data files (2024 & 2020 US county-level results).

## Setup

1. **Install dependencies:**

   ```bash
   pip install streamlit pandas geopandas plotly numpy
   ```

2. **Run the app:**

   ```bash
   streamlit run app.py
   ```

3. **Data files:**
   - Data files are expected in the same folder.

## Usage

- Open the Streamlit app in your browser.
- Navigate between tabs for different visualizations.
- Hover over map/scatter points for detailed info.

## Notes

- For the global dashboard, ensure `visualization3_dark.py` is present in the same directory.
- Some visualizations require internet access to fetch US Census shapefiles.

## License

Please Note that this project has been done by LBS Students as part of their assignment.
Sincerely, Group 6, MAM'26.

