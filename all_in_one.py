import airtable
from airtableScripts import airtableScripts
from datetime import date
import requests
from GUI_Class import GUI
from nfcProgramming_class import nfcProgramming
from recordCheck_class import recordCheck
from validation_class import validation
from insulation_class import insulation
from bms_class import bmsTester
from serial import *

today = date.today()
d3 = today.strftime("%m/%d/%y")
assyParts = airtable.Airtable('base ID','Assembled Parts','API key')
testInstances = airtable.Airtable('base ID','Test Instances','API key')

auth = airtable.auth.AirtableAuth('API key')
response = requests.get('https://api.airtable.com/v0/{basekey}/{table_name}', auth=auth)

airtabler = airtableScripts.airtableScripts(assyParts,testInstances,auth,response)

gui = GUI(airtabler=airtabler, title='All in one')

testingTechnician = gui.getTechnician()

while 1:
	gui.root.title("All in one")
	program = gui.optionSelectSuper(header='Choose a program', optionsText=['NFC Programming', 'Record Check', 'Validation', 'Insulation Test', 'BMS Test'])

	try:
		gui.root.title(program)
		if program == 'NFC Programming':
			nfc = nfcProgramming(gui)
			nfc.start()
		elif program == 'Record Check':
			record = recordCheck(gui)
			record.start()
		elif program == 'Validation':
			val = validation(gui, testingTechnician)
			val.start()
		elif program == 'Insulation Test':
			ins = insulation(gui, testingTechnician)
			ins.start()
		elif program == 'BMS Test':
			bms = bmsTester(gui, testingTechnician)
			bms.start()
	except Exception as e:
		try:
			#try to close connections to ports and turn off voltage output from power supplies whenever a test ends
			if program == 'NFC Programming':
				nfc.tagger.close()
			elif program == 'Insulation Test':
				ins.hiPotTester.close()
			elif program == 'BMS Test':
				bms.controlBoard.turnHVOff()
				bms.controlBoard.close()
				bms.psu.setOutputOFF()
				bms.psu.close()
		except Exception: pass		#if unable to communicate with the ports, nothing can be done
		#super quit is a unique error and indicates the user wished to change tests
		#this script only facilitates other scripts so if a script crashed and couldn't handle the exception itself then raise the error and fully crash
		if "super quit" not in str(e): raise

gui.root.mainloop()
