"""Atomic declaration/assumption boundaries; SPEC, never native evidence."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest
from leanputer.kernel.arena import Limits
from leanputer.kernel.environment import EnvironmentDriver
from leanputer.kernel.syntax import SyntaxCodec


FIXTURE = Path(__file__).parent/'fixtures/kernel-source-smoke.jsonl'


class KernelEnvironmentTest(unittest.TestCase):
    def test_real_source_bodies_and_explicit_missing_service(self):
        docs = [json.loads(line) for line in FIXTURE.read_text().splitlines()[:3]]
        docs += [json.loads((FIXTURE.parent/'kernel-nested-source.jsonl').read_text())]
        results = []
        for doc in docs:
            driver = EnvironmentDriver(SyntaxCodec().document(doc))
            result = driver.check()
            results.append(result)
            self.assertEqual(driver.c.mark(), 0)
            self.assertFalse(result.assumptions)
        self.assertEqual([r.status for r in results], ['ACCEPT', 'GAP', 'ACCEPT', 'ACCEPT'])
        self.assertEqual([r.admitted_declarations for r in results], [0, 3, 4, 12])
        self.assertIn('projection', results[1].reason)

    def test_transaction_rollback_scope_and_resource_boundaries(self):
        docs = [json.loads(line) for line in FIXTURE.read_text().splitlines()[:3]]
        bad_claim = deepcopy(docs[1])
        bad_claim['declarations'][0]['recursor_claims'][0]['type'] = ['sort', ['zero']]
        driver = EnvironmentDriver(SyntaxCodec().document(bad_claim))
        result = driver.check()
        self.assertEqual((result.status, result.checked_input_items, result.admitted_declarations), ('GAP', 0, 0))
        self.assertFalse(driver.services.constants)
        self.assertFalse(driver.services.recursors)
        self.assertEqual(driver.c.mark(), 0)
        # Earlier genuine assumptions survive; an invalid next block publishes
        # none of its headers/constructors/recursors, including partial progress.
        bad = deepcopy(docs[1])
        assumption = dict(kind='axiom', name=[{'str': 'AssumedCarrier'}], level_params=[],
            type=['sort', ['succ', ['zero']]], value=None)
        bad['declarations'].insert(0, assumption)
        block = bad['declarations'][1]
        block['families'][0]['constructors'][0]['name'] = block['families'][0]['name']
        driver = EnvironmentDriver(SyntaxCodec().document(bad))
        result = driver.check()
        self.assertEqual((result.status, result.checked_input_items, result.admitted_declarations), ('REJECT', 1, 1))
        self.assertEqual(len(result.assumptions), 1)
        self.assertEqual(driver.c.mark(), 0)
        escaped = deepcopy(docs[2])
        escaped['target']['value'] = ['local', 47]
        driver = EnvironmentDriver(SyntaxCodec().document(escaped))
        result = driver.check()
        self.assertEqual((result.status, result.admitted_declarations), ('REJECT', 4))
        self.assertEqual(driver.c.mark(), 0)
        limited = EnvironmentDriver(SyntaxCodec(replace(Limits(), declarations=2)).document(docs[1])).check()
        self.assertEqual((limited.status, limited.admitted_declarations), ('RESOURCE', 0))
        non_prop = deepcopy(docs[0])
        non_prop['target']['kind'] = 'theorem'
        result = EnvironmentDriver(SyntaxCodec().document(non_prop)).check()
        self.assertEqual(result.status, 'REJECT')
        self.assertIn('not a proposition', result.reason)


if __name__ == '__main__':
    unittest.main()
