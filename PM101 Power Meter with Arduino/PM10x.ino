// SoftwareSerial - Version: Latest 
#include <SoftwareSerial.h>

// Sets the speed (baud rate) for the serial communication to the Thorlabs PM10x. Supported baud rates are 
// 300, 600, 1200, 2400, 4800, 9600, 14400, 19200, 28800, 31250, 38400, 57600, 115200 
const int tlBaudrate = 19200;

const byte rxPin = 10; // the pin 10 of the Arduino board is used to receive the data
const byte txPin = 11; // the pin 11 of the Arduino board is used to transmit the data

// read all transmitted data from the Thorlabs PM10x until the end char '\n' and convert the response to a double value
bool readDoubleValue(double* powerValue);

// initialize the serial communication with the defined pins on the Arduiono board
SoftwareSerial tlSerial = SoftwareSerial(rxPin, txPin);

// setup the serial communication to the Thorlabs PM10x and the USB/serial Monitor
void setup() 
{  
  Serial.begin(19200); // baudrate of the USB/serial communication to the PC
  while (!Serial) {
    ; // wait for serial port to connect. Needed for native USB port only
  }
  
  // initialize the serial communication with the Thorlabs Powermeter
  tlSerial.begin(tlBaudrate);
  
  // test the communication
  queryIdentify();
  
  Serial.write("\n**** Communication Initialized ****\n");
}

void queryIdentify()
{
  char responseBuffer[256];
  char* responsePrt;

  responsePrt = responseBuffer;

  tlSerial.write("*IDN?\n");
  while(tlSerial.available() == 0){delay(100);}
	
	Serial.print("I am: ");

  char c = 1;
	while(tlSerial.available() > 0 && c != 0 && c != '\n')
	{
	  c = tlSerial.read();
	  *responsePrt = c;
	  responsePrt++;
	}

  *responsePrt = '\0';

  Serial.print(responseBuffer);
}

void loop() 
{ 
  double powerValue = 1;
  
  // request a new power value from the Thorlabs PM10x (all commands are listed in the manual)
  tlSerial.write("meas?\n");
    
  // read the response and convert it into a double value
  if(readDoubleValue(&powerValue))
  {  
    Serial.print("\nPower: ");
  	Serial.print(powerValue, 8); // print the power value with an accuracy of 8 digits behind the separator
  }
}

bool readDoubleValue(double* powerValue)
{  
  char responseBuffer[256];
  char* responsePrt;

  delay(100);
  
  responsePrt = responseBuffer;
  
  // if there's any serial available, read it:  
  char c = 1;
	while(tlSerial.available() > 0)
	{
	  c = tlSerial.read();
	  *responsePrt = c;
	  responsePrt++;
	}
	
	if (responsePrt == responseBuffer)
	{
	  // no response
	  return false;
	}
	
	// convert the response to the power value
	*powerValue = atof(responseBuffer);  
	
	return true;
}
