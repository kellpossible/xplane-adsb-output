import socket
from adsb_output import NetworkInterfacePacket, EasyDref, EasyCommand, UTC
from datetime import datetime
from XPLMDefs import *
from XPLMProcessing import *
from XPLMDataAccess import *
from XPLMUtilities import *
from XPLMPlanes import *
from XPLMPlugin import *
from XPLMMenus import *
from XPWidgetDefs import *
from XPWidgets import *
from XPStandardWidgets import *
from XPLMScenery import *
from XPLMDisplay import *
from SandyBarbourUtilities import *
from PythonScriptMessaging import *


from Queue import Queue
from google.protobuf.internal import encoder
from google.protobuf.internal import decoder
from threading import Thread
import socket
import sys
import time
import math

"""
Author: Luke Frisken
Information:
This is a plugin for x-plane to be used with Sandy Barbour's python interface
for x-plane. See http://www.xpluginsdk.org/python_interface.htm for more info.
The version of python required is 2.7.

Currently you will need to edit the script to set up the target port and address
of the LibGDX_ATC_Simulator instance which will receive the ADSB output

pip packages required are:
- protobuf
"""

__VERSION__='alpha1'

# These methods are from here: http://stackoverflow.com/questions/2340730/are-t
# here-c-equivalents-for-the-protocol-buffers-delimited-i-o-functions-in-ja/3453
# 9706#34539706

UPDATE_RATE = 2.0
PORT = 6989
ADDRESS = 'localhost'

EARTH_MSL = 6371000.0


def writeDelimitedTo(message, connection):
    message_str = message.SerializeToString()
    delimiter = encoder._VarintBytes(len(message_str))
    connection.send(delimiter + message_str)

class ServerThread(Thread):
    def __init__(self, message_queue):
        Thread.__init__(self)
        self.daemon = True
        self.message_queue = message_queue
        self.running = False
        self.listening = False
        self.address = ADDRESS
        self.port = PORT
        self.connection = None
        self.client_address = None

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print("IS THIS EVEN WORKING???")
        print("starting server on {} port {}".format(self.address, self.port))
        sock.bind((self.address, self.port))
        print("socket has been bound")

        # listen for incoming connections
        sock.listen(1)
        self.listening = True
        print("has started listening to socket")

        while True:
            # wait for a connection
            self.connection, self.client_address = sock.accept()
            print("connection initiated from {}", self.client_address)
            self.running = True
            time.sleep(1.0)
            # while True:
            #     message = self.message_queue.get(True, None)
            #     writeDelimitedTo(message, connection)

        self.running = False
        print("server thread finished")

    def stop(self):
        print("stopping server")
        self.running = False
        # socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((self.address, self.port))
        # self.socket.close()

    def is_running(self):
        return self.running and self.is_alive()


class PythonInterface:
    def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
        pass

    def XPluginStart(self):
        self.Name = "ADSB Output"
        self.Sig = "LukeFrisken.Python.ADSBOutput"
        self.Desc = "ADSB Output Thing"

        # Sim pause
        self.paused = EasyDref('sim/time/paused', 'int')

        self.aboutWindow = False

        self.mMenu = self.mainMenuCB

        self.mPluginItem = XPLMAppendMenuItem(XPLMFindPluginsMenu(), 'ADSB Output', 0, 1)
        self.mMain       = XPLMCreateMenu(self, 'ADSB Output', XPLMFindPluginsMenu(), self.mPluginItem, self.mMenu, 0)

        self.mAboutIndex = 1
        self.mAbout     =  XPLMAppendMenuItem(self.mMain, 'About', self.mAboutIndex, 1)

        # Register commands
        self.cmd = []


        # Aircraft Data Access
        self.aircraft = Aircraft()

        # Time Data Access
        self.time = Time()

        self.message_queue = Queue(10)

        self.server_thread = ServerThread(self.message_queue)
        self.server_thread.start()

        self.mainCB = self.mainCallback
        XPLMRegisterFlightLoopCallback(self, self.mainCB, 0, 0)
        XPLMSetFlightLoopCallbackInterval(self, self.mainCB, -1, 0, 0)

        self.adsbCB = self.adsbMessageCallback
        XPLMRegisterFlightLoopCallback(self, self.adsbCB, 0, 0)
        XPLMSetFlightLoopCallbackInterval(self, self.adsbCB, -1, 0, 0)

        return self.Name, self.Sig, self.Desc

    def XPluginStop(self):
        # self.server_thread.stop()
        self.reset()
        XPLMUnregisterFlightLoopCallback(self, self.mainCB, 0)
        XPLMDestroyMenu(self, self.mMain)

    def XPluginEnable(self):
        return 1

    def XPluginDisable(self):
        pass

    def XPluginReceiveMesage(self, inFromWho, inMessage, inParam):
        pass

    def reset(self):
        # XPLMSetFlightLoopCallbackInterval(self, self.mainCallback, 0, 0, 0)
        if self.aboutWindow:
            XPDestroyWidget(self, self.aboutWindowWidget, 1)
            self.aboutWindow = False

    def mainMenuCB(self, menuRef, menuItem):
        if menuItem == self.mAboutIndex:
            if (not self.aboutWindow):
                self.CreateAboutWindow(221, 640, 200, 165)
                self.aboutWindow = True
            elif (not XPIsWidgetVisible(self.aboutWindowWidget)):
                XPShowWidget(self.aboutWindowWidget)

    def CreateAboutWindow(self, x, y, w, h):
        x2 = x + w
        y2 = y - 40 - 20 * 8
        Buffer = "About CADSB Output"

        # Create the About Widget Main Window
        self.aboutWindowWidget = XPCreateWidget(x, y, x2, y2, 1, Buffer, 1,0 , xpWidgetClass_MainWindow)
        window = self.aboutWindowWidget

        # Create the Sub window
        subw = XPCreateWidget(x+10, y-30, x2-20 + 10, y2+40 -25, 1, "" ,  0,window, xpWidgetClass_SubWindow)
        # Set the style to sub window
        XPSetWidgetProperty(subw, xpProperty_SubWindowType, xpSubWindowStyle_SubWindow)
        x += 20
        y -= 30

        # Add Close Box decorations to the Main Widget
        XPSetWidgetProperty(window, xpProperty_MainWindowHasCloseBoxes, 1)

        from sys import version_info

        XPlaneVersion, XPLMVersion, HostID = XPLMGetVersions()

        sysinfo = [
        'ADSB Output: %s' % __VERSION__,
        '(c) Luke Frisken 2016',
        ]
        for label in sysinfo:
            y -= 15
            XPCreateWidget(x, y, x+40, y-20, 1, label, 0, window, xpWidgetClass_Caption)

        # Visit site
        self.aboutVisit = XPCreateWidget(x+20, y-20, x+120, y-60, 1, "Visit site", 0, window, xpWidgetClass_Button)
        XPSetWidgetProperty(self.aboutVisit, xpProperty_ButtonType, xpPushButton)

        y -= 40
        sysinfo = [
        'System information:',
        'X-plane: %.2f' % (int(XPlaneVersion)/1000.0),
        'Python: %i.%i.%i' % (version_info[0], version_info[1], version_info[2])
        ]

        for label in sysinfo:
            y -= 15
            XPCreateWidget(x, y, x+40, y-20, 1, label, 0, window, xpWidgetClass_Caption)

        # Register our widget handler
        self.aboutWindowHandlerCB = self.aboutWindowHandler
        XPAddWidgetCallback(self, window, self.aboutWindowHandlerCB)

    def aboutWindowHandler(self, inMessage, inWidget, inParam1, inParam2):
        if (inMessage == xpMessage_CloseButtonPushed):
            if (self.aboutWindow):
                XPHideWidget(self.aboutWindowWidget)
            return 1

        # Handle any button pushes
        if (inMessage == xpMsg_PushButtonPressed):
            self.send_adsb_message()
            # if (inParam1 == self.aboutVisit):
            #     from webbrowser import open_new
            #     open_new('http://google.com');
            #     return 1
        return 0

    def float(self, string):
        # try to convert to float or return 0
        try: 
            val = float(string)
        except ValueError:
            val = 0.0
        return val

    def int(self, string):
        # try to convert to integer or return 0
        try: 
            val = int(string)
        except ValueError:
            val = 0
        return val


    def adsbMessageCallback(self, elapsedMe, elapsedSim, counter, refcon):
        self.send_adsb_message()
        return UPDATE_RATE

    def mainCallback(self, elapsedMe, elapsedSim, counter, refcon):
        # print("running")
        return -1

    def send_adsb_message(self):
        print("building adsb message")

        altitude = self.aircraft.elevation.value
        latitude = self.aircraft.latitude.value
        longitude = self.aircraft.longitude.value
        heading = self.aircraft.true_heading.value
        vertical_speed = self.aircraft.vertical_speed.value
        ground_speed = self.aircraft.ground_speed.value

        dangle = math.asin(ground_speed/(EARTH_MSL+altitude))
        dtheta = dangle * math.sin(math.radians(heading))
        dphi = dangle * math.cos(math.radians(heading))

        print("groundspeed: {} verticalspeed: {}".format(ground_speed, vertical_speed))

        print("dangle: {} dtheta: {} dphi: {}".format(dangle, dtheta, dphi))
        
        print("altitude", altitude)
        print("latitude", latitude)
        print("longitude", longitude)
        print("heading", heading)
        print("\n")

        t = int(round(time.time() * 1000))
        system_state_message = NetworkInterfacePacket.SystemStateMessage()
        system_state_message.time = t
        # assert not system_state.HasField("time")

        aircraft_state_message = system_state_message.aircraftState.add()
        aircraft_state_message.aircraftID = "LFR92"
        aircraft_state_message.time = t
        aircraft_state_message.heading = heading


        position_message = aircraft_state_message.position
        position_message.altitude = altitude
        position_message.latitude = math.radians(latitude)
        position_message.longitude = math.radians(longitude)

        velocity_message = aircraft_state_message.velocity
        velocity_message.dr = vertical_speed
        velocity_message.dtheta = dtheta
        velocity_message.dphi = dphi

        if self.server_thread.is_running():
            # self.message_queue.put(system_state_message, True, 2.0)
            writeDelimitedTo(system_state_message, self.server_thread.connection)
            # print(system_state_message)
            print(self.message_queue.qsize())
        else:
            pass
            print("tried sending message but server not running")
            # print("and, server is listening: " + str(self.server_thread.listening))
            # print("and, server is alive: " + str(self.server_thread.is_alive()))




class Time:
    def __init__(self):
        self.current_day = EasyDref('sim/cockpit2/clock_timer/current_day', 'int')
        self.current_month = EasyDref('sim/cockpit2/clock_timer/current_month', 'int')
        self.zulu_time_hours = EasyDref('sim/cockpit2/clock_timer/zulu_time_hours', 'int')
        self.zulu_time_minutes = EasyDref('sim/cockpit2/clock_timer/zulu_time_minutes', 'int')
        self.zulu_time_seconds = EasyDref('sim/cockpit2/clock_timer/zulu_time_seconds', 'int')

    def refresh(self):
        # refresh values on acf change
        pass


class Aircraft:
    def __init__(self):
        self.elevation = EasyDref('sim/flightmodel/position/elevation' , 'double')
        self.latitude = EasyDref('sim/flightmodel/position/latitude', 'double')
        self.longitude = EasyDref('sim/flightmodel/position/longitude', 'double')
        self.true_heading = EasyDref('sim/flightmodel/position/true_psi', 'float')
        self.vertical_speed = EasyDref('sim/flightmodel/position/vh_ind', 'float')
        self.ground_speed = EasyDref('sim/flightmodel/position/groundspeed', 'float')

    def refresh(self):
        # refresh values on acf change
        pass
