# visualization3_dark.py
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import seaborn as sns
import geopandas as gpd
import country_converter as coco
import wbgapi as wb
import janitor

# --- Global color palette ---
fuel_color_palette = {
    'coal': '#A0522D', 'oil': '#36454F', 'gas': '#6B9BD1',
    'hydro': '#0077BE', 'solar': '#FFA500', 'wind': '#A8D5E2',
    'biofuel': '#556B2F', 'other_renewable': '#20B2AA', 'nuclear': '#E91E63'
}

# --- Load Data ---
@st.cache_data(show_spinner=True)
def load_data():
    # CO2 data
    co2_df = (
        pd.read_csv("https://ourworldindata.org/grapher/co-emissions-per-capita.csv?v=1&csvType=full&useColumnShortNames=true")
        .clean_names()
        .rename(columns={'emissions_total_per_capita': 'co2_per_capita', 'entity': 'country', 'code': 'iso_code'})
        .query("year >= 1990")
    )

    # Energy data
    energy_df = (
        pd.read_csv("https://nyc3.digitaloceanspaces.com/owid-public/data/energy/owid-energy-data.csv")
        .clean_names()
        .query("year >= 1990")
        .dropna(subset=['iso_code'])
        .rename(columns={
            'biofuel_electricity': 'biofuel', 'coal_electricity': 'coal', 'gas_electricity': 'gas',
            'hydro_electricity': 'hydro', 'nuclear_electricity': 'nuclear', 'oil_electricity': 'oil',
            'other_renewable_exc_biofuel_electricity': 'other_renewable',
            'solar_electricity': 'solar', 'wind_electricity': 'wind'
        })
    )

    # GDP data
    indicator_id = 'NY.GDP.PCAP.PP.KD'
    gdp_percap_df = wb.data.DataFrame(
        indicator_id, time=range(1990, 2024), skipBlanks=True, columns='series'
    ).reset_index().rename(columns={'economy': 'iso_code', 'time': 'year', indicator_id: 'GDPpercap'})
    gdp_percap_df['year'] = gdp_percap_df['year'].str.replace('YR', '', regex=False).astype(int)

    # Long-format energy
    energy_long_df = (
        energy_df
        .filter(items=['country', 'year', 'iso_code', 'population', 'gdp', 'biofuel', 'coal', 'gas', 'hydro', 'nuclear', 'oil', 'other_renewable', 'solar', 'wind'])
        .melt(id_vars=['country', 'year', 'iso_code', 'population', 'gdp'], var_name='source', value_name='value')
        .dropna(subset=['value', 'iso_code'])
    )

    # Merge datasets
    merged_df = pd.merge(energy_df, gdp_percap_df, on=['iso_code', 'year'], how='inner')
    combined_df = pd.merge(merged_df, co2_df.drop(columns=['country']), on=['iso_code', 'year'], how='inner')
    combined_df['continent'] = coco.convert(names=combined_df['country'], to='continent', not_found=None)

    return co2_df, energy_df, energy_long_df, combined_df

# --- Plot Functions ---
def plot_electricity_mix(country, energy_long_df):
    country_energy_df = energy_long_df.query(f"country == '{country}'")
    if country_energy_df.empty:
        st.warning(f"No energy data for {country}")
        return

    pivot_df = country_energy_df.pivot_table(index='year', columns='source', values='value', aggfunc='sum')
    source_order = pivot_df.max().sort_values(ascending=False).index
    pivot_df = pivot_df[source_order]
    pivot_df_percentage = pivot_df.divide(pivot_df.sum(axis=1), axis=0).fillna(0)
    ordered_colors = [fuel_color_palette.get(source, '#CCCCCC') for source in source_order]

    fig, ax = plt.subplots(figsize=(12, 6))
    pivot_df_percentage.plot.area(ax=ax, stacked=True, alpha=0.9, linewidth=0.5, legend=False, color=ordered_colors)
    ax.set_title(f"Electricity Production Mix (%) for {country}", fontsize=16)
    ax.set_ylabel("Share of Total Electricity Production")
    ax.set_xlabel(None)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: '{:.0%}'.format(y)))
    ax.margins(x=0, y=0)
    ax.set_ylim(0, 1)
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles=handles[::-1], labels=labels[::-1], title='Source', bbox_to_anchor=(1.05, 1), loc='upper left')
    st.pyplot(fig)

def top_fuel(source, year, n, energy_long_df):
    top_producers = (
        energy_long_df.query(f"source == '{source}' and year == {year}")
        .nlargest(n, 'value').sort_values('value', ascending=True)
    )
    if top_producers.empty:
        st.warning(f"No data for {source} in {year}")
        return
    bar_color = fuel_color_palette.get(source, '#CCCCCC')
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(top_producers['country'], top_producers['value'], color=bar_color)
    ax.set_title(f"Top {n} {source.capitalize()} Producing Countries in {year} (TWh)", fontsize=16)
    ax.set_xlabel("Electricity Produced (TWh)")
    ax.bar_label(bars, fmt='%.1f', padding=5, fontsize=10, fontweight='bold')
    ax.set_xlim(right=ax.get_xlim()[1] * 1.05)
    st.pyplot(fig)

# --- Main function for Streamlit ---
def run_visualization_3():
    st.header("Global Electricity, CO2 & GDP Dashboard")
    st.write("This interactive dashboard allows users to explore the relationship between electricity consumption, CO₂ emissions, and economic performance across countries. Users can select a specific country (e.g., Canada), choose a fuel type (e.g., biofuel), and pick a year (e.g., 1990 or 2023) to analyze trends. The dashboard also highlights top countries based on selected criteria, enabling comparisons of energy usage, emissions, and GDP growth over time.")
    co2_df, energy_df, energy_long_df, combined_df = load_data()

    # --- Interactive country selector ---
    country_list = sorted(energy_df['country'].dropna().unique())
    selected_country = st.selectbox("Select a country", country_list)
    plot_electricity_mix(selected_country, energy_long_df)

    # --- Interactive fuel top-n ---
    st.markdown("---")
    st.header("Top Fuel Producing Countries Visualization (1990-2023)")
    fuel_list = sorted(energy_long_df['source'].unique())
    selected_fuel = st.selectbox("Select fuel", fuel_list)
    year = st.slider("Select year", min_value=1990, max_value=2023, value=2023)
    n = st.slider("Number of top countries", min_value=3, max_value=30, value=10)
    top_fuel(selected_fuel, year, n, energy_long_df)
