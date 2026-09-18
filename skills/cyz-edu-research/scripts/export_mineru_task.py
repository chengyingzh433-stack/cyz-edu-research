"""Export a completed Desk task and the source-binding metadata, without credentials."""
import argparse
import base64
import json
from pathlib import Path
import re
import subprocess
import sys


def export(desk_root, task_id):
    cli = desk_root.resolve() / 'Codex.ps1'
    if not cli.is_file():
        raise ValueError('Codex.ps1 not found')

    def get(identifier):
        if not re.fullmatch(r'[A-Za-z0-9-]+', identifier):
            raise ValueError('Invalid task ID')
        literal = str(cli).replace("'", "''")
        command = ("[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); "
                   f"& '{literal}' request GET 'tasks/{identifier}'; exit $LASTEXITCODE")
        encoded = base64.b64encode(command.encode('utf-16le')).decode('ascii')
        result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
            '-EncodedCommand', encoded],
            capture_output=True, text=True, encoding='utf-8', timeout=150,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            raise RuntimeError('Desk task query failed; inspect the local service diagnostics')
        return json.loads(result.stdout)

    task = get(task_id)
    if task.get('status') not in ('completed', 'reused'):
        raise ValueError('Task not completed; continue polling the same ID')
    base = task
    seen = set()
    while base.get('reusedFrom'):
        if base['id'] in seen or len(seen) >= 100:
            raise ValueError('Invalid task reuse chain')
        seen.add(base['id'])
        base = get(base['reusedFrom'])
    if task.get('key') != base.get('key'):
        raise ValueError('Reused task key differs from original task')
    match = re.search(r'(?m)^mineru-cli\.py, version [^\r\n]+', base.get('log', ''))
    if not match:
        raise ValueError('Desk runtime version not present in base task log')
    result = {k: task[k] for k in ('id','status','source','options','markdown','outputDir','key')}
    if result['options'].get('env'):
        raise ValueError('Custom environment tasks require a separate reviewed export; not copying secrets')
    result['runtime_version'] = match.group(0)
    result['runtimeSettings'] = {k:base['runtimeSettings'][k] for k in ('modelSource','offline','modelRoot')}
    result['base_task_id'] = base['id']
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--desk-root', type=Path, required=True)
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        record = export(args.desk_root, args.task_id)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        print('TASK_EXPORTED ' + str(args.output.resolve()))
    except Exception as exc:
        print('ERROR ' + str(exc), file=sys.stderr)
        sys.exit(1)
