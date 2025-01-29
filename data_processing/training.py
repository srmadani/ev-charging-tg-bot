
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import datetime
import os
from tensorflow.keras.models import load_model
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, RepeatVector, TimeDistributed
from tensorflow.keras.optimizers import Adam

# ---------------------------
# 1) Model Training Function
# ---------------------------

def train_lstm_model(
    csv_file_path: str,
    history_length: int = 24,
    forecast_horizon: int = 24,
    feature_cols = ["price", "emission"],
    epochs: int = 10,
    batch_size: int = 32
):
    """
    Trains a seq2seq LSTM model on the given CSV file data.
    Returns the trained Keras model.
    """
    # 1.1) Read data
    df = pd.read_csv(csv_file_path, parse_dates=["time"])
    df = df.sort_values("time").reset_index(drop=True)

    # 1.2) Extract relevant columns
    data = df[feature_cols].values  # shape: (N, 2) -> columns: [price, emission]

    # 1.3) Create sequences (sliding windows)
    X, Y = create_sequences(data, history_length, forecast_horizon)

    # 1.4) Train/Validation Split
    train_size = int(0.8 * len(X))
    X_train, Y_train = X[:train_size], Y[:train_size]
    X_val,   Y_val   = X[train_size:], Y[train_size:]

    # 1.5) Build Model
    model = Sequential()
    # Encoder
    model.add(LSTM(64, activation='relu', input_shape=(history_length, len(feature_cols))))
    # Repeat final state
    model.add(RepeatVector(forecast_horizon))
    # Decoder
    model.add(LSTM(64, activation='relu', return_sequences=True))
    # Output: forecast for each of the 24 future steps, 2 features
    model.add(TimeDistributed(Dense(len(feature_cols))))

    model.compile(optimizer=Adam(learning_rate=0.001), loss='mse')
    model.summary()

    # 1.6) Train
    history = model.fit(
        X_train, Y_train,
        epochs=epochs,
        batch_size=batch_size,
        validation_data=(X_val, Y_val),
        verbose=1
    )

    # Optional: plot training history
    plt.figure()
    plt.plot(history.history['loss'], label='Train Loss')
    plt.plot(history.history['val_loss'], label='Val Loss')
    plt.legend()
    plt.title('Training History')
    plt.show()

    return model


# Helper function to create supervised sequences
def create_sequences(data: np.ndarray, history=24, forecast=24):
    """
    data: shape (N, num_features)
    returns:
      X: (samples, history, num_features)
      Y: (samples, forecast, num_features)
    """
    X, Y = [], []
    for i in range(len(data) - history - forecast + 1):
        X.append(data[i : i + history])
        Y.append(data[i + history : i + history + forecast])
    return np.array(X), np.array(Y)


# ----------------------------------
# 2) Prediction (Inference) Function
# ----------------------------------

# Assume we have a global (or class-level) model.
# We will set this up after training.
MODEL = None

def forecast(
    carbon_intensity_vector: np.ndarray,
    electricity_price_vector: np.ndarray
) -> tuple[np.ndarray, float]:
    """
    Given a datetime `dt` (e.g., 8:31 PM),
    the past 24 hours of carbon_intensity_vector and electricity_price_vector,
    returns a tuple (predicted_24h, avg_price_over_forecast).

    predicted_24h: np.ndarray of shape (24, 2), columns [price, emission]
    avg_price_over_forecast: float (average predicted price over next 24h)
    """

    # 2.1) Combine the two input features into shape (1, 24, 2)
    # The user provides carbon_intensity_vector (24,) and electricity_price_vector (24,)
    # We'll stack them column-wise.
    if len(carbon_intensity_vector) != 24 or len(electricity_price_vector) != 24:
        raise ValueError("Expecting 24 elements in each vector (past 24 hours).")

    # shape (24, 2)
    past_24_data = np.column_stack((electricity_price_vector, carbon_intensity_vector))

    # shape (1, 24, 2)
    input_data = np.expand_dims(past_24_data, axis=0)

    # 2.2) Predict with the global model
    if MODEL is None:
        raise ValueError("Global MODEL is not initialized. Train or load the model first.")

    prediction = MODEL.predict(input_data)  # shape (1, 24, 2)
    prediction_24 = prediction[0]          # shape (24, 2)

    # 2.3) Suppose we want to return the average price over next 24 hours
    prices_24 = prediction_24[:, 0]
    avg_price = float(np.mean(prices_24))

    return prediction_24, avg_price

def get_forecasts(electricity_price_vector, carbon_intensity_vector):
    MODEL_PATH = "data_processing/trained_model.h5"
    MODEL = load_model(MODEL_PATH)
    print(f"electricity_price_vector: {electricity_price_vector}")
    print(f"carbon_intensity_vector: {carbon_intensity_vector}")
    past_24_data = np.column_stack((electricity_price_vector[0:24], carbon_intensity_vector))
    input_data = np.expand_dims(past_24_data, axis=0)
    prediction = MODEL.predict(input_data)
    return prediction[0] 
# -----------------------
# 3) Main (Train & Demo)
# -----------------------

if __name__ == "__main__":

    MODEL_PATH = "trained_model.h5"
    if os.path.exists(MODEL_PATH):
        MODEL = load_model(MODEL_PATH)
    else:
        csv_path = "combined_electricity_data_hourly.csv"
        trained_model = train_lstm_model(
            csv_file_path=csv_path,
            history_length=24,
            forecast_horizon=24,
            feature_cols=["price", "emission"],
            epochs=100,
            batch_size=32
        )
        MODEL = trained_model
        MODEL.save(MODEL_PATH)

    now = datetime.datetime(2024, 1, 1, 20, 31)
    example_price_vector = np.random.rand(24) * 0.15
    example_emission_vector = np.random.rand(24) * 300
    forecasted_24, average_price = forecast(
        carbon_intensity_vector=example_emission_vector,
        electricity_price_vector=example_price_vector
    )
    print("=== Forecast for Next 24 Hours ===")
    print("Shape of forecasted data:", forecasted_24.shape)
    print("First few predictions [price, emission]:\n", forecasted_24[:5])
    print("Average forecasted price over next 24h:", average_price)
