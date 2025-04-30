# hc/api/tests/test_check_model.py
from datetime import timedelta as td
from uuid import uuid4

from hc.api.models import Check, Ping
from hc.test import BaseTestCase # Assuming BaseTestCase exists
from django.utils.timezone import now

class CheckModelTestCase(BaseTestCase): # Or add to existing class

    def test_ping_calculates_and_saves_duration(self):
        check = Check.objects.create(project=self.project)
        rid = uuid4()
        start_time = now()

        # Send start ping
        check.ping("", "", "GET", "", b"", "start", rid)

        # Wait a bit
        end_time = start_time + td(seconds=5)
        with self.settings(NOW=end_time): # Use freeze_time if available, otherwise adjust timing
            # Send success ping with matching rid
            check.ping("", "", "GET", "", b"", "success", rid)

        # Retrieve the completion ping (should be the last one)
        ping = Ping.objects.filter(owner=check).latest("created")

        self.assertEqual(ping.kind, None) # Success pings have kind=None
        self.assertIsNotNone(ping.duration)
        # Allow for slight timing differences if not using freeze_time
        self.assertAlmostEqual(ping.duration.total_seconds(), 5.0, delta=0.1)

        # Check object's last_duration should also be updated
        check.refresh_from_db()
        self.assertIsNotNone(check.last_duration)
        self.assertAlmostEqual(check.last_duration.total_seconds(), 5.0, delta=0.1)

    def test_ping_does_not_save_duration_if_rid_mismatches(self):
        check = Check.objects.create(project=self.project)
        start_rid = uuid4()
        end_rid = uuid4() # Different RID

        check.ping("", "", "GET", "", b"", "start", start_rid)
        check.ping("", "", "GET", "", b"", "success", end_rid)

        ping = Ping.objects.filter(owner=check).latest("created")
        self.assertEqual(ping.kind, None)
        self.assertIsNone(ping.duration) # Duration should be None

        check.refresh_from_db()
        self.assertIsNone(check.last_duration) # Check's last_duration should also be None

    def test_ping_handles_duration_out_of_bounds(self):
        check = Check.objects.create(project=self.project)
        # Set bounds: min 5s, max 15s
        check.min_duration = td(seconds=5)
        check.max_duration = td(seconds=15)
        check.save()

        rid = uuid4()
        start_time = now()

        # --- Test duration BELOW minimum ---
        check.ping("", "", "GET", "", b"", "start", rid)
        end_time_short = start_time + td(seconds=3)
        with self.settings(NOW=end_time_short):
             check.ping("", "", "GET", "", b"", "success", rid)

        ping_short = Ping.objects.filter(owner=check, rid=rid).latest("created")
        flip_short = check.flip_set.latest("created")

        self.assertEqual(ping_short.kind, "fail") # Should be marked as fail
        self.assertEqual(flip_short.reason, "duration") # Reason should be duration
        self.assertIsNotNone(ping_short.duration)
        self.assertAlmostEqual(ping_short.duration.total_seconds(), 3.0, delta=0.1)

        # --- Test duration ABOVE maximum ---
        # Reset last_start manually for the next test part
        check.last_start = None
        check.last_start_rid = None
        check.save()

        rid2 = uuid4()
        start_time_2 = now()
        check.ping("", "", "GET", "", b"", "start", rid2)
        end_time_long = start_time_2 + td(seconds=20)
        with self.settings(NOW=end_time_long):
            check.ping("", "", "GET", "", b"", "success", rid2)

        ping_long = Ping.objects.filter(owner=check, rid=rid2).latest("created")
        flip_long = check.flip_set.latest("created")

        self.assertEqual(ping_long.kind, "fail") # Should be marked as fail
        self.assertEqual(flip_long.reason, "duration") # Reason should be duration
        self.assertIsNotNone(ping_long.duration)
        self.assertAlmostEqual(ping_long.duration.total_seconds(), 20.0, delta=0.1)