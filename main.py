# === Combined Sensor Reading + SoC Estimation using XGBoost ===
import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from w1thermsensor import W1ThermSensor
import pandas as pd
import joblib
import os
import xgboost as xgb
import RPi.GPIO as GPIO
from RPLCD import CharLCD

# === Load XGBoost model and scaler ===
model = joblib.load("/home/amber/Downloads/soc_predictor_xgb.pkl")
scaler = joblib.load("/home/amber/Downloads/scaler.pkl")

# === I2C and ADC Setup ===
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
ads.gain = 1

# === Sensor Channel Assignments ===
current_channel = AnalogIn(ads, ADS.P0)
voltage_channel = AnalogIn(ads, ADS.P1)
temp_sensor = W1ThermSensor()

# === Constants ===
V_REF = 2.570
SENSITIVITY = 0.066
VOLTAGE_DIVIDER_RATIO = 8.2

# === LCD Setup ===
lcd = CharLCD(cols=16, rows=2, pin_rs=26, pin_e=19, pins_data=[13, 6, 5, 11], numbering_mode=GPIO.BCM)

with open("/home/amber/log.txt", "a") as f:
    f.write(f"Script started at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

# === Data Logging File ===
log_file = "ev_sensor_log.csv"
if not os.path.exists(log_file):
    pd.DataFrame(columns=["Timestamp", "Voltage (V)", "Current (A)", "Temperature (°C)", "Predicted SoC (%)"]).to_csv(log_file, index=False)

while True:
    try:
        # === Sensor Readings ===
        sensor_voltage = current_channel.voltage
        current = (sensor_voltage - V_REF) / SENSITIVITY

        adc_voltage = voltage_channel.voltage
        battery_voltage = adc_voltage * VOLTAGE_DIVIDER_RATIO

        temperature = temp_sensor.get_temperature()

        # === Prepare Input for Model ===
        input_df = pd.DataFrame([{
            "Voltage (V)": battery_voltage,
            "Current (A)": current,
            "Temperature (°C)": temperature
        }])

        input_scaled = scaler.transform(input_df)
        soc = model.predict(input_scaled)[0]
        soc = max(0, min(100, soc))  # Clamp between 0-100%

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        # === Logging ===
        log_entry = pd.DataFrame([{
            "Timestamp": timestamp,
            "Voltage (V)": round(battery_voltage, 2),
            "Current (A)": round(current, 2),
            "Temperature (°C)": round(temperature, 2),
            "Predicted SoC (%)": round(soc, 2)
        }])
        log_entry.to_csv(log_file, mode="a", header=False, index=False)

        # === LCD Output ===
        lcd.clear()
        lcd.write_string(f"SOC:{soc:.1f}%")
        lcd.crlf()
        lcd.write_string(f"V:{battery_voltage:.1f} I:{current:.1f}")

        # === Console Output ===
        print(f"{timestamp} | Voltage: {battery_voltage:.2f}V | Current: {current:.2f}A | Temp: {temperature:.2f}°C | SoC: {soc:.2f}%")
        time.sleep(1)

    except Exception as e:
        print("Error:", e)
        time.sleep(5)
