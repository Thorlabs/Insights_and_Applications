
import json
import PySimpleGUI as sg
import numpy as np

def readTrackingParams():

	trackingFile  = 'trackingParams.json'

	with open(trackingFile,"r") as file:
		fileContents = file.read()
		file.close()
		trackingDict = json.loads(fileContents)


	return trackingDict


def writeTrackingParams(paramDict):

	trackingFile  = 'trackingParams.json'	
	with open(trackingFile, "w") as outFile:
		json.dump(paramDict, outFile)

	return	

sg.theme('Dark Grey 13')

#The default offsets for the azimuth and elevation axes
aziOffset = 0 
eliOffset = 0  
#How many degrees each offset increments with button press
increment = 0.05


defaultParams = {"azimuthOffset":0.0,
"elevationOffset":0,
"updateRate":1,
"killTracking":0}

trackParams = defaultParams

writeTrackingParams(defaultParams)

aziUP = sg.Button("+",key="-aziIncrease-", enable_events=True)
aziDOWN = sg.Button("-",key="-aziDecrease-", enable_events=True)

eliUP = sg.Button("+",key="-eliIncrease-", enable_events=True)
eliDOWN = sg.Button("-",key="-eliDecrease-", enable_events=True)

layout = [[sg.Text('Solar Telescope Tracking Controls')],
            [sg.Text('Azimuth Offset: '),sg.Text('0.00',key='-AZIOFFSET-'),aziUP,aziDOWN,sg.Text('Elevation Offset: '),sg.Text('0.00',key='-ELIOFFSET-'),eliUP,eliDOWN],
            [sg.Button('Stop Tracking',key="-STOP-"), sg.Button('Close')]]


# Create the Window
window = sg.Window('Solar Telescope Tracking Controls', layout)
# Event Loop to process "events" and get the "values" of the inputs
while True:
    event, values = window.read()
    if event == sg.WIN_CLOSED or event == 'Close': # if user closes window or clicks close
        break

    if event == '-aziIncrease-':
    	aziOffset += increment
    	window['-AZIOFFSET-'].update("{:.2f}".format(aziOffset))
    	trackParams['azimuthOffset'] = aziOffset
    	writeTrackingParams(trackParams)

    if event == '-aziDecrease-':
    	aziOffset -= increment
    	window['-AZIOFFSET-'].update("{:.2f}".format(aziOffset))
    	trackParams['azimuthOffset'] = aziOffset
    	writeTrackingParams(trackParams)

    if event == '-eliIncrease-':
    	eliOffset += increment
    	window['-ELIOFFSET-'].update("{:.2f}".format(eliOffset))
    	trackParams['elevationOffset'] = eliOffset
    	writeTrackingParams(trackParams)


    if event == '-eliDecrease-':
    	eliOffset -= increment
    	window['-ELIOFFSET-'].update("{:.2f}".format(eliOffset))
    	trackParams['elevationOffset'] = eliOffset
    	writeTrackingParams(trackParams)

    if event == '-STOP-':
    	trackParams['killTracking'] = 1
    	writeTrackingParams(trackParams)

window.close()            



