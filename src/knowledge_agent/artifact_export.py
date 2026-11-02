"""Deterministic submission projection; runtime logs remain untouched."""

import argparse
import hashlib
import json
import os
from pathlib import Path

FORMAT = 'compact-v1'


def read(files, name, default=None):
    path = files.get(name)
    return json.loads(path.read_text()) if path else default


def lines(files, name):
    path = files.get(name)
    return [json.loads(line) for line in path.read_text().splitlines()] if path else []


def save(path, value, *, jsonl=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    content = (''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in value) if jsonl else
               json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    if path.exists() and path.read_text() != content:
        raise FileExistsError(f'Refusing to overwrite different submission evidence: {path}')
    path.write_text(content)


def selected(value, keys):
    return {k: value[k] for k in keys if k in value and value[k] is not None}


def tool_summary(result):
    data = result.get('data') or {}
    items = (data.get('hits') or []) + (data.get('segments') or [])
    return {
        'tool': result['tool'], 'tool_call_id': result['tool_call_id'], 'status': result['status'],
        'returned_items': len(items),
        'documents': sorted({item['doc_id'] for item in items}),
        'evidence_ids': list(dict.fromkeys(item['evidence_id'] for item in items if 'evidence_id' in item)),
        'errors': result.get('errors', []), 'execution': result.get('execution', {}),
    }


def compact_trace(files, output):
    evidence = output.get('observed_evidence', read(files, 'observed-evidence.json', []))
    refs = []
    for item in evidence:
        ref = selected(item, ('evidence_id', 'tool_call_id', 'doc_id', 'content_hash',
                              'delivered_to_model', 'reused_from'))
        ref['spans'] = [selected(s, ('start', 'end')) for s in item.get('source_spans') or [item]]
        refs.append(ref)
    events = [{'event': 'evidence_index', 'items': refs}]
    returns = {r['tool_call_id']: r for r in lines(files, 'tool-results.jsonl')}
    retained = {
        'research_complete', 'evidence_requested', 'session_evidence_restored',
        'model_request_failed', 'model_request_retry', 'model_context_rejected',
        'budget_blocked', 'framework_stopped', 'runtime_error', 'final_result',
        'test_fault_injected', 'offline_fault_injected', 'output_rejected',
        'test_observation_boundary',
        'validation_failed', 'output_retry_limit', 'output_correction_reserved',
    }
    for event in lines(files, 'trace.jsonl'):
        kind, payload = event['event_type'], event['payload']
        row = {'sequence': event['sequence'], 'event': kind,
               **selected(event, ('model_turn', 'origin'))}
        if kind == 'model_response':
            # Keep the actual chosen actions, including rejected or unexecuted calls.
            calls = [selected(p, ('tool_name', 'tool_call_id', 'args'))
                     for m in payload.get('messages', []) for p in m.get('parts', [])
                     if p.get('part_kind') == 'tool-call']
            for call in calls:
                if isinstance(call.get('args'), str):
                    try:
                        call['args'] = json.loads(call['args'])
                    except ValueError:
                        pass  # Preserve malformed arguments so a failed action stays inspectable.
                if call['tool_name'] == 'submit_answer' and isinstance(call.get('args'), dict):
                    call['args'] = selected(call['args'], ('status', 'decision_summary'))
            row.update(event='model_actions', actions=calls)
        elif kind == 'tool_requested':
            # Parameters already appear in model_actions; this records actual admission.
            row.update(data=selected(payload, ('tool', 'tool_call_id')))
        elif kind == 'tool_result':
            value = returns.get(payload['tool_call_id'])
            row.update(data=tool_summary(value) if value else payload)
        elif kind == 'answer_started':
            packet = read(files, f"answer-input-{payload['round']}.json", {})
            row.update(data={**payload, 'source_mapping': [
                selected(s, ('source_id', 'evidence_id', 'start', 'end')) for s in packet.get('sources', [])]})
        elif kind == 'answer_draft':
            # Keep source selection for every attempt, without repeating the complete answer.
            draft = payload['result']
            row.update(data={'status': draft['status'], 'decision_summary': draft['decision_summary'],
                             'source_ids': [p['source_ids'] for p in draft['parts']]})
        elif kind in retained or any(word in kind for word in ('reject', 'cancel', 'timeout', 'blocked')):
            row.update(data=payload)
        else:
            continue
        events.append(row)
    return events


def export_files(files, destination, case_id, run_id):
    """Publish input/output/trace and a shared corpus; omit session/debug-only folders."""
    destination = Path(destination)
    for value in (case_id, run_id):
        if not value or value in {'.', '..'} or Path(value).name != value:
            raise ValueError('case_id and run_id must be single path components')
    if 'output.json' not in files:
        return None
    output = read(files, 'output.json')
    inp = read(files, 'input.json', {})
    config = inp.get('config', {})
    input_path = destination / 'inputs' / case_id / run_id / 'input.json'
    corpus = read(files, 'corpus.json')
    corpus_ref = None
    if corpus:
        # Original documents and metadata are sufficient to resolve exact source spans.
        # Prepared chunks and repeated index snapshots are runtime diagnostics.
        shared = selected(corpus, ('corpus_hash', 'documents'))
        canonical = json.dumps(shared, ensure_ascii=False, sort_keys=True).encode()
        corpus_path = destination / 'corpora' / (hashlib.sha256(canonical).hexdigest() + '.json')
        save(corpus_path, shared)
        corpus_ref = os.path.relpath(corpus_path, input_path.parent)
    settings = selected(config, ('mode', 'model_name', 'retrieval_mode', 'requested_retrieval',
                                 'thinking', 'mock_scenario', 'max_model_turns', 'max_tool_calls',
                                 'max_http_attempts', 'model_timeout', 'tool_timeout', 'turn_timeout'))
    if 'corpus_path' in config:
        settings['fixture'] = Path(config['corpus_path']).parent.name
    compact_input = {'format': FORMAT, **selected(inp, ('question', 'session_id', 'turn_id', 'previous_run_id')),
                     'history': [selected(m, ('role', 'content')) for m in inp.get('effective_history', [])],
                     'settings': settings, 'corpus': corpus_ref}
    fault = read(files, 'fault-injection.json')
    if fault and (fault.get('injections') or fault.get('failure')):
        compact_input['fault_injection'] = fault
    metadata = read(files, 'run.json', {})
    compact_input['test'] = selected(metadata, ('scope', 'test_id', 'live_model', 'model_origin', 'scenario'))
    compact_output = {k: v for k, v in output.items() if k not in {'observed_evidence', 'action_summaries', 'tool_results'}}
    compact_output['export'] = {'format': FORMAT, 'raw_output_sha256': hashlib.sha256(files['output.json'].read_bytes()).hexdigest()}
    save(input_path, compact_input)
    save(destination / 'outputs' / case_id / run_id / 'output.json', compact_output)
    save(destination / 'traces' / case_id / run_id / 'trace.jsonl', compact_trace(files, output), jsonl=True)
    return {'case_id': case_id, 'run_id': run_id, 'format': FORMAT}


def export_run(source, destination, case_id):
    source = Path(source)
    return export_files({p.name: p for p in source.iterdir() if p.is_file()}, destination, case_id, source.name)


def convert_archive(source, destination):
    """Convert a previously exported full batch, validating every original manifest."""
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if destination.exists():
        raise FileExistsError('Use a new destination; never overwrite original evidence')
    count = 0
    for manifest in sorted(source.rglob('artifacts.json')):
        record = json.loads(manifest.read_text())
        root = manifest.parents[3]
        files = {}
        for entry in record['artifacts']:
            path = (root / entry['path']).resolve()
            if not path.is_relative_to(source) or hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
                raise ValueError(f'Invalid source artifact: {manifest}')
            files[path.name] = path
        result = export_files(files, destination / root.relative_to(source), record['case_id'], record['run_id'])
        count += result is not None
    return count


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Project full archived runs into compact submission evidence; never rerun the model.')
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(f'Exported {convert_archive(args.source, args.output)} runs.')
