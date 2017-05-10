# pytrthree
A Pythonic wrapper for the TRTH API based on [Zeep](http://docs.python-zeep.org/en/master/).

Pytrthree attempts to provide an user-friendly interface for the notably hard to use [Thomson Reuters Tick History](https://tickhistory.thomsonreuters.com/TickHistory/TRTH?action=get_main_applet) 
API. Leveraging the wonderfull [Zeep](http://docs.python-zeep.org/en/master/) library, 
it provides a REST-like user experience, by 1) providing resonable defaults many parameters, 
and 2) taking care of the generation of custom XML objects.


#### Naming
[brotchie](https://github.com/brotchie) made the original [`pytrth`](https://github.com/brotchie/pytrth) library and [Continuum Analytics](https://www.continuum.io/) [fork](https://github.com/ContinuumIO/pytrth) gave continuation to the project. As of 2017, both projects are stale. Pytr**three** aims to be the **third** incarnation of a Python wrapper for TRTH, and provides Python **3** support ONLY (because it is 2017).

#### Requirements
It is assumed the user has some basic knowledge of the TRTH service and has a **valid subscription**. The official TRTH API User Guide can be found [here](https://tickhistory.thomsonreuters.com/data/results/RDTH.sample@reuters.com/TRTH_API_User_Guide_v5_8.pdf) (login required).


## Usage

#### Authentication
In order to authenticate with the API, you need to make a YAML configuration file as the following:

```yaml
credentials:
  username: yourusername@thomsonreuters.com
  password: yourpassword
log: ~/path/to/logdir
ftp:
  hostname: ftp.yourserver.com:21
  user: ftpuser
  password: yourpassword
  path: /some/relative/path
```

#### Initialization

```python
from pytrthree import TRTH
api = TRTH(config='trth_config.yml')
```

#### Calling API methods

All TRTH API functions are accessible as `TRTH` object methods. `CamelCase` naming is changed in favor of more Pythonic `snake_case` naming. For example, the `ExpandChain` TRTH API function can used like the following: 

```python
>>> api.expand_chain('0#.N225', requestInGMT=True)
['.N225', '1332.T', '4061.T', '5711.T', ... ]
```

In order to see the function signature call the `signature` method of the wrapped function: 

```python
>>> api.expand_chain.chain()
ExpandChain(instrument: Instrument, dateRange: DateRange, timeRange: TimeRange, requestInGMT: xsd:boolean) --> ArrayOfInstrument
```

If using IPython, `?` can be used instead. For further detailed usage of each API function, please refer to the official TRTH documentation.

Pytrthree adds some extra functionality on top of Zeep in order to parse standard Python objects into XML that can be sent to the TRTH API. In order to turn off the added Pytrthree functionality see the [debugging](#Debugging) section.

#### Requesting instrument data

TRTH instrument data request objects are parsed from YAML files:

```yaml
friendlyName: simple_request
requestType: TimeAndSales
instrument:
  code: 7203.T
date: 2016-04-12
timeRange:
  start: 08:59
  end: 09:05
messageTypeList:
  messageType:
    - name: Trade
      fieldList:
        string:
          - Price
          - Volume
dateFormat: YYYYMMDD
disableDataPersistence: true
includeCurrentRIC: false
requestInGMT: false
displayInGMT: true
disableHeader: false
applyCorrections: false
displayMicroseconds: true
```

We recommend users start off one of the templates provided in the `templates` folder and modify it according to their needs. To send simple direct request:

```python
import yaml
req_obj = api.factory.RequestSpec(**yaml.load(open('templates/RequestSpec.yml')))
req_id = api.submit_request(req_dict)
```

Here, `req_obj` is a dictionary-like object. To change the instrument, simply try:

```python
req_obj['instrument']['code'] = '9984.T'
```

`req_id` contains the request ID:

```python
>>> req_id
{'requestID': 'yourusername@thomsonreuters.com-simple_request-N146877655'}
```

To retrieve your request result:

```python
>>> api.get_request_result(**req_id)
       #RIC   Date[G]          Time[G]  GMT Offset   Type  Price  Volume
0    9984.T  20160412  00:00:00.311790           9  Trade   5656  156300
1    9984.T  20160412  00:00:00.481720           9  Trade   5657     100
2    9984.T  20160412  00:00:02.143839           9  Trade   5657     100
3    9984.T  20160412  00:00:02.143839           9  Trade   5657     100
4    9984.T  20160412  00:00:02.162364           9  Trade   5660     200
5    9984.T  20160412  00:00:02.172187           9  Trade   5663     300
...

```



## Debugging/options