"""Unit tests for the Zero-Click Job Alert Pipeline."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from config import TARGET_ROLES
from pipeline import (
    build_telegram_digest,
    check_sponsorship_disqualification,
    clean_html_tags,
    escape_html,
    generate_job_id,
    is_location_eligible,
    load_seen_jobs,
    match_target_role,
    save_seen_jobs,
)


class TestJobPipeline(unittest.TestCase):

    def test_location_eligibility(self):
        # Strict rejection of non-US locations (like Spain, Europe, UK, etc.)
        non_us_locations = [
            "Spain",
            "Docplanner - Spain",
            "Madrid, Spain",
            "Europe",
            "London, UK",
            "United Kingdom",
            "EMEA",
            "Germany",
            "Berlin, Germany",
            "India",
            "Brazil",
            "APAC",
        ]
        for loc in non_us_locations:
            ok, reason = is_location_eligible(loc)
            self.assertFalse(ok, f"Expected non-US location '{loc}' to be rejected, got reason: {reason}")

        # Eligible US locations
        us_locations = [
            "USA",
            "United States",
            "Remote - US",
            "Remote (USA)",
            "North America",
            "Canada, USA",
            "Europe, USA, Canada",
            "Worldwide",
        ]
        for loc in us_locations:
            ok, reason = is_location_eligible(loc)
            self.assertTrue(ok, f"Expected US-eligible location '{loc}' to be accepted, got reason: {reason}")

    def test_role_matching(self):
        self.assertTrue(match_target_role("Senior Data Scientist"))
        self.assertTrue(match_target_role("Lead Analytics Engineer"))
        self.assertTrue(match_target_role("Decision Scientist II"))
        self.assertTrue(match_target_role("Machine Learning Engineer - NLP"))
        self.assertFalse(match_target_role("Front-end React Developer"))
        self.assertFalse(match_target_role("Office Receptionist"))
        self.assertFalse(match_target_role(""))

    def test_visa_exclusion_detection(self):
        disqualifying_texts = [
            "We will not sponsor applicants for work visas.",
            "Candidate must have permanent work authorization; no visa sponsorship provided.",
            "This position is open to US citizens without sponsorship.",
            "Sponsorship is not available for this role.",
            "Applicants must be a US citizen or permanent resident.",
            "US Citizen or Green Card only due to export regulations.",
            "We are unable to sponsor any visas at this time.",
            "Security clearance required.",
        ]
        for sample in disqualifying_texts:
            excluded, pattern = check_sponsorship_disqualification(sample)
            self.assertTrue(
                excluded,
                f"Failed to detect disqualification in: '{sample}'",
            )
            self.assertIsNotNone(pattern)

        qualifying_texts = [
            "We offer comprehensive visa sponsorship including H1-B transfers.",
            "Open to global applicants with work authorization.",
            "We sponsor top talent worldwide.",
            "Equal Opportunity Employer. All qualified applicants will receive consideration.",
        ]
        for sample in qualifying_texts:
            excluded, pattern = check_sponsorship_disqualification(sample)
            self.assertFalse(
                excluded,
                f"False positive on qualifying text: '{sample}'",
            )

    def test_html_cleaning_and_escaping(self):
        raw_html = "<p>Role requires <b>Python</b> &amp; SQL.</p>"
        cleaned = clean_html_tags(raw_html)
        self.assertEqual(cleaned.strip(), "Role requires  Python  & SQL.")

        raw_company = "AT&T <Data Team>"
        escaped = escape_html(raw_company)
        self.assertEqual(escaped, "AT&amp;T &lt;Data Team&gt;")

    def test_job_id_generation(self):
        id1 = generate_job_id("Stripe", "Data Scientist", "https://stripe.com/job/1")
        id2 = generate_job_id("Stripe", "Data Scientist", "https://stripe.com/job/1")
        id3 = generate_job_id("Netflix", "Data Scientist", "https://netflix.com/job/2")

        self.assertEqual(id1, id2)
        self.assertNotEqual(id1, id3)
        self.assertEqual(len(id1), 16)

        explicit = generate_job_id("Stripe", "DS", "https://stripe.com", explicit_id="job_9988")
        self.assertEqual(explicit, "job_9988")

    def test_seen_jobs_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "seen_test.json"
            
            # Initial load should be empty
            seen = load_seen_jobs(cache_file)
            self.assertEqual(seen, {})

            # Save seen entries
            seen["job_1"] = {"title": "Data Scientist", "company": "Acme"}
            save_seen_jobs(seen, cache_file)

            # Reload and verify
            reloaded = load_seen_jobs(cache_file)
            self.assertIn("job_1", reloaded)
            self.assertEqual(reloaded["job_1"]["company"], "Acme")

    def test_telegram_digest_formatting(self):
        sample_jobs = [
            {
                "title": "Senior Data Scientist",
                "company": "Spotify",
                "location": "Remote - US",
                "apply_url": "https://spotify.com/apply/123",
            },
            {
                "title": "Analytics Engineer",
                "company": "Shopify",
                "location": "Remote",
                "apply_url": "https://shopify.com/apply/456",
            },
        ]
        chunks = build_telegram_digest(sample_jobs)
        self.assertEqual(len(chunks), 1)
        self.assertIn("Spotify", chunks[0])
        self.assertIn("Tap to 1-Click Apply", chunks[0])
        self.assertIn("href=\"https://spotify.com/apply/123\"", chunks[0])


if __name__ == "__main__":
    unittest.main()
