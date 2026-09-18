"""Import verified local Desk artifacts into the existing page-mapped cache."""
from pathlib import Path
import hashlib
import json
import re
import shutil


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def contained(path, root):
    path = path.resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f'Missing or out-of-root MinerU artifact: {path}')
    return path


def import_task(task_json, pdf, output, pdf_hash, page_count, title, generated):
    task = json.loads(Path(task_json).read_text(encoding='utf-8-sig'))
    if task.get('status') not in ('completed', 'reused'):
        raise ValueError('MinerU task has not completed')
    options = task.get('options', {})
    if options.get('provider') != 'local' or options.get('pages') is not None:
        raise ValueError('Only full-document local tasks may become canonical caches')
    if Path(task.get('source', '')).resolve() != pdf.resolve():
        raise ValueError('MinerU task source does not match requested PDF')
    if task.get('source_sha256') != pdf_hash or digest(pdf) != pdf_hash:
        raise ValueError('MinerU task original source hash does not match requested PDF')
    task_id = task.get('id')
    base_task_id = task.get('base_task_id')
    lineage = task.get('lineage_task_ids')
    if (
        not isinstance(task_id, str)
        or not isinstance(base_task_id, str)
        or not isinstance(lineage, list)
        or not lineage
        or any(not isinstance(item, str) for item in lineage)
        or len(lineage) != len(set(lineage))
        or lineage[0] != task_id
        or lineage[-1] != base_task_id
    ):
        raise ValueError('MinerU task lineage is missing or invalid')
    if task['status'] == 'completed' and (base_task_id != task_id or lineage != [task_id]):
        raise ValueError('Completed MinerU task lineage is inconsistent')
    if task['status'] == 'reused':
        reused_from = task.get('reused_from_task_id')
        if (
            not isinstance(reused_from, str)
            or len(lineage) < 2
            or lineage[1] != reused_from
            or base_task_id == task_id
        ):
            raise ValueError('Reused MinerU task lineage is incomplete')
    root = Path(task['outputDir']).resolve()
    md = contained(Path(task['markdown']), root)
    stem = md.stem
    content_path = contained(md.parent / f'{stem}_content_list.json', root)
    middle_path = contained(md.parent / f'{stem}_middle.json', root)
    content = json.loads(content_path.read_text(encoding='utf-8'))
    middle = json.loads(middle_path.read_text(encoding='utf-8'))
    # Desk 0.3.1 binds source bytes to options/runtime in its cache key.
    # MinerU's *_origin.pdf is reserialized and is not byte-identical to input.
    settings = task.get('runtimeSettings', {})
    version = task.get('runtime_version')
    if not isinstance(version, str) or not version.endswith('version ' + str(middle.get('_version_name'))):
        raise ValueError('Missing or inconsistent task runtime version')
    for field in ('modelSource', 'offline', 'modelRoot'):
        if field not in settings:
            raise ValueError('Missing task runtime settings for source verification')
    if settings['offline'] is not True or options.get('backend') != 'pipeline':
        raise ValueError('Importer supports offline local Pipeline tasks only')
    payload = {'digest': pdf_hash, 'conversion': {k:v for k,v in options.items() if k != 'force'},
               'version': version, 'server': '', 'vlmUrl': '',
               **{k:settings[k] for k in ('modelSource', 'offline', 'modelRoot')}}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    if hashlib.sha256(encoded.encode('utf-8')).hexdigest() != task.get('key'):
        raise ValueError('Desk task cache key does not match current PDF/options/runtime')
    expected = list(range(page_count))
    if [p.get('page_idx') for p in middle.get('pdf_info', [])] != expected:
        raise ValueError('MinerU page map does not cover original PDF exactly')
    if not isinstance(content, list) or not content:
        raise ValueError('Empty or unsupported MinerU content list')
    known = {'text', 'equation', 'image', 'table', 'list', 'discarded', 'header', 'footer', 'page_number'}
    for block in content:
        if not isinstance(block, dict) or block.get('type') not in known:
            raise ValueError('Unsupported MinerU block: retain raw output and use explicit fallback')
        if type(block.get('page_idx')) is not int or block['page_idx'] not in expected:
            raise ValueError('Invalid MinerU block page index')
    metadata = {
        'task_id': task_id, 'task_status': task['status'],
        'source_sha256': pdf_hash, 'backend': middle.get('_backend'),
        'desk_cache_key': task['key'], 'source_verification': 'original_input_sha256',
        'runtime_version': version,
        'runtime_settings': {k: settings[k] for k in ('modelSource', 'offline', 'modelRoot')},
        'base_task_id': base_task_id, 'lineage_task_ids': lineage,
        'reused_from_task_id': task.get('reused_from_task_id'),
        'version': middle.get('_version_name'),
        'options': {k: options.get(k) for k in ('provider', 'backend', 'method', 'language', 'formula', 'table', 'pages')},
        'content_list_sha256': digest(content_path), 'middle_sha256': digest(middle_path),
        'raw_markdown': str(md), 'raw_output_dir': str(root),
    }
    source_map = {'source_pdf': str(pdf), 'pdf_sha256': pdf_hash,
                  'generated_at_utc': generated, 'extraction_source': 'mineru_desk_local',
                  'page_numbering': 'page_idx + 1; printed page numbers not inferred',
                  'mineru': metadata, 'pages': []}
    lines = ['---', 'source_pdf: ' + json.dumps(str(pdf), ensure_ascii=False),
             'pdf_sha256: ' + pdf_hash, f'pdf_pages: {page_count}',
             'extraction_source: mineru_desk_local', 'generated_cache: true', '---', '',
             '# ' + title, '', '> MinerU 本地解析缓存；数字、引文、公式及图表须回原 PDF 核验。', '']
    assets = output / 'assets'
    assets.mkdir(parents=True, exist_ok=True)
    count = images = 0
    uncertain = []

    def strings(value):
        if isinstance(value, str):
            return value
        if isinstance(value, list) and all(isinstance(x, str) for x in value):
            return '\n'.join(value)
        if value is None:
            return ''
        raise ValueError('Unsupported structured MinerU text field')

    for page_idx in expected:
        number = page_idx + 1
        lines += [f'## PDF 第 {number} 页', '']
        record = {'pdf_page': number, 'printed_page': None, 'blocks': [], 'figures': [], 'page_renders': []}
        chars = 0
        for item_index, block in enumerate(content):
            if block['page_idx'] != page_idx:
                continue
            kind = block['type']
            parts = []
            if kind == 'equation':
                parts.append('$$\n' + strings(block.get('text')) + '\n$$')
            elif kind == 'list':
                parts.append(strings(block.get('list_items')))
            else:
                parts.append(strings(block.get('text')))
            for field in ('image_caption', 'table_caption', 'table_body', 'image_footnote', 'table_footnote'):
                if field in block:
                    parts.append(strings(block[field]))
            text = '\n\n'.join(p for p in parts if p)
            # A document's text cannot forge canonical page delimiters.
            text = re.sub(r'(?m)^(## PDF 第 \d+ 页)$', r'\\\1', text)
            chars += len(re.sub(r'\s+', '', text))
            count += 1
            anchor = f'S{count:04d}'
            record['blocks'].append({'id': anchor, 'type': kind, 'bbox': block.get('bbox'),
                'mineru_item_index': item_index, 'extraction': 'mineru_desk_local', 'confidence': 'requires_visual_check'})
            lines += [f'<a id="{anchor}"></a>', text, '']
            if block.get('img_path'):
                image = contained(md.parent / block['img_path'], md.parent)
                name = digest(image)[:20] + image.suffix.lower()
                shutil.copyfile(image, assets / name)
                relative = 'assets/' + name
                images += 1
                figure = f'F{images:04d}'
                lines += [f'<a id="{figure}"></a>', f'![PDF 第 {number} 页 {figure}]({relative})', '']
                record['figures'].append({'id': figure, 'asset': relative, 'extraction': 'mineru_desk_local'})
            elif not text.strip():
                raise ValueError(f'MinerU block has no usable content: {kind}')
        record['text_characters'] = chars
        record['needs_ocr'] = chars < 40
        if chars < 40:
            uncertain.append(number)
            lines += ['> [本页文字稀少或未识别；需回原 PDF 核验，不视为空白页。]', '']
        source_map['pages'].append(record)
    stats = {'page_count': page_count, 'text_blocks': count, 'captions': 0,
             'embedded_images': images, 'rendered_pages': 0, 'ocr_pages': uncertain,
             'visual_risk': 'MinerU OCR/版面解析仍需核验；文字稀少页不等于空白页', 'engine': 'MinerU Desk local'}
    return '\n'.join(lines).rstrip() + '\n', source_map, stats
