import re
import functools
from collections import OrderedDict
from functools import partialmethod as pm
from typing import Optional

from lxml import etree
from zeep import Client, Plugin
from zeep.exceptions import Fault
from zeep.helpers import serialize_object

from . import utils


class TRTH:
    """A Pythonic wrapper for the TRTH API based on Zeep."""

    TRTH_VERSION = '5.8'
    TRTH_WSDL_URL = f'https://trth-api.thomsonreuters.com/TRTHApi-{TRTH_VERSION}/wsdl/TRTHApi.wsdl'

    def __init__(self, config=None):
        self.config = utils.load_config(config)
        self.logger = utils.make_logger('pytrthree', self.config)
        self.options = dict(debug=False, target_cls=dict, raise_exception=False,
                            input_parser=True, output_parser=True)
        self.plugin = DebugPlugin(self)
        self.client = Client(self.TRTH_WSDL_URL, strict=True, plugins=[self.plugin])
        self.factory = self.client.type_factory('ns0')
        self.header = self.make_credentials()
        self.signatures = self._parse_signatures()
        self._make_docstring()
        self.client.set_default_soapheaders(self.header)
        self.logger.info('TRTH API initialized.')

    def __getattr__(self, item):
        try:
            return self.__dict__[item]
        except KeyError:
            return self.options[item]

    def _parse_signatures(self):
        """Parses API functions signature from WSDL document"""
        signatures = {}
        for service in self.client.wsdl.services.values():
            for port in service.ports.values():
                for op in port.binding._operations.values():
                    input_sig = re.sub("{[^}]*}", '', op.input.body.signature())
                    output_sig = re.sub("{[^}]*}", '', op.output.body.signature())
                    input_sig = re.sub('\w+\(|\)', '', input_sig)
                    output_sig = re.sub('\w+\(|\)', '', output_sig)
                    signatures[op.name] = (input_sig, output_sig)
        return signatures

    def _make_docstring(self):
        """Dynamically generates docstrings for API function partials"""

        def formatter(func_name):
            indent = ' ' * 8 + '\n'
            input_sig, output_sig = self.signatures[func_name]
            output_sig = re.sub('\w+: ', '', output_sig) if output_sig else None
            signature = f'{indent}{func_name}({input_sig}) --> {output_sig}'
            reference = ('See TRTH API User Guide for further documentation: '
                         'https://tickhistory.thomsonreuters.com/\n')
            params = indent.join([':param {}'.format(i) for i in input_sig.split(', ') if i])
            ret = f'{indent}:return: {output_sig}'
            docstring = '\n'.join([signature, reference, params, ret])
            docstring = re.sub(r'\n\s*\n', '\n', docstring)
            return lambda: print(signature.strip()), docstring

        for attr in dir(self):
            obj = getattr(self, attr)
            if isinstance(obj, functools.partial):
                new_obj = functools.update_wrapper(obj, self._wrap)
                func = obj.keywords['function']
                new_obj.signature, new_obj.__doc__ = formatter(func)
                setattr(self, attr, new_obj)

    def make_credentials(self):
        """
        Does initial authentication with the TRTH API
        and generates unique token used in subsequent API requests.
        """
        self.logger.info('Making credentials.')
        credentials = self.factory.CredentialsHeader(tokenId='', **self.config['credentials'])
        header = {'CredentialsHeader': credentials}

        # Dummy request to get tokenId
        response = self.client.service.GetVersion(_soapheaders=header)
        header = {'CredentialsHeader': response.header.CredentialsHeader}

        self.logger.info(f'Username: {response.header.CredentialsHeader.username}')
        self.logger.info(f'Token ID: {response.header.CredentialsHeader.tokenId}')
        return header

    def _wrap(self, *args, function=None, **kwargs) -> Optional[dict]:
        """
        Wrapper for TRTH API functions.
        :param function: Wrapped TRTH API function string name
        :param args: API function arguments
        :param kwargs: API function arguments
        """
        if function is None:
            raise ValueError('API function not specified')
        if self.debug:
            print(self.signatures[function])
        input_type, output_type = self.signatures[function]
        params = self._parse_params(args, kwargs, input_type)
        try:
            f = getattr(self.client.service, function)
            resp = f(**params)
            return self._parse_response(resp, output_type)
        except Fault as fault:
            if self.raise_exception:
                raise fault
            else:
                self.logger.error(fault)

    def _parse_params(self, args, kwargs, input_type):
        """
        Uses util parser functions so that the user doesn't have to manually instanciate
        `self.factory` classes. Also provides reasonable default values for some types.
        Can be disabled by editing `self.options`.
        :param args: API function arguments passed by the user
        :param kwargs: API function arguments passed by the user
        :param input_type: API function input signataure
        :return: Parsed/filled function input parameter dictionary
        """

        # Parsing args and kwargs into an OrderedDict
        params = re.findall('(\w+): (\w*:?\w+)', input_type)
        params = OrderedDict([(name, [typ, None]) for name, typ in params])
        for name, value in zip(params, args):
            params[name][1] = value
        for name, value in kwargs.items():
            params[name][1] = value

        # Calling parser functions for each data type
        if self.input_parser:
            for name, (typ, value) in params.items():
                try:
                    parser = getattr(utils, f'make_{typ}')
                    params[name][1] = parser(value, self.factory)
                except AttributeError:
                    pass

        return {k: v[1] for k, v in params.items()}

    def _parse_response(self, resp, output_type):
        """
        Uses util parser functions in order to return response in a
        less verbose and more more user-friendly format.
        Can be disabled/customized by editing `self.options`.
        :param resp: Zeep response object
        :param output_type: API function output signataure
        :return: Parsed dictionary/DataFrameresponse
        """
        output_type = output_type.split(': ')[-1]
        if self.target_cls is None:
            return resp
        else:
            resp = serialize_object(resp.body, target_cls=self.target_cls)

        # Calling parser functions for data type
        if self.output_parser:
            try:
                parser = getattr(utils, f'parse_{output_type}')
                resp = parser(resp)
            except AttributeError:
                pass
        return resp

    # # Quota and permissions
    get_look_back_period = pm(_wrap, function='GetLookBackPeriod')
    get_quota = pm(_wrap, function='GetQuota')
    get_ric_list = pm(_wrap, function='GetRICList')
    get_used_instruments = pm(_wrap, function='GetUsedInstruments')

    # Instrument details
    expand_chain = pm(_wrap, function='ExpandChain')
    get_ric_symbology = pm(_wrap, function='GetRICSymbology')
    search_rics = pm(_wrap, function='SearchRICs')
    verify_rics = pm(_wrap, function='VerifyRICs')

    # Request instrument data directly
    submit_request = pm(_wrap, function='SubmitRequest')
    clean_up = pm(_wrap, function='CleanUp')

    # Request instrument data using HTTP/FTP
    set_ftp_details = pm(_wrap, function='SetFTPDetails')
    test_ftp = pm(_wrap, function='TestFTP')
    submit_ftp_request = pm(_wrap, function='SubmitFTPRequest')

    # Retrieving requested data
    get_status = pm(_wrap, function='GetInflightStatus')
    cancel_request = pm(_wrap, function='CancelRequest')
    get_request_result = pm(_wrap, function='GetRequestResult')

    # Speed Guide
    get_page = pm(_wrap, function='GetPage')
    get_snapshot_info = pm(_wrap, function='GetSnapshotInfo')
    search_page = pm(_wrap, function='SearchPage')

    # Data dictionary
    get_asset_domains = pm(_wrap, function='GetAssetDomains')
    get_bond_types = pm(_wrap, function='GetBondTypes')
    get_countries = pm(_wrap, function='GetCountries')
    get_credit_ratings = pm(_wrap, function='GetCreditRatings')
    get_currencies = pm(_wrap, function='GetCurrencies')
    get_exchanges = pm(_wrap, function='GetExchanges')
    get_option_expiry_months = pm(_wrap, function='GetOptionExpiryMonths')
    get_futures_delivery_months = pm(_wrap, function='GetFuturesDeliveryMonths')
    get_instrument_types = pm(_wrap, function='GetInstrumentTypes')
    get_restricted_pes = pm(_wrap, function='GetRestrictedPEs')
    get_message_types = pm(_wrap, function='GetMessageTypes')
    get_version = pm(_wrap, function='GetVersion')


class DebugPlugin(Plugin):
    def __init__(self, parent):
        self.parent = parent

    def egress(self, envelope, http_headers, operation, binding_options):
        if self.parent.debug:
            print(operation)
            print(http_headers)
            print(etree.tostring(envelope, pretty_print=True).decode('utf-8'))
        return envelope, http_headers

    def ingress(self, envelope, http_headers, operation):
        if self.parent.debug:
            print(operation)
            print(http_headers)
            print(etree.tostring(envelope, pretty_print=True).decode('utf-8'))
        return envelope, http_headers
