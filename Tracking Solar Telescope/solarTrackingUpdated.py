from pysolar.solar import *
import pylunar as pl
import pytz
from datetime import datetime
from pyKinesis import *
import time
from time import sleep
import sys
import json
import numpy as np
###############################################################################################
#USER SETTINGS
###############################################################################################
# Tracking Object (#Comment out the one you don't want to track)
trackingObject = "Sun"
#trackingOject = "Moon"

#User Longitude
userLongitude = -74.7527
#User Latitude
userLatitude = 41.0582
#User Time Zone
userTimeZone = pytz.timezone('US/Eastern')#Enter relavent timezone (to view all timezones, see pytz.all_timezones)

#Azimuth Axis KDC101 Serial Number (Horizontal Rotation Axis)
azimuthKDC101SN = '27005375'

#Elevation Axis KDC101 Serial Number (Elevation/Altitude Rotation Axis)
elevationKDC101SN = '27005349'
###############################################################################################


def decdeg2dms(dd):
	#convert decimal degrees to degrees, minutes, seconds
    mult = -1 if dd < 0 else 1
    mnt,sec = divmod(abs(dd)*3600, 60)
    deg,mnt = divmod(mnt, 60)
    return mult*deg, mult*mnt, mult*sec

def getObjectPosition(Object,Longitude,Latitude,TimeZone):

	#Returns Azimuth and Elevation in degrees
	#Object is "Sun" or "Moon" for dictating which object to track
	#Longitude is in degrees
	#Latitude is in degrees
	#TimeZone is a pytz.timezone() object. All timezones can be viewed via pytz.all_timezones

	
	currentTime = datetime.utcnow().replace(tzinfo=pytz.utc)

	if Object == "Sun":
		Real_Elevation = get_altitude(Latitude,Longitude,currentTime)
		Real_Azimuth = get_azimuth(Latitude,Longitude,currentTime)
	elif Object == "Moon":
		moon = pl.MoonInfo(decdeg2dms(Latitude), decdeg2dms(Longitude))
		moon.update(currentTime)
		Real_Elevation = moon.altitude()
		Real_Azimuth = moon.azimuth()

	return Real_Azimuth,Real_Elevation

def findControllers():
	# Get device com ports and serial numbers
	detectedDevices = getAllDevices()

	deviceInfo = []

	for device in detectedDevices:
		#Get port number
		comm = str(device[0])	
		#create serial object with port
		ser=serial.Serial(port=comm, baudrate = 115200, bytesize=8, parity=serial.PARITY_NONE, stopbits=1, xonxoff=0, rtscts=0, timeout=0.1)
		ser.flushInput()
		ser.flushOutput()
		#get destination byte to rule out cube or benchtop controller
		dest = getDestination(ser)
		
		#if K cube
		if dest != 0x50:
			print("No K-Cubes Detected; ensure deivces are connected and virtual comports enabled")
		else:	
			(serialNum,model,nChannels) = getHWinfo(ser,dest)
			deviceParams = {
			"COM Port":device[0],
			"Serial Number":str(serialNum),
			"Model": model,
			"Number of Channels": nChannels}

			deviceInfo.append(deviceParams)
		ser.close()
		del ser	

	return	deviceInfo

def read_tracking_params():

	'''
	tracking_file  = open('trackingParams.json','r')
	tracking_params = tracking_file.readlines()
	tracking_file.close()

	cleaned_data = [line.replace('\n','') for line in tracking_params]
	param_dict = {}
	for param in cleaned_data:
		Split_params = param.split(':')
		param_dict[Split_params[0]] = float(Split_params[1])

	'''
	trackingFile  = 'trackingParams.json'

	with open(trackingFile,"r") as file:
		fileContents = file.read()
		file.close()	
	param_dict = json.loads(fileContents)
	return param_dict



#Make sure the serial numbers are strings
if isinstance(azimuthKDC101SN,int):
	azimuthKDC101SN = str(azimuthKDC101SN)

if isinstance(elevationKDC101SN,int):
	elevationKDC101SN = str(elevationKDC101SN)

#Find controller for each axis
print("Finding Telescope Motor Controllers")
controllers = findControllers()
try:
	azimuthCOMPort = [controller["COM Port"] for controller in controllers if controller["Serial Number"] == azimuthKDC101SN][0]
	print("\tFound Azimuth Axis Motor: COM Port - {}".format(azimuthCOMPort))
except:
	print("KDC101 with specified azimuth axis serial number not found.")

try:
	elevationCOMPort = [controller["COM Port"] for controller in controllers if controller["Serial Number"] == elevationKDC101SN][0]
	print("\tFound Elevation Axis Motor: COM Port - {}".format(elevationCOMPort))
except:
	print("KDC101 with specified evelvation axis serial number not found.")

#Create Controllers for each axis
scale_factors = [1919.6418578623391,42941.66,14.66] #PRMTZ8 Scale Factors

print("Initializing each motor controller.")
azimuthController = ThorController(azimuthCOMPort,scale_factors,Controller_Type='cube')
elevationController = ThorController(elevationCOMPort,scale_factors,Controller_Type='cube')

#Enable Each Motor
azimuthController.Enable_Channel(1)
elevationController.Enable_Channel(1)

#Home each axis
print("\tHoming Azimuth Axis Motor")
azimuthController.Home(1)
print("Homing Completed.")
print("\tHoming Elevation Axis Motor")
elevationController.Home(1)
print("Homing Completed.")

#Disable backlash correction?

#Get Current Sun Position
Current_Time = datetime.utcnow().replace(tzinfo=pytz.utc)
print("Getting Current Solar Position.")
azimuthPosition,elevationPosition = getObjectPosition(trackingObject,userLongitude,userLatitude,userTimeZone)


if elevationPosition < 0:
	elevationPosition = 360+elevationPosition	
if elevationPosition > 180:
	elevationPosition = 360 - elevationPosition


if azimuthPosition < 0:
		azimuthPosition = 360+azimuthPosition
if azimuthPosition > 180:
	azimuthPosition = 360 - azimuthPosition				

#Move to New positions before starting tracking

print('\tElevation: {}'.format(np.round(elevationPosition,4)))
print('\tAzimuth: {}'.format(np.round(azimuthPosition,4)))

print("\nMoving Elevation axis to current position.")
if elevationPosition<0:
	print("\t\tInvalid Elevation: Elevation must be above zero degrees")
else:	
	elevationController.Move_Absolute(elevationPosition,1,wait=True)

print("\nMoving Azimuth axis to current position.")
azimuthController.Move_Absolute(azimuthPosition,1,wait=True)		



X = input('\n\tTo start tracking, hit enter...')

tracking_params = {"azimuthOffset":0.0,
	"elevationOffset":0,
	"updateRate":1,
	"killTracking":0}

#print('\n\n\tTo stop tracking, hit enter...') #need to implement still
#Start continuous tracking
while True:

	#get Offsets and calculate current positions
	try:
		tracking_params  = read_tracking_params()
	except:
		pass	

	Current_Time = datetime.utcnow().replace(tzinfo=pytz.utc)
	#Get New Positions
	azimuthPosition,elevationPosition = getObjectPosition(trackingObject,userLongitude,userLatitude,userTimeZone)

	azimuthPosition += tracking_params['azimuthOffset']
	elevationPosition += tracking_params['elevationOffset']

	#Helps with complenatary angle to reduce the path of movement
	if elevationPosition < 0:
		elevationPosition = 360+elevationPosition
	if elevationPosition > 180:
		elevationPosition = 360 - elevationPosition	

	if azimuthPosition < 0:
			azimuthPosition = 360+azimuthPosition
	if azimuthPosition > 180:
		azimuthPosition = 360 - azimuthPosition		

	print("\r\t\tAzimuth: {}\t\tElevation: {}".format(np.round(azimuthPosition,4),np.round(elevationPosition,4)),end='')
	#Move to New positions
	elevationController.Move_Absolute(elevationPosition,1,wait=False)
	azimuthController.Move_Absolute(azimuthPosition,1,wait=False)	

	
	sleep(tracking_params['updateRate'])
	#Break from loop with user input
	if tracking_params['killTracking'] == 1:
		print('\nTracking Terminated')
		break



elevationController.Close_Port()
azimuthController.Close_Port()
del elevationController
del azimuthController

