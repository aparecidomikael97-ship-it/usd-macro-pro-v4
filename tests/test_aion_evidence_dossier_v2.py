from copy import deepcopy
import json
import unittest
from atlasquant_aion_first_install_preparation_v2.evidence_dossier_reference import synthetic_dossier,review_dossier
from atlasquant_aion_first_install_preparation.contracts import AUTHORITY_FIELDS

class DossierTests(unittest.TestCase):
    def test_synthetic_fields_never_verify(self):
        data=synthetic_dossier()
        for row in data['requirements']:
            row.update(negative_result='SIMULATED_PASS',revocation='SIMULATED_NOT_REVOKED')
        out=review_dossier(data,now=1001)
        self.assertEqual(out['state'],'REFERENCE_DOSSIER_VALID_UNTRUSTED')
        self.assertEqual(out['unresolved_gate_count'],20)
        self.assertTrue(all(x['state']=='BLOCKED' for x in out['requirements']))
        for k in AUTHORITY_FIELDS:self.assertIs(out[k],False)

    def test_sensitive_fields_rejected_no_echo(self):
        for field in ['pin','biometric','private_key','token','customer_data','document','installation_authorized']:
            with self.subTest(field=field):
                data=synthetic_dossier();data['requirements'][0][field]='SECRET_SENTINEL'
                out=review_dossier(data,now=1001);self.assertEqual(out['state'],'BLOCKED');self.assertNotIn('SECRET_SENTINEL',str(out))

    def test_whitelist_projection_redacts_even_freeform_fixture_values(self):
        data=synthetic_dossier();data['requirements'][0]['source_ref']='fixture://SECRET_SENTINEL'
        out=review_dossier(data,now=1001);self.assertNotIn('SECRET_SENTINEL',str(out));self.assertNotIn('artifact_sha256',str(out))

    def test_expired_revoked_verified_missing_dependencies(self):
        for field,value in [('expires_at',999),('observed_at',True),('audit_decision','VERIFIED'),('source_ref','https://secret.example'),('artifact_sha256','bad'),('unsatisfied_dependencies',[]),('tenant_alias','real-tenant')]:
            with self.subTest(field=field):
                data=synthetic_dossier();data['requirements'][-1][field]=value
                self.assertEqual(review_dossier(data,now=1001)['state'],'BLOCKED')
        data=synthetic_dossier();data['requirements'][0]['revocation']='REVOKED'
        self.assertEqual(review_dossier(data,now=1001)['unresolved_gate_count'],20)

    def test_exact_twenty_unique_and_bounded(self):
        for count in [0,19,21]:
            with self.subTest(count=count):
                d=synthetic_dossier();d['requirements']=(d['requirements']*2)[:count]
                self.assertEqual(review_dossier(d,now=1001)['state'],'BLOCKED')
        d=synthetic_dossier();d['requirements'][1]=deepcopy(d['requirements'][0]);self.assertEqual(review_dossier(d,now=1001)['state'],'BLOCKED')

if __name__=='__main__':unittest.main()
