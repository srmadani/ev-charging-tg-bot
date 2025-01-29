import pandas as pd

# Load the data files
lbmp_file = "OASIS_Real_Time_Dispatch_Zonal_LBMP.csv"
emission_file = "US-NY-NYIS_2024_hourly.csv"

# Load the data into DataFrames
lbmp_df = pd.read_csv(lbmp_file, parse_dates=['RTD End Time Stamp'])
emission_df = pd.read_csv(emission_file, parse_dates=['Datetime (UTC)'])

# Select required columns and rename for clarity
lbmp_df = lbmp_df[['RTD End Time Stamp', 'RTD Zonal LBMP']]
lbmp_df.rename(columns={'RTD End Time Stamp': 'time', 'RTD Zonal LBMP': 'price'}, inplace=True)
lbmp_df['price'] = lbmp_df['price'] / 1000  # Convert $/MWh to $/kWh
lbmp_df['price'] = lbmp_df['price'] * 4.24  # Approximate residential rate multiplier
""""
To approximate residential electricity prices in New York City based on wholesale market rates, it's essential to understand the relationship between wholesale and retail pricing. Residential rates encompass additional costs beyond the wholesale price, including transmission, distribution, maintenance, administrative expenses, and taxes.

Wholesale vs. Residential Rates:

Wholesale Prices: In November 2024, the average wholesale electricity price in New York was approximately $64.21 per megawatt-hour (MWh), equating to about 6.42 cents per kilowatt-hour (kWh). 
EIA.GOV

Residential Prices: As of December 2024, New York area households paid an average of 27.2 cents per kWh. 
BLS.GOV

Calculating the Multiplier:

By comparing these figures, the multiplier between wholesale and residential rates is approximately:

Multiplier
=
Residential Rate
Wholesale Rate
=
27.2
 
cents/kWh
6.42
 
cents/kWh
≈
4.24
Multiplier= 
Wholesale Rate
Residential Rate
​
 = 
6.42cents/kWh
27.2cents/kWh
​
 ≈4.24
"""

emission_df = emission_df[['Datetime (UTC)', 'Carbon Intensity gCO₂eq/kWh (LCA)']]
emission_df.rename(columns={'Datetime (UTC)': 'time', 'Carbon Intensity gCO₂eq/kWh (LCA)': 'emission'}, inplace=True)

# Resample lbmp_df to hourly, taking the mean price for each hour
lbmp_df.set_index('time', inplace=True)
lbmp_df = lbmp_df.resample('H').mean().reset_index()

# Merge the data on time, using an inner join to match overlapping timestamps
merged_df = pd.merge_asof(
    lbmp_df.sort_values('time'), 
    emission_df.sort_values('time'), 
    on='time', 
    direction='backward'  # Match the most recent prior emission data for each price entry
)

merged_df['price'] = merged_df['price'].fillna(method='ffill')  # forward fill

# Save or display the resulting DataFrame
print(merged_df.head())

# Optionally save to a new CSV
merged_df.to_csv("combined_electricity_data_hourly.csv", index=False)
