# dbus-fronius-smart-meter with Phase 1 Hack

⚠️ ⚠️ ⚠️ Work in Progress, not yet 100% ⚠️ ⚠️ ⚠️ 

⚠️ Only usable with a Single-Phase System, where the actual values of L2 and L3 doesn't matter *for ESS* ⚠️

This is a fork of the original dbus-fronius-smart-meter repository. I'm running ESS on a victron with a *dedicated* battery behind
a fronius hybrid inverter with it's own battery. The subgrid Multigrid inverter should take over supply of it's attached loads during
nighttime to increase the runtime of the hybrid's battery. With usual smart-meter readings this leads to both inverters / batteries
trying to go up and down on their feed-in values, both trying to zero out consumption at the feed in point. 

This script reads a fronius smartmeter from the inverts solar-api and manipulates the readings in the following way: 

- Value of L1 will be replaced with the actual consumption of the ESS subgrid - so ESS can cancel out that consumption. 
- When there is solar overhead available, the value L1 will be adjust to a virtual feedin, so ESS starts to charge the desired amount. 
- In either case, the original value of L1 is added to L2 and the artificial value L1' is deducted from L2, so the overall Consumption stays correct. 
- Currents then are recalculated to match the displayed power based on the original voltage. 

# Installation.

```
wget https://github.com/realdognose/dbus-fronius-smart-meter-with-phase1-injection/archive/refs/heads/main.zip
unzip main.zip "dbus-fronius-smart-meter-with-phase1-injection-main/*" -d /data
mv /data/dbus-fronius-smart-meter-with-phase1-injection-main /data/dbus-fronius-smart-meter-with-phase1-injection
chmod a+x /data/dbus-fronius-smart-meter-with-phase1-injection/install.sh
/data/dbus-fronius-smart-meter-with-phase1-injection/install.sh
rm main.zip
```
⚠️ Check configuration after that - because service is already installed an running and with wrong connection data (host, username, pwd) you will spam the log-file
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
Within the project there is a file `/data/dbus-fronius-smart-meter-with-phase1-injection/config.ini` - just change the values - most important is the host and hostPlug in section "ONPREMISE". More details below:

Afther change the config file execute restart.sh to reload new settings 

---

# original description

For information about additional configuration, please view the original smart meter readout repository at: 
https://github.com/ayasystems/dbus-fronius-smart-meter
 
# ⚠️ ⚠️ ⚠️ Important ⚠️ ⚠️ ⚠️ 
This hack fixes the ESS not beeing able to determine it's required Feed-In when running behind a fronius hybrid inverter with a battery. 
There is a second Issue with that layout: When the fronius is providing battery power at the end of the night, when the scheduled loading window for ESS kicks in, it will start directly charging of the hybrids battery feed, because ESS sees that there is "enough PV Input available".

I've made a second script that corrects the readings for the hybrid inverter (disable the original victron implementation) by injecting another
regular PV-Inverter and a generater on the AC-side that mimics the battery-feed-in rather than showing it as PV-Output.

ESS will now wait until the PV inverters now start to produce REAL PV Feed-In. 

See here: https://github.com/realdognose/dbus-fronius-hybrid-battery-visualisation

(The script to split up the hibrid inverter into regular PV-Inverter plus generator can be used without this phase manipulation script)
