import time
from colorama import Fore
from controlBoardSerialv13 import controlBoardSerialv13GUI
from GUI_Class import GUI
from itech import itech

class cblog():
	def __init__(self, gui: GUI, controlBoard: controlBoardSerialv13GUI.controlBoardv13_maxim, battpsu: itech.itech, buspsu: itech.itech):
		self.gui = gui
		self.controlBoard = controlBoard
		self.battpsu = battpsu
		self.buspsu = buspsu

	def cblog(self, testmode: str, cycle: int = 0, result: str = '--', printout: bool = False) -> tuple[float, float, float, list[float], str]:
			logwrite = []
			bmVoltage, busVoltage, current, controlBoardTemperatures = self.controlBoard.getDetails_cblog()		#get CM measurements
			cbFlags = self.controlBoard.getBMFlags()																#get CM state info (HV/SC)
			battpsuVoltage, battpsuCurrent = self.battpsu.getVoltageAndCurrent()									#get batt ITECH voltage and current
			buspsuVoltage, buspsuCurrent = self.buspsu.getVoltageAndCurrent()										#get bus ITECH voltage and current
			
			#log all the data in a list format that will be printed and saved to airtable
			if testmode != 'CAN Test' or testmode != 'Maxim Test':
				logwrite.append(int(time.time()))
				logwrite.append(bmVoltage)
				logwrite.append(busVoltage)
				logwrite.append(current)
				logwrite.append(controlBoardTemperatures)
				logwrite.append(cbFlags['atus'])
				logwrite.append(cbFlags['ShortCircuit'])
				logwrite.append(testmode)
				logwrite.append(cycle)
				logwrite.append(result)
				logwrite.append(battpsuVoltage)
				logwrite.append(buspsuVoltage)
				logwrite.append(battpsuCurrent)
				logwrite.append(buspsuCurrent)
			else:
				logwrite.append(testmode)
				logwrite.append(cycle)	
				logwrite.append(result)

			#print info to cmd and make GUI labels when appropriate
			if result == 'Pass':
				if printout: self.gui.label(testmode+' '+result, color='dark green')
				else: print(Fore.GREEN + testmode + ' ' + result + Fore.RESET)
			elif result == 'Fail':
				if printout: self.gui.label(testmode+' '+result, color='red')
				else: print(Fore.RED + testmode + ' ' + result + Fore.RESET)
			print(logwrite)

			#add log to airtable data
			airtableMessage = str(logwrite) + '\n'

			return bmVoltage, busVoltage, current, controlBoardTemperatures, airtableMessage