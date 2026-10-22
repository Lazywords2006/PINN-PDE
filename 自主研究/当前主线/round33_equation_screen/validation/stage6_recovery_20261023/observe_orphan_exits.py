"""Read-only Windows HANDLE observer. Never starts, stops, or signals training."""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class WindowsQuery:
    def __init__(self):
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.ntdll = ctypes.WinDLL('ntdll')
        self.shell = ctypes.WinDLL('shell32', use_last_error=True)
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        self.kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel.WaitForSingleObject.restype = wintypes.DWORD
        self.kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        self.ntdll.NtQueryInformationProcess.argtypes = [wintypes.HANDLE, wintypes.ULONG, ctypes.c_void_p, wintypes.ULONG, ctypes.POINTER(wintypes.ULONG)]
        self.ntdll.NtQueryInformationProcess.restype = wintypes.LONG
        self.shell.CommandLineToArgvW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
        self.shell.CommandLineToArgvW.restype = ctypes.POINTER(wintypes.LPWSTR)
        self.kernel.LocalFree.argtypes = [ctypes.c_void_p]

    def argv(self, command):
        count = ctypes.c_int()
        pointer = self.shell.CommandLineToArgvW(command, ctypes.byref(count))
        if not pointer:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return [pointer[i] for i in range(count.value)]
        finally:
            self.kernel.LocalFree(pointer)

    def open(self, pid):
        # SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION; no write/terminate rights.
        handle = self.kernel.OpenProcess(0x00100000 | 0x1000, False, pid)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        return handle

    def identity(self, handle):
        times = [wintypes.FILETIME() for _ in range(4)]
        if not self.kernel.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
            raise ctypes.WinError(ctypes.get_last_error())
        creation = times[0].dwHighDateTime << 32 | times[0].dwLowDateTime
        image = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(image))
        if not self.kernel.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        needed = wintypes.ULONG()
        self.ntdll.NtQueryInformationProcess(handle, 60, None, 0, ctypes.byref(needed))
        if not 0 < needed.value < 1024 * 1024:
            raise OSError('Command-line information size unavailable')
        buffer = ctypes.create_string_buffer(needed.value)
        result = self.ntdll.NtQueryInformationProcess(handle, 60, buffer, len(buffer), ctypes.byref(needed))
        if result < 0:
            raise OSError(f'NtQueryInformationProcess status {result:#x}')

        class UnicodeString(ctypes.Structure):
            _fields_ = [('length', wintypes.USHORT), ('maximum', wintypes.USHORT), ('buffer', ctypes.c_void_p)]

        value = UnicodeString.from_buffer(buffer)
        begin, end = ctypes.addressof(buffer), ctypes.addressof(buffer) + len(buffer)
        if value.length % 2 or not begin <= value.buffer <= value.buffer + value.length <= end:
            raise OSError('Command-line string lies outside returned buffer')
        command = ctypes.wstring_at(value.buffer, value.length // 2)
        return {'creation_filetime_utc': creation, 'executable_path': image.value,
                'command_line': command, 'argv': self.argv(command)}

    def exit_code(self, handle):
        waited = self.kernel.WaitForSingleObject(handle, 0)
        if waited == 258:
            return None
        if waited != 0:
            raise ctypes.WinError(ctypes.get_last_error())
        code = wintypes.DWORD()
        if not self.kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
            raise ctypes.WinError(ctypes.get_last_error())
        return code.value


def observe(snapshot, output):
    api = WindowsQuery()
    inventory = json.loads(snapshot.read_text(encoding='utf-8-sig'))
    output.mkdir(parents=True, exist_ok=False)
    journal = (output / 'events.jsonl').open('x', encoding='utf-8', buffering=1)
    handles = []

    def emit(event):
        event = dict(utc=now(), **event)
        journal.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + '\n')
        journal.flush()
        os.fsync(journal.fileno())

    try:
        emit({'event': 'observer_started', 'observer_pid': os.getpid(),
              'snapshot': str(snapshot), 'snapshot_sha256': digest(snapshot),
              'observer_source_sha256': digest(__file__),
              'original_gate_sha256': inventory['original_gate_sha256'],
              'access_mask': 'SYNCHRONIZE|PROCESS_QUERY_LIMITED_INFORMATION',
              'process_control': False})
        tasks = {tuple(t['job']): t for t in inventory['tasks'] if t['state'] == 'running'}
        errors = []
        # Open every handle first so an early-exiting process retains a queryable object.
        for row in inventory['workers']:
            try:
                handles.append([api.open(row['pid']), row, None, False])
            except Exception as exc:
                error = {'event': 'attach_failed', 'pid': row['pid'], 'error': repr(exc)}
                errors.append(error)
                emit(error)
        attached = []
        for item in handles:
            handle, row, _, _ = item
            try:
                actual = api.identity(handle)
                argv = actual['argv']
                offset = argv.index('--worker')
                job = (argv[offset + 1], argv[offset + 2], argv[offset + 3], int(argv[offset + 4]))
                task = tasks[job]
                role = 'launcher' if row['pid'] == task['pid'] else 'worker'
                if role == 'worker' and row['ppid'] != task['pid']:
                    raise ValueError('Worker parent is not original launcher')
                if abs(actual['creation_filetime_utc'] - row['creation_filetime_utc']) > 10:
                    raise ValueError('PID creation time differs from CIM inventory')
                if os.path.normcase(actual['executable_path']) != os.path.normcase(row['executable_path']):
                    raise ValueError('Executable differs from CIM inventory')
                if actual['command_line'] != row['command_line']:
                    raise ValueError('Command line differs from CIM inventory')
                if argv[1:] != task['attempts'][-1]['command'][1:]:
                    raise ValueError('Arguments differ from original dispatched command')
                identity = dict(pid=row['pid'], ppid=row['ppid'], role=role, job=list(job),
                                **actual)
                item[2] = identity
                attached.append(identity)
                emit(dict(event='attached', **identity))
            except Exception as exc:
                error = {'event': 'identity_failed', 'pid': row['pid'], 'error': repr(exc)}
                errors.append(error)
                emit(error)
        ready = {'observer_pid': os.getpid(), 'started_utc': now(), 'attached_count': len(attached),
                 'expected_count': len(inventory['workers']), 'errors': errors,
                 'snapshot_sha256': digest(snapshot), 'processes': attached}
        (output / 'attached.json').write_text(json.dumps(ready, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        emit({'event': 'attachment_complete', 'attached_count': len(attached), 'errors': len(errors)})
        print(json.dumps({'output': str(output), 'attached_count': len(attached), 'errors': errors}), flush=True)
        while any(not item[3] for item in handles):
            for item in handles:
                handle, row, identity, finished = item
                if finished:
                    continue
                code = api.exit_code(handle)
                if code is not None:
                    emit({'event': 'process_exited', 'pid': row['pid'], 'exit_code': code,
                          'identity_verified': identity is not None,
                          'role': identity['role'] if identity else None,
                          'job': identity['job'] if identity else None,
                          'creation_filetime_utc': identity['creation_filetime_utc'] if identity else None})
                    item[3] = True
            if any(not item[3] for item in handles):
                time.sleep(1)
        emit({'event': 'observer_completed', 'all_handles_signaled': True})
        return 0 if not errors else 2
    except BaseException:
        import traceback
        emit({'event': 'observer_error', 'error': traceback.format_exc()})
        raise
    finally:
        for handle, *_ in handles:
            api.kernel.CloseHandle(handle)
        journal.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--probe-self', action='store_true')
    args = parser.parse_args()
    if args.probe_self:
        api = WindowsQuery()
        handle = api.open(os.getpid())
        try:
            identity = api.identity(handle)
            assert api.exit_code(handle) is None
            print(json.dumps(identity, ensure_ascii=False), flush=True)
        finally:
            api.kernel.CloseHandle(handle)
        return 0
    if args.snapshot is None or args.output is None:
        parser.error('--snapshot and --output required')
    return observe(args.snapshot.resolve(), args.output.resolve())


if __name__ == '__main__':
    raise SystemExit(main())
