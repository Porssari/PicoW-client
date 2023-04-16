###########################################################################
#
# Description:     Pörssäri Micropython client for Raspberry Pico W
#                  
# Requirements:    Tested with Pico W Micropython v1.19.1-994-ga4672149b
#
# Known issues:    Web server gets stuck when losing wifi connection
#
############################################################################

VERSION = "Micropython-1.0-rc2"

# Import network modules
try:
    import urequests as requests
except:
    import requests
try:
    import usocket as socket
except:
    import socket

# Import custom python modules
import connectionmanager
import webpages
    
# Import libs to read and convert data
import json
from ubinascii import hexlify
import random
from math import floor

#import time
from time import sleep, mktime, localtime

# Import pin-control
from machine import Pin, Timer

# Import carbage collector
import gc

# Import MQTT (experimental)
from umqttsimple import MQTTClient

# Define variables
# MQTT server (experimental)
mqtt_control = True
mqtt_server = '192.168.1.91'
client_id = 'PicoW'
user_t = 'pico'
password_t = 'picopassword'
channel1_topic = 'hello'
channel2_topic = 'hello'
channel3_topic = 'hello'
channel4_topic = 'hello'
channel5_topic = 'hello'
channel6_topic = 'hello'
channel7_topic = 'hello'
channel8_topic = 'hello'

# Channel mode (experimental)
# GPIO or MQTT
channel1_mode = 'MQTT'
channel2_mode = 'GPIO'
channel3_mode = 'MQTT'
channel4_mode = 'MQTT'
channel5_mode = 'MQTT'
channel6_mode = 'MQTT'
channel7_mode = 'MQTT'
channel8_mode = 'MQTT'


# Real time clock
rtc = machine.RTC()

# Timers
programTimer = Timer()
controlTimer = Timer()
requestTimer = Timer()

# Onboard led
onboard = Pin("LED", Pin.OUT, value=0)

# Relay pins
relay1 = Pin(21, Pin.OUT)
relay2 = Pin(20, Pin.OUT)
relay3 = Pin(19, Pin.OUT)
relay4 = Pin(18, Pin.OUT)
relay5 = Pin(17, Pin.OUT)
relay6 = Pin(16, Pin.OUT)
relay7 = Pin(15, Pin.OUT)
relay8 = Pin(14, Pin.OUT)

# Tuple for web interface (add all the relays above for proper functionality)
relays = (relay1, relay2, relay3, relay4, relay5, relay6, relay7, relay8)

# Get config from json 
try:
    with open("config.json", "r") as jsonfile:
        data = json.load(jsonfile)
        
        # Get fallback-url
        fallbackUrl = data['Fetch_url_fallback']
        
        # Get failsafe-setting
        failsafe = data['Failsafe']
        
        # Get wifi-information to dictionary
        profiles = {}
        try:
            wifi = data['Known_networks']
            for item in wifi:
                ssid = item['SSID']
                try:
                    password = item['PASS']
                    profiles[ssid] = password
                except:
                    profiles[ssid] = ''
        except:
            print('No saved wifi networks')
                           
except:
    # If configs cannot be read, flash twice and reboot
    onboard.on()
    sleep(0.25)
    onboard.off()
    sleep(0.25)
    onboard.on()
    sleep(0.25)
    onboard.off()
    sleep(1)
    print("Error! Could not retrieve configs, rebooting..")
    machine.reset()
    
# Get device mac from wifi adapter
try:
    deviceMacHex = connectionmanager.wlan_sta.config('mac')
    mac = hexlify(deviceMacHex).decode()
    print("Device-MAC: {}".format(mac))
except:
    try:
        # Get fallback-mac
        with open("config.json", "r") as jsonfile:
            data = json.load(jsonfile)   
            
            mac = data['Mac_fallback']
            print("Could not retrieve MAC from network adapter, using user defined mac: {}".format(mac))
    except:
        # Flash led three times and reboot
        onboard.on()
        sleep(0.25)
        onboard.off()
        sleep(0.25)
        onboard.on()
        sleep(0.25)
        onboard.off()
        sleep(0.25)
        onboard.on()
        sleep(0.25)
        onboard.off()
        sleep(1)
        print("Error with device MAC, rebooting..")
        machine.reset()

# Get wifi connection (Returns wlan_sta or wlan_ap)
wifi = connectionmanager.get_connection(profiles)

# Program state variables
lastRequest = 0
hoursLeftOnJson = 0
doControlsTimerArmed = False
getControlsTimerArmed = False
rtcSynced = False
bootTimestampSynced = False

# Empty list for webserver until first request is succeeded
controlsJson = {}

#MQTT connect
def mqttConnect():
    client = MQTTClient(client_id, mqtt_server, user=user_t, password=password_t, keepalive=10)
    client.connect()
    print('Connected to %s MQTT Broker'%(mqtt_server))
    return client

    
def updateStatus():
    global doControlsTimerArmed,hoursLeftOnJson,controlsJson,wifi
    
    # Micropython health checks
    # Collect garbages
    if gc.mem_free() < 102000:
        gc.collect()
    
    time = rtc.datetime()    
    print("\n[{:02d}:{:02d}:{:02d}]".format(time[4],time[5],time[6]),end=" ")
    print("Memory: free:{}, alloc:{}".format(gc.mem_free(), gc.mem_alloc()))
           
    # If device is not connected to wifi-network, try to connect       
    if not connectionmanager.wlan_sta.isconnected():
        time = rtc.datetime() 
        print("[{:02d}:{:02d}:{:02d}]".format(time[4],time[5],time[6]),end=" ")
        print("No internet connection, trying to connect")
        
        wifi = connectionmanager.get_connection(profiles)
        if not connectionmanager.wlan_sta.isconnected():
            print("[{:02d}:{:02d}:{:02d}]".format(time[4],time[5],time[6]),end=" ")
            print("Could not connect")
            
    else:
        time = rtc.datetime() 
        print("[{:02d}:{:02d}:{:02d}]".format(time[4],time[5],time[6]),end=" ")
        print('Network connected')
    
    # Program state checks
    # RTC has to be synced to control relays
    if rtcSynced:
        
        # Calculate how many hours are left in JSON (if request is ok, should equal with hours_count - 1)
        if controlsJson:
            timeUnix = mktime(localtime())
            requestWithOffset = int(controlsJson['Metadata']['Timestamp']) + int(controlsJson['Metadata']['Timestamp_offset'])
            hoursCountSeconds = int(controlsJson['Metadata']['Hours_count']) * 3600
            hoursLeftOnJson = floor(((requestWithOffset + hoursCountSeconds) - timeUnix) / 3600)
            time = rtc.datetime()
            print("[{:02d}:{:02d}:{:02d}]".format(time[4],time[5],time[6]),end=" ")
            print('Control hours left in JSON: {}'.format(hoursLeftOnJson))
  
        # Check if controls_timer is armed and arm if not, JSON is not required because function check if failsafe is set
        if not doControlsTimerArmed:
            toNextQuarter = secondsUntilNextQuarter()
            time = rtc.datetime()
            print("[{:02d}:{:02d}:{:02d}]".format(time[4],time[5],time[6]),end=" ")
            print('Set relay control timer ({} seconds)'.format(toNextQuarter))
            controlTimer.deinit()
            controlTimer.init(mode=Timer.ONE_SHOT, period=toNextQuarter * 1000, callback=doControlsTimer)
            doControlsTimerArmed = True
    else:
        time = rtc.datetime()
        print("[{:02d}:{:02d}:{:02d}]".format(time[4],time[5],time[6]),end=" ")
        print('RTC not synced, control loop not possible')

        
def getControls():
    global controlsJson,lastRequest,rtcSynced
    
    # If controller is in ap-mode there is no internet connection, not worth trying to get new JSON..
    if connectionmanager.wlan_ap.isconnected():
        print("\n[{:02d}:{:02d}:{:02d}]".format(time[4],time[5],time[6]),end=" ")
        print('No internet connection, JSON request not possible.')
        return
    
    time = rtc.datetime() 
    print("\n[{:02d}:{:02d}:{:02d}]".format(time[4],time[5],time[6]),end=" ")
    print('Get JSON from',end=" ")
    
    urlToCall = '{}?device_mac={}&client={}'.format(fallbackUrl,mac,VERSION)
    
    #If request already succesfully made once then add last response unix time to request and use fetch-url from JSON.
    #If RTC is not synced we do not add last_request because we want get new JSON from server to update rtc-time
    if lastRequest > 0 and rtcSynced:
        fetchUrl = controlsJson['Metadata']['Fetch_url']
        urlToCall = "{}?device_mac={}&last_request={}&client={}".format(fetchUrl,mac,lastRequest,VERSION)
       
    print(urlToCall)
    
    # JSON-request 
    try:
        try:
            resp = requests.get(urlToCall, timeout=8, json=True)
        except:
            time = rtc.datetime() 
            print("[{:02d}:{:02d}:{:02d}]".format(time[4],time[5],time[6]),end=" ")
            print("Error! Trying fallback-url (",end="")
            urlToCall = "{}?device_mac={}&last_request={}".format(fallbackUrl,deviceMac,lastRequest)
            print("{})".format(urlToCall))
            resp = requests.get(urlToCall, timeout=8, json=True)
        
        if resp.status_code == 200:
            controlsJson = resp.json()
            resp.close()
            time = rtc.datetime() 
            print("\n[{:02d}:{:02d}:{:02d}]".format(time[4],time[5],time[6]),end=" ")
            print('Control data requested succesfully. Code 200.')
            
            # Check RTC
            try:
                # Check if RTC-time is +- 1 second from json-timestamp. If difference is more, update RTC-time from current json.
                timeUnix = int(mktime(localtime()))
                timeWithOffset = int(controlsJson['Metadata']['Timestamp']) + int(controlsJson['Metadata']['Timestamp_offset'])
                diff = timeWithOffset - timeUnix
                if diff not in range(-1, 2):
                    time = rtc.datetime() 
                    print("\n[{:02d}:{:02d}:{:02d}]".format(time[4],time[5],time[6]),end=" ")
                    print("RTC out of range (JSON: {}, Local: {}), updating from host server...".format(timeWithOffset,timeUnix),end=" ")
                    rtcSynced = syncClock(timeWithOffset,diff)
                    
                else:
                    rtcSynced = True
                time = rtc.datetime() 
                print("[{:02d}:{:02d}:{:02d}]".format(time[4],time[5],time[6]),end=" ")
                    
            # General error expection, need for a better handling...
            except:
                rtcSynced = False
                
            print("RTC synced: {}".format(rtcSynced))
            
            # Do controls right after new JSON
            deviceChannels = int(controlsJson['Metadata']['Channels'])
            lastRequest = int(controlsJson['Metadata']['Timestamp'])
            time = rtc.datetime() 
            print("[{:02d}:{:02d}:{:02d}]".format(time[4],time[5],time[6]),end=" ")
            print('Channels to control: {}'.format(deviceChannels))
            updateStatus()
            doControls(False)
            
        elif resp.status_code == 400:
            time = rtc.datetime() 
            print("[{:02d}:{:02d}:{:02d}]".format(time[4],time[5],time[6]),end=" ")
            print('JSON not updated. Bad request. Code: {}'.format(resp.status_code))
            resp.close()
        elif resp.status_code == 429:
            time = rtc.datetime() 
            print("[{:02d}:{:02d}:{:02d}]".format(time[4],time[5],time[6]),end=" ")
            print('JSON not updated. Request rate limiter. Code: {}'.format(resp.status_code))
            resp.close()
        elif resp.status_code == 425:
            time = rtc.datetime() 
            print("[{:02d}:{:02d}:{:02d}]".format(time[4],time[5],time[6]),end=" ")
            print('JSON not updated. Too fast subsequent requests. Code: {}'.format(resp.status_code))
            resp.close()
        elif resp.status_code == 304:
            time = rtc.datetime() 
            print("[{:02d}:{:02d}:{:02d}]".format(time[4],time[5],time[6]),end=" ")
            print('JSON not updated. Control settings not changed after last request. Code: {}'.format(resp.status_code))
            resp.close()
        else:
            time = rtc.datetime() 
            print("[{:02d}:{:02d}:{:02d}]".format(time[4],time[5],time[6]),end=" ")
            print('JSON not updated. Code: {}'.format(resp.status_code))
            resp.close()
           
    # General error catch with nothing inside
    except:
        time = rtc.datetime() 
        print("[{:02d}:{:02d}:{:02d}]".format(time[4],time[5],time[6]),end=" ")
        print("ERROR!")


def doControls(timerInitiated):
    global controlsJson,doControlsTimerArmed,rtcSynced,hoursLeftOnJson

    doControlsTimerArmed = False
    
    if not rtcSynced:
        time = rtc.datetime() 
        print("[{:02d}:{:02d}:{:02d}]".format(time[4],time[5],time[6]),end=" ")
        print('RTC out of sync, control-loop not possible')
        return False
    
    # Control relays
    time = rtc.datetime()
    hour = time[4]
    print("[{:02d}:{:02d}:{:02d}]".format(time[4],time[5],time[6]),end=" ")
    print("Update relay states")
        
    # If there are more than 0 hour left on JSON, do controls based on it
    if controlsJson and hoursLeftOnJson > 0:
        channels = int(controlsJson['Metadata']['Channels'])
        
        # If mqtt in use, open connection (experimental)
        client = False
        if mqtt_control:
            try:
                client = mqttConnect()
            except:
                print('Could not establish mqtt connection')
            
        i = 0
        relay = []
        while i < channels:
            try:
                result = controlsJson['Channel{}'.format(i + 1)]['{!s}'.format(hour)]
                relay.append('relay{}'.format(i + 1))
                print("           Channel {},".format(i + 1), "hour {}: {}".format(hour,result))
                channelMode = globals()['channel{}_mode'.format(i + 1)]
                print(channelMode)
                if result == '1':
                    if channelMode == 'GPIO':
                        control = "{}.on()".format(relay[i])
                        exec(control)
                    elif channelMode == 'MQTT':
                        topic = globals()['channel{}_topic'.format(i + 1)]
                        if client:
                            client.publish(topic, msg='ON')
                            print('Published ON to topic {}'.format(topic))
                        else:
                            print('Could not publish to topic {}'.format(topic))
                else:
                    if channelMode == 'GPIO':
                        control = "{}.off()".format(relay[i])
                        exec(control)
                    elif channelMode == 'MQTT':
                        topic = globals()['channel{}_topic'.format(i + 1)]
                        if client:
                            client.publish(topic, msg='OFF')
                            print('Published OFF to topic {}'.format(topic))
                        else:
                            print('Could not publish to topic {}'.format(topic))
                i += 1
            except:
                print("Could not control channel {}".format(i + 1))
                i += 1
            controlError = 0
            
        if client:
            client.disconnect()

            
        return True
        
    # If JSON data is expired, try failsafe. If not set, set all relays to 0
    else:
        print("           Control-data too old")
        # Read current hour from failsafe.json
        if failsafe:
            try:
                with open("failsafe.json", "r") as jsonfile:
                    data = json.load(jsonfile)
                    hour = "{:02d}".format(hour)
                    relays = data[hour]
                    for item in relays:
                        control = "{}.on()".format(item)
                        exec(control)
                        print("           Failsafe-mode: {} on".format(item))
                    
                return True

            except:
                print("           Error while reading JSON-file")
            
        else:
            channels = int(controlsJson['Metadata']['Channels'])
            i = 0
            while i < channels:
                relays[i].off()
                print("           Relay {}:".format(i + 1), relays[i].value())
                i += 1
        
        return False


# Timer functions        
def doControlsTimer(Timer):
    doControls(True)
    
def getControlsTimer(Timer):
    global getControlsTimerArmed
    #If over 60 seconds until next quarted, call getControls
    if secondsUntilNextQuarter() > 60:
        getControls()
    
    getControlsTimerArmed = False
        
def runProgram(Timer):
    global rtcSynced, getControlsTimerArmed
           
    # Get controls if RTC not synced. Makes initial JSON-request happen faster.
    if not rtcSynced:
        getControls()
    
    # Update state
    updateStatus()
        

    #If getControls timer not armed -> arm. Set timer also when out of connection to try periodically if connection becomes established
    if not getControlsTimerArmed:
        #Set new random interval for timer: 90 sec + random 0-30 sec
        requestInterval = random.randrange(30) + 90
        
        time = rtc.datetime() 
        print("[{:02d}:{:02d}:{:02d}]".format(time[4],time[5],time[6]),end=" ")
        print('Set server request timer ({} seconds)'.format(requestInterval))
        
        requestTimer.deinit()
        requestTimer.init(mode=Timer.ONE_SHOT, period=requestInterval * 1000, callback=getControlsTimer)

        getControlsTimerArmed = True

# Helper functions
def secondsUntilNextQuarter():
    time = rtc.datetime()
    minute = time[5]
    second = time[6]
    
    if minute in range(0, 15):
        toNextQuarter = (14 - minute) * 60 + (60 - second)
    elif minute in range(15, 30):
        toNextQuarter = (29 - minute) * 60 + (60 - second)
    elif minute in range(30, 45):
        toNextQuarter = (44 - minute) * 60 + (60 - second)
    elif minute in range(45, 60):
        toNextQuarter = (59 - minute) * 60 + (60 - second)
    return toNextQuarter

def syncClock(t,diff):
    global bootTimestamp,bootTimestampSynced
    # Edit Unix-timestamp (t) to RTC-tuple and set RTC-time
    try:
        rtcTuple = localtime(t)
        rtcOrder = [0, 1, 2, 6, 3, 4, 5]
        rtcTuple = tuple(rtcTuple[i] for i in rtcOrder)
        rtc.datetime(rtcTuple + (0,))
        
        # Wait a bit for RTC to update time
        sleep(0.5)
        rtcSynced = True

    except:
        rtcSynced = False
    
    # Add diff to boot timestamp after first succesfull sync
    if rtcSynced and not bootTimestampSynced:
        print("Boot timestamp: {}, diff: {}, ".format(bootTimestamp,diff),end="")
        bootTimestamp = bootTimestamp + diff
        print("new timestamp: {}".format(bootTimestamp))
        bootTimestampSynced = True
    
    return rtcSynced
           
    
# Start the program
# RTC is probably not yet in time, but we save timestamp here and add add diff once time is synced
bootTimestamp = mktime(localtime())

# Start program loop timer
programTimer.init(mode=Timer.PERIODIC, period = 5 * 1000, callback=runProgram)

# HTTP-server for info and managing settings, known bug, needs to be rewritten into function to reset socket state when wifi changes
if connectionmanager.wlan_sta:
    ip = connectionmanager.wlan_sta.ifconfig()[0]
else:
    ip = '0.0.0.0'

addr = socket.getaddrinfo(ip, 80)[0][-1]
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(addr)
s.listen(5)

while True:
    cl, addr = s.accept()
    cl_file = cl.makefile('rwb', 0)
    time = rtc.datetime() 
    print("\n[{:02d}:{:02d}:{:02d}]".format(time[4],time[5],time[6]),end=" ")
    print("Client connected, ip: {}".format(addr[0]))
    while True:
        line = cl_file.readline()
        if not line or line == b'\r\n':
            break
    time = rtc.datetime()
    uptimeUnix = mktime(localtime()) - bootTimestamp
    upMinutes, upSeconds = divmod(uptimeUnix, 60)
    upHours, upMinutes = divmod(upMinutes, 60)
    upDays, upHours = divmod(upHours, 24)
    uptime = "{} days, {:02d} hours, {:02d} minutes, {:02d} seconds".format(upDays,upHours,upMinutes,upSeconds)
    if controlsJson:
        if connectionmanager.wlan_ap.isconnected():
            ip = '192.168.4.1'
        else:
            ip = connectionmanager.wlan_sta.ifconfig()[0]
        
        response = webpages.frontpage_with_json(controlsJson,relays,time,uptime,mac,ip)
            
    else:
        if connectionmanager.wlan_ap.isconnected():
            ip = '192.168.4.1'
        else:
            ip = connectionmanager.wlan_sta.ifconfig()[0]
            
        response = webpages.frontpage_without_json(time,uptime,mac,ip)
        
        
   
    cl.send('HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n')
    cl.sendall(response)
    cl.close()
    time = rtc.datetime() 
    print("\n[{:02d}:{:02d}:{:02d}]".format(time[4],time[5],time[6]),end=" ")
    print("Client disconnected")


# Shouldn't get here from server loop. If something goes wrong, then reboot machine.
machine.reset()
