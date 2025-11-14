import time
from cblog import cblog
from colorama import Fore
from itech import itech
from GUI_Class import GUI
from cmOneStopSerial import cmOneStopSerial
from controlBoardSerialv13 import controlBoardSerialv13GUI

class functionality():
	def __init__(self, gui: GUI, cmTester: cmOneStopSerial.cmOneStopSerial, controlBoard: controlBoardSerialv13GUI.controlBoardv13_maxim, battpsu: itech.itech, buspsu: itech.itech):
		#import current objects to be used here
		self.gui = gui
		self.cmTester = cmTester
		self.controlBoard = controlBoard
		self.battpsu = battpsu
		self.buspsu = buspsu
		
		#setup cblog function from cblog class
		cblog_class = cblog(gui=gui, controlBoard=controlBoard, battpsu=battpsu, buspsu=buspsu)
		self.cblog = cblog_class.cblog

		self.failureType = []

	def shortDiscovery(self, inputfeed: str['batt', 'bus']) -> str:
		if 'batt' in inputfeed:
			self.cmTester.feedBattShortBus() ## change on where you want to feed your power
			__voltage = 19

			while(1): ### change buspsu or battpsu to your desired input
				self.battpsu.setVoltage(__voltage)
				self.battpsu.setOutputON()
				self.gui.wait(1)
				self.cmTester.resetOCF()
				self.controlBoard.turnOffSafetyCheck()	#turn off CM internal safety check ("5")
				self.controlBoard.turnHVOn()			#clsoe FETs ("3")
				aM = self.cblog('short discovery',__voltage)
				airtableMessage = aM[-1]
				self.controlBoard.turnHVOff()			#open FETs ("4")
				self.gui.wait(1)
				__voltage = __voltage + 0.5
		elif 'bus' in inputfeed:
			self.cmTester.feedBusShortBatt() ## change on where you want to feed your power
			__voltage = 19

			while(1): ### change buspsu or battpsu to your desired input
				self.buspsu.setVoltage(__voltage)
				self.buspsu.setOutputON()
				self.gui.wait(1)
				self.cmTester.resetOCF()
				self.controlBoard.turnOffSafetyCheck()	#turn off CM internal safety check ("5")
				self.controlBoard.turnHVOn()			#close FETs ("3")
				aM = self.cblog('short discovery',__voltage)
				airtableMessage += aM[-1]
				self.controlBoard.turnHVOff()			#open FETs ("4")
				self.gui.wait(1)
				__voltage = __voltage + 0.5
		
		return airtableMessage

	def canCheck(self):
		#check for a specific line of dialogue when connecting/resetting the CM ESP
		if 'Joined network' in self.controlBoard.receiveSerial(False):
			self.gui.label("CAN Test Pass", color='dark green')
		else:
			self.gui.label("CAN Test Fail", color='red')
			self.failureType.append('CAN')

	def maximCheck(self):
		self.gui.test_in_progress(testName='Maxim Check', testLength=10)
		self.cmTester.maximBMSOn()			#establish maxim connection to CM ("9")
		self.controlBoard.reboot()			#reboot CM after change to maxim
		self.gui.wait(2)
		#check for a specific line of dialogue in the CM reboot printout
		if 'Uart rx busy error' in self.controlBoard.out:
			self.gui.label("Maxim Test Fail", color='red')
			self.failureType.append('Maxim')
		else:
			self.gui.label('Maxim Test Pass', color='dark green')
		
		self.cmTester.maximBMSOff()		#close maxim connection to CM ("0")
		self.controlBoard.reboot()			#reboot CM after change to maxim

	def controlBoardTemperatureCheck(self, _ambientTemperature: int) -> str:
		airtableMessage = ''
		detailedFail = ''
		self.gui.test_in_progress(testName="Temperature/Humidity Check", testLength=6)
		#get the CB temps and humidity from full details printout ("d")
		soc, cellVoltages, sumOfCellVoltage, bmVoltage, busVoltage, current, cellTemperatures, controlBoardTemperatures, busbarVoltage, humidity = self.controlBoard.getDetails(cmTest=True)
		_ambientTemperatureOffset = 20
		_ambientTemperatureMax = _ambientTemperature + _ambientTemperatureOffset
		_ambientTemperatureMin = _ambientTemperature - _ambientTemperatureOffset

		_tempError = 0
		_idx = 0
		for i in controlBoardTemperatures:
			if _ambientTemperatureMin <= i <= _ambientTemperatureMax:	#check that each thermistor value is within +-20 degrees of entered ambient temp
				pass
			else:
				_tempError = _tempError + 1		#if one fails to fall within this range, mark that there is an error
			_idx = _idx + 1

		cbtemp_difference = max(controlBoardTemperatures)-min(controlBoardTemperatures)		#get the delta of the thermistors

		if _tempError == 0 and (0 < cbtemp_difference < 1.0):
			aM = self.cblog('CB Temp Sense Test', 0, 'Pass', True)
			airtableMessage += aM[-1]
		elif cbtemp_difference >= 1:
			aM = self.cblog('CB Temp Sense Test', 0, 'Fail', True)
			airtableMessage += aM[-1]
			detailedFail = 'Difference between thermistors > 1\n'
			self.failureType.append('CB Temp Sense - Unequal thermistors')
			# self.failureType.append('CB Temp Sense')
		elif cbtemp_difference == 0:
			aM = self.cblog('CB Temp Sense Test', 0, 'Fail', True)
			airtableMessage += aM[-1]
			detailedFail = 'Thermistors not reading correctly\n'
			self.failureType.append('CB Temp Sense - Reading error')
		else:
			aM = self.cblog('CB Temp Sense Test', 0, 'Fail', True)
			airtableMessage += aM[-1]
			detailedFail = 'Difference in ambient and CM > ' + str(_ambientTemperatureOffset) + '\n'
			self.failureType.append('CB Temp Sense - Ambient difference')
			# self.failureType.append('CB Temp Sense')

		if humidity > 100:		#humidity >100 can be from a failed humidity sensor or if no humidity value is detected in the printout (automatically set to 130% in this case)
			aM = self.cblog('Humidity Sensor Test', humidity, 'Fail', True)
			airtableMessage += aM[-1]
			detailedFail += 'Humidity sensor reading > 100\n'
			self.failureType.append('CB Temp Sense - Humidity')
		else:
			aM = self.cblog('Humidity Sensor Test', humidity, 'Pass', True)
			airtableMessage += aM[-1]
		if detailedFail:
			self.gui.label(detailedFail[:-1])
			airtableMessage += detailedFail
		
		return airtableMessage

	def preChargeCheck(self) -> str:
		airtableMessage = ''
		self.gui.test_in_progress(HV=True, testName='Precharge Check', testLength=6)
		self.cmTester.feedBattOpenBus()		#engage contactors to feed batt and open bus ("4")
		self.battpsu.setVoltage(200)			#set batt ITECH voltage
		self.battpsu.setOutputON()				#turn on batt ITECH
		self.gui.wait(1)
		self.controlBoard.turnPCOn()			#turn precharge on on the CM ("x")
		self.gui.wait(1)
		__bmVoltage, __busVoltage, current, cbTemp, aM = self.cblog('Precharge Check', 0)
		airtableMessage += aM
		self.battpsu.setOutputOFF()			#turn off batt ITECH
		if ((__bmVoltage - __busVoltage) < 7) or ((__bmVoltage - __busVoltage) > 3):		#BAD CHECK, THIS WILL ALWAYS PASS
			self.gui.label("Precharge Check Pass", color='dark green')
		else:
			self.gui.label("Precharge Check Fail", color='red')
			detailedFail = 'batt - bus < 3 or batt - bus > 7\n'
			self.gui.label(detailedFail[:-1])
			airtableMessage += detailedFail
			self.failureType.append('Precharge - batt bus difference')
			# self.failureType.append('Precharge')
		
		return airtableMessage

	def preFetCheck(self) -> str:
		airtableMessage = ''
		detailedFail = ''
		self.gui.test_in_progress(HV=True, testName='Pre FET Check', testLength=28)
		self.cmTester.feedBattfeedBus()		#engage contactors to feed both batt and bus ("8")

		#batt->bus off check:
		self.controlBoard.turnHVOff()			#open FETs ("4")
		self.battpsu.setVoltage(5)				#set batt ITECH V
		self.buspsu.setVoltage(1)				#set bus ITECH V
		self.buspsu.setOutputON()				#turn on bus ITECH
		self.battpsu.setOutputON()				#turn on batt ITECH
		self.gui.wait(1)

		#get the current values from the ITECHs
		curr_batt_1 = self.battpsu.getCurrent()
		curr_bus_1 = self.buspsu.getCurrent()
		if (curr_batt_1 < 0.07) and (curr_bus_1 > -0.07):	#check that current is below 0.07A and flowing from batt to bus
			aM = self.cblog('pre batt->bus off', 0, 'Pass')
			airtableMessage += aM[-1]
		else:
			aM = self.cblog('pre batt->bus off', 0, 'Fail')
			airtableMessage += aM[-1]
			detailedFail += 'An ITECH absolute current reading < 0.07\n'
			self.failureType.append('pre batt->bus off')
		print('Batt current is: ' + str(curr_batt_1))
		print('Bus current is: ' + str(curr_bus_1))

		self.battpsu.setOutputOFF()		#turn off batt ITECH
		self.buspsu.setOutputOFF()			#turn off bus ITECH
		self.gui.wait(2)

		#batt->bus on check
		self.controlBoard.turnOffSafetyCheck()	#turn off CM internal safety check ("5")
		self.gui.wait(1)
		self.controlBoard.turnHVOn()		#close FETs ("3")
		self.gui.wait(1)
		self.battpsu.setOutputON()			#turn on batt ITECH
		self.buspsu.setOutputON()			#turn on bus ITECH
		self.gui.wait(1)
		
		#get the current values from the ITECHs
		curr_batt_2 = self.battpsu.getCurrent()
		curr_bus_2 = self.buspsu.getCurrent()
		if (curr_batt_2) and (curr_bus_2):		#check that both ITECHs have a nonzero current reading
			aM = self.cblog('pre batt->bus on', 0, 'Pass')
			airtableMessage += aM[-1]
		else:
			aM = self.cblog('pre batt->bus on', 0, 'Fail')
			airtableMessage += aM[-1]
			detailedFail += 'An ITECH has no current reading\n'
			self.failureType.append('pre batt->bus on')
		print('Batt current is: ' + str(curr_batt_2))
		print('Bus current is: ' + str(curr_bus_2))
		self.controlBoard.turnHVOff()		#open FETs ("4")

		self.battpsu.setOutputOFF()		#turn off batt ITECH
		self.buspsu.setOutputOFF()			#turn off bus ITECH
		self.gui.wait(2)

		#bus->batt off check:

		#swap ITECH voltage settings to change direction of current
		self.battpsu.setVoltage(1)
		self.buspsu.setVoltage(5)
		self.battpsu.setOutputON()			#turn on batt ITECH
		self.buspsu.setOutputON()			#turn on bus ITECH
		self.gui.wait(1)

		#get the current values from the ITECHs
		curr_batt_3 = self.battpsu.getCurrent()
		curr_bus_3 = self.buspsu.getCurrent()
		if (curr_bus_3) and (curr_batt_3):		#check that both ITECHs have a nonzero current reading
			aM = self.cblog('pre bus->batt off', 0, 'Pass')
			airtableMessage += aM[-1]
		else:
			aM = self.cblog('pre bus->batt off', 0, 'Fail')
			airtableMessage += aM[-1]
			detailedFail += 'An ITECH has no current reading\n'
			self.failureType.append('pre bus->batt off')
		print('Batt current is: ' + str(curr_batt_3))
		print('Bus current is: ' + str(curr_bus_3))

		self.battpsu.setOutputOFF()		#turn off batt ITECH
		self.buspsu.setOutputOFF()			#turn off bus ITECH
		self.gui.wait(2)

		#bus->batt on check
		self.controlBoard.turnHVOn()		#close FETs ("3")
		self.gui.wait(1)
		self.battpsu.setOutputON()			#turn on batt ITECH
		self.buspsu.setOutputON()			#turn on bus ITECH
		self.gui.wait(1)

		#get the current values from the ITECHs
		curr_bus_4 = self.buspsu.getCurrent()
		curr_batt_4 = self.battpsu.getCurrent()
		if (curr_bus_4 > 0.93) and (curr_batt_4 < -0.93):	#check that current is above 0.93A and flowing from bus to batt
			aM = self.cblog('pre bus->batt on', 0, 'Pass')
			airtableMessage += aM[-1]
		else:
			aM = self.cblog('pre bus->batt on', 0, 'Fail')
			airtableMessage += aM[-1]
			detailedFail += 'An ITECH absolute current reading > 0.93\n'
			self.failureType.append('pre bus->batt on')
		print('Batt current is: ' + str(curr_batt_4))
		print('Bus current is: ' + str(curr_bus_4))

		self.controlBoard.turnHVOff()		#open FETs ("4")
		self.buspsu.setOutputOFF()			#turn off bus ITECH
		self.battpsu.setOutputOFF()		#turn off batt ITECH
		self.cmTester.turnContactorsOff()	#open all contactors ("3")

		if len(self.failureType) == 0:
			self.gui.label('Pre FET Check Pass', color='dark green')
		else:
			self.gui.label('Pre FET Check Fail', color='red')
			self.gui.label(detailedFail)
			airtableMessage += detailedFail
		
		return airtableMessage

	def calibrateVoltage(self) -> str:
		airtableMessage = ''
		self.gui.test_in_progress(HV=True, testName='Voltage Calibration', testLength=26)
		self.cmTester.feedBattOpenBus()			#engage contactors to feed batt and open bus ("4")
		self.gui.wait(0.5)
		__voltageError = 1
		self.battpsu.initializePulseTest(5,5)		#set batt ITECH current limits to +-5A
		self.battpsu.setVoltage(200)				#set batt ITECH V

		self.controlBoard.turnOffSafetyCheck()		#turn off CM internal safety check ("5")
		self.gui.wait(1)
		self.controlBoard.turnHVOn()				#close FETs ("3")
		self.controlBoard.receiveSerial(True)

		self.controlBoard.calibrateVoltage()		#open CM voltage calibration menu ("g") and begin the calibration process ("u")
		self.controlBoard.receiveSerial(True)
		# self.gui.wait(1)

		print(Fore.RED + "Starting Calibrating! CAUTION HIGH VOLTAGE!" + Fore.RESET)

		self.battpsu.setOutputON()					#turn on batt ITECH

		self.battpsu.setVoltage(200)				#set batt ITECH V
		self.gui.wait(1)
		self.controlBoard.sendEnter()				#interact with CM menu
		self.gui.wait(1)

		self.battpsu.setVoltage(300)				#set batt ITECH V
		self.gui.wait(1)	
		self.controlBoard.sendEnter()				#interact with CM menu
		self.gui.wait(1)

		self.battpsu.setVoltage(400)				#set batt ITECH v
		self.gui.wait(1)
		self.controlBoard.sendEnter()				#interact with CM menu
		self.gui.wait(1)

		self.battpsu.setVoltage(200)				#set batt ITECH V
		self.gui.wait(1)
		self.controlBoard.sendEnter()				#interact with CM menu
		self.gui.wait(1)

		self.battpsu.setVoltage(300)				#set batt ITECH V
		self.gui.wait(1)
		self.controlBoard.sendEnter()				#interact with CM menu
		self.gui.wait(1)

		self.battpsu.setVoltage(400)				#set batt ITECH V
		self.gui.wait(1)
		self.controlBoard.sendEnter()				#interact with CM menu
		self.gui.wait(1)
		self.battpsu.setOutputOFF()				#turn off batt ITECH

		self.controlBoard.receiveSerial(True)
		self.controlBoard.sendCommand("q")			#exit out of the voltage calibration menu ("q")
		self.controlBoard.reboot()
		self.controlBoard.turnOffSafetyCheck()		#turn off CM internal safety check after reboot ("5")
		self.gui.wait(1)
		self.controlBoard.turnHVOn()				#close FETs ("3")
		self.battpsu.setVoltage(400)				#set batt ITECH V
		self.battpsu.setOutputON()					#turn on batt ITECH
		self.gui.wait(1.5)
		__bmVoltage, __busVoltage = self.controlBoard.getBMVBusV(True)		#get batt and bus voltages from CM
		print("BM Voltage:  " + str(__bmVoltage))
		print("Bus Voltage: " + str(__busVoltage))
		#check that batt and bus voltages are within accepted deviation from batt ITECH value
		if (abs(400 - __bmVoltage) < __voltageError) or (abs(400 - __busVoltage) < __voltageError):
			aM = self.cblog('Voltage Calibration', 0, 'Pass', True)
			airtableMessage += aM[-1]
		else:
			aM = self.cblog('Voltage Calibration', 0, 'Fail', True)
			airtableMessage += aM[-1]
			detailedFail = 'Batt or bus voltage > '+ str(__voltageError) + 'V away from 400V\n'
			self.gui.label(detailedFail[:-1])
			airtableMessage += detailedFail
			self.failureType.append('Voltage Cal - incorrect reading')
			# self.failureType.append('Voltage Calibration')

		self.battpsu.setOutputOFF()				#turn off batt ITECH
		self.controlBoard.turnHVOff()				#open FETs ("4")
		self.gui.wait(0.5)

		return airtableMessage

	def calibrateCurrent(self) -> str:
		airtableMessage = ''
		__current = -10
		__increment = 10
		__endCurrent = 20

		self.gui.test_in_progress(HV=True, testName='Current Calibration', testLength=34)
		self.cmTester.feedBattfeedBus()			#engage contactors to feed both batt and bus ("8")
		self.controlBoard.turnOffSafetyCheck()		#turn off CM internal safety check ("5")
		self.gui.wait(0.5)
		self.controlBoard.turnHVOn()				#close FETs ("3")
		self.gui.wait(0.5)
		self.controlBoard.calibrateCurrent()		#begin CM current calibration process ("u")
		self.gui.wait(0.5)

		self.battpsu.initializePulseTest(21,21)	#set batt ITECH current limits to +-21A
		self.buspsu.initializePulseTest(21,21)		#set bus ITECH current limits to +-21A
		self.battpsu.setVoltage(1)					#set batt ITECH V
		self.buspsu.setVoltage(5)					#set bus ITECH V
		self.buspsu.setOutputON()					#turn on bus ITECH
		self.battpsu.setOutputON()					#turn on batt ITECH
		self.gui.wait(0.5)

		while(__current <= __endCurrent):
			
			if (__current < 0):
				self.battpsu.setVoltage(1)			#set batt ITECH V
				self.buspsu.setVoltage(7)			#set bus ITECH V
			elif (__current == 0):
				self.buspsu.setOutputON()			#turn on bus ITECH
				self.battpsu.setOutputON()			#turn on batt ITECH
			elif (__current > 0):
				self.battpsu.setVoltage(7)			#set batt ITECH V
				self.buspsu.setVoltage(1)			#set bus ITECH V
			self.battpsu.setCurrent(abs(__current))	#set batt ITECH current
			self.buspsu.setCurrent(abs(__current))		#set bus ITECH current
			self.gui.wait(1.5)
			self.controlBoard.sendEnter()			#interact with CM menu
			rx = self.controlBoard.receiveSerial(True)
			__current = __current + __increment

		self.buspsu.setOutputOFF()					#turn off bus ITECH
		self.battpsu.setOutputOFF()				#turn off batt ITECH
		self.controlBoard.reboot()					#reboot CM
		self.controlBoard.turnOffSafetyCheck()		#turn off CM internal safety check ("5")
		self.gui.wait(0.5)
		self.controlBoard.turnHVOn()				#close FETs ("3")
		self.controlBoard.receiveSerial(True)

		self.buspsu.setOutputON()					#turn on bus ITECH
		self.battpsu.setOutputON()					#turn on batt ITECH

		__current = -40
		__increment = 40
		__endCurrent = 40

		while(__current <= __endCurrent):
			
			if (__current < 0):
				self.battpsu.setVoltage(1)			#set batt ITECH V
				self.buspsu.setVoltage(7)			#set bus ITECH V
			elif (__current == 0):
				self.buspsu.setOutputON()			#turn on bus ITECH
				self.battpsu.setOutputON()			#turn on batt ITECH
			elif (__current > 0):
				self.battpsu.setVoltage(7)			#set batt ITECH V
				self.buspsu.setVoltage(1)			#set bus ITECH V
			self.battpsu.setCurrent(abs(__current))	#set batt ITECH current
			self.buspsu.setCurrent(abs(__current))		#set bus ITECH current

			bmVoltage, busVoltage, current, cbTemps, aM = self.cblog('current calibration', __current)
			airtableMessage += aM
			#check that CM current reading is within 0.9A of expected
			if abs(abs(current) - abs(__current)) < 0.9: # 1% error
				aM = self.cblog('current calibration', __current, 'Pass')
				airtableMessage += aM[-1]
			else:
				aM = self.cblog('current calibration', __current, 'Fail')
				airtableMessage += aM[-1]
				detailedFail = 'Current reading > 0.9A away from ' + str(__current) + '\n'
				self.gui.label(detailedFail[:-1])
				airtableMessage += detailedFail
				self.failureType.append('Current Cal - incorrect reading')

			# ADD TEMP CHECK:
			
			__current = __current + __increment

		self.gui.wait(0.5)
		self.controlBoard.turnHVOff()				#open FETs ("4")
		self.buspsu.setOutputOFF()					#turn off bus ITECH
		self.battpsu.setOutputOFF()				#turn off batt ITECH
		self.battpsu.initializePulseTest(1,1)		#set batt ITECH current limit to +-1A
		self.buspsu.initializePulseTest(1,1)		#set bus ITECH current limit to +-1A
		if len(self.failureType) == 0:
			result = "Pass"
			color = 'dark green'
		else:
			result = "Fail"
			color = 'red'
		self.gui.label("Current Calibration " + result, color=color)

		return airtableMessage

	def resistanceCapture(self) -> str:
		airtableMessage = ''
		self.gui.test_in_progress(HV=True, testName="Resistance Capture", testLength=13)

		self.cmTester.feedBusShortBatt()					#feed bus short batt ("7")
		self.buspsu.initializePulseTest(40, 40)			#allow current to go up to 40A in either direction
		self.buspsu.setVoltage(1.5)						#set bus ITECH to 10V
		self.buspsu.setOutputON()							#start flow of voltage and current

		self.gui.wait(0.5)
		self.controlBoard.resetShortCircuit()				#reset CM SC ("7")
		self.gui.wait(0.5)
		self.controlBoard.turnOffSafetyCheck()				#turn off CM internal safety check
		self.gui.wait(0.5)
		self.controlBoard.turnHVOn()						#close FETs ("3")
		aM = self.cblog('HVON')
		airtableMessage += aM[-1]

		startTime = time.time()									#track start of test
		while time.time()-startTime <= 3:
			aM = self.cblog('resistance capture')
			airtableMessage += aM[-1]
			# self.gui.wait((i+1)-(time.time()-startTime))		#wait until the end of the current second before taking a new log

		self.controlBoard.turnHVOff()						#open FETs ("4")
		aM = self.cblog('HVOFF')
		airtableMessage += aM[-1]

		self.buspsu.setOutputOFF()							#stop ITECH HV
		self.buspsu.initializePulseTest(1, 1)				#reset ITECH to maximum 1A charge and discharge
		self.cmTester.turnContactorsOff()					#open contactors ("3")

		self.gui.label("Resistance Capturing Complete")

		return airtableMessage