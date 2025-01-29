import numpy as np
from datetime import datetime, timedelta

def pred(soc: float, dt: datetime, battery_capacity: float, charging_rate: float,
         forecasted_24) -> tuple[np.ndarray, float]:
    """
    Calculate cost and emission savings for different EV charging start times.
    
    Args:
        soc: Current state of charge (percentage)
        dt: Departure time (datetime object)
        battery_capacity: Battery capacity in kWh
        charging_rate: Charging rate in kW
        forecasted_24: forecast of price and emission for the next 24 hours (shape: (24, 2))
                      where columns are [price, emission]
    
    Returns:
        tuple containing:
            - numpy array with cost and emission savings for each possible start hour
            - float: hours needed to charge
    """
    # Calculate energy needed to fully charge
    energy_needed = battery_capacity * (100 - soc) / 100  # kWh
    
    # Calculate hours needed to charge
    hours_to_charge = energy_needed / charging_rate
    
    # Calculate how many hours until departure
    now = datetime.now()
    hours_until_departure = (dt - now).total_seconds() / 3600
    
    # Maximum number of hours we can delay charging while still finishing before departure
    max_delay_hours = int(hours_until_departure - hours_to_charge)
    
    if max_delay_hours < 0:
        raise ValueError("Not enough time to charge before departure!")
    
    # Calculate baseline cost and emissions (starting now)
    baseline_cost = 0
    baseline_emissions = 0
    hours_charging = int(np.ceil(hours_to_charge))
    
    for hour in range(hours_charging):
        baseline_cost += forecasted_24[hour][0] * charging_rate
        baseline_emissions += forecasted_24[hour][1] * charging_rate
    
    # Initialize arrays to store savings
    num_scenarios = min(24, max_delay_hours + 1)  # Can't delay more than 24 hours
    savings = np.zeros(2 * num_scenarios)  # First half for cost savings, second half for emission savings
    
    # Calculate savings for each possible delay
    for delay in range(num_scenarios):
        delayed_cost = 0
        delayed_emissions = 0
        
        # Calculate cost and emissions for delayed start
        for hour in range(hours_charging):
            if delay + hour >= 24:  # Don't access beyond forecasted data
                break
            delayed_cost += forecasted_24[delay + hour][0] * charging_rate
            delayed_emissions += forecasted_24[delay + hour][1] * charging_rate
        
        # Calculate and store savings
        savings[delay] = baseline_cost - delayed_cost  # Cost savings
        savings[delay + num_scenarios] = baseline_emissions - delayed_emissions  # Emission savings
    
    return savings, hours_to_charge