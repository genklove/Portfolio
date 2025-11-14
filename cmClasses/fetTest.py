from cblog import cblog
import time
from GUI_Class import GUI
from cmOneStopSerial import cmOneStopSerial
from controlBoardSerialv13 import controlBoardSerialv13GUI
from itech import itech

class fetTest():
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

	def runCurrent(self) -> str:
		airtableMessage = ''
		self.gui.test_in_progress(HV=True, testName="High Current Test", testLength=35)
		# self.gui.wait(1)
		self.cmTester.feedBattfeedBus()			#engage contactors to feed both batt and bus ("8")
		self.controlBoard.turnHVOff()				#open FETs("4")
		self.battpsu.initializePulseTest(40, 40)	#set batt ITECH current limit to +-40A
		self.buspsu.initializePulseTest(40, 40)	#set bus ITECH current limit to +-40A
		self.battpsu.setVoltage(400)				#set batt ITECH V
		self.buspsu.setVoltage(400)				#set bus ITECH V
		self.battpsu.setOutputON()					#turn on batt ITECH
		self.buspsu.setOutputON()					#turn on bus ITECH

		self.gui.wait(0.5)
		self.controlBoard.resetShortCircuit()		#reset CM SC ("7")
		self.gui.wait(0.5)
		self.controlBoard.turnHVOn()				#close FETs ("3")
		aM = self.cblog('HVON')
		airtableMessage += aM[-1]
		self.gui.wait(0.5)
		#lower bus ITECH V in small steps to increase current b/w ITECHs
		self.buspsu.setVoltage(398)
		self.gui.wait(0.5)
		self.buspsu.setVoltage(397)
		self.gui.wait(0.5)
		self.buspsu.setVoltage(396)
		self.gui.wait(0.5)
		self.buspsu.setVoltage(395)
		self.gui.wait(0.5)
		self.buspsu.setVoltage(394)

		timeStart = int(time.time())
		while (int(time.time()) - timeStart) < 20:
			self.gui.wait(2)
			bmVoltage, busVoltage, current, cbTemps, aM = self.cblog('current')
			airtableMessage += aM
			#if cb temp readings ever get too far apart, fail the test
			if (max(cbTemps) - min(cbTemps)) > 5:
				detailedFail = 'Difference between thermistors > 5\n'
				self.gui.label(detailedFail[:-1])
				airtableMessage += detailedFail
				self.failureType.append('HC - FET temp delta')
				# self.failureType.append('FET Unequal Temp')
				break
			#if the current reading is too far from expected, fail for not being a true test
			elif current < 35:
				detailedFail = 'Current reading < 35A\n'
				self.gui.label(detailedFail[:-1])
				airtableMessage += detailedFail
				self.failureType.append('HC - low current')
				# self.failureType.append('Test Fail')
				self.gui.label("Current too low!", color='red')
				break

		self.controlBoard.turnHVOff()				#open FETs ("4")
		aM = self.cblog('HVOFF')
		airtableMessage += aM[-1]

		self.battpsu.setOutputOFF()				#turn off batt ITECH
		self.buspsu.setOutputOFF()					#turn off bus ITECH

		self.battpsu.initializePulseTest(1, 1)		#set batt ITECH current limit to +-1A
		self.buspsu.initializePulseTest(1, 1)		#set bus ITECH current limit to +-1A
		self.cmTester.turnContactorsOff()			#open contactors ("3")
		self.gui.wait(0.5)
		if len(self.failureType) == 0:
			self.gui.label("High Current Test Pass", color='dark green')
		else:
			self.gui.label("High Current Test Fail", color='red')

		return airtableMessage