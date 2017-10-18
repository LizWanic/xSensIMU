'''
Name -- Drew Watson, Liz Wanic, Damon Alcorn
Date -- 5 Dec 2016
Description -- File contains the sender and receiver classes for the xSens MTi-G IMU.  Use required command line
arguments --receiver or --sender, as well as the following optional command line args:
     usage: xSens.py [-h] [-ip [IPADDRESS]] [-mp [MYPORT]] [-dp [DESTPORT]]
                     [-rp [RECVPORT]] [-b [BAUDRATE]] [-f [FILENAME]] [-r | -s]
When running as sender, xSens.py will immediately open the IMU hardware and start transmitting location/orientation
packets over the network.  When specified, the sender will also archive the data to disk.
When running as receiver, xSens.py will block until receiving the start point packet containing the initial lat/lon.
Once received, the GUI is launched and the sender's location and orientation is plotted in realtime on satellite
imagery.  When the IMU travels off map, a new map is downloaded and tracking continues.
Filename -- xSens.py
'''

import serial
import struct
import socket
import json
from ModestMaps import *
import wx
import argparse
from multiprocessing import Process, Pipe
import signal
import time

## Default globals (can be changed via command line input)
DESTINATION_PORT = 12333      #default Port Number
DESTINATION_IP = "127.0.0.1"  #loopback IP address
RECEIVER_PORT = 12333         #default Receiver port


class xSens_Sender(object):

    def __init__(self, port=None, baudrate=None, fileName = "IMU_data.txt", transmit = True):
        """Initializes a sender object"""

        self.device=None

        ## Opens the device
        try:
            self.device = serial.Serial(port, baudrate)
            print(self.device)

        except Exception as e:
            print "Had an issue opening your xSens IMU device, is it plugged in and connected to", port, \
                "with baudrate", baudrate, "?"
            print "Error Code: ", str(e)

        ## Creates an output file and adds a header
        if fileName != None:
            try:
                self.outputFile = open(fileName, "w")
                self.outputFile.write('    YAW          LON            PITCH          LAT            ALT            ROLL')
                self.outputFile.write('_________________________________________________________________________________\n\n')
            except Exception as e:
                print "Couldn't open and write output file, quitting. Error", str(e)
                quit(1)

        else:
            self.outputFile = None

        ## Indicates transmission
        self.transmitFlag = transmit

        ## Sets up signal handling for SIGINT
        signal.signal(signal.SIGINT, self.sigint_handler)

    def sigint_handler(self, signum, frame):
        """Signal catcher for SIGINT"""

        print "Caught SIGINT signal, shutting down"
        print "Closing output file"
        self.outputFile.close()
        print "Closing serial device", self.device.name
        self.device.close()

    def readPacket(self):
        """Reads a data packet from the IMU and parses the data"""

        startTime = time.time()

        while time.time() - startTime < 7:

            input = self.device.read(1) #reads one byte from the IMU
            preamble = ord(input) #gives decimal equivalent of input byte

            if preamble == 250:  #start of a new packet indicated by this value

                packetList = []

                packetList.append(preamble)  #appends each byte to the packetList

                bid = ord(self.device.read(1))
                packetList.append(bid)

                mid = ord(self.device.read(1))
                packetList.append(mid)

                length = ord(self.device.read(1))
                packetList.append(length)

                rawData = self.device.read(length)  # data is unord-ed at this point - still in raw form
                packetList.append(rawData)

                checkSum = ord(self.device.read(1))
                packetList.append(checkSum)

                dataBytes = packetList[4]  #parse out data from packetList and save as dataBytes for further parsing

                firstDataByte = dataBytes[0:4]
                secondDataByte = dataBytes[4:8]
                thirdDataByte = dataBytes[8:12]
                fourthDataByte = dataBytes[12:16]
                fifthDataByte = dataBytes[16:20]
                sixthDataByte = dataBytes[20:24]

                roll = struct.unpack('>f', firstDataByte)
                roll = roll[0]

                pitch = struct.unpack('>f', secondDataByte)
                pitch = pitch[0]

                yaw = struct.unpack('>f', thirdDataByte)
                yaw = yaw[0]

                lat = struct.unpack('>f', fourthDataByte)
                lat = lat[0]

                lon = struct.unpack('>f', fifthDataByte)
                lon = lon[0]

                alt = struct.unpack('>f', sixthDataByte)
                alt = alt[0]

                outputDict = {"roll": roll, "pitch": pitch, "yaw": yaw, "lat": lat, "lon": lon, "alt": alt}

                #print("Roll:", roll, ", Pitch:", pitch, ", Yaw:", yaw, ", Lat:", lat, ", Lon:", lon, ", Alt:", alt)

                return outputDict

    def isOpen(self):
        """Returns whether a device is open"""

        if self.device:
            return True
        else:
            return False


    def dataManager(self):
        """Writes the parsed data to an output file and calls transmitUDP function"""

        data = self.readPacket()

        try:
            if self.outputFile != None:
                for item in data:
                    self.outputFile.write(str(data[item]) + ",")

                self.outputFile.write("\n")

        except Exception as e:
            print 'Error writing to file', str(e)

        if self.transmitFlag == True:
            print "sending data to IP:", DESTINATION_IP,  "Port:", DESTINATION_PORT
            self.__transmitUDP__(data, sendToIP = DESTINATION_IP, sendToPort = DESTINATION_PORT)
            for item in data:
                print item, data[item]

    def run(self, loopTime = -1): #time in seconds
        """Runs the loop for calling the dataManager function"""

        startTime = time.time()

            ## Infinite loop
        try:
            if loopTime == -1:
                while True:
                    self.dataManager()

            ## Timed loop
            else:
                while time.time() - startTime < loopTime:
                    self.dataManager()

        except Exception as e:
            print "Shutting down"


    def getRollPitchYaw(self):
        """Gets the roll, pitch and yaw values from the packet"""

        values = self.readPacket()

        roll = values["roll"]
        pitch = values["pitch"]
        yaw = values["yaw"]

        outputDict = {"roll": roll, "pitch": pitch, "yaw": yaw}

        return outputDict

    def getLatLonAlt(self):
        """Gets the lat, lon and alt values from the packet"""

        values = self.readPacket()

        lat = values["lat"]
        lon = values["lon"]
        alt = values["alt"]

        outputDict = {"lat": lat, "lon": lon, "alt": alt}

        return outputDict


    def __transmitUDP__(self, data, sendToIP, sendToPort):
        """Uses JSON to convert the data and send it over a UDP connection"""

        try:
            data_string = json.dumps(data)  # data serialized

            sock = socket.socket(socket.AF_INET,  # Internet
                                 socket.SOCK_DGRAM)  # UDP
            sock.sendto(data_string, (sendToIP, sendToPort))

        except Exception as e:
            print "Error sending data packet: ", str(e)



class xSens_Receiver(object):

    def __init__(self, initial_lat=None, initial_lon=None, initial_zoom=18, x_mapsize=800, y_mapsize=600, x_window_size=800, y_window_size=600):
        """Initializes a Receiver object"""

        ## Sets up an empty list and initializes first packet as None
        self.last_location_and_packet = []
        first_packet_from_remote=None

        ## Machine IP will be determined by your OS
        myMachineIP = ""

        ## Opens and binds to a socket
        try:
            self.sock = socket.socket(socket.AF_INET,  # Internet
                             socket.SOCK_DGRAM)  # UDP
            self.sock.bind((myMachineIP, RECEIVER_PORT))

            if initial_lat==None and initial_lon==None:
                print('--waiting to create map based on Xsens location')   # this blocks until the first packet is received
                first_packet_from_remote = self.getDataPacket()
                initial_lat=first_packet_from_remote[u'lat']
                initial_lon=first_packet_from_remote[u'lon']
                print 'setting initial_lat to', initial_lat
                print 'setting initial lon to', initial_lon

        except Exception as e:
            print 'Error binding to socket/reading data', str(e)
            print 'Exiting program'
            quit(1)

        ## Sets up framework for pop-up window and pulling the map
        self.app = wx.App(False)
        self.frame = wx.Frame(None, title="xSens IMU mapping", size=(x_window_size, y_window_size),\
                              style=wx.DEFAULT_FRAME_STYLE ^ wx.RESIZE_BORDER)
        self.panel = wx.Panel(self.frame)

        ## Sets up the map with the current location as the center
        self.center = Geo.Location(initial_lat, initial_lon)
        self.zoom = initial_zoom
        self.dimensions = Core.Point(x_mapsize, y_mapsize)

        self.map = mapByCenterZoom(Microsoft.AerialProvider(), self.center, self.zoom, self.dimensions)

        if first_packet_from_remote:
            x, y = self.get_xy_of_latlon(lat=first_packet_from_remote[u'lat'], lon=first_packet_from_remote[u'lon'])
            self.last_location_and_packet = x, y, first_packet_from_remote

        ## Conversion of map format
        self.pic_pil_format = self.map.draw(verbose=True)
        self.pic_wx_format = self.PilImageToWxBitmap(self.pic_pil_format)

        ## Sets the timer for asking for a redraw
        TIMER_REDRAW_ID = 52  # pick a number
        timerCheck = wx.Timer(self.panel, TIMER_REDRAW_ID)  # message will be sent to the panel
        timerCheck.Start(500)  #  milliseconds
        self.panel.Bind(wx.EVT_TIMER, self.timer_redraw, timerCheck)
        self.panel.Bind(wx.EVT_PAINT, self.on_paint)

        self.frame.Bind(wx.EVT_CLOSE, self.close_window_and_shutdown)

        # Create a shared variable for both processes
        self.parent_conn, child_conn = Pipe()

        # Create a new process for pulling the data
        self.p = Process(target = self.timer_usercode, args = (child_conn,))
        self.p.start()

        ## Start the GUI loop
        self.frame.Show(True)
        self.app.MainLoop()

    def close_window_and_shutdown(self, event):
        """Shut down function, Asks the user via pop-up if they want to exit when red x is clicked on the window"""

        dlg = wx.MessageDialog(self.frame, "Are you sure you want to exit?", "Exit", wx.YES_NO )

        ## If no is clicked
        if dlg.ShowModal() != wx.ID_YES:
            dlg.Destroy()
            self.panel.Close(False)
            return
        ## If yes is clicked
        else:
            self.frame.Destroy()
            dlg.Destroy()
            self.panel.Close(True)
            self.sock.close()
            self.p.terminate()

    def on_paint(self, event):
        """Receives the information from the data pulling process and draws the IMU's location on the map"""

        self.last_location_and_packet = self.parent_conn.recv()

        x,y = self.get_xy_of_latlon(lat= self.last_location_and_packet[0], lon= self.last_location_and_packet[1])

        ## Grabs a new map if the IMU moves off the current one
        if not self.is_IMU_on_map(x, y):
            new_lat = self.last_location_and_packet[0]
            new_lon = self.last_location_and_packet[1]
            self.center = Geo.Location(new_lat, new_lon)
            self.map = mapByCenterZoom(Microsoft.AerialProvider(), self.center, self.zoom, self.dimensions)
            self.pic_pil_format = self.map.draw(verbose=True)
            self.pic_wx_format = self.PilImageToWxBitmap(self.pic_pil_format)

        ## Painting the object on the map
        dc = wx.PaintDC(event.GetEventObject())
        dc.Clear()

        ## Draw a directional line with the current heading from the current point
        dc.SetPen(wx.Pen("BLUE", 4))
        dc.DrawBitmap(self.pic_wx_format,0,0)
        packet = self.last_location_and_packet[2]
        yaw = packet[u'yaw']
        angle_rad = math.radians(yaw)
        x_line = x + 30 * math.sin(angle_rad)
        y_line = y - 30 * math.cos(angle_rad)
        dc.DrawLine(x, y, x_line, y_line)

        ## Draw a circle with current location
        dc.SetPen(wx.Pen("RED", 4))
        dc.DrawCircle(x, y, 10)


    def timer_redraw(self, event):
        """Generates an EVT_PAINT which is sent the window"""
        self.frame.Refresh()

    def timer_usercode(self, conn):
        """Gets the data and sends it through the pipe to the shared variable"""

        while True:
            new_packet=self.getDataPacket()
            self.last_location_and_packet= new_packet[u'lat'], new_packet[u'lon'], new_packet
            conn.send(self.last_location_and_packet)

    def WxImageToWxBitmap(self, myWxImage):
        '''conversion function from Wx Tutorial'''
        return myWxImage.ConvertToBitmap()

    def PilImageToWxBitmap(self, myPilImage):
        '''conversion function from Wx Tutorial'''
        return self.WxImageToWxBitmap(self.PilImageToWxImage(myPilImage))

    def PilImageToWxImage(self, myPilImage):
        '''conversion function from Wx Tutorial'''
        myWxImage = wx.EmptyImage(myPilImage.size[0], myPilImage.size[1])
        myWxImage.SetData(myPilImage.convert('RGB').tobytes())
        return myWxImage

    def get_xy_of_latlon(self, lat, lon):
        """Converts from lat and lon to pixel positions"""
        point_xy = self.map.locationPoint(Geo.Location(lat, lon))
        point_xy = (int(point_xy.x), int(point_xy.y))
        return point_xy

    def is_IMU_on_map(self,x,y):
        """Verifies whether IMU is still on current map"""
        if x<0 or x>self.dimensions.x or y<0 or y>self.dimensions.y:
            return False
        else:
            return True

    def getDataPacket(self):
        """Calls receiveUDP to obtain the next data packet"""
        return self.__receiveUDP__()

    def __receiveUDP__(self):
        """Receives the data through the UDP connection and de-serializes it with JSON"""

        try:
            data, addr = self.sock.recvfrom(1024)  # buffer size is 1024 bytes
            deserializedData = json.loads(data)

            return deserializedData

        except Exception as e:
            print "Error reading data packet: ", str(e)



if __name__ == "__main__":

    ##  Parsing the arguments from the command line
    parser = argparse.ArgumentParser()
    parser.add_argument("-ip", "--ipaddress", nargs='?', help="Specify destination IP address")
    parser.add_argument("-mp", "--myport", nargs='?', help="Specify your serial port information")
    parser.add_argument("-dp", "--destport", nargs='?', type=int, help="Specify destination port information")
    parser.add_argument("-rp", "--recvport", nargs='?', type=int, help="Specify receiver port information")
    parser.add_argument("-b", "--baudrate", nargs='?', type=int, help="Specify baudrate - check compatible with hardware setting")
    parser.add_argument("-f", "--filename", nargs='?', help="Specify file name for data writing")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-r", "--receiver", action="store_true", help="Indicates receiver mode")
    group.add_argument("-s", "--sender", action="store_true", help = "Indicates sender mode")
    args = parser.parse_args()

    ## Error checking
    if args.receiver != True and args.sender != True:
        print "Please specify --sender or --receiver when running xSens.py"
        quit(1)

    ## Mode setting
    elif args.sender:
        ## Run as sender
        print "running in sender mode"
        print 'hit Control C to stop sending'

        ## Setting serial port
        if args.myport != None:
            port = args.myport
        else:
            port = "/dev/ttyUSB0"

        ## Setting the baudrate
        if args.baudrate != None:
            baudrate = args.baudrate
        else:
            baudrate = 115200

        ## Indicating the file name
        if args.filename != None:
            fileName = args.filename
        else:
            fileName = "IMU_data.txt"
        print 'Your data is being saved to', fileName

        ## Setting destination IP address
        if args.ipaddress != None:
            DESTINATION_IP = args.ipaddress

        # Setting destination port
        if args.destport != None:
            DESTINATION_PORT = args.destport

        ## Creates a sender object
        orangeIMU = xSens_Sender(port, baudrate, fileName)

        ## Runs the sending functionality
        if orangeIMU.isOpen():
            orangeIMU.run()

    elif args.receiver:
        ## Run as receiver
        print "Running in receiver mode"
        if args.recvport !=None:
            RECEIVER_PORT=args.recvport

        ## Creates a receiver object
        xSens_Receiver()





# NPS quad
# 36.595479 -121.875781








