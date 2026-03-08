import board
import time
import displayio
import gc
from i2cdisplaybus import I2CDisplayBus
import adafruit_sht4x
import adafruit_sgp30
import adafruit_displayio_sh1107
from adafruit_display_text import label
import terminalio

displayio.release_displays()
i2c = board.STEMMA_I2C()
display_bus = I2CDisplayBus(i2c, device_address=0x3C)
oled = adafruit_displayio_sh1107.SH1107(display_bus, width=128, height=64, rotation=90)
sht = adafruit_sht4x.SHT4x(i2c)
sgp = adafruit_sgp30.Adafruit_SGP30(i2c)
sgp.iaq_init()

splash = displayio.Group()
oled.root_group = splash

temp_label  = label.Label(terminalio.FONT, text="Temp:     --", x=0, y=4)
humid_label = label.Label(terminalio.FONT, text="Humidity: --", x=0, y=18)
co2_label   = label.Label(terminalio.FONT, text="CO2:      --", x=0, y=32)
tvoc_label  = label.Label(terminalio.FONT, text="TVOC:     --", x=0, y=46)
splash.append(temp_label)
splash.append(humid_label)
splash.append(co2_label)
splash.append(tvoc_label)

print("Sensors connected!")
print("Press CTRL+C to stop")
try:
    while True:
        temp, humidity = sht.measurements
        temp_f = round((temp * 9 / 5) + 32, 1)
        co2, tvoc = sgp.iaq_measure()

        temp_label.text  = "Temp:     " + str(temp_f) + " F"
        humid_label.text = "Humidity: " + str(round(humidity)) + " %"
        co2_label.text   = "CO2:      " + str(co2) + " ppm"
        tvoc_label.text  = "TVOC:     " + str(tvoc) + " ppb"

        print("Temp:", temp_f, "F | Humidity:", round(humidity), "%")
        print("CO2:", co2, "ppm | TVOC:", tvoc, "ppb")
        gc.collect()
        for _ in range(30):
            time.sleep(0.1)
except KeyboardInterrupt:
    print("Stopped!")
    displayio.release_displays()
