"""
Title: Brewster's Angle Insight
Created Date: 08/07/2024
Last Modified Date: 08/07/2024
Python version: python3
Thorlabs Software versions: Kinesis 1.14.49 OPM 6.1
Example description: This example goes over using PRM1Z8 rotation stage and Thorlabs power meter to show the 
relationship between Fresnel reflection and angle of incidence. Measurmenets are plotted and stored in an excel file
given by the user.
"""


# Import system modules, dlls, and required python libraries.
import time
import clr
import os
os.add_dll_directory(os.getcwd())
clr.AddReference('C:\\Program Files\\Thorlabs\\Kinesis\\Thorlabs.MotionControl.DeviceManagerCLI.dll')
clr.AddReference('C:\\Program Files\\Thorlabs\\Kinesis\\Thorlabs.MotionControl.GenericMotorCLI.dll')
clr.AddReference('C:\\Program Files\\Thorlabs\\Kinesis\\Thorlabs.MotionControl.KCube.DCServoCLI.dll')
from Thorlabs.MotionControl.DeviceManagerCLI import *
from Thorlabs.MotionControl.GenericMotorCLI import *
from Thorlabs.MotionControl.GenericMotorCLI import KCubeMotor
from Thorlabs.MotionControl.GenericMotorCLI.ControlParameters import JogParametersBase
from Thorlabs.MotionControl.KCube.DCServoCLI import *
from System import Decimal
from TLPMX import TLPMX
from TLPMX import TLPM_DEFAULT_CHANNEL
from ctypes import c_uint32, byref, create_string_buffer, c_bool, c_char_p, c_int, c_double
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import openpyxl as openpy
import xlsxwriter as xls

# Set scaling for plot
plt.rcParams["figure.figsize"] = [7.50, 3.50]
plt.rcParams["figure.autolayout"] = True
fig,ax=plt.subplots()

Degree_x=[]
Power_y=[]

def main():
    """The main entry point for the application"""
    # Set up connection to Thorlabs power meter.
    os.add_dll_directory(os.getcwd())
    meter = TLPMX()
    device_count = c_uint32()
    meter.findRsrc(byref(device_count))

    if device_count == 0:
        print('No connected Meters')
        quit()

    resource_name = create_string_buffer(1024)
    meter.getRsrcName(c_int(0), resource_name)
    meter.open(resource_name, c_bool(True), c_bool(True))
    meter.setWavelength(c_double(633.0), TLPM_DEFAULT_CHANNEL)

    # Set up connection to KDC101 controller. 
    SimulationManager.Instance.InitializeSimulations()
    serial_num = str('27000001')
    DeviceManagerCLI.BuildDeviceList()
    controller = KCubeDCServo.CreateKCubeDCServo(serial_num)
    time.sleep(.25)


    if not controller == None:
        controller.Connect(serial_num)

        if not controller.IsSettingsInitialized():
            controller.WaitForSettingsInitialized(3000)
        
        controller.StartPolling(50)
        time.sleep(.1)
        controller.EnableDevice()
        time.sleep(.1)

        # Load settings parameters inot KDC101.
        config = controller.LoadMotorConfiguration(serial_num, DeviceConfiguration.DeviceSettingsUseOptionType.UseFileSettings)
        config.DeviceSettingsName = str('PRM1-Z8')
        config.UpdateCurrentConfiguration()

        controller.SetSettings(controller.MotorDeviceSettings, True, False)


        # Set and initialize jog parameters. 
        print('Homing Motor')
        controller.Home(60000)
        controller.SetJogVelocityParams(Decimal(10), Decimal(1))
        jog_params = controller.GetJogParams()
        
        jog_params.StepSize = Decimal(75)
        jog_params.JogMode = JogParametersBase.JogModes.SingleStep

        controller.SetJogParams(jog_params)
        
        print('Moving Motor')
        controller.MoveJog(MotorDirection.Backward, 0)
        time.sleep(0.25)

        # Take power measurments while motor is moving. 
        while controller.IsDeviceBusy:
            power = c_double()
            meter.measPower(byref(power),TLPM_DEFAULT_CHANNEL)
            Degree_x.append(float(f'{controller.Position}'))
            Power_y.append(float(f'{power.value*1000000}'))
            
            print(f'{controller.Position}, {power.value*1000000}')
            time.sleep(0.05)
        
        jog_params.StepSize = Decimal(77)
        controller.SetJogParams(jog_params)
        print('Moving Motor')
        controller.MoveJog(MotorDirection.Forward, 60000)
        time.sleep(0.5)

        print('Homing Motor')
        controller.Home(60000)

        # Clean up resources and close devices.
        controller.StopPolling()
        controller.Disconnect(False)
        SimulationManager.Instance.UninitializeSimulations()
        
           
    meter.close()


if __name__ == "__main__":
    main()

# Create arrays to hold collected data.
Newx=np.array(Degree_x)
Newy=np.array(Power_y)
Newx2=np.subtract(Newx,360)
Newx3=np.negative(Newx2)
MyInt=539
Newy2=np.divide(Newy,MyInt)
Newy2=np.multiply(Newy2,100)

# Create DataFrame and open excel document to store said DataFrame. 
myList=np.vstack((Newx3,Newy))
df=pd.DataFrame(myList)
df=df.transpose()
xlsfile = 'XXXXXXX' # Insert name of excel file you want to save teh data to.
writer = pd.ExcelWriter(xlsfile, engine='xlsxwriter')
df.to_excel(writer, sheet_name="Sheet1",startrow=1, startcol=1, header=False, index=False)
writer.close()

# Create and show plot of collected data. 
ax.set_title("S-Polarization Transmission vs AOI")
ax.set_xlabel('Angle of Incidence (°)')
ax.set_ylabel('Transmission (%)')
ax.plot(Newx3,Newy2)
plt.show()