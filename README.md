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


## Getting started

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

#### Calling API functions

All TRTH API functions are accessible as `TRTH` object methods. `CamelCase` naming is changed in favor of more Pythonic `snake_case` naming. For example, the `ExpandChain` TRTH API function can used like the following: 

```python
>>> api.expand_chain('0#.N225', requestInGMT=True)
['.N225', '1332.T', '4061.T', '5711.T', ... ]
```

In order to see the function signature call the `signature` method of the wrapped function: 

```python
>>> api.expand_chain.signature()
ExpandChain(instrument: Instrument, dateRange: DateRange, timeRange: TimeRange, requestInGMT: xsd:boolean) --> ArrayOfInstrument
```

If using IPython, `?` can be used instead. For further detailed usage of each API function, 
please refer to the official TRTH documentation.

Pytrthree adds some extra functionality on top of Zeep in order to parse standard Python 
objects into XML that can be sent to the TRTH API. 

#### Requesting instrument data

In the TRTH API, there are two data types for instrument data requests, 
`RequestSpec` and `LargeRequestSpec`.
The former is used for direct, single-RIC requests, while the later is used for FTP 
requests. Both request type objects can be parsed from YAML files. 
Here is a sample `RequestSpec`: 

```yaml
friendlyName: simple_request
requestType: TimeAndSales
instrument:
  code: 7203.T
date: '2016-04-12'
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

You can submit a `RequestSpec` request by passing a template file path to `submit_request`:

```python
request_id = api.submit_request('templates/RequestSpec.yml')
```

`request_id` contains the request ID:

```python
>>> request_id
{'requestID': 'yourusername@thomsonreuters.com-simple_request-N146877655'}
```

Instead of using a template directly, users can also use the object generation factory 
to programatically make a request object. 
We recommend users start off one of the templates provided in the `templates` folder 
and modify it according to their needs (for details see [below](#)). 
For example, in order to change the instrument of the template above and 
resend the request:

```python
import yaml
request = api.factory.RequestSpec(**yaml.load(open('templates/RequestSpec.yml')))
request['instrument']['code'] = '9984.T'
req_id = api.submit_request(request)
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

## Submitting multiple FTP requests (`request_sender.py`)

The TRTH API `SubmitRequest` function is limited to a single day and single RIC requests. 
Therefore, in request data for multiple RICs and a long period of time (i.e. all trades 
of all stocks in the S&P500 over a period of 5 years), you must call `SubmitFTPRequest` using
a `LargeRequestSpec`.

You can use the **`request_sender.py`** CLI tool to send such requests. 
For detailed usage see the help:
 
 ```bash
 $ tools/request_sender.py --help
 ```
 
You also need to prepare a YAML file to specify which RICs and fields you want to retrieve.
A sample can be found in `tools/sample_criteria.yml`:
 
 ```yaml
TYO_eq:
  ric:
    Exchange: TYO
    RICRegex: '^[0-9]{4}\.T$'
OSA_eqoptions:
  ric:
    Exchange: OSA
    RICRegex: '^J\w*[0-9]\.OS$'
    InstrumentType: 115
  fields:
    - Price
    - Volume
    - Implied Volatility
```

### Example usage:

```bash
$ tools/request_sender.py --config <CONFIG> --criteria <CRITERIA> --template <TEMPLATE> --start 2012-01-01
```

The above will retrieve:
1) Data from stocks listed in the Tokyo Stock Exchange with the fields specified in `<TEMPLATE>`
2) Data from index options listed in the Osaka Stock Exchange with fields overridden by `<CRITERIA>`

See the official TRTH documentation for field/message types information.

## Retrieving data from FTP requests 

FTP requests can be retrieved by two methods:
1) Setting up your own FTP server and having results being pushed (RECOMMENDED) 
2) Downloading from [TRTH HTTP Pull](https://tickhistory.thomsonreuters.com/HttpPull/)

Since setting up you own FTP server is not always possible/straight forward, 
Pytrthree comes with `downloader.py`, a basic tool to download files from HTTP  
using `asyncio`. For detailed usage see the help:
 
 ```bash
 $ tools/downloader.py --help
 ```

## Parsing downloaded files

Pytrthree includes a parser class to help convert downloaded CSV files into [Pandas](http://pandas.pydata.org/)
DataFrames. It is basically a wrapper around `pandas.read_csv`.

```python
from pytrthree import TRTHIterator
for df in TRTHIterator(files):
    # further process DataFrame, insert into database, etc
```

## Contributing

To contribute, fork the repository on GitHub, make your changes and 
submit a pull request :)
Pytrthree is not a mature project yet, so just simply raising issues is 
also greatly appreciated :)
