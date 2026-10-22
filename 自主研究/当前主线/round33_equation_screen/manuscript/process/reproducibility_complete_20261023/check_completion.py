"""Bounded Stage6 completion audit. Standard library only; no training/model loading.

Default: print a compact check summary without writing files.
--write: save audit JSON/CSV only beside this script.
Uses frozen complete_v1 and completion_archive_20261023, never live checkpoints.
Old 398 artifact bytes are NOT rehashed: their frozen map and formal-gate proof
are reused explicitly. All 90 completed new artifacts are rehashed.
"""
import argparse
import ast
import csv
import hashlib
import json
import math
from pathlib import Path
import re
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
ARCHIVE = ROOT / 'validation/stage6_20261022/completion_archive_20261023'
ANALYSIS = ROOT / 'validation/stage6_analysis_20261022/complete_v1'
RECOVERY = ROOT / 'validation/stage6_recovery_20261023'
checks, inputs = [], {}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def track(path, role, expected=None):
    path = Path(path)
    actual = digest(path)
    key = str(path)
    entry = inputs.setdefault(key, {'sha256': actual, 'bytes': path.stat().st_size,
                                    'roles': []})
    if role not in entry['roles']:
        entry['roles'].append(role)
    if expected is not None:
        entry.setdefault('expected_sha256', []).append(expected)
        check('hash:' + role + ':' + path.name, actual == expected, 'byte_hash',
              {'path': key, 'actual': actual, 'expected': expected})
    return actual


def read(path, role):
    track(path, role)
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def check(name, ok, layer, detail=None):
    checks.append({'id': name, 'status': 'PASS' if ok else 'FAIL',
                   'evidence_layer': layer, 'detail': detail})


def keyed(rows):
    return {tuple(row['job']): row for row in rows}


def close_sequences(left, right, rtol, atol):
    return len(left) == len(right) == 5 and all(
        math.isfinite(x) and math.isfinite(y) and abs(x-y) <= atol + rtol*abs(y)
        for x, y in zip(left, right))


def main(write=False):
    manifest = read(ARCHIVE/'archive_manifest.json', 'completion_archive_manifest')
    state = read(ARCHIVE/'final_runtime_status.json', 'frozen_final_state')
    validation = read(ARCHIVE/'results_validation.json', 'frozen_validation')
    summary = read(ARCHIVE/'summary.json', 'frozen_summary')
    gate = read(ARCHIVE/'engineering_gate.json', 'frozen_current_gate')
    plan = read(ARCHIVE/'task_plan.json', 'frozen_plan')
    exit_event = read(ARCHIVE/'runner_exit_observation.json', 'archived_runner_exit')
    analysis = read(ANALYSIS/'analysis_evidence.json', 'complete_v1_evidence')
    old_path = ROOT/'validation/stage5_analysis_20261022/analysis_evidence.json'
    old = read(old_path, 'old398_frozen_map')
    evidence = analysis['evidence']
    track(old_path, 'old398_map_bound_by_final', evidence['old_manifest_sha256'])
    archive_files = {p.relative_to(ARCHIVE).as_posix() for p in ARCHIVE.rglob('*') if p.is_file()}
    expected_archive = set(manifest['archived_files']) | {'archive_manifest.json', 'runner_exit_observation.json'}
    check('archive_exact_39_files', archive_files == expected_archive and len(archive_files) == 39,
          'directory_metadata', {'observed': len(archive_files), 'bound_core': len(manifest['archived_files'])})
    for rel, entry in manifest['archived_files'].items():
        track(ARCHIVE/rel, 'archive37', entry['sha256'])
        check('archive_size:' + rel, (ARCHIVE/rel).stat().st_size == entry['bytes'], 'directory_metadata')
    track(ARCHIVE/'runner_exit_observation.json', 'runner_exit_separate_binding', manifest['runner_exit_observation_sha256'])
    frozen_by_source = {v['source_path']: (rel, v) for rel, v in manifest['archived_files'].items()}
    bound_inputs = {}
    for source, expected in evidence['input_sha256'].items():
        found = frozen_by_source.get(source)
        ok = found is not None and found[1]['sha256'] == expected
        check('analysis_input_frozen_binding:' + Path(source).name, ok, 'byte_hash')
        bound_inputs[source] = {'archive_path': str(ARCHIVE/found[0]) if found else None,
                                'sha256': expected, 'matches_archive': ok}
    check('analysis_exact_five_inputs', len(bound_inputs) == 5, 'frozen_report')
    check('analysis_embedded_runtime_equals_archive', evidence['runtime_status'] == state, 'frozen_report')
    for rel, expected in analysis['output_sha256'].items():
        track(ANALYSIS/rel, 'complete_v1_derived_output_binding', expected)
    check('analysis_inventory_only', analysis['analysis_state'] == 'complete'
          and analysis['new_task_count'] == 30 and analysis['default_comparison_records'] == 36
          and analysis['tau_records'] == 18 and len(analysis['records']) == 48,
          'frozen_analysis_metadata', {'new_training': 30, 'default_rows': 36, 'tau_rows': 18,
                                       'overlap_rows': 6, 'unique_analysis_records': 48})

    tau = [(tag, eq, 'hardic+layer', seed)
           for tag in ('sensitivity_tau003_v1', 'sensitivity_tau03_v1')
           for seed in (0, 1, 2) for eq in ('E1_heat', 'E3_fisher')]
    soap = [('final_soap64_v1', eq, method, seed) for seed in (0, 1, 2)
            for eq in ('E1_heat', 'E3_fisher') for method in ('vanilla', 'hardic', 'hardic+layer')]
    expected_jobs = tau + soap
    maps = {'state': keyed(state['tasks']), 'plan': keyed(plan['jobs']),
            'validation': keyed(validation['results']), 'summary': keyed(summary['results']),
            'summary_tasks': keyed(summary['task_status'])}
    for name, rows in maps.items():
        check('exact_30_jobs:' + name, len(rows) == 30 and set(rows) == set(expected_jobs), 'identity_inventory')
    check('exact_30_jobs:gate', gate['tasks'] == [list(j) for j in expected_jobs], 'identity_inventory')
    check('state_complete', state['phase'] == 'completed' and state['counts'] ==
          {'queued': 0, 'running': 0, 'completed': 30, 'failed': 0}, 'runtime_saved_state')
    prereg = 'bfe89e3a07f1bb3bcc8e049d8d3d7ff95b4a647a'
    check('prereg_exact_binding', all(x['prereg_commit'] == prereg for x in
          (manifest, state, validation, summary, gate, plan, analysis)), 'protocol_binding')
    check('formal_reports_complete_30', all(x['complete'] is True and x['required_count'] ==
          x['validated_count'] == 30 for x in (validation, summary)), 'saved_scientific_validation')
    check('validation_summary_results_identical', maps['validation'] == maps['summary'], 'saved_scientific_validation')
    check('gate_passed_and_reference_checks', gate['passed'] is True and len(gate['references']) == 2
          and all(r['passed'] and r['N64_N96_max_abs'] <= r['tolerance'] == 1e-8 for r in gate['references']),
          'saved_engineering_reference_gate', gate['references'])
    current_gate_hash = digest(ARCHIVE/'engineering_gate.json')
    check('state_current_gate_binding', state['current_gate_sha256'] == current_gate_hash, 'byte_hash')
    for rel, expected in gate['source_hashes'].items():
        track(ROOT/rel, 'current_gate12_source', expected)
    check('analysis_gate_source12_equal', evidence['source_hashes'] == gate['source_hashes']
          and len(gate['source_hashes']) == 12, 'source_lineage')

    lineage = state['source_lineage']
    original, later = lineage
    check('source_lineage_exact_21_9', len(original['jobs']) == 21 and len(later['jobs']) == 9
          and original['jobs'] + later['jobs'] == [list(j) for j in expected_jobs]
          and original['role'] == 'original_workers' and later['role'] == 'current_orchestration', 'source_lineage')
    changed = sorted(k for k in original['source_hashes'] if original['source_hashes'][k] != later['source_hashes'][k])
    check('only_orchestration_test_differ', changed == ['stage6_runner.py', 'test_stage6_runner.py'],
          'source_lineage', {'different': changed, 'unchanged_other_sources': 10})
    check('new_lineage_gate_binding', later['source_hashes'] == gate['source_hashes']
          and later['gate_sha256'] == current_gate_hash, 'source_lineage')
    recovery_lineage = gate['recovery_lineage']
    recovery_manifest = Path(recovery_lineage['manifest']['path'])
    track(recovery_manifest, 'recovery_manifest', recovery_lineage['manifest']['sha256'])
    recovery = read(recovery_manifest, 'recovery_manifest_content')
    check('recovery_exact_seven_artifacts', recovery['artifacts'] == recovery_lineage['artifacts']
          and len(recovery['artifacts']) == 7, 'recovery_binding')
    for role, item in recovery['artifacts'].items():
        track(Path(item['path']), 'recovery7:' + role, item['sha256'])
    check('original_lineage_prior_gate_binding', original['gate_sha256'] == recovery_lineage['prior_gate_sha256']
          and original['source_hashes'] == recovery_lineage['prior_source_hashes'], 'source_lineage')
    reconciled = keyed(recovery_lineage['reconciled'])
    check('original42_exit0_saved_handle_evidence', len(reconciled) == 21 and
          set(reconciled) == set(map(tuple, original['jobs'])) and all(
              r[role]['exit_code'] == 0 and r[role]['identity_verified'] is True and
              r[role]['event'] == 'process_exited' and r[role]['role'] == role
              for r in reconciled.values() for role in ('worker', 'launcher')), 'saved_native_HANDLE_observation')
    event_file = Path(recovery['artifacts']['observer_events']['path'])
    observer_events = [json.loads(line) for line in event_file.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    exits = [x for x in observer_events if x.get('event') == 'process_exited']
    check('original42_exit_events_present', len(exits) == 42 and all(e['exit_code'] == 0 for e in exits)
          and all(r[role] in exits for r in reconciled.values() for role in ('worker', 'launcher')),
          'saved_native_HANDLE_observation', {'exit_events': len(exits)})
    check('original_observer_journal_closed', observer_events[-1].get('event') == 'observer_completed'
          and observer_events[-1].get('all_handles_signaled') is True, 'saved_native_HANDLE_observation', observer_events[-1])
    gate_time = datetime.fromisoformat(gate['time_utc'])
    check('new_gate_after_original42_exit', gate_time > datetime.fromisoformat(observer_events[-1]['utc']),
          'saved_runtime_timing', {'observer_completed_utc': observer_events[-1]['utc'], 'new_gate_utc': gate['time_utc']})
    check('only_remaining9_started_after_new_gate', all(
          datetime.fromisoformat(maps['state'][tuple(j)]['attempts'][0]['started_utc']) >= gate_time
          for j in later['jobs']), 'saved_runtime_timing')
    observer_archive = read(event_file.parent/'archive_manifest.json', 'closed_observer_archive_manifest')
    for item in observer_archive['files']:
        track(Path(item['archive']), 'closed_observer_archive_file', item['sha256'])

    new_raw = manifest['new_raw_files']
    old_raw = old['raw_sha256']
    check('old398_map_bound_in_final_488', len(old_raw) == 398 and all(
          evidence['raw_sha256'].get(k) == v for k, v in old_raw.items()), 'reused_formal_gate_and_frozen_map')
    check('old398_formal_unchanged_reports', gate['old_results'] == summary['old_results']
          and gate['old_results']['files'] == 398 and gate['old_results']['unchanged'] is True
          and evidence['old398_unchanged'] is True, 'reused_formal_gate',
          {'old398_artifact_bytes_rehashed_this_audit': False})
    check('new90_exact_difference', len(new_raw) == 90 and not set(new_raw) & set(old_raw)
          and evidence['raw_sha256'] == (old_raw | new_raw) and evidence['new_raw_files'] == 90,
          'frozen_manifest_map')
    for rel, expected in new_raw.items():
        track(ROOT/rel, 'completed_new90_artifact', expected)

    log_pattern = re.compile(r'warning|traceback|exception|runtimeerror|out of memory|\boom\b|\bnan\b|\binf\b|error:', re.I)
    log_findings, task_rows, bundle_paths = [], [], set()
    constant_config = {'width': 64, 'depth': 4, 'adam_steps': 20000, 'lr0': .001, 'lr1': 1e-5,
                       'nf': 4096, 'nb': 256, 'n0': 256, 'lbfgs_iters': 3000, 'lbfgs_chunk': 50,
                       'nf_fixed': 8192, 'nb_fixed': 512, 'n0_fixed': 512, 'rba_gamma': .999,
                       'rba_eta': .01, 'arch': 'mlp', 'pirate_blocks': 3, 'fourier_scale': 1.,
                       'causal_eps': 0., 'causal_chunks': 32, 'w_ic': 1, 't_refine': 0,
                       'soap_freq': 10, 'soap_beta': .95}
    for job in expected_jobs:
        task, planned, result = (maps[k][job] for k in ('state', 'plan', 'validation'))
        attempt = task['attempts'][0]
        tag, eq, method, seed = job
        label = '__'.join(map(str, job))
        config = constant_config | {'tau': .03 if tag == 'sensitivity_tau003_v1' else .3 if tag == 'sensitivity_tau03_v1' else .1,
                                    'seed': seed, 'optimizer': 'soap_official64' if tag == 'final_soap64_v1' else 'adam'}
        check('config:' + label, task['config'] == planned['config'] == result['config'] == config, 'frozen_config')
        command = attempt['command']
        pos = command.index('--worker')
        settings = [command[i+1] for i, x in enumerate(command) if x == '--set']
        expected_settings = [k + '=' + str(v) for k, v in config.items()]
        check('argv:' + label, command == planned['command'] and command[pos+1:pos+5] == list(map(str, job))
              and len(settings) == len(config) and set(settings) == set(expected_settings), 'frozen_argv')
        check('single_attempt_completed:' + label, len(task['attempts']) == 1 and task['state'] == 'completed'
              and task['pid'] is None and attempt['exit_code'] == 0 and attempt['resume_checkpoint_present'] is False,
              'runtime_saved_attempt')
        check('summary_task:' + label, maps['summary_tasks'][job] == {k: task[k] for k in
              ('id', 'job', 'state', 'attempts', 'last_error')}, 'runtime_saved_attempt')
        is_original = job in reconciled
        lineage_gate = original['gate_sha256'] if is_original else current_gate_hash
        if is_original:
            r = reconciled[job]
            identity_ok = (attempt['pid'] == r['launcher']['pid'] and attempt['observed_worker_pid'] == r['worker']['pid']
                           and attempt['worker_exit_code'] == 0 and attempt['supervision_interrupted'] is True
                           and attempt['recovery_manifest_sha256'] == recovery_lineage['manifest']['sha256'])
        else:
            identity_ok = ('supervision_interrupted' not in attempt and 'worker_exit_code' not in attempt)
        check('attempt_source:' + label, attempt['source_gate_sha256'] == lineage_gate and identity_ok, 'source_lineage')
        check('task_saved_validation:' + label, task['validation'] == result and result['complete_and_recomputed'] is True,
              'saved_scientific_validation')
        tolerance = result['tolerance']
        arrays_ok = (tolerance == {'rtol': 1e-5, 'atol': 1e-9} and result['metrics']['times'] ==
                     result['recomputed_N64_GL200']['times'] == [.05, .1, .25, .5, 1.])
        for metric in ('vol', 'trace'):
            base = result['metrics'][metric]
            arrays_ok &= close_sequences(base, result['recomputed_N64_GL200'][metric], **tolerance)
            arrays_ok &= close_sequences(base, result['dense_metrics_N96_GL400'][metric], **tolerance)
        check('saved_metric_sequences:' + label, arrays_ok, 'saved_scientific_validation_arithmetic')
        n_expected = {'pde': 8192, 'left_neumann': 1024, 'right_dynamic': 1024, 'initial': 1024}
        check('saved_heldout:' + label, set(result['heldout']) == set(n_expected) and all(
              result['heldout'][k]['n'] == n and all(math.isfinite(result['heldout'][k][v]) and
              result['heldout'][k][v] >= 0 for v in ('rms', 'max_abs')) for k, n in n_expected.items()),
              'saved_heldout_metadata')
        h = result['history_counters']
        updates = 19999 if tag == 'final_soap64_v1' else 20000
        check('budget:' + label, h['adam_gradient_calls'] == 20000 and h['lbfgs_budget_used'] == 3000
              and h['lbfgs_stop_reason'] == 'budget_exhausted' and h['resumed_at'] == []
              and result['optimizer_accounting']['parameter_updates_inferred_from_frozen_optimizer_semantics'] == updates,
              'saved_budget_and_frozen_semantics')
        stem = method.replace('+', '_') + '_s' + str(seed)
        folder = Path('runs')/tag/eq
        expected_bundle = {stem+'.json', stem+'.pt', stem+'.model.pt'}
        check('bundle_exact3:' + label, set(result['bundle_sha256']) == expected_bundle
              and all(new_raw.get((folder/name).as_posix()) == value for name, value in result['bundle_sha256'].items()),
              'byte_bound_bundle_inventory')
        for name in expected_bundle:
            bundle_paths.add((folder/name).as_posix())
        raw = json.loads((ROOT/folder/(stem+'.json')).read_text(encoding='utf-8-sig'))
        check('raw_json_identity_and_history:' + label, (raw['tag'], raw['eq'], raw['method'], raw['seed']) == job
              and raw['config'] == config and raw['metrics'] == result['metrics']
              and all(raw['history'].get(k) == v for k, v in h.items()) and raw['env'] == gate['environment']
              and raw['artifacts']['base']['sha256'] == result['bundle_sha256'][stem+'.pt']
              and raw['artifacts']['model']['sha256'] == result['bundle_sha256'][stem+'.model.pt'], 'completed_json_metadata')
        log = ARCHIVE/'worker_logs'/Path(attempt['log']).name
        lines = log.read_text(encoding='utf-8-sig').splitlines()
        cmds = [json.loads(line[len('COMMAND '):]) for line in lines if line.startswith('COMMAND ')]
        starts = [re.match(r'^START (\S+) PID=(\d+) JOB=(.*)$', line) for line in lines]
        starts = [m for m in starts if m]
        log_identity_ok = len(starts) == 1 and ast.literal_eval(starts[0].group(3)) == job
        if is_original:
            log_identity_ok &= int(starts[0].group(2)) == attempt['observed_worker_pid']
        done = [line for line in lines if line.startswith('done ')]
        check('full_worker_log:' + label, cmds == [command] and log_identity_ok and len(done) == 1
              and (folder/(stem+'.json')).as_posix() in done[0].replace('\\', '/'), 'captured_production_log')
        for line_num, line in enumerate(lines, 1):
            if log_pattern.search(line):
                log_findings.append({'file': str(log), 'line': line_num, 'text': line})
        task_rows.append({'tag': tag, 'equation': eq, 'method': method, 'seed': seed,
                          'lineage': 'original21' if is_original else 'new9', 'state': task['state'],
                          'attempt_count': len(task['attempts']), 'attempt_exit_code': attempt['exit_code'],
                          'worker_HANDLE_exit_code': attempt.get('worker_exit_code', ''),
                          'resume_checkpoint_present': attempt['resume_checkpoint_present'],
                          'source_gate_sha256': lineage_gate, 'json_sha256': result['json_sha256'],
                          'adam_gradient_calls': h['adam_gradient_calls'], 'inferred_parameter_updates': updates,
                          'lbfgs_budget_used': h['lbfgs_budget_used'], 'lbfgs_n_iter': h['lbfgs_n_iter'],
                          'lbfgs_func_evals': h['lbfgs_func_evals'], 'lbfgs_stop_reason': h['lbfgs_stop_reason'],
                          'complete_and_recomputed': result['complete_and_recomputed'],
                          'attempt_wall_seconds': attempt['wall_seconds'], 'archived_worker_log': str(log)})
    check('bundle_union_exact_new90', bundle_paths == set(new_raw), 'byte_bound_bundle_inventory')
    for log in (ARCHIVE/'runner_logs').glob('*.log'):
        for num, line in enumerate(log.read_text(encoding='utf-8-sig').splitlines(), 1):
            if log_pattern.search(line):
                log_findings.append({'file': str(log), 'line': num, 'text': line})
    check('captured_new30_warning_error_token_scan', not log_findings, 'captured_production_log',
          {'pattern': log_pattern.pattern, 'matches': log_findings,
           'worker_logs': 30, 'final_runner_logs': 2, 'scope': 'captured files only; does not erase earlier runner failure'})

    check('runner91632_actual_exit0_saved_handle', exit_event['pid'] == state['runner_pid'] == 91632
          and exit_event['handle_signaled'] is True and exit_event['exit_code'] == 0
          and exit_event['command_line_verified'] is True, 'saved_native_HANDLE_observation', exit_event)
    deadline = state['review_deadline_unix']
    finished = datetime.fromisoformat(state['updated_utc']).timestamp()
    check('within_original_48h_window', abs(deadline - datetime.fromisoformat(state['first_started_utc']).timestamp() - 48*3600) < .01
          and finished <= deadline and datetime.fromisoformat(exit_event['observed_exit_utc']).timestamp() <= deadline,
          'saved_runtime_timing')
    stderr = Path(recovery['artifacts']['runner_stderr']['path'])
    incident_text = stderr.read_text(encoding='utf-8-sig', errors='replace')
    check('original_runner_failure_preserved', bool(state['failure_history']) and '[WinError 5]' in incident_text
          and 'PermissionError' in incident_text, 'captured_historical_incident')
    check('summary_preserves_runtime_lineage_failures_timing', all(summary[k] == state[k] for k in
          ('source_lineage', 'recovery_incidents', 'failure_history', 'total_runner_wall_seconds', 'batch_elapsed_seconds')),
          'frozen_report')

    tags = [('screen', 30), ('confirm', 24), ('causal1', 6), ('causal10', 6), ('pirate', 12),
            ('axis', 36), ('e4screen', 8), ('e4confirm', 12), ('final_ic_v1', 18),
            ('preflight4_adam', 12), ('preflight4_soap64', 12),
            ('sensitivity_tau003_v1', 6), ('sensitivity_tau03_v1', 6), ('final_soap64_v1', 18)]
    counts = []
    for tag, num in tags:
        actual = {p.relative_to(ROOT).as_posix() for p in (ROOT/'runs'/tag).rglob('*') if p.is_file()}
        bound = {p for p in evidence['raw_sha256'] if p.startswith('runs/'+tag+'/')}
        json_count = sum(p.endswith('.json') for p in actual)
        model_count = sum(p.endswith('.model.pt') for p in actual)
        base_count = sum(p.endswith('.pt') and not p.endswith('.model.pt') for p in actual)
        check('tag_inventory:' + tag, actual == bound and json_count == num, 'directory_metadata_and_frozen_map')
        counts.append({'tag': tag, 'scope': 'stage6_new' if tag in {j[0] for j in expected_jobs} else 'historical',
                       'json_records': json_count, 'base_pt': base_count, 'full_model_pt': model_count,
                       'raw_files': len(actual)})
    totals = {k: sum(r[k] for r in counts) for k in ('json_records', 'base_pt', 'full_model_pt', 'raw_files')}
    check('total206_records488_files', totals == {'json_records': 206, 'base_pt': 206, 'full_model_pt': 76, 'raw_files': 488},
          'directory_metadata_and_frozen_map', totals)

    test_paths = [RECOVERY/'pytest_attempt1.xml', RECOVERY/'pytest_final.xml',
                  RECOVERY/'pytest_final_attempt2.xml', RECOVERY/'timezone_binding_repair/pytest_attempt1.xml',
                  ROOT/'validation/stage6_20261022/pytest.xml']
    test_history = []
    for path in test_paths:
        sha = track(path, 'saved_engineering_test_history')
        suites = list(ET.parse(path).getroot().iter('testsuite'))
        counts_xml = {k: sum(int(s.attrib.get(k, 0)) for s in suites) for k in ('tests', 'failures', 'errors', 'skipped')}
        counts_xml['passed'] = counts_xml['tests'] - counts_xml['failures'] - counts_xml['errors'] - counts_xml['skipped']
        test_history.append({'path': str(path), 'sha256': sha, **counts_xml})
        sibling = path.with_suffix('.log')
        if sibling.exists():
            track(sibling, 'saved_engineering_test_log')
    check('final_gate110_junit_binding', digest(test_paths[-1]) == gate['runner_tests']['junit_sha256']
          and test_history[-1]['tests'] == 110 and test_history[-1]['failures'] == test_history[-1]['errors'] == 0,
          'saved_engineering_tests_only')
    for rel in ('manuscript/process/reproducibility/REPRODUCIBILITY_CN.md',
                'manuscript/process/reproducibility/AI_USE_STATEMENT_N03_CN.md',
                'manuscript/process/reproducibility_recovery_20261023/RECOVERY_REPRODUCIBILITY_CN.md',
                'manuscript/process/reproducibility_recovery_20261023/FINAL_REFRESH_FIELDS_CN.md'):
        track(ROOT/rel, 'prior_reproducibility_material_preserved')
    track(RECOVERY/'RECOVERY_ROUTE.md', 'mutable_guide_current_value_not_manifest_artifact')
    track(Path(__file__).resolve(), 'this_readonly_checker')
    failures = [c for c in checks if c['status'] == 'FAIL']
    result = {'schema': 'r33_stage6_complete_reproducibility_audit_v1',
              'generated_utc': datetime.now(timezone.utc).isoformat(),
              'assessment_scope': 'bounded completion/runtime provenance and saved validation audit; no training/model reload/reference integration/new gate/test rerun',
              'frozen_analysis_version': 'complete_v1', 'archive_release_reference_reported_by_parent': '7d3857e',
              'overall_scoped_result': 'PASS' if not failures else 'FAIL',
              'check_count': len(checks), 'failed_check_count': len(failures), 'checks': checks,
              'counts': totals, 'tag_counts': counts, 'analysis_input_archive_binding': bound_inputs,
              'source_lineage': lineage, 'archived_runner_exit': exit_event,
              'production_log_token_findings': log_findings, 'saved_engineering_test_history': test_history,
              'costs': analysis['costs'],
              'limits': ['historical 130 full production logs unavailable; new30 cannot replace them',
                         'old398 byte checks reused from formal gate; this audit checks frozen map binding and directory inventory, not rehashes old398',
                         'saved numerical validation and arrays checked; no independent model reload/ODE integration or figure/data regrouping',
                         'complete_v2 presentation refresh pending; v1 derived output/source hashes remain version specific',
                         'engineering110 pass does not prove scientific improvement; no new scientific decision',
                         'human author identity/contribution/AI-use final responsibility verification pending'],
              'not_run': ['training', 'gate', 'runner', 'checkpoint_content_read', 'torch_import',
                          'full_engineering_tests', 'model_reload', 'reference_ODE', 'data_or_chart_regrouping']}
    if write:
        (OUT/'completion_checks.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        hashes = {'schema': 'r33_stage6_complete_input_hashes_v1', 'generated_utc': result['generated_utc'],
                  'scope': result['assessment_scope'], 'files': inputs,
                  'old398_expected_only_not_fresh_rehashed': old_raw,
                  'complete_v1_analysis_code_historical_hashes': analysis['analysis_code_sha256']}
        (OUT/'input_hashes.json').write_text(json.dumps(hashes, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        for filename, rows in (('tag_counts.csv', counts), ('task_inventory.csv', task_rows)):
            with (OUT/filename).open('w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    print(json.dumps({'scoped_result': result['overall_scoped_result'], 'checks': len(checks),
                      'failures': failures, 'counts': totals, 'input_file_count': len(inputs),
                      'written': write}, ensure_ascii=False))
    return 1 if failures else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='write only audit JSON/CSV beside this script')
    raise SystemExit(main(parser.parse_args().write))
