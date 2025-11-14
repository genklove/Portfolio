import serial
from serial import SerialException
import serial.tools.list_ports
import csv
from hiPotTester import hiPotTester
from controlBoardSerialv13 import controlBoardSerialv13GUI
from itech import itech
from cmOneStopSerial import cmOneStopSerial
import airtable
from airtableScripts import airtableScripts
from colorama import Fore
import requests
import re
import os
from GUI_Class import GUI
from insulation_class import insulation
import subprocess
import atexit
from cmClasses import fetsAndShorts, functionality, fetTest

class cm_tester():
	def __init__(self):
		assyParts = airtable.Airtable('base ID','Assembled Parts','API key')
		testInstances = airtable.Airtable('base ID','Test Instances','API key')

		auth = airtable.auth.AirtableAuth('API key')
		response = requests.get('https://api.airtable.com/v0/{basekey}/{table_name}', auth=auth)

		self.airtabler = airtableScripts.airtableScripts(assyParts,testInstances,auth,response)
		self.gui = GUI(airtabler=self.airtabler, title="CM Combo Tester")

		equipment = 'AMEC-27944-1-1'
		self.equipmentObj = assyParts.match('Name',equipment, view = 'Test Equipment')

		self.partNumbers = [27219, 17997]

		self.actuatorList = []

		self.binVersion = '0.19.3.0'
		self.fullBinName = 'BATTERY_MODULE_%s_12069.2' %(self.binVersion)
		self.binFile = '"' + os.getcwd() + '\\binaries\\bmSoftware\\%s.bin"' %(self.fullBinName)
		self.pythonSoftwareVersion = '2025.8.13.4'

	def start(self):
		self.gui.test_in_progress(testName="Initial Setup")
		self.findCOMPorts()
		self.setupPorts()
		
		self.gui.test_over()

		#get one time
		self.technician = self.gui.getTechnician()
		self.temperature = self.gui.getTemp()
		
		self.cmTester.resetOCF()
		
		#running main in a while loop so all the classes and functions are terminated between runs to help with memory
		while 1:
			try:
				self.main()
			except Exception as e:
				if str(e) == 'restart loop': pass
				else: raise

	def findCOMPorts(self):
		#extract the port info from the csv file
		rawData = []
		with open('comports_cm_tester.csv', 'rU') as csvfile:
			csvreader = csv.reader(csvfile, dialect=csv.excel_tab) 
			for row in csvreader:
				rawData.append(str(row[0]))
			# get total number of rows 
			print("Total no. of rows: %d"%(csvreader.line_num))

		#match the device info to currently available ports
		ports = serial.tools.list_ports.comports()
		print("\n\rAvailable COM Ports:\n\r")
		for port, desc, hwid in sorted(ports):
			print("{}: {} [{}]".format(port, desc, hwid))
			if str(rawData[0]) in hwid:
				cmTesterPort = port
			elif str(rawData[1]) in hwid:
				itechbattport = port
			elif str(rawData[2]) in hwid:
				itechbusport = port
			elif str(rawData[3]) in hwid:
				hipottesterport = port
		
		#track the port numbers of all the equipment to exclude when connecting to control board, avoids flashing tester ESP
		self.portNumList = [str(cmTesterPort), str(itechbattport), str(itechbusport), str(hipottesterport)]
	
	def setupPorts(self, rerun: bool = False):
		try:
			#open tester ESP, close, and reopen since ESP only works after second connection
			self.cmTester = cmOneStopSerial.cmOneStopSerial(self.portNumList[0])
			self.cmTester.close()
			self.gui.wait(0.5)
			self.cmTester = cmOneStopSerial.cmOneStopSerial(self.portNumList[0])
			
			#use com port list from findCOMPorts to connect to testers
			self.itech1 = itech.itech(self.portNumList[1])
			self.itech2 = itech.itech(self.portNumList[2])
			self.hiPotTesterObj = hiPotTester.hiPotTester(self.portNumList[3])
			
			#since ITECHs could be plugged in either order, use their serial IDs to determine which is batt and which is bus
			itech1ID = self.itech1.getID()
			itech2ID = self.itech2.getID()
			print(itech1ID)
			print(itech2ID)
			if not itech2ID: raise Exception("batt psu")
			if not itech1ID: raise Exception("bus psu")
			if '803990011767840001' in itech1ID:
				self.battpsu = self.itech1
				self.buspsu = self.itech2
			elif '803990011767840001' in itech2ID:
				self.buspsu = self.itech1
				self.battpsu = self.itech2
			else:
				self.gui.remove_widget('plug and power')
				self.gui.label("Make sure both ITECHs plugged in and powered on!", name='plug and power', color='blue', big=True)
				self.gui.wait_for_plug_in(includeLabel=False)	#actively wait for new com ports to appear on the computer, then close any opened ports and redo port setup
				self.closePorts()
				self.setupPorts()
				return
			
			#use initialize pulse test to see if they are properly connected and receiving commands
			battpsuReturn = self.battpsu.initializePulseTest(1, 1)
			print(battpsuReturn)
			if "VOLTage" not in battpsuReturn: raise Exception("batt psu")
			buspsuReturn = self.buspsu.initializePulseTest(1, 1)
			print(buspsuReturn)
			if "VOLTage" not in buspsuReturn: raise Exception("bus psu")
			print(self.hiPotTesterObj.getID())

		except Exception as e:
			print(e)
			self.gui.remove_widget('plug and power')
			if "psu" in str(e) and not rerun:
				#try using the tester ESP to reset the ITECHs, if this fails the tech will have to manually disconnect and reconnect cables
				self.autoReConnectItechs()
				self.closePorts()
				self.setupPorts(rerun=True)
				return
			elif "psu" in str(e):
				battSuccess = False
				busSuccess = False
				while not battSuccess and not busSuccess:
					try:
						#use custom error messages to determine which ITECH isn't connected after auto reconnecting fails
						if "batt" in str(e):
							self.gui.label("Disconnect and reconnect ITECH 1 USB from back of ITECH (NOT FROM PC USB HUB)", name='plug and power', color='blue', big=True)
						else:
							self.gui.label("Disconnect and reconnect ITECH 2 USB from back of ITECH (NOT FROM PC USB HUB)", name='plug and power', color='blue', big=True)
						self.gui.wait_for_plug_in(False)	#wait for number of ports to increase. when a port is disconnected, the number of current ports is updated so when that port is connected again it counts as an increase

						#see if ITECHs are responding properly. repeat this process until both successfully respond
						battpsuReturn = self.battpsu.initializePulseTest(1, 1)
						print(battpsuReturn)
						buspsuReturn = self.buspsu.initializePulseTest(1, 1)
						print(buspsuReturn)
						if "VOLTage" in battpsuReturn:
							battSuccess = True
						if "VOLTage" in buspsuReturn:
							busSuccess = True
					except Exception:
						pass
			else:
				#if connection problem is not ITECH related, just wait for new port to appear and retry connecting to all ports
				self.gui.label("Make sure everything is plugged in and powered on!\n" + str(e), name='plug and power', color='blue', big=True)
				self.gui.wait_for_plug_in(includeLabel=False)
			self.closePorts()
			self.setupPorts(rerun=True)
			return
		self.gui.remove_widget('plug and power')

		#get tester ESP software version if available
		self.cmTester.sendCommand('h')
		self.cmTester.sendCommand('\r')
		espMenu = self.cmTester.receiveSerial()
		versionLine = re.search(r'==\s+VERSION: [a-zA-Z0-9]+\s+==', espMenu)
		try:
			self.testerESPVersion = re.sub(r'==\s+VERSION: ', '', re.sub(r'\s+==', '', versionLine))
		except TypeError:
			self.testerESPVersion = 'Version not specified'

	def closePorts(self, keepCMTester: bool = False):
		if not keepCMTester:					#in cases where we want to keep tester ESP but close everything else, set this argument to true
			try:
				self.cmTester.close()		#close tester ESP connection, ignores errors in case port is already disconnected or closed
			except Exception: pass
		try:
			self.hiPotTesterObj.close()	#close GPT connection, ignores errors in case port is already disconnected or closed
		except Exception: pass
		try:
			self.battpsu.close()			#close batt ITECH connection, ignores errors in case port is already disconnected or closed
		except Exception: pass
		try:
			self.buspsu.close()			#close bus ITECH connection, ignores errors in case port is already disconnected or closed
		except Exception: pass

	def runSniffer(self):
		snifferPath = 'C:/Users/' + os.getenv('username') + '/Desktop/BMLineScripts/sniffer.py'	#set path to sniffer script
		shellLine = ['python.exe', snifferPath]
		self.snifferP = subprocess.Popen(shellLine, stdout=subprocess.PIPE)	#use subprocess to run sniffer in the background without opening a new cmd window

	def reset(self):
		try:
			self.cmTester.actuator1Off()		#functionality side pressurized actuators (yokowo + maxim) ("x")
			self.cmTester.actuator2Off()		#hi pot side pressurzied actuators (yokowo) ("v")
			self.cmTester.turn12VOFF()			#12V connection to tester PCB ("2")
			self.cmTester.turnContactorsOff()	#4 blue contactors ("3")
			self.cmTester.resetOCF()			#over current fault reset on tester board ("d")
			self.cmTester.actuator3Off()		#usb connection to CM (off means connected) ("n")
			self.cmTester.actuator4Off()		#usb connection to first ITECH (off means connected) ("y")
			self.cmTester.actuator5Off()		#usb connection to second ITECH (off means connected) ("i")
		except Exception: pass
		try:
			self.battpsu.setOutputOFF()		#batt ITECH output off
		except Exception: pass
		try:
			self.buspsu.setOutputOFF()			#bus ITECH output off
		except Exception: pass
		try:
			self.hiPotTesterObj.stopTest()		#GPT output off
		except Exception: pass

	def limitedReset(self):
		try:
			self.cmTester.turnContactorsOff()		#4 blue contactors ("3")
		except Exception: pass
		try:
			self.battpsu.setOutputOFF()			#batt ITECH output off
		except Exception: pass
		try:
			self.buspsu.setOutputOFF()				#bus ITECH output off
		except Exception: pass
		try:
			self.controlBoard.turnHVOff() 			#turn off CM HV ("4")
			self.controlBoard.turnOffSafetyCheck()	#turn off CM safety check ("5")
			self.controlBoard.resetShortCircuit()	#reset short circuit ("7")
		except Exception: pass

	def connectControlBoard(self, includeLabel: bool = True):
		opened = False
		while not opened:
			if not includeLabel:
				self.cmTester.actuator3On()	#disconnect USB port to CM ("b")
				self.gui.wait(0.5)
				self.cmTester.actuator3Off()	#reconnect USB port to CM ("n")
			self.COMPort = self.gui.wait_for_plug_in(includeLabel=includeLabel)		#wait for connection to CM
			
			#check that newly plugged in com port is not one of the tester ports. if it is, restart the loop
			forbiddenPort = False
			for port in self.portNumList:
				if self.COMPort == port:
					self.COMPort = None
					forbiddenPort = True
			if forbiddenPort:
				continue

			self.gui.wait(3)
			# instantiate maxim stuff
			try:
				self.controlBoard = controlBoardSerialv13GUI.controlBoardv13_maxim(str(self.COMPort), self.gui)
				opened = self.controlBoard.serialPort.isOpen()
			except Exception as e:
				self.gui.label("error open serial port: " + str(e), name='open serial', color='red', big=True)
				self.gui.continueButton()
				self.gui.remove_widget('open serial')

	def autoReConnectItechs(self):
		self.gui.remove_widget('take a second')		#try to remove this label in case some other test already made it so there is no double instance of it
		self.gui.test_in_progress(testName='ITECH Reset')
		self.gui.label('This may take a second', name='take a second')
		self.closePorts(keepCMTester=True)			#close connection to ITECHs and GPT but keep connection to tester ESP
		self.cmTester.actuator4On()			#disconnect USB port to ITECH 1 ("t")
		self.cmTester.actuator5On()			#diconnect USB port to ITECH 2 ("u")
		#the gui root.after command queues a function to be executed after x ms. This is useful for here to have the computer already waiting for a new com port before telling the tester ESP to reconnect the port switches
		self.gui.root.after(100, self.cmTester.actuator4Off)	#reconnect USB port to ITECH 1 after 100 ms ("y")
		self.gui.wait_for_plug_in(False)							#wait for new port, will already be waiting when tester ESP activates USB switch
		self.gui.root.after(100, self.cmTester.actuator5Off)	#reconnect USB port to ITECH 2 after 100 ms ("i")
		self.gui.wait_for_plug_in(False)							#wait for new port
		self.gui.wait(3)											#additional wait time after both ITECH ports are back so there isn't a communication problem
		self.gui.test_over()
		self.gui.remove_widget('take a second')

		#fully close all ports and then set them up again
		self.closePorts()
		self.setupPorts()

	def handleSerialExceptions(self, error: Exception, itechs: bool = True, actuators: bool = True, hipot: bool = False):
		self.gui.test_over()
		self.reset()
		print("error: " + str(error))
		if ("WindowsError(5," in str(error) or "list index out of range" in str(error) or "invalid literal for int() with base 10:" in str(error)) and not hipot:
			self.gui.label("Problem encountered with connection to CM, please wait for port to reset", name='serial error')
			self.connectControlBoard(includeLabel=False)	#reconnect to the control board
		elif "WindowsError(22," in str(error) and itechs:
			self.gui.label("Porblem encountered with connection to ITECHs, please wait for ports to reset", name='serial error')
			self.autoReConnectItechs()						#reconnect to ITECHs, will also reset all testing equipment connections
		else:
			#if there is a new serial error that we have not seen before, we will try just resetting the ports
			self.gui.label("Unknown serial port error encountered, attempting to reset connections\n" + str(error), name='serial error')
			self.closePorts()
			self.setupPorts()
		
		#give the user the option to start over from the start of the test to avoid getting stuck in and endless loop where ports aren't working
		selection = self.gui.optionSelect(optionsText=['Retry', 'Start over from the beginning'])
		self.gui.remove_widget('serial error')
		if selection == 'Start over from the beginning':
			self.gui.restartButton(showButton=False)
			raise Exception('restart loop')
		#after doing a full reset of the system state, reengage actuators and 12V if applicable
		if actuators:
			self.cmTester.actuator1On()		#actuator for functionality/FET side of tester ("z")
			self.controlBoard.reboot()
			self.gui.wait(2)
			self.cmTester.turn12VON()			#turn on 12V connection to tester PCB ("1")
			self.gui.wait(2)
		elif hipot:
			self.cmTester.actuator2On()		#actuator for hi pot side of tester ("c")

	def runHiPot(self):
		#use existing insulation class script to run the test and pass it hi pot tester object and test data preamble
		ins = insulation(self.gui)
		ins.hiPotTester = self.hiPotTesterObj
		ins.testComments = 'BM Software Version: ' + self.binVersion + '\nTester ESP Software Version: ' + self.testerESPVersion + '\nPython Software Version: ' + self.pythonSoftwareVersion + '\nTesting Technician: ' + self.technician + '\n'

		testName = 'CM Insulation Test'
		while True:
			try:
				self.cmTester.actuator2On()	#engage yokowo and contact needle on hi pot side ("c")
				#######################################################
				# Step 1: 0.1kV ACW
				acwResult = ins.hiPot(stepNumber=20, voltage='0.1kV', testType='ACW', testLength=3)
				if acwResult == 'Fail':
					if ins.test_1['current'] < 0.01:
						self.gui.label("No connection between tester and CM, make sure tester is set up and CM is properly engaged", color='blue', big=True)
					else:
						self.gui.label("Capacitance too high, Disconnect CM and move to fall out shelf", color='blue', big=True)
					self.cmTester.actuator2Off()	#disengage yokowo and connecting pin ("v")
					self.gui.resultsUpload(testName=testName, deviceUnderTest=self.serialNumber, result=acwResult, testData=ins.testComments, equipment=self.equipmentObj['id'])
					self.failureType.append('ACW')
					return
				break
			except Exception as e:
				self.handleSerialExceptions(e, False, False, True)
		while True:
			try:
				# Step 2: 1kV IR
				IRresult = ins.IR(testName=testName, stepNumber=17, resistanceThreshold=9999, voltage='1kV', testLength=20)

				#rerun any fail one time but keep test data
				if IRresult == 'Fail':
					ins.testComments += 'First run results:\n\r'
					IRresult = ins.IR(testName=testName, stepNumber=17, resistanceThreshold=9999, voltage='1kV', testLength=20)
					ins.testComments += 'Second run results:\n\r'

				#if CM fails twice, log it as a true fail
				if IRresult == 'Fail':
					self.gui.label('Disconnect CM and move to fall out shelf', color='blue', big=True)
					self.cmTester.actuator2Off()	#disengage yokowo and connecting pin ("v")
					self.gui.resultsUpload(testName=testName, deviceUnderTest=self.serialNumber, result=IRresult, testData=ins.testComments, equipment=self.equipmentObj['id'])
					self.failureType.append('IR')
					return
				break
			except Exception as e:
				self.handleSerialExceptions(e, False, False, True)

		########################################################
		# Step 3: 2.6kV DCW
		while True:
			try:
				self.hipot_testResult = ins.hiPot(19, voltage='2.6kV', testType='DCW', testLength=11)

				#rerun any fail one time but keep test data
				if (self.hipot_testResult == 'Fail'):
					ins.testComments = 'First run results:\n\r' + ins.testComments
					self.hipot_testResult = ins.hiPot(19, voltage='2.6kV', testType='DCW', testLength=11)
					ins.testComments = 'Second run results:\n\r' + ins.testComments

				#if CM fails twice, log it as a true fail
				if (self.hipot_testResult == 'Fail'):
					self.gui.label('Disconnect CM and move to fall out shelf', color='blue', big=True)
					self.gui.resultsUpload(testName, self.serialNumber, self.hipot_testResult, ins.testComments, equipment=self.equipmentObj['id'], testData1=ins.dcwVoltage)
					self.failureType.append('DCW')
				else:
					self.gui.resultsUpload(testName, self.serialNumber, self.hipot_testResult, ins.testComments, equipment=self.equipmentObj['id'], testData1=ins.dcwVoltage)
				self.gui.wait(2)
				self.cmTester.actuator2Off()	#disengage yokowo and connecting pin ("v")
				break
			except SerialException as e:
				self.handleSerialExceptions(e, False, False, True)

	def flashControlBoard(self):
		self.gui.test_in_progress(testName='Flashing')
		self.gui.label("This may take a moment")
		self.controlBoard.close()		#close connection to CM so the flashing script can use the port
		
		#run the flashing scripts
		os.system('cmd /c "python C:/Python27/Lib/site-packages/espefuse.py --port %s set_flash_voltage 3.3V"' %(str(self.COMPort)))
		if self.bmVersion == 27214: os.system('cmd /c "python C:/Python27/Lib/site-packages/esptool.py --port %s --chip esp32 --baud 921600 --before default_reset --after hard_reset write_flash -u --flash_mode dio --flash_freq 40m --flash_size detect 0x1000 bootloader.bin 0x10000 %s 0x8000 partition.bin"' %(str(self.COMPort), self.binFile))

		#reconnect to the CM since flashing script is complete
		try:
			self.controlBoard = controlBoardSerialv13GUI.controlBoardv13_maxim(str(self.COMPort), self.gui)
		except Exception as e:
			self.gui.label("error open serial port: " + str(e), name='open serial', color='red', big=True)
			self.gui.continueButton()
			self.gui.remove_widget('open serial')
			self.connectControlBoard()

		#i don't know why this step exists but it's been part of flashing since v13
		for i in range(30):
			self.gui.wait(0.2)
			self.controlBoard.sendEnter()

		nvsReturns = []
		self.controlBoard.gotoNVSMenu()	#open CM NVS menu ("n")
		#update version and revision in NVS menu. when this happens, the function will return True if it is successful, so we append that return to a list to check that both operations were successful
		nvsReturns.append(self.controlBoard.editNVSMenu("10", str(self.bmRevision)))
		nvsReturns.append(self.controlBoard.editNVSMenu("11", str(self.bmVersion)))
		self.controlBoard.printNVSValue()	#printout the updated NVS values ("p")
		self.controlBoard.gotoMainMenu()	#exit out of NVS and return to normal menu ("q")

		self.controlBoard.close()			#close connection to CM again for ESP check and reflashing if needed
		self.gui.remove_widget("This may take a moment")
		if nvsReturns != [True, True]:
			self.gui.label('Flashing unsuccessful! Please try again', name='bad flash', color='dark orange')
			selection = self.gui.optionSelect(optionsText=['Retry', 'Start over from the beginning'])
			self.gui.remove_widget('bad flash')
			if selection == 'Start over from the beginning':
				self.gui.restartButton(showButton=False)
				raise Exception('restart loop')
			self.connectControlBoard(includeLabel=False)
			self.flashControlBoard()
			return
		self.gui.label("Flashing Complete")
		espResult = self.checkESP()				#check the manufacturer on the CM ESP
		if not espResult:
			raise Exception('ESP flash chip')
		self.gui.test_in_progress(testName='USB reset')
		self.connectControlBoard(includeLabel=False)	#connect to the CM once again, this time by triggering the USB port switch for a "hard reset"
	
	def checkESP(self) -> bool:
		#using subprocess, we can run the ESP check and store all the lines that would get printed to cmd
		printout = ''
		p = subprocess.Popen(['python.exe', '-m', 'esptool', '--port', self.COMPort, 'flash_id'], stdout=subprocess.PIPE)
		while True:
			line = p.stdout.readline().strip()	#get each line as it's printed to cmd
			if line:
				print(line)						#catching each line from subprocess stops it from printing so doing it manually to make sure the info can still be viewed
				printout = printout + '\n' + line
			elif p.poll() != None:				#once there are no more lines to read, stop checking
				break
		matches = re.findall(r'Manufacturer: .*', printout)
		#rerun if there is no line that contains the word "Manufacturer," otherwise check that what follows is not "20"
		if not matches:
			self.gui.label("Failed to check ESP, please try again", name='failed read', big=True)
			self.gui.continueButton()
			self.gui.remove_widget('failed read')
			self.checkESP()
		for match in matches:
			if '20' in match: 
				self.gui.label('ESP has bad flashing chip\nRemove ESP and replace with a new one', name='bad esp', color='red', big=True)
				return False
		else:
			self.gui.label('ESP GOOD', color='dark green')
			return True

	def runFunctionalityTest(self):
		#create class objects
		func = functionality.functionality(self.gui, self.cmTester, self.controlBoard, self.battpsu, self.buspsu)
		FnS = fetsAndShorts.fetsAndShorts(self.gui, self.cmTester, self.controlBoard, self.battpsu, self.buspsu)
		self.functionality_testResult = 'Fail'

		while True:
			try:
				opening = self.controlBoard.receiveSerial(False)
				print(opening)

				#check current ESP software version and skip if already up to date
				if re.findall(self.binVersion, opening):
					self.gui.label('ESP already flashed, skipping flashing')
				else:
					try:
						self.flashControlBoard()
					except Exception as e:
						#fail CM is ESP manufacturer is bad
						if 'ESP flash chip' in str(e):
							self.functionality_testResult = 'Fail'
							return
						else: raise
				break
			except SerialException as e:
				self.handleSerialExceptions(e, False, False)
				func = functionality.functionality(self.gui, self.cmTester, self.controlBoard, self.battpsu, self.buspsu)
				FnS = fetsAndShorts.fetsAndShorts(self.gui, self.cmTester, self.controlBoard, self.battpsu, self.buspsu)

		#Turn on actuator and setup connection with CM for tests
		while True:
			try:
				self.gui.test_in_progress(testName="CAN Check", testLength=7)
				self.cmTester.actuator1On()	#actuator for yokowo and maxim connection ("z")

				self.controlBoard.reboot()
				self.gui.wait(2)
				self.cmTester.turn12VON()		#enable 12V from tester PCB ("1")
				self.gui.wait(2)
				# func.shortDiscovery('bus')

				# check for CAN communication
				func.canCheck()
				#check for maxim communication
				func.maximCheck()
				break
			except SerialException as e:
				self.handleSerialExceptions(e, actuators=False)
				func = functionality.functionality(self.gui, self.cmTester, self.controlBoard, self.battpsu, self.buspsu)
				FnS = fetsAndShorts.fetsAndShorts(self.gui, self.cmTester, self.controlBoard, self.battpsu, self.buspsu)
		
		self.limitedReset()		#reset electrical state
		self.gui.wait(1)

		# check for control Board Temp Sense
		if len(self.failureType) == 0:
			while True:
				try:
					self.airtableMessage += '\nControl Board Temp Sense Check\n'
					self.airtableMessage += func.controlBoardTemperatureCheck(self.temperature)
					self.failureType += func.failureType
					break
				except SerialException as e:
					self.handleSerialExceptions(e)
					func = functionality.functionality(self.gui, self.cmTester, self.controlBoard, self.battpsu, self.buspsu)
					FnS = fetsAndShorts.fetsAndShorts(self.gui, self.cmTester, self.controlBoard, self.battpsu, self.buspsu)
		
		self.limitedReset()		#reset electrical state
		self.gui.wait(1)

		#Calibrate CB voltage and current sensors
		if len(self.failureType) == 0:
			while True:
				try:
					self.airtableMessage += '\nVoltage Calibration\n'
					self.airtableMessage += func.calibrateVoltage()
					self.failureType += func.failureType
					break
				except (SerialException, IndexError, ValueError) as e:
					self.handleSerialExceptions(e)
					func = functionality.functionality(self.gui, self.cmTester, self.controlBoard, self.battpsu, self.buspsu)
					FnS = fetsAndShorts.fetsAndShorts(self.gui, self.cmTester, self.controlBoard, self.battpsu, self.buspsu)
		
		self.limitedReset()		#reset electrical state
		self.gui.wait(1)

		if len(self.failureType) == 0:
			firstRun = True
			while True:
				try:
					self.airtableMessage += '\nCurrent Calibration\n'
					self.airtableMessage += func.calibrateCurrent()
					self.failureType += func.failureType
					break
				except (SerialException, IndexError, ValueError) as e:
					self.handleSerialExceptions(e)
					func = functionality.functionality(self.gui, self.cmTester, self.controlBoard, self.battpsu, self.buspsu)
					FnS = fetsAndShorts.fetsAndShorts(self.gui, self.cmTester, self.controlBoard, self.battpsu, self.buspsu)
		
		self.limitedReset()		#reset electrical state
		self.gui.wait(1)

		#Capture resistance of CM for data
		if len(self.failureType) == 0:
			while True:
				try:
					self.airtableMessage += '\nResistance Capture\n'
					self.airtableMessage += func.resistanceCapture()
					self.failureType += func.failureType
					break
				except (SerialException, IndexError, ValueError) as e:
					self.handleSerialExceptions(e)
					func = functionality.functionality(self.gui, self.cmTester, self.controlBoard, self.battpsu, self.buspsu)
					FnS = fetsAndShorts.fetsAndShorts(self.gui, self.cmTester, self.controlBoard, self.battpsu, self.buspsu)
		
		self.limitedReset()		#reset electrical state
		self.gui.wait(1)

		if len(self.failureType) == 0:
			#Check FETs
			while True:
				try:
					self.airtableMessage += '\nPrecharge Check\n'
					self.controlBoard.reboot()
					self.airtableMessage += func.preChargeCheck()
					self.failureType += func.failureType
					break
				except (SerialException, IndexError, ValueError) as e:
					self.handleSerialExceptions(e)
					func = functionality.functionality(self.gui, self.cmTester, self.controlBoard, self.battpsu, self.buspsu)
					FnS = fetsAndShorts.fetsAndShorts(self.gui, self.cmTester, self.controlBoard, self.battpsu, self.buspsu)
		
		self.limitedReset()		#reset electrical state
		self.gui.wait(1)

		if len(self.failureType) == 0:
			while True:
				try:
					self.airtableMessage += '\nFET Check Sequence\n'
					self.airtableMessage += FnS.fetCheckSequence()
					self.failureType += FnS.failureType
					break
				except (SerialException, IndexError, ValueError) as e:
					self.handleSerialExceptions(e)
					func = functionality.functionality(self.gui, self.cmTester, self.controlBoard, self.battpsu, self.buspsu)
					FnS = fetsAndShorts.fetsAndShorts(self.gui, self.cmTester, self.controlBoard, self.battpsu, self.buspsu)
		
		self.limitedReset()		#reset electrical state
		self.gui.wait(1)

		if len(self.failureType) > 0: #there is a failure
			unique_failureType = list(set(self.failureType))	#remove dupicates from list of failure types
			self.gui.label('Control Board Functionality Test FAIL\n' + str(unique_failureType), color='red', big=True)
			self.functionality_testResult = 'Fail'
			self.gui.resultsUpload('Control Board Test', self.serialNumber, self.functionality_testResult, self.airtableMessage, self.equipmentObj['id'], failureType=unique_failureType)
		else:
			self.gui.label("Control Board Functionality Test PASS", color='dark green', big=True)
			self.functionality_testResult = 'Pass'
			self.gui.resultsUpload('Control Board Test', self.serialNumber, self.functionality_testResult, self.airtableMessage, self.equipmentObj['id'])

	def runFETTest(self):
		#create class objects
		fet = fetTest.fetTest(self.gui, self.cmTester, self.controlBoard, self.battpsu, self.buspsu)
		FnS = fetsAndShorts.fetsAndShorts(self.gui, self.cmTester, self.controlBoard, self.battpsu, self.buspsu)

		#Perform low voltage short circuit tests
		if len(self.failureType) == 0:
			while True:
				try:
					self.airtableMessage += '\nLow Voltage Short Circuit Check Sequence\n'
					self.airtableMessage += FnS.LVSCCheckSequence()
					self.failureType += FnS.failureType
					break
				except (SerialException, IndexError, ValueError) as e:
					self.handleSerialExceptions(e)
					fet = fetTest.fetTest(self.gui, self.cmTester, self.controlBoard, self.battpsu, self.buspsu)
					FnS = fetsAndShorts.fetsAndShorts(self.gui, self.cmTester, self.controlBoard, self.battpsu, self.buspsu)
		
		self.limitedReset()		#reset electrical state
		self.gui.wait(1)

		#Run HV short circuit tests
		if len(self.failureType) == 0:
			while True:
				try:
					self.airtableMessage += '\nHigh Voltage Short Circuit Check Sequence\n'
					self.airtableMessage += FnS.HVSCCheckSequence()
					self.failureType += FnS.failureType
					break
				except (SerialException, IndexError, ValueError) as e:
					self.handleSerialExceptions(e)
					fet = fetTest.fetTest(self.gui, self.cmTester, self.controlBoard, self.battpsu, self.buspsu)
					FnS = fetsAndShorts.fetsAndShorts(self.gui, self.cmTester, self.controlBoard, self.battpsu, self.buspsu)
		
		self.limitedReset()		#reset electrical state
		self.gui.wait(1)
		
		#Stress CM with high current
		if len(self.failureType) == 0:
			while True:
				try:
					self.airtableMessage += '\nHigh Current Test\n'
					self.airtableMessage += fet.runCurrent()
					self.failureType += fet.failureType
					self.controlBoard.resetShortCircuit()
					break
				except (SerialException, IndexError, ValueError) as e:
					self.handleSerialExceptions(e)
					fet = fetTest.fetTest(self.gui, self.cmTester, self.controlBoard, self.battpsu, self.buspsu)
					FnS = fetsAndShorts.fetsAndShorts(self.gui, self.cmTester, self.controlBoard, self.battpsu, self.buspsu)
		
		self.limitedReset()		#reset electrical state
		self.gui.wait(1)
		
		#recheck FETs after current stress
		while True:
			try:
				self.airtableMessage += '\nFET Check Sequence\n'
				self.airtableMessage += FnS.fetCheckSequence()
				self.failureType += FnS.failureType
				break
			except (SerialException, IndexError, ValueError) as e:
				self.handleSerialExceptions(e)
				fet = fetTest.fetTest(self.gui, self.cmTester, self.controlBoard, self.battpsu, self.buspsu)
				FnS = fetsAndShorts.fetsAndShorts(self.gui, self.cmTester, self.controlBoard, self.battpsu, self.buspsu)

		if len(self.failureType) > 0: #there is a failure
			unique_failureType = list(set(self.failureType))	#remove duplicates from list of failure types
			self.gui.label("FET Test FAIL\n" + str(unique_failureType), color='red', big=True)
			self.fet_testResult = 'Fail'
			self.gui.resultsUpload('FET Test', self.serialNumber, self.fet_testResult, self.airtableMessage, self.equipmentObj['id'], failureType=unique_failureType)
		else:
			self.gui.label("FET Test PASS", color='dark green', big=True)
			self.fet_testResult = 'Pass'
			self.gui.resultsUpload('FET Test', self.serialNumber, self.fet_testResult, self.airtableMessage, self.equipmentObj['id'])

	def main(self):
		#reset and define variables
		self.failureType = []
		self.airtableMessage = 'BM Software Version: ' + self.binVersion + '\nTester ESP Software Version: ' + self.testerESPVersion + '\nPython Software Version: ' + self.pythonSoftwareVersion +'\nTesting Technician: ' + self.technician + '\n'
		self.airtableMessage += 'Logs are formatted as [time data, CM Batt V, CM Bus V, CM current, [CM temp readings], CM HV Status, CM short circuit detection, test mode, cycle, result, Batt ITECH V, Bus ITECH V, Batt ITECH current, Bus ITECH current]\n'
		self.reset()
		self.functionality_testResult = ''
		self.hipot_testResult = ''
		self.fet_testResult = ''
		self.controlBoard = None
		####################################################################################
		self.serialNumber = self.gui.getSerial()
		#these variable could be changed during get serial, so ask GUI for current values
		self.temperature = self.gui.temperature
		self.technician = self.gui.technician

		#split serial number up to get version number
		temp = re.findall('[0-9]+', self.serialNumber)
		res = list(map(int, temp))
		print(res)
		hwVersion = res[0]

		#determine if part number is accepted
		if hwVersion == 27219:
			self.bmVersion = 27214
			self.bmRevision = 2
		else:
			self.gui.label("Part number not supported by this test", color='orange red', big=True)
			self.gui.restartButton()	#clears GUI elements for next run
			return
		
		self.gui.label("Slide control module to the hi-pot test end (left end) and engage the stopper from the top\nPressing continue will cause the tester to come down on the CM and run HV", name="slide left", color='blue', big=True)
		self.gui.label("HANDS AWAY FROM TESTER", name='hands away', color='orange red', big=True)
		self.gui.root.bind('<Control-Alt-s>', lambda event, string='quit': self.gui._buttonCheck(string))	#adds key bind of Ctrl+Alt+s as a way to skip
		try:
			self.gui.skipButton()
			self.gui.continueButton()
			skip = ''
		except Exception:
			skip = 'skip'
			self.gui.clearFrame(self.gui.footerFrame)
		self.gui.root.unbind("<Control-Alt-s>")	#unbind skip hotkey
		self.gui.remove_widget("slide left")
		self.gui.remove_widget('hands away')

		if skip == 'skip':
			self.hipot_testResult = 'skip'
			self.gui.label("Hi-Pot Test Skipped", big=True)
		else:
			self.runHiPot()
			self.gui.test_over()
			if len(self.failureType) > 0:
				self.gui.restartButton()	#clears GUI elements for next run
				return
			self.gui.label('Disengage the left stopper and release the tray', name='disengage', color='blue', big=True)

		####################################################################################
		self.gui.label("Slide control module to the right end and engage the right stopper from the top", name='slide right', color='blue', big=True)
		self.connectControlBoard()
		self.gui.remove_widget('disengage')
		self.gui.remove_widget('slide right')
		
		print("This is control board: " + self.COMPort)

		self.gui.label("Continue to Functionality Test?", name="functionality?", color='blue', big=True)
		self.gui.label("Pressing continue will engage tester and begin functionality\nFunctionality includes HIGH VOLTAGE tests", name='continue to func', color='blue', big=True)
		self.gui.label("HANDS AWAY FROM TESTER", name='hands away', color='orange red', big=True)
		self.gui.root.bind('<Control-Alt-s>', lambda event, string='quit': self.gui._buttonCheck(string))	#adds key bind of Ctrl+Alt+s as a way to skip
		try:
			self.gui.skipButton()
			self.gui.continueButton()
			skip = ''
		except Exception:
			skip = 'skip'
			self.gui.clearFrame(self.gui.footerFrame)
		self.gui.root.unbind("<Control-Alt-s>")	#unbind skip hotkey
		self.gui.remove_widget("functionality?")
		self.gui.remove_widget("continue to func")
		self.gui.remove_widget('hands away')

		doResistanceOnly = False
		if skip == 'skip':
			self.gui.test_over()
			self.functionality_testResult = 'skip'
			self.gui.label("Functionality Test Skipped", big=True)
			self.gui.label("Press continue to engage tester and begin FET test\nOnce continue is pressed, the tester will come down on the CM and run HV", name='continue to fet', color='blue', big=True)
			self.gui.label("HANDS AWAY FROM TESTER", name='hands away', color='orange red', big=True)
			self.gui.root.bind('<Control-Shift-R>', lambda event, string='quit': self.gui._buttonCheck(string))		#adds key bind of Ctrl+Shift+r as a way to do only resistance capture
			try:
				self.gui.continueButton()
			except Exception:
				doResistanceOnly = True
			self.gui.root.unbind('<Control-Shift-R>')	#unbind hotkey for resistance only check
			self.gui.remove_widget("continue to fet")
			self.gui.remove_widget('hands away')
		else:
			self.runFunctionalityTest()

		if ((self.functionality_testResult == 'skip') or (self.functionality_testResult == 'Pass')) and (not doResistanceOnly):
			if self.functionality_testResult == 'skip':
				self.cmTester.actuator1On()		#engage yokowo and maxim connections ("z")
				self.controlBoard.reboot()
				self.gui.wait(2)
				self.cmTester.turn12VON()
				self.gui.wait(2)
			else:
				self.airtableMessage += '\nBEGIN FET TEST SECTION\n'
			self.runFETTest()
		elif doResistanceOnly:
			self.cmTester.actuator1On()		#engage yokowo and maxim connections ("z")
			self.controlBoard.reboot()
			self.gui.wait(2)
			self.cmTester.turn12VON()
			self.gui.wait(2)
			self.fet_testResult = 'skip'
			func = functionality.functionality(self.gui, self.cmTester, self.controlBoard, self.battpsu, self.buspsu)
			self.airtableMessage += func.resistanceCapture()
		self.gui.test_over()

		self.printResults()

		self.controlBoard.close()
		self.reset()		#disengage actuators and reset all mechanical parts
		self.gui.wait_for_unplug()

		#check for any records that didn't upload and run sniffer if so
		fails = os.listdir("failed_upload")
		if len(fails) != 0:
			self.runSniffer()

		#since we retest all "Test Fails," tell the tech to do that now instead of having CM sit on shelf for awhile
		if 'Test Fail' in self.failureType:
			self.gui.label("Something went wrong, please retest this CM", name='disengage', color='blue', big=True)
		else:
			self.gui.label('Disengage the right stopper, release the tray, remove CM, and add appropriate dots', name='disengage', color='blue', big=True)
		self.gui.restartButton()

	def printResults(self):
		#condense result info in cmd window
		if self.hipot_testResult == 'Pass':
			print(Fore.GREEN + 'Insulation Test: Pass' + Fore.RESET)
		elif self.hipot_testResult == 'skip':
			print(Fore.YELLOW + 'Insulation Test: Skipped' + Fore.RESET)
		else:
			print(Fore.RED + 'Insulation Test: Fail' + Fore.RESET)

		if self.functionality_testResult == 'Pass':
			print(Fore.GREEN + 'Functionality Test: Pass' + Fore.RESET)
		elif self.functionality_testResult == 'skip':
			print(Fore.YELLOW + 'Functionality Test: Skipped' + Fore.RESET)
		else:
			print(Fore.RED + 'Functionality Test: Fail' + Fore.RESET)

		if self.fet_testResult == 'Pass':
			print(Fore.GREEN + 'FET Test: Pass' + Fore.RESET)
		elif self.fet_testResult == '' or self.fet_testResult == 'skip':
			print(Fore.YELLOW + 'FET Test: Skipped' + Fore.RESET)
		else:
			print(Fore.RED + 'FET Test: Fail' + Fore.RESET)

tester = cm_tester()
#make the tester reset electrically and mechanically to the best of the script's ability whenever the script crashes or closes
atexit.register(tester.reset)
tester.start()
tester.gui.root.mainloop()		#keeps the GUI open when waiting for the user to interact