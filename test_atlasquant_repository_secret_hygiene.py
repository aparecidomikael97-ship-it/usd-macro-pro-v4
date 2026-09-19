import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent
TEXT_SUFFIXES={".py",".yml",".yaml",".json",".md",".html",".js",".toml",".txt",".pine"}
SKIP_TOP={".git","dados",".atlasquant_research","__pycache__",".venv","venv"}
PATTERNS={
    "github_classic_pat":re.compile(r"ghp_[A-Za-z0-9]{30,}"),
    "github_fine_grained_pat":re.compile(r"github_pat_[A-Za-z0-9_]{35,}"),
    "openai_style_secret":re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    "aws_access_key":re.compile(r"AKIA[0-9A-Z]{16}"),
    "private_key_block":re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}
FORBIDDEN_PATHS={
    ".env",
    ".streamlit/secrets.toml",
    "secrets.toml",
}


class AtlasQuantRepositorySecretHygieneTests(unittest.TestCase):
    def test_no_committed_secret_files_or_private_keys(self):
        bad_paths=[]
        findings=[]
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            rel=path.relative_to(ROOT)
            rel_text=rel.as_posix()
            if rel.parts and rel.parts[0] in SKIP_TOP:
                continue
            lower=rel_text.lower()
            if lower in FORBIDDEN_PATHS or lower.startswith(".env."):
                if lower!=".env.example":
                    bad_paths.append(rel_text)
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            try:
                text=path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for name,pattern in PATTERNS.items():
                if pattern.search(text):
                    findings.append((rel_text,name))
        self.assertEqual(bad_paths,[],f"Committed secret-like paths: {bad_paths}")
        self.assertEqual(findings,[],f"Credential-like literals found: {findings}")

    def test_workflows_only_reference_secrets_symbolically(self):
        workflow_dir=ROOT/".github"/"workflows"
        for path in workflow_dir.glob("*.yml"):
            text=path.read_text(encoding="utf-8")
            with self.subTest(path=path.name):
                self.assertNotRegex(text,PATTERNS["github_classic_pat"])
                self.assertNotRegex(text,PATTERNS["github_fine_grained_pat"])
                self.assertNotRegex(text,PATTERNS["private_key_block"])


if __name__=="__main__":
    unittest.main()
