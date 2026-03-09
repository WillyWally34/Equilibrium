# filtration_fans.py — CircuitPython for Adafruit Feather RP2040
# Two 24V filtration fans controlled proportionally by SGP30 VOC readings
# Includes tachometer fault detection for both fans

import board
import busio
import pwmio
import countio
import time
import adafruit_sgp30

# ── Configuration ──────────────────────────────────────────────────────────────
# VOC (eCO2 used as proxy; SGP30 reports TVOC in ppb)
TVOC_MIN        = 0      # ppb — fans run at minimum speed
TVOC_MAX        = 500    # ppb — fans run at full speed (clamps above this)

FAN_MIN_DUTY    = 16384  # ~25% — minimum to keep fans spinning (don't go below this)
FAN_MAX_DUTY    = 65535  # 100% full speed
PWM_FREQ        = 25000  # 25 kHz standard PWM for fans

# Tachometer — most fans pulse twice per revolution
TACH_PULSES_PER_REV = 2
TACH_SAMPLE_TIME    = 2.0   # seconds to count pulses for RPM calc
MIN_RPM             = 200   # below this = fan fault

# How often to read VOC and update fan speed (seconds)
UPDATE_INTERVAL = 3.0

# ── Pin assignments ────────────────────────────────────────────────────────────
# PWM output → MOSFET gate → switches 24V GND path for each fan
FAN1_PWM_PIN  = board.D5
FAN2_PWM_PIN  = board.D6

# Tachometer inputs (open-collector, needs pull-up — use 10kΩ to 3.3V)
FAN1_TACH_PIN = board.D9
FAN2_TACH_PIN = board.D10

# I2C for SGP30 (Feather RP2040: SDA=D24/A4, SCL=D25/A5 or use board.SDA/SCL)
I2C_SDA = board.SDA
I2C_SCL = board.SCL

# ── Setup ──────────────────────────────────────────────────────────────────────
i2c  = busio.I2C(I2C_SCL, I2C_SDA)
sgp  = adafruit_sgp30.Adafruit_SGP30(i2c)
sgp.iaq_init()
sgp.set_iaq_baseline(0x8973, 0x8AAE)  # optional: set a saved baseline if you have one

fan1 = pwmio.PWMOut(FAN1_PWM_PIN, frequency=PWM_FREQ, duty_cycle=FAN_MIN_DUTY)
fan2 = pwmio.PWMOut(FAN2_PWM_PIN, frequency=PWM_FREQ, duty_cycle=FAN_MIN_DUTY)

tach1 = countio.Counter(FAN1_TACH_PIN, edge=countio.Edge.RISE)
tach2 = countio.Counter(FAN2_TACH_PIN, edge=countio.Edge.RISE)

# ── Helpers ────────────────────────────────────────────────────────────────────
def tvoc_to_duty(tvoc):
    """Map TVOC ppb → PWM duty cycle between FAN_MIN and FAN_MAX."""
    ratio = (tvoc - TVOC_MIN) / (TVOC_MAX - TVOC_MIN)
    ratio = max(0.0, min(1.0, ratio))           # clamp 0.0–1.0
    return int(FAN_MIN_DUTY + ratio * (FAN_MAX_DUTY - FAN_MIN_DUTY))

def set_fans(duty):
    fan1.duty_cycle = duty
    fan2.duty_cycle = duty

def measure_rpm(counter, sample_seconds):
    """Count tach pulses over sample_seconds and return RPM."""
    counter.reset()
    time.sleep(sample_seconds)
    pulses = counter.count
    rpm = (pulses / TACH_PULSES_PER_REV) * (60.0 / sample_seconds)
    return rpm

def check_faults(duty):
    """Sample both tachometers and warn if RPM is too low."""
    rpm1 = measure_rpm(tach1, TACH_SAMPLE_TIME)
    rpm2 = measure_rpm(tach2, TACH_SAMPLE_TIME)
    print(f"  Fan 1: {rpm1:.0f} RPM  |  Fan 2: {rpm2:.0f} RPM")
    if duty > FAN_MIN_DUTY:   # only flag faults when fans should be spinning
        if rpm1 < MIN_RPM:
            print("  ⚠️  FAULT: Fan 1 RPM too low — check wiring or fan!")
        if rpm2 < MIN_RPM:
            print("  ⚠️  FAULT: Fan 2 RPM too low — check wiring or fan!")

# ── SGP30 warm-up ──────────────────────────────────────────────────────────────
# SGP30 needs ~15s of readings before TVOC values are reliable
print("SGP30 warming up (15s)...")
set_fans(FAN_MIN_DUTY)   # run at minimum during warm-up
for _ in range(15):
    _ = sgp.tvoc             # keep internal algorithm running
    time.sleep(1)
print("Warm-up complete. Starting filtration control.\n")

# ── Main loop ──────────────────────────────────────────────────────────────────
while True:
    tvoc = sgp.tvoc                   # TVOC in ppb
    eco2 = sgp.eCO2                   # eCO2 in ppm (bonus reading)
    duty = tvoc_to_duty(tvoc)
    speed_pct = (duty / FAN_MAX_DUTY) * 100

    set_fans(duty)

    print(f"TVOC: {tvoc} ppb  |  eCO2: {eco2} ppm  |  Fan speed: {speed_pct:.1f}%")
    check_faults(duty)
    print()

    time.sleep(UPDATE_INTERVAL)
