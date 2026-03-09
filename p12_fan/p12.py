# exhaust_fan.py — CircuitPython for Adafruit Feather RP2040
# One P12 24V exhaust fan controlled proportionally by SHT45 temp + humidity
# Includes tachometer fault detection

import board
import busio
import pwmio
import countio
import time
import adafruit_sht4x

# ── Configuration ──────────────────────────────────────────────────────────────

# Temperature thresholds (°C)
TEMP_MIN        = 25.0   # °C — fan starts responding above this
TEMP_MAX        = 40.0   # °C — fan at full speed at this temp

# Humidity thresholds (%RH)
HUMID_MIN       = 50.0   # %RH — fan starts responding above this
HUMID_MAX       = 80.0   # %RH — fan at full speed at this humidity

# How much each sensor contributes to final fan speed (must add to 1.0)
TEMP_WEIGHT     = 0.5    # 50% influence from temperature
HUMID_WEIGHT    = 0.5    # 50% influence from humidity

# Fan PWM
FAN_MIN_DUTY    = 16384  # ~25% — minimum speed to keep fan spinning
FAN_MAX_DUTY    = 65535  # 100% full speed
FAN_OFF_DUTY    = 0      # fully off
PWM_FREQ        = 25000  # 25 kHz standard

# Below both of these → fan turns fully off (enclosure is comfortable)
TEMP_OFF_BELOW  = 23.0   # °C
HUMID_OFF_BELOW = 45.0   # %RH

# Tachometer
TACH_PULSES_PER_REV = 2
TACH_SAMPLE_TIME    = 2.0   # seconds
MIN_RPM             = 200   # below this = fault

# Loop timing
UPDATE_INTERVAL = 4.0   # seconds between sensor reads

# ── Pin assignments ────────────────────────────────────────────────────────────
FAN_PWM_PIN  = board.D11   # PWM out → MOSFET gate → switches 24V GND
FAN_TACH_PIN = board.D12   # Tachometer input (10kΩ pull-up to 3.3V)

I2C_SDA = board.SDA
I2C_SCL = board.SCL

# ── Setup ──────────────────────────────────────────────────────────────────────
i2c   = busio.I2C(I2C_SCL, I2C_SDA)
sht   = adafruit_sht4x.SHT4x(i2c)
sht.mode = adafruit_sht4x.Mode.NOHEAT_HIGHPRECISION  # high precision, no heater

fan   = pwmio.PWMOut(FAN_PWM_PIN, frequency=PWM_FREQ, duty_cycle=FAN_OFF_DUTY)
tach  = countio.Counter(FAN_TACH_PIN, edge=countio.Edge.RISE)

# ── Helpers ────────────────────────────────────────────────────────────────────
def normalize(value, v_min, v_max):
    """Map a value to 0.0–1.0 within a min/max range, clamped."""
    ratio = (value - v_min) / (v_max - v_min)
    return max(0.0, min(1.0, ratio))

def compute_duty(temp, humidity):
    """
    Combine temp + humidity into a single proportional duty cycle.
    If both readings are below their off thresholds, fan turns off.
    """
    if temp < TEMP_OFF_BELOW and humidity < HUMID_OFF_BELOW:
        return FAN_OFF_DUTY

    temp_ratio  = normalize(temp,     TEMP_MIN,  TEMP_MAX)
    humid_ratio = normalize(humidity, HUMID_MIN, HUMID_MAX)

    combined = (temp_ratio * TEMP_WEIGHT) + (humid_ratio * HUMID_WEIGHT)
    duty = int(FAN_MIN_DUTY + combined * (FAN_MAX_DUTY - FAN_MIN_DUTY))
    return max(FAN_MIN_DUTY, min(FAN_MAX_DUTY, duty))

def measure_rpm():
    """Sample tachometer pulses over TACH_SAMPLE_TIME and return RPM."""
    tach.reset()
    time.sleep(TACH_SAMPLE_TIME)
    pulses = tach.count
    return (pulses / TACH_PULSES_PER_REV) * (60.0 / TACH_SAMPLE_TIME)

def check_fault(duty):
    """Warn if fan RPM is too low while fan should be running."""
    if duty == FAN_OFF_DUTY:
        print("  Fan: OFF")
        return
    rpm = measure_rpm()
    print(f"  Fan RPM: {rpm:.0f}")
    if rpm < MIN_RPM:
        print("  ⚠️  FAULT: Exhaust fan RPM too low — check wiring or fan!")

def fan_state_label(duty):
    if duty == FAN_OFF_DUTY:
        return "OFF"
    pct = (duty / FAN_MAX_DUTY) * 100
    return f"{pct:.1f}% speed"

# ── Main loop ──────────────────────────────────────────────────────────────────
print("Exhaust fan controller starting...")
print(f"  Temp range  : {TEMP_OFF_BELOW}°C idle → {TEMP_MIN}°C min → {TEMP_MAX}°C full")
print(f"  Humid range : {HUMID_OFF_BELOW}%RH idle → {HUMID_MIN}%RH min → {HUMID_MAX}%RH full")
print(f"  Weights     : Temp {TEMP_WEIGHT*100:.0f}% / Humidity {HUMID_WEIGHT*100:.0f}%\n")

while True:
    temp, humidity = sht.measurements   # returns (°C, %RH)
    duty = compute_duty(temp, humidity)
    fan.duty_cycle = duty

    print(f"Temp: {temp:.1f}°C  |  Humidity: {humidity:.1f}%RH  |  Exhaust: {fan_state_label(duty)}")
    check_fault(duty)
    print()

    time.sleep(UPDATE_INTERVAL)
