import tkinter as tk
import serial
import serial.tools.list_ports
import re
import os
from colorama import init, Fore
from airtableScripts import airtableScripts
from controlBoardSerialv13 import controlBoardSerialv13GUI
from requests.exceptions import *
from threading import *
import timeit

class GUI():
	def __init__(self, airtabler: airtableScripts.airtableScripts | None = None, title: str = "tk"):
		self.root = tk.Tk()
		self.mainFrame = tk.Frame(self.root)
		self.headerFrame = tk.Frame(self.root)
		self.footerFrame = tk.Frame(self.root)
		self.detailsFrame = tk.Frame(self.mainFrame)
		try:
			self.root.state('zoomed')
			self.root.iconbitmap('Ample_logo.ico')
		except Exception:
			pass
		self.root.title(title)
		self.root.bind('<Control-c>', self.quit)
		self.root.bind('<Control-C>', self.quit)
		self.root.bind('<Return>', self.clickButton)
		self._dictPack = {}
		self.temperature = 0
		self._optionNum = None
		self.msgTimer = tk.Label(self.headerFrame)
		self.airtabler = airtabler
		self._tracker = {self.getTemp: False, self.optionSelect: (), self.ansiReplace: False, self.getTechnician: False}
		self.yscroll = tk.Scrollbar(self.detailsFrame)
		self.textBox = tk.Text(self.detailsFrame, wrap=tk.WORD, yscrollcommand = self.yscroll.set)
		self.textBox_color = tk.Text(self.root)
		self.btnShowDetails = tk.Button(self.detailsFrame, text='Show details', command=lambda: self._getDetails())
		self.btnHideDetails = tk.Button(self.detailsFrame, text="Hide details", command=lambda: self._hideDetails())
		self.msgSuperOption = tk.Label(self.headerFrame)
		self._superWidgets = []
		self.headerFrame.pack(side=tk.TOP)
		self.mainFrame.pack(fill='both', expand=True)
		self.footerFrame.pack(side=tk.BOTTOM)
		self.testingSection = False
		self.techList = ['Genevieve Love']		#modified for privacy

		init()

	def quit(self, event):
		self.root.destroy()
		self.root.destroy()

	def clickButton(self, event):
		widget = self.root.focus_get()
		if isinstance(widget, tk.Button):
			widget.invoke()

	def clearScreen(self):
		#fully remove all widgets from view then repack empty structural frames
		self.clearFrame(self.root)
		self.headerFrame.pack(side=tk.TOP)
		self.mainFrame.pack(fill='both', expand=True)
		self.footerFrame.pack(side=tk.BOTTOM)

	def clearFrame(self, frame: tk.Frame = None):
		if not frame: frame = self.mainFrame
		#remove all widgets in the frame from view but don't destroy so they can be placed again without redefining
		for widget in frame.winfo_children():
			widget.pack_forget()
			#make sure buttons and text fields can be interacted with when added back in the future
			if isinstance(widget, tk.Button) or isinstance(widget, tk.Text):
				widget.configure(state=tk.NORMAL)
			#clear any subframes
			if isinstance(widget, tk.Frame):
				self.clearFrame(widget)

	def _disableCurrentButtons(self, frame: tk.Frame = None):
		if not frame: frame = self.mainFrame
		#ensure the user cannot trigger a second function after starting one
		for widget in frame.winfo_children():
			if isinstance(widget, tk.Button):
				widget.configure(state=tk.DISABLED)
			#clear sub options and related text
			if isinstance(widget, tk.Frame):
				self.clearFrame(widget)
		self.root.update()

	def label(self, text: str, name: str = '', color: str = 'black', big: bool = False, frame: tk.Frame = None):
		title = name if name else text
		#if no frame is specified and a test is in progress, assume all labels are test related, otherwise pack in main
		if not frame: 
			if self.testingSection: frame= self.resultsFrame
			else: frame = self.mainFrame
		font = ('Ariel', 12) if big else ('Ariel', 10)
		#add label to dictionary of all widgets according to its name or its text if no name given
		self._dictPack[title] = tk.Label(frame, text=text, foreground=color, font=font)
		self._dictPack[title].pack()
		#print all labels to console to preserve information in case of crash and preserve most commonly used colors for readability
		if color == 'red':
			print(Fore.RED + text + Fore.RESET)
		elif color == 'blue':
			print(Fore.CYAN + text + Fore.RESET)
		elif 'orange' in color or color == 'yellow':
			print(Fore.YELLOW + text + Fore.RESET)
		elif 'green' in color:
			print(Fore.GREEN + text + Fore.RESET)
		else:
			print(text)
		self.root.update()

	def remove_widget(self, name: str):
		#remove a widget by name, ignore if name does not exist in the dictionary
		try:
			self._dictPack[name].pack_forget()
			del self._dictPack[name]
		except KeyError:
			pass

	#most buttons in this class will trigger this function which will tell already running functions which button was clicked and how to proceed
	#since many scripts use this class differently, buttons won't always lead to the same next step
	def _buttonCheck(self, _option: str):
		self._optionNum = _option	#update the tracked class variable with the string of the associated button

	def getTemp(self) -> int:
		self._optionNum = None
		self.tempFrame = tk.Frame(self.mainFrame)
		self.tempFrame.pack()
		ambientTemperatureEntry = tk.Entry(self.tempFrame)

		self._tracker[self.getTemp] = True		#note that current test uses entered temperature value, allow users to change value b/w tests
		self.label(text="Enter Ambient Temperature", color='blue', frame=self.tempFrame)
		btnTempCont = tk.Button(self.tempFrame, text="OK", command=lambda: self._buttonCheck('Temp Confirm'))
		ambientTemperatureEntry.pack(pady=10)
		btnTempCont.pack()
		ambientTemperatureEntry.focus_set()		#allow users to type without clicking on the entry field

		#wait for user to click OK or Change Test (quit from current test)
		while self._optionNum != 'Temp Confirm' and self._optionNum != 'quit':
			self.root.update()

		if self._optionNum == 'quit':
			self._optionNum = None
			raise Exception("super quit")		#unique error to return to test selection screen
		self._optionNum = None
		self._disableCurrentButtons(self.tempFrame)		#user has clicked OK, prevent double click
		try:
			self.temperature = int(ambientTemperatureEntry.get())
			self.tempFrame.destroy()
			return self.temperature
		except ValueError:		#prevent non integer entries, reset temperature frame
			self.tempFrame.destroy()
			self.temperature = self.getTemp()
			return self.temperature

	def getTime(self, default: int | float = 0) -> float:
		self._optionNum = None
		self.timeFrame = tk.Frame(self.mainFrame)
		self.timeFrame.pack()
		timeEntry = tk.Entry(self.timeFrame)

		#allow for a default amount of time to be displayed to users
		self.label(text="Enter Duration" + (" (Default: " + str(default) + ")") if default else '', color='blue', frame=self.timeFrame)
		btnTimeCont = tk.Button(self.timeFrame, text="OK", command=lambda: self._buttonCheck('Time Confirm'))
		timeEntry.pack(pady=10)
		btnTimeCont.pack()
		timeEntry.focus_set()		#allow users to type wihtout clicking on the entry field

		#wait for user to click OK or Change Test (quit from current test)
		while self._optionNum != 'Time Confirm' and self._optionNum != 'quit':
			self.root.update()

		if self._optionNum == 'quit':
			self._optionNum = None
			raise Exception("super quit")		#unique error to return to test selection screen
		self._optionNum = None
		self._disableCurrentButtons(self.timeFrame)		#user has clicked OK, prevent double click
		try:
			time = float(timeEntry.get())
			self.timeFrame.destroy()
			return time
		except ValueError:			#prevent non float entries, reset time frame
			self.timeFrame.destroy()
			time = self.getTime(default=default)
			return time

	def getVoltage(self, component: str = 'stack') -> float:
		self._optionNum = None
		self.voltageFrame = tk.Frame(self.mainFrame)
		self.voltageFrame.pack()
		voltageEntry = tk.Entry(self.voltageFrame)

		self.label(text="Enter desired " + component + " voltage", color='blue', frame=self.voltageFrame)
		btnVoltageCont = tk.Button(self.voltageFrame, text="OK", command=lambda: self._buttonCheck('Voltage Confirm'))
		voltageEntry.pack(pady=10)
		btnVoltageCont.pack()
		voltageEntry.focus_set()		#allow users to type without clicking on the entry field

		#wait for user to click OK or Change Test (quit to test selection)
		while self._optionNum != 'Voltage Confirm' and self._optionNum != 'quit':
			self.root.update()

		if self._optionNum == 'quit':
			raise Exception("super quit")		#unique error to return to test selection screen
		self._optionNum = None
		self._disableCurrentButtons(self.voltageFrame)		#user has clicked OK, prevent double click
		try:
			voltage = float(voltageEntry.get())
			self.voltageFrame.destroy()
			return voltage
		except ValueError:		#prevent non float entries, reset voltage frame
			self.voltageFrame.destroy()
			voltage = self.getVoltage()
			return voltage

	def getTechnician(self) -> str:
		self._tracker[self.getTechnician] = True		#this test logs which user is testing, allow users to "log out" b/w tests
		self._optionNum = None
		self.techFrame = tk.Frame(self.mainFrame)
		self.techFrame.pack()
		technicianNameEntry = tk.Entry(self.techFrame)

		self.label(text="Scan Badge QR", color='blue', frame=self.techFrame)
		btnTechCont = tk.Button(self.techFrame, text="OK", command=lambda: self._buttonCheck('Tech Confirm'))
		technicianNameEntry.pack(pady=10)
		btnTechCont.pack()
		technicianNameEntry.focus_set()		#allow users to type without clicking on the entry field

		#wait for user to click OK or Change Test (quit from current test)
		while self._optionNum != 'Tech Confirm' and self._optionNum != 'quit':
			self.root.update()

		if self._optionNum == 'quit':
			raise Exception("super quit")		#unique error to return to test selection
		self._optionNum = None
		self._disableCurrentButtons(self.techFrame)		#user has clicked OK, prevent double click
		self.technician = technicianNameEntry.get()
		if self.technician in self.techList:	#check that entered string is a valid name in technician list, otherwise restart tech frame
			self.techFrame.destroy()
			return self.technician
		else:
			self.techFrame.destroy()
			self.technician = self.getTechnician()
			return self.technician

	def trackPorts(self, waitFor: str):
		intendedChange = False
		self.initialPorts = serial.tools.list_ports.comports()
		initialPortCount = len(self.initialPorts)
		while not intendedChange and self._optionNum != 'quit':
			#wait for the number of connected COM ports to change or for user to click Change Test (quit from current test)
			while len(serial.tools.list_ports.comports()) == initialPortCount and self._optionNum != 'quit':
				self.root.update()
			self.wait(0.2)
			#if waiting for more ports and new port is available, return to original function
			if len(serial.tools.list_ports.comports()) > initialPortCount and waitFor == 'more': intendedChange = True
			elif len(serial.tools.list_ports.comports()) < initialPortCount and waitFor == 'less': intendedChange = True
			else:
				#if test is waiting for more ports and a port is removed, update list and number of current ports and keep waiting for new connection and vice versa
				self.initialPorts = serial.tools.list_ports.comports()
				initialPortCount = len(self.initialPorts)
		if self._optionNum == 'quit':
			self._optionNum = None
			raise Exception('super quit')		#unique error to return to test selection

	def wait_for_plug_in(self, includeLabel: bool = True) -> str:
		self._optionNum = None
		self.plugFrame = tk.Frame(self.mainFrame)
		self.plugFrame.pack()
		if includeLabel: self.label(text="Plug in USB Cable!", color="blue", frame=self.plugFrame)
		self.trackPorts(waitFor='more')

		#check list of current ports against list of previously connected ports to find new connection
		ports = serial.tools.list_ports.comports()
		for i in range(len(self.initialPorts)):
			if self.initialPorts[i] in ports:
				ports.remove(self.initialPorts[i])
		port, desc, hwid = ports[0]
		print("{}: {} [{}]".format(port, desc, hwid))
		COMPort = format(port)
		self.plugFrame.destroy()
		return COMPort		#return new port COM number

	def wait_for_unplug(self):
		self.plugFrame = tk.Frame(self.mainFrame)
		self.plugFrame.pack()
		self.label(text="Unplug USB Cable!", color='blue', frame=self.plugFrame)
		self.trackPorts(waitFor='less')
		self.plugFrame.destroy()

	def findOpenPorts(self):
		self.COMports = []
		self.portNum = []
		self.availablePorts = 0
		self.btnCOMs = []
		
		#find ports not in use, if none available, wait for one to become available or new port to appear
		while self.availablePorts == 0 and self._optionNum != 'quit':
			ports = serial.tools.list_ports.comports()
			#for each port, just try connecting to it, if its in use catch error and move on
			for port, desc, hwid in sorted(ports):
				try:
					tempPort = controlBoardSerialv13GUI.controlBoardv13_maxim(str(port), self)
					tempPort.receiveSerial(delay=0)
					tempPort.close()
				except serial.SerialException:
					continue
				self.COMports.append((port + ": " + desc + " [" + hwid + "]"))
				self.portNum.append(port)
			self.root.update()
			self.availablePorts = len(self.portNum)
		if self._optionNum == 'quit':
			self._optionNum = None
			raise Exception("super quit")		#unique error to return to test selection

	def displayAvailablePorts(self):
		#make a button for each available port with the port information displayed on the button for users to choose from
		self.label(text="Choose COM port", frame=self.portFrame)
		for i in range(self.availablePorts):
			self.btnCOMs.append(tk.Button(self.portFrame, text=self.COMports[i], command=lambda i=i: self._buttonCheck(_option=self.portNum[i])))
			self.btnCOMs[i].pack(pady=5)
		self.btnCOMs[0].focus_set()

		btnRefresh = tk.Button(self.portFrame, text="Refresh options", command = lambda: self._buttonCheck('Refresh'))
		btnRefresh.pack(side=tk.BOTTOM, pady=20)

	def portAssign(self) -> str:
		self._optionNum = None
		self.portFrame = tk.Frame(self.mainFrame)
		self.portFrame.pack()

		#assume no ports available to start, this text will disappear as soon as open ports are found
		self.label(text="No available COM Ports. \nPlug in USB Cable.", frame=self.portFrame)
		self.findOpenPorts()

		self.clearFrame(self.portFrame)

		self.displayAvailablePorts()

		#wait for user to choose an available port, click the refresh button if they don't see the port they're looking for, or click Change Test (quit to test selection)
		while (self._optionNum not in self.portNum) and (self._optionNum != 'Refresh') and self._optionNum != 'quit':
			self.root.update()
		if self._optionNum == 'quit':
			self._optionNum = None
			raise Exception("super quit")		#unique error to return to test selection

		self._disableCurrentButtons(self.portFrame)		#user has picked a port or selected refresh, prevent choosing other port

		if self._optionNum == 'Refresh':		#if refresh, reset port frame to display new list of available ports
			self._optionNum = None
			self.portFrame.destroy()
			self.portAssign()
		else:
			COMPort = self._optionNum
			self._optionNum = None
			self.portFrame.destroy()
			return COMPort

	def continueButton(self, frame: tk.Frame = None):
		if not frame: frame = self.footerFrame
		self._optionNum = None
		#always display at the bottom but will affect whatever frame is passed
		btnContinue = tk.Button(self.footerFrame, text="Continue", command=lambda: self._buttonCheck("End Loop"))
		btnContinue.pack(side=tk.BOTTOM, pady=20)
		btnContinue.focus_set()
		#wait for user to click continue or Change Test (quit to test selection)
		while self._optionNum != "End Loop" and self._optionNum != 'quit':
			self.root.update()
		self._disableCurrentButtons(frame)		#user has clicked continue, prevent double click
		self.clearFrame(frame)		#clear frame continue button is in, if in footer, any test results on screen will not be cleared
		try:
			self.skipFrame.destroy()
		except Exception: pass
		if self._optionNum == 'quit':
			self._optionNum = None
			raise Exception("super quit")		#unique error to return to test selection
		self._optionNum = None

	def restartButton(self, showButton: bool = True):
		if self._tracker[self.ansiReplace]:		#if there is test data in the text box, give the user the option to view it
			self.detailsFrame.pack(fill='both', expand=True)
			self.btnShowDetails.pack(pady=5)
		if showButton: self.continueButton()	#showButton arg determines if user manually restarts test or if test restarts automatically
		try:
			self.resultsFrame.destroy()
		except Exception: pass
		#fully clear off all widgets, empty text boxes, make labels default to main frame again, and return to initial GUI state
		self.clearScreen()
		self.textBox.delete('1.0', tk.END)
		self.textBox_color.delete('1.0', tk.END)
		self.placeSupers()
		self.testingSection = False

	def askSerial(self, _invalid: bool = False):
		self.serialEntry = tk.Entry(self.serialFrame)
		btnValid = tk.Button(self.serialFrame, text="OK", command = lambda: self._buttonCheck('Confirm Serial'))
		self.label(text="Enter Top Assembly", color='blue', frame=self.serialFrame)
		self.label(text="Make sure everything is plugged in!", color='orange', frame=self.serialFrame)
		if _invalid:		#if this function is being rerun after an invalid serial number is entered
			self.serialEntry.delete(0, tk.END)
			self.label("Please enter a valid serial number", name='Reserial', color='orange red', frame=self.serialFrame)
		self.serialEntry.pack(pady=5)
		btnValid.pack(pady=5)
		self.serialEntry.focus_set()		#allow users to type without clicking on the entry field

	def addTrackedOptions(self):
		#allow users to change previously selected/entered variables b/w tests
		multiTrack = False
		if self._tracker[self.getTemp]:
			multiTrack = True
			msgCurrentTemp = tk.Label(self.serialFrame, text="Current Tempertaure: " + str(self.temperature) + u'\N{DEGREE SIGN}' + " C")
			msgCurrentTemp.pack(pady=5)
			btnChangeTemp = tk.Button(self.serialFrame, text="Change Temperature", command = lambda: self._buttonCheck('Temperature'))
			btnChangeTemp.pack()
		if self._tracker[self.optionSelect]:
			multiTrack = True
			msgCurrentSelect = tk.Label(self.serialFrame, text="Current Selection: " + self.savedSelection)
			msgCurrentSelect.pack(pady=5)
			btnReselect = tk.Button(self.serialFrame, text="Change Selection", command = lambda: self._buttonCheck('Option'))
			btnReselect.pack()
		if self._tracker[self.getTechnician]:
			#if multiple variables available to be changed, add extra space for readability
			if multiTrack:
				msgCurrenTechnician = tk.Label(self.serialFrame, text="\nCurrent Technician: " + self.technician)
			else:
				msgCurrenTechnician = tk.Label(self.serialFrame, text="Current Technician: " + self.technician)
			msgCurrenTechnician.pack(pady=5)
			btnLogout = tk.Button(self.serialFrame, text="Logout", command = lambda: self._buttonCheck('Logout'))
			btnLogout.pack()

	def serial_determineNextPath(self) -> bool:
		#check if the user wished to update any of the available tracked options
		#if so, make sure the GUI returns to the serial entry screen and not to the testing script
		restartSerial = True
		if self._optionNum == 'quit':
			self._optionNum = None
			raise Exception("super quit")		#unqiue error to return to test selection
		elif self._optionNum == 'Temperature':
			self._optionNum = None
			self.root.update()
			self.serialFrame.destroy()
			self.getTemp()		#redo temperature entry
		elif self._optionNum == 'Option':
			self._optionNum = None
			self.serialFrame.destroy()
			self.root.update()		#redo option selection
			self.optionSelect(*self._tracker[self.optionSelect])
		elif self._optionNum == 'Logout':
			self._optionNum = None
			self.serialFrame.destroy()
			self.root.update()
			self.getTechnician()		#redo technician entry
		else: restartSerial = False
		self._optionNum = None
		return restartSerial		#tell serial entry function if serial screen needs to be setup again

	def getSerial(self, _invalid: bool = False) -> str:
		self.rawSerial = ''
		self.serialNumber = ""
		self.serialFrame = tk.Frame(self.mainFrame)
		self.serialFrame.pack()

		self.askSerial(_invalid)
		self.addTrackedOptions()
		#wait for user to click OK, change an option, or quit to test selection
		while self._optionNum not in ['Confirm Serial', 'Option', 'Temperature', 'Logout', 'quit']:
			self.root.update()
		self._disableCurrentButtons(self.serialFrame)		#user has clicked a button, prevent clicking a different one
		if self.serial_determineNextPath():		#function return says if serial entry frame needs to be resetup
			self.serialFrame.destroy()
			self.getSerial()
			return self.serialNumber		#return here as full function has already been run
		self._cleanUpSerial(self.serialEntry.get())
		if self.airtabler: self._checkSerialNum(self.rawSerial)		#if connected to Airtable database, make sure serial number exists
		else:
			self.clearScreen()
			#make a label of the entered serial number in the header so its clear which unit the results are for if the unit is removed after the test
			self.label(("SN: " + self.rawSerial), big=True, frame=self.headerFrame)
			self.serialNumber = self.rawSerial
		self.serialFrame.destroy()
		#create new frame to separate out any labels about test results from other GUI elements and make that the default location for new labels
		self.testingSection = True
		self.resultsFrame = tk.Frame(self.mainFrame)
		self.resultsFrame.pack(fill='x')
		return self.serialNumber

	def _checkSerialNum(self, serialNum: str, _canHTTP: bool = True):
		self._optionNum = None
		try:
			#ping Airtable once in case search fails when initially connecting to database
			self.airtabler._isRecordPresent(serialNum)
			if self.airtabler._isRecordPresent(serialNum):
				self.clearScreen()
				#make a label of the entered serial number in the header so its clear which unit the results are for if the unit is removed after the test
				self.label(("SN: " + serialNum), big=True, frame=self.headerFrame)
				self.serialNumber = serialNum		#serial number is good, make it the more permanent variable
			else:
				#serial is not valid, ask user for new entry
				self.serialFrame.destroy()
				self.getSerial(True)
		except (ConnectionError, HTTPError) as e:		#handle errors connecting to the database
			self.clearFrame()
			print(e)
			msgConnection = tk.Label(self.serialFrame, text="Could not connect to Airtable. \nCheck internet connection and try again.")
			msgHTTP = tk.Label(self.serialFrame, text="Server error encountered. Wait a moment and try again.")
			btnTryAgain = tk.Button(self.serialFrame, text="Try Again", command=lambda: self._buttonCheck(serialNum))
			if ("it is safe to retry" in e) and _canHTTP:		#auto rerun certain HTTP errors the first time they appear
				self._checkSerialNum(serialNum, False)
				return
			elif "HTTPError" in e:
				msgHTTP.pack(pady=10)
			else:
				msgConnection.pack(pady=10)
			btnTryAgain.pack()
			btnTryAgain.focus_set()
			#wait for user to click Try Again or Change Test (quit to test selection)
			while self._optionNum not in [serialNum, 'quit']:
				self.root.update()
			if self._optionNum == 'quit':
				self._optionNum = None
				raise Exception("super quit")		#unique error to return to test selection
			self._optionNum = None
			self._disableCurrentButtons(frame=self.serialFrame)		#user has clicked Try Again, prevent double click
			#only try again once before going back to serial entry screen so user isn't trapped on try again screen
			if _canHTTP: self._checkSerialNum(serialNum, False)
			else:
				self.serialFrame.destroy() 
				self.getSerial(True)
		except IndexError:		#if serial number format is wrong, _isRecordPresent will throw this error so ask user to reenter
			self.serialFrame.destroy()
			self.getSerial(True)

	def _cleanUpSerial(self, serialNumber: str):
		#remove product order (PO) numbers which can pre or proceed and be separated by a space or :
		serialNumber = re.sub(r'[:\s]?PO-\d{4}[:\s]?', '', serialNumber).upper()
		#remove any leading zeros
		self.rawSerial = re.sub(r'-0+', '-', serialNumber)

	def makeButtons(self, buttonsText: list[str], frame: tk.Frame = None):
		#create and pack buttons for every string in a list
		if not frame: frame = self.mainFrame
		btnList = []
		for  i in range(len(buttonsText)):
			btnList.append(tk.Button(frame, text=buttonsText[i], command = lambda i=i:self._buttonCheck(_option=buttonsText[i])))
			btnList[i].pack(pady=5)
		btnList[0].focus_set()

	def optionSelect(self, header: str = '', optionsText: list[str] = ['Option 1'], reask: bool = False) -> str:
		#take a list of strings and setup buttons for each string and return the string of whichever button is clicked
		self._optionNum = None
		self.optionFrame = tk.Frame(self.mainFrame)
		self.optionFrame.pack()
		#save these options and allow the user to repick between tests
		if reask: self._tracker[self.optionSelect] = (header, optionsText, reask)
		if header:		#optional preamble text for the buttons
			self.label(text=header, frame=self.optionFrame)

		self.makeButtons(optionsText, frame=self.optionFrame)
		#wait for user to choose an option or click Change Test (quit to test selection)
		while self._optionNum not in optionsText and self._optionNum != 'quit':
			self.root.update()
		if self._optionNum == 'quit':
			self.optionFrame.destroy()
			self._optionNum = None
			raise Exception("super quit")		#unique error to return to test selection
		
		self._disableCurrentButtons(self.optionFrame)		#user chose an option, prevent choosing a different one
		selection = self._optionNum
		#if users can change this b/w tests, save what is currently chosen so they know what is already selected
		if reask: self.savedSelection = selection
		self._optionNum = None
		self.optionFrame.destroy()
		return selection
	
	def optionSelectSuper(self, header: str = '', optionsText: list[str] = ['Option 1']) -> str:
		#test selection menu, resets all trackers since the previous test is no longer active
		self._optionNum = None
		self._tracker = {self.getTemp: False, self.optionSelect: (), self.ansiReplace: False, self.getTechnician: self._tracker[self.getTechnician]}
		self.clearScreen()
		if header:		#optional preamble text to option buttons
			self.label(text=header)

		self.makeButtons(optionsText)
		#wait for user to choose a test, quit is not an option since already in test selection menu
		while self._optionNum not in optionsText:
			self.root.update()
		self._disableCurrentButtons()		#user selected a test, prevent clicking another
		selectionSuper = self._optionNum
		self._optionNum = None
		#label to tell user which test is currently selected since serlial entry screen is the same for all
		self.msgSuperOption = tk.Label(self.headerFrame, text="Current Test: " + selectionSuper, font=('Ariel', 12))
		self.placeSupers()
		return selectionSuper
	
	def placeSupers(self):
		#add the Change Test button and current test label if applicable
		#since this function is always called by restart button but some scripts have singular purposes, skip if not applicable
		if self.msgSuperOption['text']:
			self.clearScreen()
			btnChangeSuper = tk.Button(self.footerFrame, text="Change Test", command = lambda: self._buttonCheck('quit'))
			self.msgSuperOption.pack(pady=5)
			btnChangeSuper.pack(pady=20)
			btnChangeSuper.lower()		#always be the lowest thing in the footer frame
			self._superWidgets = [self.msgSuperOption, btnChangeSuper]
	
	def skipButton(self, side=tk.RIGHT):
		#button for skipping a section of a test. individual scripts handle what happens if this button is clicked
		self.skipFrame = tk.Frame(self.resultsFrame)
		self.skipFrame.pack(side=side)
		skipButton = tk.Button(self.skipFrame, text='Skip', command = lambda: self._buttonCheck('quit'))
		skipButton.pack(padx=200, pady=200)

	def _timer(self, count: int | float):
		#timer that can take handle int or float and will only display float
		#use time package to ensure that the timer will always subtract the correct amount of time from the initial even if other processes slow down GUI updating
		self.msgTimer['text']= int(count-(timeit.default_timer()-self.initialTime)) + 1
		self.root.update()
		if self.msgTimer['text'] > 0:
			#use after function since it doesn't stop/interupt other functions
			#storing the return object allows the script to remove an after action from queue once timer is up
			self.timer_obj = self.root.after(100, self._timer, count)
				
	def test_in_progress(self, HV: bool = False, testLength: int | float = 0, testName: str = ''):
		self.test_over()		#remove any previous test section labels/timers
		self.testingFrame = tk.Frame(self.headerFrame)
		self.testingFrame.pack()
		if HV:		#add danger label when applicable
			self._dictPack['msgDanger'] = tk.Label(self.testingFrame, text="DANGER HIGH VOLTAGE", foreground = "red", font=('Ariel',15))
			self._dictPack['msgDanger'].pack()
		if testName:		#add label of test name if provided
			self.label(text=("Running: " + testName), name='Testing', color='orange', frame=self.testingFrame)
		if testLength:		#add timer if length of the test is known
			self.initialTime = timeit.default_timer()
			self.msgTimer = tk.Label(self.testingFrame)
			self.msgTimer.pack()
			self._timer(testLength)

	def test_over(self):
		#get rid of HV, test in progress, timer labels and remove after object from queue, do nothing if they don't exist
		try:
			self.testingFrame.destroy()
		except AttributeError: 
			pass
		try:
			self.root.after_cancel(self.timer_obj)
		except AttributeError:
			pass
		self.root.update()

	def resultsUpload(self, testName: str, deviceUnderTest: str, result: str, testData: str, equipment: str = None, testData1: float = None, testData2: float = None, testData3: float = None, testData4: float = None, testData5: float = None, testData6: float = None, failureType: list[str] = None, _canHTTP: bool = True):
		try:
			self.airtabler.createTestInstance_GUI(testName, deviceUnderTest, result, testData, equipment, testData1, testData2, testData3, testData4, testData5, testData6, failureType)
		except (ConnectionError, HTTPError) as e:		#catch errors if can't connect to database
			if ("it is safe to retry" in e) and _canHTTP:		#auto rerun certain HTTP errors the first time they occur
				self.resultsUpload(testName, deviceUnderTest, result, testData, equipment, testData1, testData2, testData3, testData4, testData5, testData6, failureType, _canHTTP=False)
			else:		#otherwise use alternate upload function that will save JSON file of results to upload later
				self.airtabler.createTestInstance(testName, deviceUnderTest, result, testData, equipment, testData1, testData2, testData3, testData4, testData5, testData6, failureType)
		self.remove_widget('Nothing left to upload')
		self.remove_widget('Failed Uploads')
		#check if any files have failed to upload and tell user to use sniffer to upload them when possible
		fails = os.listdir("failed_upload")
		if len(fails) == 0:
			self.label(text='Nothing left to upload', color='dark green')
		else:
			self.label(text=('Failed upload records: ' + str(len(fails)) + '\nRun sniffer.py to upload soon'), name='Failed Uploads', color='dark orange')

	def ansiReplace(self, text: str) -> str:
		#get colored text in CMD required placing ANSI escape characters around the text but make regular strings hard to read
		#any text passed to this function will have the ANSI characters removed and placed in Tkinter text box with color tags that don't show up in the string variable
		#this allows for text to be viewed in color in the GUI but uploaded to Airtable as a simple string
		self.textBox.insert(tk.END, text)
		self._tracker[self.ansiReplace] = True		#if this function is called, add the Show Details button at the end of the test

		#list of partial ANSI characters that surround sections of string (first code corresponds to text color, \[0m is the clear formatting code)
		#the true escape characters are difficult to search for but always precede the rest of the color/format codes so can be dealth with whenever the rest of the code is found
		ansiColors = [r'\[30m.*?\[0m', r'\[31m.*?\[0m', r'\[32m.*?\[0m', r'\[33m.*?\[0m', r'\[34m.*?\[0m', r'\[35m.*?\[0m', r'\[36m.*?\[0m', r'\[37m.*?\[0m']
		ansiFormats = ['[0m', '[1m', '[4m', '[7m']		#ANSI formatting codes for clear format, bold, italics, and underline
		ansiColorLen = 5		#total number of characters for ANSI color codes (1 + [3xm)

		#create Tk textbox tags that correspond to the ANSI color codes
		self.textBox.tag_config('0', foreground='black')
		self.textBox.tag_config('1', foreground='red')
		self.textBox.tag_config('2', foreground='dark green')	
		self.textBox.tag_config('3', foreground='dark orange')		
		self.textBox.tag_config('4', foreground='blue')
		self.textBox.tag_config('5', foreground='magenta')
		self.textBox.tag_config('6', foreground='cyan')
		self.textBox.tag_config('7', foreground='white')

		countVar = tk.IntVar()

		#for each ANSI color code, find any matches, add the corresponding texbox color tag then remove the escape characters and ANSI codes
		for color in range(len(ansiColors)):
			idx = '1.0'		#start at the beginning for each color
			while 1:
				#get index of first match for ANSI color code and length of match from color code to clear formatting code (smallest possible full match)
				idx = self.textBox.search(ansiColors[color], idx, stopindex=tk.END, count=countVar, regexp = True)		#search from where last ANSI code instance was found to the end of the string
				if not idx: break		#if no more matches, go to next color
				lastidx = '%s + %sc' % (idx, countVar.get())
				self.textBox.tag_add(str(color), idx, lastidx)		#tag appropriet text
				idx = '%s - %dc' % (idx, 1)		#set start index back one character to include escape character that was not searched for
				ansiOnlyidx = '%s + %dc' % (idx, ansiColorLen)		#set new end index for just the ANSI code
				self.textBox.delete(idx, ansiOnlyidx)		#delete the preceding ANSI code (clear formatting code will be handled separately)

		#for each formating code, find all instances and delete, these are not replicated in the textbox and thus no tag needed for affected text
		for format in range(len(ansiFormats)):
			idx = '1.0'		#start at the beginning for each format code
			while 1:
				#get index of first instance of ANSI format code
				idx = self.textBox.search(ansiFormats[format], idx, stopindex=tk.END)		#search from where last ANSI code instance was found to the end of the string
				if not idx: break		#if no more matches, go to next format
				lastidx = '% s+% dc' % (idx, len(ansiFormats[format]))		#set last index based on length of format code
				idx = '% s-% dc' % (idx, 1)		#set start index back one character to include escape character that was not searched for
				self.textBox.delete(idx, lastidx)		#delete format code

		self.textBox.insert(tk.END, '\n')		#add newline at the end in case more text is added later

		return self.textBox.get('1.0', tk.END)		#return new string with no ANSI codes
	
	def colorSwap(self, text: str, red: list[str] = [], yellow: list[str] = [], green: list[str] = [], blue: list[str] = []) -> str:
		#this function takes an ANSI coded string and replaces the color codes of specific strings based on the arg lists
		#edited ANSI coded string is printed to CMD and returned as is to be interpreted by ansiReplace and placed and the textbox that can be viewed by the user
		colors = locals()		#create a list of the args for easy looping
		self.textBox_color.insert(tk.END, text)		#insert full string into the textbox
		ansiCode = None
		for color in list(colors.keys()):
			#for each list in the args, check that the list is not empty and set the appropriet ANSI color code
			if (color == 'red') and colors['red']: ansiCode = '[31m'
			elif (color == 'yellow') and colors['yellow']: ansiCode = '[33m'
			elif (color == 'green') and colors['green']: ansiCode = '[32m'
			elif (color == 'blue') and colors['blue']: ansiCode = '[34m'

			if ansiCode:		#if the current list is not empty
				for i in range(len(colors[color])):
					#for each string in the arg list, find the stirng in the text regardless of what ANSI color code it currently has
					regex = r'\[3[0-9]m\s*' + re.escape(colors[color][i])		#full string to search for starts with existing ANSI code, escape any special characters in the arg string
					idx = self.textBox_color.search(regex, '1.0', stopindex=tk.END, regexp=True)		#search from beginning to end as the strings in the arg list may not be in order for the full text
					if not idx: continue		#if unable to match the string from the arg, ignore and go to the next
					postIdx = idx + '+4c'		#set index for the end of the ANSI code (4 characters past the start)
					self.textBox_color.delete(idx, postIdx)		#delete the existing color code (don't touch escape character)
					self.textBox_color.insert(idx, ansiCode)	#add new color code in the place of the old one reusing the existing escape character
			ansiCode = None		#set ansiCode back to none in case next arg list is empty
		
		print(self.textBox_color.get('1.0', tk.END))		#print recolored full text to CMD
		return self.textBox_color.get('1.0', tk.END)		#return recolored text with ANSI codes still embedded
	
	def _getDetails(self):
		#displays the textbox from ansiReplace and adds a hide details button to remove it
		self.clearFrame(self.detailsFrame)
		self.btnHideDetails.pack(pady=5)
		self.yscroll.config(command = self.textBox.yview)
		#expand textbox to fill whatever space is available after test result labels
		#pack textbox and scrollbar as left aligned with no x axis margins between them so the scrollbar looks like part of the textbox
		self.textBox.pack(fill='both', expand=True, padx=(30, 0), pady=20, side=tk.LEFT)
		self.yscroll.pack(side=tk.LEFT, fill='y', padx=(0, 15), pady=20)		#even though scrollbar is left aligned, since it's packed after the textbox, it will show up to the right of it
		self.textBox['yscrollcommand'] = self.yscroll.set
		self.yscroll.focus_set()		#set the scrollbar as the focus so scrollwheel/mousepad will automatically scroll the textbox
		self.textBox.config(state=tk.DISABLED)		#disable editing in the textbox since its the data from the test

	def _hideDetails(self):
		#remove textbox from the screen and readd the Show Details button
		self.clearFrame(self.detailsFrame)
		self.btnShowDetails.pack(pady=5)
		self.btnShowDetails.focus_set()

	def wait(self, seconds):
		#GUI friendly time.sleep that will prevent other processes from continuing for the allotted time but lets on screen timers keep counting down
		start = timeit.default_timer()
		while (timeit.default_timer() - start) < seconds:
			self.root.update()
