## Preparations ##

Before starting sipp traffic you first need to start webrtc-test.py testing tool which will spawn the webrtc test app in the browsers and register webrtc clients that will be the recipients of the calls. Please refer to root README.md at https://github.com/RestComm/webrtc-test for more details

## How to execute test ##

The way this works is that sipp forwards SIP traffic to a Restcomm number, in this example +5556 (notice that you can use any tool you like to generate traffic towards Restcomm; we are using Sipp as an example). That number is linked to a Restcomm App which  distributes the calls to all registered webrtc clients.

```
$ sudo sipp -sf webrtc-sipp-client.xml -s <restcomm app number> <restcomm instance ip>:<SIP port> -mi <sipp ip>:<port> -l 50 -m 1000 -r 2 -trace_screen -trace_err -recv_timeout 5000 -nr -t u1
```

Example:

```
$ sudo sipp -sf webrtc-sipp-client.xml -s +5556 10.33.207.119:5080 -mi 10.33.207.119:5090 -l 50 -m 1000 -r 2 -trace_screen -trace_err -recv_timeout 5000 -nr -t u1
```

