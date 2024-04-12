#!/bin/bash


kill $(pgrep -f 'supervise dbus-fronius-smart-meter-with-phase1-injection')
chmod a-x /data/dbus-fronius-smart-meter-with-phase1-injection/service/run
svc -d /service/dbus-fronius-smart-meter-with-phase1-injection
./restart.sh
