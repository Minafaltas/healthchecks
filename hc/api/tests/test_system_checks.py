from __future__ import annotations

from django.test.utils import override_settings

from hc.api.apps import settings_check
from hc.test import BaseTestCase


@override_settings(EMAIL_HOST="localhost")
class SystemChecksCase(BaseTestCase):
    @override_settings(SITE_ROOT="example.com")
    def test_it_validates_site_root_syntax(self) -> None:
        ids = [item.id for item in settings_check(None, None)]
        self.assertEqual(ids, ["hc.api.W001"])

    @override_settings(SITE_ROOT="http://surprise.example.com", ALLOWED_HOSTS=["example.com"])
    def test_it_checks_site_root_host_is_present_in_allowed_hosts(self) -> None:
        ids = [item.id for item in settings_check(None, None)]
        self.assertEqual(ids, ["hc.api.E002"])

    @override_settings(EMAIL_HOST=None)
    def test_it_warns_about_missing_smtp_credentials(self) -> None:
        ids = [item.id for item in settings_check(None, None)]
        self.assertEqual(ids, ["hc.api.W002"])

    @override_settings(SECURE_PROXY_SSL_HEADER="abc")
    def test_it_checks_secure_proxy_ssl_header_tupleness(self) -> None:
        ids = [item.id for item in settings_check(None, None)]
        self.assertEqual(ids, ["hc.api.W005"])
