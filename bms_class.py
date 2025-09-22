import serial
import serial.tools.list_ports
from datetime import date
from controlBoardSerialv13 import controlBoardSerialv13GUI
from bkPSU import bkPSU
import re
import csv
from GUI_Class import GUI

class bmsTester():
	def __init__(self, externalGUI: GUI, testingTechnician: str):
		self.errorMessage = ''
		self.failureType = []
		self.today = date.today()
		self.lastSerial = ''

		self.testName = 'BMS Board Test'
		self.equipment = '3DPF-23906-1-2'
		self.gui = externalGUI
		self.psu = None
		self.technician = testingTechnician

		self.controlBoard = None
		#since this script can be used for both v17 and v18 BMS testers, these dictionaries will ensure that the correct tester and power supply are used for the correct tests
		self.v17Components = {'BMS part number': 27230, 'Equipment': '3DPF-23906-1-2', 'Tester ESP serial': "SER=DE8EAC423F29EE11B17419CDF49E3369", 'PSU serial': "SER=508F22120"}
		self.v18Components = {'BMS part number': 34714, 'Equipment': '', 'Tester ESP serial': "SER=0CED7B396029EE118C8E1ECDF49E3369", 'PSU serial': "SER=508G21139"}
		self.bmsPartNumbers = [self.v17Components['BMS part number'], self.v18Components['BMS part number']]		#list of all accepted serials
		self.testerBoardSerials = [self.v17Components['Tester ESP serial'], self.v18Components['Tester ESP serial']]		#list of known tester port serials
		self.psuSerials = [self.v17Components['PSU serial'], self.v18Components['PSU serial']]		#list of known power supply port serials
		
		self.v18Temperatures = [0.4]		#list of preset temperature values for v18 tester

		#list of indices for v17 and v18 where reading errors may present differently depending on which pins have no connection
		self.v17NextToBusbars = [1, 21, 41, 61, 98]
		self.v18NextToBusbars = [1, 31, 61, 91, 119]

		#lists for strings to be recolored by GUI
		self.red = []
		self.green = []

		self.voltageTolerance = 0.1

	def checkConnection(self, _cellVoltages: list[float], _cellTemperatures: list[float]) -> bool:
		#check that the tester is correctly getting readings from the board
		cellsOnline = True
		tempOnline = True
		if max(_cellVoltages) == 0:		#all voltages 0
			cellsOnline = False
		if max(_cellTemperatures) <= 0:		#all temps negative
			tempOnline = False
		if not cellsOnline and not tempOnline:
			self.gui.label("NO CONNECTION BETWEEN BMS AND TESTER", color='red')
			self.failureType.append('No connection')
			self.errorMessage = self.errorMessage + 'BMS Error, '
			return False
		else:
			return True

	def cellVoltageCheck(self, _cellVoltages: list[float]) -> bool:
		self.voltsPsu = self.psu.getVoltage()		#save power supply voltage output close to when readings are taken for later comparison

		#recolor all voltage readings to green then recolor individual values back to red when they're known to be bad
		for i in range(len(_cellVoltages)):
			fuseID = self.getCellIndex(i)
			self.green.append(str(fuseID) + ":" + '%.4f' % _cellVoltages[i])

		_cellVoltageDifference = max(_cellVoltages) - min(_cellVoltages)
		_cellVoltageAverage = sum(_cellVoltages)/len(_cellVoltages)
		print(_cellVoltageDifference)
		print(_cellVoltageAverage)
		print(sum(_cellVoltages))
		if (_cellVoltageDifference >= self.voltageTolerance):		#determine if the readings are out of accepted range
			self.gui.label("CV IMBALANCE ON BMS", color='red')
			self.errorMessage = self.errorMessage + "BMS Imbalance, " + str(_cellVoltageDifference) + ', '
			self.voltsOutOfTolerance(_cellVoltages)		#determine where the readings differ from expectations
			return False
		elif ((self.voltsPsu-2) > sum(_cellVoltages)) or (sum(_cellVoltages) > (self.voltsPsu+2)):		#check that total voltage out matches total voltage in
			self.gui.label("SUM NOT CORRECT", color='red')
			self.failureType.append('Sum incorrect')
			self.errorMessage = self.errorMessage + "BMS Error, "
			return False
		else:
			self.gui.label("ALL VOLTAGES GOOD", color='darkgreen')
			return True

		#find cell Voltage difference of each bank

	def voltsOutOfTolerance(self, _cellVoltages: list[float]):
		badindices = []
		idxString = ''
		pinIndices = []
		voltsPerCell = self.voltsPsu/len(_cellVoltages)		#expected voltage value for each reading based on power supply voltage
		for i in range(len(_cellVoltages)):
			if abs(_cellVoltages[i]-voltsPerCell) >= self.voltageTolerance:		#if delta b/w actual and expected too great
				fuseID = self.getCellIndex(i)		#get displayed index for a given index from backend list
				fuseString = str(fuseID) + ":" + '%.4f' % _cellVoltages[i]		#make string of how this index and its voltage are displayed in full readings
				self.red.append(fuseString)		#make the section of the output for this value red
				try:
					self.green.remove(fuseString)		#remove this value from list of strings to be made green
				except ValueError:
					pass		#don't crash script over a color mismatch

				badindices.append(fuseID)		#add display index to list of bad indicies to dsiplay to user at the end

				#most bad pins will affect a pair of indicies with one low and one high so only deal with the low one to avoid doubling work
				if voltsPerCell - _cellVoltages[i] >= self.voltageTolerance:
					
					#if displayed index is next to busbars according to appropriet version lists
					if (fuseID in self.v17NextToBusbars and not self.isV18) or (fuseID in self.v18NextToBusbars and self.isV18):
						
						#handle final index separately
						if i != len(_cellVoltages)-1:
							
							#if the next index is unaffected, its the stack's B1(-), otherwise it's B1
							if abs(_cellVoltages[i+1] - voltsPerCell) >= self.voltageTolerance:
								pinIndices.append(fuseID)
							
							#the first ID can be affected by B1, B1(-), and B1(-) DC so check for DC for ID 1 only
							#if ID 1 voltage closer to 0 than expected voltage and ID 2 uneffected, then it's DC
							elif i == 0 and abs(_cellVoltages[i]-voltsPerCell) > _cellVoltages[i]:
								pinIndices.append(str(fuseID) + '(-) DC')
							else:
								pinIndices.append(str(fuseID) + '(-)')
						
						else:
							
							#final index has no higher index so if its low it's B19/B29, otherwise it's B19/B29(-)
							if _cellVoltages[i] < voltsPerCell:
								pinIndices.append(fuseID)
							else:
								pinIndices.append(str(fuseID) + '(-)')
					
					else:
						# a bad pin is almost always 0 with the next fuse high 
						# but there was one pin during testing where the bad pin was high with the next fuse 0 so check for flipped order
						if _cellVoltages[i-1] - voltsPerCell >= self.voltageTolerance:
							pinIndices.append(fuseID-1)
						else:
							pinIndices.append(fuseID)
				
				#deal with voltages next to busbar connections that manifest differently
				elif _cellVoltages[i] - voltsPerCell >= self.voltageTolerance and ((fuseID in self.v17NextToBusbars and not self.isV18) or (fuseID in self.v18NextToBusbars and self.isV18)):
					pinIndices.append(str(fuseID) + '(-)')
		badindices = list(set(badindices))		#remove any double counted indices
		badindices.sort()		#display indices in order
		for idx in badindices:
			idxString += str(idx) + ', '
		if badindices: 
			self.gui.label("CV imbalance at indices: " + idxString[:-2])
			self.errorMessage += "CV imbalance at indices: " + idxString[:-2] + ', '
		self.createFailureType(fuseIndices=pinIndices)		#create unique fail strings for each individual failed pin

	def getCellIndex(self, listIndex: int) -> int:
		#take an index from the list of cell voltages and find the corresponding display ID accounting for busbar values and indexing from 1
		
		#number of visual IDs between the start of each stack (num of fuses per stack + 1 busbar)
		if self.isV18: cellsPerStack = 30
		else: cellsPerStack = 20

		#display IDs include a busbar between (almost) every stack so the display ID will be the index plus however many stacks there are before it
		#add 1 at the end since going from 0 indexing to 1 indexing
		listIndex = listIndex + listIndex//cellsPerStack + 1

		#due to the combination of different indexing and busbar values in the visual IDs, every n indeces immediately after a busbar will still be one too low after previous reindexing where n is the number of full stacks below a busbar
		#v17 has no busbar ID b/w stacks 4 and 5 so no increase needed after stack 4
		if self.isV18 or listIndex < cellsPerStack*4:
			if listIndex%cellsPerStack == 0: listIndex += 1
			elif (listIndex - listIndex//cellsPerStack)//cellsPerStack < listIndex//cellsPerStack: listIndex += 1

		#for v17, indices in the original cell voltages list after 80 will now be over adjusted so bring them back down		
		if listIndex >= 84 and not self.isV18: listIndex -= 1
		
		return listIndex

	def cellTemperatureCheck(self, _cellTemperatures: list[float]) -> bool:
		#this function is only for v17 tester

		tempDifference = max(_cellTemperatures) - min(_cellTemperatures)

		if 0 < tempDifference < 1:		#all temps should be within a degree of each other but if theyre exactly equal something is wrong
			self.gui.label("CELL TEMPERATURE READINGS OK", color='darkgreen')
			return True
		elif tempDifference == 0:
			#make all temp readings red in the GUI
			for i in range(len(_cellTemperatures)):
				#negative values have no space after the colon but positive values do
				if _cellTemperatures[i] < 0: self.red.append(str(i+1) + ":" + '%.3f' % _cellTemperatures[i])
				else: self.red.append(str(i+1) + ": " + '%.3f' % _cellTemperatures[i])

			self.gui.label('CELL TEMPERATURE READINGS ERROR')
			self.errorMessage += 'Cell Temperature Readings Error, '
			self.failureType.append('Uncanny Temperatures')
			return False
		else:
			self.gui.label("CELL TEMPERATURE READINGS ERROR", color='red')
			self.errorMessage = self.errorMessage + "Cell Temperature Readings Error, "
			self.checkStackTemps(_cellTemperatures)
			self.determineOutliers(_cellTemperatures)
			return False

	def determineOutliers(self, _cellTemperatures: list[float]):
		viableThermistors = []
		pinIndices = []
		#make new list of temperature values that we can reorder and remove items from
		for therm in _cellTemperatures:
			if therm > 0:
				viableThermistors.append(therm)
		viableThermistors.sort()
		
		#remove indices of already known bad temperatures from checkStackTemps
		for idx in self.ignoreIndices:
			viableThermistors.remove(_cellTemperatures[idx])
		
		#use IQR to determine which temperatures are outliers since there is no preset temperature for v17
		if len(viableThermistors) % 2:
			medianIndex = int(len(viableThermistors)/2)
			q1Median = self.getMedian(viableThermistors[:medianIndex])
			q3Median = self.getMedian(viableThermistors[medianIndex+1:])
		else:
			medianUpperIndex = int(len(viableThermistors)/2)
			q1Median = self.getMedian(viableThermistors[:medianUpperIndex])
			q3Median = self.getMedian(viableThermistors[medianUpperIndex:])
		iqr = q3Median - q1Median
		upperLim = q3Median + iqr
		lowerLim = q1Median - iqr

		badTempsString = 'Bad temp reading(s) at: '
		for i in range(len(_cellTemperatures)):
			if not (lowerLim < _cellTemperatures[i] < upperLim):		#temperature is an outlier
				#make temp value red in GUI
				if _cellTemperatures[i] < 0: self.red.append(str(i+1) + ":" + '%.3f' % _cellTemperatures[i])
				else: self.red.append(str(i+1) + ": " + '%.3f' % _cellTemperatures[i])
				if (i+1) not in self.ignoreIndices:		#if index is not already accounted for
					badTempsString += str(i+1) + ', '
					pinIndices.append(i+1)
		if badTempsString[-2] == ',':		#outliers were found
			self.gui.label(badTempsString[:-2])
			self.errorMessage += badTempsString
			self.createFailureType(tempIndices=pinIndices)		#create unique fail strings for each individual failed pin

	def getMedian(self, sortedList: list[float]) -> float:
		#get median of a pre sorted list
		if len(sortedList) % 2:		#list has an odd number of values
			medianIndex = int(len(sortedList)/2)
			median = sortedList[medianIndex]
		else:
			medianUpperIndex = int(len(sortedList)/2)
			median = (sortedList[medianUpperIndex] + sortedList[medianUpperIndex-1])/2		#if list has an even number of values, use avg of two innermost values
		return median

	def checkStackTemps(self, _cellTemperatures: list[float]):
		self.ignoreIndices = []
		badBanks = []
		bankindices = []
		pinIndices = []
		tempsPerBank = int(len(_cellTemperatures)/10)		#both v17 and v18 have 10 "banks" or temperature pins, 2 per stack
		#create two lists of lists that separate the temperature values (first list) and their indeces starting at 1 (second list) by bank
		bankTemps = [_cellTemperatures[i:i + tempsPerBank] for i in range(0, len(_cellTemperatures), tempsPerBank)]
		for bank in range(int(len(_cellTemperatures)/tempsPerBank)):
			bankindices.append(list(range(bank*tempsPerBank+1, (bank+1)*tempsPerBank+1)))

		#if all temperatures in a bank are negative, assume the pin that powers the bank is the problem, not all the other pins
		for bank in bankTemps:
			if max(bank) < 0:
				badBanks.append(bankTemps.index(bank) + 1)
		
		if badBanks:
			bankString = 'No power going to temp sense bank(s): '
			for bank in badBanks:
				self.ignoreIndices.extend(bankindices[bank-1])		#ignore temps from unpowered banks when looking for individual outliers
				side = 1
				if bank % 2 == 0:
					side = 2
				bankString += 'Stack ' + str(int((bank+1)/2)) + ' Side ' + str(side) + ', '
				pinIndices.append('Stack ' + str(int((bank+1)/2)) + ' Side ' + str(side))
			self.gui.label(bankString[:-2])
			self.errorMessage += bankString
			self.createFailureType(tempIndices=pinIndices)		#create unique fail string for each bad power pin

	def v18TemperatureCheck(self, _cellTemperatures: list[float], _setTemperature: float) -> bool:
		setTempOffset = 1
		tempError = False
		badindices = []
		pinIndices = []
		
		#find temperatures that are more than a degree off from preset temperature
		for i in range(len(_cellTemperatures)):
			if abs(_cellTemperatures[i]-_setTemperature) > setTempOffset:
				tempError = True
				badindices.append(i)

		if tempError:
			self.gui.label("CELL TEMPERATURE READINGS ERROR", color='red')
			self.errorMessage = self.errorMessage + "Cell Temperature Reading Error, "

			self.checkStackTemps(_cellTemperatures)
			badTempsString = 'Bad temp reading(s) at: '
			for tempIdx in badindices:
				#make out of tolerance temp readings red in GUI
				if _cellTemperatures[tempIdx] < 0: self.red.append(str(tempIdx+1) + ":" + '%.3f' % _cellTemperatures[tempIdx])
				else: self.red.append(str(tempIdx+1) + ": " + '%.3f' % _cellTemperatures[tempIdx])
				
				#add individual bad temp indices to fail string and list if not from a bad bank
				if (tempIdx+1) not in self.ignoreIndices:
					badTempsString += str(tempIdx+1) + ', '
					pinIndices.append(tempIdx+1)
			if badTempsString[-2] == ',':		#if there are individual bad temps instead of just bad banks
				self.gui.label(badTempsString[:-2])
				self.errorMessage += badTempsString
				self.createFailureType(tempIndices=pinIndices)		#create unique fail strings for each failed pin
			return False
		else:
			self.gui.label("CELL TEMPERATURE READINGS OK", color='darkgreen')
			return True
		
	def createFailureType(self, fuseIndices=None, tempIndices = None):
		#each reading for both v17 and v18 boards has a direct mapping to a specific pin that can be referenced by the corresponding csv
		#each pin on a v18 board is numbered by the manufacturer, v17 has labeled sections of pins, use the coordinate system outlined in the csv to fully understand a given coordinate
		if self.isV18: file = 'v18_BMS_mapping.csv'
		else: file = 'v17_BMS_mapping.csv'
		#create a dictionary of lists where each list is a column of the csv file
		with open(file, mode='r') as mapping:
			reader = csv.DictReader(mapping)
			mapDict = {'Voltage ID': [], 
				'Volt J Coordinate': [], 
				'Temp ID': [], 
				'Temp J Coordinate': []}
			
			#fill the empty lists in order by row
			for row in reader:
				mapDict['Voltage ID'].append(row['\xef\xbb\xbfVoltage ID'])		#unknown why this column has escape characters but easy to include them
				mapDict['Volt J Coordinate'].append(row['Volt J Coordinate'])
				mapDict['Temp ID'].append(row['Temp ID'])
				mapDict['Temp J Coordinate'].append(row['Temp J Coordinate'])
			
		#match any known bad fuses indeces with their pin coordinates and create a unique failure type string for Airtable
		if fuseIndices:
			for idx in fuseIndices:
				row = mapDict['Voltage ID'].index(str(idx))
				self.failureType.append('Pin: ' + mapDict['Volt J Coordinate'][row] + ', Cell Volt ID ' + str(idx))

		#match any known bad temperature indices/banks with their pin coordinates and create a unique failure type string for Airtable
		if tempIndices:
			for idx in tempIndices:
				row = mapDict['Temp ID'].index(str(idx))
				if type(idx) == int:
					self.failureType.append('Pin: ' + mapDict['Temp J Coordinate'][row] + ', Cell Temp ID ' + str(idx))
				else:
					self.failureType.append('Pin: ' + mapDict['Temp J Coordinate'][row] + ', Power Supply ' + idx)

	def start(self):
		self.gui.test_in_progress(testName='Initial Setup')
		self.setupPorts()
		self.gui.test_over()
		while 1:
			self.main()

	def setupPorts(self):
		ports = serial.tools.list_ports.comports()
		self.isV18 = False
		for port, desc, hwid in sorted(ports):
			print(hwid)
			#search for tester ESPs in the available COM ports
			for ser in self.testerBoardSerials:
				if ser in hwid:
					if self.v18Components['Tester ESP serial'] in hwid: 
						self.isV18 = True
					self.controlBoard = controlBoardSerialv13GUI.controlBoardv13_maxim(port, self.gui)
					self.controlBoard.reboot()
					self.gui.wait(1)
			#search for power supplies in the available COM ports
			for psu in self.psuSerials:
				if psu in hwid:
					self.psu = bkPSU.bkPSU(str(port))
					self.psu.setBeepON()
		if not self.controlBoard:
			self.gui.label("Make sure tester ESP is plugged in and 12V is on", big=True)
			try:
				self.psu.close()		#since full setup will be rerun, power supply will be reconnected to so make it available
			except Exception: pass
			self.gui.restartButton()		#wait for user to press continue
			self.setupPorts()		#restart setup process
		if not self.psu:
			self.gui.label("Make sure power supply is plugged in and turned on", big=True)
			try:
				self.controlBoard.close()		#since full setup will be rerun, tester ESP will be reconnected to so make it available
			except Exception: pass
			self.gui.restartButton()		#wait for user to press continue
			self.setupPorts()		#restart setup process

	def goToLastSerial(self, event):
		#since this test requires boards to be placed face down in the tester, rescanning serial stickers can be a pain, allow users to use up arrow to auto fill most recent serial number
		if self.gui.serialEntry.get() == '' and self.lastSerial:		#prevent overriding an entered serial with an accidental button press and make sure there this is not the first test
			self.gui.serialEntry.insert(0, self.lastSerial)

	def main(self):
		self.errorMessage = ''
		self.failureType = []
		dateToday = self.today.strftime("%m/%d/%y")
		self.gui.root.bind('<Up>', self.goToLastSerial)		#allow use of up arrow to autofill previous serial
		serialNumber = self.gui.getSerial()
		self.gui.root.unbind('<Up>')		#up arrow not needed until next time a serial is entered
		self.technician = self.gui.technician		#redefine technician from GUI class variable in case previous user logged out and new user logged in

		#separate serial number into part number, revision, and individual serial
		temp = re.findall(r'[0-9]+', serialNumber)
		res = list(map(int, temp))
		print(res)
		hwVersion = res[0]

		#make busbar IDs blue to show that they are separate but neither good nor bad
		if self.isV18:
			self.blue = ["30:", "60:", "90:", "120:"]
		else:
			self.blue = ["20:", "40:", "60:"]


		#make sure that the current tester in use matches with the board version serial entered
		if (self.isV18 and hwVersion == self.v17Components['BMS part number']) or (not self.isV18 and hwVersion == self.v18Components['BMS part number']):
			self.gui.label('The tester currently set up does not match the part number of the scanned BMS board. \nPlease make sure the desired tester is connected and restart', color='blue', big=True)
		
		elif hwVersion in self.bmsPartNumbers:
			#perform the test
			self.gui.test_in_progress(HV=True, testLength=6, testName="BMS Test")
			self.controlBoard.turnHVOn()
			if self.isV18:
				self.gui.initialTime += 4		#v18 tester needs to be fully engaged before power can be turned on
				self.gui.wait(4)
			self.psu.setOutputON()
			self.gui.wait(6)
			self.controlBoard.receiveSerial()
			soc, cellVoltages, sumOfCellVoltage, bmVoltage, busVoltage, current, cellTemperatures, controlBoardTemperature, busbarVoltage, busCurrent = self.controlBoard.getDetails(False)
			tester_rx = self.controlBoard.rx		#save full detail printout string

			connectionResult = self.checkConnection(cellVoltages, cellTemperatures)
			if connectionResult:		#readings are valid
				cellTestResult = self.cellVoltageCheck(cellVoltages)

				#do appropriate temperature check for version in use
				if hwVersion == self.v17Components['BMS part number']:
					cellTempResult = self.cellTemperatureCheck(cellTemperatures)
				elif hwVersion == self.v18Components['BMS part number']:
					allCellTempResults = []
					#do the temperature check for each preset temperature
					for temp in self.v18Temperatures:
						allCellTempResults.append(self.v18TemperatureCheck(cellTemperatures, temp))
					if False in allCellTempResults:
						cellTempResult = False
					else:
						cellTempResult = True
			else:
				cellTestResult = False
				cellTempResult = False
			self.psu.setOutputOFF()
			self.gui.test_over()
			if cellTestResult == True and cellTempResult == True:
				testingStatus = 'Pass'
				airtableMessage = dateToday + " - Tested, Result: Passed"
				self.gui.label(airtableMessage, color='dark green', big=True)
			else:
				testingStatus = 'Fail'
				airtableMessage = dateToday + " - Tested, Result: Failed"
				self.gui.label(airtableMessage, color='red', big=True)
				failString = 'Failures: '
				for fail in self.failureType:
					failString += fail + ', '
				self.gui.label(failString[:-2])
			#make the changes to the colors in the GUI then remove ANSI codes for Airtable upload
			debuglogs_raw = self.gui.colorSwap(tester_rx, red=self.red, green=self.green, blue=self.blue)
			debuglogs = self.gui.ansiReplace(debuglogs_raw)

			if self.errorMessage: self.errorMessage = self.errorMessage[:-2]		#remove final ', '
			self.gui.resultsUpload(testName=self.testName, deviceUnderTest=serialNumber, result=testingStatus, testData= 'Testing technician: ' + self.technician + '\n' + self.errorMessage + '\n' + debuglogs, equipment=self.equipment, failureType=self.failureType)

		else:		#valid serial number was entered but is not a v17 or v18 BMS board
			self.gui.label("This part number is not supported by this test", color='orange red', big=True)

		self.controlBoard.turnHVOff()
		self.lastSerial = serialNumber		#save serial number for autofilling if user wishes to retest
		self.gui.restartButton()