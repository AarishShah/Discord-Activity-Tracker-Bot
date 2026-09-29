import unittest
from datetime import datetime
import pytz
from config.settings import IST
from services.stats_service import StatsService

class MockMember:
    def __init__(self, id, name, display_name):
        self.id = id
        self.name = name
        self.display_name = display_name
        self.bot = False

class MockGuild:
    def __init__(self, id, name):
        self.id = id
        self.name = name

class TestMonthlyStats(unittest.TestCase):
    def test_previous_month_range_standard(self):
        # When reference date is September 1, 2026
        ref_dt = datetime(2026, 9, 1, 6, 0, 0, tzinfo=IST)
        start_str, end_str, month_name, start_dt, end_dt = StatsService.get_previous_month_range(ref_dt)
        self.assertEqual(start_str, "2026-08-01")
        self.assertEqual(end_str, "2026-08-31")
        self.assertEqual(month_name, "August 2026")

    def test_previous_month_range_january_boundary(self):
        # When reference date is January 1, 2026 (year rollover)
        ref_dt = datetime(2026, 1, 1, 6, 0, 0, tzinfo=IST)
        start_str, end_str, month_name, start_dt, end_dt = StatsService.get_previous_month_range(ref_dt)
        self.assertEqual(start_str, "2025-12-01")
        self.assertEqual(end_str, "2025-12-31")
        self.assertEqual(month_name, "December 2025")

    def test_previous_month_range_leap_year(self):
        # When reference date is March 1, 2024 (leap year February)
        ref_dt = datetime(2024, 3, 1, 6, 0, 0, tzinfo=IST)
        start_str, end_str, month_name, start_dt, end_dt = StatsService.get_previous_month_range(ref_dt)
        self.assertEqual(start_str, "2024-02-01")
        self.assertEqual(end_str, "2024-02-29")
        self.assertEqual(month_name, "February 2024")

    def test_format_dynamic_duration(self):
        # Test 170 hours -> "7 days (170 hours)"
        self.assertEqual(StatsService.format_dynamic_duration(170 * 3600), "7 days (170 hours)")
        # Test 36 hours -> "1 day (36 hours)"
        self.assertEqual(StatsService.format_dynamic_duration(36 * 3600), "1 day (36 hours)")
        # Test 26 hours -> "1 day (26 hours)"
        self.assertEqual(StatsService.format_dynamic_duration(26 * 3600), "1 day (26 hours)")
        # Test 24 hours -> "1 day (24 hours)"
        self.assertEqual(StatsService.format_dynamic_duration(24 * 3600), "1 day (24 hours)")
        # Test 48 hours -> "2 days (48 hours)"
        self.assertEqual(StatsService.format_dynamic_duration(48 * 3600), "2 days (48 hours)")
        # Test 23 hours -> "23 hours"
        self.assertEqual(StatsService.format_dynamic_duration(23 * 3600), "23 hours")
        # Test 1 hour -> "1 hour"
        self.assertEqual(StatsService.format_dynamic_duration(1 * 3600), "1 hour")
        # Test 45 minutes -> "45 mins"
        self.assertEqual(StatsService.format_dynamic_duration(45 * 60), "45 mins")
        # Test 1 minute -> "1 min"
        self.assertEqual(StatsService.format_dynamic_duration(60), "1 min")
        # Test 0 seconds -> "0 hours"
        self.assertEqual(StatsService.format_dynamic_duration(0), "0 hours")
        # Test None / negative -> "0 hours"
        self.assertEqual(StatsService.format_dynamic_duration(-10), "0 hours")
        self.assertEqual(StatsService.format_dynamic_duration(None), "0 hours")

    def test_format_date(self):
        self.assertEqual(StatsService._format_date("2026-08-10"), "Monday, 10 August 2026")
        self.assertEqual(StatsService._format_date("2026-08-21"), "Friday, 21 August 2026")
        self.assertEqual(StatsService._format_date("2026-08-01"), "Saturday, 1 August 2026")

    def test_truncate_field_value(self):
        self.assertEqual(StatsService._truncate_field_value([]), "None")
        items = ["Monday, 10 August 2026", "Friday, 21 August 2026"]
        expected = "1. Monday, 10 August 2026\n2. Friday, 21 August 2026"
        self.assertEqual(StatsService._truncate_field_value(items), expected)

    def test_build_monthly_stats_embed(self):
        user = MockMember(12345, "testuser", "Test User")
        guild = MockGuild(99999, "Alpha HQ")
        stats_data = {
            "absences": ["Monday, 10 August 2026", "Friday, 21 August 2026"],
            "half_days": ["Wednesday, 12 August 2026"],
            "regular_seconds": 170 * 3600,
            "overtime_seconds": 26 * 3600,
            "regular_formatted": "7 days (170 hours)",
            "overtime_formatted": "1 day (26 hours)"
        }
        ref_dt = datetime(2026, 9, 1, 6, 0, 0, tzinfo=IST)
        embed = StatsService.build_monthly_stats_embed(user, guild, "August 2026", stats_data, generated_at=ref_dt)

        self.assertEqual(embed.title, "Monthly Attendance & Activity Stats | August 2026")
        self.assertIn("Alpha HQ", embed.description)
        self.assertEqual(embed.color.value, 5814783)

        fields_dict = {f.name: f for f in embed.fields}
        self.assertIn("Absences (2)", fields_dict)
        self.assertEqual(fields_dict["Absences (2)"].value, "1. Monday, 10 August 2026\n2. Friday, 21 August 2026")
        self.assertFalse(fields_dict["Absences (2)"].inline)

        self.assertIn("Half Days (1)", fields_dict)
        self.assertEqual(fields_dict["Half Days (1)"].value, "1. Wednesday, 12 August 2026")
        self.assertFalse(fields_dict["Half Days (1)"].inline)

        self.assertIn("Total Voice Time", fields_dict)
        self.assertEqual(fields_dict["Total Voice Time"].value, "7 days (170 hours)")
        self.assertTrue(fields_dict["Total Voice Time"].inline)

        self.assertIn("Voice Overtime", fields_dict)
        self.assertEqual(fields_dict["Voice Overtime"].value, "1 day (26 hours)")
        self.assertTrue(fields_dict["Voice Overtime"].inline)

        self.assertEqual(embed.footer.text, "Generated on 01-Sep-2026 06:00 AM")

if __name__ == "__main__":
    unittest.main()
