# webrtc-test

Framework for functional and Load Testing of WebRTC. Can be used to test client and server media components utilizing WebRTC, like Media Servers, SIP clients, etc. Has been tested both in regular hosts that have a window environment as well as headless servers in Amazon EC2 (using Xvfb)

## How it works ##

At the heart of webrtc-test is python script [webrtc-test](https://github.com/RestComm/webrtc-test/blob/master/tools/webrtc-test.py) which sets up Restcomm for the test, spawns webrtc clients in browser tabs and starts some servers to help with the scenario, more specifically it:
* Provisions the Restcomm instance with needed Incoming Number and Restcomm Clients that will be used by the webrtc clients when registering
* Starts up a node js http server that will serve the RCML for the Restcomm external service linked with the Incoming Number we provisioned previously. 
* Starts up a node js http(s) server that will serve the web app to the browser tabs. This app is configured to register with restcomm and wait for webrtc calls.
* Starts up a python http(s) server that will serve wait for re-spawn Ajax requests from the web app. That is, each browser tab when finished with the phone call from Restcomm it notifies webrtc-test.py that it's done and closes. Once webrtc-test.py receives that requests it respawns a browser tab for the same user (this is a way to workaround an issue where after some calls browser tabs performance would degrade)
* Spawn as many browser tabs as requested targeting the webrtc web app, using a separate username for each to register with Restcomm (from the pool provisioned previously)

Once that setup is done we can then start the Sipp load scenarios found at [webrtc-load-tests](https://github.com/RestComm/webrtc-test/webrtc-load-tests) towards Restcomm Incoming Number and play a 1-minute media stream. Notice that you can use any tool you like to generate traffic towards Restcomm; we are using Sipp as an example. For each call this is what happens:
* Restcomm receives the call and contacts the external service to see what to do with it
* External service return RCML that instructs Restcomm to call the next available webrtc client and bridge the 2 calls
* Webrtc client running in the browser tab receives the call from Restcomm and hears the 1-minute media stream sent by Sipp. At the same time it sends dummy media stream back
* Once the whole media stream is played Sipp hangs up the call, which means that the call from Restcomm -> Webrtc client is also hung up
* At that point the webrtc client notifies webrtc-test.py that it's about to close the tab so that the tool re-spawns another tab in it's stead

## How to use it ##

For sake of brevity we 'll go over the simple case where both Restcomm, webrtc-test.py and sipp are all on the same host. But keep in mind that you can separate them since both Restcomm and webrtc-test.py take up a lot of resources (remember that webrtc-test can spawn a lot of browsers for testing that can be pretty resource-hungry). In this example I will be using an Ubuntu Server image in Amazon EC2, but it should work on any GNU/Linux distribution as well as OSX which we have tested as well.

### 1. Install prerequisites ###

* Install sipp for the SIP call generation (as already mentioned we are using Sipp for this example, but you can use any tool you like to generate calls)
	* Download latest tar.gz bundle from https://github.com/SIPp/sipp/releases
	* Install prerequisites: `$ sudo apt-get install ncurses-dev libpcap-dev`
	* Uncompress and configure with pcap support (so that we can RTP media as well, not only signaling) and build: `$ ./configure --with-pcap && make`
	* Install: `$ sudo make install`
* Install python packages (main load script is written in python)
	* Install python package manager: `$ sudo apt-get install python-pip`
	* Install selenium (currently it isn’t used due to some scaling issues but the dependencies in the code are still there, so please install until we decide on this): `$ sudo pip install selenium`
* Install nodejs packages (http server script is in nodejs as it appears to scale better than python; with python starting more that ~30 webrtc clients caused the python web server to fail for some of them)
	* Install nodejs `$ sudo apt-get install nodejs`
	* Some applications expect nodejs to be named node, so create this link: `$ sudo ln -s "$(which nodejs)" /usr/bin/node`
	* Install nodejs package manager: `$ sudo apt-get install npm`
	* Install needed nodejs modules (globally usually works best): `$ sudo npm -g install node-static express command-line-args`
	* Export nodejs modules path so that they can be discovered and used by nodejs (remember to add this in your profile or similar to be able to use it in future sessions): `$ export NODE_PATH=/usr/local/lib/node_modules`
* Setup for headless execution
	* Install xvfb which is a virtual window environment where apps can render on memory instead of a real screen: `$ sudo apt-get install xvfb`
	* Optionally install some additional fonts to avoid getting warnings in xvfb: `$ sudo apt-get install xfonts-100dpi xfonts-75dpi xfonts-scalable xfonts-cyrillic`
	* Install firefox and chromium browsers `$ sudo apt-get install firefox chromium-browser`
	* Start xvfb in the background and configure it to use display 99 (randomly chosen display): `$ Xvfb :99 &`
* Clone webrtc-test repo that contains the load testing tools: `$ git clone https://github.com/RestComm/webrtc-test.git`
* Change dir to the load testing dir: `$ cd webrtc-test/tools`

### 2. Start webrtc-test.py ###

In this example we are running the load testing tool to use 40 webrtc clients in headless mode in an Amazon EC2 instance:

```
$ ./webrtc-test.py 
	--client-count 40 
	--client-url https://10.231.4.197:10510/webrtc-client.html 
	--client-register-ws-url wss://10.231.4.197:5083 
	--client-register-domain 10.231.4.197 
	--client-username-prefix user 
	--client-password 1234 
	--restcomm-account-sid ACae6e420f425248d6a26948c17a9e2acf 
	--restcomm-auth-token 3349145c827863209020dbc513c87260  
	--restcomm-base-url https://10.231.4.197:8443 
	--restcomm-phone-number "+5556" 
	--restcomm-external-service-url http://10.231.4.197:10512/rcml 
	--client-browser "chromium-browser" 
	--client-web-app-dir ../webrtc-load-tests/ 
	--client-respawn 
	--client-respawn-url https://10.231.4.197:10511/respawn-user 
	--client-headless 
	--client-headless-x-display ":99"
```

Option details:
* **client-count** is the number of webrtc clients to handle calls (i.e. concurrent connections)
* **client-url** is the webrtc web app URL, which will automatically register with Restcomm and be able to receive calls and auto-answer (or make in another scenario)
* **client-register-ws-url** is the websocket URL that the webrtc web app should use for registering and general signalling with Restcomm
* **client-register-domain** is the domain that the webrtc web app should use when registering
* **client-username-prefix** is the username prefix for the generated Restcomm Clients (for example if the prefix is ‘user’ and the count is 10 the generated clients will be user1-user10)
* **client-password** is the SIP password for the webrtc clients
* **restcomm-account-sid** is the Restcomm account sid that we use for various Restcomm REST APIs (mostly for provisioning/unprovisioning)
* **restcomm-auth-token** is the Restcomm auth token that we use for various Restcomm REST APIs 
* **restcomm-base-url** is the base url for Restcomm that we use for various Restcomm REST APIs 
* **restcomm-phone-number** is the incoming Restcomm number that we will target with our traffic generator (in this case Sipp)
* **restcomm-external-service-url** is the external service URL that Restcomm will contact via GET to retrieve the RCML for the App (associated with number shown previously)
* **client-browser** is the desired browser to use for the client. Currently supported are Firefox and Chrome
* **client-web-app-dir** which directory should be served over http
* **client-respawn** switch which if provided tells the tool to use respawn logic for the browser tabs. This means that after each tab finishes handling a call will be closed and recycled
* **client-respawn-url** the URL where the browser window will notify webrtc-test.py that it just finished with a call and will close, so that webrtc-test.py will spawn a new tab. 
* **client-headless** switch to be used when we want the client to run in a headless fashion, where no real X windows environment is set and instead xvfb or other virtual window manager is used
* **client-headless-x-display** when using headless, which virtual X display to use. Default is \':99\'

### 3. Initiate load tests ###

Although you can use any tool you like to generate call traffic towards Restcomm, we are using Sipp as an example. What we do is use Sipp to create calls towards ‘+5556’ Restcomm number. In this example we are setting up sipp to use 20 concurrent calls. Important: the number of concurrent calls should be less than ‘--client-count’ passed in webrtc-test.py to give the closing browser windows time to re-spawn before a new call arrives for them. In fact it's a good practice to use half the client count for sipp concurrent calls for best results, as we do here:

```
$ sudo sipp -sf webrtc-sipp-client.xml -s +5556 10.231.4.197:5080 -mi 10.231.4.197:5090 -l 20 -m 40 -r 2 -trace_screen -trace_err -recv_timeout 5000 -nr -t u1
```

The main figure to note is the `-l 20 -m 40 -r 2` portion which means 20 concurrent calls, 40 total calls, at a rate of 2 calls per second. 

### 4. Analyze the results ###

When the Sipp test finishes we are presented with this output:

```
----------------------------- Statistics Screen ------- [1-9]: Change Screen --
  Start Time             | 2016-04-07	09:32:01.115325	1460021521.115325         
  Last Reset Time        | 2016-04-07	09:34:15.723558	1460021655.723558         
  Current Time           | 2016-04-07	09:34:15.724996	1460021655.724996         
-------------------------+---------------------------+--------------------------
  Counter Name           | Periodic value            | Cumulative value
-------------------------+---------------------------+--------------------------
  Elapsed Time           | 00:00:00:001000           | 00:02:14:609000          
  Call Rate              |    0.000 cps              |    0.297 cps             
-------------------------+---------------------------+--------------------------
  Incoming call created  |        0                  |        0                 
  OutGoing call created  |        0                  |       40                 
  Total Call created     |                           |       40                 
  Current Call           |        0                  |                          
-------------------------+---------------------------+--------------------------
  Successful call        |        0                  |       40                 
  Failed call            |        0                  |        0                 
-------------------------+---------------------------+--------------------------
  Response Time 1        | 00:00:00:000000           | 00:00:00:100000          
  Call Length            | 00:00:00:000000           | 00:01:02:115000          
------------------------------ Test Terminated --------------------------------
```

Which tells us that all calls are successful along with other interesting statistics. 

But this isn't the full picture. We need to check the browser side too make sure that Webrtc calls from Restcomm -> browser web clients are successful. To do that we take advantage of the [restcomm-web-sdks's](https://github.com/RestComm/restcomm-web-sdk) latest addition that exposes PeerConnection getStats() to the web app. For now we don't do anything fancy in the app, just print out in the browser console the whole dictionary as returned from the SDK. Here's a sample for one of the calls (noticed that I have beautified this to be easier to see here:

```
[5551:5551:0407/091640:INFO:CONSOLE(226)] "Retrieved call media stats: {  
   "direction":"inbound",
   "bytes-transfered":"19092",
   "packets-transfered":"111",
   "output-level":"528",
   "media-type":"audio",
   "codec-name":"PCMA",
   "packets-lost":"0",
   "jitter":"0",
   "ssrc":"3967089803"
},
{  
   "direction":"outbound",
   "bytes-transfered":"19264",
   "packets-transfered":"112",
   "input-level":"6435",
   "media-type":"audio",
   "codec-name":"PCMA",
   "packets-lost":"-1",
   "jitter":"-1",
   "ssrc":"3854772780"
}", ...
```

The fact that we see bytes transfered and no packets lost in both directions is a pretty good indication that things went well. Another indication is the input-level and output-level, but as far as I know these are only available in Chrome. Remember that all calls from Restcomm -> web app are audio-only, which is why you only see audio 'media-type' in the getStats() results.

As always, feel free to jump in and play with the code and get your hands dirty. There's a list of [open issues](https://github.com/RestComm/webrtc-test/issues?q=is%3Aopen+is%3Aissue+label%3A%22help+wanted%22) that you can start with, or you can suggest your own enhancements. If you have any questions please post at the [Restcomm forum](https://groups.google.com/forum/#!forum/restcomm) or in Stackoverflow using tag 'restcomm'.



For frequently asked questions, please refer to the [FAQ](https://github.com/RestComm/webrtc-test/wiki/FAQ)
