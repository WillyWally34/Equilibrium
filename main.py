# main.py — CircuitPython for Adafruit Feather RP2040
# Bento Box Enclosure Controller — Unified Script
#
# Hardware:
#   - 2x 24V filtration fans  (VOC-proportional, SGP30)
#   - 1x P12 24V exhaust fan  (temp + humidity proportional, SHT45)
#   - SGP30  VOC/eCO2 sensor  (I2C)
#   - SHT45  temp/humidity    (I2C)
#   - SH1107 128x64 OLED      (I2C) — rotating pages
#   - Tachometer fault detection on all 3 fans
#
# Required libraries in /lib:
#   adafruit_sgp30.mpy
#   adafruit_sht4x.mpy
#   adafruit_displayio_sh1107.mpy
#   adafruit_display_text (folder)
#   adafruit_bitmap_font (folder)  [optional, falls back to built-in]

import board
import busio
import pwmio
import countio
import displayio
import terminalio
import time
import adafruit_sgp30
import adafruit_sht4x
import adafruit_displayio_sh1107
from adafruit_display_text import label

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

# ── Filtration fans (SGP30 TVOC → fan speed) ──────────────────────────────────
TVOC_MIN            = 0       # ppb — fans at minimum below this
TVOC_MAX            = 500     # ppb — fans at full speed at/above this

# ── Exhaust fan (SHT45 temp + humidity → fan speed) ───────────────────────────
TEMP_MIN            = 25.0    # °C  — exhaust starts ramping up
TEMP_MAX            = 40.0    # °C  — exhaust at full speed
HUMID_MIN           = 50.0    # %RH — exhaust starts ramping up
HUMID_MAX           = 80.0    # %RH — exhaust at full speed
TEMP_OFF_BELOW      = 23.0    # °C  — below this AND humidity off → fan off
HUMID_OFF_BELOW     = 45.0    # %RH — below this AND temp off → fan off
TEMP_WEIGHT         = 0.5     # contribution of temp  to exhaust speed (0.0–1.0)
HUMID_WEIGHT        = 0.5     # contribution of humid to exhaust speed (0.0–1.0)

# ── PWM ───────────────────────────────────────────────────────────────────────
PWM_FREQ            = 25000   # Hz
FAN_OFF_DUTY        = 0
FAN_MIN_DUTY        = 16384   # ~25% — minimum to keep fans spinning
FAN_MAX_DUTY        = 65535   # 100%

# ── Tachometers ───────────────────────────────────────────────────────────────
TACH_PULSES_PER_REV = 2
TACH_SAMPLE_TIME    = 1.5     # seconds — kept short so loop stays responsive
MIN_RPM             = 200     # below this while spinning = fault

# ── Timing ────────────────────────────────────────────────────────────────────
SENSOR_INTERVAL     = 4.0     # seconds between full sensor + fan updates
PAGE_INTERVAL       = 4.0     # seconds per OLED page
SGP30_WARMUP_SECS   = 15      # SGP30 needs ~15s before readings are reliable

# ── OLED ──────────────────────────────────────────────────────────────────────
DISPLAY_WIDTH       = 128
DISPLAY_HEIGHT      = 64
OLED_ROTATION       = 0       # degrees: 0 or 180

# ══════════════════════════════════════════════════════════════════════════════
#  PIN ASSIGNMENTS
# ══════════════════════════════════════════════════════════════════════════════

# Filtration fans (PWM → MOSFET gate → 24V GND switched)
FILT_FAN1_PWM  = board.D5
FILT_FAN2_PWM  = board.D6
FILT_FAN1_TACH = board.D9
FILT_FAN2_TACH = board.D10

# Exhaust fan
EXH_FAN_PWM    = board.D11
EXH_FAN_TACH   = board.D12

# I2C (SDA/SCL shared by all three I2C devices)
I2C_SDA        = board.SDA
I2C_SCL        = board.SCL

# ══════════════════════════════════════════════════════════════════════════════
#  HARDWARE INIT
# ══════════════════════════════════════════════════════════════════════════════

i2c = busio.I2C(I2C_SCL, I2C_SDA)

# Sensors
sgp = adafruit_sgp30.Adafruit_SGP30(i2c)
sgp.iaq_init()
sgp.set_iaq_baseline(0x8973, 0x8AAE)  # replace with your saved baseline if available

sht = adafruit_sht4x.SHT4x(i2c)
sht.mode = adafruit_sht4x.Mode.NOHEAT_HIGHPRECISION

# Fans — PWM output
filt_fan1 = pwmio.PWMOut(FILT_FAN1_PWM, frequency=PWM_FREQ, duty_cycle=FAN_MIN_DUTY)
filt_fan2 = pwmio.PWMOut(FILT_FAN2_PWM, frequency=PWM_FREQ, duty_cycle=FAN_MIN_DUTY)
exh_fan   = pwmio.PWMOut(EXH_FAN_PWM,   frequency=PWM_FREQ, duty_cycle=FAN_OFF_DUTY)

# Fans — tachometer input (connect 10kΩ pull-up resistor to 3.3V on each tach pin)
tach_f1 = countio.Counter(FILT_FAN1_TACH, edge=countio.Edge.RISE)
tach_f2 = countio.Counter(FILT_FAN2_TACH, edge=countio.Edge.RISE)
tach_ex = countio.Counter(EXH_FAN_TACH,   edge=countio.Edge.RISE)

# OLED — SH1107 128x64
displayio.release_displays()
display_bus = displayio.I2CDisplay(i2c, device_address=0x3C)
display = adafruit_displayio_sh1107.SH1107(
    display_bus,
    width=DISPLAY_WIDTH,
    height=DISPLAY_HEIGHT,
    rotation=OLED_ROTATION
)

# ══════════════════════════════════════════════════════════════════════════════
#  SHARED STATE  (updated each sensor cycle, read by display)
# ══════════════════════════════════════════════════════════════════════════════
state = {
    "temp":       0.0,
    "humidity":   0.0,
    "tvoc":       0,
    "eco2":       0,
    "filt_pct":   0.0,
    "exh_pct":    0.0,
    "rpm_f1":     0.0,
    "rpm_f2":     0.0,
    "rpm_ex":     0.0,
    "fault_f1":   False,
    "fault_f2":   False,
    "fault_ex":   False,
    "warming_up": True,
}

# ══════════════════════════════════════════════════════════════════════════════
#  HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def normalize(value, v_min, v_max):
    return max(0.0, min(1.0, (value - v_min) / (v_max - v_min)))

def duty_to_pct(duty):
    return (duty / FAN_MAX_DUTY) * 100.0

def tvoc_to_duty(tvoc):
    ratio = normalize(tvoc, TVOC_MIN, TVOC_MAX)
    return int(FAN_MIN_DUTY + ratio * (FAN_MAX_DUTY - FAN_MIN_DUTY))

def exhaust_duty(temp, humidity):
    if temp < TEMP_OFF_BELOW and humidity < HUMID_OFF_BELOW:
        return FAN_OFF_DUTY
    t_ratio = normalize(temp,     TEMP_MIN,  TEMP_MAX)
    h_ratio = normalize(humidity, HUMID_MIN, HUMID_MAX)
    combined = (t_ratio * TEMP_WEIGHT) + (h_ratio * HUMID_WEIGHT)
    duty = int(FAN_MIN_DUTY + combined * (FAN_MAX_DUTY - FAN_MIN_DUTY))
    return max(FAN_MIN_DUTY, min(FAN_MAX_DUTY, duty))

def measure_rpm(counter):
    counter.reset()
    time.sleep(TACH_SAMPLE_TIME)
    return (counter.count / TACH_PULSES_PER_REV) * (60.0 / TACH_SAMPLE_TIME)

def fan_label(pct, fault):
    if pct < 1.0:
        return "OFF"
    tag = " !FLT" if fault else ""
    return f"{pct:.0f}%{tag}"

# ══════════════════════════════════════════════════════════════════════════════
#  OLED DISPLAY — ROTATING PAGES
# ══════════════════════════════════════════════════════════════════════════════

PAGES = ["env", "voc", "fans"]
current_page = 0
last_page_time = time.monotonic()

def make_text_group(lines):
    """
    Build a displayio Group from a list of (text, x, y, scale) tuples.
    Uses the built-in terminal font — no external font file needed.
    """
    group = displayio.Group()
    for (txt, x, y, scale) in lines:
        lbl = label.Label(
            terminalio.FONT,
            text=txt,
            color=0xFFFFFF,
            scale=scale,
            x=x,
            y=y
        )
        group.append(lbl)
    return group

def show_page_env(s):
    """Page 1 — Temperature & Humidity"""
    lines = [
        ("ENVIRONMENT",        4,  4, 1),
        (f"Temp",              4, 20, 1),
        (f"{s['temp']:.1f}C", 60, 20, 1),
        (f"Humid",             4, 34, 1),
        (f"{s['humidity']:.1f}%", 60, 34, 1),
    ]
    display.root_group = make_text_group(lines)

def show_page_voc(s):
    """Page 2 — VOC & eCO2"""
    lines = [
        ("AIR QUALITY",        4,  4, 1),
        ("TVOC",               4, 20, 1),
        (f"{s['tvoc']} ppb",  60, 20, 1),
        ("eCO2",               4, 34, 1),
        (f"{s['eco2']} ppm",  60, 34, 1),
        ("(warming up)" if s["warming_up"] else "", 4, 50, 1),
    ]
    display.root_group = make_text_group(lines)

def show_page_fans(s):
    """Page 3 — Fan speeds & fault status"""
    f1 = fan_label(s["filt_pct"], s["fault_f1"])
    f2 = fan_label(s["filt_pct"], s["fault_f2"])
    ex = fan_label(s["exh_pct"],  s["fault_ex"])
    lines = [
        ("FANS",       4,  4, 1),
        ("Filt 1",     4, 18, 1),
        (f1,          64, 18, 1),
        ("Filt 2",     4, 30, 1),
        (f2,          64, 30, 1),
        ("Exhaust",    4, 42, 1),
        (ex,          64, 42, 1),
    ]
    display.root_group = make_text_group(lines)

def refresh_display(s):
    if   current_page == 0: show_page_env(s)
    elif current_page == 1: show_page_voc(s)
    elif current_page == 2: show_page_fans(s)

# ══════════════════════════════════════════════════════════════════════════════
#  SGP30 WARM-UP
# ══════════════════════════════════════════════════════════════════════════════

print("SGP30 warming up...")
filt_fan1.duty_cycle = FAN_MIN_DUTY
filt_fan2.duty_cycle = FAN_MIN_DUTY

warmup_group = make_text_group([
    ("BENTO BOX",    10,  8, 1),
    ("CONTROLLER",   10, 22, 1),
    ("SGP30",        10, 38, 1),
    ("warming up..", 10, 52, 1),
])
display.root_group = warmup_group

for i in range(SGP30_WARMUP_SECS):
    _ = sgp.tvoc
    time.sleep(1)

state["warming_up"] = False
print("Warm-up complete. Running.\n")

# ══════════════════════════════════════════════════════════════════════════════
#  MAIN LOOP
# ══════════════════════════════════════════════════════════════════════════════

last_sensor_time = time.monotonic() - SENSOR_INTERVAL  # force immediate first read

while True:
    now = time.monotonic()

    # ── Page rotation ────────────────────────────────────────────────────────
    if now - last_page_time >= PAGE_INTERVAL:
        current_page = (current_page + 1) % len(PAGES)
        last_page_time = now
        refresh_display(state)

    # ── Sensor + fan update ──────────────────────────────────────────────────
    if now - last_sensor_time >= SENSOR_INTERVAL:
        last_sensor_time = now

        # Read sensors
        temp, humidity = sht.measurements
        tvoc = sgp.tvoc
        eco2 = sgp.eCO2

        # Compute duties
        filt_duty = tvoc_to_duty(tvoc)
        exh_duty  = exhaust_duty(temp, humidity)

        # Apply to fans
        filt_fan1.duty_cycle = filt_duty
        filt_fan2.duty_cycle = filt_duty
        exh_fan.duty_cycle   = exh_duty

        # Measure RPM + detect faults
        rpm_f1 = measure_rpm(tach_f1)
        rpm_f2 = measure_rpm(tach_f2)
        rpm_ex = measure_rpm(tach_ex)

        fault_f1 = filt_duty > FAN_OFF_DUTY and rpm_f1 < MIN_RPM
        fault_f2 = filt_duty > FAN_OFF_DUTY and rpm_f2 < MIN_RPM
        fault_ex = exh_duty  > FAN_OFF_DUTY and rpm_ex < MIN_RPM

        # Update shared state
        state.update({
            "temp":     temp,
            "humidity": humidity,
            "tvoc":     tvoc,
            "eco2":     eco2,
            "filt_pct": duty_to_pct(filt_duty),
            "exh_pct":  duty_to_pct(exh_duty),
            "rpm_f1":   rpm_f1,
            "rpm_f2":   rpm_f2,
            "rpm_ex":   rpm_ex,
            "fault_f1": fault_f1,
            "fault_f2": fault_f2,
            "fault_ex": fault_ex,
        })

        # Serial debug
        print(f"Temp: {temp:.1f}°C  Humidity: {humidity:.1f}%RH")
        print(f"TVOC: {tvoc} ppb  eCO2: {eco2} ppm")
        print(f"Filt fans: {state['filt_pct']:.0f}%  (F1: {rpm_f1:.0f} RPM {'⚠ FAULT' if fault_f1 else 'OK'}  F2: {rpm_f2:.0f} RPM {'⚠ FAULT' if fault_f2 else 'OK'})")
        print(f"Exhaust:   {state['exh_pct']:.0f}%   (Ex: {rpm_ex:.0f} RPM {'⚠ FAULT' if fault_ex else 'OK'})")
        print()

        # Refresh display with latest data
        refresh_display(state)

    time.sleep(0.1)  # small sleep to avoid busy-looping
