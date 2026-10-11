"""Static safeguards for an explicitly authorized *future* Windows inventory.

These checks never inspect the host; they only read the tracked PowerShell
script as inert text. Parser and default-plan-only CI run only on ephemeral
GitHub runners, never on the owner's physical Windows device.
"""
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"tools/aion_windows_basic_inventory_readonly_v1.ps1"

class WindowsReadOnlyInventoryProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=SCRIPT.read_text(encoding="utf-8")
        cls.code="\n".join(row.split("#",1)[0] for row in cls.source.splitlines())
    def test_no_flag_plan_precedes_first_host_read(self):
        s=self.code
        self.assertIn("if (-not $AuthorizeReadOnlyInventory.IsPresent)",s)
        self.assertIn("PLAN_ONLY_NO_WINDOWS_READ",self.source)
        self.assertLess(s.index("if (-not $AuthorizeReadOnlyInventory.IsPresent)"),s.index("Get-ItemProperty"))
        self.assertLess(s.index("    return"),s.index("Get-ItemProperty"))
    def test_authorized_read_is_only_exact_os_version_registry_key(self):
        s=self.code
        self.assertEqual(len(re.findall(r"\bGet-ItemProperty\b",s,re.I)),1)
        self.assertIn("HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion",s)
        self.assertIn("-LiteralPath",s)
        self.assertNotIn("-Recurse",s)
        self.assertNotIn("Get-ChildItem",s)
    def test_no_host_identity_or_sensitive_hw_reads(self):
        s=self.code
        forbidden=(
            "Get-CimInstance", "Get-WmiObject", "Get-ComputerInfo",
            "Get-Tpm", "Get-BitLockerVolume", "Get-MpComputerStatus",
            "Get-Item ", "Get-ChildItem", "whoami",
            "Win32_", "Get-LocalUser", "Get-Process",
            "SerialNumber", "MachineGuid", "ProductId",
            "DigitalProductId", "BIOS", "UserName",
            "WindowsIdentity", "WindowsHello", "Credential",
        )
        for term in forbidden:
            with self.subTest(term=term):
                self.assertNotIn(term.lower(),s.lower())
        # The inert plan explicitly says hostname is excluded; that plain
        # word must not be mistaken for actual command execution.
        self.assertIn("hostname", self.source.lower())
        self.assertNotRegex(s, r"(?mi)^\s*(?:&\s*)?hostname(?:\.exe)?(?:\s|;|\||$)")
        self.assertNotRegex(s, r"(?mi)^\s*(?:&\s*)?whoami(?:\.exe)?(?:\s|;|\||$)")
    def test_no_network_or_file_write_execution_commands(self):
        s=self.code
        forbidden=(
            "Invoke-WebRequest","Invoke-RestMethod","Start-BitsTransfer",
            "curl ","wget ","Invoke-Expression","iex ","Start-Process",
            "Set-Item","New-Item","Remove-Item","Out-File","Set-Content",
            "Add-Content","Export-","schtasks","reg.exe","net.exe",
            "winget","msiexec","Install-","Enable-","Set-ExecutionPolicy",
            "Open-","WriteAllText","WriteAllBytes","DownloadFile",
            "Environment]::GetEnvironmentVariable", "$env:",
        )
        for term in forbidden:
            with self.subTest(term=term):
                self.assertNotIn(term.lower(),s.lower())
    def test_no_real_permission_or_go_promotion(self):
        s=self.source
        required=(
            "first_install_status = 'HARD_NO_GO'",
            "installation_authorized = $false",
            "worker_authorized = $false",
            "owner_identity_verified = $false",
            "hardware_attestation_verified = $false",
            "independent_witness_verified = $false",
            "security_capabilities = 'NOT_INSPECTED'",
            "windows_hello = 'NOT_INSPECTED'",
            "tpm = 'NOT_INSPECTED'",
            "bitlocker = 'NOT_INSPECTED'",
            "fido2 = 'NOT_INSPECTED'",
            "network_access_performed = $false",
            "files_written = $false",
        )
        for term in required:
            with self.subTest(term=term):
                self.assertIn(term,s)
    def test_only_explicit_release_switch_and_no_secret_in_output_schema(self):
        s=self.code
        self.assertEqual(s.count("[switch]$AuthorizeReadOnlyInventory"),1)
        self.assertIn("$report | ConvertTo-Json -Depth 2 | Write-Output",s)
        self.assertNotIn("ConvertFrom-SecureString",s)
        for value in ("$env:", "Get-Credential", "ConvertTo-SecureString"):
            self.assertNotIn(value,s)
    def test_static_tests_are_not_device_certification(self):
        s=self.source
        self.assertIn("not an installer",s)
        self.assertIn("after separate owner approval",s)
        self.assertIn("FIRST_INSTALL_HARD_NO_GO",s)

if __name__=="__main__":
    unittest.main()
