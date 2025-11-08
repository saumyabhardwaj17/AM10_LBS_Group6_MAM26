# app.py
import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from io import BytesIO
import urllib.request

st.set_page_config(layout="wide", page_title="Data Dashboards - Group 6")

st.title("Interactive Data Dashboards: Elections & Global Energy Trends")

# -------------------------
# Utility helpers
# -------------------------
def pick_first(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None

@st.cache_data
def read_csv(path_or_buffer):
    return pd.read_csv(path_or_buffer)

@st.cache_resource
def read_geodata_from_url(url):
    # geopandas will cache if same URL is used and this function is cached
    return gpd.read_file(url)

def safe_to_str_zfill(s, width=5):
    return s.astype(str).str.zfill(width)

# -------------------------
# Sidebar / Data input
# -------------------------
#st.sidebar.header("Data inputs")
#use_default = st.sidebar.checkbox("Use default data files in ./data (2024 & 2020)", value=True)
use_default=None
uploaded_2024 = None
uploaded_2020 = None
# if not use_default:
#     uploaded_2024 = st.sidebar.file_uploader("Upload 2024 county-level CSV", type=["csv"])
#     uploaded_2020 = st.sidebar.file_uploader("Upload 2020 county-level CSV", type=["csv"])

# Default paths (you can edit)
DEFAULT_2024 = "./data/2024_US_County_level_Presidential_Results.csv"
DEFAULT_2020 = "./data/2020_US_County_level_Presidential_Results.csv"

# -------------------------
# Load Data (with errors surfaced)
# -------------------------
@st.cache_data
def load_election_df_2024(path_or_buffer):
    df = pd.read_csv(path_or_buffer)
    return df

@st.cache_data
def load_election_df_2020(path_or_buffer):
    df = pd.read_csv(path_or_buffer)
    return df

# Helper to open file-like objects in either uploaded or path mode
def get_buffer(uploaded, default_path):
    if uploaded is not None:
        return uploaded
    return default_path

# -------------------------
# Tabs
# -------------------------
tab1, tab2, tab3 = st.tabs(["US County-Level Election Map (2024)", "GOP Vote Shifts: 2020 vs 2024", "Global Electricity, CO2 & GDP Dashboard"])

# -------------------------
# Tab 1: County choropleth using your provided logic
# -------------------------
with tab1:
    st.header("2024 US County Level Presidential Results: Trump vs Kamala")
    st.write("The graph shows the margin of the popular vote by county in the 2024 U.S. presidential election. Donald Trump led in most rural counties across the South, Midwest, and West, often by large margins, while Kamala Harris performed strongly in urban counties such as New York, Los Angeles, and Chicago. The visualization highlights the stark rural-urban divide, with Republican support dominating geographically and Democratic support concentrated in densely populated areas.")

    try:
        buf_2024 = get_buffer(uploaded_2024 if not use_default else None, DEFAULT_2024)
        df = load_election_df_2024(buf_2024)

        # ---------- Robust column detection ----------
        fips_col = pick_first(df, ["GEOID","fips","FIPS","county_fips","county_fips_code","fips_code","countyFIPS"])
        if fips_col is None:
            st.error(
                "No FIPS-like column found. Available columns:\n" + ", ".join(list(df.columns)) +
                "\n\nPlease include one of: GEOID, fips, FIPS, county_fips, county_fips_code, fips_code, countyFIPS"
            )
        else:
            df[fips_col] = safe_to_str_zfill(df[fips_col], width=5)

            trump_pct_col = pick_first(df, ["trump_pct","pct_trump","per_gop","pct_gop","rep_pct","republican_pct"])
            biden_pct_col = pick_first(df, ["biden_pct","pct_biden","per_dem","pct_dem","dem_pct","democrat_pct"])

            trump_votes_col = pick_first(df, ["trump_votes","votes_trump","gop_votes","rep_votes","republican_votes"])
            biden_votes_col = pick_first(df, ["biden_votes","votes_biden","dem_votes","democrat_votes"])
            total_votes_col = pick_first(df, ["total_votes","votes_total","total","ballots"])

            pre_margin_col = pick_first(df, [
                "margin","margin_pct","rep_margin","gop_margin","trump_biden_margin","trump_minus_biden_pct",
                "biden_trump_margin","per_point_diff"
            ])

            # Compute margin in percentage points (Trump − Kamala)
            used = None
            if trump_pct_col and biden_pct_col:
                # scale detection: if fractions use *100
                scale = 100 if df[trump_pct_col].abs().max() <= 1.5 else 1
                df["margin_pct"] = (df[trump_pct_col].astype(float) - df[biden_pct_col].astype(float)) * scale
                used = f"Used % columns: {trump_pct_col} − {biden_pct_col}"
            elif pre_margin_col:
                m = df[pre_margin_col].astype(float)
                df["margin_pct"] = np.where(m.abs().max() <= 1.5, m*100, m)
                used = f"Used provided margin column: {pre_margin_col}"
            elif trump_votes_col and biden_votes_col:
                if total_votes_col is None:
                    df["__total_votes__"] = df[trump_votes_col].fillna(0) + df[biden_votes_col].fillna(0)
                    total_votes_col = "__total_votes__"
                df["margin_pct"] = ( (df[trump_votes_col].astype(float) - df[biden_votes_col].astype(float)) / df[total_votes_col].astype(float) ) * 100
                used = f"Computed from vote counts: ({trump_votes_col} − {biden_votes_col}) / {total_votes_col}"
            else:
                st.error(
                    "Could not find Trump/Kamala percent or vote columns to compute a margin.\n"
                    "Available columns:\n" + ", ".join(list(df.columns)) +
                    "\nTry renaming your columns or add one of the expected names."
                )
                used = None

            if used:
                #st.info(used)

                # ---------- Load county shapes ----------
                # Use Census 2024 counties (20m resolution)
                shp_url = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_20m.zip"
                with st.spinner("Loading county shapes (may take a few seconds)..."):
                    counties = read_geodata_from_url(shp_url)

                # drop territories like VI if present (as in your code)
                if "STATEFP" in counties.columns:
                    counties = counties[~counties["STATEFP"].isin(["78"])]
                # make GEOID for join
                counties["GEOID"] = counties["STATEFP"].astype(str) + counties["COUNTYFP"].astype(str)
                # Merge
                g = counties.merge(df[[fips_col,"margin_pct"]], left_on="GEOID", right_on=fips_col, how="left")

                # ---------- Plotly choropleth ----------
                my_scale = ['#00429d','#4771b2','#73a2c6','#a5d5d8','#ffffe0',
                            '#ffbcaf','#f4777f','#cf3759','#93003a']

                # Plotly Express expects geojson; pass index-based locations and the __geo_interface__
                fig = px.choropleth(
                    g,
                    geojson=g.__geo_interface__,
                    locations=g.index,
                    color="margin_pct",
                    color_continuous_scale=my_scale,
                    range_color=[-50, 50],
                    color_continuous_midpoint=0,
                    scope="usa",
                    projection="albers usa",
                    hover_data={"NAME":True,"STATEFP":False,"margin_pct":":.1f"}
                )
                fig.update_traces(marker_line_width=0.2, marker_line_color="rgba(80,80,80,0.7)")

                # Add state abbrevs as text annotations
                states = read_geodata_from_url("https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_state_20m.zip")
                # drop territories commonly excluded
                if "STUSPS" in states.columns:
                    states = states[~states["STUSPS"].isin(["AS","GU","MP","VI"])].copy()
                try:
                    # compute centroids safely by projecting
                    states = states.to_crs(5070)
                    states["cx"] = states.geometry.centroid.x
                    states["cy"] = states.geometry.centroid.y
                    states = states.to_crs(4326)
                    fig.add_trace(go.Scattergeo(
                        lon=states.to_crs(4326).geometry.centroid.x,
                        lat=states.to_crs(4326).geometry.centroid.y,
                        text=states["STUSPS"],
                        mode="text",
                        textfont=dict(size=12, color="black"),
                        hoverinfo="skip",
                        showlegend=False
                    ))
                except Exception:
                    # If centroid calculation fails, ignore state labels
                    st.warning("Could not compute state centroids for labels — continuing without state text overlay.")

                fig.update_layout(
                    title={"text": "% Margin of the popular vote by county<br><sup>US Presidential Election 2024</sup>",
                           "x":0.02,"y":0.9,"xanchor":"left"},
                    margin=dict(l=10,r=10,t=60,b=10),
                    coloraxis_colorbar=dict(
                        title="Margins",
                        tickvals=[-50,0,50],
                        ticktext=["+50% Kamala","0%","+50% Trump"],
                        len=0.75
                    )
                )
                

                # Show interactive figure
                st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.exception(e)

# -------------------------
# Tab 2: 2024 vs 2020 scatter (your provided code adapted)
# -------------------------
with tab2:
    st.header("County Margin Comparison: 2024 vs 2020 U.S. Presidential Election")
    st.write("This scatter plot compares Republican (GOP) vote margins in each county between the 2020 and 2024 U.S. presidential elections. The graph shows how support for Republican and Democratic candidates shifted over the two elections. Points above the diagonal indicate counties that swung further toward Republicans in 2024, while points below show counties that leaned more Democratic, highlighting changing voting patterns across the country.")

    try:
        buf_2024 = get_buffer(uploaded_2024 if not use_default else None, DEFAULT_2024)
        buf_2020 = get_buffer(uploaded_2020 if not use_default else None, DEFAULT_2020)
        df2024 = load_election_df_2024(buf_2024)
        df2020 = load_election_df_2020(buf_2020)

        # Ensure we have a common FIPS column name — try some variants
        fips_2024 = pick_first(df2024, ["GEOID","fips","FIPS","county_fips","county_fips_code","fips_code","countyFIPS"])
        fips_2020 = pick_first(df2020, ["GEOID","fips","FIPS","county_fips","county_fips_code","fips_code","countyFIPS"])

        if fips_2024 is None or fips_2020 is None:
            st.error("Couldn't find FIPS-like column in one of the files. Please ensure both files contain a FIPS column.")
        else:
            df2024[fips_2024] = safe_to_str_zfill(df2024[fips_2024])
            df2020[fips_2020] = safe_to_str_zfill(df2020[fips_2020])

            # Normalize column names used in your snippet: assume county_fips in 2024 is called 'county_fips'
            merge_left_on = fips_2024
            merge_right_on = fips_2020

            merged_df = pd.merge(
                df2024,
                df2020.drop(columns=[c for c in ['state_name', 'county_name', 'votes_gop', 'votes_dem', 'total_votes', 'diff'] if c in df2020.columns]),
                left_on=merge_left_on,
                right_on=merge_right_on,
                how='inner',
                suffixes=('_2024', '_2020')
            )

            # try to create or map columns used in your plotting logic
            # Many different names are possible — try to find them
            per_gop_2024 = pick_first(merged_df, ['per_gop_2024','per_gop_2024','per_gop','pct_gop_2024','gop_pct_2024','per_gop'])
            per_dem_2024 = pick_first(merged_df, ['per_dem_2024','per_dem','pct_dem_2024','dem_pct_2024','per_dem'])
            per_gop_2020 = pick_first(merged_df, ['per_gop_2020','per_gop_2020','per_gop_2020'])
            per_dem_2020 = pick_first(merged_df, ['per_dem_2020','per_dem_2020','per_dem_2020'])

            # If per_gop/per_dem not found, try votes -> percent conversion
            # We'll attempt to use columns that are present — but we will prefer any 'per_point_diff' style columns if present
            # Create Margin columns if not present
            if 'per_point_diff_2024' not in merged_df.columns:
                # Try to compute from per_gop/per_dem (0-1 or percent)
                if per_gop_2024 and per_dem_2024:
                    scale = 100 if merged_df[per_gop_2024].abs().max() <= 1.5 else 1
                    merged_df['per_point_diff_2024'] = (merged_df[per_gop_2024].astype(float) - merged_df[per_dem_2024].astype(float)) * scale
                else:
                    # fallback: try votes difference / total_votes_2024 if present
                    votes_gop = pick_first(merged_df, ['gop_votes_2024','votes_gop_2024','votes_gop','gop_votes'])
                    votes_dem = pick_first(merged_df, ['dem_votes_2024','votes_dem_2024','votes_dem','dem_votes'])
                    tot_votes = pick_first(merged_df, ['total_votes_2024','total_votes'])
                    if votes_gop and votes_dem:
                        if tot_votes is None:
                            merged_df['__total_votes__'] = merged_df[votes_gop].fillna(0) + merged_df[votes_dem].fillna(0)
                            tot_votes = '__total_votes__'
                        merged_df['per_point_diff_2024'] = ((merged_df[votes_gop].astype(float) - merged_df[votes_dem].astype(float)) / merged_df[tot_votes].astype(float)) * 100

            if 'per_point_diff_2020' not in merged_df.columns:
                if per_gop_2020 and per_dem_2020:
                    scale = 100 if merged_df[per_gop_2020].abs().max() <= 1.5 else 1
                    merged_df['per_point_diff_2020'] = (merged_df[per_gop_2020].astype(float) - merged_df[per_dem_2020].astype(float)) * scale
                else:
                    # fallback skip if not found
                    pass

            # Rename for clarity like your snippet
            if 'state_name_2024' in merged_df.columns:
                merged_df = merged_df.rename(columns={'state_name_2024':'State'})
            elif 'state_name' in merged_df.columns:
                merged_df = merged_df.rename(columns={'state_name':'State'})

            # Winner_2024
            # attempt to find per_gop and per_dem columns with _2024 suffix or without
            p_gop_24 = pick_first(merged_df, ['per_gop_2024','per_gop','per_gop2024','per_gop_24','pct_gop_2024'])
            p_dem_24 = pick_first(merged_df, ['per_dem_2024','per_dem','per_dem2024','per_dem_24','pct_dem_2024'])
            if p_gop_24 and p_dem_24:
                merged_df['Winner_2024'] = np.where(merged_df[p_gop_24].astype(float) > merged_df[p_dem_24].astype(float),'Republican','Democratic')

            
            else:
                # fallback by sign of margin
                if 'per_point_diff_2024' in merged_df.columns:
                    merged_df['Winner_2024'] = merged_df['per_point_diff_2024'].apply(lambda x: 'Republican' if x > 0 else 'Democratic')
                else:
                    merged_df['Winner_2024'] = 'Unknown'

            # Prepare plotting columns
            x_col = 'per_point_diff_2024'
            y_col = 'per_point_diff_2020'
            hover_name_col = pick_first(merged_df, ['county_name_2024','county_name','NAME','county_name'])
            state_name_col = 'State'
            total_votes_col = pick_first(merged_df, ['total_votes_2024','total_votes','Total_Votes_2024'])

            # if x_col not in merged_df.columns or y_col not in merged_df.columns:
            #     st.error("Could not construct both margin columns (per_point_diff_2024 and per_point_diff_2020). Check your data or provide compatible CSVs.")
            # else:
            #     # Color and axis range setup
            #     color_map = {'Republican': 'red', 'Democratic': 'blue', 'Unknown': 'gray'}
            #     max_val = max(merged_df[x_col].abs().max(), merged_df[y_col].abs().max()) * 1.05
            #     range_val = [-max_val, max_val]

            #     fig = px.scatter(
            #         merged_df,
            #         x=y_col,
            #         y=x_col,
            #         color='Winner_2024',
            #         color_discrete_map=color_map,
            #         hover_name=hover_name_col,
            #         hover_data={
            #             state_name_col: True,
            #             x_col: ':.2f',
            #             y_col: ':.2f',
            #             total_votes_col: ':,'
            #         },
            #         #title="US Presidential Election: 2024 vs. 2020 (County margins)",
            #         title=dict(text="US Presidential Election: 2024 vs. 2020 (County margins)", font=dict(color='black', size=20),  x=0.5),  # center the title
                    
            #     )

            #     # Shift reference line
            #     fig.add_shape(
            #         type="line",
            #         x0=range_val[0], y0=range_val[0],
            #         x1=range_val[1], y1=range_val[1],
            #         line=dict(
            #             color="gray",
            #             width=1,
            #             dash="dot"))

            #     # Q2 reddish
            #     fig.add_shape(
            #         type="rect",
            #         x0=range_val[0], x1=0,
            #         y0=0, y1=range_val[1],
            #         line=dict(width=0),
            #         fillcolor='rgba(255, 0, 0, 0.08)',
            #         layer="below"
            #     )

            #     # Q4 bluish
            #     fig.add_shape(
            #         type="rect",
            #         x0=0, x1=range_val[1],
            #         y0=range_val[0], y1=0,
            #         line=dict(width=0),
            #         fillcolor='rgba(0, 0, 255, 0.08)',
            #         layer="below"
            #     )

            #     fig.update_traces(marker=dict(size=4, opacity=0.6))
            #     fig.update_layout(
            #         width=1000,
            #         height=800,
            #         plot_bgcolor='white',
            #         paper_bgcolor='white',
            #         yaxis_scaleanchor="x",
            #         yaxis_scaleratio=1,
            #         xaxis=dict(
            #             title=dict(text="2020 GOP Win Margin (GOP % - DEM %)", font=dict(color='black', size=14)  ),
            #             range=range_val,
            #             showgrid=False,
            #             zeroline=True,
            #             zerolinecolor='grey',
            #             zerolinewidth=2,
            #             tickformat=".0%",
            #             dtick=0.2,
            #             tickfont=dict(color='black')
            #         ),
            #         yaxis=dict(
            #             dict(text="2024 GOP Win Margin (GOP % - DEM %)", font=dict(color='black', size=14)  ),
            #             range=range_val,
            #             showgrid=False,
            #             zeroline=True,
            #             zerolinecolor='grey',
            #             zerolinewidth=2,
            #             tickformat=".0%",
            #             dtick=0.2,
            #             tickfont=dict(color='black')
            #         ),
            #         legend_title_text='2024 County Winner',
            #         hovermode="closest"
            #     )

            #     st.plotly_chart(fig, use_container_width=True)

            
            if x_col not in merged_df.columns or y_col not in merged_df.columns:
                st.error(
                    "Could not construct both margin columns (per_point_diff_2024 and per_point_diff_2020). "
                    "Check your data or provide compatible CSVs."
                )
            else:
                # Color and axis range setup
                color_map = {'Republican': 'red', 'Democratic': 'blue', 'Unknown': 'gray'}
                max_val = max(merged_df[x_col].abs().max(), merged_df[y_col].abs().max()) * 1.05
                range_val = [-max_val * 1.1, max_val * 1.1]

                fig = px.scatter(
                    merged_df,
                    x=y_col,
                    y=x_col,
                    color='Winner_2024',
                    color_discrete_map=color_map,
                    hover_name=hover_name_col,
                    hover_data={
                        state_name_col: True,
                        x_col: ':.2f',
                        y_col: ':.2f',
                        total_votes_col: ':,'
                    }
                )

                # Set main title
                fig.update_layout(
                    title=dict(
                        text="US Presidential Election: 2024 vs. 2020 (County margins)",
                        font=dict(color='black', size=20),
                        x=0.5,  # center
                        xanchor='center'
                    )
                )

                # Reference line
                fig.add_shape(
                    type="line",
                    x0=range_val[0], y0=range_val[0],
                    x1=range_val[1], y1=range_val[1],
                    line=dict(color="gray", width=1, dash="dot")
                )

                # Quadrant shading
                fig.add_shape(
                    type="rect",
                    x0=range_val[0], x1=0,
                    y0=0, y1=range_val[1],
                    line=dict(width=0),
                    fillcolor='rgba(255, 0, 0, 0.08)',
                    layer="below"
                )
                fig.add_shape(
                    type="rect",
                    x0=0, x1=range_val[1],
                    y0=range_val[0], y1=0,
                    line=dict(width=0),
                    fillcolor='rgba(0, 0, 255, 0.08)',
                    layer="below"
                )

                # Marker style
                fig.update_traces(marker=dict(size=4, opacity=0.6))

                # Layout for axes and legend
                fig.update_layout(
                    width=1000,
                    height=800,
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    yaxis_scaleanchor="x",
                    yaxis_scaleratio=1,
                    xaxis=dict(
                        title=dict(text="2020 GOP Win Margin (GOP % - DEM %)", font=dict(color='black', size=14)),
                        range=range_val,
                        showgrid=False,
                        zeroline=True,
                        zerolinecolor='grey',
                        zerolinewidth=2,
                        tickformat=".0%",
                        dtick=0.2,
                        tickfont=dict(color='black')
                    ),
                    yaxis=dict(
                        title=dict(text="2024 GOP Win Margin (GOP % - DEM %)", font=dict(color='black', size=14)),
                        range=range_val,
                        showgrid=False,
                        zeroline=True,
                        zerolinecolor='grey',
                        zerolinewidth=2,
                        tickformat=".0%",
                        dtick=0.2,
                        tickfont=dict(color='black')
                    ),
                    legend_title_text='2024 County Winner',
                    legend=dict(
                        title=dict(font=dict(color='black', size=18)),
                        font=dict(color='black')
                    ),
                    hovermode="closest"
                )

                st.plotly_chart(fig, use_container_width=True)


    except Exception as e:
        st.exception(e)

# -------------------------
# Tab 3: Placeholder for visualization 3
# -------------------------
# -------------------------
# Tab 3: Global Energy, CO₂ Emissions & GDP Explorer
# -------------------------
with tab3:
    from visualization3_dark import run_visualization_3  # optional if kept in a separate file
    run_visualization_3()
