#! /usr/bin/env python

# Main webrtc test tool
#
# TODOs:
#
# - Fix the unprovisioning functionality also remove the Restcomm Clients and Restcomm Number
# - Make accountSid and authToken not required since we have introduced the --test-modes where we can configure if we want provisioning to take place or not 
#

import argparse
import sys
import json
import time
import ssl
import subprocess 
import os 
import re
import urllib
import urlparse
import signal
import datetime
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from socket import *
from threading import Thread

# Notice that we are using the dummy module which is implemented with threads,
# not multiple processes, as processes might be overkill in our situation (in
# case for example we want to spawn hundredths)
#
# To use multiple processes instead we should  use:
# import multiprocessing
# And replace ThreadPool with Pool
from multiprocessing.dummy import Pool as ThreadPool

# Selenium imports
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
import selenium.common.exceptions

# Globals
# Version
VERSION = "0.3.4"
# TAG for console logs
TAG = '[restcomm-test] '
# Keep the nodejs process in a global var so that we can reference it after the tests are over to shut it down
httpProcess = None
# Used in non-selenium runs
browserProcesses = list()
# restcomm test modes. Which parts of the tool do we want executed (bitmap):
# - 001: Spawn webrtc browsers
# - 010: Start HTTP server for external service & web app
# - 100: Do Restcomm provisioning/unprovisioning
testModes = None
# Command line args
args = None
# list containing a dictionary for each webrtc client browser we are spawning
clients = None
# number of browsers spawned so far
totalBrowserCount = 0
# log index
logIndex = 0

def threadFunction(dictionary): 
	try:
		print TAG + 'browser thread #' + str(dictionary['id']) + ' Running test for URL: ' + dictionary['url']

		chromeOptions = Options()
		# important: don't request permission for media
		chromeOptions.add_argument("--use-fake-ui-for-media-stream")
		# enable browser logging
		caps = DesiredCapabilities.CHROME
		#caps['loggingPrefs'] = {'browser': 'ALL', 'client': 'ALL', 'driver': 'ALL', 'performance': 'ALL', 'server': 'ALL'}
		caps['loggingPrefs'] = { 'browser':'ALL' }
		#driver = webdriver.Chrome(chrome_options = chromeOptions, desired_capabilities = caps, service_args = ["--verbose", "--log-path=chrome.log"])
		driver = webdriver.Chrome(chrome_options = chromeOptions, desired_capabilities = caps)

		# navigate to web page
		driver.get(dictionary['url'])
		#print driver.title

		#print 'Waiting for condition to be met'
		#WebDriverWait(driver, 30).until(expected_conditions.text_to_be_present_in_element((By.ID,'log'), 'Connection ended'))
		# this is actually a hack to keep the browser open for n seconds. Putting the thread to sleep doesn't work and so far I haven't found a nice way to do that in Selenium
		WebDriverWait(driver, 300).until(expected_conditions.text_to_be_present_in_element((By.ID,'log'), 'Non existing text'))
		

	except selenium.common.exceptions.TimeoutException as ex:
		print TAG + 'EXCEPTION: browser thread #' + str(dictionary['id']) + ' Test timed out'
	except:
		print TAG + 'EXCEPTION: browser thread #' +  str(dictionary['id']) + ' Unexpected exception: ', sys.exc_info()[0]
		return

	# print messages
	print TAG + 'browser thread #' + str(dictionary['id']) + ' Saving the logs'
	logBuffer = ''
	for entry in driver.get_log('browser'):
		# entry is a dictionary
		logBuffer += json.dumps(entry, indent = 3)

	logFile = open('browser#' + str(dictionary['id']) + '.log', 'a')
	logFile.write(logBuffer)
	logFile.close()

	print TAG + 'browser thread #' + str(dictionary['id']) + ' Closing Driver'
	driver.close()

def signalHandler(signal, frame):
	print('User interrupted testing with SIGINT; bailing out')
	stopServer()
	sys.exit(0)

# take a url and break it in protocol and transport counterparts
def breakUrl(url):
	matches = re.search('(^.*?:\/\/)(.*$)', url)
	protocol = matches.group(1)
	transport = matches.group(2)
	return protocol, transport

# Return the account base Restcomm URL, like http://ACae6e420f425248d6a26948c17a9e2acf:0d01c95aac798602579fe08fc2461036@127.0.0.1:8080/restcomm/2012-04-24/Accounts/ACae6e420f425248d6a26948c17a9e2acf,
# from base URL (i.e. http://127.0.0.1:8080), account sid and auth token
def restBaseUrlFromCounterparts(accountSid, authToken, restcommUrl):
	# Need to break URL in protocol and transport parts so that we can put account sid and auth token in between 
	matches = re.search('(^.*?:\/\/)(.*$)', restcommUrl)
	#protocol = matches.group(1)
	#transport = matches.group(2)
	protocol, transport = breakUrl(restcommUrl)
	return protocol + accountSid + ':' + authToken + '@' + transport + '/restcomm/2012-04-24/Accounts/' + accountSid

# curl will break if we target an https server that has self signed certificate. Let's always use -k (avoid checks for cert) when targeting https
def curlSecureOptionsIfApplicable(restcommUrl):
	protocol, transport = breakUrl(restcommUrl)
	if protocol == 'https://':
		return '-k'
	else:
		return ''

# Provision Restcomm Number for external service via REST call
def provisionPhoneNumber(phoneNumber, externalServiceUrl, accountSid, authToken, restcommUrl): 
	print TAG + "Provisioning phone number " + phoneNumber + ' and linking it with Voice URL: ' + externalServiceUrl
	devnullFile = open(os.devnull, 'w')
	# Need to break URL in protocol and transport parts so that we can put account sid and auth token in between 
	matches = re.search('(^.*?:\/\/)(.*$)', restcommUrl)
	protocol = matches.group(1)
	transport = matches.group(2)
	postData = {
		'PhoneNumber': phoneNumber,
		'VoiceUrl': externalServiceUrl,
		'VoiceMethod': 'GET',
		'FriendlyName': 'Load Testing App',
		'isSIP' : 'true',
	}
	#cmd = 'curl -X POST ' + restBaseUrlFromCounterparts(accountSid, authToken, restcommUrl) + '/IncomingPhoneNumbers.json -d PhoneNumber=' + phoneNumber + ' -d VoiceUrl=' + externalServiceUrl + ' -d FriendlyName=LoadTestingApp -d isSIP=true'
	cmd = 'curl ' + curlSecureOptionsIfApplicable(restcommUrl) + ' -X POST ' + restBaseUrlFromCounterparts(accountSid, authToken, restcommUrl) + '/IncomingPhoneNumbers.json -d ' + urllib.urlencode(postData)
	print TAG + cmd 
	#subprocess.call(cmd.split(), stdout = devnullFile, stderr = devnullFile)
	# remember this runs the command synchronously
	subprocess.call(cmd.split())


# Provision Restcomm Clients via REST call
# count: number of Clients to provision
# accountSid: Restcomm accountSid, like: ACae6e420f425248d6a26948c17a9e2acf
# authToken: Restcomm authToken, like: 0a01c34aac72a432579fe08fc2461036 
# restcommUrl: Restcomm URL, like: http://127.0.0.1:8080
def provisionClients(count, accountSid, authToken, restcommUrl, usernamePrefix, password): 
	print TAG + "Provisioning " + str(count) + " Restcomm Clients"
	devnullFile = open(os.devnull, 'w')
	# Need to break URL in protocol and transport parts so that we can put account sid and auth token in between 
	matches = re.search('(^.*?:\/\/)(.*$)', restcommUrl)
	protocol = matches.group(1)
	transport = matches.group(2)
	for i in range(1, count + 1):
		postData = {
			'Login': usernamePrefix + str(i),
			'Password': password,
		}
		#cmd = 'curl -X POST ' + restBaseUrlFromCounterparts(accountSid, authToken, restcommUrl) + '/Clients.json -d Login=user' + str(i) + ' -d Password=1234'
		cmd = 'curl ' + curlSecureOptionsIfApplicable(restcommUrl) + ' -X POST ' + restBaseUrlFromCounterparts(accountSid, authToken, restcommUrl) + '/Clients.json -d ' + urllib.urlencode(postData)
		#system(cmd)
		print TAG + cmd 
		#subprocess.call(cmd.split(), stdout = devnullFile, stderr = devnullFile)
		subprocess.call(cmd.split())

def startServer(count, clientUrl, externalServiceUrl, usernamePrefix, clientWebAppDir, clientRole): 
	print TAG + 'Starting http server to handle both http/https request for the webrtc-client web page, and RCML REST requests from Restcomm'

	externalServicePort = '80'
	externalServiceParsedUrl = urlparse.urlparse(externalServiceUrl);
	if externalServiceParsedUrl.port:
		externalServicePort = externalServiceParsedUrl.port
	
	webAppPort = '80'
	clientParsedUrl = urlparse.urlparse(clientUrl);
	if (clientParsedUrl.port):
		webAppPort = clientParsedUrl.port

	secureArg = ''
	if clientParsedUrl.scheme == 'https':
		secureArg = '--secure-web-app'
	
	# Make a copy of the current environment
	envDictionary = dict(os.environ)   
	# Add the nodejs path, as it isn't found when we run as root
	envDictionary['NODE_PATH'] = '/usr/local/lib/node_modules'
	#cmd = 'server.js ' + str(count) + ' 10512 10510 10511'
	cmd = 'node http-server.js --client-count ' + str(count) + ' --external-service-port ' + str(externalServicePort) + ' --external-service-client-prefix ' + usernamePrefix + ' --web-app-port ' + str(webAppPort) + ' ' + secureArg + ' --web-app-dir ' + clientWebAppDir + ' --client-role ' + clientRole
	# We want it to run in the background
	#os.system(cmd)
	#subprocess.call(cmd.split(), env = envDictionary)
	#print "--- CMD: " + cmd
	global httpProcess
	httpProcess = subprocess.Popen(cmd.split(), env = envDictionary)
	#httpProcess = subprocess.Popen(cmd.split())
	print TAG + 'PID for http server: ' + str(httpProcess.pid)

# TODO: Not finished yet
def unprovisionClients(count, accountSid, authToken, restcommUrl): 
	print TAG + "(Not implemented yet) Unprovisioning " + str(count) + " Restcomm Clients"
	#for i in range(1, count + 1):
	#	cmd = 'curl ' + curlSecureOptionsIfApplicable(restcommUrl) + ' -X DELETE http://' + accountSid + ':' + authToken + '@' + transport + '/restcomm/2012-04-24/Accounts/' + accountSid + '/Clients.json -d Login=user' + str(i) + ' -d Password=1234'
	#	...

def stopServer(): 
	if httpProcess:
		print TAG + 'Stopping http server'
		httpProcess.terminate()

def globalSetup(dictionary): 
	print TAG + "Setting up tests"

	global testModes
	# if user asked for restcomm provisioning/unprovisioning (i.e. testModes = 001 binary)
	if testModes & 1:
		# Provision Restcomm with the needed Clients
		provisionPhoneNumber(dictionary['phone-number'], dictionary['external-service-url'], dictionary['account-sid'], dictionary['auth-token'], dictionary['restcomm-base-url'])

		if dictionary['client-role'] == 'passive':
			# Provision Restcomm with the needed Clients only when in passive mode
			provisionClients(dictionary['count'], dictionary['account-sid'], dictionary['auth-token'], dictionary['restcomm-base-url'], dictionary['username-prefix'], dictionary['password'])

	# if user asked for http server to be started  (i.e. testModes = 010 binary)
	if testModes & 2:
		# Start the unified server script to serve both RCML (REST) and html page for webrtc clients to connect to
		startServer(dictionary['count'], dictionary['client-url'], dictionary['external-service-url'], dictionary['username-prefix'], dictionary['client-web-app-dir'], dictionary['client-role'])

def globalTeardown(dictionary): 
	print TAG + "Tearing down tests"

	global testModes
	# if user asked for restcomm provisioning/unprovisioning (i.e. testModes = 001 binary)
	if testModes & 1:
		# Provision Restcomm with the needed Clients
		unprovisionClients(dictionary['count'], dictionary['account-sid'], dictionary['auth-token'], dictionary['restcomm-base-url'])

	# if user asked for http server to be started  (i.e. testModes = 010 binary)
	if testModes & 2:
		# Start the unified server script to serve both RCML (REST) and html page for webrtc clients to connect to
		stopServer()

# Check if a command exists
def commandExists(cmd):
	for path in os.environ["PATH"].split(os.pathsep):
		path = path.strip('"')
		execFile = os.path.join(path, cmd)
		if os.path.isfile(execFile) and os.access(execFile, os.X_OK):
			return True
	return False

# Check if a process is running
def processRunning(cmd):
	output = subprocess.check_output('ps ax'.split())
	for line in output.splitlines():
		if re.search('Xvfb', line):
			return True
	return False

# Spawn browsers for all 'clients'
def spawnBrowsers(browserCommand, clients, totalBrowserCount, logIndex, headless, display, threaded):
	envDictionary = None
	cmdList = None
	#global totalBrowserCount
	#global logIndex
	#totalBrowserCount += len(clients)

	# TODO: we could make work both in Linux/Darwin but we need extra handling here
	#osName = subprocess.check_output(['uname'])
	if re.search('chrom', browserCommand, re.IGNORECASE):
		envDictionary = None
		# Make a copy of the current environment
		envDictionary = dict(os.environ)   
		# Set the chrome log file
		#envDictionary['CHROME_LOG_FILE'] = 'browser#' + str(client['id']) + '.log'
		#envDictionary['CHROME_LOG_FILE'] = 'chrome.log.' + str(datetime.datetime.utcnow()).replace(' ', '.')
		envDictionary['CHROME_LOG_FILE'] = 'chrome.log.' + str(logIndex)
		#logIndex += 1
		if headless:
			envDictionary['DISPLAY'] = display

		cmdList = [ 
			browserCommand,
			#'--user-data-dir=' + str(client['id']),
			#'--incognito',
			#'--new-window',
			'--no-first-run',  # even if it's the first time Chrome is starting up avoid showing the welcome message, which needs user intervention and causes issues on headless environment
			'--enable-logging',  # enable logging at the specified file
			#'--vmodule=webrtc-client*',  # not tested
			'--use-fake-ui-for-media-stream',  # don't require user to grant permission for microphone and camera
			'--use-fake-device-for-media-stream',  # don't use real microphone and camera for media, but generate fake media
			'--ignore-certificate-errors',  # don't check server certificate for validity, again to avoid user intervention
			#'--process-per-tab',  # not tested
		]

	else:
		# Make a copy of the current environment
		envDictionary = None
		envDictionary = dict(os.environ)   
		# Set the chrome log file
		#envDictionary['NSPR_LOG_FILE'] = 'browser#' + str(client['id']) + '.log'
		envDictionary['NSPR_LOG_FILE'] = 'firefox.log'
		# not sure why but this is the 'module' name for the web console and '5' to get all levels
		envDictionary['NSPR_LOG_MODULES'] = 'timestamp,textrun:5'
		#envDictionary['NSPR_LOG_MODULES'] = 'timestamp,all:3'
		if headless:
			envDictionary['DISPLAY'] = display
		# Firefox
		cmdList = [ 
			browserCommand,
			'--jsconsole',   # without this I'm not getting proper logs for some weird reason
			#'--args', 
			#'--new-tab',
			#client['url'], 
		]

	# add all the links in the command after the options
	for client in clients:
		cmdList.append(client['url'])

	separator = ' '
	print TAG + 'Spawning ' + str(len(clients)) + ' browsers (total: ' + str(totalBrowserCount) + '). Command: ' + separator.join(cmdList)
	devnullFile = open(os.devnull, 'w')
	# We want it to run in the background
	if threaded:
		subprocess.Popen(cmdList, env = envDictionary, stdout = devnullFile, stderr = devnullFile)
	else:
		browserProcess = subprocess.Popen(cmdList, env = envDictionary, stdout = devnullFile, stderr = devnullFile)

# Define a handler for the respawn HTTP server
class httpHandler(BaseHTTPRequestHandler):
	def do_GET(self):
		responseText = None
		if re.search('^/respawn-user.*', self.path) == None:
			self.send_response(501)
			responseText = 'Not Implemented, please use /respawn-user'
		else:
			self.send_response(200)
			# query string for the GET request
			qsDictionary = None
			if '?' in self.path:
				qsDictionary = urlparse.parse_qs(urlparse.urlparse(self.path).query)
			else:
				print '--- Not found ? in request'
				return

			print 'Received respawn request: ' + json.dumps(qsDictionary, indent = 3)

			global totalBrowserCount
			global logIndex
			# check which 'client' the request is for
			for client in clients:
				if client['id'] == qsDictionary['username'][0]:
					respawnClients = list()
					respawnClients.append(client)
					totalBrowserCount += len(respawnClients)
					spawnBrowserThread = Thread(target = spawnBrowsers, args = (args.clientBrowserExecutable, respawnClients, totalBrowserCount, logIndex, args.clientHeadless, args.clientHeadlessDisplay, False))
					spawnBrowserThread.start()
					logIndex += 1
					#spawnBrowsers(args.clientBrowserExecutable, respawnClients, totalBrowserCount, logIndex, args.clientHeadless, args.clientHeadlessDisplay, True)
					responseText = 'Spawning new browser with username: ' + qsDictionary['username'][0]

		self.send_header('Content-type', 'text/html')
		# Allow requests from any origin (CORS)
		self.send_header("Access-Control-Allow-Origin", self.headers.get('Origin'))
		self.end_headers()
		self.wfile.write(responseText)

		return

# HTTP server listening for AJAX requests and spawning new browsers when existing browsers finish with the call and close
def startRespawnServer(respawnUrl):

	respawnPort = '80'
	respawnParsedUrl = urlparse.urlparse(respawnUrl);
	if respawnParsedUrl.port:
		respawnPort = respawnParsedUrl.port
	
	print TAG + 'Starting respawn HTTP server at port: ' + str(respawnPort)

	httpd = None	
	serverAddress = ('', respawnPort)
	httpd = HTTPServer(serverAddress, httpHandler)
	if respawnParsedUrl.scheme == 'https':
		httpd.socket = ssl.wrap_socket(httpd.socket, keyfile='cert/key.pem', certfile='cert/cert.pem', server_side=True)
	httpd.socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)

	size = httpd.socket.getsockopt(SOL_SOCKET, SO_RCVBUF)
	print 'Socket recv buffer size: ' + str(size)
	httpd.socket.setsockopt(SOL_SOCKET, SO_RCVBUF, size * 2)
	newSize = httpd.socket.getsockopt(SOL_SOCKET, SO_RCVBUF)
	print 'Socket recv buffer size after set: ' + str(newSize)

	httpd.serve_forever()


## --------------- Main code --------------- ##
parser = argparse.ArgumentParser()
parser.add_argument('-c', '--client-count', dest = 'count', default = 10, type = int, help = 'Count of Webrtc clients spawned for the test')
parser.add_argument('--client-url', dest = 'clientUrl', default = 'http://127.0.0.1:10510/webrtc-client.html', help = 'Webrtc clients target URL, like \'http://127.0.0.1:10510/webrtc-client.html\'')
parser.add_argument('--client-web-app-dir', dest = 'clientWebAppDir', default = '.', help = 'Directory where the web app resides, so that our http server knows what to serve, like \'../webrtc-load-tests\'')
parser.add_argument('--client-register-ws-url', dest = 'registerWsUrl', default = 'ws://127.0.0.1:5082', help = 'Webrtc clients target websocket URL for registering, like \'ws://127.0.0.1:5082\'')
parser.add_argument('--client-register-domain', dest = 'registerDomain', default = '127.0.0.1', help = 'Webrtc clients domain for registering, like \'127.0.0.1\'')
parser.add_argument('--client-username-prefix', dest = 'usernamePrefix', default = 'user', help = 'User prefix for the clients, like \'user\'')
parser.add_argument('--client-password', dest = 'password', default = '1234', help = 'Password for the clients, like \'1234\'')
parser.add_argument('--client-browser-executable', dest = 'clientBrowserExecutable', default = 'chromium-browser', help = 'Browser executable for the test. Can be full path (if not in PATH), like \'/Applications/Firefox.app/Contents/MacOS/firefox-bin\', \'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome\' (for OSX) or just executable, like \'firefox\', \'chromium-browser\' (for GNU/Linux), default is \'chromium-browser\'')
parser.add_argument('--client-headless', dest = 'clientHeadless', action = 'store_true', default = False, help = 'Should we use a headless browser?')
parser.add_argument('--client-respawn', dest = 'respawn', action = 'store_true', default = False, help = 'Should we use respawn browser logic? This means a. starting an http server to listen for respawn requests (see --client-respawn-url) and b. tell the clients to close the tabs after done with the call scenario')
parser.add_argument('--client-respawn-url', dest = 'respawnUrl', default = 'http://127.0.0.1:10511/respawn-user', help = 'Webrtc clients respawn URL to be notified when the call is over, like \'http://127.0.0.1:10511/respawn-user\'')
parser.add_argument('--client-headless-x-display', dest = 'clientHeadlessDisplay', default = ':99', help = 'When using headless, which virtual X display to use when setting DISPLAY env variable. Default is \':99\'')
parser.add_argument('--client-role', dest = 'clientRole', default = 'passive', help = 'Role for the client. When \'active\' it makes a call to \'--target-sip-uri\'. When \'passive\' it waits for incoming call. Default is \'passive\'')
parser.add_argument('--client-target-uri', dest = 'clientTargetUri', default = '+1234@127.0.0.1', help = 'Client target URI when \'--client-role\' is \'active\' (it\'s actually a SIP URI without the \'sip:\' part. Default is \'+1234@127.0.0.1\'')
parser.add_argument('--restcomm-base-url', dest = 'restcommBaseUrl', default = 'http://127.0.0.1:8080', help = 'Restcomm instance base URL, like \'http://127.0.0.1:8080\'')
parser.add_argument('--restcomm-account-sid', dest = 'accountSid', required = True, help = 'Restcomm accound Sid, like \'ACae6e420f425248d6a26948c17a9e2acf\'')
parser.add_argument('--restcomm-auth-token', dest = 'authToken', required = True, help = 'Restcomm auth token, like \'0a01c34aac72a432579fe08fc2461036\'')
parser.add_argument('--restcomm-phone-number', dest = 'phoneNumber', default = '+5556', help = 'Restcomm phone number to provision and link with external service, like \'+5556\'')
parser.add_argument('--restcomm-external-service-url', dest = 'externalServiceUrl', default = 'http://127.0.0.1:10512/rcml', help = 'External service URL for Restcomm to get RCML from, like \'http://127.0.0.1:10512/rcml\'')
parser.add_argument('--test-modes', dest = 'testModes', default = 7, type = int, help = 'Testing modes for the load test. Which parts of the tool do we want to run? Provisioning, HTTP server, client browsers or any combination of those. This is a bitmap where binary 001 (i.e. 1) means to do provisioning unprovisioning, binary 010 (i.e. 2) means start HTTP(S) server and binary 100 (i.e. 4) means to spawn webrtb browsers. Default is binary 111 (i.e. 7) which means to do all the above')
parser.add_argument('--version', action = 'version', version = 'restcomm-test.py ' + VERSION)

args = parser.parse_args()

print TAG + 'Webrtc clients settings: \n\tcount: ' + str(args.count) + '\n\ttarget URL: ' + args.clientUrl + '\n\tregister websocket url: ' + args.registerWsUrl + '\n\tregister domain: ' + args.registerDomain + '\n\tusername prefix: ' + args.usernamePrefix + '\n\tpassword: ' + args.password + '\n\tbrowser executable: ' + args.clientBrowserExecutable + '\n\theadless: ' + str(args.clientHeadless) + '\n\theadless X display: ' + args.clientHeadlessDisplay + '\n\trespawn client browsers: ' + str(args.respawn) + '\n\trespawn url: ' + args.respawnUrl + '\n\tclient role: ' + args.clientRole + '\n\tclient target SIP URI: ' + args.clientTargetUri
print TAG + 'Restcomm instance settings: \n\tbase URL: ' + args.restcommBaseUrl + '\n\taccount sid: ' + args.accountSid + '\n\tauth token: ' + args.authToken + '\n\tphone number: ' + args.phoneNumber + '\n\texternal service URL: ' + args.externalServiceUrl
print TAG + 'Testing modes: ' + str(args.testModes)

# assign to global to be able to use from functions
testModes = args.testModes

# Let's handle sigint so the if testing is interrupted we still cleanup
signal.signal(signal.SIGINT, signalHandler)

globalSetup({ 
	'count': args.count, 
	'client-url': args.clientUrl, 
	'username-prefix': args.usernamePrefix,
	'password': args.password,
	'account-sid': args.accountSid, 
	'auth-token': args.authToken, 
	'restcomm-base-url': args.restcommBaseUrl,
	'phone-number': args.phoneNumber, 
	'external-service-url': args.externalServiceUrl,
	'client-web-app-dir': args.clientWebAppDir,
	'client-role': args.clientRole,
})

# Populate a list with browser thread ids and URLs for each client thread that will be spawned
clients = list()
for i in range(1, args.count + 1):
	GETData = {
		'username': args.usernamePrefix + str(i),
		'password': args.password,
		'register-ws-url': args.registerWsUrl,
		'register-domain': args.registerDomain,
		'fake-media': str(args.clientHeadless).lower(),
		'role': args.clientRole,
	}
	if args.respawn:
		GETData['respawn-url'] = args.respawnUrl;
		GETData['close-on-end'] = 'true';
	if args.clientRole == 'active':
		GETData['call-destination'] = args.clientTargetUri;
	
	clients.append({ 
		'id': GETData['username'], 
		'url' : args.clientUrl + '?' + urllib.urlencode(GETData)
	})

browserProcess = None
# if user asked for browsers to be spawned (i.e. testModes = 100 binary)
if testModes & 4:
	if args.clientHeadless: 
		if not commandExists('Xvfb'):
			# Check if Xvfb exists
			print 'ERROR: Running in headless mode but Xvfb does not exist'
			stopServer()
			sys.exit(1)

		if not processRunning('Xvfb'):
			print 'ERROR: Running in headless mode but Xvfb is not running'
			stopServer()
			sys.exit(1)

	useSelenium = False;
	if useSelenium:
		print TAG + 'Spawning ' + str(args.count) + ' tester threads' 
		# Make the Pool of workers
		pool = ThreadPool(args.count) 
		# Open the urls in their own threads and return the results
		try:
			results = pool.map(threadFunction, clients)
		except:
			print TAG + 'EXCEPTION: pool.map() failed. Unexpected exception: ', sys.exc_info()[0]

		# Close the pool and wait for the work to finish 
		pool.close() 
		pool.join() 
	else:
		# No selenium, spawn browsers manually (seems to scale better than selenium)
		#global totalBrowserCount
		#global logIndex
		# check which 'client' the request is for
		totalBrowserCount += len(clients)
		spawnBrowsers(args.clientBrowserExecutable, clients, totalBrowserCount, logIndex, args.clientHeadless, args.clientHeadlessDisplay, False)
		logIndex += 1

		# Start the respawn server which monitors if browsers are closing after handling call scenario and creates new in their place so that load testing can carry on
		if args.respawn:
			startRespawnServer(args.respawnUrl)

		print TAG + 'Please start call scenarios. Press Ctrl-C to stop ...'

# raw_input doesn't exist in 3.0 and inputString issues an error in 2.7
if (sys.version_info < (3, 0)):
	inputString = raw_input(TAG + 'Press any key to stop the test...\n')
else:
	inputString = input(TAG + 'Press any key to stop the test...')

# if user asked for browsers to be spawned (i.e. testModes = 100 binary)
if testModes & 4:
	if not useSelenium:
		print TAG + "Stopping browser"
		browserProcess.kill()

globalTeardown({ 
	'count': args.count, 
	'username': args.password,
	'password': args.password,
	'account-sid': args.accountSid, 
	'auth-token': args.authToken, 
	'restcomm-base-url': args.restcommBaseUrl,
	'phone-number': args.phoneNumber, 
	'external-service-url': args.externalServiceUrl
})
