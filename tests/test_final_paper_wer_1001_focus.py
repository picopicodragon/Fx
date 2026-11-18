"""FINAL-PAPER-51: Windows WER metadata examination must not leak contents or trade."""
from pathlib import Path
import unittest


class WER1001FocusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=(Path(__file__).resolve().parents[1] /
                    "scripts" / "final_paper_wer_1001_focus_once.ps1").read_text("utf-8")

    def test_uses_bounded_local_application_event_query(self):
        src=self.source
        self.assertIn("Get-WinEvent -FilterHashtable",src)
        self.assertIn("LogName = 'Application'",src)
        self.assertIn("Id = @(1000,1001,1002)",src)
        self.assertIn("-MaxEvents 60",src)
        self.assertIn("GetAttribute('Name')",src)
        self.assertIn("app_family_from_structured_event_fields_only",src)

    def test_redacted_output_and_no_effects(self):
        src=self.source
        for forbidden in ("$event.Message", "$_.Message",
                          "Write-Output $event", "ToXml() |",
                          "Select-Object -ExpandProperty Message",
                          "OrderSend(", "OrderClose(", "OrderModify(",
                          "WebRequest(", "OPENAI_API_KEY", "TYPESAFE_API_KEY",
                          "Remove-Item", "Stop-Process", "Restart-Computer",
                          "new_paid_ai_calls_permitted = $true",
                          "communication_latch_cleared = $true"):
            self.assertNotIn(forbidden,src)
        for required in ("query_status", "NO_MATCH_OR_QUERY_UNAVAILABLE",
                         "specific_python_exit_proven = $false",
                         "root_cause_explained = $false",
                         "communication_latch_cleared = $false",
                         "command_lines_or_full_paths_saved = $false",
                         "[System.IO.FileMode]::CreateNew"):
            self.assertIn(required,src)


if __name__ == "__main__":
    unittest.main()
