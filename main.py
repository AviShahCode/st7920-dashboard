from datetime import datetime
import requests
import time
import dotenv
import os

from driver import ST7920
from graphics import *

dotenv.load_dotenv()
owm_api_key = os.environ.get("OPEN_WEATHER_MAP_API_KEY")
owm_lat = os.environ.get("LAT")
owm_lon = os.environ.get("LON")

base_url = f"https://api.openweathermap.org/data/2.5/weather?lat={owm_lat}&lon={owm_lon}&units=metric&appid={owm_api_key}"
weather_data = requests.get(base_url).json()

lcd = ST7920(13, reset_pin=26)

lcd.set_instruction_set(True, True)
lcd.clear_gdram()

g = GraphicsBuffer()

time_text = DrawableText("", "./fonts/JetBrainsMono-Bold.ttf", 36, y=-8)
am_pm_text = DrawableText("", "./fonts/JetBrainsMono-Regular.ttf", 14, x=110, y=-1)
seconds_text = DrawableText("", "./fonts/JetBrainsMono-Regular.ttf", 14, x=110, y=15)

date_text = DrawableText("", "./fonts/JetBrainsMono-Regular.ttf", 18, x=4, y=37)
celcius_text = DrawableText("°C", "./fonts/JetBrainsMono-Regular.ttf", 10, x=112, y=41)
date_border = Rectangle(0, 32, 128, 32)

g.add(time_text)
g.add(am_pm_text)
g.add(seconds_text)

g.add(date_text)
g.add(date_border)
g.add(celcius_text)
g.add(Triangle(0, 32, 5, 32, 0, 37, True))
g.add(Triangle(127, 32, 122, 32, 127, 37, True))
g.add(Triangle(0, 63, 5, 63, 0, 58, True))
g.add(Triangle(127, 63, 122, 63, 127, 58, True))

while True:
    while datetime.now().strftime("%S") == seconds_text.text:
        time.sleep(0.1)

    now = datetime.now()
    time_text.text = now.strftime("%I:%M")
    am_pm_text.text = now.strftime("%p")
    seconds_text.text = now.strftime("%S")
    temp = int(weather_data['main']['temp']) if weather_data['cod'] == 200 else '--'
    date_text.text = now.strftime(f"%d %a//{temp}")

    g.draw()
    # g.reverse()
    lcd.write_gdram_buffer(g)
    time.sleep(0.6)

    if now.strftime("%M") != "00":
        continue
    r = requests.get(base_url)
    if r.status_code != 200:
        continue
    r = r.json()
    if r['cod'] == 200:
        weather_data = r
