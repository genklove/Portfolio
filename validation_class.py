import re
import tkinter as tk
from controlBoardSerialv13 import controlBoardSerialv13GUI
from datetime import date
from validationCheckFunctions import validationCheckFunctions
from GUI_Class import GUI

class validation():
	def __init__(self, externalgui: GUI, testingTechnician: str):
		self.gui = externalgui
		self.testName = 'Battery Module Validation'
		self.technician = testingTechnician

		self.productionParts = [12069, 18016, 27214, 32827]		#standard part numbers for v13, v14, v17, and v18
		self.dummyParts = [26518, 24911, 24914, 30005, 30006]	#part numbers for every type of dummy BM
		self.LEParts = [32380, 32004]							#any version LE part numbers
		self.v17Parts = [27214, 32004]							#v17 standard and LE versions
		self.v18Parts = [32827]
		self.partNumbers = self.productionParts + self.dummyParts + self.LEParts

	def encodeSerial(self):
		self.controlBoard.gotoNVSMenu()
		self.controlBoard.editNVSMenu("10", str(self.hwRevision))
		self.controlBoard.editNVSMenu("11", str(self.hwVersion))
		self.controlBoard.editNVSMenu("0", str(self.serialNumber))
		self.controlBoard.printNVSValue()
		if self.hwVersion in self.v18Parts:
			reset = self.controlBoard.resetNVSValues()			#make sure dynamic NVS values are set correctly
			if not reset: self.gui.label('Failed to set NVS menu values!', color='red')
		self.controlBoard.gotoMainMenu()
		self.controlBoard.reboot()
		self.gui.wait(2)
	
	def start(self):
		while True:
			self.main()

	def main(self):
		today = date.today()
		self.dateToday = today.strftime("%m/%d/%y")

		COMPort = self.gui.wait_for_plug_in()		#have user connect to BM via USB
		serialNumber = self.gui.getSerial()
		self.technician = self.gui.technician		#get technician name again in case previous user logged out and new user logged in b/w tests
		temp = re.findall('[0-9]+', serialNumber)
		res = list(map(int, temp))
		print(res)
		self.serialNumber = res[2]
		self.hwVersion = res[0]
		self.hwRevision = res[1]

		if self.hwVersion not in self.partNumbers:		#not a BM
			self.gui.label("Part number not supported by this test", color='orange red', big=True)
			self.gui.restartButton()
			return
		
		checkFunctions = validationCheckFunctions(self.gui, self.hwVersion, self.hwRevision, COMPort)
		if self.hwVersion in self.v17Parts:
			#for v17, make sure that ESP has most up to date code and has good manufacturer
			checkFunctions.flashControlBoard()
			checkFunctions.checkESP()

		self.gui.test_in_progress(testName='Connect Control Board', testLength=3)
		if (self.hwVersion == 12069) and (self.hwRevision < 8):		#old software has different readings/printouts
			try:
				self.controlBoard = controlBoardSerialv13GUI.controlBoardv13(str(COMPort), self.gui)
				self.controlBoard.reboot()

			except Exception as e:		#couldn't connect to BM
				print("error open serial port: " + str(e))
				self.gui.test_over()
				return
		else:	
			try:
				self.controlBoard = controlBoardSerialv13GUI.controlBoardv13_maxim(str(COMPort), self.gui)
				self.controlBoard.reboot()

			except Exception as e:		#couldn't connect to BM
				print("error open serial port: " + str(e))
				self.gui.test_over()
				return

		testLength = 21
		if self.hwVersion in self.v18Parts: testLength += 12		#added time to reset all the NVS values in v18
		self.gui.test_in_progress(testName='Validation', testLength=testLength)
		self.encodeSerial()

		#initial HV off section
		if ((self.hwVersion == 12069) and (self.hwRevision < 8)):
			soc, cellVoltages, sumOfCellVoltage, bmVoltage, busVoltage, current, cellTemperatures, controlBoardTemperature = self.controlBoard.getDetails(True)
		else:
			soc, cellVoltages, sumOfCellVoltage, bmVoltage, busVoltage, current, cellTemperatures, controlBoardTemperature, busbarVoltages, busCurrent = self.controlBoard.getDetails(True)
		detailsLog = self.controlBoard.rx

		#remove any extra text from before results
		detailsLog = "SOC is at" + detailsLog.split("SOC is at", 1)[-1]
		#label which section of the test these results are for
		detailsLog = "Initial readings (HV OFF):\n" + detailsLog
		try:
			#get temp reading from humidity sensor on control board if it has it
			onBoardTempString = str(re.findall(r"Temperature:\s+[0-9]+\.[0-9]+ C", detailsLog)[0])
		except IndexError:
			onBoardTempString = None

		#check that BMS board is properly connected to all components and functioning, don't bother checking cell voltages if not
		bmsResult = checkFunctions.bmsCheck(cellVoltages, cellTemperatures)
		if bmsResult:
			cellResult = checkFunctions.cellVoltageCheck(cellVoltages)
			battVoltageReadingResult = checkFunctions.voltageReadingCheckFetOff(sumOfCellVoltage, bmVoltage, busVoltage, cellResult)
		else:
			cellResult = False
			battVoltageReadingResult = checkFunctions.voltageReadingCheckFetOff(sumOfCellVoltage, bmVoltage, busVoltage, False)
		cellTemperatureResult, controlBoardTemperatureResult, onboardTemperatureResult = checkFunctions.checkAllTemperatures(cellTemperatures, controlBoardTemperature, onBoardTempString)

		if self.hwVersion in self.v18Parts:
			#ignore HV on section for v18
			busVoltageReadingResult = None
			busbarResult = None
			currentResult = None
			hvOff = None
			cellVoltageDifference = max(cellVoltages) - min(cellVoltages)
		else:
			self.controlBoard.turnOffSafetyCheck()
			self.gui.wait(0.1)
			self.controlBoard.turnHVOn()
			self.gui.wait(3)		#wait for ESP to process new electrical state before getting readings

			#HV on section
			if ((self.hwVersion == 12069) and (self.hwRevision < 8)):
				soc, cellVoltages, sumOfCellVoltage, bmVoltage, busVoltage, current, cellTemperatures, controlBoardTemperature = self.controlBoard.getDetails(True)
				tempRX = self.controlBoard.rx
				busVoltageReadingResult = checkFunctions.voltageReadingCheckFetOn(sumOfCellVoltage, busVoltage, cellResult)
				busbarResult = True		#not applicable for old software
				currentResult = checkFunctions.currentCheck(current)
			else:
				soc, cellVoltages, sumOfCellVoltage, bmVoltage, busVoltage, current, cellTemperatures, controlBoardTemperature, busbarVoltages, busCurrent = self.controlBoard.getDetails(True)
				tempRX = self.controlBoard.rx
				busVoltageReadingResult = checkFunctions.voltageReadingCheckFetOn(sumOfCellVoltage, busVoltage, cellResult)
				#use averages functions for busbar voltages and current reading as they're more accurate
				busbarResult = checkFunctions.busBarCheck(self.controlBoard.getBusBarVoltagesAve(), cellVoltages)
				currentResult = checkFunctions.currentCheck(self.controlBoard.getCurrentAve())
			
			#include only section of readings that change between HV off and on in the full results string
			detailsLog = detailsLog + "\nSecond readings (HV ON):\n" + re.findall(r"Sum of Cell Voltages:.*Bus Voltage:\s+[+-]?[0-9]+\.[0-9]+", tempRX, flags=re.S)[0].strip()
			checkFunctions.voltageCheck(bmVoltage, sumOfCellVoltage)		#check that BM is safe for indoor work
			if self.hwVersion in self.v18Parts:
				self.controlBoard.fastHVOff()
			else:
				self.controlBoard.turnHVOff()
			self.gui.wait(1)
			cellVoltageDifference = max(cellVoltages) - min(cellVoltages)

			#final HV off section
			if ((self.hwVersion == 12069) and (self.hwRevision < 8)):
				soc, cellVoltages, sumOfCellVoltage, bmVoltage, busVoltage, current, cellTemperatures, controlBoardTemperature = self.controlBoard.getDetails(True)
			else:
				soc, cellVoltages, sumOfCellVoltage, bmVoltage, busVoltage, current, cellTemperatures, controlBoardTemperature, busbarVoltages, busCurrent = self.controlBoard.getDetails(True)
			tempRX = self.controlBoard.rx
			#include only section of readings that change between HV on and off in the full results string
			detailsLog = detailsLog + "\n\nFinal readings (HV OFF):\n" + re.findall(r"Sum of Cell Voltages:.*Bus Voltage:\s+[+-]?[0-9]+\.[0-9]+", tempRX, flags=re.S)[0].strip()
			hvOff = checkFunctions.hvShutoff(busVoltage)		#check that HV correctly turned off

		#make any color changes needed then remove ANSI codes and add to details textbox
		debuglogs_raw = self.gui.colorSwap(text=detailsLog, red=checkFunctions.red, yellow=checkFunctions.yellow, blue=checkFunctions.blue)
		debuglogs = self.gui.ansiReplace(debuglogs_raw)
		
		#remove lines from the log string of asking for readings
		countVar = tk.IntVar()
		idx = '1.0'
		while 1:
			idx = self.gui.textBox.search(r"BM>.*", idx, stopindex=tk.END, count=countVar, regexp = True)
			if not idx: break
			lastidx = '%s + %sc' % (idx, countVar.get())
			# idx = '%s - %dc' % (idx, 1)
			self.gui.textBox.delete(idx, lastidx)
		
		#add testing technician line to logs
		debuglogs = 'Testing technician: ' + self.technician + '\n' + self.gui.textBox.get("1.0", tk.END)

		self.gui.test_over()

		errorString = 'CV: ' + str(cellResult) + ', Cur: ' + str(currentResult) + ', BMV: ' + str(battVoltageReadingResult) + ', BusV: ' + str(busVoltageReadingResult) + ', CellT: ' + str(cellTemperatureResult) + ', CBT: ' + str(controlBoardTemperatureResult) + ', HST: ' + str(onboardTemperatureResult) + ', BBV: ' + str(busbarResult) + ', HVOff: ' + str(hvOff)

		if len(checkFunctions.failure) == 0:		#no issues
			airtableMessage = self.dateToday + " - Final BM Check, No Error"

			self.gui.label("Adding: " + airtableMessage)

			self.gui.resultsUpload(testName=self.testName, deviceUnderTest=serialNumber, result='Pass', testData=debuglogs, testData1=cellVoltageDifference, testData2=soc)

		else:
			airtableMessage = self.dateToday + " - Final BM Check, Errors: "

			self.gui.label("Adding: " + airtableMessage + checkFunctions.errorMessage)
			self.gui.label("DEBUG NEEDED", color='red')

			self.gui.resultsUpload(testName=self.testName, deviceUnderTest=serialNumber, result='Fail', testData=errorString + '\n' + debuglogs, failureType = checkFunctions.failure, testData1 = cellVoltageDifference, testData2=soc)

		self.controlBoard.close()		#close out COM connection

		self.gui.wait_for_unplug()		#have technician unplug USB cable
		self.gui.restartButton()