import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def get_data(emission_api_token):
    response = requests.get(
        "https://api.electricitymap.org/v3/carbon-intensity/history?zone=US-NY-NYIS",
        headers={
            "auth-token": emission_api_token
        }
    )
    data = response.json()

    carbon_intensity_vector = []
    for item in data['history']:
        carbon_intensity_vector.append(item['carbonIntensity'])

    # Define the time range: past 24 hours
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=24)

    # NYISO real-time LBMP data URL (data for the past 7 days)
    base_url = "http://mis.nyiso.com/public/csv/realtime/"

    # Initialize an empty DataFrame to store the data
    all_data = pd.DataFrame()

    # Loop through the past 2 days to ensure we cover the full 24-hour range
    for i in range(2):
        date = (start_time + timedelta(days=i)).strftime("%Y%m%d")
        file_url = f"{base_url}{date}realtime_zone.csv"
        
        try:
            # Read the CSV file for the specific date
            daily_data = pd.read_csv(file_url)
            
            # Append to the main DataFrame
            all_data = pd.concat([all_data, daily_data], ignore_index=True)
        except Exception as e:
            print(f"Could not retrieve data for {date}: {e}")

    # Convert the 'Time Stamp' column to datetime
    all_data['Time Stamp'] = pd.to_datetime(all_data['Time Stamp'])

    # Filter data for the 'New York City' zone and the desired time range
    nyc_data = all_data[
        (all_data['Name'] == 'N.Y.C.') &
        (all_data['Time Stamp'] >= start_time) &
        (all_data['Time Stamp'] <= end_time)
    ]

    # Select only the numeric columns along with 'Time Stamp'
    numeric_columns = ['Time Stamp', 'LBMP ($/MWHr)']

    # Drop rows with missing or non-numeric 'LBMP ($/MWHr)' values
    nyc_data = nyc_data[numeric_columns].dropna()

    # Ensure 'LBMP ($/MWHr)' is of numeric type
    nyc_data['LBMP ($/MWHr)'] = pd.to_numeric(nyc_data['LBMP ($/MWHr)'], errors='coerce')

    # Resample to hourly intervals by taking the mean of the 5-minute intervals
    nyc_hourly = nyc_data.resample('h', on='Time Stamp').mean()

    # Reset index to have 'Time Stamp' as a column
    nyc_hourly.reset_index(inplace=True)

    nyc_hourly['LBMP ($/MWHr)'] /= 1000
    electricity_price_vector = nyc_hourly['LBMP ($/MWHr)'].to_numpy()
    
    
    return np.array(carbon_intensity_vector), np.array(electricity_price_vector)