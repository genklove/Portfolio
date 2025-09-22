import airtable
import re
import copy
from datetime import datetime
from GUI_Class import GUI

class recordCheck():
	def __init__(self, externalgui: GUI):
		self.gui = externalgui

		self.assyParts = airtable.Airtable('base ID','Assembled Parts','API key')
		self.testInstances = airtable.Airtable('base ID','Test Instances','API key')
		self.qcInstances = airtable.Airtable('base ID','QC Instances','API key')

		#all items in this dict need to be formatted as a tuple of the top serial version and revision respectively for the keys,
		#and a list of lists of subassembly name, version, list of accepted revisions, and expected quantity of the subassembly
		#all BM and CM top serial numbers and revisions need to be acounted for
		self.assembliesDict = {
			#v14 BMs
			(18016, 18): [['Stack', 15195, [10, 12, 13], 5], ['CM', 17997, [12, 14], 1], ['Tempsense', 18018, [8], 3], ['BMS', 18019, [8], 1]],
			(18016, 19): [['Stack', 15195, [10, 12, 13], 5], ['CM', 17997, [15], 1], ['Tempsense', 18018, [8], 3], ['BMS', 18019, [8], 1]],
			(18016, 21): [['Stack', 15195, [10, 12, 13], 5], ['CM', 17997, [12, 14, 15], 1], ['Tempsense', 18018, [8], 3], ['BMS', 18019, [8], 1]],
			(18016, 22): [['Stack', 15195, [13], 5], ['CM', 17997, [16], 1], ['Tempsense', 18018, [8], 3], ['BMS', 18019, [9], 1]],
			#v14 LE BMs
			(32380, 1): [['Stack', 15195, [13], 4], ['CM', 17997, [16], 1], ['Tempsense', 18018, [8], 3], ['BMS', 18019, [9], 1], ['LE Stack', 32357, [1], 1]],
			#v17 BMs
			(27214, 2): [['Stack', 27217, [2], 5], ['CM', 27219, [2], 1], ['BMS', 27230, [2], 1]],
			(27214, 3): [['Stack', 27217, [3], 5], ['CM', 27219, [3], 1], ['BMS', 27230, [2], 1]],
			(27214, 4): [['Stack', 27217, [3], 5], ['CM', 27219, [3, 4], 1], ['BMS', 27230, [2], 1]],
			(27214, 6): [['Stack', 27217, [5], 5], ['CM', 27219, [3, 4], 1], ['BMS', 27230, [2], 1]],
			(27214, 7): [['Stack', 27217, [5, 6], 5], ['CM', 27219, [5], 1], ['BMS', 27230, [2], 1]],
			(27214, 8): [['Stack', 27217, [5, 6], 5], ['CM', 27219, [5], 1], ['BMS', 27230, [2], 1]],
			(27214, 15): [['Stack', 27217, [5, 6, 7], 5], ['CM', 27219, [5, 6], 1], ['BMS', 27230, [2], 1]],
			(27214, 16): [['Stack', 27217, [6, 7], 5], ['CM', 27219, [6, 11], 1], ['BMS', 27230, [4], 1]],
			(27214, 17): [['Stack', 27217, [9], 5], ['CM', 27219, [11], 1], ['BMS', 27230, [4], 1]],
			(27214, 25): [['Stack', 27217, [15], 5], ['CM', 27219, [16], 1], ['BMS', 27230, [7], 1]],
			(27214, 28): [['Stack', 27217, [16], 5], ['CM', 27219, [16, 18], 1], ['BMS', 27230, [9], 1]],
			(27214, 29): [['Stack', 27217, [16], 5], ['CM', 27219, [18], 1], ['BMS', 27230, [9], 1]],
			(27214, 30): [['Stack', 27217, [16], 5], ['CM', 27219, [18, 20], 1], ['BMS', 27230, [9, 10], 1]],
			(27214, 31): [['Stack', 27217, [16], 5], ['CM', 27219, [18, 20], 1], ['BMS', 27230, [9, 10], 1]],
			(27214, 32): [['Stack', 27217, [17], 5], ['CM', 27219, [20, 21], 1], ['BMS', 27230, [10], 1]],
			(27214, 33): [['Stack', 27217, [19], 5], ['CM', 27219, [20, 21], 1], ['BMS', 27230, [10], 1]],
			(27214, 34): [['Stack', 27217, [19, 20], 5], ['CM', 27219, [21], 1], ['BMS', 27230, [10], 1]],
			#v17 LE BMs
			(32004, 2): [['Stack', 27217, [15], 4], ['CM', 27219, [16], 1], ['BMS', 27230, [9], 1], ['LE Stack', 31996, [2], 1]],
			(32004, 3): [['Stack', 27217, [16], 4], ['CM', 27219, [18], 1], ['BMS', 27230, [9], 1], ['LE Stack', 31996, [2], 1]],
			(32004, 4): [['Stack', 27217, [16], 4], ['CM', 27219, [20], 1], ['BMS', 27230, [9], 1], ['LE Stack', 31996, [2], 1]],
			(32004, 5): [['Stack', 27217, [16], 4], ['CM', 27219, [20], 1], ['BMS', 27230, [10], 1], ['LE Stack', 31996, [2], 1]],
			#v14 CMs
			(17997, 10): [['Yokowo', 17635, [3], 1], ['Control Board', 17998, [5], 1], ['Tempsense', 22719, [3], 1]],
			(17997, 12): [['Yokowo', 17635, [3], 1], ['Control Board', 17998, [7], 1], ['Tempsense', 22719, [4], 1]],
			(17997, 15): [['Yokowo', 17635, [5], 1], ['Control Board', 17998, [7], 1], ['Tempsense', 22719, [4], 1]],
			(17997, 16): [['Yokowo', 17635, [6], 1], ['Control Board', 17998, [8], 1], ['Tempsense', 22719, [5], 1]],
			#v17 CMs
			(27219, 2): [['Yokowo', 27242, [1], 1], ['Control Board', 27786, [2], 1], ['Tempsense', 27974, [2], 1]],
			(27219, 3): [['Yokowo', 27242, [2], 1], ['Control Board', 27786, [3], 1], ['Tempsense', 27974, [2], 1]],
			(27219, 4): [['Yokowo', 27242, [2], 1], ['Control Board', 27786, [3], 1], ['Tempsense', 27974, [2], 1]],
			(27219, 5): [['Yokowo', 27242, [2], 1], ['Control Board', 27786, [3], 1], ['Tempsense', 27974, [2], 1]],
			(27219, 6): [['Yokowo', 27242, [2], 1], ['Control Board', 27786, [3], 1], ['Tempsense', 27974, [2], 1]],
			(27219, 11): [['Yokowo', 27242, [2], 1], ['Control Board', 27786, [5], 1], ['Tempsense', 27974, [2], 1]],
			(27219, 16): [['Yokowo', 27242, [3], 1], ['Control Board', 27786, [6], 1], ['Tempsense', 27974, [2], 1]],
			(27219, 18): [['Yokowo', 27242, [3], 1], ['Control Board', 27786, [6], 1], ['Tempsense', 27974, [2], 1]],
			(27219, 20): [['Yokowo', 27242, [3], 1], ['Control Board', 27786, [6], 1], ['Tempsense', 27974, [2], 1]],
			(27219, 21): [['Yokowo', 27242, [3], 1], ['Control Board', 27786, [6], 1], ['Tempsense', 27974, [2], 1]]
		}

	def checkAssociations(self, record: dict, hwVersion: int, hwRevision: int, qcType: str):
		subAssemblies = []
		nonconforming = []
		stackList = []
		workingDict = copy.deepcopy(self.assembliesDict)		#make deep copy to be edited

		#find the approporiate list of subassemblies to compare against from the dictionary
		for key, value in workingDict.items():
			if (hwVersion, hwRevision) == key: expectedParts = value

		#get a list of all the subassembly serial numbers for the top level serial number
		#if there is no 'Assembly Contains' field then nothing is associated
		try:
			for subassembly in record['fields']['Assembly Contains']:
				subAssemblies.append(str(self.assyParts.get(subassembly)['fields']['Name']))
			subAssemblies.sort()		#sort for better readability for users
		except KeyError:
			#make labels for each missing association and their expected quantity
			for part in expectedParts:
				if part[0] == 'BMS' and qcType == 'BM Base': continue		#no BMS installed at base, ignore missing part
				#part[3] is quantity, part[0] is name
				self.gui.label(text='Missing ' + str(part[3]) + ' ' + part[0] + '(s) from association', color='red', big=True)
			return

		#count down the number of subassemblies present and check that they all have an accepted revision
		for subassembly in subAssemblies:
			temp = re.findall('[0-9]+', subassembly)
			res = list(map(int, temp))
			tempVersion = res[0]
			tempRevision = res[1]
			for part in expectedParts:
				if tempVersion == part[1]:		#find matching list for a part number
					part[3] += -1				#account for an associated part by counting down number of expected remaining
					if tempRevision not in part[2]: nonconforming.append([part[0], subassembly, tempRevision, part[2]])		#part is present but wrong revision
					if 'Stack' in part[0]: stackList.append(subassembly)		#keep track of stacks for later checks

		#tell the user which subassemblies are missing
		for part in expectedParts:
			if part[3] != 0:		#a given part still has remaining expected
				if part[0] == 'BMS' and qcType == 'BM Base': continue		#no BMS at base, ignore
				#part[3] is quantity, part[0] is name
				self.gui.label(text='Missing ' + str(part[3]) + ' ' + part[0] + '(s) from association', color='red', big=True)

		#tell the user which subassemblies have the wrong revision
		for i in range(len(nonconforming)):
			#nonconforming items are [name, full serial, actual revision, accepted revision(s)]
			correctRevString = nonconforming[i][0] + " " + nonconforming[i][1] + " has revision " + str(nonconforming[i][2]) + ", should be: "
			if len(nonconforming[i][3]) == 1:		#one accepted revision
				correctRevString += str(nonconforming[i][3][0])
			else:		#multiple accepted revisions
				for j in range(len(nonconforming[i][3])):		#for each accepted revision
					if j == len(nonconforming[i][3])-2:			#add 'or' before last item
						correctRevString = correctRevString + str(nonconforming[i][3][j]) + ', or '
					else:
						correctRevString = correctRevString + str(nonconforming[i][3][j]) + ', '
				correctRevString = correctRevString[:-2]		#remove last ', ' 
			self.gui.label(text=correctRevString, color='dark orange', big=True)
		
		#check if BM is considered pick tested
		# self.isPickTest(stackList=stackList)		#pick test BMs not in demand, stop checking until asked for
		
		#check that batches match
		self.cellBatchCheck(stackList=stackList, qcType=qcType)

		#check that subassemblies have all necessary parts and what their status is
		self.gui.label(text="Assembly contains:", big=True)
		for subassembly in subAssemblies:
			subRecord = self.assyParts.match('Name', subassembly, view='Auto: Master Top View')
			errors = self.subassemblyTestCheck(record=subRecord, serialNum=subassembly, componentType=str(subRecord['fields']['Sync: Description']))
		if errors == 0:
			self.gui.label(text="All subassembly records are good!", color='dark green', big=True)

	def isPickTest(self, stackList: list[str]):
		for stack in stackList:		#items in stack list are serial numbers not record dictionaries
			subRecord = self.assyParts.match('Name', stack, view='Auto: Master Top View')
			individualPickTest = False
			try:
				for i in range(len(subRecord['fields']['Lookup: QC Passes'])):
					if 'Pick Test' in str(subRecord['fields']['Lookup: QC Passes'][i]):
						individualPickTest = True
						break			#pick test QC found, stop searching
			except KeyError: pass		#no picktest on this stack
			if not individualPickTest:
				return				#if a single stack isn't pick tested, BM is not considered pick tested
		
		#all stacks checked and function not yet returned
		self.gui.label('This is a Pick Test BM', big=True, color='purple')
	
	def cellBatchCheck(self, stackList: list[str], qcType: str):
		cellBatches = []
		for stack in stackList:		#items in stack list are serial numbers, not record dictionaries
			subRecord = self.assyParts.match('Name', stack, view='Auto: Master Top View')
			try:
				cellBatches.append(str(subRecord['fields']['Cell Batch']))
			except KeyError:		#no batch listed in Airtable
				cellBatches.append('') 
		if '' in cellBatches and qcType == "BM Base":		#batches still visible at base
			self.gui.label("Could not check cell batches, please look directly at stacks")
		elif '' in cellBatches:
			self.gui.label("Not all batch records available")
		
		batchMatch = True
		firstPresentBatch = ''
		for batch in cellBatches:
			if batch and not firstPresentBatch:				#save first non empty batch to check others against
				firstPresentBatch = batch
			if batch and batch != firstPresentBatch:		#if batch exists and does not match other existing batch, mix deteted
				batchMatch = False
				self.gui.label("Cell Batches Mixed!", color='red', big=True)
				break
		if batchMatch and firstPresentBatch:				#no mix detected and batch information at least partially available 
			self.gui.label("Cell batches good", color='dark green', big=True)

	def testCheck(self, record: dict, qcType: str):
		missingTests = []
		missingString = 'This assembly is missing: '

		#check if BM was manual or auto assembly
		autoAssembled = False
		if qcType == 'BM Packout':
			try:
				if self.newestQC[-1]['fields']['EOL Manual or Auto Assembly'] == 'Auto Line Assembly: No paper traveler, no Base or Core QC records':
					autoAssembled = True
			except KeyError: pass

		if qcType != 'CM':				#check for all BM records
			if not autoAssembled:		#Base QC not performed during autoline production
				try:
					if 'Base' not in str(record['fields']['Lookup: QC Passes']):
						missingTests.append("Base QC")
				except KeyError:
					missingTests.append("Base QC")
			try:		#BM should have validation pass for any QC past base
				if str(record['fields']['Lookup: Validation'][0]) != 'Pass':
					missingTests.append("Validation")
			except KeyError:
				missingTests.append("Validation")

		if qcType in ['BM EOL', 'BM Packout']:	#BM past core level
			if not autoAssembled:		#Core QC not performed during autoline production
				try:
					if 'Core' not in str(record['fields']['Lookup: QC Passes']):
						missingTests.append("Core QC")
				except KeyError:
					missingTests.append("Core QC")
			#BM should have hi pot and pulse passes for any QC past core
			try:
				if str(record['fields']['Lookup: Hi Pot Test'][0]) != 'Pass':
					missingTests.append("Insulation Test")
			except KeyError:
				missingTests.append("Insulation Test")
			try:
				if str(record['fields']['Lookup: Pulse Test'][0]) != 'Pass':
					missingTests.append("Pulse Test")
			except KeyError:
				missingTests.append("Pulse Test")

		if qcType == 'BM Packout':
			#every BM needs EoL QC regardless of auto or manual prod
			try:
				if 'EoL' not in str(record['fields']['Lookup: QC Passes']):
					missingTests.append("EoL QC")
			except KeyError:
				missingTests.append("EoL QC")

		if qcType == 'CM':
			#make sure every CM has hi pot, functionality, and FET tests
			try:
				if str(record['fields']['Lookup: Hi Pot Test'][0]) != 'Pass':
					missingTests.append("Insulation Test")
			except KeyError:
				missingTests.append("Insulation Test")
			try:
				if str(record['fields']['Lookup: Validation'][0]) != 'Pass':
					missingTests.append("Functionality")
			except KeyError:
				missingTests.append("Functionality")
			try:
				if str(record['fields']['Lookup: FET Test'][0]) != 'Pass':
					missingTests.append("FET Test")
			except KeyError:
				missingTests.append("FET Test")

		if len(missingTests) == 0:
			self.gui.label(text="All test records are present and good!", color='dark green', big=True)
		else:
			for test in missingTests:
				missingString = missingString + test + ', '
			missingString = missingString[:-2]		#remove last ', '
			self.gui.label(text=missingString, color='red', big=True)

	def subassemblyTestCheck(self, record: dict, serialNum: str, componentType: str) -> int:
		missingTests = []
		missingString = ', Missing: '
		color = 'black'
		status = None

		#warn user that a subassembly is in a bad status
		try:
			status = str(record['fields']['Status'])
			if status in ['Production Debug', 'Recycled/Disassembled', 'Engineering - Not for Production']:
				self.gui.label(text= componentType + ' ' + serialNum + " is " + status + "!", color='red', big=True)
				return 1
			elif status == 'Tested': color = 'dark green'
		except KeyError:
			pass

		#make sure stacks have hi pot and pulse and are in a good status
		if 'Welded Stack' in componentType or 'LE Cell Stack 5' in componentType:
			if status in ['Tested', 'Vacuum Tested', 'Production Ready']: color= 'dark green'
			else: color = 'orange'
			try:
				if str(record['fields']['Lookup: Hi Pot Test'][0]) != 'Pass':
					missingTests.append("Insulation Test")
			except KeyError:
				missingTests.append("Insulation Test")
			try:
				if str(record['fields']['Lookup: Pulse Test'][0]) != 'Pass':
					missingTests.append("Pulse Test")
			except KeyError:
				missingTests.append("Pulse Test")
		
		#check that a fully assembled CM in a BM has QC, hi pot, functionality, and FET test, and is in completed status
		elif 'Control Module' in componentType and 'Tempsense' not in componentType and 'Yokowo' not in componentType:
			try:
				if 'CM' not in str(record['fields']['Lookup: QC Passes'][0]):
					missingTests.append("CM QC")
			except KeyError:
				missingTests.append("CM QC")
			try:
				if str(record['fields']['Lookup: Hi Pot Test'][0]) != 'Pass':
					missingTests.append("Insulation Test")
			except KeyError:
				missingTests.append("Insulation Test")
			try:
				if str(record['fields']['Lookup: Validation'][0]) != 'Pass':
					missingTests.append("Functionality")
			except KeyError:
				missingTests.append("Functionality")
			try:
				if str(record['fields']['Lookup: FET Test'][0]) != 'Pass':
					missingTests.append("FET Test")
			except KeyError:
				missingTests.append("FET Test")
			if status == 'Completed': color = 'dark green'
			else: color = 'orange'
		
		#check that BMS has been tested
		elif 'BMS' in componentType:
			try:
				if str(record['fields']['Lookup: Validation'][0]) != 'Pass':
					missingTests.append("BMS Test")
			except KeyError:
				missingTests.append("BMS Test")
		
		#make sure control board is in tested status
		elif 'Control Board' in componentType:
			if status != 'Tested':
				color = 'orange'
		
		try:
			try:		#try to include cell batch next to each stack serial num
				if 'Welded Stack' or 'LE Cell Stack 5' in componentType:
					batchString = ', Cell Batch: ' + str(record['fields']['Cell Batch'])
				else:
					batchString = ''
			except KeyError: 
				batchString = ''
			if len(missingTests) != 0:
				#include missing tests/Qcs next to each component serial num
				for test in missingTests:
					missingString = missingString + test + ', '
				missingString = missingString[:-2]		#remove last ', '
				self.gui.label(text=serialNum + ', Type: ' + componentType + ', Status: ' + str(record['fields']['Status']) + batchString + missingString, color='red', big=True)
			else:
				self.gui.label(text=serialNum + ', Type: ' + componentType + ', Status: ' + str(record['fields']['Status']) + batchString, color=color, big=True)
		except KeyError:		#if component has no status, just include serial num, component name, and any missing tests/QCs
			if len(missingTests) != 0:
				missingString = ''
				for test in missingTests:
					missingString = missingString + test + ', '
				missingString = missingString[:-2]		#remove last ', '
				self.gui.label(text=serialNum + ', Type: ' + componentType + missingString, color='red', big=True)
			else:
				self.gui.label(text=serialNum + ', Type: ' + componentType, color=color, big=True)
		return len(missingTests)

	def getNewestEachTest(self, record: dict) -> dict | None:
		testDict = {}
		try:
			allTests = record['fields']['Link: Part Test Instances']
		except KeyError:		#component has no test records
			self.newestTest = None
			return None

		for test in allTests:
			newest = False
			if test == allTests[-1]:		#most recent test always at the end of the list
				newest = True
			test = self.testInstances.get(str(test))		#get the full record for current test
			name = str(test['fields']['Test Name'])
			if name in testDict.keys():		#a test of the same type is already in the dict
				testDict[name].append((str(test['fields']['Test Result']), str(test['createdTime'])))
			else:							#create a key for this type of test
				testDict[name] = [(str(test['fields']['Test Result']), str(test['createdTime']))]
			if newest: self.newestTest = (name, testDict[name][-1][0], testDict[name][-1][1], test)		#create class variable of newest test's name, result, and reported time
		newestPasses = {}
		for key, value in testDict.items():
			times = []
			for test in value:
				if test[0] == 'Pass':
					times.append(test[1])			#append times only for tests with a pass result
			for test in value:
				if test[1] == max(times):			#if this test is the most recent of its type
					newestPasses[key] = test[1]		#create a dicitonary entry for the current test type and the most recent time that test passed
		return newestPasses

	def getNewestEachQC(self, record: dict) -> dict | None:
		qcDict = {}
		try:
			allQCs = record['fields']['Link: QC Instances']
		except KeyError:			#component has no QC instances
			self.newestQC = None
			return None

		for qc in allQCs:
			newest = False
			if qc == allQCs[-1]:			#most recent QC always at the end of the list
				newest = True
			qc = self.qcInstances.get(str(qc))		#get the full record for current QC
			name = str(qc['fields']['Inspection Type'])
			if name in qcDict.keys():		#a QC of the same type is already in the list
				qcDict[name].append((str(qc['fields']['QC PASS']), str(qc['createdTime'])))
			else:							#create a key for this type of QC
				qcDict[name] = [(str(qc['fields']['QC PASS']), str(qc['createdTime']))]
			if newest: self.newestQC = (name, qcDict[name][-1][0], qcDict[name][-1][1], qc)		#create class variable of newest QC's name, result, and reported time
		newestPasses = {}
		for key in qcDict.keys():
			times = []
			for qc in qcDict[key]:
				if qc[0] == 'Pass':
					times.append(qc[1])			#append times only for QCs with a pass result
			for qc in qcDict[key]:
				if qc[1] == max(times):			#if this QC is the most recent of its type
					newestPasses[key] = qc[1]	#create a dicitonary entry for this current QC type and the most recent time there was a pass for it
		return newestPasses

	def continuityCheck(self, record: dict, qcType: str):
		#check that tests and QCs that must be specific orders regardless of rework status adhere to the proper order
		testPassDict = self.getNewestEachTest(record)
		qcPassDict = self.getNewestEachQC(record)
		issuesString = ''
		warningsString = ''

		if not qcPassDict:		#without any QC records, continuity cannot be checked
			if testPassDict:	#show user most recent test info if available
				self.gui.label('Most recent test: ' + self.newestTest[0] + ', result: ' + self.newestTest[1] + ', tested ' + self.strftime(self.newestTest[2]), color='blue violet', big=True)
			return

		if testPassDict:
			try:
				if qcPassDict['Base'] > testPassDict['Battery Module Validation']:		#if BM goes down to base level, validation always needed when building back up
					issuesString += 'Validation was skipped in current build up, '
			except KeyError: pass

			#this should already be covered by test check but just for redundancy
			if self.newestTest[0] == 'Battery Module Validation' and self.newestTest[1] == 'Fail':
				issuesString += 'Most recent Validation failed, '
		
		if qcType in ['BM EOL', 'BM Packout']:
			try:
				if (qcPassDict['Base'] > qcPassDict['Core']) or (self.newestQC[0] == 'Base'):		#make sure there was a core QC after most recent base QC
					issuesString += 'Core QC was skipped in the current build up, '
			except KeyError: pass

			#this should already be covered by test check but just for redundancy
			if self.newestQC[0] in ['Base', 'Core'] and self.newestQC[1] == 'Fail':
				issuesString += 'Most recent ' + self.newestQC[0] + ' QC failed, '

			#packout QC should be final and no reword performed after it, warn users that this BM already passed
			if self.newestQC[0] == 'Packout' and self.newestQC[1] == 'Pass':
				warningsString += 'This BM has already passed Packout QC most recently, '

			#make sure that EoL is the most recent QC if doing packout QC
			elif qcType == 'BM Packout':
				if self.newestQC[0] != 'EoL':
					issuesString += 'EoL QC was skipped in the current build up, '

			if testPassDict:
				try:
					#if a BM returns to base level, pulse test must be performed again by EoL QC
					if qcPassDict['Base'] > testPassDict['Battery Module Pulse Test']:
						issuesString += 'Pulse test was skipped in current build up, '
				except KeyError: pass
				try:
					#a core QC means the BM was opened and thus needs another hi pot test after being closed again
					if qcPassDict['Core'] > testPassDict['BM Insulation: DCW']:
						issuesString += 'BM has not been insulation tested since last closed, '
				except KeyError: pass

				#this should already be covered by test check but just for redundancy
				if self.newestTest[1] == 'Fail':
					issuesString += 'Most recent ' + self.newestTest[0] + ' failed, '
		
		if qcType == 'BM EOL':
			if self.newestQC[0] == qcType:
				#alert user that this BM has already passed EoL QC most recently
				if self.newestQC[1] == 'Pass':
					warningsString += 'This BM already passed EoL QC most recently, '
				else:
					try:
						#check if BM most recently fell out for gasket issue
						gasketsSection = self.newestQC[-1]['fields']['EOL Gaskets and Labels Check']
						if 'Sealing gaskets installed and not damaged' not in gasketsSection:
							try:
								#BM must be opened to deal with gasket problems and thus need another hi pot test after being closed again
								if testPassDict['BM Insulation: DCW'][2] < self.newestQC[2]:
									issuesString += 'This BM has not received insulation tseting since falling out for a gasket problem'
							except (KeyError, IndexError):		#no hi pot test pass found
								issuesString += 'This BM has not received insulation tseting since falling out for a gasket problem'
					except KeyError: pass
		
		if qcType == 'BM Packout' and testPassDict:
			try:
				#warn users that another test has been run since EoL QC which is not standard for production flow but not strictly prohibited
				if self.newestTest[2] > qcPassDict['EoL']:
					warningsString += self.newestTest[0] + ' has been run since last EoL QC, '
			except KeyError: pass
		
		if warningsString: 
			warningsString = warningsString[:-2]		#remove last ', '
			self.gui.label(warningsString, color='dark orange', big=True)
		if issuesString: 
			issuesString = issuesString[:-2]			#remove last ', '
			self.gui.label(issuesString, color='red', big=True)

		#show user most recent test and QC records
		if testPassDict:
			self.gui.label('Most recent test: ' + self.newestTest[0] + ', result: ' + self.newestTest[1] + ', tested ' + self.strftime(self.newestTest[2]), color='blue violet', big=True)
		self.gui.label('Most recent QC: ' + self.newestQC[0] + ', result: ' + self.newestQC[1] + ', submitted ' + self.strftime(self.newestQC[2]), color='blue violet', big=True)

	def strftime(self, dateStr: str) -> str:
		#take the time stamp string from Airtable and convert it to a datetime object so it can be easily formatted by datetime.strftime
		date, time = dateStr.split('T')
		Y, m, d = date.split('-')
		H, M, S = time.split(':')
		dttm = datetime(int(Y), int(m), int(d), int(H), int(M), int(float(S[:-1])))
		return dttm.strftime('%m/%d/%Y, %H:%M:%S')

	def start(self):
		while True:
			self.main()

	def main(self):
		qcType = self.gui.optionSelect(header='Which QIS are you performing?', optionsText=['CM', 'BM Base', 'BM Core','BM EOL', 'BM Packout'], reask=True)
		serialNumber = self.gui.getSerial()
		qcType = self.gui.savedSelection		#get the qc selection again in case the user changed it during serial entry
		statusRecord = self.assyParts.match('Name', serialNumber, view='Auto: Master Top View')
		temp = re.split('-', serialNumber)
		hwVersion = int(temp[1])
		hwRevision = int(temp[2])
		if (hwVersion, hwRevision) not in self.assembliesDict.keys():		#can't check this part number revision combo against dictionary
			self.gui.label("The part number or the revision for this part number is not supported, please use DALT", big=True)
			self.gui.restartButton()
			return

		self.gui.label(text=qcType, color='blue', big=True)
		self.gui.test_in_progress(testName="Record Check")

		self.checkAssociations(record=statusRecord, hwVersion=hwVersion, hwRevision=hwRevision, qcType=qcType)
		self.gui.label('')			#add space for readability
		if qcType not in ['CM', 'BM Base']: 
			self.continuityCheck(record=statusRecord, qcType=qcType)
			self.gui.label('')		#add space for readability
		if qcType != 'BM Base': self.testCheck(record=statusRecord, qcType=qcType)
		try:						#display any notes someone may have made in history comments
			historyComments = 'History Comments:\n' + str(statusRecord['fields']['Sync: History Comments'])
		except KeyError:
			historyComments = 'No history comments yet'
		self.gui.label(historyComments)
		self.gui.test_over()
		self.gui.restartButton()