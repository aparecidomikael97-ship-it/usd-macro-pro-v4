"""A54 CI contract tests. Mock Git transport ONLY, never identity/producer proof."""
import os,subprocess,unittest
from unittest.mock import patch
import test_atlasquant_aion_convergence as gate
MAIN='a'*40
A49='lab/aion-v16-a49-worker-pure-transition-simulation-20261013'
A52='lab/aion-v16-a52-a50-a51-integrated-containment-20261013'
class MainBoundaryTests(unittest.TestCase):
 def setUp(self):
  self.calls=[];self.origin=next(iter(gate.A54_ORIGIN_URLS));self.fail_main=False;self.fail_lab=False;self.fail_diff=False;self.ancestry=0;self.main=MAIN;self.pin=None;self.paths='safe.py\x00docs/safe.md\x00'
 def git(self,args):
  self.calls.append(args)
  code=0;out=''
  if args[:2]==['remote','get-url']:out=self.origin
  elif args[0]=='fetch':code=int(self.fail_main if args[-1].startswith('+refs/heads/main:') else self.fail_lab)
  elif args[:2]==['rev-parse','--verify']:
   out=self.main if args[-1]=='origin/main^{commit}' else (self.pin or gate.A54_PINNED_LAB_BASES[args[-1][7:-9]])
  elif args[0]=='merge-base':code=self.ancestry
  elif args[0]=='diff':code=int(self.fail_diff);out=self.paths
  else:raise AssertionError('Unexpected Git fixture call '+repr(args))
  return subprocess.CompletedProcess(args,code,out,'SIMULATED_ONLY_GIT_ERROR' if code else '')
 def resolve(self,target):
  with patch.dict(os.environ,{'GITHUB_BASE_REF':target,'GITHUB_EVENT_NAME':'pull_request'}),patch.object(gate,'_git',side_effect=self.git):return gate._production_base()
 def surfaces(self):
  with patch.object(gate,'_git',side_effect=self.git):gate._assert_production_surfaces(MAIN)
 def test_main_valid_returns_immutable_true_main_sha(self):
  self.assertEqual(self.resolve('main'),MAIN);self.assertIn(['fetch','--no-tags','--depth','1','origin','+refs/heads/main:refs/remotes/origin/main'],self.calls)
 def test_a49_valid_still_compares_true_main(self):
  self.assertEqual(self.resolve(A49),MAIN);self.assertIn(['merge-base','--is-ancestor',gate.A54_A49_PARENT,gate.A54_PINNED_LAB_BASES[A49]],self.calls)
 def test_a52_valid_requires_pinned_a49_ancestry(self):
  self.assertEqual(self.resolve(A52),MAIN);self.assertIn(['merge-base','--is-ancestor',gate.A54_A49_PARENT,gate.A54_PINNED_LAB_BASES[A52]],self.calls)
 def test_unknown_target_closed(self):
  with self.assertRaisesRegex(AssertionError,'UNKNOWN_PR_BASE'):self.resolve('lab/not-allowlisted')
  self.assertEqual(self.calls,[])
 def test_missing_pr_base_closed(self):
  with self.assertRaisesRegex(AssertionError,'PR_BASE_REQUIRED'):self.resolve('')
 def test_main_unavailable_never_uses_cached_lab(self):
  self.fail_main=True
  with self.assertRaisesRegex(AssertionError,'TRUE_MAIN_UNAVAILABLE'):self.resolve(A49)
  self.assertFalse(any('refs/heads/'+A49 in ' '.join(c) for c in self.calls))
 def test_unapproved_origin_closed(self):
  self.origin='https://github.com/attacker/SIMULATED'
  with self.assertRaisesRegex(AssertionError,'ORIGIN_NOT_APPROVED'):self.resolve('main')
 def test_invalid_main_commit_closed(self):
  self.main='not-a-commit'
  with self.assertRaisesRegex(AssertionError,'MAIN_COMMIT_INVALID'):self.resolve('main')
 def test_a49_wrong_pin_closed(self):
  self.pin='b'*40
  with self.assertRaisesRegex(AssertionError,'LAB_BASE_SHA_MISMATCH'):self.resolve(A49)
 def test_a52_wrong_pin_closed(self):
  self.pin='c'*40
  with self.assertRaisesRegex(AssertionError,'LAB_BASE_SHA_MISMATCH'):self.resolve(A52)
 def test_a49_ancestry_failure_closed(self):
  self.ancestry=1
  with self.assertRaisesRegex(AssertionError,'A49_PARENT_NOT_VERIFIED'):self.resolve(A52)
 def test_pinned_ref_unavailable_closed(self):
  self.fail_lab=True
  with self.assertRaisesRegex(AssertionError,'PINNED_BASE_UNAVAILABLE'):self.resolve(A49)
 def test_safe_changes_diff_uses_main_not_lab(self):
  self.surfaces();self.assertEqual(self.calls[-1],['diff','--no-renames','--name-only','-z',MAIN])
 def test_render_change_closed(self):
  self.paths='render.yaml\x00'
  with self.assertRaisesRegex(AssertionError,'FORBIDDEN_PRODUCTION_SURFACE'):self.surfaces()
 def test_deploy_change_closed(self):
  self.paths='deploy/SIMULATED.txt\x00'
  with self.assertRaisesRegex(AssertionError,'FORBIDDEN_PRODUCTION_SURFACE'):self.surfaces()
 def test_secret_change_closed(self):
  self.paths='docs/SIMULATED_secret.md\x00'
  with self.assertRaisesRegex(AssertionError,'FORBIDDEN_PRODUCTION_SURFACE'):self.surfaces()
 def test_uppercase_production_path_closed(self):
  self.paths='DEPLOY/SIMULATED.txt\x00'
  with self.assertRaisesRegex(AssertionError,'FORBIDDEN_PRODUCTION_SURFACE'):self.surfaces()
 def test_newline_filename_cannot_hide_deploy(self):
  self.paths='deploy/SIMULATED\nname.txt\x00'
  with self.assertRaisesRegex(AssertionError,'FORBIDDEN_PRODUCTION_SURFACE'):self.surfaces()
 def test_rename_keeps_old_protected_path_in_diff(self):
  self.paths='deploy/old.txt\x00docs/new.txt\x00'
  with self.assertRaisesRegex(AssertionError,'FORBIDDEN_PRODUCTION_SURFACE'):self.surfaces()
  self.assertIn('--no-renames',self.calls[-1])
 def test_diff_failure_closed(self):
  self.fail_diff=True
  with self.assertRaisesRegex(AssertionError,'MAIN_SURFACE_DIFF_UNAVAILABLE'):self.surfaces()
