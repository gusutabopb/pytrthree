import re
import functools
from functools import partialmethod as pm
from typing import Any, Callable, Optional

from lxml import etree
from zeep import Client, Plugin
from zeep.exceptions import Fault
from zeep.helpers import serialize_object

from . import utils

logger = utils.make_logger(__name__)


class TRTH(object):
    """A Pythonic wrapper for the TRTH API based on Zeep."""

    TRTH_VERSION = '5.8'
    TRTH_WSDL_URL = f'https://trth-api.thomsonreuters.com/TRTHApi-{TRTH_VERSION}/wsdl/TRTHApi.wsdl'

    def __init__(self, config=None):
        self.config = utils.load_config(config)
        self._debug = False
        self.plugin = DebugPlugin(self._debug)
        self.client = Client(self.TRTH_WSDL_URL, strict=True, plugins=[self.plugin])
        self.factory = self.client.type_factory('ns0')
        self.header = self.make_credentials()
        self.signatures = self._parse_signatures(self.client)
        self._make_docstring()
        # self.client.set_default_soapheaders(self.header)
        logger.info('TRTH API initialized.')

    @property
    def debug(self):
        return self._debug

    @debug.setter
    def debug(self, value):
        self._debug = value
        self.plugin.debug = value

    @staticmethod
    def _parse_signatures(client):
        """Parses API functions signature from WSDL document"""
        signatures = {}
        for service in client.wsdl.services.values():
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
            return signature, docstring

        for attr in dir(self):
            obj = getattr(self, attr)
            if isinstance(obj, functools.partial):
                new_obj = functools.update_wrapper(obj, self._wrap)
                func_name = obj.keywords['function']
                new_obj.signature, new_obj.__doc__ = formatter(func_name)
                setattr(self, attr, new_obj)

    def make_credentials(self):
        """
        Does initial authentication with the TRTH API
        and generates unique token used in subsequent API requests.
        """
        logger.info('Making credentials.')
        credentials = self.factory.CredentialsHeader(**self.config['credentials'], tokenId='')
        header = {'CredentialsHeader': credentials}

        # Dummy request to get tokenId
        response = self.client.service.GetVersion(_soapheaders=header)
        header = {'CredentialsHeader': response.header.CredentialsHeader}

        logger.info(f'Username: {response.header.CredentialsHeader.username}')
        logger.info(f'Token ID: {response.header.CredentialsHeader.tokenId}')
        return header

    def _wrap(self, *args, function=None, **kwargs) -> Callable[[Any], Optional[dict]]:
        """
        Wrapper for TRTH API functions. For function signature see show_signature.
        :param function: Wrapped TRTH API function string name
        :param args: API function arguments
        :param kwargs: API function arguments
        """
        if function is None:
            raise ValueError('API function not specified')
        if self.debug:
            print(self.signatures[function])
        f = getattr(self.client.service, function)
        try:
            resp = f(_soapheaders=self.header, *args, **kwargs)
            return serialize_object(resp.body, target_cls=dict)
        except Fault as fault:
            if self.debug:
                raise fault
            else:
                logger.error(fault)

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
    def __init__(self, debug):
        self.debug = debug

    def egress(self, envelope, http_headers, operation, binding_options):
        if self.debug:
            print(operation)
            print(http_headers)
            print(etree.tostring(envelope, pretty_print=True).decode('utf-8'))
        return envelope, http_headers

    def ingress(self, envelope, http_headers, operation):
        if self.debug:
            print(operation)
            print(http_headers)
            print(etree.tostring(envelope, pretty_print=True).decode('utf-8'))
        return envelope, http_headers
