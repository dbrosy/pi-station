#!/usr/bin/python
''' --------------------------------------------------------
  Name:     Rasbery Pi Weather Station
  Author:   Damian Brosnahan
  Credits:  John M. Wargo of www.johnwargo.com
  
  Details:  Raspbery Pi Weather Station logging Tempurature(Corrected), Humidity
            and Pressure to Weather Underground and Initial State
---------------------------------------------------------'''

from __future__ import print_function

import sys
import os
import time
import datetime

from urllib import urlencode
import urllib2

# Import config file
from config import Config

from sense_hat import SenseHat

# Required for Initial State 
from ISStreamer.Streamer import Streamer  


# ============================================================================
# Constants
# ============================================================================
# specifies how often to measure values from the Sense HAT (in minutes)
MEASUREMENT_INTERVAL = 10  # minutes
# Set to False when testing the code and/or hardware
# Use Metric instead of Imperial
USE_METRIC = True
# Set to True to enable upload of weather data to Weather Underground
WU_UPLOAD = True
# Set to True to enable upload of weather data to Initial State
IS_UPLOAD = True
# the weather underground URL used to upload weather data
WU_URL = "http://weatherstation.wunderground.com/weatherstation/updateweatherstation.php"
# some string constants
SINGLE_HASH = "#"
HASHES = "########################################"
SLASH_N = "\n"

DEBUG = True
OUT_CONSOLE = False

# constants used to display an up and down arrows plus bars
# modified from https://www.raspberrypi.org/learning/getting-started-with-the-sense-hat/worksheet/
# set up the colours (blue, red, empty)
b = [0, 0, 255]  # blue
r = [255, 0, 0]  # red
e = [0, 0, 0]  # empty
# create images for up and down arrows
arrow_up = [
    e, e, e, r, r, e, e, e,
    e, e, r, r, r, r, e, e,
    e, r, e, r, r, e, r, e,
    r, e, e, r, r, e, e, r,
    e, e, e, r, r, e, e, e,
    e, e, e, r, r, e, e, e,
    e, e, e, r, r, e, e, e,
    e, e, e, r, r, e, e, e
]
arrow_down = [
    e, e, e, b, b, e, e, e,
    e, e, e, b, b, e, e, e,
    e, e, e, b, b, e, e, e,
    e, e, e, b, b, e, e, e,
    b, e, e, b, b, e, e, b,
    e, b, e, b, b, e, b, e,
    e, e, b, b, b, b, e, e,
    e, e, e, b, b, e, e, e
]
bars = [
    e, e, e, e, e, e, e, e,
    e, e, e, e, e, e, e, e,
    r, r, r, r, r, r, r, r,
    r, r, r, r, r, r, r, r,
    b, b, b, b, b, b, b, b,
    b, b, b, b, b, b, b, b,
    e, e, e, e, e, e, e, e,
    e, e, e, e, e, e, e, e
]


def c_to_f(input_temp):
    # convert input_temp from Celsius to Fahrenheit
    return (input_temp * 1.8) + 32


def get_cpu_temp():
    # 'borrowed' from https://www.raspberrypi.org/forums/viewtopic.php?f=104&t=111457
    # executes a command at the OS to pull in the CPU temperature
    res = os.popen('vcgencmd measure_temp').readline()
    print(res.replace("temp=", "").replace("'C\n", ""))
    return float(res.replace("temp=", "").replace("'C\n", ""))


# use moving average to smooth readings
def get_smooth(x):
    # do we have the t object?
    if not hasattr(get_smooth, "t"):
        # then create it
        get_smooth.t = [x, x, x]
    # manage the rolling previous values
    get_smooth.t[2] = get_smooth.t[1]
    get_smooth.t[1] = get_smooth.t[0]
    get_smooth.t[0] = x
    # average the three last temperatures
    xs = (get_smooth.t[0] + get_smooth.t[1] + get_smooth.t[2]) / 3
    return xs


def get_temp():
    # ====================================================================
    # Unfortunately, getting an accurate temperature reading from the
    # Sense HAT is improbable, see here:
    # https://www.raspberrypi.org/forums/viewtopic.php?f=104&t=111457
    # so we'll have to do some approximation of the actual temp
    # taking CPU temp into account. The Pi foundation recommended
    # using the following:
    # http://yaab-arduino.blogspot.co.uk/2016/08/accurate-temperature-reading-sensehat.html
    # ====================================================================
    # First, get temp readings from both sensors
    t1 = sense.get_temperature_from_humidity()
    t2 = sense.get_temperature_from_pressure()
    # t becomes the average of the temperatures from both sensors
    t = (t1 + t2) / 2
    # Now, grab the CPU temperature
    t_cpu = get_cpu_temp()
    # Calculate the 'real' temperature compensating for CPU heating
    t_corr = t - ((t_cpu - t) / 1.5)
    
    print("Temp (h): %s, Temp (p): %s, Temp (a): %s" % (t1, t2, t)

    # print("Temp (h): %s, Temp (p): %s, Temp (a): %s, Temp (cpu): $.2f, Temp (corr): %s" % (t1, t2, t, t_cpu, t_corr))
    # Finally, average out that value across the last three readings
    
    t_corr = get_smooth(t_corr)
    
    # convoluted, right?
    
    
    # Return the calculated temperature
    return t_corr


def main():
    global last_temp
    
    # initialize the lastMinute variable to the current time to start
    last_minute = datetime.datetime.now().minute
    # on startup, just use the previous minute as lastMinute
    last_minute -= 1
    if last_minute == 0:
        last_minute = 59

    # infinite loop to continuously check weather values
    while 1:
        # The temp measurement smoothing algorithm's accuracy is based
        # on frequent measurements, so we'll take measurements every 5 seconds
        # but only upload on measurement_interval
        current_second = datetime.datetime.now().second
        # are we at the top of the minute or at a 5 second interval?
        if (current_second == 0) or ((current_second % 5) == 0):
            # ========================================================
            # read values from the Sense HAT
            # ========================================================
            # calculate the temperature
            calc_temp = get_temp()
            # now use it for our purposes
            temp_c = round(calc_temp, 1)
            temp_f = round(c_to_f(calc_temp), 1)
            humidity = round(sense.get_humidity(), 0)
            # convert pressure from millibars to inHg before posting
            pressure = round(sense.get_pressure() * 0.0295300, 1)
            pressure_hpa = round(sense.get_pressure(), 1)
            if (OUT_CONSOLE):
              if USE_METRIC:
                  print("Temp: %sC (%sF), Pressure: %s hPa, Humidity: %s%%" % (temp_c, temp_f, pressure_hpa, humidity))
              else:
                  print("Temp: %sF (%sC), Pressure: %s inHg, Humidity: %s%%" % (temp_f, temp_c, pressure, humidity))

            # get the current minute
            current_minute = datetime.datetime.now().minute
            # is it the same minute as the last time we checked?
            if current_minute != last_minute:
                # reset last_minute to the current_minute
                last_minute = current_minute
                # is minute zero, or divisible by 10?
                # we're only going to take measurements every MEASUREMENT_INTERVAL minutes
                if (current_minute == 0) or ((current_minute % MEASUREMENT_INTERVAL) == 0):
                    # get the reading timestamp
                    now = datetime.datetime.now()
                    print("\n%d minute mark (%d @ %s)" % (MEASUREMENT_INTERVAL, current_minute, str(now)))
                    # did the temperature go up or down?
                    if last_temp != temp_f:
                        if last_temp > temp_f:
                            # display a blue, down arrow
                            sense.set_pixels(arrow_down)
                        else:
                            # display a red, up arrow
                            sense.set_pixels(arrow_up)
                    else:
                        # temperature stayed the same
                        # display red and blue bars
                        sense.set_pixels(bars)
                    # set last_temp to the current temperature before we measure again
                    last_temp = temp_f

                    # ========================================================
                    # Upload the weather data to Weather Underground
                    # ========================================================
                    # is WU_UPLOAD enabled (True)?
                    if WU_UPLOAD:
                        # From http://wiki.wunderground.com/index.php/PWS_-_Upload_Protocol
                        print("Uploading data to Weather Underground")
                        # build a weather data object
                        weather_data = {
                            "action": "updateraw",
                            "ID": wu_station_id,
                            "PASSWORD": wu_station_key,
                            "dateutc": "now",
                            "tempf": str(temp_f),
                            "humidity": str(humidity),
                            "baromin": str(pressure),
                        }
                        try:
                            upload_url = WU_URL + "?" + urlencode(weather_data)
                            response = urllib2.urlopen(upload_url)
                            html = response.read()
                            print("Server response:", html)
                            # do something
                            response.close()  # best practice to close the file
                        except:
                            print("Exception:", sys.exc_info()[0], SLASH_N)
                    else:
                        print("Skipping Weather Underground upload")

                    # ========================================================
                    # Upload the weather data to Initial State
                    # ========================================================
                    # is IS_UPLOAD enabled (True)?                        
                    if IS_UPLOAD:         
                        print("Uploading data to Initial State")
                        try:
                            # Setup streamer for Initial State
                            # streamer = Streamer(bucket_name=is_bucket_name, bucket_key=is_bucket_key, access_key=is_access_key, debug_level=1)
                            streamer = Streamer(bucket_name=is_bucket_name, bucket_key=is_bucket_key, access_key=is_access_key)
                            time.sleep(0.1)
                            #streamer.log(":sunny: " + Config.SENSOR_LOCATION_NAME + " Temperature(C)", temp_c)
                            #streamer.log(":sweat_drops: " + Config.SENSOR_LOCATION_NAME + " Humidity(%)", humidity)
                            #streamer.log(":cloud: " + Config.SENSOR_LOCATION_NAME + " Pressure(IN)", pressure)
                            streamer.log(":sunny: " + " Temperature (C)", temp_c)
                            streamer.log(":sweat_drops: " + " Humidity (%)", humidity)
                            streamer.log(":cloud: " + " Pressure (hPa)", pressure_hpa)
                            streamer.close()
                        except:
                            print("Exception:", sys.exc_info()[0], SLASH_N)
                            streamer.close()
                    else:
                        print("Skipping Initial State")
                        
        # wait a second then check again
        # You can always increase the sleep value below to check less often
        time.sleep(1)  # this should never happen since the above is an infinite loop

    print("Leaving main()")


# ============================================================================
# here's where we start doing stuff
# ============================================================================
print(SLASH_N + HASHES)
print(SINGLE_HASH, "Raspberry Pi Weather Station               ", SINGLE_HASH)
print(SINGLE_HASH, "By Damian Brosnahan                        ", SINGLE_HASH)
print(HASHES)

# make sure we don't have a MEASUREMENT_INTERVAL > 60
if (Config.MEASUREMENT_INTERVAL is not None):
    MEASUREMENT_INTERVAL = Config.MEASUREMENT_INTERVAL
    
if (MEASUREMENT_INTERVAL is None) or (MEASUREMENT_INTERVAL > 60):
    print("The application's 'MEASUREMENT_INTERVAL' cannot be empty or greater than 60")
    sys.exit(1)

# ============================================================================
#  Read Weather Underground Configuration Parameters
# ============================================================================
print("\nInitializing Weather Underground configuration")
wu_station_id = Config.STATION_ID
wu_station_key = Config.STATION_KEY
if (wu_station_id is None) or (wu_station_key is None):
    print("Missing values from the Weather Underground configuration file\n")
    sys.exit(1)

# we made it this far, so it must have worked...
print("Successfully read Weather Underground configuration values")
print("Station ID:", wu_station_id)
# print("Station key:", wu_station_key)

# ============================================================================
#  Read Initial State Configuration Parameters
# ============================================================================
print("\nInitializing Initial State configuration")
is_bucket_name = Config.BUCKET_NAME
is_bucket_key = Config.BUCKET_KEY
is_access_key = Config.ACCESS_KEY
if (is_bucket_name is None) or (is_bucket_key is None) or (is_access_key is None):
    print("Missing values from the Initial State configuration file\n")
    sys.exit(1)

# we made it this far, so it must have worked...
print("Successfully read Initial State configuration values")
print("Bucket Name:", is_bucket_name)

# ============================================================================
# initialize the Sense HAT object
# ============================================================================
try:
    print("Initializing the Sense HAT client")
    sense = SenseHat()
    # sense.set_rotation(180)
    # then write some text to the Sense HAT's 'screen'
    sense.show_message("Init", text_colour=[255, 255, 0], back_colour=[0, 0, 255])
    # clear the screen
    sense.clear()
    # get the current temp to use when checking the previous measurement
    if USE_METRIC:
        last_temp = round(get_temp(), 1)
    else:
        last_temp = round(c_to_f(get_temp()), 1)
    
    print("Current temperature reading:", last_temp)
except:
    print("Unable to initialize the Sense HAT library:", sys.exc_info()[0])
    sys.exit(1)

print("Initialization complete!")

# Now see what we're supposed to do next
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting application\n")
        sys.exit(0)
