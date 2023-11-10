###########################################################################
#
# Description:     Pörssäri Micropython client for Raspberry Pico W
#                  
# Requirements:    Tested with Pico W Micropython v1.19.1-994-ga4672149b
#
# Known issues:    Web server gets stuck when losing wifi connection
#
############################################################################

VERSION = "Micropython-2.0_beta1"

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
#import webpages
    
# Import libs to read and convert data
import json
from ubinascii import hexlify
import random
#from math import floor

#import time
from time import sleep, mktime, gmtime, time

# Import pin-control
from machine import Pin, Timer
from neopixel import NeoPixel

# Import carbage collector
import gc

# Define variables
# Real time clock
rtc = machine.RTC()
# We will keep rtc in utc-time, offset is needed for user interface
offset = 0

# Timers
programTimer = Timer()

# Onboard led
onboard = Pin("LED", Pin.OUT, value=0)

# Neopixel RGB (red light while initial setup)
np = NeoPixel(machine.Pin(13), 1)
np[0] = (255, 0, 0)
np.write()


# Relay pins
relay0 = Pin(21, Pin.OUT)
relay1 = Pin(20, Pin.OUT)
relay2 = Pin(19, Pin.OUT)
relay3 = Pin(18, Pin.OUT)
relay4 = Pin(17, Pin.OUT)
relay5 = Pin(16, Pin.OUT)
relay6 = Pin(15, Pin.OUT)
relay7 = Pin(14, Pin.OUT)

# Tuple for web interface (add all the relays above for proper functionality)
#relays = (relay1, relay2, relay3, relay4, relay5, relay6, relay7, relay8)

# Get config from json 
try:
    with open("config.json", "r") as jsonfile:
        data = json.load(jsonfile)
        
        # Get fallback-url
        apiEndpoint = data['Fetch_url_fallback']
        
        # Get failsafe-setting
        failsafe = data['Failsafe']
        
        updatePeriod = 15000
        deviceChannels = 0
        returnTimestamps = 20
        jsonVersion = 2
        jsonChannelNames = False
        
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
controlsReady = False
getControlsInit = False
doControlsInit = False
lastRequest = 0
lastRequestHttpCode = 0
jsonValidUntil = 0
controlsJson = {}
channelLastControlTimeStamps = {}
mainCycleCounter = 20 
cyclesUntilRequest = 20
rtcSynced = False
bootTimestampSynced = False

# Helper functions

def syncClock(timestamp,diff):
    global bootTimestamp,bootTimestampSynced
    # Edit Unix-timestamp to RTC-tuple and set RTC-time
    try:
        rtcTuple = gmtime(timestamp)
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

def controlSwitch(switchId, setState):
    switch = str('relay{}'.format(switchId))
    if setState == True: 
        control = switch.on()
        print(control)
        exec(control)
    else:
        control = switch.off()
        print(control)
        exec(control)
        
def consoleLog(message):
    time = getLocalTime()
    print("[{:02d}:{:02d}:{:02d}]".format(time[3],time[4],time[5]),end=" ")
    print(message)
    
def consoleLogContinueline(message):
    time = getLocalTime()
    print("[{:02d}:{:02d}:{:02d}]".format(time[3],time[4],time[5]),end=" ")
    print('{}'.format(message),end=" ")

def getLocalTime():
    global offset
    return gmtime(time() + int(offset))


# Service control functions
def updateStatus():
    global wifi, getControlsInit, jsonValidUntil
    
    # Micropython health checks
    # Collect garbages
    if gc.mem_free() < 102000:
        gc.collect()
    
    #time = rtc.datetime()    
    #print("[{:02d}:{:02d}:{:02d}]".format(time[4],time[5],time[6]),end=" ")
    #print("Memory: free:{}, alloc:{}".format(gc.mem_free(), gc.mem_alloc()))
    message = "Memory: free:{}, alloc:{}".format(gc.mem_free(), gc.mem_alloc())
    consoleLog(message)
    
    # If device is not connected to wifi-network, try to connect       
    if not connectionmanager.wlan_sta.isconnected():
        
        consoleLog("No internet connection, trying to connect")
        wifi = connectionmanager.get_connection(profiles)
        
        if not connectionmanager.wlan_sta.isconnected():
            consoleLog("Could not connect")
            
    else:
        consoleLog("Network connected")
        
    # Program state checks
    # RTC has to be synced to control relays
    if rtcSynced:
        consoleLog("RTC synced")
        
    else:
        consoleLog("RTC not synced")
    
    # Check if controls json is valid
    currentUnixTime = time()
    if (getControlsInit == True and jsonValidUntil <= currentUnixTime):
        consoleLog("Control schedule empty. Rebooting device.")
        machine.reset()
        
def getControls():
    global controlsJson,lastRequest,rtcSynced,offset,jsonValidUntil,apiEndPoint,lastRequestCode,deviceChannels,getControlsInit,controlsReady,cyclesUntilRequest,mainCycleCounter
    
    # If controller is in ap-mode there is no internet connection, not worth trying to get new JSON..
    if connectionmanager.wlan_ap.isconnected():
        consoleLog("No internet connection, JSON request not possible.")
        return
    
    urlToCall = "{}?device_mac={}&last_request={}&client={}&json_version={}".format(apiEndpoint,mac,lastRequest,VERSION,jsonVersion)
       
    consoleLog("Get JSON from {}".format(urlToCall))
    
    # JSON-request 
    try:
        try:
            resp = requests.get(urlToCall, timeout=8, json=True)
        except:
            consoleLog("Error! Request failed")
        
        if resp.status_code == 200:
            controlsJson = resp.json()
            lastRequestCode = resp.status_code
            resp.close()
            consoleLog('Control data requested succesfully. Code 200.')
            
            # Check RTC
            try:
                # Check if RTC-time is +- 1 second from json-timestamp. If difference is more, update RTC-time from current json.
                currentUnixTime = time()
                jsonTime = int(controlsJson['metadata']['timestamp'])
                offset = int(controlsJson['metadata']['timestamp_offset'])
                diff = jsonTime - currentUnixTime
                if diff not in range(-1, 2):
                    consoleLog("RTC out of range (JSON: {}, Local: {}), updating RTC from host server".format(jsonTime,currentUnixTime))
                    rtcSynced = syncClock(jsonTime,diff)
                    
                else:
                    rtcSynced = True
                    consoleLog("RTC synced")
                    
            # General error expection, need for a better handling...
            except:
                rtcSynced = False
                
            
            # Do controls right after new JSON
            deviceChannels = int(controlsJson['metadata']['channels'])
            lastRequest = int(controlsJson['metadata']['timestamp'])
            jsonValidUntil = int(controlsJson['metadata']['valid_until'])
            apiEndPoint = controlsJson['metadata']['fetch_url']
            getControlsInit = True
            consoleLog('Channels to control: {}'.format(deviceChannels))
            
            # Set RGB to blue if there's a succesfull request
            np[0] = (0, 0, 255)
            np.write()
            
        elif resp.status_code == 400:
            consoleLog('JSON not updated. Bad request. Code: {}'.format(resp.status_code))
            lastRequestCode = resp.status_code
            resp.close()
        elif resp.status_code == 429:
            consoleLog('JSON not updated. Request rate limiter. Code: {}'.format(resp.status_code))
            lastRequestCode = resp.status_code
            resp.close()
        elif resp.status_code == 425:
            consoleLog('JSON not updated. Too fast subsequent requests. Code: {}'.format(resp.status_code))
            lastRequestCode = resp.status_code
            resp.close()
        elif resp.status_code == 304:
            consoleLog('JSON not updated. Control settings not changed after last request. Code: {}'.format(resp.status_code))
            lastRequestCode = resp.status_code
            resp.close()
        else:
            consoleLog('JSON not updated. Code: {}'.format(resp.status_code))
            lastRequestCode = resp.status_code
            resp.close()
            
        controlsReady = True
        cyclesUntilRequest = random.randrange(18,20)
        mainCycleCounter = 0
        #print('Server request done. ', requestInfo);
           
    # General error catch with nothing inside
    except:
        consoleLog("Unknown error with request")

def doControls():
    global controlsJson,rtcSynced,jsonValidUntil,doControlsInit,channelLastControlTimeStamps
    
    if not rtcSynced:
        consoleLog('RTC out of sync, control-loop not possible')
        return False
    
    # Control relays
        
    # If there are more than 0 hour left on JSON, do controls based on it
    if doControlsInit == True:
        
        consoleLog("Executing schedule loop")
        
        # Check if current timestamp is past next control timestamp and doing controls
        # Get current timestamp from rtc and loop through channels
        currentUnixTime = int(mktime(gmtime()))
        for channel in controlsJson['controls']:
            if channel['id']:
                
                # Loop through schedules
                switchId = int(channel['id']) - 1
                for scheduleEntry in channel['schedules']:
                    if scheduleEntry['timestamp']:
                        
                        # If current timestamp is greater or equal than schedule entrys timestamp then check if control already done
                        scheduleTimestamp = int(scheduleEntry['timestamp'])
                        channelUpdated = int(channel['updated'])
                        if currentUnixTime >= scheduleTimestamp:
                            
                            if scheduleTimestamp > channelLastControlTimeStamps[switchId]:
                                consoleLog("Passed uncontrolled schedule timestamp, updating relay state")
                                
                                # Control switch and update last control timestamp
                                controlState = int(scheduleEntry['state'])
                                if controlState == 1:
                                    control = "relay{}.on()".format(switchId)
                                    exec(control)
                                elif controlState == 0:
                                    control = "relay{}.off()".format(switchId)
                                    exec(control)
                                
                                channelLastControlTimeStamps[switchId] = scheduleTimestamp
                                print("           Channel {},".format(switchId), "state: {}".format(controlState))

                        # If channel settings changed after last control then set switch to current state
                        elif channelUpdated > channelLastControlTimeStamps[switchId]:
                            consoleLog('Switch id {} user settings changed. Controlling to current state.'.format(switchId));
                            
                            controlState = channel['state']
                            if controlState == 1:
                                control = "relay{}.on()".format(switchId)
                                exec(control)
                            elif controlState == 0:
                                control = "relay{}.off()".format(switchId)
                                exec(control)
                            
                            channelLastControlTimeStamps[switchId] = currentUnixTime
                            print("           Channel {},".format(switchId), "state: {}".format(controlState))

                            
    else:
        consoleLog("Initializing relays to current states")
        
        currentUnixTime = int(mktime(gmtime()))
        for channel in controlsJson['controls']:
            if channel['id']:
                
                # Loop through channels
                switchId = int(channel['id']) - 1
                controlState = int(channel['state'])
                if controlState == 1:
                    control = "relay{}.on()".format(switchId)
                    exec(control)
                elif controlState == 0:
                    control = "relay{}.off()".format(switchId)
                    exec(control)
                            
                channelLastControlTimeStamps[switchId] = currentUnixTime
                print("           Channel {},".format(switchId), "state: {}".format(controlState))

                
        doControlsInit = True
        print(channelLastControlTimeStamps)

    return True
            
    # If JSON data is expired, try failsafe. If not set, set all relays to 0
    #else:
    #    print("           Control-data too old")
        # Read current hour from failsafe.json
    #    if failsafe:
    #        try:
    #            with open("failsafe.json", "r") as jsonfile:
    #                data = json.load(jsonfile)
    #                hour = "{:02d}".format(hour)
    #                relays = data[hour]
    #                for item in relays:
    #                    control = "{}.on()".format(item)
    #                    exec(control)
    #                    print("           Failsafe-mode: {} on".format(item))
    #            
                # Set RGB to cyan
    #            np[0] = (0, 255, 255)
    #            np.write()
                
    #            return True

    #        except:
    #            print("           Error while reading JSON-file")
            
    #    else:
    #        # Set RGB to white
    #        np[0] = (0, 0, 0)
    #        np.write()
    #        channels = int(controlsJson['Metadata']['Channels'])
    #        i = 0
    #        while i < channels:
    #            relays[i].off()
    #            print("           Relay {}:".format(i + 1), relays[i].value())
    #            i += 1
        
    #    return False
    

    

# Timer functions                
def runProgram(Timer):
    global rtcSynced, mainCycleCounter, cyclesUntilRequest, getControlsInit, controlsReady
    
    consoleLog('Cycle {}/{} until next request'.format(mainCycleCounter, cyclesUntilRequest))

    if getControlsInit == True:
        
        # Update time
        updateStatus()
        
        # Do controls
        if controlsReady == True:
            doControls()
          
    else:
        consoleLog('Initial controls data not fetched from server, impossible to do controls');


    if mainCycleCounter >= cyclesUntilRequest:
        controlsReady = False
        getControls()

    mainCycleCounter += 1
           
    
# Start the program
# RTC is probably not yet in time, but we save timestamp here and add add diff once time is synced
bootTimestamp = mktime(gmtime())

# Start program loop timer
programTimer.init(mode=Timer.PERIODIC, period = 15 * 1000, callback=runProgram)

# HTTP-server for info and managing settings, known bug, needs to be rewritten into function to reset socket state when wifi changes
#if connectionmanager.wlan_sta:
#    ip = connectionmanager.wlan_sta.ifconfig()[0]
#else:
#    ip = '0.0.0.0'

#addr = socket.getaddrinfo(ip, 80)[0][-1]
#s = socket.socket()
#s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
#s.bind(addr)
#s.listen(5)

#while True:
#    cl, addr = s.accept()
#    cl_file = cl.makefile('rwb', 0)
#    time = rtc.datetime() 
#    print("\n[{:02d}:{:02d}:{:02d}]".format(time[4],time[5],time[6]),end=" ")
#    print("Client connected, ip: {}".format(addr[0]))
#    while True:
#        line = cl_file.readline()
#        if not line or line == b'\r\n':
#            break
#    time = rtc.datetime()
#    uptimeUnix = mktime(localtime()) - bootTimestamp
#    upMinutes, upSeconds = divmod(uptimeUnix, 60)
#    upHours, upMinutes = divmod(upMinutes, 60)
#    upDays, upHours = divmod(upHours, 24)
#    uptime = "{} days, {:02d} hours, {:02d} minutes, {:02d} seconds".format(upDays,upHours,upMinutes,upSeconds)
#    if controlsJson:
#        if connectionmanager.wlan_ap.isconnected():
#            ip = '192.168.4.1'
#        else:
#            ip = connectionmanager.wlan_sta.ifconfig()[0]
        
#        response = webpages.frontpage_with_json(controlsJson,relays,time,uptime,mac,ip)
            
#    else:
#        if connectionmanager.wlan_ap.isconnected():
#            ip = '192.168.4.1'
#        else:
#            ip = connectionmanager.wlan_sta.ifconfig()[0]
            
#        response = webpages.frontpage_without_json(time,uptime,mac,ip)
        
        
   
#    cl.send('HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n')
#    cl.sendall(response)
#    cl.close()
#    time = rtc.datetime() 
#    print("\n[{:02d}:{:02d}:{:02d}]".format(time[4],time[5],time[6]),end=" ")
#    print("Client disconnected")


# Shouldn't get here from server loop. If something goes wrong, then reboot machine.
#machine.reset()
