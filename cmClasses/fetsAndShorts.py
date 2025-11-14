from cblog import cblog
import time
from GUI_Class import GUI
from cmOneStopSerial import cmOneStopSerial
from controlBoardSerialv13 import controlBoardSerialv13GUI
from itech import itech

class fetsAndShorts():
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

	def inject(self, battorbus: str['Batt', 'Bus']):
		if battorbus == 'Batt':
			self.cmTester.feedBattOpenBus()	#engage contactors to feed batt and open bus ("4")
		elif battorbus == 'Bus':
			self.cmTester.feedBusOpenBatt()	#engage contactors to feed bus and open batt ("6")

	def short(self, battorbus: str['Batt', 'Bus']):
		if battorbus == 'Batt':
			self.cmTester.feedBattShortBus()	#engage contactors to feed batt and short bus ("5")
		elif battorbus == 'Bus':
			self.cmTester.feedBusShortBatt()	#engage contactors to feed bus and short batt ("7")

	def fetCheck(self, inputWhere: str['Batt', 'Bus'], inputVoltage: float, fet: bool) -> bool:
		self.controlBoard.turnOffSafetyCheck()	#turn off CM internal safety check ("5")
		detailedFail = ''
		_result = True
		if inputWhere == 'Batt':
			_input = 'Batt'
			_output = 'Bus'
		else:
			_input = 'Bus'
			_output = 'Batt'

		if fet == True:
			self.controlBoard.turnHVOn()	#close FETs ("3")
			self.gui.wait(2)
			bmVoltage, busVoltage, current, cbTemps, aM = self.cblog('fetcheckon')
			self.airtableMessage += aM
			terminalDifference = abs(bmVoltage - busVoltage)
			terminalDifferenceCheck = 1
			currentCheck = 0.2
			#check all parameters and separate out different failure types
			if (terminalDifference < terminalDifferenceCheck) and ((abs(bmVoltage-inputVoltage)<1) or (abs(busVoltage-inputVoltage)<1)) and (abs(current) < currentCheck):  #check for pass
				print('FET GOOD')
			elif (terminalDifference > terminalDifferenceCheck) and (abs(current) > currentCheck):
				self.gui.label('Current Sensor Error', color='red')
				_message = 'Current Sensor Error'
				detailedFail = 'Batt <-> Bus diff > ' + str(terminalDifferenceCheck) + ' and absolute current > ' + str(currentCheck) + '\n'
				self.failureType.append('FET Check - Current sensor error')
				# self.failureType.append(_message)
				_result = False
			elif (terminalDifference > terminalDifferenceCheck):
				self.gui.label('FET Open', color='red')
				_message = _input + '->' + _output + ' FET Open'
				detailedFail = 'Batt <-> Bus diff > ' + str(terminalDifferenceCheck) + '\n'
				self.failureType.append('FET Check - Batt and bus voltage unequal')
				# self.failureType.append(_message)
				_result = False
			elif (abs(current) > currentCheck):
				self.gui.label('Test Fail', color='red')
				_message = 'Test Fail'
				detailedFail = 'absolute current > ' + str(currentCheck) + '\n'
				self.failureType.append('FET Check - Current too high')
				# self.failureType.append(_message)
				_result = False
			else:
				self.gui.label('Test Fail', color='red')
				_message = 'Test Fail'
				detailedFail = 'Batt or bus voltage > 1V away from expected\n'
				self.failureType.append('FET Check - Not shorting to ITECH')
				# self.failureType.append(_message)
				_result = False
		elif fet == False:
			self.controlBoard.turnHVOff()	#open FETs ("4")
			self.gui.wait(5)
			bmVoltage, busVoltage, current, cbTemps, aM = self.cblog('fetcheckoff')
			self.airtableMessage += aM
			terminalDifference = abs(bmVoltage - busVoltage)
			terminalDifferenceCheck = inputVoltage - 1
			#check all parameters and separate out fails
			if (terminalDifference > terminalDifferenceCheck) and ((abs(bmVoltage-inputVoltage)<1) or (abs(busVoltage-inputVoltage)<1)): #check for pass
				print('FET GOOD')
			elif (terminalDifference < terminalDifferenceCheck):
				self.gui.label('FET Short', color='red')
				_message = _input + '->' + _output + ' FET Short'
				detailedFail = 'Batt and bus voltage equal\n'
				self.failureType.append('FET Check - Batt bus short')
				# self.failureType.append(_message)
				_result = False
			else:
				self.gui.label('Test Fail', color='red')
				_message = 'Test Fail'
				detailedFail = 'Batt or bus voltage match expected voltage\n'
				self.failureType.append('FET Check - Short to ITECH')
				# self.failureType.append(_message)
				_result = False

		self.controlBoard.turnHVOff()	#open FETs ("4")
		if detailedFail:
			self.gui.label(detailedFail[:-1])
			self.airtableMessage += detailedFail
		return _result
	
	def fetCheckSequence(self) -> str:
		self.airtableMessage = ''
		self.gui.test_in_progress(HV=True, testName="FET Check", testLength=42)
		initialFailureNum = len(self.failureType)	#since we want to run this test even after a fail, we need to see if number of fails increases
		inputVoltage = 400
		self.inject('Batt')		#feed batt open bus ("4")

		self.battpsu.setVoltage(inputVoltage)
		self.battpsu.setOutputON()

		self.fetCheck('Batt', inputVoltage, False)
		self.fetCheck('Batt', inputVoltage, True)
		self.fetCheck('Batt', inputVoltage, False)

		self.battpsu.setOutputOFF()

		self.gui.wait(1)
		self.inject('Bus')		#feed bus open batt ("6")
		self.gui.wait(0.3)
		self.buspsu.setVoltage(inputVoltage)
		self.buspsu.setOutputON()

		self.fetCheck('Bus', inputVoltage, False)
		self.fetCheck('Bus', inputVoltage, True)
		self.fetCheck('Bus', inputVoltage, False)
		self.cmTester.turnContactorsOff()	#open all contactors
		self.buspsu.setOutputOFF()
		if len(self.failureType) == initialFailureNum:
			self.gui.label('FET Check Pass', color='dark green')
		else:
			self.gui.label('FET Check Fail', color='red')

		return self.airtableMessage
	
	def scCheck(self, inputWhere: str['Batt', 'Bus'], inputVoltage: float, shortUsingFET: bool, sccyle: int = 0, itShouldShort: bool = True):
		_result = True
		self.inject(inputWhere)			#feed input open other location ("4" or "6")
		print(inputWhere + str(inputVoltage) + str(shortUsingFET))
		if inputWhere == 'Batt':
			psu = self.battpsu
		else:
			psu = self.buspsu
		psu.setVoltage(inputVoltage)
		psu.setOutputON()

		if shortUsingFET:
			self.short(inputWhere)		#feed input short other location ("5" or "7")
			self.gui.wait(0.5)
			if psu.getCurrent() > -0.1: # you can run the test to check if fet has shorted. 
				aM = self.cblog('HVOFF',sccyle)
				self.airtableMessage += aM[-1]
				self.controlBoard.turnOffSafetyCheck()	#turn of CM internal safety check ("5")
				self.controlBoard.resetShortCircuit()	#reset CM short circuit ("7")
				self.cmTester.resetOCF()
				self.gui.wait(0.2)
				self.controlBoard.turnHVOn()			#close FETs ("3")
				self.gui.wait(0.5)
				self.inject(inputWhere)						#feed input open other location ("4" or "6")
				cbFlagsPost = self.controlBoard.getBMFlags()
				# cmTesterOCF = self.cmTester.readOCF()
				aM = self.cblog('shortusingfet',sccyle)
				self.airtableMessage += aM[-1]
				## if CM did not short but it should short
				# print(cmTesterOCF == itShouldShort)
				# if cmTesterOCF == itShouldShort:
				if True:
					if (cbFlagsPost['ShortCircuit'] == 0) and itShouldShort:
						self.failureType.append('SC Check - SC not detected')
						# self.failureType.append('SC not detected')
					## if CM shorts but should not short
					elif (cbFlagsPost['ShortCircuit'] == 1) and not itShouldShort:
						self.failureType.append('SC Check - Premature SC')
						# self.failureType.append('Premature SC')
				else:
					self.failureType.append('Test Fail - OCF')
			else:
				detailedFail = 'ITECH current <= -0.1A\n'
				self.gui.label(detailedFail[:-1])
				self.airtableMessage += detailedFail
				self.failureType.append('SC Check - ITECH current reading')
				# self.failureType.append('Failed Short')

		elif not shortUsingFET:
			self.controlBoard.turnOffSafetyCheck()	#turn off CM internal safety check ("5")
			self.controlBoard.resetShortCircuit()	#reset CM short circuit ("7")
			self.cmTester.resetOCF()
			self.gui.wait(0.2)
			self.controlBoard.turnHVOn()			#close FETs ("3")
			self.gui.wait(0.5)
			bmVoltage, busVoltage, current, cbTemps, aM = self.cblog('HVON',sccyle)
			self.airtableMessage += aM
			if current > -0.1: # you can run the test
				self.short(inputWhere)					#feed input short other location ("5" or "7")
				self.gui.wait(0.5)
				self.inject(inputWhere)					#feed input open other location ("4" or "6")
				cbFlagsPost = self.controlBoard.getBMFlags()
				# cmTesterOCF = self.cmTester.readOCF()
				aM = self.cblog('shortusingcont',sccyle)
				self.airtableMessage += aM[-1]
				## if CM did not short but it should short
				# print(cmTesterOCF == itShouldShort)
				# if cmTesterOCF == itShouldShort:
				if True:
					if (cbFlagsPost['ShortCircuit'] == 0) and itShouldShort:
						self.failureType.append('SC Check - SC not detected')
						# self.failureType.append('SC not detected')
					## if CM shorts but should not short
					elif (cbFlagsPost['ShortCircuit'] == 1) and not itShouldShort:
						self.failureType.append('SC Check - Premature SC')
						# self.failureType.append('Premature SC')
				else:
					self.failureType.append('Test Fail - OCF')
			else:
				detailedFail = 'ITECH current <= -0.1A\n'
				self.gui.label(detailedFail[:-1])
				self.airtableMessage += detailedFail
				self.failureType.append('SC Check - ITECH current reading')
				# self.failureType.append('Failed Short')

		self.controlBoard.turnHVOff()			#open FETs ("4")
		self.controlBoard.resetShortCircuit()	#reset CM short circuit ("7")
		self.cmTester.resetOCF()
		aM = self.cblog('resetsc',sccyle)
		self.airtableMessage += aM[-1]
		psu.setOutputOFF()

	def LVContinuousCurrent(self, inputCurrent: float, sccyle: int = 0, itShouldShort: bool = True):
		self.cmTester.feedBattfeedBus()		#feed batt and bus ("8")
		self.battpsu.initializePulseTest(inputCurrent, inputCurrent)
		self.buspsu.initializePulseTest(inputCurrent, inputCurrent)
		self.battpsu.setVoltage(15)
		self.buspsu.setVoltage(1)
		self.battpsu.setOutputON()
		self.buspsu.setOutputON()

		self.gui.wait(0.5)
		self.controlBoard.resetShortCircuit()	#reset CM short circuit ("7")
		self.gui.wait(0.5)
		self.controlBoard.turnHVOn()			#close FETs ("3")
		aM = self.cblog('HVON', sccyle)
		self.airtableMessage += aM[-1]

		if self.battpsu.getCurrent() > -0.1 or self.buspsu.getCurrent() > -0.1:	#check that fets aren't shorted
			startTime = time.time()										#track start of test
			while time.time-startTime <= 3:
				aM = self.cblog('shortusingfet',sccyle)
				self.airtableMessage += aM[-1]
				# self.gui.wait((i+1)-(time.time()-startTime))			#wait until the end of the current second before taking a new log
			cbFlagsPost = self.controlBoard.getBMFlags()
			if (cbFlagsPost['ShortCircuit'] == 0) and itShouldShort:
				self.failureType.append('SC Check - SC not detected')
				# self.failureType.append('SC not detected')
			## if CM shorts but should not short
			elif (cbFlagsPost['ShortCircuit'] == 1) and not itShouldShort:
				self.failureType.append('SC Check - Premature SC')
				# self.failureType.append('Premature SC')
			
			#reverse flow of current by swapping ITECH voltage maximums
			self.battpsu.setVoltage(1)
			self.buspsu.setVoltage(15)

			startTime = time.time()										#track start of test
			while time.time()-startTime <= 3:
				aM = self.cblog('shortusingfet',sccyle)
				self.airtableMessage += aM[-1]
				# self.gui.wait((i+1)-(time.time()-startTime))			#wait until the end of the current second before taking a new log
			cbFlagsPost = self.controlBoard.getBMFlags()
			if (cbFlagsPost['ShortCircuit'] == 0) and itShouldShort:
				self.failureType.append('SC Check - SC not detected')
				# self.failureType.append('SC not detected')
			## if CM shorts but should not short
			elif (cbFlagsPost['ShortCircuit'] == 1) and not itShouldShort:
				self.failureType.append('SC Check - Premature SC')
				# self.failureType.append('Premature SC')
		else:
			detailedFail = 'ITECH current <= -0.1A\n'
			self.gui.label(detailedFail[:-1])
			self.airtableMessage += detailedFail
			self.failureType.append('SC Check - ITECH current reading')
			# self.failureType.append('Failed Short')

		self.controlBoard.turnHVOff()			#open FETs ("4")
		self.controlBoard.resetShortCircuit()	#reset CM SC ("7")
		aM = self.cblog('resetsc',sccyle)
		self.airtableMessage += aM[-1]

		self.battpsu.setOutputOFF()
		self.buspsu.setOutputOFF()

		self.battpsu.initializePulseTest(1, 1)
		self.buspsu.initializePulseTest(1, 1)
		self.cmTester.turnContactorsOff()		#open all contactors ("3")
		self.gui.wait(0.5)

	def LVSCCheckSequence(self) -> str:
		self.airtableMessage = ''
		self.gui.test_in_progress(HV=True, testName='Low Voltage Short Circuit Tests', testLength=26)
		# check for OCP limits
		# self.LVContinuousCurrent(72, 0, False)
		self.scCheck('Batt', 15, True, 0, False) # batt -> bus low current, False = should not short
		self.gui.wait(0.5)
		# self.scCheck('Batt', 25, True, 0, True) # batt -> bus higher current, True = should short
		# self.gui.wait(0.5)
		# self.LVContinuousCurrent(72, 0, False)
		self.scCheck('Bus', 15, True, 0, False) # bus -> batt low current, False = should not short
		self.gui.wait(0.5)
		# self.scCheck('Bus', 25, True, 0, True) # bus -> batt higher current, True = should short
		# self.gui.wait(0.5)
		
		if len(self.failureType) == 0:
			self.gui.label("LV Short Circuit Check Sequence Pass", color='dark green')
		else:
			self.gui.label("LV Short Circuit Check Sequence Fail", color='red')

		return self.airtableMessage
	
	def HVSCCheckSequence(self) -> str:
		self.airtableMessage = ''
		self.gui.test_in_progress(HV=True, testName='HV Short Circuit Check Sequence', testLength=27)

		self.scCheck('Batt', 100, True, 0 , True)
		self.gui.wait(2)
		self.scCheck('Bus', 100, True, 0, True)
		self.gui.wait(2)

		self.cmTester.turnContactorsOff()	#open all contactors ("3")
		self.battpsu.setOutputOFF()
		self.buspsu.setOutputOFF()
		if len(self.failureType) == 0:
			self.gui.label("HV Short Circuit Check Sequence Pass", color='dark green')
		else:
			self.gui.label("HV Short Circuit Check Sequence Fail", color='red')

		return self.airtableMessage