from controlBoardSerialv13 import controlBoardSerialv13GUI
import re
from serial import *
from GUI_Class import GUI

class nfcProgramming():
	def __init__(self, externalgui: GUI):
		self.gui = externalgui
	
	def start(self):
		COMPort = self.gui.portAssign()		#prompt user to select an available COM port
		self.tagger = controlBoardSerialv13GUI.controlBoardv13_maxim(COMPort, self.gui)
		self.gui.wait(1)
		while True:
			self.main()

	def interpretHex(self, hexlog: str):
		#take full ESP printout and find the hex code line
		hexString = re.search(r'Ample ID: 0x4[0-9A-Fa-f]{6}', hexlog)		#serial hex will always appear as 0x4 followed by a 6 character hex
		if not hexString:
			self.gui.label(text="Read failed! No hex ID found", color='red', big=True)
		else:
			hexString = hexString.group()			#turn match object into string of match
			pureHex = hexString[-6:].lstrip('0')	#take just serial hex and remove leading zeros
			decimal = int(pureHex, 16)				#convert to decimal
			#show all three forms of the serial number/hex
			self.gui.label(text="The hex code is: " + pureHex + "\nAnd the serial number is: " + str(decimal) + '\n' + hexString, color='dark green', big=True)

	def findHex(self, hexlog: str, serialDecimal: int) -> bool:
		ranCorrectly = re.search('Write Finished', hexlog)		#make sure ESP properly executed write function
		if not ranCorrectly: 
			self.gui.label("Error! Try again", big=True)
			return False
		hexString = re.search(r'Ample ID: 0x4[0-9A-Fa-f]{6}', hexlog)		#serial hex will always appear as 0x4 followed by a 6 character hex
		if not hexString:
			self.gui.label(text="Programming failed! NFC tag did not accept programming", color='red', big=True)
			return False
		else:
			hexString = hexString.group()			#turn match object into string of match
			pureHex = hexString[-6:].lstrip('0')	#take just serial hex and remove leading zeros
			decimal = int(pureHex, 16)				#convert to decimal
			if decimal != serialDecimal:			#hex read off the NFC does not match intended hex to be written
				self.gui.label(text="NFC did not update to new hex code\nNFC is: " + pureHex + ", should be: " + hex(serialDecimal)[:2] + "\nplease try again", color='red', big=True)
				return False
			else:
				#show all three forms of the serial number/hex
				self.gui.label(text="Success!\nThe hex code is: " + pureHex + "\nAnd the serial number is: " + str(decimal) + '\n' + hexString, color='dark green', big=True)
				return True

	def readHex(self):
		try:
			self.tagger.sendCommand('h')			#go to home menu
			self.tagger.receiveSerial(delay=1)		#give long wait for the slow tagger
			self.tagger.sendCommand('4')			#ask tagger to scan NFC and print hex
			hexlog = self.tagger.receiveSerial(1)	#give long wait for slow tagger before reading full printout
			self.interpretHex(hexlog)
		except SerialException:						#NFC tagger has lost COM connection, ask user to choose port again
			COMPort = self.gui.portAssign()			#prompt user to select an available COM port
			self.tagger = controlBoardSerialv13GUI.controlBoardv13_maxim(COMPort, self.gui)
			#no need to rerun function since this is one of two options the user is prompted with and let's them start when ready
			self.gui.wait(1)

	def writeHex(self) -> bool:
		#get just serial instance number
		temp = re.findall('[0-9]+', self.serialNumber)
		res = list(map(int, temp))
		serialInstanceTag = res[2]
		makeHex = '0x4%06x' % serialInstanceTag		#convert to the expected format of 0x4 followed by 6 character hex

		try:
			self.tagger.receiveSerial()					#clear any past output from log
			self.tagger.sendCommand('3')				#go to write function
			self.gui.wait(0.5)							#wait for processing
			self.tagger.sendCommand(makeHex)			#send the properly formatted hex string
			self.tagger.sendEnter()
			returnCode = self.tagger.receiveSerial(1)	#wait a second then read full printout
		except SerialException:							#NFC tagger has lost COM connection, ask user to choose port again
			COMPort = self.gui.portAssign()				#prompt user to select an available COM port
			self.tagger = controlBoardSerialv13GUI.controlBoardv13_maxim(COMPort, self.gui)
			#no need to rerun function since this is one of two options the user is prompted with and let's them start when ready
			self.gui.wait(1)

		return self.findHex(returnCode, serialInstanceTag)
	
	def main(self):
		interaction = self.gui.optionSelect(header='Would you like to:', optionsText=['Read NFC', 'Program NFC'])
		if interaction == 'Read NFC':
			self.gui.clearScreen()				#getSerial not called so need to manually clear supers
			self.readHex()
		else:
			self.serialNumber = self.gui.getSerial()
			self.writeHex()
		self.tagger.sendReset()
		self.gui.restartButton()