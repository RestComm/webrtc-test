#! /usr/bin/env python
#
# IMPORTANT: this is no longer used by webrtc-test.py, since we had scaling
# issues, so it has been superseded by http-server.js implemented in node js.
# I'm just keeping this around in case we need it in the future
#
# This is a 'unified' server used in our testing for serving:
# - RCML (REST) for Restcomm at /rcml. The logic for RCML is to return a Dial command towards Restcomm Client userX, where X is a increasing counter reaching up to client count and wrapping around so that continuous tests can be ran
# - html pages of this directory at /, like webrtc-client.html over https/https
#
# Two threads are used. One to serve RCML to Restcomm and the other to server the web app html page over http/https
# 
# Example invocations:
# $ server.py --client-count 10 --external-service-port 10512 --secure-web-app --web-app-port 10510
# $ server.py --client-count 10 --external-service-port 10512 --secure-web-app --web-app-port 10511 
# 

import argparse
import SocketServer
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import SimpleHTTPServer
import ssl
import random
import re
from socket import *

# To use multiple processes instead we should  use:
# import multiprocessing
# And replace ThreadPool with Pool
from multiprocessing.dummy import Pool as ThreadPool

# Globals
TAG = '[server.py] '
usernamePrefix = None
CLIENT_COUNT = None
rcmlClientId = 1

# Define a handler for the RCML REST server
class httpHandler(BaseHTTPRequestHandler):
	def do_GET(self):
		#if self.path != '/rcml':
		if re.search('^/rcml.*', self.path) == None:
			self.send_response(403)
			self.send_header('Content-type', 'text/xml')
			self.end_headers()
			return

		self.send_response(200)
		self.send_header('Content-type', 'text/xml')
		self.end_headers()

		global rcmlClientId
		print '[server.py] Handing client ' + str(rcmlClientId)
		rcml = '<?xml version="1.0" encoding="UTF-8"?><Response> <Dial record="false"> <Client>'
		rcml += usernamePrefix; 
		rcml += str(rcmlClientId)
		rcml += '</Client> </Dial> </Response>'

		if (rcmlClientId == CLIENT_COUNT):
			print '[server.py] Reached ' + str(rcmlClientId) + ', wrapping around'
			rcmlClientId = 0

		rcmlClientId += 1

		self.wfile.write(rcml)
		return


def threadFunction(dictionary): 
	if 'secure' in dictionary.keys():
		print TAG + 'Starting: ' + dictionary['type'] + ' thread, port: ' + str(dictionary['port']) + ', secure: ' + str(dictionary['secure'])
	else:
		print TAG + 'Starting: ' + dictionary['type'] + ' thread, port: ' + str(dictionary['port'])

	httpd = None	
	serverAddress = ('', dictionary['port'])

	if dictionary['type'] == 'external-service':
		httpd = HTTPServer(serverAddress, httpHandler)
		# for now external service is already cleartext. If we want secure at some point follow the steps below to implement

	if dictionary['type'] == 'app-web-server':
		httpd = SocketServer.TCPServer(("", dictionary['port']), SimpleHTTPServer.SimpleHTTPRequestHandler)
		if 'secure' in dictionary.keys() and dictionary['secure']:
			httpd.socket = ssl.wrap_socket(httpd.socket, keyfile='cert/key.pem', certfile='cert/cert.pem', server_side=True)

	httpd.socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
	httpd.serve_forever()


## --------------- Main code --------------- ##

parser = argparse.ArgumentParser()
parser.add_argument('-c', '--client-count', dest = 'count', default = 10, type = int, help = 'Count of Webrtc clients expected to be used for test. This is needed to know how many different Restcomm Clients the RCML returned will target')
parser.add_argument('--external-service-port', dest = 'externalServicePort', default = 10512, type = int, help = 'Which port will be used to serve RCML to Restcomm')
parser.add_argument('--external-service-client-prefix', dest = 'externalServiceClientPrefix', default = 'user', help = 'The prefix for the Client noun of the RCML, like \'user\'')
parser.add_argument('--web-app-port', dest = 'webAppPort', default = 10510, type = int, help = 'Which port will be used to serve web app pages')
parser.add_argument('--secure-web-app', dest = 'secureWebApp', action = 'store_true', default = False, help = 'Should we use https for the web app?')
args = parser.parse_args()

print TAG + 'External service settings: \n\tclient count: ' + str(args.count) + '\n\tport: ' + str(args.externalServicePort) + '\n\tclient prefix: ' + args.externalServiceClientPrefix
print TAG + 'Web app server settings: \n\tport: ' + str(args.webAppPort) + '\n\tsecure: ' + str(args.secureWebApp)

CLIENT_COUNT = args.count
usernamePrefix = args.externalServiceClientPrefix

# Populate a list with browser thread ids and URLs for each client thread that will be spawned
poolArgs = [
	{ 'type': 'external-service', 'port': args.externalServicePort }, 
	{ 'type': 'app-web-server', 'secure': args.secureWebApp, 'port': args.webAppPort }, 
] 

# Make the Pool of workers
pool = ThreadPool(2) 
# Open the urls in their own threads and return the results
results = pool.map(threadFunction, poolArgs)
# close the pool and wait for the work to finish 
pool.close() 
pool.join() 
