"""A157 emergency main-targeted PR: 24 YAML mutations, NO real workflow action."""
import unittest
from tools.aion_p0_a157_main_hardstop_review_lab import (
    WORKFLOWS, POLICY, check_source, audit
)
F="$"+"{{ false }}"
T="$"+"{{ true }}"

def read(name):
    return (WORKFLOWS/name).read_text(encoding="utf-8")


class A157MainEmergencyHardstopLab(unittest.TestCase):
    def check(self,name,source,accept):
        report=check_source(name,source)
        self.assertIs(report["source_pinned"],accept,report)
        self.assertIn("HARD_NO_GO",report["verdict"])
        if not accept:
            self.assertTrue(report["findings"])
        self.assertIs(report.get("real_write_authorized",False),False)

    def test_01_autopilot_current_source_pinned(self):
        self.check("autopilot-v107.yml",read("autopilot-v107.yml"),True)

    def test_02_coleta_current_source_pinned(self):
        self.check("coleta_automatica.yml",read("coleta_automatica.yml"),True)

    def test_03_bootstrap_current_source_pinned(self):
        self.check("aion-runtime-checkpoint-bootstrap.yml",read("aion-runtime-checkpoint-bootstrap.yml"),True)

    def test_04_migrate_current_source_pinned(self):
        self.check("aion-runtime-checkpoint-migrate.yml",read("aion-runtime-checkpoint-migrate.yml"),True)

    def test_05_source_checkpoint_readonly_artifact(self):
        self.check("atlasquant-checkpoint.yml",read("atlasquant-checkpoint.yml"),True)

    def test_06_source_backup_readonly_artifact(self):
        self.check("atlasquant-source-backup.yml",read("atlasquant-source-backup.yml"),True)


MUTANTS=[
    ("autopilot-v107.yml","extra_job"),
    ("coleta_automatica.yml","extra_job"),
    ("aion-runtime-checkpoint-bootstrap.yml","extra_job"),
    ("aion-runtime-checkpoint-migrate.yml","extra_job"),
    ("autopilot-v107.yml","job_if_true"),
    ("coleta_automatica.yml","job_if_true"),
    ("aion-runtime-checkpoint-bootstrap.yml","job_if_true"),
    ("aion-runtime-checkpoint-migrate.yml","job_if_true"),
    ("autopilot-v107.yml","workflow_write"),
    ("coleta_automatica.yml","workflow_write"),
    ("autopilot-v107.yml","job_write"),
    ("coleta_automatica.yml","job_write"),
    ("atlasquant-checkpoint.yml","credentials_persist"),
    ("atlasquant-source-backup.yml","credentials_persist"),
    ("autopilot-v107.yml","duplicate_job_if"),
    ("coleta_automatica.yml","duplicate_job_if"),
    ("atlasquant-checkpoint.yml","backup_http_put"),
    ("atlasquant-source-backup.yml","backup_git_push"),
]
assert len(MUTANTS)==18


def mutate(name,original,kind):
    if kind=="extra_job":
        return original+"\n  rogue:\n    runs-on: ubuntu-latest\n    steps:\n      - run: gh api --method PUT repo\n"
    if kind=="job_if_true":
        return original.replace("    if: "+F,"    if: "+T,1)
    if kind=="workflow_write":
        return original.replace("  contents: read","  contents: write",1)
    if kind=="job_write":
        return original.replace("    runs-on: ubuntu-latest",
                                "    permissions:\n      contents: write\n    runs-on: ubuntu-latest",1)
    if kind=="credentials_persist":
        return original.replace("persist-credentials: false","persist-credentials: true",1)
    if kind=="duplicate_job_if":
        return original.replace("    if: "+F,"    if: "+F+"\n    if: "+T,1)
    if kind=="backup_http_put":
        return original.replace('          print(f"Created: {out}")',
                                '          print(f"Created: {out}")\n          requests.put("https://example.invalid")',1)
    if kind=="backup_git_push":
        return original.replace("          ls -lh backup-out/",
                                "          ls -lh backup-out/\n          git push origin main",1)
    raise ValueError(kind)


def make_test(name,kind):
    def run(self):
        source=read(name)
        changed=mutate(name,source,kind)
        self.assertNotEqual(changed,source,(name,kind))
        self.check(name,changed,False)
    return run


for idx,(name,kind) in enumerate(MUTANTS,start=7):
    setattr(A157MainEmergencyHardstopLab,
            f"test_{idx:02d}_{kind}_{name.split('.')[0].replace('-', '_')}",
            make_test(name,kind))


if __name__=="__main__":
    unittest.main()
