# P12 Fan Control

Controls the Arctic P12 Pro 120mm PWM fan based on temperature.

## Hardware
- Adafruit Feather RP2040
- Arctic P12 Pro fan
- IRF520 MOSFET module
- LM2596 Buck converter set to 12V
- Adafruit SHT45 temperature sensor

## Wiring
- Fan blue wire (PWM) → Feather GPIO 5
- Fan yellow wire (12V) → IRF520 Motor+ output
- IRF520 SIG pin → Feather GPIO 5
- IRF520 V+ → Buck converter 12V output
- All GND tied to common ground

## Libraries Required
- adafruit_sht4x

## How It Works
- Below 25C the fan is completely off
- Between 25C and 40C the fan ramps up proportionally
- Above 40C the fan runs at 100%
- Minimum running speed is 30% to prevent stalling
