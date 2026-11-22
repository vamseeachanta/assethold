"""Mocked scraping tests for the SEC filing fetch-and-parse path.

The scraping path fetches a filing over HTTP (``ReadURLData`` on urllib3),
extracts the embedded ``<XML>`` blocks and parses them into records. These
tests drive that path through the application entry point
(``SECDataForm.get_sec_form_data``) with the HTTP layer replaced by canned
responses. Every test also blocks DNS and socket connects, so an unmocked
request fails the test instead of reaching the network.

Selected in CI by the ``scraping`` marker (Financial Data Integration job).
"""

import json
import socket
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# get_SEC_data does `from sec_edgar_downloader._utils import ...` at import
# time; provide the submodule so the import resolves under the test harness.
sys.modules.setdefault('sec_edgar_downloader', MagicMock())
sys.modules.setdefault('sec_edgar_downloader._utils', MagicMock())

from assethold.common.data import ReadURLData  # noqa: E402
from assethold.modules.stocks import get_SEC_data  # noqa: E402
from assethold.modules.stocks.get_SEC_data import SECDataForm, SECDataTicker  # noqa: E402

pytestmark = pytest.mark.scraping

FILING_URL = 'https://www.sec.gov/Archives/edgar/data/0000000000/0000000000-26-000001.txt'

# Synthetic 13F-HR full submission: a primary document and an information
# table, each wrapped in <XML> ... </XML> lines as in an EDGAR .txt submission.
FULL_SUBMISSION_13F_HR = b"""<SEC-DOCUMENT>
<DOCUMENT>
<TYPE>13F-HR
<TEXT>
<XML>
<edgarSubmission>
  <formData>
    <coverPage>
      <reportCalendarOrQuarter>09-30-2026</reportCalendarOrQuarter>
    </coverPage>
    <signatureBlock>
      <signatureDate>11-01-2026</signatureDate>
    </signatureBlock>
  </formData>
</edgarSubmission>
</XML>
</TEXT>
</DOCUMENT>
<DOCUMENT>
<TYPE>INFORMATION TABLE
<TEXT>
<XML>
<informationTable>
  <infoTable>
    <nameOfIssuer>EXAMPLE CORP A</nameOfIssuer>
    <cusip>000000AA0</cusip>
    <value>1500</value>
  </infoTable>
  <infoTable>
    <nameOfIssuer>EXAMPLE CORP B</nameOfIssuer>
    <cusip>000000BB0</cusip>
    <value>2500</value>
  </infoTable>
</informationTable>
</XML>
</TEXT>
</DOCUMENT>
</SEC-DOCUMENT>
"""


class NetworkBlocked(AssertionError):
    """Raised when a test reaches for the real network."""


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Fail any DNS lookup or socket connect made during a scraping test."""
    attempts = []

    def _blocked(*args, **kwargs):
        attempts.append(args)
        raise NetworkBlocked('live network access attempted in a scraping test')

    monkeypatch.setattr(socket, 'getaddrinfo', _blocked)
    monkeypatch.setattr(socket, 'create_connection', _blocked)
    monkeypatch.setattr(socket.socket, 'connect', _blocked)
    monkeypatch.setattr(get_SEC_data.time, 'sleep', lambda *_: None)
    return attempts


def _canned_response(body):
    return SimpleNamespace(data=body, status=200)


def test_scrape_13f_hr_filing_through_get_sec_form_data():
    """Application path: list filings, fetch the submission, parse holdings."""
    filing = SimpleNamespace(full_submission_url=FILING_URL)
    form = SECDataForm()
    cfg_sec = {
        'filing_type': '13F-HR',
        'include_amends': False,
        'after_date': None,
        'before_date': None,
        'num_filings_to_download': 1,
    }

    with patch.object(get_SEC_data, 'get_filing_urls_to_download',
                      return_value=[filing]) as list_filings, \
            patch.object(get_SEC_data.read_url.http_connection, 'request',
                         return_value=_canned_response(FULL_SUBMISSION_13F_HR)) as request:
        result = form.get_sec_form_data('EXMP', cfg_sec)

    list_filings.assert_called_once()
    assert list_filings.call_args.args[:2] == ('13F-HR', 'EXMP')
    request.assert_called_once_with('GET', FILING_URL)

    assert isinstance(result, dict), 'parser failure leaves an empty DataFrame'
    assert result['reportCalendarOrQuarter'] == '09-30-2026'
    assert result['signatureDate'] == '11-01-2026'
    holdings = json.loads(result['infoTable'])
    assert [h['cusip'] for h in holdings] == ['000000AA0', '000000BB0']
    assert [h['value'] for h in holdings] == ['1500', '2500']


def test_scrape_failed_fetch_leaves_empty_result():
    """A fetch error is logged and yields an empty frame, not an exception."""
    filing = SimpleNamespace(full_submission_url=FILING_URL)
    cfg_sec = {'filing_type': '13F-HR', 'num_filings_to_download': 1}

    with patch.object(get_SEC_data, 'get_filing_urls_to_download',
                      return_value=[filing]), \
            patch.object(get_SEC_data.read_url.http_connection, 'request',
                         side_effect=OSError('connection reset')):
        result = SECDataForm().get_sec_form_data('EXMP', cfg_sec)

    assert hasattr(result, 'empty') and result.empty


def test_scrape_company_tickers_returns_response_body():
    """SECDataTicker returns the raw JSON body from the tickers endpoint."""
    body = b'{"0": {"cik_str": 1, "ticker": "EXMP", "title": "EXAMPLE CORP"}}'

    with patch.object(get_SEC_data.read_url.http_connection, 'request',
                      return_value=_canned_response(body)) as request:
        data = SECDataTicker().get_company_tickers()

    request.assert_called_once_with('GET', 'https://www.sec.gov/files/company_tickers.json')
    assert json.loads(data)['0']['ticker'] == 'EXMP'


def test_scrape_xml_endpoint_parsed_to_dict():
    """ReadURLData.get_xml_data_as_dict parses a canned XML response."""
    reader = ReadURLData({})
    xml = b'<feed><entry><title>Form 4</title></entry></feed>'

    with patch.object(reader.http_connection, 'request',
                      return_value=_canned_response(xml)):
        data = reader.get_xml_data_as_dict({'url': FILING_URL})

    assert data == {'feed': {'entry': {'title': 'Form 4'}}}


def test_scrape_unmocked_request_is_blocked(no_network):
    """Guard check: an unmocked fetch hits the block and returns no data."""
    reader = ReadURLData({})

    data = reader.get_response_data({'url': FILING_URL})

    assert data is None
    assert no_network, 'the request did not reach the network guard'
