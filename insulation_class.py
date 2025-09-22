import timeit
from hiPotTester import hiPotTester
import airtable
from datetime import date
from colorama import init, Fore
import re
from serial import *
from requests.exceptions import *
from GUI_Class import GUI

class insulation():
	def __init__(self, externalgui: GUI, testingTechnician: str = ''):
		self.gui = externalgui
		self.technician = testingTechnician

		self.assyParts = airtable.Airtable('base ID','Assembled Parts','API key')
		self.testInstances = airtable.Airtable('base ID','Test Instances','API key')

		self.equipment = 'EPP-20489-1-2'

		#list of status possible during regular production before a component is completed and sent for delivery
		self.productionStatuses = ['Incomplete', 'Assembled', 'Started', 'Associated', 'Validated', 'Insulation Tested', 'Pulse Tested', 'Tested', 'Completed', 'Production Debug']


		#all serial numbers accepted by this test organized by component type and version
		self.cmHWVersions = ['17997', '27219', '36242']
		self.bmV14 = ['18016', '32380']
		self.bmV17 = ['27214', '32004']
		self.bmv18 = ['32827', '36242']
		self.bmHWVersions = self.bmV14 + self.bmV17 + self.bmv18
		self.dummyHWVersions = ['30005', '30006', '30008', '30009']
		
		init()

		self.testComments = ''

	def start(self):
		COMPort = self.gui.portAssign()		#have user choose GPT as their are multiple stations that perform this test
		self.hiPotTester = hiPotTester.hiPotTester(str(COMPort))
		#choose testing mode
		self.testMode = self.gui.optionSelect(header="Is this test for: ", optionsText=['Production', 'Ops Debug', 'Engineering'], reask=True)
		while True:
			self.main()

	def checkStatuses(self, reconnect: bool = False):
		try:
			statusRecord = self.assyParts.match('Name', self.serialNumber, view='Auto: Master Top View')
		except (ConnectionError, HTTPError):
			#serial number has already been verified by GUI class but internet/Airtable connection could drop b/w requests

			#autoretry one time
			if not reconnect:
				self.checkStatuses(reconnect=True)
				return
			else:
				self.gui.label("Make sure internet is connected then press continue to test!", name='check internet', big=True)
				self.gui.continueButton()
				self.gui.remove_widget('check internet')
				self.checkStatuses()
				return
		nonProduction = False
		engineering = True
		for i in range(len(statusRecord['fields']['Lookup: Status Instances Select'])):
			if statusRecord['fields']['Lookup: Status Instances Select'][i] not in self.productionStatuses:		#component has left normal production cycle
				nonProduction = True
			if statusRecord['fields']['Lookup: Status Instances Select'][i] == 'Validated':		#specific case of battery receiving engineering testing at base level
				engineering = False

		#alert user that the selected testing mode doesn't match with what's expected for this components status history and ask if they would like to change to expected testing mode
		if engineering and (self.testMode != 'Engineering'):
			changeMode = self.gui.optionSelect(header="This BM has not been validated, would you like to change to Engineering mode?", optionsText=['Yes, run test as Engineering', 'No, keep using current selection'])
			if 'Yes,' in changeMode:
				self.testMode = 'Engineering'
		elif not engineering and (self.testMode == 'Engineering'):
			changeMode = self.gui.optionSelect(header='This BM has been validated, would you like to switch to Production or Ops Debug mode?', optionsText=['Yes, run test as Production', 'Yes, run test as Ops Debug', 'No, keep using Engineering'])
			if 'Production' in changeMode:
				self.testMode = 'Production'
			elif 'Ops Debug' in changeMode:
				self.testMode = 'Ops Debug'
		if not nonProduction and (self.testMode == 'Ops Debug'):
			changeMode = self.gui.optionSelect(header="This BM only has production history, would you like to change to Production mode?", optionsText=['Yes, run test as Production', 'No, keep using Ops Debug'])
			if "Yes," in changeMode:
				self.testMode = 'Production'
		elif nonProduction and (self.testMode == 'Production'):
			changeMode = self.gui.optionSelect(header="This BM has non-production history, would you like to change to Ops Debug mode?", optionsText=['Yes, run test as Ops Debug', 'No, keep using Production'])
			if "Yes," in changeMode:
				self.testMode = 'Ops Debug'
	
	def IR(self, testName: str, stepNumber: int, resistanceThreshold: int, voltage: str, testLength: int | float = 0) -> str:
		try:
			self.hiPotTester.goToStep(stepNumber)
		except SerialException:		#GPT has been disconnected from the computer, ask user to choose port again
			COMPort = self.gui.portAssign()		#have user choose GPT as their are multiple stations that perform this test
			self.hiPotTester = hiPotTester.hiPotTester(str(COMPort))
			self.hiPotTester.goToStep(stepNumber)
		self.hiPotTester.setManuName(voltage + ' IR')

		#list test settings before data for easier viewing in Airtable
		test_data = testName + ' ' + voltage + ' '  + str(testLength) + " sec\n\r"

		self.gui.test_in_progress(HV=True, testLength=testLength, testName=voltage+" IR Test")
		self.hiPotTester.startTest()		#test settings are preset under step numbers so no need to define parameters here
		testStart = timeit.default_timer()
		seconds = 1
		self.gui.label(u'Resistance: ---- M\u03A9', name='current resistance')
		while(self.hiPotTester.isTestRunning() == 1):
			self.gui.wait(0.2)
			test_20 = self.hiPotTester.getMeasurements_insulation()
			res = test_20['raw'].split(',')[3].split('M ')[0]
			self.gui._dictPack['current resistance']['text'] = 'Resistance: ' + res + u' M\u03A9'		#update the label that displays what resistance the GPT is reading in mega ohms

			#get readings every second for the first 10 seconds then every 10 seconds after that
			if (timeit.default_timer() - testStart) > seconds:
				test_data = test_data + str(test_20['raw'])
				if seconds > 11:
					seconds = seconds + 10
				else:
					seconds = seconds + 1
		
		#if GUI timer is over but tester is still running wait for tester to finish before removing HV warning
		if self.hiPotTester.isTestRunning():
			self.gui.wait(0.5)
		
		self.gui.test_over()
		self.gui.remove_widget('current resistance')
		test_20 = self.hiPotTester.getMeasurements_insulation()		#get final readings
		self.testComments = re.sub(r'[^\x00-\x7f]', '', (test_data + str(test_20['raw']) + "\n\r" + self.testComments))		#remove potential random escape characters then add to overall test data
		print(test_data)
		#get final resistance value
		test_parsed = re.split(',', test_20['raw'])
		resistance = re.findall(r'\d+', test_parsed[3])
		try:
			resistance = int(resistance[0])
		except TypeError:		#if test is stopped before ramp time is over resistance reading will just be '----'
			resistance = 0
		#to ensure the test runs for the full duration, the minimum resistance limit is set very low so the test will often be a pass but the final resistanc value may not meet requirements
		if ('FAIL' in test_data) or (resistance < resistanceThreshold):
			self.gui.label(text=("FAILED " + voltage + " IR Test, Final Resistance: " + str(resistance) + u'M\u03A9'), color='red')
			testResult = 'Fail'
		else:
			self.gui.label(text=("PASSED " + voltage + " IR, Final Resistance: " + str(resistance) + u'M\u03A9'), color='darkgreen')
			testResult = 'Pass'
		return testResult

	def hiPot(self, stepNumber: int, voltage: str, testType: str, testLength: int | float = 0, colorCodeResult: bool = True) -> str:
		try:
			self.hiPotTester.goToStep(stepNumber)
		except SerialException:		#GPT has been disconnected from the computer, ask user to choose port again
			COMPort = self.gui.portAssign()		#have user choose GPT as their are multiple stations that perform this test
			self.hiPotTester = hiPotTester.hiPotTester(str(COMPort))
			self.hiPotTester.goToStep(stepNumber)

		self.hiPotTester.setManuName(voltage + ' ' + testType)

		self.gui.test_in_progress(HV=True, testLength=testLength, testName=voltage+" "+testType)
		self.hiPotTester.startTest()		#test settings are preset under step numbers so no need to define parameters here

		#wait for test to complete or fail early
		while(self.hiPotTester.isTestRunning() == 1):
			self.gui.wait(0.2)
		self.gui.test_over()
		self.test_1 = self.hiPotTester.getMeasurements()
		if testType == 'DCW': self.dcwVoltage = self.test_1['voltage']		#save final voltage readings for DCW tests, ACW is just for connectivity, final voltage doesn't matter
		self.hiPotTester.stopTest()
				
		self.testComments = str(self.test_1['raw']) + "\n\r" + self.testComments

		textColor = 'black'
		#if colorCodeResult is False, then the test is just for data collection and p/f doesn't matter so don't confuse user with red/green that doesn't affect final result
		if ('FAIL' in str(self.test_1['raw'])):
			if colorCodeResult: textColor = 'red'
			testResult = 'Fail'
		else:
			if colorCodeResult: textColor = 'dark green'
			testResult = 'Pass'
		self.gui.label(text=str(self.test_1['raw']).replace('\n', ''), color=textColor)		#display final readings
		return testResult

	def main(self):
		self.testComments = ''
		acceptedSerial = True

		self.serialNumber = self.gui.getSerial()
		self.testMode = self.gui.savedSelection		#redefine testMode variable in case user changed selection b/w tests
		self.technician = self.gui.technician		#redefine technician in case previous user signed out and new user signed in b/w tests
		hwVersion = self.serialNumber.split('-')[1]

		#only allow Ops Debug mode for BMs
		if (self.testMode == 'Ops Debug') and (hwVersion not in self.bmHWVersions):
			self.gui.label('This part number is not compatable with the Ops Debug test mode\nSwitching to Production mode', big=True)
			self.gui.restartButton()		#let use read the message then press continue to restart loop
			self.testMode = 'Production'
			return

		print(Fore.CYAN + 'ID Updated!' + Fore.RESET)

		if hwVersion in self.cmHWVersions:
			testName = 'CM Insulation Test'
			result = self.IR(testName=testName, stepNumber=17, resistanceThreshold=9999, voltage='1kV', testLength=20)

			#CM has only one record for all insulation tests so don't upload after each sub test
			if result == 'Fail' and hwVersion not in self.bmv18:		#v18 parameters not finalized, continue even if failed
				self.gui.resultsUpload(testName=testName, deviceUnderTest=self.serialNumber, result=result, testData='Testing technician: ' + self.technician + '\n' + self.testComments, equipment=self.equipment)
			
			else:
				result = self.hiPot(stepNumber=19, voltage='2.6kV', testType='DCW', testLength=11)
				self.gui.resultsUpload(testName=testName, deviceUnderTest=self.serialNumber, result=result, testData='Testing technician: ' + self.technician + '\n' + self.testComments, equipment=self.equipment, testData1=self.dcwVoltage)

		elif hwVersion in self.bmHWVersions:
			self.checkStatuses()		#make sure the current test mode matches status history
			#use lower IR threshold for Ops Debug since it's just for receiving and any BMS that get sent out again will need production level test
			if self.testMode == 'Ops Debug': resistanceThreshold = 1000
			else: resistanceThreshold = 2000
			#use GPT settings according to BM version
			if hwVersion in self.bmV14:
				acwStep, dcwStep, dcwTime = 4, 3, 75
			elif hwVersion in self.bmV17 or hwVersion in self.bmv18:
				acwStep, dcwStep, dcwTime = 7, 6, 85
			#use special settings for engineering testing, otherwise all BM DCW tests are 1.5 kV
			if self.testMode == 'Engineering':
				dcwStep, dcwTime, dcwVoltage = 8, 96, '2.15kV'
			else:
				dcwVoltage = '1.5kV'
			testName = 'BM Insulation: ACW'
			result = self.hiPot(stepNumber=acwStep, voltage='0.1kV', testType='ACW')		#check connectivity
			
			#upload each subtest as its own record
			self.gui.resultsUpload(testName=testName, deviceUnderTest=self.serialNumber, result=result, testData='Testing technician: ' + self.technician + '\n' + self.testComments, equipment=self.equipment)

			if result == 'Pass' or hwVersion in self.bmv18:		#v18 parameters not finalized, continue even if failed
				self.testComments = ''
				testName = 'BM Insulation: IR'
				result = self.IR(testName=testName, stepNumber=27, resistanceThreshold=resistanceThreshold, voltage='1kV', testLength=70)

				self.gui.resultsUpload(testName=testName, deviceUnderTest=self.serialNumber, result=result, testData='Testing technician: ' + self.technician + '\n' + self.testComments, equipment=self.equipment)

				if (result == 'Pass' or hwVersion in self.bmv18) and (self.testMode == 'Production'):		#only run DCW if in production, v18 parameters not finalized, continue even if failed
					self.testComments = ''
					testName = "BM Insulation: DCW"
					result = self.hiPot(stepNumber=dcwStep, voltage=dcwVoltage, testType='DCW', testLength=dcwTime)

					self.gui.resultsUpload(testName=testName, deviceUnderTest=self.serialNumber, result=result, testData='Testing technician: ' + self.technician + '\n' + self.testComments, equipment=self.equipment, testData1=self.dcwVoltage)
		
		elif hwVersion in self.dummyHWVersions:
			#dummies don't have enough capacitance for ACW, have to trust that the user properly connected tester to BM
			#little to no current for these tests, just use v14 settings since max voltages after ramp are the same for IR and DCW across versions
			testName = 'BM Insulation: IR'
			result = self.IR(testName=testName, stepNumber=27, resistanceThreshold=2000, voltage="1kV", testLength=70)

			self.gui.resultsUpload(testName=testName, deviceUnderTest=self.serialNumber, result=result, testData='Testing technician: ' + self.technician + '\n' + self.testComments, equipment=self.equipment)

			if result == 'Pass':
				self.testComments = ''
				testName = "BM Insulation: DCW"
				result = self.hiPot(stepNumber=6, voltage=dcwVoltage, testType='DCW', testLength=85)

				self.gui.resultsUpload(testName=testName, deviceUnderTest=self.serialNumber, result=result, testData='Testing technician: ' + self.technician + '\n' + self.testComments, equipment=self.equipment, testData1=self.dcwVoltage)
		
		else:
			#serial number is valid but is not a part that gets insulation tested, possibly scanned wrong serial sticker
			self.gui.label("Part number not supported by this test", color='orange red', big=True)
			acceptedSerial = False

		if acceptedSerial:
			self.gui.label("Insulation test complete, it is safe to remove yokowo connector", color='blue', big=True)
		self.gui.restartButton()
