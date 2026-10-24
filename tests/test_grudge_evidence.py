"""Structured evidence reports. Fixtures, not real source verification."""
import copy
from datetime import date
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'skills/arena'))
from grudge_evidence import validate_report, report_markdown, report_html, judge_index, validate_document_citations


def evidence_fixture():
    return {'schema_version':1, 'summary':'One supported claim and one unresolved claim.', 'claims':[
        {'id':'c1','origin':'original','claim':'A factual claim','assessment':'supported','explanation':'Source supports the stated condition.',
         'sources':[{'title':'Official reference','url':'https://example.com/reference','locator':'Section 2','checked_on':date.today().isoformat(),'finding':'Concise paraphrase of supporting content.'}]},
        {'id':'c2','origin':'review','claim':'Another claim','assessment':'unverified','explanation':'Source could not be accessed.','sources':[]},
        {'id':'c3','origin':'synthesis','claim':'Revised factual claim','assessment':'supported','explanation':'The cited section supports it.',
         'sources':[{'title':'Official reference','url':'https://example.com/reference','locator':'Section 2','checked_on':date.today().isoformat(),'finding':'Concise paraphrase.'}]}]}


class EvidenceTests(unittest.TestCase):
    def test_report_links_and_assessments(self):
        report = evidence_fixture()
        self.assertEqual(validate_report(report), report)
        text = report_markdown(report)
        self.assertIn('[Official reference](https://example.com/reference)', text)
        self.assertIn('unverified', text)

    def test_all_three_outputs_must_be_checked(self):
        report = evidence_fixture()
        report['claims'] = report['claims'][:2]
        with self.assertRaises(ValueError): validate_report(report)

    def test_no_source_cannot_be_supported(self):
        report = evidence_fixture()
        report['claims'][0]['sources'] = []
        with self.assertRaises(ValueError): validate_report(report)

    def test_unsafe_and_invented_source_shapes_rejected(self):
        for url in ('javascript:alert(1)','file:///secret','https://user:password@example.com/path','https://example.com/\nmalicious','not a URL'):
            report = evidence_fixture()
            report['claims'][0]['sources'][0]['url'] = url
            with self.assertRaises(ValueError): validate_report(report)

    def test_unverified_and_nonfactual_claims_need_no_fake_citations(self):
        report = evidence_fixture()
        claim = report['claims'][0]
        claim.update(assessment='not_applicable', explanation='Creative preference without external factual claim.', sources=[])
        self.assertEqual(validate_report(report), report)

    def test_duplicate_ids_empty_report_and_missing_locator_rejected(self):
        for change in ('duplicate','empty','missing'):
            report = evidence_fixture()
            if change == 'duplicate': report['claims'][1]['id']='c1'
            if change == 'empty': report['claims']=[]
            if change == 'missing': del report['claims'][0]['sources'][0]['locator']
            with self.assertRaises(ValueError): validate_report(report)

    def test_judge_index_uses_anonymous_candidates_and_no_review_claims(self):
        value = judge_index(evidence_fixture(), {'a001':'y','a002':'x'})
        self.assertEqual([r['candidate'] for r in value['claims']], ['y','x'])
        self.assertTrue(all('origin' not in row and 'explanation' not in row for row in value['claims']))

    def test_html_escapes_claims_and_source_titles(self):
        report = evidence_fixture()
        report['claims'][0]['claim']='<script>bad()</script>'
        report['claims'][0]['sources'][0]['title']='<img src=x onerror=bad()>'
        rendered=report_html(report)
        self.assertNotIn('<script>',rendered)
        self.assertNotIn('<img ',rendered)
        self.assertIn('href="https://example.com/reference"',rendered)

    def test_supplied_document_citations_require_real_id_and_location(self):
        import tempfile,base64,hashlib
        from supporting_documents import DocumentStore,snapshot_documents
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);store=DocumentStore(root/'uploads');data=b'Name,Amount\nWidget,42\n'
            store.upload('a'*32,'budget.csv',len(data),hashlib.sha256(data).hexdigest(),0,base64.b64encode(data).decode())
            run=root/'run';run.mkdir();snapshot_documents(run,store.resolve(['a'*32]))
            report=evidence_fixture()
            source={'kind':'document','document_id':'a'*32,'title':'budget.csv','locator':'CSV!B2','checked_on':date.today().isoformat(),'finding':'Supplied cell contains 42.'}
            report['claims'][0]['sources']=[source]
            validate_report(report);validate_document_citations(report,run)
            self.assertIn('#document-',report_html(report))
            source['locator']='CSV!Z9999'
            with self.assertRaises(ValueError):validate_document_citations(report,run)
            source['locator']='CSV!B2';source['document_id']='b'*32
            with self.assertRaises(ValueError):validate_document_citations(report,run)

    def test_source_text_cannot_inject_markup(self):
        report = evidence_fixture()
        report['claims'][0]['sources'][0]['title'] = 'Injected](javascript:alert(1))'
        text = report_markdown(report)
        self.assertNotIn('[Injected](javascript:', text)

if __name__ == '__main__': unittest.main()
