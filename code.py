import time, gc, os
import adafruit_dotstar
import board
import busio
import feathers2
import adafruit_displayio_ssd1306
import displayio
import terminalio
from adafruit_display_text import label
import time
import wifi
import socketpool
import ipaddress
import adafruit_requests
import ssl
from digitalio import DigitalInOut, Direction, Pull
import sys
import adafruit_datetime


def create_splash():
    # Make a display context
    splash = displayio.Group(max_size=10)
    display.show(splash)
    return splash

def clear_screen(splash):
    # Fill screen with black
    color_bitmap = displayio.Bitmap(128,32,1)
    color_palette = displayio.Palette(1)
    color_palette[0] = 0x000000
    bg_sprite = displayio.TileGrid(color_bitmap, pixel_shader=color_palette, x=0, y=0)
    splash.append(bg_sprite)

def display_text(splash, the_text, line=1):
    if line == 1:
        x = 0
        y = 4
    elif line == 2:
        x = 0
        y = 14
    elif line == 3:
        x = 0
        y = 24
    else:
        x = 0
        y = 4

    # Display text on screen
    text_area = label.Label(terminalio.FONT, text=the_text, color=0xFFFFFF, x=x, y=y)
    splash.append(text_area)

def get_city_forecast(requests, location):
    # Issue HTTP request for a city's forecast
    response = requests.get(
        "https://api.openweathermap.org/data/2.5/onecall"
            + "?lat=" + location["latitude"]
            + "&lon=" + location["longitude"]
            + "&exclude=alerts,minutely"
            + "&units=metric"
            + "&APPID=" + credentials["api_key"]
    )

    return response.json()

def convert_to_date(stamp):
    # Convert a numeric Posix-style date into a "real" date
    dt = time.localtime(stamp)

    conv = {
        "year": dt[0],
        "month": dt[1],
        "day": dt[2],
        "hour": dt[3],
        "minute": dt[4]
    }

    conv["formatted"] = str(conv["day"]) + "/" + str(conv["month"]) + "/" + str(conv["year"]) + " " + str(conv["hour"]) + ":" + str(conv["minute"])

    return conv

def convert_part_forecast(part):
    # Convert part of a retrieved forecast into a cut-down version
    conv_forecast = {
        "datetime": convert_to_date(part["dt"]),
        "temp": str(part["temp"]) + "C",
        "feels_like": str(part["feels_like"]) + "C",
        "humidity": str(part["humidity"]) + "%",
        "wind": str(part["wind_speed"]) + "m/s",
        "weather": part["weather"][0]["main"],
        "weather_detail": part["weather"][0]["description"]
    }

    try:
        conv_forecast["rain"] = str(part["pop"] * 100) + "%"
    except Exception as e:
        print(e)
        pass

    return conv_forecast

def convert_forecast(forecast):
    # Convert the entire and parts of a forecast
    conv_forecast = {
        "current": convert_part_forecast(forecast["current"])
    }
    conv_forecast["hourly"] = []
    for hour in forecast["hourly"]:
        conv_forecast["hourly"].append(convert_part_forecast(hour))

    return conv_forecast


# Make sure the 2nd LDO is turned on
feathers2.enable_LDO2(True)

# Turn on the internal blue LED
feathers2.led_set(True)

# Create the i2c bus
i2c = board.I2C()

# Release the displays and then re-create them
displayio.release_displays()
display_bus = displayio.I2CDisplay(i2c, device_address=0x3c)
display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=128, height=32)

# Define buttons
button_a = DigitalInOut(board.D13)
button_a.direction = Direction.INPUT
button_a.pull = Pull.UP

button_b = DigitalInOut(board.D12)
button_b.direction = Direction.INPUT
button_b.pull = Pull.UP

button_c = DigitalInOut(board.D9)
button_c.direction = Direction.INPUT
button_c.pull = Pull.UP

# Create initial splash screen context
splash = create_splash()

# Import secrets/credentials
clear_screen(splash)
display_text(splash, "Importing secrets")

try:
    from secrets import secrets, credentials

except ImportError:
    clear_screen(splash)
    display_text(splash, "Unable to import secrets")
    sys.exit(1)

clear_screen(splash)
display_text(splash, "Secrets imported")

# Connect to WiFi
clear_screen(splash)

display_text(splash, "Initialising wifi")
time.sleep(1)

try:
    # Start screen again
    splash = create_splash()
    clear_screen(splash)
    display_text(splash, "Connecting to " + secrets["ssid"])
    wifi.radio.connect(secrets["ssid"], secrets["password"])
    clear_screen(splash)
    display_text(splash, "Connected to " + secrets["ssid"])
    time.sleep(1)
    clear_screen(splash)
    display_text(splash, "IP: " + str(wifi.radio.ipv4_address))

except Exception as e:
    print("Exception trying to connect: " + str(e))
    clear_screen(splash)
    display_text(splash, "Unable to connect to WiFi")
    exit(1)

# Create a connection pool and a session
pool = socketpool.SocketPool(wifi.radio)
requests = adafruit_requests.Session(pool, ssl.create_default_context())

# Define locations for forecasts (for which you need the Lat/Lon of the locations)
locations = [
    {"city": "North Walsham,uk", "longitude": "1.3860", "latitude": "52.8227"},
    {"city": "Potton,uk", "longitude": "-0.2156", "latitude": "52.1291"},
    {"city": "Halstead,uk", "longitude": "0.6390", "latitude": "51.9450"}
]

clear_screen(splash)
display_text(splash, "Ready for forecasting")

print("Ready to start forecasting")

loc = 1
location = locations[loc-1]
got_forecast = False

while True:
    if not button_a.value:
        splash = create_splash()
        loc = loc + 1
        num_locations = len(locations)
        if loc > num_locations:
            loc = 1

        # Get index - 1 (because Python's lists start at zero)
        location = locations[loc-1]
        display_text(splash, "Location:")
        display_text(splash, location["city"], 2)
        got_forecast = False

        # debounce
        time.sleep(0.5)

    if not button_b.value:
        splash = create_splash()
        display_text(splash, "Getting weather for")
        display_text(splash, location["city"], 2)
        forecast = get_city_forecast(requests, location)
        conv_forecast = convert_forecast(forecast)
        display_text(splash, "Weather obtained", 3)
        got_forecast = True
        part_index = 1

        # debounce
        time.sleep(0.5)

    if not button_c.value:
        if got_forecast:
            splash = create_splash()
            display_text(splash, "C:" + conv_forecast["current"]["datetime"]["formatted"] + "UTC")
            display_text(splash, "Tmp:" + conv_forecast["current"]["feels_like"] + " Hm:" + conv_forecast["current"]["humidity"], 2)
            display_text(splash, conv_forecast["current"]["weather"], 3)

            time.sleep(3)

            ix = 1
            for hour in conv_forecast["hourly"]:
                splash = create_splash()
                display_text(splash, "F:" + hour["datetime"]["formatted"] + "UTC")
                display_text(splash, "Tmp:" + hour["feels_like"] + " Hm:" + hour["humidity"], 2)
                display_text(splash, hour["weather"] + " " + hour["rain"], 3)
                time.sleep(2)

                ix = ix + 1
                if ix == 8:
                    break

            splash = create_splash()
            display_text(splash, "End of forecast")

        else:
            splash = create_splash()
            display_text(splash, "No data available")

        # debounce
        time.sleep(0.5)