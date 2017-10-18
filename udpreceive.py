'''
Name -- Drew Watson, Liz Wanic, Damon Alcorn
Date -- 5 Dec 2016
Description -- Custom tool developed to simulate network receiving of realtime IMU data
Filename -- udpreceive.py
'''

import socket
import json

def __receiveUDP__(receivePort=12335):
    # This function blocks

    myMachineIP = ""

    sock = socket.socket(socket.AF_INET,  # Internet
                         socket.SOCK_DGRAM)  # UDP
    sock.bind((myMachineIP, receivePort))

    data, addr = sock.recvfrom(1024)  # buffer size is 1024 bytes
    deserializedData = json.loads(data)

    print("received message:", deserializedData)

    return deserializedData


while True:
    __receiveUDP__()