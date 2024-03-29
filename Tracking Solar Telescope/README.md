

# Build A Motorized Imaging Solar Telescope | Thorlabs Insights

This repository is the code used for the Thorlabs Insight that covers the design and build of an imaging, tracking solar telescope using the PRMTZ8 rotation stages. This Insight provides a overall explanation the the telescope design and using the software. 

For more details on the parts, BOM, and 3D printable motor Bracket, there is a detailed README in the [Design Files folder](https://github.com/Thorlabs/Insights_and_Applications/tree/main/Tracking%20Solar%20Telescope/Design%20Files). 

Currently the python scripts only control the motors and do not interface with the CS165MU camera. The camera feed can be observed using Thorcam or developing a program to stream the camera feed. For camera examples, please refer to the [Camera Examples repo](https://github.com/Thorlabs/Camera_Examples). 

## What are each of these files?
<ul>

- **pyKinesis.py** - A class that wraps the basic commands of the Kinesis serial communication protocol into a more user friendly interface

- **solarTrackingGUI.py** - A program that runs a small GUI for altering the telescope offsets and to disable the solar tracking. This generates 
	a .json config file for communicating tracking parameters with the tracking script. 

	![solarTrackingGUI](https://github.com/Thorlabs/Insights_and_Applications/blob/main/Tracking%20Solar%20Telescope/assetts/SolarTrackingGUI.PNG)	
	
- **trackingParams.json** - A .json file containing parameters read in by the tracking software
	
- **solarTracking.py** - The actual program that communicates with the rotation stages and tracks the sun. This requires user specific settings that must be accurate to work correctly. 
	
	* Whether the user wants to track the sun or moon
	* User's Longitude
	* User's Latitude
	* User's Time Zone (per pytz.all_timeszones)
	* The serial numbers of the controllers for the Azimuth and Elevation axes

	![User Settings](https://github.com/Thorlabs/Insights_and_Applications/blob/main/Tracking%20Solar%20Telescope/assetts/UserSettings.PNG)


</ul>



## How to use this project

<ul>

1. Install the [VCP FTDI drivers](https://ftdichip.com/drivers/vcp-drivers/) so the K-Cubes can be identified as COM ports
	- If using Windows and Kinesis is installed, this is not necessary.
	- If using linux, the FTDI drivers are included in most linux kernals, so this is not necessary

2. (If using windows) Connect each K-cube to the computer, open device manager, and make sure there is a COM port for each cube.
	- If not showing up as COM port devices, open device manager, select properties for each 'APT USB Device', check the 'Load VCP' box, and power cycle the controllers. 
![Virtual Com Ports](https://github.com/Thorlabs/Insights_and_Applications/blob/main/Tracking%20Solar%20Telescope/assetts/Load%20VCP.PNG)

3. Install the necessary Python dependencies if not already
	- PySerial (pip install pyserial)
	- numpy (pip install numpy)
	- pysimplegui (pip install PySimpleGUI==4.60.5)
	- pysolar (pip install pysolar)
	- pylunar (pip install pylunar)
	- pytz (pip install pytz)


4. Open solarTracking.py in a text editor and update the following user specific settings:

	- **trackingObject** - What object you want to track; "Sun" or "Moon"
	- **userLongitude** - Your Longitude position
	- **userLatitude** - Your Latitude position
	- **userTimeZone** - Your Timezone (printing pytz.all_timezones will show all options)
	- **azimuthKDC101SN** - Serial Number(string)  of the azimuth axis K-Cube Controller
	- **elevationKDC101SN** - Serial Number(string)  of the elevation/altitude axis K-Cube Controller

	![User Settings](https://github.com/Thorlabs/Insights_and_Applications/blob/main/Tracking%20Solar%20Telescope/assetts/UserSettings.PNG)

5. Save the updated user settings in solarTracking.py 
6. Open a terminal and run solarTrackingGUI.py.(This program is a GUI for updating the tracking offsets and to stop the tracking program.)
		
		python solarTrackingGUI.py

7. In another terminal, run solarTracking.py, which will initiate the tracking
		
		python solarTracking.py

	- The program will look for COM ports with device serial numbers that match those entered
	- Home each stage
	- Move each axis to the current solar position based on your location/timezone
	- Prompt the user to start tracking by hitting enter. 

	![solarTrackingOutput](https://github.com/Thorlabs/Insights_and_Applications/blob/main/Tracking%20Solar%20Telescope/assetts/solarTrackingOutput.png)	

8. To stop the program, click 'Stop Tracking' in the GUI and the program will terminate tracking and end
	![solarTrackingGUI](https://github.com/Thorlabs/Insights_and_Applications/blob/main/Tracking%20Solar%20Telescope/assetts/SolarTrackingGUI.PNG)

</ul>

