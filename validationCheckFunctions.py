import subprocess
import re
import os
from controlBoardSerialv13 import controlBoardSerialv13GUI
from GUI_Class import GUI

class validationCheckFunctions():
	def __init__(self, externalgui: GUI, hwVersion: int, hwRevision: int, COMPort: str):
		self.gui = externalgui
		self.hwVersion = hwVersion
		self.hwRevision = hwRevision
		self.COMPort = COMPort
		self.failure = []
		self.errorMessage = ''
		self.v17Parts = [27214, 32004]
		self.v18Parts = [32827]
		self.LEParts = [32380, 32004]
		self.red = []
		self.yellow = []

		#break full directory of current ESP software version into pieces for easier updating and comparison
		self.binVersion = '0.19.3.0'
		self.fullBinName = 'BATTERY_MODULE_%s_12069.2' %(self.binVersion)
		#include double quotes at beginning and end in case username has spaces
		self.binFile = '"' + os.getcwd() + '\\binaries\\bmSoftware\\%s.bin"' %(self.fullBinName)
		if self.hwVersion in self.v18Parts:
			self.cls_p_stk = 29
			self.blue = ["30:", "60:", "90:", "120:"]
		else:
			self.cls_p_stk = 19
			self.blue = ["20:", "40:", "60:"]
		self.fetDeltaLim = 1		#limit for temp difference on the FETs in celcius
		self.stackDeltaLim = 1		#limit for temp difference between stacks in celcius
		self.totalDeltaLim = 3		#limit for total temp difference across all components in celcius

	def bmsCheck(self, _cellVoltages: list[float], _cellTemperatures: list[float]) -> bool:
		self.cellsOnline = True
		self.tempOnline = True
		if max(_cellVoltages) == 0:			#all voltage readings 0
			self.cellsOnline = False
		if max(_cellTemperatures) <= -40:	#all temp readings invalid
			self.tempOnline = False
		if not self.cellsOnline and not self.tempOnline:		#BMS faulty, not aligned, or not installed
			self.gui.label("No connection between BMS and CM", color='red')
			self.failure.append("BMS Connection")
			self.errorMessage = self.errorMessage + 'BMS to CM error, '
			return False
		else:
			return True
		

	def cellVoltageCheck(self, _cellVoltages: list[float]) -> bool:
		#break cell voltages list into a list of lists for cell voltages in each stack
		#last stack being cells per stack * 4 to the end accounts for LE BMs
		stackVoltages = [_cellVoltages[0:self.cls_p_stk * 1], _cellVoltages[self.cls_p_stk * 1:self.cls_p_stk * 2], _cellVoltages[self.cls_p_stk * 2:self.cls_p_stk * 3], _cellVoltages[self.cls_p_stk * 3:self.cls_p_stk * 4], _cellVoltages[self.cls_p_stk * 4:]]
		stackNetVoltages = []
		stackAverages = []
		#get the total voltage and average voltage of each stack
		for i in range(len(stackVoltages)):
			stackNetVoltages.append(sum(stackVoltages[i]))
			stackAverages.append(sum(stackVoltages[i])/len(stackVoltages[i]))

		#get voltage delta and average across BM
		_cellVoltageDifference = max(_cellVoltages) - min(_cellVoltages)
		_cellVoltageAverage = sum(_cellVoltages)/len(_cellVoltages)

		if self.hwVersion in self.v18Parts: # v18
			nextToBusBars = [0, 28, 29, 57, 58, 86, 87, 115, 116, -1]
		else:
			nextToBusBars = [0, 18, 19, 37, 38, 56, 57, 76, -1]

		#if voltage delta too great or average cell voltage outside of manufacturer specified SOC range
		if (2 < _cellVoltageDifference) or (_cellVoltageAverage < 2.5 or _cellVoltageAverage > 4.2):
			self.gui.label("STACK ERROR", color='red')
			self.errorMessage = self.errorMessage + "Stack Error, "
			self.failure.append("Cell Voltage")
			return False
		
		#if overall voltage diff too big and an extrema is next to a busbar, it's likely there's a fully bad fuse being hidden by proximity to busbar
		elif (_cellVoltages.index(max(_cellVoltages)) in nextToBusBars or _cellVoltages.index(min(_cellVoltages)) in nextToBusBars) and _cellVoltageDifference >= 0.02:
			for fuse in nextToBusBars:
				if abs(_cellVoltages[fuse]-_cellVoltageAverage) >= 0.015:
					fuseID = self.getCellIndex(fuse)		#get the corresponding visual ID number for a given list index
					self.red.append(str(fuseID) + ":" + '%.4f' % _cellVoltages[fuse])		#make affected voltage reading red to highlight problem
			self.gui.label("STACK ERROR", color='red')
			self.errorMessage = self.errorMessage + "Stack Error, "
			self.failure.append("Cell Voltage")
			return False
		
		#stacks are out of voltage tolerance with each other and can cause problems at pulse
		elif (max(stackAverages) - min(stackAverages)) > (0.1/self.cls_p_stk + 0.0022):		#0.0022 is inaccuracy of BMS board
			self.gui.label("Slight Imbalance on Stack", color='red')
			self.errorMessage = self.errorMessage + "Stack Imbalance: " + str(_cellVoltageDifference) + ", "
			self.failure.append("Cell Voltage")
			stackVoltageString = ''
			#show the stack net voltages so users can decide which stack(s) to swap out or charge/discharge to match the rest
			if self.hwVersion in self.LEParts:		#LE stack has different voltage sum so tell user the average cell voltage of each stack and the limit b/w averages
				stackVoltageString = 'Cell Voltage average per stack (should be within ' + '%.5f' % (0.1/self.cls_p_stk + 0.0022) + 'V of each other):\n'
				for i in range(len(stackAverages)):
					stackVoltageString = stackVoltageString + 'Stack ' + str(i+1) + ': ' + '%.5f' % stackAverages[i] + 'V, '
			else:
				for i in range(len(stackNetVoltages)):
					stackVoltageString = stackVoltageString + 'Stack ' + str(i+1) + ': ' + '%.2f' % stackNetVoltages[i] + 'V, '
			stackVoltageString = stackVoltageString[:-2]		#remove last ', '
			self.gui.label(stackVoltageString)
			return False

		#cell voltage diff too big but not a clear bad fuse, could be partial bad fuse or BMS pins not making good connection with all stacks
		elif (0.02 <= _cellVoltageDifference <= 2):
			self.gui.label("BMS/Connection ERROR", color='red')
			self.errorMessage = self.errorMessage + "BMS/Connection Error, "
			self.failure.append("Cell Voltage")
			#highlight highest and lowest voltages for user to more easily see potential problem spots
			if 0.02 < _cellVoltageDifference <= 2:
				maxIndex = self.getCellIndex(_cellVoltages.index(max(_cellVoltages)))
				minIndex = self.getCellIndex(_cellVoltages.index(min(_cellVoltages)))
				self.yellow.extend([(str(maxIndex) + ':' + '%.4f' % max(_cellVoltages)), (str(minIndex) + ':' + '%.4f' % min(_cellVoltages))])
			return False
		
		else:
			self.gui.label("ALL CELLS GOOD", color='darkgreen')
			return True

	def busBarCheck(self, _busbarVoltages: list[float], _cellVoltages: list[float]) -> bool:
		_cellVoltageAverage = sum(_cellVoltages)/len(_cellVoltages)
		_busbarVoltages = [abs(ele) for ele in _busbarVoltages]		#use absolute value for busbar checks
		busbars = True

		for i in range(len(_busbarVoltages)):
			if _busbarVoltages[i] >= 0.006:					#busbar out of tolerance
				busbarIndex = i+1							#start from 1 instead of 0
				busID = busbarIndex*(self.cls_p_stk + 1)	#get visual ID number of the busbar voltage (20, 40, or 60 for non v18)
				#if a neighboring cell voltage reading is out of tolerance, likely a fuse problem rather than busbar problem
				if abs(_cellVoltages[busID-busbarIndex-1]-_cellVoltageAverage) > 0.02 or abs(_cellVoltages[busID-busbarIndex]-_cellVoltageAverage) > 0.02: continue
				#mark the bad busbar red in the details textbox
				self.red.append(str(busID) + ":" + str(_busbarVoltages[i]))
				self.blue.remove(str(busID) + ":")
				busbars = False

		if busbars:
			self.gui.label("Bus Bars Good", color='darkgreen')
		else:
			self.gui.label("Bus Bars BAD", color='red')
			self.errorMessage = self.errorMessage + "Bus Bars BAD, "
			self.failure.append("HV Bus Bar")

		return busbars

	def currentCheck(self, _current: tuple[float, float]) -> bool:
		_measurementOffsetCurrent = 0.2
		print(_current)
		try:
			print(_current[1])
		except Exception:
			_current[1] = 0
		#make sure both current readings are in tolerance
		if (-_measurementOffsetCurrent <= _current[0] <= _measurementOffsetCurrent) and (-_measurementOffsetCurrent <= _current[1] <= _measurementOffsetCurrent):
			self.gui.label("CURRENT READING OK", color='darkgreen')
			return True
		else:
			self.gui.label("CURRENT READING ERROR", color='red')
			self.errorMessage = self.errorMessage + "Current Reading Error, "
			self.failure.append("Current Reading")
			return False
			
	def voltageReadingCheckFetOff(self, _sumOfCellVoltage: float, _bmVoltage: float, _busVoltage: float, cellResult: bool) -> bool:
		if self.hwVersion in self.v18Parts:
			_measurementOffsetVoltage = 2.1		#wider tolerance for v18 given higher overall voltage
		else:
			_measurementOffsetVoltage = 1
		_error = 0
		# will only perform batt votlage accracy if there are no cell error because this is reliant on sum of cell voltages
		if cellResult: 
			#make sure voltage from HVBB matches sum of cell voltages
			if -_measurementOffsetVoltage <= (_sumOfCellVoltage - _bmVoltage) <= _measurementOffsetVoltage:
				self.gui.label("BATT VOLTAGE READINGS OK", color='darkgreen')
			else:
				self.gui.label("BATT VOLTAGE READINGS NOT OK", color='red')
				self.errorMessage = self.errorMessage + "Batt Voltage Reading Error, "
				_error = _error + 1
				self.failure.append("Batt Voltage Reading")

		else:
			pass
		#if bus voltage not 0 when HV off then FETs are leaking voltage
		if (_busVoltage == 0) or (-2 <= _busVoltage <= 3 and self.hwVersion in self.v18Parts):
			self.gui.label("FET OK", color='darkgreen')
		else:
			self.gui.label("FET NOT OK", color='red')
			self.errorMessage = self.errorMessage + "FET Error, "
			_error = _error + 1
			self.failure.append("FET Short")

		if _error == 0:
			return True
		else:
			return False

	def voltageReadingCheckFetOn(self, _bmVoltage: float, _busVoltage: float, cellResult: bool) -> bool:
		_measurementOffsetVoltage = 1.5
		_error = 0
		if cellResult:
			if self.hwVersion in self.v18Parts:
				#make sure bus is reading roughly 380V (charge value of 2QC)
				if -_measurementOffsetVoltage <= (_busVoltage - 380) <= _measurementOffsetVoltage:
					self.gui.label("BUS VOLTAGE READINGS OK / 2QC OK", color='darkgreen')
				else:
					self.gui.label("BUS VOLTAGE READINGS NOT OK / 2QC NOT OK", color='red')
					self.errorMessage = self.errorMessage + "2QC Error, "
					_error = _error + 1
					self.failure.append("2QC")
				if -2 <= _busVoltage <= 3:
					self.gui.label("2QC NOT OK", color='red')
					self.failure.append("2QC")
					_error = _error + 1
				else:
					pass

			else:		#non v18
				#make sure batt and bus match
				if -_measurementOffsetVoltage <= (_busVoltage - _bmVoltage) <= _measurementOffsetVoltage:
					self.gui.label("BUS VOLTAGE READINGS OK", color='darkgreen')
				else:
					self.gui.label("BUS VOLTAGE READINGS NOT OK", color='red')
					self.errorMessage = self.errorMessage + "Bus Voltage Reading Error, "
					_error = _error + 1
					self.failure.append("Bus Voltage Reading")

				if _busVoltage == 0:		#FETs did not turn on
					self.gui.label("FET NOT OK", color='red')
					self.failure.append("FET Open")
					_error = _error + 1

				else:
					pass

		else:
			return False

		if _error == 0:
			return True
		else:
			return False
		
	def voltageCheck(self, _bmVoltage: float, _sumOfCellVoltage: float):
		#check if BM voltage is within acceptable range for indoor work
		if self.hwVersion in self.v18Parts:
			voltsSOC30 = 523
		else:
			voltsSOC30 = 347

		if (_bmVoltage < voltsSOC30) or (_sumOfCellVoltage < voltsSOC30):
			self.gui.label("BM Voltage is at " + str(_bmVoltage) + "V")
		else:
			self.gui.label("BM Voltage is at " + str(_bmVoltage) + "V\nCell voltages are at " + str(_sumOfCellVoltage) + "V\n DO NOT DEAL WITH THIS BM INDOORS", color='orange red')
	
	def getCellIndex(self, listIndex: int) -> int:
		#take an index from the list of cell voltages and find the corresponding display ID accounting for busbar values and indexing from 1
		
		#number of visual IDs between the start of each stack (num of fuses per stack + 1 busbar)
		if self.hwVersion in self.v18Parts: cellsPerStack = 30
		else: cellsPerStack = 20

		#display IDs include a busbar between (almost) every stack so the display ID will be the index plus however many stacks there are before it
		#add 1 at the end since going from 0 indexing to 1 indexing
		listIndex += listIndex//cellsPerStack + 1

		#due to the combination of different indexing and busbar values in the visual IDs, every n indeces immediately after a busbar will still be one too low after previous reindexing where n is the number of full stacks below a busbar
		#v17 has no busbar ID b/w stacks 4 and 5 so no increase needed after stack 4
		if self.hwVersion in self.v18Parts or listIndex < cellsPerStack*4:
			if listIndex%cellsPerStack == 0: listIndex += 1
			elif (listIndex - listIndex//cellsPerStack)//cellsPerStack < listIndex//cellsPerStack: listIndex += 1

		#for v17, indices in the original cell voltages list after 80 will now be over adjusted so bring them back down		
		if listIndex >= 84 and self.hwVersion not in self.v18Parts: listIndex -= 1
		
		return listIndex
	
	def flashControlBoard(self):
		#check the current software version and return if up to date
		controlBoard = controlBoardSerialv13GUI.controlBoardv13_maxim(str(self.COMPort), self.gui)
		controlBoard.sendReset()
		self.gui.wait(1)
		if self.binVersion in controlBoard.receiveSerial():		#current software version found in restart printout
			controlBoard.close()		#close connection to CM for ESP check
			return		#already up to date, no need to flash
		controlBoard.close()		#close connection to CM so esptool can access port
		
		#run the flashing scripts
		self.gui.test_in_progress(testName='Flashing')
		os.system('cmd /c "python -m espefuse --port %s set_flash_voltage 3.3V"' %(str(self.COMPort)))
		#don't bother with anything older than v17, v18 has its own separate flashing process
		if self.hwVersion in self.v17Parts: os.system('cmd /c "python -m esptool --port %s --chip esp32 --baud 921600 --before default_reset --after hard_reset write_flash -u --flash_mode dio --flash_freq 40m --flash_size detect 0xd000 ota_data_initial.bin 0x1000 bootloader.bin 0x10000 %s 0x8000 partition.bin"' %(str(self.COMPort), self.binFile))

		#reconnect to the CM since flashing script is complete
		controlBoard = controlBoardSerialv13GUI.controlBoardv13_maxim(str(self.COMPort), self.gui)

		#i don't know why this step exists but it's been part of flashing since v13
		for i in range(30):
			self.gui.wait(0.2)
			controlBoard.sendEnter()

		controlBoard.close()			#close connection to CM again for ESP check and reflashing if needed
		self.gui.test_over()
		self.gui.label("Flashing Complete")
	
	def checkESP(self):
		self.gui.test_in_progress(testName='ESP Check')
		printout = ''
		p = subprocess.Popen(['python3.exe', '-m', 'esptool', '--port', self.COMPort, 'flash_id'], stdout=subprocess.PIPE)
		#print and collect all the lines of output from esptool until it finishes
		while True:
			line = p.stdout.readline().strip().decode(errors='ignore')
			if line:
				print(line)
				printout = printout + '\n' + line
			elif p.poll() != None:		#subprocess is done
				break
		#check manufacturer line for known issue
		match = re.search(r'Manufacturer: .*', printout)
		if not match:
			self.gui.label("Failed to check ESP, please try again", color='orange')
		else:
			if '20' in match.group():		#.group converts match object to string
				self.gui.label('ESP has bad flashing chip, replace ESP', color='red')
				self.errorMessage = self.errorMessage + "ESP has flashing chip batch 20, "
			else:
				self.gui.label('ESP GOOD', color='dark green')
		self.gui.test_over()
	
	def hvShutoff(self, _busVoltage: float) -> bool:
		#make sure that bus voltage drops to 0 after HV off signal
		if (_busVoltage != 0) and ("FET Short" not in self.failure):
			self.gui.label("BM DID NOT TURN OFF HV CORRECTLY", color='red')
			self.failure.append('FET Short')
			self.errorMessage = self.errorMessage + 'FET Error, '
			return False
		else:
			return True
		
	def checkFETTemps(self, _cbTemp: list[float]) -> bool:
		#make sure all thermistors on the FETs are in tolerance with each other
		self.fetsAverage = sum(_cbTemp)/len(_cbTemp)
		fetDelta = max(_cbTemp) - min(_cbTemp)
		if fetDelta > self.fetDeltaLim:
			return False
		else:
			return True
	
	def checkStackTemps(self, _cellTemperatures: list[float]) -> list:
		self.stackAverages = []
		stackDeltas = []
		stackTemps = []
		badComponents = []
		self.badStackIndices = []
		if self.hwVersion in (self.v17Parts + self.v18Parts):		#thermistors are part of stacks so group by stack
			tempsPerStack = int(len(_cellTemperatures)/5)
			if self.hwVersion in self.LEParts:		#ignore temp readings for thermistors that sit over empty cell chambers
				stackTemps = [_cellTemperatures[i:i + tempsPerStack] for i in range(0, int(4*len(_cellTemperatures)/5), tempsPerStack)]		#list of lists of cell temps by stack minus last (LE) stack
				#mark the ignored temps with blue to indicated they are neither good nor bad
				self.blue.append("43: %.3f;" % _cellTemperatures[42])
				self.blue.append("44: %.3f;" % _cellTemperatures[43])
				self.blue.append("48: %.3f;" % _cellTemperatures[47])
				self.blue.append("50: %.3f;" % _cellTemperatures[49])
				#remove in descending order to preserve list indexing
				_cellTemperatures.remove(_cellTemperatures[49])
				_cellTemperatures.remove(_cellTemperatures[47])
				_cellTemperatures.remove(_cellTemperatures[43])
				_cellTemperatures.remove(_cellTemperatures[42])
				stackTemps.append(_cellTemperatures[40:])		#add reduced number of LE stack temps
		else:		#thermistors are on 3 separate tempsense boards
			tempsPerStack = int(len(_cellTemperatures)/3)
		
		#create list of lists of temp readings divided into their appropriate component
		if not stackTemps: stackTemps = [_cellTemperatures[i:i + tempsPerStack] for i in range(0, len(_cellTemperatures), tempsPerStack)]
		
		#get the average and delta for each component
		for i in range(len(stackTemps)):
			self.stackAverages.append(sum(stackTemps[i])/len(stackTemps[i]))
			stackDeltas.append(max(stackTemps[i]) - min(stackTemps[i]))
		
		#check that all the temps on a single component are within tolerance of one another and if not mark the component as having an issue
		for j in range(len(stackDeltas)):
			if stackDeltas[j] > self.stackDeltaLim:
				badComponents.append(j)
		
		#check that all the averages of the components are within range of each other and if not mark all as bad to be sorted more later
		if max(self.stackAverages) - min(self.stackAverages) > self.stackDeltaLim:
			for k in range(len(self.stackAverages)):
				badComponents.append(k)
		
		#if there are problems, create a new list of temps that can be sorted lowest to highest to easily get median
		if badComponents:
			cellTempsCopy = []
			for cell in _cellTemperatures:
				cellTempsCopy.append(cell)
			cellTempsCopy.sort()
			median = self.getMedian(cellTempsCopy)

			#use median to judge all other temps to avoid outliers skewing average and marking everything as bad
			for j in range(len(_cellTemperatures)):
				if abs(median - _cellTemperatures[j]) > self.stackDeltaLim:
					#negative readings are 'ID:-' and positive readings are 'ID: ' so correctly mark strings for recoloring
					if _cellTemperatures[j] < 0: self.red.append(str(j+1) + ":" + '%.3f' % _cellTemperatures[j])
					else: self.red.append(str(j+1) + ": " + '%.3f' % _cellTemperatures[j])
					self.badStackIndices.append(j)		#add to list of individual bad indices

			#mark components with bad temp readings for easier rework
			for stack in stackTemps:
				containsBadCell = False
				for index in self.badStackIndices:
					if _cellTemperatures[index] in stack:
						containsBadCell = True
				if not containsBadCell and stackTemps.index(stack) in badComponents:
					badComponents.remove(stackTemps.index(stack))		#remove any components that don't have bad indices
		return badComponents
	
	def sortBadCellTemp(self, badComponents: list[int]):
		self.gui.label("CELL TEMPERATURE READINGS ERROR", color='red')
		self.errorMessage = self.errorMessage + "Cell Temperature Reading Error, "
		self.failure.append("Cell Temp Reading")
		badTempString = 'Bad Thermistor(s) on: '
		badComponents = list(set(badComponents))		#remove any double instances
		if self.hwVersion in (self.v17Parts + self.v18Parts):		#thermistors are directly on the stacks
			for component in badComponents:
				badTempString = badTempString + 'Stack ' + str(component+1) + ', '
			badTempString = badTempString[:-2]		#remove last ', '
			self.gui.label(badTempString)
		else:		#thermistors are on separate temp sense borads
			for component in badComponents:
				badTempString = badTempString + 'Temp Sense Board ' + str(component+1) + ', '
			badTempString = badTempString[:-2]		#remove last ', '
			self.gui.label(badTempString)

	def getMedian(self, sortedList: list[float]) -> float:
		#if list has an odd number of items, median is just middle item, otherwise use average of two innermost items
		if len(sortedList) % 2:
			medianIndex = int(len(sortedList)/2)
			median = sortedList[medianIndex]
		else:
			medianUpperIndex = int(len(sortedList)/2)
			median = (sortedList[medianUpperIndex] + sortedList[medianUpperIndex-1])/2
		return median
	
	def determineOutliers(self, _cellTemperatures: list[float], _cbTemp: list[float], _onBoardTempString: str | None, onBoardTemp: float | None, fetTempResult: bool, badStackTemps: list) -> tuple[bool, bool, bool | None]:
		allThermistors = []
		#make a list of all temperatures across every type of component excluding known bad thermistors
		for i in range(len(_cellTemperatures)):
			if i not in self.badStackIndices:
				allThermistors.append(_cellTemperatures[i])
		allThermistors.extend(_cbTemp)
		if _onBoardTempString: allThermistors.append(onBoardTemp)

		viableThermistors = []
		for therm in allThermistors:
			if therm > -40:		#-40 degrees and lower known to always be bad
				viableThermistors.append(therm)
		viableThermistors.sort()
		
		#use IQR to determine which temp readings are statistical outliers
		if len(viableThermistors) % 2:
			medianIndex = int(len(viableThermistors)/2)
			q1Median = self.getMedian(viableThermistors[:medianIndex])
			q3Median = self.getMedian(viableThermistors[medianIndex+1:])
		else:
			medianUpperIndex = int(len(viableThermistors)/2)
			q1Median = self.getMedian(viableThermistors[:medianUpperIndex])
			q3Median = self.getMedian(viableThermistors[medianUpperIndex:])
		iqr = q3Median - q1Median
		upperLim = q3Median + (self.totalDeltaLim * iqr)
		lowerLim = q1Median - (self.totalDeltaLim * iqr)
		
		#make list of all temps that are not outliers
		goodThermisters = []
		for therm in viableThermistors:
			if lowerLim < therm < upperLim:
				goodThermisters.append(therm)

		skipCB = False
		if badStackTemps and "BMS Connection" not in self.failure: 		#if BMS not connected then all stack temp readings bad
			self.sortBadCellTemp(badStackTemps)		#find which components have bad readings
			cellTempResult = False
			allAverages = []
			#make a list of all viable component averages
			for k in range(len(self.stackAverages)): 
				if k not in badStackTemps:
					allAverages.append(self.stackAverages[k])
			if _onBoardTempString: allAverages.append(onBoardTemp)
			allAverages.append(self.fetsAverage)
			totalDelta = max(allAverages) - min(allAverages)
			if totalDelta <= self.totalDeltaLim: skipCB = True		#if all the viable averages are within tolerance then the humidity sensor is not a problem
		else: 
			cellTempResult = True

		#make sure all the temps out of tolerance are marked red
		for i in range(len(_cellTemperatures)):
			if _cellTemperatures[i] not in goodThermisters:
				cellTempResult = False
				#negative readings are 'ID:-' and positive readings are 'ID: ' so correctly mark strings for recoloring
				if _cellTemperatures[i] < 0: self.red.append(str(i+1) + ":" + '%.3f' % _cellTemperatures[i])
				else: self.red.append(str(i+1) + ": " + '%.3f' % _cellTemperatures[i])
		
		if not cellTempResult and not badStackTemps:
			#make labels since sortBadCellTemp not called but cell temps are bad
			self.gui.label("CELL TEMPERATURE READINGS ERROR", color='red')
			self.errorMessage = self.errorMessage + "Cell Temperature Reading Error, "
			self.failure.append("Cell Temp Reading")
		elif cellTempResult and not badStackTemps:
			self.gui.label("CELL TEMPERATURE READINGS OK", color='dark green')
		
		if not skipCB:
			for j in range(len(_cbTemp)):
				if _cbTemp[j] not in goodThermisters:		#problem with a CM temp sense reading
					#negative readings are 'ID:-' and positive readings are 'ID: ' so correctly mark strings for recoloring
					if _cbTemp[j] < 0: self.red.append(str(j+1) + ":" + '%.3f' % _cbTemp[j])
					else: self.red.append(str(j+1) + ": " + '%.3f' % _cbTemp[j])
					fetTempResult = False
			if not fetTempResult:
				self.gui.label("CONTROL BOARD TEMPERATURE READINGS ERROR", color='red')
				self.errorMessage = self.errorMessage + "Control Board Temperature Reading Error, "
				self.failure.append("CB Temp Reading")
			else:
				self.gui.label("CONTROL BOARD TEMPERATURE READINGS OK", color='dark green')

			if _onBoardTempString:		#humidity sensor exists
				if (onBoardTemp in goodThermisters) or (self.hwVersion in self.v18Parts):
					onboardTempResult = True
				else:
					onboardTempResult = False
					self.gui.label("HUMIDITY SENSOR TEMP READING ERROR", color='red')
					self.failure.append("Humidity Sensor Temp Reading")
					self.red.append(_onBoardTempString)
			else:
				onboardTempResult = None
		else:
			self.gui.label("CONTROL BOARD TEMPERATURE READINGS OK", color='dark green')
			if _onBoardTempString: onboardTempResult = True
			else: onboardTempResult = None
		return cellTempResult, fetTempResult, onboardTempResult

	def checkAllTemperatures(self, _cellTemperatures: list[float], _cbTemp: list[float], _onBoardTempString: str | None = None) -> tuple[bool, bool, bool | None]:
		if _onBoardTempString:
			onBoardTemp = float(re.findall(r'[0-9]+\.[0-9]+', _onBoardTempString)[0])		#isolate just the temp value from the string
		else:
			onBoardTemp = None

		allAverages = []
		badStackTemps = []
		fetTempResult = self.checkFETTemps(_cbTemp)
		if self.tempOnline: 		#BMS is getting readings from stack temps
			badStackTemps = self.checkStackTemps(_cellTemperatures)
		else:		#mark all stack temp components as bad since none are supplying readings
			if self.hwVersion in (self.v17Parts + self.v18Parts): badStackTemps = [1, 2, 3, 4, 5]
			else: badStackTemps = [1, 2, 3]
			self.stackAverages = []
			self.badStackIndices = []
			for i in range(len(_cellTemperatures)):
				self.badStackIndices.append(i)		#mark all indices as bad
		
		if fetTempResult and not badStackTemps:		#components are internally consistent
			for stack in self.stackAverages: allAverages.append(stack)
			if _onBoardTempString: allAverages.append(onBoardTemp)
			allAverages.append(self.fetsAverage)

			totalDelta = max(allAverages) - min(allAverages)
			if totalDelta <= self.totalDeltaLim:		#check that all averages are in range since the components are good on their own
				self.gui.label("ALL CELL AND CONTROL BOARD TEMPERATURE READINGS GOOD", color='dark green')
				if not _onBoardTempString: onboardTempResult = None
				else: onboardTempResult = True
				self.zPass = True
				return True, True, onboardTempResult
			else:		#too big a difference between component types
				self.zPass = False
				cellTempResult, fetTempResult, onboardTempResult = self.determineOutliers(_cellTemperatures, _cbTemp, _onBoardTempString, onBoardTemp, fetTempResult, badStackTemps)
				self.red = list(set(self.red))
				return cellTempResult, fetTempResult, onboardTempResult
		else:		#difference too big within component types
			self.zPass = None
			cellTempResult, fetTempResult, onboardTempResult = self.determineOutliers(_cellTemperatures, _cbTemp, _onBoardTempString, onBoardTemp, fetTempResult, badStackTemps)
			self.red = list(set(self.red))
			return cellTempResult, fetTempResult, onboardTempResult