"""Versioned fixed-weight artifacts. Loading checks the deterministic compiler output."""
from pathlib import Path
import pickle

import torch

from .checker import Config, compile_checker

FORMAT_VERSION = 1


def save_checker(model, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        'format_version': FORMAT_VERSION,
        'config': {'nodes': model.config.nodes, 'types': model.config.types},
        'state_dict': {name: tensor.cpu() for name, tensor in model.state_dict().items()},
    }, path)


def load_checker(path):
    """Load tensors without arbitrary pickle execution and verify every weight.

    Recompilation is intentional: a modified weight file must not silently become
    a different acceptance predicate. Artifacts are not a compilation cache.
    """
    try:
        artifact = torch.load(path, map_location='cpu', weights_only=True)
    except (OSError, RuntimeError, EOFError, pickle.UnpicklingError) as error:
        raise ValueError(f'unable to read checker artifact: {error}') from error
    if (not isinstance(artifact, dict) or type(artifact.get('format_version')) is not int
            or artifact['format_version'] != FORMAT_VERSION):
        raise ValueError('unsupported checker artifact format')
    config = artifact.get('config')
    if not isinstance(config, dict) or set(config) != {'nodes', 'types'}:
        raise ValueError('malformed checker artifact configuration')
    model = compile_checker(Config(**config))
    expected, actual = model.state_dict(), artifact.get('state_dict')
    if not isinstance(actual, dict) or actual.keys() != expected.keys():
        raise ValueError('artifact weights do not match this compiler')
    for name, weight in expected.items():
        candidate = actual[name]
        if (not isinstance(candidate, torch.Tensor) or candidate.shape != weight.shape
                or candidate.dtype != weight.dtype or candidate.layout != weight.layout):
            raise ValueError(f'artifact weight mismatch: {name}')
        if weight.is_sparse:
            candidate, weight = candidate.coalesce(), weight.coalesce()
            same = (torch.equal(candidate.indices(), weight.indices())
                    and torch.equal(candidate.values(), weight.values()))
        else:
            same = torch.equal(candidate, weight)
        if not same:
            raise ValueError(f'artifact weight mismatch: {name}')
    return model.eval()
