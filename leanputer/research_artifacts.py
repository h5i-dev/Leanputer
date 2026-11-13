"""Versioned shared-machine artifacts with compiler compatibility verification."""
import hashlib
from dataclasses import asdict
from pathlib import Path

import torch

from .machine_spec import MachineConfig
from .transition import compile_machine

ARTIFACT_FORMAT = 'leanputer.shared-ground-pi.v1'
COMPILER_FILES = ('transition.py', 'circuit.py', 'bitvec.py', 'logic.py', 'memory.py', 'machine_spec.py',
                  'state_layout.py', 'dependent.py')


def compiler_fingerprint():
    digest = hashlib.sha256()
    for name in COMPILER_FILES:
        digest.update(name.encode())
        digest.update(Path(__file__).with_name(name).read_bytes())
    return digest.hexdigest()


def save_machine(model, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(dict(format=ARTIFACT_FORMAT, compiler=compiler_fingerprint(), config=asdict(model.config), optimized=model.optimized, memory_update=model.memory_update,
                    state_dict={name: tensor.cpu() for name, tensor in model.state_dict().items()}), path)


def load_machine(path):
    artifact = torch.load(path, map_location='cpu', weights_only=True)
    if not isinstance(artifact, dict) or artifact.get('format') != ARTIFACT_FORMAT:
        raise ValueError('unsupported shared-machine artifact format')
    if artifact.get('compiler') != compiler_fingerprint():
        raise ValueError('artifact compiler fingerprint mismatch; recompile this checkpoint')
    optimized = artifact.get('optimized', True)
    if type(optimized) is not bool:
        raise ValueError('artifact lowering flag must be Boolean')
    model = compile_machine(MachineConfig(**artifact['config']), optimized=optimized, memory_update=artifact.get('memory_update', 'logic'))
    expected, actual = model.state_dict(), artifact.get('state_dict')
    if not isinstance(actual, dict) or actual.keys() != expected.keys():
        raise ValueError('shared-machine artifact tensor keys mismatch')
    for name, tensor in expected.items():
        candidate = actual[name]
        if (not isinstance(candidate, torch.Tensor) or candidate.shape != tensor.shape
                or candidate.dtype != tensor.dtype or candidate.layout != tensor.layout):
            raise ValueError(f'artifact tensor mismatch: {name}')
        if tensor.is_sparse:
            candidate, tensor = candidate.coalesce(), tensor.coalesce()
            equal = torch.equal(candidate.indices(), tensor.indices()) and torch.equal(candidate.values(), tensor.values())
        else:
            equal = torch.equal(candidate, tensor)
        if not equal:
            raise ValueError(f'artifact tensor mismatch: {name}')
    return model
