/* 
 * This is a unified server used in our testing for serving:
 * - html pages of this directory at /, like webrtc-client.html over http
 * - html pages of this directory at /, like webrtc-client.html over https
 * - RCML (REST) for Restcomm at /rcml. The logic for RCML is to return a Dial command towards Restcomm Client userX, where X is a increasing counter reaching up to client count and wrapping around so that continuous tests can be ran
 *
 * Command line:
 * $ node server.js [client count] [REST RCML port] [HTTP port for html] [HTTPS port for html]
 */

var nodeStatic = require('node-static');
var commandLineArgs = require('command-line-args');
var http = require('http');
var https = require('https');
var express = require('express');
var fs = require('fs');

var TAG = '[http-server] ';

// TODO: replace with node-getopt
var CLIENT_COUNT = 10;
var RCML_PORT = 10512;
var HTTP_PORT = 10510;
var HTTPS_PORT = 10511;

var cli = commandLineArgs([
  { name: 'client-count', alias: 'c', type: Number, defaultValue: 10 },
  { name: 'external-service-port', alias: 'p', type: Number, defaultValue: 10512 },
  { name: 'external-service-client-prefix', alias: 'x', type: String, defaultValue: 'user' },
  { name: 'web-app-port', alias: 'w', type: Number, defaultValue: 10510 },
  { name: 'web-app-dir', alias: 'd', type: String, defaultValue: '.' },
  { name: 'secure-web-app', alias: 's', type: Boolean, defaultValue: false },
  { name: 'record-media', alias: 'm', type: Boolean, defaultValue: false },
  { name: 'client-role', alias: 'r', type: String, defaultValue: 'passive' },
  { name: 'help', alias: 'h' },
]);

var options = cli.parse();
if (options['help']) {
	cli.getUsage();
}
//console.log('[server.js] Options: ' + JSON.stringify(options));	

/*
if (process.argv.length <= 2) {
	console.log('[server.js] Usage: $ server.js [client count] [REST RCML port] [HTTP port for html] [HTTPS port for html]');	
	process.exit(1);
}
if (process.argv[2]) {
	CLIENT_COUNT = process.argv[2];
}
if (process.argv[3]) {
	RCML_PORT = process.argv[3];
}
if (process.argv[4]) {
	HTTP_PORT = process.argv[4];
}
if (process.argv[5]) {
	HTTPS_PORT = process.argv[5];
}
*/

//console.log('[server.js] Initializing http(s) server with ' + options[' + ' clients: \n\tRCML (REST) port: ' + RCML_PORT + ' \n\thttp (Webrtc App) port: ' + HTTP_PORT + ' \n\thttps (Webrtc App) port: ' + HTTPS_PORT);	
console.log(TAG + 'External service settings: \n\tclient count: ' + options['client-count'] + '\n\tport: ' + options['external-service-port'] + '\n\tclient prefix: ' + options['external-service-client-prefix'] + '\n\tclient role: ' + options['client-role'] + '\n\trecord media: ' + options['record-media']);
console.log(TAG + 'Web app server settings: \n\tport: ' + options['web-app-port'] + '\n\tsecure: ' + options['secure-web-app'] + '\n\tserving contents of: ' + options['web-app-dir']);

// -- Serve html pages over http
var fileServer = new nodeStatic.Server(options['web-app-dir']);
var app = null;

if (!options['secure-web-app']) {
	app = http.createServer(function (req, res) {
	  fileServer.serve(req, res);
	}).listen(options['web-app-port']);
}
else {
	// Options for https
	var secureOptions = {
	  key: fs.readFileSync('cert/key.pem'),
	  cert: fs.readFileSync('cert/cert.pem')
	};

	// Serve html pages over https
	app = https.createServer(secureOptions, function (req, res) {
	  fileServer.serve(req, res);
	}).listen(options['web-app-port']);
}

// -- Serve RCML with REST
var app = express();
var id = 1; 

app.get('/rcml', function (req, res) {
	console.log('[server.js] Handing client ' + id);	
	var rcml = ''
	if (options['client-role'] == 'passive') {
		// when webrtc client is passive the RCML should be active and make calls towards it
		//rcml = '<?xml version="1.0" encoding="UTF-8"?><Response> <Say>Welcome to RestComm, a TeleStax sponsored project.</Say></Response>';
		rcml = '<?xml version="1.0" encoding="UTF-8"?><Response> <Dial '; 
		if (options['record-media']) {
			rcml += 'record="true"';
		}
		else {
			rcml += 'record="false"';
		}
		rcml += '> <Client>' + options['external-service-client-prefix'];
		rcml += id; 
		rcml += '</Client> </Dial> </Response>';

		if (id == options['client-count']) {
			console.log('[server.js] Reached ' + id + ', wrapping around');	
			id = 0;	
		}
		id++;
	}
	else {
		// when webrtc client is active the RCML should be passive and accept webrtc calls from the client
		rcml = '<?xml version="1.0" encoding="UTF-8"?><Response><Say>One morning, when Gregor Samsa woke from troubled dreams, he found himself transformed in his bed into a horrible vermin. He lay on his armour-like back, and if he lifted his head a little he could see his brown belly, slightly domed and divided by arches into stiff sections. The bedding was hardly able to cover it and seemed ready to slide off any moment. His many legs, pitifully thin compared with the size of the rest of him, waved about helplessly as he looked. "What\'s happened to me?" he thought. It wasn\'t a dream. His room, a proper human room although a little too small, lay peacefully between its four familiar walls. A collection of textile samples lay spread out on the table - Samsa was a travelling salesman - and above it there hung a picture that he had recently cut out of an illustrated magazine and housed in a nice, gilded frame. It showed a lady fitted out with a fur hat and fur boa who sat upright, raising a heavy fur muff that covered the whole of her lower arm towards the viewer. Gregor then turned to look out the window at the dull weather</Say></Response>';
	}

	res.set('Content-Type', 'text/xml');
	res.send(rcml);
})
 
app.listen(options['external-service-port']);
