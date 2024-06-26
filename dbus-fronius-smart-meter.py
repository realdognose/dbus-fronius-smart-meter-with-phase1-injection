#!/usr/bin/env python
 
# import normal packages
# https://github.com/victronenergy/dbus_modbustcp/blob/master/attributes.csv
from dbus.mainloop.glib import DBusGMainLoop

# Have a mainloop, so we can send/receive asynchronous calls to and from dbus
DBusGMainLoop(set_as_default=True)

import platform 
import logging
import sys
import os
import sys
if sys.version_info.major == 2:
    import gobject
else:
    from gi.repository import GLib as gobject
import sys
import time
import dbus
import requests # for http GET
import configparser # for config/ini file

# our own packages from victron
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python'))
from vedbus import VeDbusService, VeDbusItemImport

dbusConn = dbus.SessionBus() if 'DBUS_SESSION_BUS_ADDRESS' in os.environ else dbus.SystemBus()

class DbusFroniusMeterService:
  def __init__(self, servicename, deviceinstance, paths, productname='Fronius Smart Meter VIR w. Phase1 Hack', connection='Fronius meter JSON API'):
    self._config = configparser.ConfigParser()
    self._config.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))
    self._dbusservice = VeDbusService("{}.http_{:02d}".format(servicename, deviceinstance))
    self._paths = paths
 
    logging.debug("%s /DeviceInstance = %d" % (servicename, deviceinstance))
 
    # Create the management objects, as specified in the ccgx dbus-api document
    self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
    self._dbusservice.add_path('/Mgmt/ProcessVersion', 'Unkown version, and running on Python ' + platform.python_version())
    self._dbusservice.add_path('/Mgmt/Connection', connection)
 
    # Create the mandatory objects
    self._dbusservice.add_path('/DeviceInstance', deviceinstance)
    self._dbusservice.add_path('/ProductId', 45069) # Carlo Gavazzi ET 340 Energy Meter
    self._dbusservice.add_path('/DeviceType', 345) # found on https://www.sascha-curth.de/projekte/005_Color_Control_GX.html#experiment - should be an ET340 Engerie Meter
    self._dbusservice.add_path('/ProductName', productname) 
    self._dbusservice.add_path('/CustomName', productname)
    self._dbusservice.add_path('/Latency', None)    
    self._dbusservice.add_path('/FirmwareVersion', 0.1)
    self._dbusservice.add_path('/HardwareVersion', 0)
    self._dbusservice.add_path('/Connected', 1)
    self._dbusservice.add_path('/Role', "grid")
    #self._dbusservice.add_path('/Position', 1) # normaly only needed for pvinverter
    #self._dbusservice.add_path('/Serial', self._getFronisSerial())
    self._dbusservice.add_path('/Serial', "12345")
    self._dbusservice.add_path('/UpdateIndex', 0)
 
    # add path values to dbus
    for path, settings in self._paths.items():
      self._dbusservice.add_path(
        path, settings['initial'], gettextcallback=settings['textformat'], writeable=True, onchangecallback=self._handlechangedvalue)
 
    # last update
    self._lastUpdate = 0
 
    # add _update function 'timer'
    gobject.timeout_add(int(self._config['ONPREMISE']['intervalMs']), self._update) # pause 250ms before the next request
    
    # add _signOfLife 'timer' to get feedback in log every 5minutes
    gobject.timeout_add(self._getSignOfLifeInterval()*60*1000, self._signOfLife)

  def _getFronisSerial(self):
    meter_data = self._getFroniusData()  
    
    if not meter_data['Body']['Data']['Details']['Serial']:
        raise ValueError("Response does not contain 'mac' attribute")
    
    serial = meter_data['Body']['Data']['Details']['Serial']
    return serial
  
  def _getConfig(self):
    config = configparser.ConfigParser()
    config.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))
    return config
  
  def _getSignOfLifeInterval(self):
    config = self._getConfig()
    value = config['DEFAULT']['SignOfLifeLog']
    
    if not value: 
        value = 0
    
    return int(value)
  
  
  def _getFroniusDataUrl(self):
    config = self._getConfig()
    accessType = config['DEFAULT']['AccessType']
    
    if accessType == 'OnPremise': 
        #URL = "http://%s:%s@%s/status" % (config['ONPREMISE']['Username'], config['ONPREMISE']['Password'], config['ONPREMISE']['Host'])
        URL = "http://%s/solar_api/v1/GetMeterRealtimeData.cgi?Scope=Device&DeviceId=%s&DataCollection=MeterRealtimeData" % (config['ONPREMISE']['Host'], config['ONPREMISE']['MeterID'])
        #URL = URL.replace(":@", "")
    else:
        raise ValueError("AccessType %s is not supported" % (config['DEFAULT']['AccessType']))
    
    return URL
 
  def _getFroniusData(self):
    URL = self._getFroniusDataUrl()
    meter_r = requests.get(url = URL)
    
    # check for response
    if not meter_r:
        raise ConnectionError("No response from Fronius - %s" % (URL))
    
    meter_data = meter_r.json()     
    
    # check for Json
    if not meter_data:
        raise ValueError("Converting response to JSON failed on Fronius")
    
    return meter_data
 
  def dbus_getvalue_ve(bus, service, object_path):
    object = bus.get_object(service, object_path)
    return object.GetValue()

  def _signOfLife(self):
    logging.info("--- Start: sign of life ---")
    logging.info("Last _update() call: %s" % (self._lastUpdate))
    logging.info("--- End: sign of life ---")
    return True
 
  def _update(self):   
    try:
       #current Update Cycle Index
       currentCycleIndex = self._dbusservice['/UpdateIndex']

       #get data from bus        
       acInESS = 0
       try:
         if (self._dbusservice['/Initialized'] == 1):
           acInESS = float(VeDbusItemImport(dbusConn, self._config['ONPREMISE']['L1ServiceName'], '/Ac/ActiveIn/L1/P').get_value())
       except Exception as e:
          logging.warn("Failed to retrieve value. DBUS Object not yet ready?")

       acOutESS = 0
       try:
        if (self._dbusservice['/Initialized'] == 1):
          acOutESS = float(VeDbusItemImport(dbusConn, self._config['ONPREMISE']['L1ServiceName'], '/Ac/Out/L1/P').get_value())
       except Exception as e:
         logging.warn("Failed to retrieve value. DBUS Object not yet ready?")

       availablePVOnGrid = 0   
       try:
         if (self._dbusservice['/Initialized'] == 1):
           availablePVOnGrid = float(VeDbusItemImport(dbusConn, "com.victronenergy.system", '/Ac/PvOnGrid/L1/Power').get_value()) + float(VeDbusItemImport(dbusConn, "com.victronenergy.system", '/Ac/PvOnGrid/L2/Power').get_value()) + float(VeDbusItemImport(dbusConn, "com.victronenergy.system", '/Ac/PvOnGrid/L3/Power').get_value()) 
       except Exception as e:
         logging.warn("Failed to retrieve value. DBUS Object not yet ready?")

       acLoads=0
       try:
         if (self._dbusservice['/Initialized'] == 1):
           acLoads = float(VeDbusItemImport(dbusConn, "com.victronenergy.system", '/Ac/Consumption/L1/Power').get_value()) + float(VeDbusItemImport(dbusConn, "com.victronenergy.system", '/Ac/Consumption/L2/Power').get_value()) + float(VeDbusItemImport(dbusConn, "com.victronenergy.system", '/Ac/Consumption/L3/Power').get_value()) 
       except Exception as e:
         logging.warn("Failed to retrieve value. DBUS Object not yet ready?")

       #get data from Fronius
       meter_data = self._getFroniusData()

       #get data from config
       pvOverheadShare = float(self._config['ONPREMISE']['SolarOverheadShare'])
       pvOverheadLimit = float(self._config['ONPREMISE']['SolarOverheadLimit'])
       
       vicBatCharge = acInESS - acOutESS
       finalInjectionValue = 0
       batteryChargeHybrid = 0
       acLoadsCleared = acLoads - acOutESS

       try:
         if (self._dbusservice['/Initialized'] == 1):
          batteryChargeHybrid = VeDbusItemImport(dbusConn, self._config['ONPREMISE']['BatteryServiceName'], '/Dc/0/Power').get_value()
       except Exception as e:
        logging.warn("Failed to retrieve value. DBUS Object not yet ready?")

       #dump all values we gathered  
       if (currentCycleIndex == 100):
         logging.info("------------------------------")
         logging.info("pvOverheadShare configured to " + str(pvOverheadShare) + " with a limit of " + str(pvOverheadLimit))
         logging.info("AC-IN Victron: " + str(acInESS))
         logging.info("AC-OUT Victron: " + str(acOutESS))
         logging.info("AC Loads: " + str(acLoads)) #AC Loads already contains Critical Loads as well
         logging.info("AC Loads (cleared): " + str(acLoadsCleared)) 
         logging.info("PV in: " + str(availablePVOnGrid)) #PV In will contain hybrid discharge. 
         logging.info("Bat charge Hybrid: " + str(batteryChargeHybrid))
         logging.info("Bat charge Victron: " + str(vicBatCharge))
       else:  
         logging.debug("------------------------------")
         logging.debug("pvOverheadShare configured to " + str(pvOverheadShare) + " with a limit of " + str(pvOverheadLimit))
         logging.debug("AC-IN Victron: " + str(acInESS))
         logging.debug("AC-OUT Victron: " + str(acOutESS))
         logging.debug("AC Loads: " + str(acLoads)) #AC Loads already contains Critical Loads as well
         logging.debug("AC Loads (cleared): " + str(acLoadsCleared))
         logging.debug("PV in: " + str(availablePVOnGrid)) #PV In will contain hybrid discharge. 
         logging.debug("Bat charge Hybrid: " + str(batteryChargeHybrid)) 
         logging.debug("Bat charge Victron: " + str(vicBatCharge))

       virtuallyAvailableEnergy = availablePVOnGrid - acLoadsCleared - acOutESS + max(batteryChargeHybrid, 0) + max(vicBatCharge, 0) + min(batteryChargeHybrid, 0)
       additionalChargeDesired = min(virtuallyAvailableEnergy * pvOverheadShare, pvOverheadLimit) - vicBatCharge
       finalInjectionValue = min(additionalChargeDesired * -1, acInESS)

       if (currentCycleIndex == 100):
         logging.info("=> Virtual available E: " + str(virtuallyAvailableEnergy))
         logging.info("==> Vic Charge Change: " + str(additionalChargeDesired))
         logging.info("===> Final InjectionValue: " + str(finalInjectionValue))
       else:
         logging.debug("=> Virtual available E: " + str(virtuallyAvailableEnergy))
         logging.debug("==> Vic Charge Change: " + str(additionalChargeDesired))
         logging.debug("===> Final InjectionValue: " + str(finalInjectionValue))

       #set Voltages
       self._dbusservice['/Ac/L1/Voltage'] = float(meter_data['Body']['Data']['Voltage_AC_Phase_1'])
       self._dbusservice['/Ac/L2/Voltage'] = float(meter_data['Body']['Data']['Voltage_AC_Phase_2'])
       self._dbusservice['/Ac/L3/Voltage'] = float(meter_data['Body']['Data']['Voltage_AC_Phase_3'])

       #set Power
       self._dbusservice['/Ac/L1/Power'] = finalInjectionValue # Value we want ESS to see on Phase 1
       self._dbusservice['/Ac/L2/Power'] = float(meter_data['Body']['Data']['PowerReal_P_Phase_2']) + float(meter_data['Body']['Data']['PowerReal_P_Phase_1']) - finalInjectionValue #corrections, so overall Total stays the same.
       self._dbusservice['/Ac/L3/Power'] = float(meter_data['Body']['Data']['PowerReal_P_Phase_3']) #untouched
       self._dbusservice['/Ac/Power'] = self._dbusservice['/Ac/L1/Power'] + self._dbusservice['/Ac/L2/Power'] + self._dbusservice['/Ac/L3/Power']

       #Calculate Fake Current as well.
       self._dbusservice['/Ac/L1/Current'] = round(self._dbusservice['/Ac/L1/Power'] / self._dbusservice['/Ac/L1/Voltage'],2)
       self._dbusservice['/Ac/L2/Current'] = round(self._dbusservice['/Ac/L2/Power'] / self._dbusservice['/Ac/L2/Voltage'],2)
       self._dbusservice['/Ac/L3/Current'] = round(self._dbusservice['/Ac/L3/Power'] / self._dbusservice['/Ac/L3/Voltage'],2)

       #stats
       self._dbusservice['/Ac/L1/Energy/Forward'] = float(meter_data['Body']['Data']['EnergyReal_WAC_Sum_Consumed'])/3000 
       self._dbusservice['/Ac/L1/Energy/Reverse'] = float(meter_data['Body']['Data']['EnergyReal_WAC_Sum_Produced'])/3000  
       self._dbusservice['/Ac/L2/Energy/Forward'] = float(meter_data['Body']['Data']['EnergyReal_WAC_Sum_Consumed'])/3000 
       self._dbusservice['/Ac/L2/Energy/Reverse'] = float(meter_data['Body']['Data']['EnergyReal_WAC_Sum_Produced'])/3000  
       self._dbusservice['/Ac/L3/Energy/Forward'] = float(meter_data['Body']['Data']['EnergyReal_WAC_Sum_Consumed'])/3000 
       self._dbusservice['/Ac/L3/Energy/Reverse'] = float(meter_data['Body']['Data']['EnergyReal_WAC_Sum_Produced'])/3000  
       self._dbusservice['/Ac/Energy/Forward'] = float(meter_data['Body']['Data']['EnergyReal_WAC_Sum_Consumed'])/1000
       self._dbusservice['/Ac/Energy/Reverse'] = float(meter_data['Body']['Data']['EnergyReal_WAC_Sum_Produced'])/1000
              
       # increment UpdateIndex - to show that new data is available
       index = currentCycleIndex + 1  # increment index
       if index > 255:   # maximum value of the index
         index = 0       # overflow from 255 to 0
       
       #After approx 1 min, set the initialized flag. 
       #It should now be save to query other dbus-services.
       dbusQueryCycleStart = int(self._config['ONPREMISE']['DbusQueryCycleStart'])
       if (index == dbusQueryCycleStart):
         logging.info(str(dbusQueryCycleStart) + " cycles passed. Attempting to resolve dbus values from now on. If you see exceptions after that, increase DbusQueryCycleStart in config.ini.")
         self._dbusservice['/Initialized'] = 1 
       
       self._dbusservice['/UpdateIndex'] = index

       #update lastupdate vars
       self._lastUpdate = time.time()              
    except Exception as e:
       logging.critical('Error at %s', '_update', exc_info=e)
       
    # return true, otherwise add_timeout will be removed from GObject - see docs http://library.isr.ist.utl.pt/docs/pygtk2reference/gobject-functions.html#function-gobject--timeout-add
    return True
 
  def _handlechangedvalue(self, path, value):
    logging.critical("someone else updated %s to %s" % (path, value))
    return True # accept the change
 

def main():
  config = configparser.ConfigParser()
  config.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))

  logLevelString = config['ONPREMISE']['LogLevel']
  logLevel = logging.getLevelName(logLevelString)
  logDir = "/data/log/dbus-fronius-smart-meter-with-phase1-injection"
  
  if not os.path.exists(logDir):
    os.mkdir(logDir)

  #configure logging
  logging.basicConfig(      format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S',
                            level=logLevel,
                            handlers=[
                                logging.FileHandler(logDir + "/current.log"),
                                logging.StreamHandler()
                            ])
 
  try:
      from dbus.mainloop.glib import DBusGMainLoop

      # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
      DBusGMainLoop(set_as_default=True)

      #formatting 
      _kwh = lambda p, v: (str(round(v, 2)) + ' kWh')
      _a = lambda p, v: (str(round(v, 1)) + ' A')
      _w = lambda p, v: (str(round(v, 1)) + ' W')
      _v = lambda p, v: (str(round(v, 1)) + ' V')  
      _p = lambda p, v: (str(v))  

      
      servicename = 'com.victronenergy.grid'
      
      #start our main-service
      pvac_output = DbusFroniusMeterService(
        servicename=servicename,
        deviceinstance=int(config['ONPREMISE']['CreatedMeterID']),
        paths={
          '/Ac/Energy/Forward': {'initial': 0, 'textformat': _kwh}, # energy bought from the grid
          '/Ac/Energy/Reverse': {'initial': 0, 'textformat': _kwh}, # energy sold to the grid
          '/Ac/Power': {'initial': 0, 'textformat': _w},
          '/Ac/L1/Voltage': {'initial': 0, 'textformat': _v},
          '/Ac/L2/Voltage': {'initial': 0, 'textformat': _v},
          '/Ac/L3/Voltage': {'initial': 0, 'textformat': _v},
          '/Ac/L1/Current': {'initial': 0, 'textformat': _a},
          '/Ac/L2/Current': {'initial': 0, 'textformat': _a},
          '/Ac/L3/Current': {'initial': 0, 'textformat': _a},
          '/Ac/L1/Power': {'initial': 0, 'textformat': _w},
          '/Ac/L2/Power': {'initial': 0, 'textformat': _w},
          '/Ac/L3/Power': {'initial': 0, 'textformat': _w},
          '/Ac/L1/Energy/Forward': {'initial': 0, 'textformat': _kwh},
          '/Ac/L2/Energy/Forward': {'initial': 0, 'textformat': _kwh},
          '/Ac/L3/Energy/Forward': {'initial': 0, 'textformat': _kwh},
          '/Ac/L1/Energy/Reverse': {'initial': 0, 'textformat': _kwh},
          '/Ac/L2/Energy/Reverse': {'initial': 0, 'textformat': _kwh},
          '/Ac/L3/Energy/Reverse': {'initial': 0, 'textformat': _kwh},
          '/Initialized': {'initial': 0, 'textformat': _p},
        })
     
      logging.info('Connected to dbus, and switching over to gobject.MainLoop() (= event based)')
      mainloop = gobject.MainLoop()
      mainloop.run()            
  except Exception as e:
    logging.critical('Error at %s', 'main', exc_info=e)
if __name__ == "__main__":
  main()
