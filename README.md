# x-plane ADSB output
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE.txt)

This project was small subset of the code I wrote for my undergraduate final
year software project.

This is a plugin for the [x-plane](http://www.x-plane.com/) flight simulator
which sends flight data equivalent to what might be present in an ADSB message
via sockets over the network to a server capable of receiving the messages.

The original purpose was for this to be used as a realtime, high frequency data
source for simulating air traffic control situations and algorithms. 

The message format, which uses Google Protocol Buffers can be found in
[DebugDataFeedServe.proto](adsb_output/DebugDataFeedServe.proto).

This plugin to be used with Sandy Barbour's python interface for x-plane. See
http://www.xpluginsdk.org/python_interface.htm for more info. The version of
python required is 2.7, and the
[protobuf](https://pypi.python.org/pypi/protobuf/3.5.1) 
module is required to be installed in your python distribution.