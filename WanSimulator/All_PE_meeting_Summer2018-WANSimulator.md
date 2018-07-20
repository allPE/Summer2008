
# All PE meeting - Summer 2018 - Project WAN Simulator

## 1. Objective

The objective of this project is to build a WAN simulator using your Pi.

Your Pi should act as a "transparent" device, so if it's installed/inserted in the middle of a link between two other devices, no IP configuration
change is required to keep connectivity between such devices.

Through your simulator, you should be able to do the following, independently of the type of traffic (IPv4 or IPv6):

* Add latency on the link between devices
* Discard packets (to emulate packet loss)
* Limit the bandwidth

## 2. Groups

Your group should be integrated by 2 engineers, but if you prefer to work alone that's ok, just consider that we might not have enough accessories.

Each group will have 2 additional USB/Ethernet dongle for their Pi.

Each group should be able to present 1 or 2 WAN simulators that will be used by a team on the Network Tools project.

![alt text](https://github.com/allPE/Summer2018/blob/master/WanSimulator/All-PE-NT-Fig3.png "WAN Simulator")

## 3. Requirements

To access your PI, you should:

* Connect to the on-board LAN port of your Pi and ssh/telnet directly to it.
* Identify which IP address was assigned to the WLAN interface.
* Disconnect the cabled connection and try to access your Pi though the WLAN interface.
* The 2 LAN interfaces on each Pi will be used by the WAN simulator. In order to do this, you should disable the DHCP server on the on-
board LAN interface.

To perform the base tasks of this project, the following should be installed in your Raspberry Pi:

* [tcconfig](https://github.com/thombashi/tcconfig): Simple tc command wrapper tool.

## 4. References

* tcconfig documentation: [http://tcconfig.readthedocs.io/en/latest/](http://tcconfig.readthedocs.io/en/latest/)
* If you get stuck, you can get an idea from [here](http://www.uebi.net/howtos/rpiwanem.htm).

## 5. Interaction with Network Tools project

Once your WAN simulator is ready, it will be added to the Network Tools project in order to test its capabilities.

The WAN simulator will modify parameters in the link in order to simulate particular scenarios: satellite like delay, packet drops, etc. It is up to
your team (including the Network Tools team) to decide what kind of testing do.

![alt text](https://github.com/allPE/Summer2018/blob/master/WanSimulator/All-PE-NT-Fig2.png "Network Tools Integration")

## 6. Challenges

Depending on your level of expertise on python, linux and other topics, you might want to try the following challenges:

* Instead of using tcconfig, you might directly use Linux [Traffic Control](https://www.tldp.org/HOWTO/html_single/Traffic-Control-HOWTO/) and manipulate the packets directly (which it is pretty much what tcconfig is doing).
* Use any Web Framework for Python (i.e. [Flask](http://flask.pocoo.org/), [Django](https://www.djangoproject.com/), [web2py](https://github.com/allPE/Summer2018/blob/master/NetworkTools/web2py), etc.) to provide a web-based interface for the WAN simulator.


```
The information contained herein is confidential and should not be disclosed, copied, or duplicated in any manner without written
permission from Charter Communications<sup>TM</sup>.
```
