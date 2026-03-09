# Equilibrium

> An intelligent enclosure controller for maintaining optimal environmental conditions — monitoring air quality, temperature, and humidity in real time and responding autonomously through a coordinated three-fan filtration and exhaust system.

---

## Overview

Equilibrium is an embedded systems project built around the **Adafruit Feather RP2040**, designed to continuously monitor and regulate the internal environment of a sealed enclosure. It reads VOC/eCO2 levels, temperature, and humidity from dedicated sensors, then drives three 24V fans proportionally based on those readings to maintain clean, stable air conditions.

All live sensor data and fan statuses are surfaced on an onboard **SH1107 OLED display** with rotating pages, and all three fans are monitored via tachometer feedback for real-time fault detection.

The project is written entirely in **CircuitPython** and runs as a single unified `main.py` on boot.

---

## Goals

- Maintain safe VOC and eCO2 levels inside the enclosure through active filtration
- Regulate internal temperature and humidity through proportional exhaust ventilation
- Provide real-time environmental feedback on an embedded display
- Detect fan failures automatically and surface fault warnings
- Keep the codebase readable, tunable, and easy to extend

---

## Hardware

| Component | Description | Role |
|---|---|---|
| Adafruit Feather RP2040 | Microcontroller — CircuitPython | Central controller |
| SGP30 | VOC / eCO2 sensor (I2C) | Drives filtration fan speed |
| SHT45 | Temperature & humidity sensor (I2C) | Drives exhaust fan speed |
| SH1107 128×64 OLED | Monochrome I2C display | Live readout — rotating pages |
| 2× 24V filtration fans | Bento box intake/filter fans | Pull air through filtration media |
| 1× 24V P12 exhaust fan | Enclosure exhaust fan | Expels conditioned air |
| 3× Logic-level N-MOSFET | e.g. IRL540N or IRLZ44N | PWM-switch 24V GND path per fan |
| 3× 10kΩ resistors | Pull-ups for tachometer lines | Tach signal conditioning |
| 24V DC power supply | Powers all three fans | Fan power rail |

> **Note:** The Feather RP2040 operates at 3.3V logic. All three fans are switched via logic-level MOSFETs — the Feather PWM pins drive the MOSFET gates, which switch the 24V ground path for each fan. The 24V supply connects directly to each fan's positive terminal.

---

## Software Setup

### Requirements

CircuitPython 8.x or later installed on the Feather RP2040.

### Libraries

Copy the following into the `/lib` folder on the `CIRCUITPY` drive:

| Library | Source |
|---|---|
| `adafruit_sgp30.mpy` | Adafruit CircuitPython SGP30 |
| `adafruit_sht4x.mpy` | Adafruit CircuitPython SHT4x |
| `adafruit_displayio_sh1107.mpy` | Adafruit CircuitPython DisplayIO SH1107 |
| `adafruit_display_text/` | Adafruit CircuitPython Display Text |
| `adafruit_bus_device/` | Adafruit CircuitPython BusDevice |

All libraries are available via the [Adafruit CircuitPython Bundle](https://circuitpython.org/libraries).

### Installation

1. Flash CircuitPython onto the Feather RP2040 via the UF2 bootloader
2. Copy the required libraries into `/lib` on the `CIRCUITPY` drive
3. Copy `main.py` to the root of the `CIRCUITPY` drive
4. The controller starts automatically on power-up

---

## Pin Reference

| Signal | Feather Pin | Notes |
|---|---|---|
| Filtration Fan 1 PWM | `D5` | To MOSFET gate |
| Filtration Fan 2 PWM | `D6` | To MOSFET gate |
| Filtration Fan 1 Tach | `D9` | 10kΩ pull-up to 3.3V |
| Filtration Fan 2 Tach | `D10` | 10kΩ pull-up to 3.3V |
| Exhaust Fan PWM | `D11` | To MOSFET gate |
| Exhaust Fan Tach | `D12` | 10kΩ pull-up to 3.3V |
| I2C SDA | `SDA` | Shared — SGP30, SHT45, OLED |
| I2C SCL | `SCL` | Shared — SGP30, SHT45, OLED |

All three I2C devices share the same SDA/SCL bus. Ensure each device has a unique I2C address (SGP30: `0x58`, SHT45: `0x44`, SH1107: `0x3C`).

---

## Control Logic

### Filtration Fans (SGP30 → Fan Speed)

The two filtration fans are controlled proportionally by the **TVOC reading** from the SGP30 sensor. As VOC concentration rises, the fans spin faster to pull more air through the filtration media.

```
TVOC ≤   0 ppb  →  fans at minimum speed (~25%)
TVOC = 500 ppb  →  fans at full speed (100%)
Between          →  smooth linear ramp
```

The SGP30 runs a **15-second warm-up routine** on boot before VOC readings are trusted. During this period the fans hold at minimum speed and the OLED displays a warm-up notice.

### Exhaust Fan (SHT45 → Fan Speed)

The P12 exhaust fan is controlled by a **weighted combination** of temperature and humidity readings from the SHT45, each contributing 50% to the final speed. This allows the fan to respond meaningfully to either condition independently, or amplify its response when both are elevated simultaneously.

```
Temp  < 23°C  AND  Humidity < 45%RH  →  fan OFF
Temp  = 25°C  OR   Humidity = 50%RH  →  fan at minimum speed
Temp  = 40°C  OR   Humidity = 80%RH  →  fan at full speed
Between                               →  smooth proportional ramp
```

Both thresholds and weights are tunable constants at the top of `main.py`.

### Fault Detection

All three fans report RPM via tachometer feedback. After each sensor update cycle, the controller samples each tachometer and compares the measured RPM against a minimum threshold (default: 200 RPM). If a fan that should be spinning reads below this threshold, a fault flag is set and displayed on the OLED fan status page.

### OLED Display

The SH1107 cycles through three pages every 4 seconds:

| Page | Content |
|---|---|
| **Environment** | Live temperature (°C) and humidity (%RH) |
| **Air Quality** | Live TVOC (ppb) and eCO2 (ppm) |
| **Fans** | Speed % for all three fans, fault flags where applicable |

---

## Tuning

All configurable thresholds are defined as named constants at the top of `main.py` and can be adjusted without modifying any logic:

```python
TVOC_MIN         = 0      # ppb — filtration fans start ramping
TVOC_MAX         = 500    # ppb — filtration fans at full speed
TEMP_MIN         = 25.0   # °C  — exhaust starts ramping
TEMP_MAX         = 40.0   # °C  — exhaust at full speed
HUMID_MIN        = 50.0   # %RH — exhaust starts ramping
HUMID_MAX        = 80.0   # %RH — exhaust at full speed
TEMP_WEIGHT      = 0.5    # temp contribution to exhaust speed
HUMID_WEIGHT     = 0.5    # humidity contribution to exhaust speed
PAGE_INTERVAL    = 4.0    # seconds per OLED page
SENSOR_INTERVAL  = 4.0    # seconds between sensor reads
```

---

## Project Structure

```
CIRCUITPY/
├── main.py          # Unified controller — runs on boot
└── lib/
    ├── adafruit_sgp30.mpy
    ├── adafruit_sht4x.mpy
    ├── adafruit_displayio_sh1107.mpy
    ├── adafruit_display_text/
    └── adafruit_bus_device/
```

---

## License

MIT License — free to use, modify, and build upon.
