# webrtc-test

Framework for functional and Load Testing of WebRTC. Can be used to test client and server media components utilizing WebRTC, like Media Servers, SIP clients, etc. Has been tested both in regular hosts that have a window environment as well as headless servers in Amazon EC2 (using Xvfb)

## How it works ##

At the heart of webrtc-test is python script [webrtc-test](https://github.com/RestComm/webrtc-test/blob/master/tools/webrtc-test.py) which sets up Restcomm for the test, spawns webrtc clients in browser tabs and starts some servers to help with the scenario, more specifically it:
* Provisions the Restcomm instance with needed Incoming Number and Restcomm Clients that will be used by the webrtc clients when registering
* Starts up a node js http server that will serve the RCML for the Restcomm external service linked with the Incoming Number we provisioned previously. 
* Starts up a node js http(s) server that will serve the web app to the browser tabs. This app is configured to register with restcomm and wait for webrtc calls.
* Starts up a python http(s) server that will serve wait for re-spawn Ajax requests from the web app. That is, each browser tab when finished with the phone call from Restcomm it notifies webrtc-test.py that it's done and closes. Once webrtc-test.py receives that requests it respawns a browser tab for the same user (this is a way to workaround an issue where after some calls browser tabs performance would degrade)
* Spawn as many browser tabs as requested targeting the webrtc web app, using a separate username for each to register with Restcomm (from the pool provisioned previously)

Once that setup is done we can then start the Sipp load scenarios found at [webrtc-load-tests](https://github.com/RestComm/webrtc-test/webrtc-load-tests) towards Restcomm Incoming Number and play a 1-minute media stream. For each call this is what happens:
* Restcomm receives the call and contacts the external service to see what to do with it
* External service return RCML that instructs Restcomm to call the next available webrtc client and bridge the 2 calls
* Webrtc client running in the browser tab receives the call from Restcomm and hears the 1-minute media stream sent by Sipp. At the same time it sends dummy media stream back
* Once the whole media stream is played Sipp hangs up the call, which means that the call from Restcomm -> Webrtc client is also hung up
* At that point the webrtc client notifies webrtc-test.py that it's about to close the tab so that the tool re-spawns another tab in it's stead

## How to use it ##

For sake of brevity we 'll go over the simple case where both Restcomm, webrtc-test.py and sipp are all on the same host. But keep in mind that you can separate them since both Restcomm and webrtc-test.py take up a lot of resources (remember that webrtc-test can spawn a lot of browsers for testing that can be pretty resource-hungry). In this example I will be using an Ubuntu Server image in Amazon EC2, but it should work on any GNU/Linux distribution as well as OSX which we have tested as well.

## First, install prerequisites ##

* Install sipp for the SIP call generation
	* Download latest tar.gz bundle from https://github.com/SIPp/sipp/releases
	* Install prerequisites:
		$ sudo apt-get install ncurses-dev libpcap-dev
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

## Then, start webrtc-test.py ##

In this example we are running the load testing tool to use 40 webrtc clients:

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
	--client-respawn-url https://10.231.4.197:10511/respawn-user 
	--client-respawn 
	--client-headless 
	--client-headless-x-display ":99"
```

Option details:
* **client-count** is the number of webrtc clients to handle calls (i.e. concurrent connections)
* **client-url** is the webrtc web app URL, which will automatically register with Restcomm and be able to receive calls and auto-answer (or make in another scenario)
* **client-register-ws-url** is the websocket URL that the webrtc web app should use for registering and general signalling with Restcomm
* **client-register-domain** Is the domain that the webrtc web app should use when registering
* **client-username-prefix** is the username prefix for the generated Restcomm Clients (for example if the prefix is ‘user’ and the count is 10 the generated clients will be user1-user10)
* **client-password** is the SIP password for the webrtc clients
* **restcomm-account-sid** is the Restcomm account sid that we use for various Restcomm REST APIs (mostly for provisioning/unprovisioning)
* **restcomm-auth-token** is the Restcomm auth token that we use for various Restcomm REST APIs 
* **restcomm-base-url** is the base url for Restcomm that we use for various Restcomm REST APIs 
* **restcomm-phone-number** is the incoming Restcomm number that we will target with our sipp script
* **restcomm-external-service-url** is the external service URL that Restcomm will contact via GET to retrieve the RCML for the App (associated with number shown previously)
* **client-browser** is the desired browser to use for the client. Currently supported are ‘firefox’ and ‘chrome’
* **client-headless** should be used when we want the client to run in a headless fashion, where no real X windows environment is set and instead xvfb is set
* **client-web-app-dir** which directory should be served over http
* **client-respawn-url** the URL where the browser window will notify webrtc-test.py that it just finished with a call and will close, so that webrtc-test.py will spawn a new tab. 

## Finally, start Sipp load tests

Run sipp to create the actual SIP traffic towards ‘+5556’ Restcomm number. In this example we are setting up sipp to use 20 concurrent calls. Important: the number of concurrent calls should be less than ‘--client-count’ passed in webrtc-test.py to give the closing browser windows time to re-spawn. In fact it's a good practice to use half the client count for sipp concurrent calls for best results.

