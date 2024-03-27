# Insights_and_Applications

## Build A Motorized Imaging Solar Telescope | Thorlabs Insights

This repository is the code used for the Thorlabs Insight that covers the design and build of an imaging, tracking solar telescope using the PRMTZ8 rotation stages. This Insight provides a overall explanation the the telescope design and using the software. 

## What are each of these files?
<ul>
+ **pyKinesis.py** - A class that wraps the Kinesis serial communication into a more user friendly interface
+ **solarTrackingGUI.py** - A program that runs a small GUI for altering the telescope offsets and to disable the solar tracking. It generates a config file for communicating with the tracking script. 
+ **trackingParams.json** - A json file containing parameters read in by the tracking software
+ **solarTracking.py** - The actual program that connects the rotation stages and tracks the sun. This requires user specific settings that we'll have to set for TLS
	1) User's longitude
	2) User Latitude
	3) Users Time Zone
	4) The serial numbers of the controllers for the Azimuth and Elevation axes

</ul>



## How to use this project

### **Windows**
<ul>

1. Install the [VCP FTDI drivers](https://ftdichip.com/drivers/vcp-drivers/)
	- If Kinesis is installed, this is not necessary

2. With each K-cube connected to the computer, open device manager and make sure there is a COM port for each cube.
	- If not showing as as COM port devices, open device manager and select properties for each APT USB Device and check the 'Load VCP' is box and power cycle the controllers. 
![Virtual Com Ports](https://github.com/Thorlabs/Insights_and_Applications/blob/main/Tracking%20Solar%20Telescope/assetts/Load%20VCP.PNG)

3. Install the necessary Python dependencies if not already
	- PySerial (pip install pyserial)
	- numpy (pip install numpy)
	- pysimplegui (pip install pysimplegui)
	- pysolar (pip install pysolar)
	- pylunar (pip install pylunar)
	- pytz (pip install pytz)


4. Open solarTracking.py in a text editor and update the following user specific settings:
	- userLongitude - Your Longitude position
	- userLatitude - Your Latitude position
	- userTimeZone - Your Timezone (printing pytz.all_timezones will show all options)
	- azimuthKDC101SN - Serial Number(string)  of the azimuth axis K-Cube Controller
	- elevationKDC101SN - Serial Number(string)  of the elevation/altitude axis K-Cube Controller

	![User Settings](https://github.com/Thorlabs/Insights_and_Applications/blob/main/Tracking%20Solar%20Telescope/assetts/UserSettings.PNG)

5. Save the updated user settings in solarTracking.py 
6. Open a terminal and run solarTrackingGUI.py.(This program is a GUI for updating the tracking offsets and to stop the tracking program.)


7. In another terminal, run solarTracking.py which will initiate the tracking
	- The program will look for COM ports with device serial numbers that match those entered
	- Home each stage
	- Move each axis to the current solar position based on your location/timezone
	- Prompt the user to start tracking by hitting enter. 

8. To stop the program, click 'Stop Tracking' in the GUI and the program will terminate tracking and end
</ul>

### **Linux**
<ul>

Most Linus kernels incorporate the FTDI drivers necessary for identifying the K-Cube motor controllers, so only python dependencies are needed
1. Install the necessary Python dependencies
	- PySerial (pip install pyserial)
	- numpy (pip install numpy)
	- pysimplegui (pip install pysimplegui)
	- pysolar (pip install pysolar)
	- pylunar (pip install pylunar)
	- pytz (pip install pytz)

2. Open solarTracking.py in a text editor and update the following user specific settings:
	- userLongitude - Your Longitude position
	- userLatitude - Your Latitude position
	- userTimeZone - Your Timezone (printing pytz.all_timezones will show all options)
	- azimuthKDC101SN - Serial Number(string)  of the azimuth axis K-Cube Controller
	- elevationKDC101SN - Serial Number(string)  of the elevation/altitude axis K-Cube Controller

3. Save the updated user settings in solarTracking.py 
4. Open a terminal and run solarTrackingGUI.py.(This program is a GUI for updating the tracking offsets and to stop the tracking program.)
5. In another terminal, run solarTracking.py which will initiate the tracking
	* The program will look for COM ports with device serial numbers that match those entered
	* Home each stage
	* Move each axis to the current solar position based on your location/timezone
	* Prompt the user to start tracking by hitting enter. 
![User Settings](https://github.com/Thorlabs/Insights_and_Applications/blob/main/Tracking%20Solar%20Telescope/assetts/UserSettings.PNG)	

6. To stop the program, click 'Stop Tracking' in the GUI and the program will terminate tracking and end

</ul>





