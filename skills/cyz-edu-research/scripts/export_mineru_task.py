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
import time


PUBLIC_OPTION_FIELDS = (
    'provider', 'backend', 'cloudMode', 'method', 'language', 'formula', 'table',
    'imageAnalysis', 'effort', 'formats', 'timeout', 'pages', 'force',
    'extraArgs', 'env'
)
KEY_OPTION_FIELDS = tuple(key for key in PUBLIC_OPTION_FIELDS if key != 'force')
RUNTIME_FIELDS = ('modelSource', 'offline', 'modelRoot')
MAX_LINEAGE_DEPTH = 100


def is_full_document_pages(value):
    return value is None or (type(value) is str and value == '')


def validate_desk_options(options):
    if not isinstance(options, dict):
        raise ValueError('Task options are missing')
    unknown = set(options) - set(PUBLIC_OPTION_FIELDS)
    missing = set(PUBLIC_OPTION_FIELDS) - set(options)
    if unknown:
        raise ValueError('Task contains unsupported option fields; refusing possible secrets')
    if missing:
        raise ValueError('Task options are missing required fields: ' + ', '.join(sorted(missing)))
    if options['provider'] != 'local':
        raise ValueError('Every lineage node must use the local provider')
    if options['backend'] != 'pipeline':
        raise ValueError('Every lineage node must use the Pipeline backend')
    if options['cloudMode'] != 'extract':
        raise ValueError('cloudMode must be extract for local tasks')
    if options['method'] not in {'auto', 'txt', 'ocr'}:
        raise ValueError('method is unsupported')
    if not isinstance(options['language'], str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,31}', options['language']):
        raise ValueError('language is invalid')
    for field in ('formula', 'table', 'imageAnalysis', 'force'):
        if type(options[field]) is not bool:
            raise ValueError(f'{field} must be boolean')
    if options['effort'] not in {'low', 'medium', 'high'}:
        raise ValueError('effort is unsupported')
    formats = options['formats']
    if (
        not isinstance(formats, list)
        or not all(isinstance(value, str) for value in formats)
        or len(formats) != len(set(formats))
        or not {'md', 'json'}.issubset(formats)
        or any(value not in {'md', 'json'} for value in formats)
    ):
        raise ValueError('formats must be the unique local md/json set')
    if type(options['timeout']) is not int or options['timeout'] <= 0:
        raise ValueError('timeout must be a positive integer')
    if not is_full_document_pages(options['pages']):
        raise ValueError('Only full-document local tasks may be exported')
    if options['extraArgs'] != []:
        raise ValueError('extraArgs must be empty')
    if options['env'] != {}:
        raise ValueError('env must be empty')
    return {key: options[key] for key in PUBLIC_OPTION_FIELDS}


def key_options(options):
    canonical = {key: options[key] for key in KEY_OPTION_FIELDS}
    canonical['pages'] = None
    return canonical


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


def submit_resume_and_poll(
    state_path,
    request,
    submit_task,
    fetch_task,
    *,
    runtime_settings=None,
    max_polls=60,
    poll_interval=0,
):
    """Submit once, persist the ID, and resume polling that ID after interruption."""
    if not isinstance(request, dict):
        raise ValueError('Task request must be a JSON object')
    options = validate_desk_options(request.get('options'))
    if request.get('server') not in (None, '') or request.get('vlmUrl') not in (None, ''):
        raise ValueError('Remote server submission fields are forbidden')
    if 'offline' in request and request['offline'] is not True:
        raise ValueError('Explicit online submission is forbidden')
    if (
        not isinstance(runtime_settings, dict)
        or runtime_settings.get('offline') is not True
        or not isinstance(runtime_settings.get('modelSource'), str)
        or not runtime_settings['modelSource']
        or not isinstance(runtime_settings.get('modelRoot'), str)
        or not runtime_settings['modelRoot']
    ):
        raise ValueError('A verified offline local runtime preflight is required')
    if type(max_polls) is not int or max_polls < 1:
        raise ValueError('max_polls must be a positive integer')
    if (
        isinstance(poll_interval, bool)
        or not isinstance(poll_interval, (int, float))
        or poll_interval < 0
    ):
        raise ValueError('poll_interval must be a non-negative number')
    canonical_request = json.loads(json.dumps(request))
    canonical_request['options'] = key_options(options)
    canonical_request['runtimeSettings'] = {
        key: runtime_settings[key] for key in RUNTIME_FIELDS
    }
    request_hash = canonical_digest(canonical_request)
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
    for poll_number in range(max_polls):
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
        if poll_interval and poll_number + 1 < max_polls:
            time.sleep(poll_interval)
    raise TimeoutError('Task is still running; resume polling the same saved task ID')


def run_codex(desk_root, *arguments):
    cli = Path(desk_root).resolve() / 'Codex.ps1'
    if not cli.is_file():
        raise ValueError('Codex.ps1 not found')
    command = [
        'powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', str(cli), *[str(value) for value in arguments],
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding='utf-8',
        timeout=150,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )
    if result.returncode:
        raise RuntimeError('MinerU Desk command failed; inspect local diagnostics')
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError('MinerU Desk returned invalid JSON') from exc


def validate_cli_request(request):
    if not isinstance(request, dict):
        raise ValueError('Submission request must be a JSON object')
    allowed = {'files', 'outputRoot', 'options'}
    if set(request) != allowed:
        raise ValueError('Submission request must contain only files, outputRoot, and options')
    files = request.get('files')
    if not isinstance(files, list) or len(files) != 1:
        raise ValueError('Exactly one local input file is required')
    source = Path(files[0]).expanduser()
    if not source.is_absolute() or not source.is_file():
        raise ValueError('Submission source must be an existing absolute local file')
    output_root = Path(request.get('outputRoot', '')).expanduser()
    if not output_root.is_absolute():
        raise ValueError('Submission outputRoot must be absolute')
    validate_desk_options(request.get('options'))
    return request


def validated_runtime_preflight(state):
    if not isinstance(state, dict):
        raise ValueError('MinerU Desk state must be a JSON object')
    if state.get('paused') is True:
        raise ValueError('MinerU Desk queue is paused')
    settings = state.get('settings')
    if (
        not isinstance(settings, dict)
        or settings.get('offline') is not True
        or not isinstance(settings.get('modelSource'), str)
        or not settings['modelSource']
        or not isinstance(settings.get('modelRoot'), str)
        or not settings['modelRoot']
        or settings.get('serverUrl') not in (None, '')
        or settings.get('vlmUrl') not in (None, '')
    ):
        raise ValueError('MinerU Desk must be verified offline with no remote endpoints')
    return {key: settings[key] for key in RUNTIME_FIELDS}


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
        public_options = validate_desk_options(base.get('options'))
        settings = base.get('runtimeSettings')
        if not isinstance(settings, dict) or any(key not in settings for key in RUNTIME_FIELDS):
            raise ValueError('Every lineage node must include runtime settings')
        public_settings = {key: settings[key] for key in RUNTIME_FIELDS}
        if public_settings['offline'] is not True:
            raise ValueError('Every lineage node must be offline')
        identity = {
            'key': base.get('key'),
            'source': str(Path(base.get('source', '')).expanduser().resolve()),
            'options': key_options(public_options),
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
    result['options'] = validate_desk_options(task['options'])
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--desk-root', type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--task-id')
    source.add_argument('--request', type=Path)
    parser.add_argument('--state', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-polls', type=int, default=120)
    parser.add_argument('--poll-interval', type=float, default=5.0)
    args = parser.parse_args(argv)
    try:
        if args.request is None:
            if args.state is not None:
                raise ValueError('--state is only valid with --request')
            record = export(args.desk_root, args.task_id)
        else:
            if args.state is None:
                raise ValueError('--state is required with --request')
            request = validate_cli_request(
                json.loads(args.request.read_text(encoding='utf-8-sig'))
            )
            runtime_settings = validated_runtime_preflight(
                run_codex(args.desk_root, 'request', 'GET', 'state')
            )

            def submit_task(payload):
                if payload != request:
                    raise ValueError('Submission payload changed after validation')
                response = run_codex(args.desk_root, 'submit', args.request.resolve())
                if not isinstance(response, list) or len(response) != 1:
                    raise ValueError('Desk must return exactly one submitted task')
                return response[0].get('id') if isinstance(response[0], dict) else None

            def fetch_task(task_id):
                return run_codex(args.desk_root, 'request', 'GET', f'tasks/{task_id}')

            task = submit_resume_and_poll(
                args.state,
                request,
                submit_task,
                fetch_task,
                runtime_settings=runtime_settings,
                max_polls=args.max_polls,
                poll_interval=args.poll_interval,
            )
            record = export(args.desk_root, task['id'], fetch_task=fetch_task)
        atomic_json(args.output, record)
        print('TASK_EXPORTED ' + str(args.output.resolve()))
        return 0
    except TimeoutError as exc:
        print('PENDING ' + str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print('ERROR ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
