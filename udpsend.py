'''
Name -- Drew Watson, Liz Wanic, Damon Alcorn
Date -- 5 Dec 2016
Description -- Custom tool developed to simulate network sending of realtime IMU data, to include IMU movement.
Filename -- udpsend.py
'''

import json
import socket
import time

my_ip = ""
damon_ip = "172.20.150.22"
liz_ip = "172.20.156.160"

x= {u'yaw': 0, u'lon': -121.87532043457031, u'pitch': 3.990230083465576, u'lat': 36.594940185546875, u'alt': -7.0032172203063965, u'roll': -0.15934012830257416}

def __transmitUDP__(data, sendToIP, sendToPort):
    data_string = json.dumps(data)  # data serialized
    # data_loaded = json.loads(data)  #data loaded

    sock = socket.socket(socket.AF_INET,  # Internet
                         socket.SOCK_DGRAM)  # UDP
    sock.sendto(data_string, (sendToIP, sendToPort))



while True:
    print("sending some  data")
    __transmitUDP__(x, my_ip, 12333)
    time.sleep(0.2)
    x[u'lon']+=0.0001

    x[u'yaw'] += 10