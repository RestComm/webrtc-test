## Preparations ##

Tools comprising the webrtc-test framework: 

* Main script is webrtc-test.py that does the orchestration
* http-server.js is a node js script that handles both external service for Restcomm as well as serving the webrtc web app to the browsers
* cert/ has a self-signed cert used when we need to use https instead of http for serving the web app with http-server.js (remember that this is needed for chrome to avoid issues with getUserMedia() from insecure origins)
