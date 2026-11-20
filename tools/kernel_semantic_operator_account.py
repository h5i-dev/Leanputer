"""Joint typed-node account for the fixed semantic operators. No stock emission."""
import json
from pathlib import Path
from leanputer.kernel.control_capture import capture
from leanputer.kernel.semantic_operators import account
from leanputer.kernel.traversal_machine import MachineConfig

if __name__ == '__main__':
    config = MachineConfig(**json.loads(Path('benchmarks/kernel-full-source-stock/config.json').read_text()))
    compiler, _addresses = capture(config)
    print(json.dumps(account(compiler), indent=2, sort_keys=True))
