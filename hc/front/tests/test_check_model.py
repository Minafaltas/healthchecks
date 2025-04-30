# hc/api/tests/test_check_model.py

from __future__ import annotations

from datetime import timedelta as td
from uuid import uuid4

# Ensure freezegun is installed and imported if using freeze_time
# pip install freezegun
from freezegun import freeze_time

from hc.api.models import Check, Ping, Flip # Import necessary models
from hc.test import BaseTestCase # Use the project's base test case
from django.utils.timezone import now

# It's good practice to keep model related tests together
class CheckModelTestCase(BaseTestCase):

    def setUp(self):
        super().setUp()
        # self.project is typically created in BaseTestCase setUp
        # Create a check for use in multiple tests if needed
        self.check = Check(project=self.project)
        # Set other common attributes if needed
        self.check.save()


    @freeze_time("2025-01-01 12:00:00") # Use freeze_time for precise timing
    def test_ping_calculates_and_saves_duration(self):
        """ Test that Ping.duration is saved when start/end pings match by rid. """
        rid = uuid4()

        # Send start ping at 12:00:00
        self.check.ping("", "", "GET", "", b"", "start", rid)
        start_ping_time = now() # Should be 12:00:00

        # Advance time by 5 seconds
        with freeze_time("2025-01-01 12:00:05"):
            # Send success ping with matching rid at 12:00:05
            self.check.ping("", "", "GET", "", b"", "success", rid)
            end_ping_time = now() # Should be 12:00:05

        # Retrieve the completion ping (n=2 if check was fresh)
        ping = Ping.objects.filter(owner=self.check).latest("created")

        self.assertEqual(ping.kind, None) # Success pings have kind=None
        self.assertIsNotNone(ping.duration)
        # Assert exact timedelta now that we use freeze_time
        self.assertEqual(ping.duration, td(seconds=5))

        # Check object's last_duration should also be updated
        self.check.refresh_from_db()
        self.assertIsNotNone(self.check.last_duration)
        self.assertEqual(self.check.last_duration, td(seconds=5))
        # Check last_start was cleared
        self.assertIsNone(self.check.last_start)

    def test_ping_does_not_save_duration_if_rid_mismatches(self):
        """ Test that Ping.duration is None if rids don't match. """
        start_rid = uuid4()
        end_rid = uuid4() # Different RID

        # Use check.ping to properly set last_start_rid
        self.check.ping("", "", "GET", "", b"", "start", start_rid)
        # Send completion ping with different rid
        self.check.ping("", "", "GET", "", b"", "success", end_rid)

        ping = Ping.objects.filter(owner=self.check).latest("created")
        self.assertEqual(ping.kind, None)
        self.assertIsNone(ping.duration) # Duration should be None

        # Check object's last_duration should also be None in this case
        self.check.refresh_from_db()
        self.assertIsNone(self.check.last_duration)
        # last_start should also be cleared because a non-matching success ping arrived
        self.assertIsNone(self.check.last_start)


    def test_ping_does_not_save_duration_if_start_rid_is_missing(self):
        """ Test that Ping.duration is None if start ping had no rid. """
        end_rid = uuid4()

        # Start ping without rid
        self.check.ping("", "", "GET", "", b"", "start", None)
        # Completion ping with rid
        self.check.ping("", "", "GET", "", b"", "success", end_rid)

        ping = Ping.objects.filter(owner=self.check).latest("created")
        self.assertIsNone(ping.duration)
        self.check.refresh_from_db()
        self.assertIsNone(self.check.last_duration)
        # last_start should be cleared as success arrived without matching rid
        self.assertIsNone(self.check.last_start)

    def test_ping_does_not_save_duration_if_end_rid_is_missing(self):
        """ Test that Ping.duration is None if completion ping has no rid. """
        start_rid = uuid4()

        # Start ping with rid
        self.check.ping("", "", "GET", "", b"", "start", start_rid)
        # Completion ping without rid
        self.check.ping("", "", "GET", "", b"", "success", None)

        ping = Ping.objects.filter(owner=self.check).latest("created")
        self.assertIsNone(ping.duration)
        self.check.refresh_from_db()
        self.assertIsNone(self.check.last_duration)
        # last_start should be cleared as success arrived without matching rid
        self.assertIsNone(self.check.last_start)

    @freeze_time("2025-01-01 12:00:00")
    def test_ping_handles_duration_out_of_bounds(self):
        """ Test that pings fail if duration is outside min/max bounds. """
        # IMPORTANT: This test assumes the migrations changing min/max_duration
        # to DurationField have been successfully created and applied.
        check = Check.objects.create(project=self.project)
        check.min_duration = td(seconds=5) # Set bounds using timedelta
        check.max_duration = td(seconds=15) # Set bounds using timedelta
        check.save()

        # --- Test duration BELOW minimum ---
        rid_short = uuid4()
        check.ping("", "", "GET", "", b"", "start", rid_short) # time = 12:00:00
        with freeze_time("2025-01-01 12:00:03"): # 3 seconds later
             check.ping("", "", "GET", "", b"", "success", rid_short)

        ping_short = Ping.objects.filter(owner=check, rid=rid_short).latest("created")
        flip_short = check.flip_set.latest("created") # Flip should exist

        self.assertEqual(ping_short.kind, "fail") # Ping kind should be set to fail
        self.assertEqual(flip_short.reason, "duration") # Flip reason should be duration
        self.assertEqual(flip_short.new_status, "down") # Check status should be down
        self.assertIsNotNone(ping_short.duration) # Duration should still be saved
        self.assertEqual(ping_short.duration, td(seconds=3))
        check.refresh_from_db()
        self.assertEqual(check.status, "down") # Verify check status

        # --- Test duration ABOVE maximum ---
        # Reset check status and last_start for next part
        check.status = "up"
        check.last_start = None
        check.last_start_rid = None
        check.save()

        rid_long = uuid4()
        # Use freeze_time again to reset the clock for the start ping
        with freeze_time("2025-01-01 12:01:00"):
            check.ping("", "", "GET", "", b"", "start", rid_long) # time = 12:01:00

        with freeze_time("2025-01-01 12:01:20"): # 20 seconds later
            check.ping("", "", "GET", "", b"", "success", rid_long)

        ping_long = Ping.objects.filter(owner=check, rid=rid_long).latest("created")
        flip_long = check.flip_set.latest("created")

        self.assertEqual(ping_long.kind, "fail") # Ping kind should be set to fail
        self.assertEqual(flip_long.reason, "duration") # Flip reason should be duration
        self.assertEqual(flip_long.new_status, "down") # Check status should be down
        self.assertIsNotNone(ping_long.duration) # Duration should still be saved
        self.assertEqual(ping_long.duration, td(seconds=20))
        check.refresh_from_db()
        self.assertEqual(check.status, "down")

