"""A157 adversarial workflow YAML policy tests. SOURCE ONLY; NEVER launch jobs."""
import unittest
from tools.aion_p0_a157_workflow_yaml_policy_lab import (
    ROOT, CRITICAL, BACKUPS, inspect_critical_workflow, inspect_readonly_backup,
)
from tools.aion_p0_workflow_credential_surface_a137 import inspect_one as a137

WF = ROOT / ".github" / "workflows"
F = "$" + "{{ false }}"
T = "$" + "{{ true }}"


def read(name):
    return (WF / name).read_text(encoding="utf-8")


def second_job(source, command="gh api --method PUT repos/x/y/contents/dados/aion/checkpoint_master.json"):
    return source.rstrip() + "\n  rogue:\n    runs-on: ubuntu-latest\n    steps:\n      - run: " + command + "\n"


def mutate(source, name, variant):
    if variant == "second_job":
        return second_job(source)
    if variant == "second_job_always":
        return second_job(source,"echo runnable")
    if variant == "duplicate_if":
        return source.replace("    if: " + F, "    if: "+F+"\n    if: "+T, 1)
    if variant == "duplicate_top_permissions":
        return source.replace("permissions:\n", "permissions:\n",1) + "\npermissions:\n  contents: write\n"
    if variant == "duplicate_contents":
        return source.replace("  contents: read","  contents: read\n  contents: write",1)
    if variant == "duplicate_jobs":
        return source + "\njobs:\n  bypass:\n    runs-on: ubuntu-latest\n    steps: []\n"
    if variant == "duplicate_job_name":
        job = CRITICAL.get(name, BACKUPS.get(name))
        return source + "\n  "+job+":\n    runs-on: ubuntu-latest\n    steps: []\n"
    if variant == "condition_true":
        return source.replace("    if: "+F,"    if: "+T,1)
    if variant == "condition_not_false":
        return source.replace("    if: "+F,"    if: $"+"{{ !false }}",1)
    if variant == "condition_env":
        return source.replace("    if: "+F,"    if: $"+"{{ vars.ACTIVATE == '1' }}",1)
    if variant == "condition_comment":
        return source.replace("    if: "+F,"    # if: "+F,1)
    if variant == "write_permission":
        return source.replace("  contents: read","  contents: write",1)
    if variant == "job_write_permission":
        return source.replace("    runs-on: ubuntu-latest",
            "    permissions:\n      contents: write\n    runs-on: ubuntu-latest",1)
    if variant == "writer_removed_autopilot":
        return source.replace("python autopilot_setup_audit_v114.py","python innocent.py",1)
    if variant == "writer_comment_only":
        return source.replace("python autopilot_setup_audit_v114.py",
            "python innocent.py\n        # python autopilot_setup_audit_v114.py",1)
    if variant == "writer_removed_coleta":
        return source.replace("python coleta_automatica_v86.py","python innocent.py",1)
    if variant == "writer_removed_bootstrap":
        return source.replace("gh api --method PUT","gh api --method GET",1)
    if variant == "writer_removed_migrate":
        return source.replace("gh api --method PUT","gh api --method GET",1)
    if variant == "bootstrap_read_only":
        return source.replace("  contents: write","  contents: read",1)
    if variant == "yaml_anchor":
        return source.replace("    runs-on: ubuntu-latest",
            "    runs-on: &runner ubuntu-latest",1)
    if variant == "yaml_alias":
        return source.replace("    runs-on: ubuntu-latest",
            "    runner: &runner ubuntu-latest\n    runs-on: *runner",1)
    if variant == "backup_git_push":
        return source.replace("          ls -lh backup-out/",
            "          ls -lh backup-out/\n          git push origin main",1)
    if variant == "backup_gh_put":
        return source.replace("          print(f\"Created: {out}\")",
            "          print(f\"Created: {out}\")\n          gh api --method PUT repository",1)
    if variant == "backup_requests_put":
        return source.replace("          print(f\"Created: {out}\")",
            "          print(f\"Created: {out}\")\n          requests.put('https://invalid.example')",1)
    if variant == "backup_unpinned_checkout":
        return source.replace("persist-credentials: false","persist-credentials: true",1)
    if variant == "backup_missing_artifact":
        return source.replace("actions/upload-artifact@","actions/cache@",1)
    if variant == "backup_extra_step_gh":
        return source.rstrip() + "\n      - run: gh api --method PUT repos/x/y/contents/secret\n"
    if variant == "backup_extra_step_git":
        return source.rstrip() + "\n      - run: git push origin main\n"
    if variant == "no_workflow_jobs":
        return "on:\n  workflow_dispatch:\njobs: {}\n"
    if variant == "yaml_not_mapping":
        return "- jobs\n- false\n"
    if variant == "yaml_invalid":
        return "jobs:\n  broken: [invalid\n"
    raise AssertionError(variant)


class A157WorkflowYAMLPolicyLAB(unittest.TestCase):
    def check(self, name, text, accepted):
        out = (inspect_critical_workflow(name,text)
               if name in CRITICAL
               else inspect_readonly_backup(name,text))
        self.assertIs(out["source_shape_strict"], accepted, out)
        self.assertIn("HARD_NO_GO", out["verdict"])
        self.assertIs(out["real_writes_allowed"], False)
        self.assertIs(out["no_live_iam_verified"], True)
        if not accepted:
            self.assertTrue(out["findings"], out)
        return out

    def test_01_real_autopilot_job_denied(self):
        self.check("autopilot-v107.yml",read("autopilot-v107.yml"),True)

    def test_02_real_coleta_job_denied(self):
        self.check("coleta_automatica.yml",read("coleta_automatica.yml"),True)

    def test_03_real_bootstrap_job_denied(self):
        self.check("aion-runtime-checkpoint-bootstrap.yml",read("aion-runtime-checkpoint-bootstrap.yml"),True)

    def test_04_real_migration_job_denied(self):
        self.check("aion-runtime-checkpoint-migrate.yml",read("aion-runtime-checkpoint-migrate.yml"),True)

    def test_05_source_checkpoint_job_readonly(self):
        self.check("atlasquant-checkpoint.yml",read("atlasquant-checkpoint.yml"),True)

    def test_06_source_backup_job_readonly(self):
        self.check("atlasquant-source-backup.yml",read("atlasquant-source-backup.yml"),True)

    def test_07_old_a137_false_negative_active_second_job(self):
        name="autopilot-v107.yml"
        src=second_job(read(name))
        self.assertTrue(a137(name,src)["target_p0_fence_ok"])
        self.check(name,src,False)

    def test_08_old_a137_false_negative_duplicate_if(self):
        name="autopilot-v107.yml"
        src=mutate(read(name),name,"duplicate_if")
        self.assertTrue(a137(name,src)["target_p0_fence_ok"])
        self.check(name,src,False)

    def test_09_readonly_checkout_does_not_cache_credentials(self):
        for name in BACKUPS:
            self.assertIn("persist-credentials: false",read(name))
            self.check(name,read(name),True)

    def test_10_no_live_enrollment_even_after_static_clean(self):
        for name in list(CRITICAL)+list(BACKUPS):
            out=self.check(name,read(name),True)
            self.assertTrue(out["no_live_iam_verified"])
            self.assertFalse(out["real_writes_allowed"])

    def test_11_missing_critical_job_denied(self):
        self.check("autopilot-v107.yml","jobs:\n  nothing:\n    runs-on: ubuntu-latest\n",False)

    def test_12_backup_unparseable_yaml_denied(self):
        self.check("atlasquant-checkpoint.yml","jobs:\n  broken: [",False)

    def test_13_critical_wrong_source_type_denied(self):
        self.check("autopilot-v107.yml",{"jobs":"rogue"},False)

    def test_14_backup_wrong_source_type_denied(self):
        self.check("atlasquant-source-backup.yml",None,False)


_MUTATIONS = [
    ("autopilot-v107.yml","second_job"),
    ("coleta_automatica.yml","second_job"),
    ("aion-runtime-checkpoint-bootstrap.yml","second_job"),
    ("aion-runtime-checkpoint-migrate.yml","second_job"),
    ("autopilot-v107.yml","duplicate_if"),
    ("coleta_automatica.yml","duplicate_if"),
    ("autopilot-v107.yml","duplicate_top_permissions"),
    ("autopilot-v107.yml","duplicate_contents"),
    ("autopilot-v107.yml","duplicate_jobs"),
    ("autopilot-v107.yml","duplicate_job_name"),
    ("aion-runtime-checkpoint-bootstrap.yml","duplicate_job_name"),
    ("autopilot-v107.yml","condition_true"),
    ("coleta_automatica.yml","condition_not_false"),
    ("autopilot-v107.yml","condition_env"),
    ("coleta_automatica.yml","condition_comment"),
    ("autopilot-v107.yml","write_permission"),
    ("coleta_automatica.yml","write_permission"),
    ("autopilot-v107.yml","job_write_permission"),
    ("coleta_automatica.yml","job_write_permission"),
    ("autopilot-v107.yml","writer_removed_autopilot"),
    ("autopilot-v107.yml","writer_comment_only"),
    ("coleta_automatica.yml","writer_removed_coleta"),
    ("aion-runtime-checkpoint-bootstrap.yml","writer_removed_bootstrap"),
    ("aion-runtime-checkpoint-migrate.yml","writer_removed_migrate"),
    ("aion-runtime-checkpoint-bootstrap.yml","bootstrap_read_only"),
    ("autopilot-v107.yml","yaml_anchor"),
    ("autopilot-v107.yml","yaml_alias"),
    ("atlasquant-checkpoint.yml","write_permission"),
    ("atlasquant-source-backup.yml","write_permission"),
    ("atlasquant-checkpoint.yml","second_job"),
    ("atlasquant-source-backup.yml","second_job"),
    ("atlasquant-source-backup.yml","job_write_permission"),
    ("atlasquant-checkpoint.yml","job_write_permission"),
    ("atlasquant-source-backup.yml","backup_git_push"),
    ("atlasquant-source-backup.yml","backup_unpinned_checkout"),
    ("atlasquant-checkpoint.yml","backup_unpinned_checkout"),
]
assert len(_MUTATIONS)==36, len(_MUTATIONS)


def _make_test(name, variant):
    def run(self):
        original=read(name)
        mutated=mutate(original,name,variant)
        self.assertNotEqual(mutated,original,(name,variant))
        self.check(name,mutated,False)
    return run


for index, (name, variant) in enumerate(_MUTATIONS, start=15):
    setattr(A157WorkflowYAMLPolicyLAB,
            f"test_{index:02d}_mutation_{variant}_{name.split('.')[0].replace('-', '_')}",
            _make_test(name,variant))


if __name__=="__main__":
    unittest.main()
