"""External syntax preparation for real elaborated Lean input."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def lean_tool(name):
    candidates = [Path(__file__).resolve().parents[1]/'tools/lean'/name,
                  Path(sys.prefix)/'share/leanputer/lean'/name]
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(f'packaged Lean helper not found: {name}')


def export(source, module, targets, output, workdir, lean='lean'):
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    working = Path(tempfile.mkdtemp(prefix='export-', dir=workdir))
    environment = dict(os.environ)
    environment['LEAN_PATH'] = str(working)+(os.pathsep+environment['LEAN_PATH'] if environment.get('LEAN_PATH') else '')
    commands = []
    if source:
        source = Path(source).resolve()
        # Lean computes the source module relative to --root. Explicitly set
        # that root so preparation also works for sources outside our cwd.
        parts = module.split('.')
        if source.stem != parts[-1] or any(not part for part in parts):
            raise ValueError('source filename must match the final module component')
        package_root = source.parents[len(parts)-1]
        olean = working/(module.replace('.', '/')+'.olean')
        olean.parent.mkdir(parents=True, exist_ok=True)
        commands.append([str(lean), '--root='+str(package_root), '-o', str(olean), str(source)])
    config = working/'export-config.json'
    config.write_text(json.dumps(dict(modules=[module], targets=targets, output=str(Path(output).resolve()))))
    commands.append([str(lean), '--run', str(lean_tool('Export.lean')), str(config)])
    for index, command in enumerate(commands):
        completed = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=300)
        (working/f'command-{index}.log').write_text(completed.stdout+completed.stderr)
        if completed.returncode:
            raise RuntimeError('Lean preparation failed: '+completed.stdout+completed.stderr)
    return dict(output=str(Path(output).resolve()), working_directory=str(working), commands=commands)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, help='optional source module to compile externally')
    parser.add_argument('--module', help='module to import; defaults to source filename')
    parser.add_argument('--targets', required=True, type=Path, help='array of name/ground-level target objects')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--workdir', type=Path, default=Path('/mnt/scratch/leanputer-runs/preparation') if Path('/mnt/scratch').is_dir() else Path(tempfile.gettempdir())/'leanputer-preparation')
    args = parser.parse_args(argv)
    try:
        module = args.module or (args.source.stem if args.source else None)
        if not module:
            raise ValueError('--module or --source required')
        targets = json.loads(args.targets.read_text())
        if not isinstance(targets, list):
            raise ValueError('targets must be a JSON array')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        print(json.dumps(export(args.source, module, targets, args.output, args.workdir), indent=2))
        return 0
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        parser.error(str(error))


if __name__ == '__main__':
    raise SystemExit(main())
