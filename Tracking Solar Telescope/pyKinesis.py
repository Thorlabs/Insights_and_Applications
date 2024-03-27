import serial
import serial.tools.list_ports
from struct import pack,unpack
import time

'''
This class is used to find, initialize and controls Thorlabs T-Cube, K-Cube, and Benchtop Controllers using the host-controller communication protocal:
https://www.thorlabs.com/software_pages/ViewSoftwarePage.cfm?Code=Motion_Control&viewtab=2

This protocol uses serial communication to package the motor control information per the document above.

This method avoids the need for using the Kinesis .NET .dlls. 
'''


def getDestination(serial):
	dest = 0x50

	serial.write(pack('<HBBBB', 0x0005, 0x00, 0x00, dest, 0x01))
	rx = serial.read(90)
	serial.flushInput()
	serial.flushOutput()
	if len(rx)>0:
		return 0x50
	else:
		return 0x11	

def getAllDevices():
	ports = list(serial.tools.list_ports.comports())

	APT_devices = [port for port in ports if 'APT' in port[1]]
	return 	APT_devices

def getHWinfo(serial,destination):

	msg=pack('<HBBBB', 0x0005, 0x00, 0x00, destination, 0x01)
	serial.write(msg)

	#Read Back Data
	header=bytearray(serial.read(6))
	msgid, length, destOR, source = unpack('<HHBB', header)
	data=bytearray(serial.read(length))
	serialnum, model, hwtype, swversion, notes, hwversion, modstate, nchans = unpack('<I8sHI48s12xHHH', data)

	return (serialnum,model,nchans)

class ThorController:

	#Thorlabs Controller Object Initialization	
	def __init__(self,PORT,Scale_Factors,Controller_Type = 'cube'):

		'''
		Creates a Thorlabs Controller object. 
		Input Arguements:
			PORT - Takes in string argument for the device's Serial Com Port

			Scale_Factors - Takes in a list of the scale factors for position, velocity, and acceleration 
						to convert from device units to real units

			Controller_Type - String arguement for the type of controller. This defaults to T-Cube and K-Cube
						type controllers. If not a cube controller, 'benchtop' must be provided as an argument

		----------------------- Cube Example -----------------------			

		Example for KBD101 and DDSM100

		port = 'COM14'

		scale_factors= [2000., 13421.77, 1.374] #scale factors order format [position, velocity, acceleration] 
		
		KBD101 = ThorController(port,scale_factors)

		----------------------- Benchtop Example -----------------------			

		Example for BSC202 and NRT150 

		port = 'COM14'
		scale_factors= [409600., 21987328., 4506.] #scale factors order format [position, velocity, acceleration]
	
		BSC202 = ThorController(port,scale_factors,Controller_Type = 'benchtop')

		'''


		#destination byte dependent on controller and channel.
		self.Controller_Type = Controller_Type.lower()
		self.Controller_Types = ['cube','benchtop']

		if self.Controller_Type not in self.Controller_Types:
			raise Exception('Error: Invalid Controller Type')
			print("Valid Controller Types: "+ str(self.Controller_Types).strip("[]"))


		#Define Controller Object Parameters
		
		self.port = PORT
		self.posScaleFactor,self.velScaleFactor,self.accScaleFactor = Scale_Factors[:]
		#self.channel = channel
		#self.channel_byte = 0x01
		self.source_byte = 0x01
		try:
			#Create Serial Object for the controller to communicate to the declared Com Port	
			self.Serial_Port = serial.Serial(port = self.port, baudrate = 115200, bytesize=8,
				parity=serial.PARITY_NONE, stopbits=1,timeout=0.1)
		except:
			print("Port Error: Unable to connect to '%s'. Device may already be in use." % self.port)


	def get_destination_byte(self,channel_num):

		'''Function used to provide correct destination byte for function requiring channel input'''
		#All cubes and internal controller stages are USB type and use 0x50 for the most part
		#If a benchtop controller, the destination byte changes based on channel number

		if self.Controller_Type == 'benchtop':
			dest_byte = 0x20 + channel_num
		else: 	
			dest_byte = 0x50

		return dest_byte	


	def Initialize(self,channel_num):

		'''
		Creates a serial object for the ThorController object. 

		Initalizes the controller by sending the GetHWInfo and MGMSG_HW_NO_FLASH_PROGRAMMING methods.
		These commands allow the controllers to send confirmation Rx commands when the've complete homing, 
		moving, etc... 

		'''
			
		#Initialize the motors so they can send confirmation Rx commands for when they complete moves
		#Some K-Cubes and T-Cubes require calling the GetHWInfo Command to allow Rx confirmation calls
		#This does not negatively impact if it's a benchtop controller in any way
		self.Serial_Port.write(pack('<HBBBB', 0x0005, 0x00, 0x00, self.get_destination_byte(channel_num), self.source_byte))
		self.Serial_Port.reset_input_buffer()
		self.Serial_Port.reset_output_buffer()

		#Benchtop Controllers require the MGMSG_HW_NO_FLASH_PROGRAMMING to allow confirmation Rx
		#This should not negatively impact a T Cube/K Cube in any way
		#MGMSG_HW_NO_FLASH_PROGRAMMING
		self.Serial_Port.write(pack('<HBBBB', 0x0018, 0x00, 0x00, self.get_destination_byte(channel_num), self.source_byte))

		self.Flush_Buffers()

		return

		#Non-Thorlabs Functions
	
	def Close_Port(self):
		
		''' Closes the serial port from communication'''

		self.Serial_Port.close()
		return

	def Open_Port(self):

		''' Opens the serial port from communication if closed'''

		self.Serial_Port.open()
		return

	def Flush_Buffers(self):

		'''Clears the serial objects input/output buffers'''

		self.Serial_Port.reset_input_buffer()
		self.Serial_Port.reset_output_buffer()

		return	
		
	def Identify(self,channel_num):

		'''
		Will blink the relevent cube and or channel on a benchtop controller to help identify
		 the controller asscoaited with a particular ThorController object. 

		'''
		if self.Controller_Type == 'cube':
			#MGMSG_MOD_IDENTIFY
			self.Serial_Port.write(pack('<HBBBB',0x0223,0x01, 0x00, 0x50, self.source_byte)) 
		elif self.Controller_Type == 'benchtop':
			#MGMSG_MOD_IDENTIFY
			self.Serial_Port.write(pack('<HBBBB',0x0223,channel_num, 0x00, 0x11, self.source_byte))

		self.Stay_Alive(channel_num)
		self.Flush_Buffers()
		return			

	def Stay_Alive(self,channel_num):

		''' Must be sent at least once every 50 commands to keep the connection alive'''

		#MGMSG_MOT_ACK_DCSTATUSUPDATE
		#Must be sent every 50 Tx commands if polling, otherwise polling will stop
		self.Serial_Port.write(pack('<HBBBB',0x0492,0x00,0x00,self.get_destination_byte(channel_num),self.source_byte))

		return



	def Enable_Channel(self,channel_num):

		'''
		Enables the ThorController object's controller and powers the motor coils

		For benchtop controllers, it's been observed the channel LED does not illluminate after the channel
		has been enabled using this command alone. The channel will still be enabled, allowing it move once 
		commands are sent.

		'''

		#Enable Stage; MGMSG_MOD_SET_CHANENABLESTATE 
		Enable = 0x01
		self.Serial_Port.write(pack('<HBBBB',0x0210,0x01,Enable,self.get_destination_byte(channel_num),self.source_byte))
		time.sleep(0.1)

		self.Flush_Buffers()		
		self.Stay_Alive(channel_num)

		if self.Controller_Type == 'benchtop':
			
			self.Serial_Port.write(pack('<HBBBB',0x0210,0x01,Enable,self.get_destination_byte(channel_num),self.source_byte))
			time.sleep(0.1)

			self.Flush_Buffers()		
			self.Stay_Alive(channel_num)
		


		return


	def Disable_Channel(self,channel_num):

		'''
		Disables the channel of the ThorController object. 

		When channel is disabled, no power will flow to the motor coils and the stage will not be
		respone to move commands. 

		'''


		#Disable Stage; MGMSG_MOD_SET_CHANENABLESTATE 
		Disable = 0x02
		self.Serial_Port.write(pack('<HBBBB',0x0210,channel_num,Disable,self.get_destination_byte(channel_num),self.source_byte))
		time.sleep(0.1)
		self.Flush_Buffers()		
		self.Stay_Alive(channel_num)

		if self.Controller_Type == 'benchtop':
			
			self.Serial_Port.write(pack('<HBBBB',0x0210,0x01,Disable,self.get_destination_byte(channel_num),self.source_byte))
			time.sleep(0.1)

			self.Flush_Buffers()		
			self.Stay_Alive(channel_num)

		return

	def Home(self,channel_num,wait=True):



		'''
		Homes the stage as a default will wait for the stage to complete homing.
		If wait is defined as False in the input arguement, the method will return and
		advance in the program immediately after homing has initiated

		'''

		#Home Stage; MGMSG_MOT_MOVE_HOME 
		self.Serial_Port.write(pack('<HBBBB',0x0443,0x01,0x00,self.get_destination_byte(channel_num),self.source_byte))
		
		#wait is default true and won't return until finished homing
		#If wait is false, it will advance before homing has completed
		if wait:
			Rx = ''

			#MGMSG_MOT_MOVE_HOMED  
			Homed = pack('<H',0x0444)
			while Rx != Homed:
				Rx = self.Serial_Port.read(2)


		self.Flush_Buffers()		
		self.Stay_Alive(channel_num)

		return	


	def Move_Absolute(self,Position,channel_num,wait=True):

		'''
		Move stage to absolute postion of real unit arguement 'Position'. 
		 Method waits for stage to complete homing before returning from method asa default value

		If False is provided for wait as an additional input argument, the method returns immediately after
		 the movehas started
		'''

		#Convert real unit position to device unit position
		dUnitpos = int(self.posScaleFactor*Position)

		#MGMSG_MOT_MOVE_ABSOLUTE 
		self.Serial_Port.write(pack('<HBBBBHI',0x0453,0x06,0x00,self.get_destination_byte(channel_num)|0x80,self.source_byte, 
			0x01,dUnitpos))

		if wait:
			Rx = ''

			#MGMSG_MOT_MOVE_COMPLETED
			Move_Complete = pack('<H',0x0464)
			while Rx != Move_Complete:
				Rx = self.Serial_Port.read(2)

		
		self.Flush_Buffers()		
		self.Stay_Alive(channel_num)

		return				

	#differnt methods for returning position
	def getPosition(self,channel_num):

		''' 
		Returns the real unit of the stages current position

		'''

		self.Flush_Buffers()	
		#MGMSG_MOT_REQ_POSCOUNTER 
		self.Serial_Port.write(pack('<HBBBB',0x0411,0x01,0x00,self.get_destination_byte(channel_num),self.source_byte))
		header, chan_dent, position_dUnits = unpack('<6sHI',self.Serial_Port.read(12))

		self.Stay_Alive(channel_num)		
		self.Flush_Buffers()	
		
		return position_dUnits/float(self.posScaleFactor)	


	def get_status_Update(self,channel_num):

		'''
		MGMSG_MOT_REQ_DCSTATUSUPDATE 0x0490

		Returns MGMSG_MOT_GET_DCSTATUSUPDATE 0x0491 which will include position, velocity, and statusbits

		function return the positiona and velocity in real units

		'''
		self.Flush_Buffers()
		self.Serial_Port.write(pack('<HBBBB',0x0490,0x01,0x00,self.get_destination_byte(channel_num),self.source_byte))
		msg = self.Serial_Port.read(20)
		unused, positionDU,velocityDU, reserved, status_bits = unpack('<8sIHHI',msg)
		self.Flush_Buffers()
		self.Stay_Alive(channel_num)	

		return (positionDU/self.posScaleFactor), (velocityDU/204.8)#/self.velScaleFactor	

	def getEncCounter(self,channel_num):

		'''
		MGMSG_MOT_REQ_ENCCOUNTER 0x040A

		returns the real unit position based on the supplied scale factor

		'''

		self.Flush_Buffers()	
		#MGMSG_MOT_REQ_POSCOUNTER 
		self.Serial_Port.write(pack('<HBBBB',0x040A,0x01,0x00,self.get_destination_byte(channel_num),self.source_byte))
		header, chan_dent, EncCount = unpack('<6sHI',self.Serial_Port.read(12))

		self.Stay_Alive(channel_num)		
		self.Flush_Buffers()	
		
		return EncCount/float(self.posScaleFactor)									
