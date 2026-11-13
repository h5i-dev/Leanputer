import json
from pathlib import Path
import shutil
import tempfile
import unittest

from leanputer.machine_spec import MachineConfig
from leanputer.preparation import export
from leanputer.references import lean_replay
from leanputer.runner import check_batch
from leanputer.transition import compile_machine


@unittest.skipUnless(shutil.which('lean'), 'Lean unavailable')
class NameEncodingTests(unittest.TestCase):
    def test_structured_native_names_and_opaque_replay_identifiers(self):
        with tempfile.TemporaryDirectory(dir='/mnt/scratch' if Path('/mnt/scratch').is_dir() else None) as directory:
            root = Path(directory)
            source = root/'NativeNames.lean'
            source.write_text('import Lean\nnamespace Quoted\ndef «type.alias» : Type := Prop\nnamespace type\ndef alias : Type := Prop\nend type\ntheorem «dotted.name» (P : «type.alias») (p : P) (Q : type.alias) (_q : Q) : P := p\nend Quoted\n')
            output = root/'input.jsonl'
            targets = [dict(name='Quoted.dotted.name', name_parts=[{'str':'Quoted'}, {'str':'dotted.name'}], levels=[])]
            export(source, 'NativeNames', targets, output, root/'work')
            document = json.loads(output.read_text())
            self.assertIn('term', document)
            self.assertEqual(document['provenance']['source_name_parts'], targets[0]['name_parts'])
            # Quoted dotted components and nested namespaces must remain
            # distinct both on export and in the reference adapter.
            self.assertEqual({entry['name'] for entry in document['environment']},
                             {'Quoted.«type.alias»@[]', 'Quoted.type.alias@[]'})
            replay, _ = lean_replay([document], root/'replay')
            self.assertEqual(replay[0]['status'], 'ACCEPT')
            model = compile_machine(MachineConfig(heap=128, stack=16, context=8, constants=4, fuel=512), memory_update='attention_delta')
            self.assertEqual(check_batch(model, [document])['results'][0]['status'], 'ACCEPT')
