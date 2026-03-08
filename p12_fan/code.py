import board
import pwmio
import time
import busio
import adafruit_sht4x

# I2C and temperature sensor
i2c = board.STEMMA_I2C()
sht = adafruit_sht4x.SHT4x(i2c)

# P12 Pro PWM fan on GPIO 5 — 25kHz standard PC fan frequency
fan = pwmio.PWMOut(board.D5, frequency=25000, duty_cycle=0)

# Thresholds — adjust to your enclosure
TEMP_MIN = 25.0   # C — fan starts here
TEMP_MAX = 40.0   # C — fan hits 100% here
FAN_MIN  = 30     # % — minimum speed before stall

def set_fan_percent(pct):
    fan.duty_cycle = int(max(0, min(100, pct)) / 100 * 65535)

def temp_to_fan_speed(temp):
    if temp <= TEMP_MIN:
        return 0
    if temp >= TEMP_MAX:
        return 100
    pct = (temp - TEMP_MIN) / (TEMP_MAX - TEMP_MIN) * 100
    return max(FAN_MIN, pct)

while True:
    temp, humidity = sht.measurements
    speed = temp_to_fan_speed(temp)
    set_fan_percent(speed)
    print(f"Temp: {temp:.1f}C  Humidity: {humidity:.0f}%  Fan: {speed:.0f}%")
    time.sleep(3)
```

5. Scroll down and click **Commit new file**

---

## Step 3 — Add a README for p12_fan
1. Click **Add file** → **Create new file**
2. Name it `p12_fan/README.md`
3. Paste this:
```
# P12 Fan Control

Controls the Arctic P12 Pro 120mm PWM fan based on temperature.

## Hardware
- Adafruit Feather RP2040
- Arctic P12 Pro fan
- IRF520 MOSFET module
- LM2596 Buck converter (12V)
- Adafruit SHT45 temperature sensor

## Wiring
- Fan PWM blue wire → GPIO 5
- Fan yellow 12V → IRF520 Motor+ output
- IRF520 SIG → GPIO 5
- Buck converter set to 12V

## Libraries needed
- adafruit_sht4x
```

4. Click **Commit new file**

---

Your repo will look like this:
```
air-filtration-monitor/
├── README.md
├── p12_fan/
│   ├── code.py
│   └── README.md
├── sensors/          ← add later
└── filtration_fans/  ← add later
