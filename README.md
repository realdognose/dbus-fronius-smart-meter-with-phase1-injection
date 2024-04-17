# dbus-fronius-smart-meter with Phase 1 Hack

⚠️ ⚠️ ⚠️ Work in Progress, not yet 100% ⚠️ ⚠️ ⚠️ 

⚠️ Only usable with a Single-Phase System, where the actual values of L2 and L3 doesn't matter *for ESS* ⚠️

This is a fork of the original dbus-fronius-smart-meter repository. I'm running ESS on a victron with a *dedicated* battery behind
a fronius hybrid inverter with it's own battery. The *subgrid*s inverter (victron multigrid) should take over supply of it's attached loads during
nighttime to increase the runtime of the hybrids battery. With usual smart-meter readings this leads to both inverters / batteries
trying to go up and down on their feed-in values, both trying to zero out consumption at the feed in point. 

| ![image](https://github.com/realdognose/dbus-fronius-smart-meter-with-phase1-injection/blob/main/img/Schema.png) | 
|:--:| 
| *Schematic Layout to illustrate what subgrid means.* |


This script reads a fronius smartmeter from the inverts solar-api and manipulates the readings in the following way: 

- Value of L1 will be replaced with the actual consumption of the ESS subgrid - so ESS can cancel out that consumption. 
- When there is solar overhead available, the value L1 will be adjust to a virtual feedin, so ESS starts to charge the desired amount. 
- In either case, the original value of L1 is added to L2 and the artificial value "L4" is deducted from L2, so the overall consumption stays correct. 
- Currents then are recalculated to match the displayed power based on the original voltage. 
- It can be configured how much of available solar overheat the ESS should steal from the fronius hybrid ;)

# Example One, Controlled discharge: 
From dusk till dawn, the value presented as L1 will equal the victron inverters *AC-IN Value minus ESS Battery Feed-In*. In this example ESS is working 
with a grid set point of 35 Watts, so a tiny bit of energy will always flow from the main-grid to the sub grid. ESS will feed in enough from it's own 
battery to satisfy it's own critical loads needs: 

This mode is entered, when there is < 100 Watts PV-Feedin available, i.e. the hybrids battery is already discharging and supplying all loads. 

| ![image](https://github.com/realdognose/dbus-fronius-smart-meter-with-phase1-injection/blob/main/img/ControlledDischarge.png) | 
|:--:| 
| *Controlled discharge from dusk till dawn* |

# Example Two, Charge ESS first
In the config file, two values can be set: `SolarOverheadShare` and `SolarOverheadLimit`. In this Example, we want the ESS battery to charge
first, because it is only capable of charging with ~ 450 Watts, so it should get precedence above the hybrid inverter who can charge with around
7000 Watts. Therefore, we configure `SolarOverheadShare=1` (100%)  and `SolarOverheadLimit=600` (Watts). 

100% of the available PV-Overhead will now be requested by ESS, first. This is achieved by setting L1 to a manipulated `-600` so ESS will start to 
act and balance on it's AC-IN until L1 will reach about `-150` and the battery charge rate 450 Watts. The script will take care to take the actual 
loads as well as actual available PV-Overhead into account and recalculate a proper L1 value every cycle.

| ![Image](https://github.com/realdognose/dbus-fronius-smart-meter-with-phase1-injection/blob/main/img/ControlledCharge.png) | 
|:--:| 
| *Controlled charge, by manipulating L1 to simulate available PV-Overhead*: L1 is set in a way that ESS is starting to charge and the hybrid inverter will favour it's loads, charging less on it's own battery |

# Example Three, Balance PV Overheat evenly

TODO

# Installation.

```
wget https://github.com/realdognose/dbus-fronius-smart-meter-with-phase1-injection/archive/refs/heads/main.zip
unzip main.zip "dbus-fronius-smart-meter-with-phase1-injection-main/*" -d /data
mv /data/dbus-fronius-smart-meter-with-phase1-injection-main /data/dbus-fronius-smart-meter-with-phase1-injection
chmod a+x /data/dbus-fronius-smart-meter-with-phase1-injection/install.sh
/data/dbus-fronius-smart-meter-with-phase1-injection/install.sh
rm main.zip
```
⚠️ Check configuration after that - because service is already installed an running and with wrong data you will spam the log-file
### Stop service
```
svc -d /service/dbus-fronius-smart-meter-with-phase1-injection
```
### Start service
```
svc -u /service/dbus-fronius-smart-meter-with-phase1-injection
```
### Reload data
```
/data/dbus-fronius-smart-meter-with-phase1-injection/restart.sh
```
### View log file
```
cat /data/dbus-fronius-smart-meter-with-phase1-injection/current.log
```
### Change config.ini
Within the project there is a file `/data/dbus-fronius-smart-meter-with-phase1-injection/config.ini`. For details, read the comments in the config file.
After changing the config, restart cerbo in order to apply new settings due to the service beeing restarted. 

---

# original description

For information about additional configuration, please view the original smart meter readout repository at: 
https://github.com/ayasystems/dbus-fronius-smart-meter
 
# ⚠️ ⚠️ ⚠️ Important ⚠️ ⚠️ ⚠️ 
This hack fixes the ESS not beeing able to determine it's required Feed-In when running behind a fronius hybrid inverter with a battery. 
In Order to apply the solar overheat distribution between the hybrids battery and the ESS battery, another script to visualize the hybrids
battery in ESS is required: 

See here: https://github.com/realdognose/dbus-fronius-hybrid-battery-visualisation

(The script to split up the hybrid inverter into regular PV-Inverter plus battery can be used without this phase manipulation script, but is 
a prerequisite of the solar distribution feature, because it is mandatory to know if the fronius battery is already charging.)
