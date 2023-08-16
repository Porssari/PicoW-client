try:
    import urequests as requests
except:
    import requests
try:
    import usocket as socket
except:
    import socket
import network
import time

# Siirrä configiin
ap_ssid = "Pico_porssari"
ap_password = "Pico_pass"
ap_authmode = 3  # WPA2

# Define wifi variables
wlan_ap = network.WLAN(network.AP_IF)
wlan_sta = network.WLAN(network.STA_IF)

        
def get_connection(profiles):
    """return a working WLAN(STA_IF) instance or None"""

    # First check if there already is any connection:
    time.sleep(3)
    if wlan_sta.isconnected():
        return wlan_sta
    wlan_sta.active(False)
    connected = False
     
    if profiles:  
        print("Found saved wifi-profiles, scan if there are known networks in range.")

        # Search WiFis in range
        wlan_sta.active(True)
        networks = wlan_sta.scan()

        AUTHMODE = {0: "open", 1: "WEP", 2: "WPA-PSK", 3: "WPA2-PSK", 4: "WPA/WPA2-PSK"}
        for ssid, bssid, channel, rssi, security, hidden in sorted(networks, key=lambda x: x[3], reverse=True):
            ssid = ssid.decode('utf-8')
            encrypted = security > 0
            #print(security)
            #print("ssid: %s chan: %d rssi: %d authmode: %s" % (ssid, channel, rssi, AUTHMODE.get(security, '?')))
            if ssid in profiles:
                if encrypted:
                    password = profiles[ssid]
                    connected = do_connect(ssid, password)
                else:
                    connected = do_connect(ssid, None)
            if connected:
                break
    #try:
    #    print("something")
    #except OSError as e:
    #    print("exception", str(e))

    # start web server for connection manager:
    if not connected:
        wlan_sta.active(False)
        # If already started, no need to start again
        if wlan_ap.isconnected():
            return wlan_ap
        
        wlan_ap.config(essid=ap_ssid, password=ap_password)
        wlan_ap.active(True)
        print('Created WiFi-AP with ssid ' + ap_ssid + ' and password: ' + ap_password + ' with host 192.168.4.1.')
        return wlan_ap

    return wlan_sta if connected else None

def do_connect(ssid, password):
    print('Trying to connect to %s' % ssid, end='')
    wlan_sta.connect(ssid, password)
    for retry in range(100):
        connected = wlan_sta.isconnected()
        if connected:
            break
        time.sleep(0.1)
        print('.', end='')
    if connected:
        print('\nConnected. IP: {}'.format(wlan_sta.ifconfig()[0]))
    else:
        print('\nFailed. Not Connected to: ' + ssid)
    return connected
