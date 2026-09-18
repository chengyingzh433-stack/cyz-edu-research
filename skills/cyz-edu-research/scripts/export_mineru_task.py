"""Export a completed Desk task and the source-binding metadata, without credentials."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile


PUBLIC_OPTION_FIELDS = (
    'provider', 'backend', 'method', 'language', 'formula', 'table', 'pages'
)
RUNTIME_FIELDS = ('modelSource', 'offline', 'modelRoot')
MAX_LINEAGE_DEPTH = 100


def source_digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def canonical_digest(value):
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(',', ':')
    ).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f'.{path.name}.', suffix='.tmp', dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with open(handle, 'w', encoding='utf-8', closefd=True) as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def submit_resume_and_poll(state_path, request, submit_task, fetch_task, max_polls=60):
    """Submit once, persist the ID, and resume polling that ID after interruption."""
    if not isinstance(request, dict):
        raise ValueError('Task request must be a JSON object')
    options = request.get('options', {})
    if not isinstance(options, dict) or options.get('provider') != 'local':
        raise ValueError('Only local MinerU submissions are permitted')
    if options.get('pages') is not None:
        raise ValueError('Only full-document MinerU submissions are permitted')
    request_hash = canonical_digest(request)
    state_path = Path(state_path)
    if state_path.is_file():
        state = json.loads(state_path.read_text(encoding='utf-8'))
        if state.get('request_fingerprint') != request_hash:
            raise ValueError('Saved submission belongs to a different request')
        task_id = state.get('task_id')
        if not isinstance(task_id, str) or not re.fullmatch(r'[A-Za-z0-9-]+', task_id):
            raise ValueError('Saved submission has an invalid task ID')
    else:
        task_id = submit_task(request)
        if not isinstance(task_id, str) or not re.fullmatch(r'[A-Za-z0-9-]+', task_id):
            raise ValueError('Submission returned an invalid task ID')
        state = {
            'schemaVersion': 1,
            'request_fingerprint': request_hash,
            'task_id': task_id,
            'status': 'submitted',
        }
        # This commit happens before the first poll, so interruption cannot resubmit.
        atomic_json(state_path, state)
    if not isinstance(max_polls, int) or max_polls < 1:
        raise ValueError('max_polls must be a positive integer')
    for _ in range(max_polls):
        task = fetch_task(task_id)
        if not isinstance(task, dict) or task.get('id') != task_id:
            raise ValueError('Poll returned the wrong task ID')
        status = task.get('status')
        if status in ('completed', 'reused'):
            state['status'] = status
            atomic_json(state_path, state)
            return task
        if status not in ('queued', 'running'):
            raise ValueError(f'Unexpected task status while polling: {status!r}')
    raise TimeoutError('Task is still running; resume polling the same saved task ID')


def export(desk_root, task_id, fetch_task=None):
    cli = desk_root.resolve() / 'Codex.ps1'
    if fetch_task is None and not cli.is_file():
        raise ValueError('Codex.ps1 not found')

    def get(identifier):
        if not re.fullmatch(r'[A-Za-z0-9-]+', identifier):
            raise ValueError('Invalid task ID')
        if fetch_task is not None:
            return fetch_task(identifier)
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
    lineage = []
    expected_id = task_id
    reference = None
    while True:
        if expected_id in seen or len(seen) >= MAX_LINEAGE_DEPTH:
            raise ValueError('Invalid task reuse chain: cycle or depth limit')
        seen.add(expected_id)
        if not isinstance(base, dict) or base.get('id') != expected_id:
            raise ValueError('Desk returned task ID does not match the requested lineage node')
        status = base.get('status')
        if status not in ('completed', 'reused'):
            raise ValueError('Every lineage node must be completed or reused')
        options = base.get('options')
        if not isinstance(options, dict):
            raise ValueError('Task options are missing')
        unknown = set(options) - set(PUBLIC_OPTION_FIELDS) - {'force'}
        if unknown:
            raise ValueError('Task contains unsupported option fields; refusing possible secrets')
        public_options = {key: options.get(key) for key in PUBLIC_OPTION_FIELDS}
        if public_options['provider'] != 'local':
            raise ValueError('Every lineage node must use the local provider')
        if public_options['backend'] != 'pipeline':
            raise ValueError('Every lineage node must use the Pipeline backend')
        if public_options['pages'] is not None:
            raise ValueError('Only full-document local tasks may be exported')
        settings = base.get('runtimeSettings')
        if not isinstance(settings, dict) or any(key not in settings for key in RUNTIME_FIELDS):
            raise ValueError('Every lineage node must include runtime settings')
        public_settings = {key: settings[key] for key in RUNTIME_FIELDS}
        if public_settings['offline'] is not True:
            raise ValueError('Every lineage node must be offline')
        identity = {
            'key': base.get('key'),
            'source': str(Path(base.get('source', '')).expanduser().resolve()),
            'options': public_options,
            'runtimeSettings': public_settings,
        }
        if not isinstance(identity['key'], str) or not identity['key']:
            raise ValueError('Every lineage node must include a cache key')
        if reference is None:
            reference = identity
        else:
            for field in ('key', 'source', 'options', 'runtimeSettings'):
                if identity[field] != reference[field]:
                    raise ValueError(f'Lineage {field} mismatch')
        lineage.append(expected_id)
        reused_from = base.get('reusedFrom')
        if status == 'reused':
            if not isinstance(reused_from, str) or not reused_from:
                raise ValueError('Reused task is missing source lineage')
            expected_id = reused_from
            base = get(expected_id)
            continue
        if reused_from is not None:
            raise ValueError('Completed lineage base cannot reuse another task')
        break
    match = re.search(r'(?m)^mineru-cli\.py, version [^\r\n]+', base.get('log', ''))
    if not match:
        raise ValueError('Desk runtime version not present in base task log')
    result = {k: task[k] for k in ('id','status','source','markdown','outputDir','key')}
    result['options'] = {key: task['options'].get(key) for key in PUBLIC_OPTION_FIELDS}
    result['runtime_version'] = match.group(0)
    result['runtimeSettings'] = {k:base['runtimeSettings'][k] for k in RUNTIME_FIELDS}
    if result['runtimeSettings']['offline'] is not True:
        raise ValueError('Only offline local tasks may be exported')
    source = Path(result['source']).expanduser().resolve()
    if not source.is_file():
        raise ValueError('Original task source is unavailable for hashing')
    result['source_sha256'] = source_digest(source)
    result['base_task_id'] = base['id']
    result['lineage_task_ids'] = lineage
    if task.get('status') == 'reused':
        if len(lineage) < 2:
            raise ValueError('Reused task is missing source lineage')
        result['reused_from_task_id'] = lineage[1]
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
