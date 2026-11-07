"""Linux research-child supervisor with sampled resource gates and owned cleanup.

Run as a dedicated process: python -B scripts/supervise_research.py SPEC.json.
The scientific command runs in a new session. Linux child-subreaper ownership
retains orphan descendants, including those which create another session.
RSS is sampled, not an OS memory reservation or an exact unsampled peak.
"""
import argparse
import ctypes
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback
import psutil


class AdmissionError(ValueError):
    pass


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate(spec):
    command = spec.get('command')
    if not isinstance(command, list) or not command or any(
            not isinstance(arg, str) or not arg or '\0' in arg for arg in command):
        raise AdmissionError('command must be a nonempty argument-string array')
    if not isinstance(spec.get('cwd'), str) or not Path(spec['cwd']).is_dir():
        raise AdmissionError('cwd must be an existing directory')
    for name, default, positive in (('wall_cap_seconds', None, True),
                                    ('rss_cap_bytes', None, True),
                                    ('host_headroom_bytes', 0, False),
                                    ('sample_seconds', .2, True),
                                    ('cleanup_grace_seconds', 5., True)):
        value = spec.get(name, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise AdmissionError(name + ' must be finite numeric')
        if value < 0 or (positive and value == 0):
            raise AdmissionError(name + ' has an invalid sign')
    if spec.get('sample_seconds', .2) > min(5., spec['wall_cap_seconds']):
        raise AdmissionError('sample_seconds must not exceed five seconds or the wall cap')
    if spec.get('cleanup_grace_seconds', 5.) > 10:
        raise AdmissionError('cleanup grace must not exceed ten seconds per escalation tier')
    environment = spec.get('env', {})
    if not isinstance(environment, dict) or any(
            not isinstance(k, str) or not k or '=' in k or '\0' in k or
            not isinstance(v, str) or '\0' in v for k, v in environment.items()):
        raise AdmissionError('env must map valid names to string values')


class LinuxOwnership:
    """Ownership belongs to this dedicated supervisor, never an arbitrary PID."""
    def __init__(self):
        if sys.platform != 'linux' or not hasattr(os, 'waitid') or not hasattr(os, 'WNOWAIT'):
            raise AdmissionError('production containment requires Linux waitid/subreaper support')
        self.self_process = psutil.Process()
        if self.self_process.children(recursive=True):
            raise AdmissionError('supervisor must be a dedicated process without pre-existing children')
        self.libc = ctypes.CDLL(None, use_errno=True)
        previous = ctypes.c_int()
        if self.libc.prctl(37, ctypes.byref(previous), 0, 0, 0) != 0:  # PR_GET_CHILD_SUBREAPER
            raise OSError(ctypes.get_errno(), 'PR_GET_CHILD_SUBREAPER failed')
        self.previous = previous.value
        if self.libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
            raise OSError(ctypes.get_errno(), 'PR_SET_CHILD_SUBREAPER failed')
        self.root = None
        self.known = {}

    def attach(self, process):
        self.root = process
        if process.pid == os.getpgrp():
            raise RuntimeError('refusing supervisor process-group ownership')

    def remember(self, process):
        created = process.create_time()
        old = self.known.get(process.pid)
        if old is not None and old != created:
            raise RuntimeError('owned PID was reused before lifetime completion')
        self.known[process.pid] = created

    def members(self):
        # The subreaper adopts orphans after a parent exit, even if they call
        # setsid(). No other children are created by this dedicated supervisor.
        candidates = {p.pid: p for p in self.self_process.children(recursive=True)}
        if self.root is not None:
            # The root is deliberately not reaped until cleanup is complete,
            # reserving its PID and therefore the owned session/group identity.
            for pid in psutil.pids():
                try:
                    if os.getpgid(pid) == self.root.pid:
                        candidates[pid] = psutil.Process(pid)
                except (ProcessLookupError, psutil.NoSuchProcess):
                    continue
        live = []
        for process in candidates.values():
            try:
                self.remember(process)
                if process.is_running() and process.status() != psutil.STATUS_ZOMBIE:
                    live.append(process)
            except psutil.NoSuchProcess:
                continue
        return live

    def parent_exited(self):
        # Unlike Popen.poll(), WNOWAIT does not release the group leader PID.
        event = os.waitid(os.P_PID, self.root.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        return event is not None and event.si_pid == self.root.pid

    def send(self, sig):
        errors = []
        if self.root is not None:
            if self.root.pid == os.getpgrp():
                raise RuntimeError('refusing to signal supervisor group')
            try:
                os.killpg(self.root.pid, sig)
            except ProcessLookupError:
                pass
            except OSError as exc:
                errors.append(type(exc).__name__ + ': ' + str(exc))
        try:
            members = self.members()
        except Exception as exc:
            errors.append(type(exc).__name__ + ': ' + str(exc))
            members = []
            # Preserve safe cleanup of already identified escaped descendants
            # even when a fresh enumeration fails. Never signal a reused PID.
            for pid, created in self.known.items():
                try:
                    process = psutil.Process(pid)
                    if process.create_time() == created:
                        members.append(process)
                except psutil.NoSuchProcess:
                    continue
                except Exception as fallback:
                    errors.append(type(fallback).__name__ + ': ' + str(fallback))
        for process in members:
            try:
                if process.create_time() != self.known[process.pid]:
                    raise RuntimeError('refusing reused PID')
                process.send_signal(sig)
            except psutil.NoSuchProcess:
                pass
            except Exception as exc:
                errors.append(type(exc).__name__ + ': ' + str(exc))
        return errors

    def reap_orphans(self):
        for pid in list(self.known):
            if self.root is not None and pid == self.root.pid:
                continue
            try:
                os.waitpid(pid, os.WNOHANG)
            except (ChildProcessError, ProcessLookupError):
                pass

    def cleanup(self, grace):
        errors = []
        for sig in (signal.SIGTERM, signal.SIGKILL):
            errors.extend(self.send(sig))
            until = time.monotonic() + grace
            while time.monotonic() < until:
                try:
                    self.reap_orphans()
                    live = self.members()
                    if not live:
                        break
                    # Catch descendants born while the parent handled TERM.
                    if sig == signal.SIGKILL:
                        errors.extend(self.send(sig))
                except Exception as exc:
                    errors.append(type(exc).__name__ + ': ' + str(exc))
                    break
                time.sleep(.02)
            try:
                if not self.members():
                    break
            except Exception as exc:
                errors.append(type(exc).__name__ + ': ' + str(exc))
        try:
            self.reap_orphans()
            survivors = [p.pid for p in self.members()]
        except Exception as exc:
            errors.append(type(exc).__name__ + ': ' + str(exc))
            survivors = None
        return errors, survivors

    def restore(self):
        if self.libc.prctl(36, self.previous, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), 'restore child-subreaper state failed')


def run(spec, raw, output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / 'spec.json').write_bytes(raw)
    log_path = output / 'execution.log'
    log_path.touch()
    started = time.monotonic()
    result = dict(schema='linux_research_supervisor_v1', status='failed', started_utc=stamp(),
                  platform=sys.platform, returncode=None, stop_reason=None, launched=False,
                  samples=[], cleanup_errors=[], survivors_after_cleanup=None,
                  spec_sha256=hashlib.sha256(raw).hexdigest(), supervisor_sha256=sha(__file__),
                  containment='Dedicated Linux session/group plus child-subreaper; parent PID retained until cleanup',
                  memory_scope='Sampled process-tree RSS with enforcement after observation, not a hard OS memory reservation or exact unsampled peak')
    owner = process = None
    old_handlers = {}
    cleaning = False
    def interrupted(signum, frame):
        if not cleaning:
            raise InterruptedError('supervisor received signal ' + str(signum))
    try:
        validate(spec)
        owner = LinuxOwnership()
        for sig in (signal.SIGINT, signal.SIGTERM):
            old_handlers[sig] = signal.signal(sig, interrupted)
        env = os.environ.copy()
        env.update(spec.get('env', {}))
        with log_path.open('wb') as log:
            started = time.monotonic()
            deadline = started + spec['wall_cap_seconds']
            process = subprocess.Popen(spec['command'], cwd=spec['cwd'], env=env,
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            result['launched'] = True
            owner.attach(process)
            last_notice = 0.
            while True:
                terminal = owner.parent_exited()
                live = owner.members()
                rss = 0
                cpu = 0.
                for member in live:
                    try:
                        rss += member.memory_info().rss
                        used = member.cpu_times()
                        cpu += used.user + used.system
                    except psutil.NoSuchProcess:
                        continue
                elapsed = time.monotonic() - started
                row = dict(wall_seconds=elapsed, rss_bytes=rss,
                           host_available_bytes=psutil.virtual_memory().available,
                           live_processes=len(live), cpu_seconds_currently_observed=cpu)
                result['samples'].append(row)
                reason = None
                if elapsed >= spec['wall_cap_seconds']:
                    reason = 'wall_cap'
                elif rss > spec['rss_cap_bytes']:
                    reason = 'sampled_process_tree_rss_cap'
                elif row['host_available_bytes'] < spec.get('host_headroom_bytes', 0):
                    reason = 'host_memory_headroom'
                elif terminal and any(p.pid != process.pid for p in live):
                    reason = 'live_descendants_after_parent'
                if terminal or reason:
                    result['stop_reason'] = reason
                    result['execution_wall_seconds'] = elapsed
                    break
                if elapsed - last_notice >= 30:
                    print(json.dumps(dict(running=True, **row)), flush=True)
                    last_notice = elapsed
                time.sleep(min(spec.get('sample_seconds', .2), max(0., deadline - time.monotonic())))
    except BaseException as exc:
        result['stop_reason'] = 'admission_error' if isinstance(exc, AdmissionError) else 'supervisor_error'
        result['error'] = type(exc).__name__ + ': ' + str(exc)
        result['traceback'] = traceback.format_exc()
    finally:
        cleaning = True
        if owner is not None:
            # Cleanup remains bounded even if the original error was a bad spec.
            grace = spec.get('cleanup_grace_seconds', 5.)
            try:
                errors, survivors = owner.cleanup(grace)
                result['cleanup_errors'].extend(errors)
                result['survivors_after_cleanup'] = survivors
            except BaseException as exc:
                result['cleanup_errors'].append(type(exc).__name__ + ': ' + str(exc))
            if process is not None:
                try:
                    result['returncode'] = process.wait(timeout=grace)
                except BaseException as exc:
                    result['cleanup_errors'].append(type(exc).__name__ + ': ' + str(exc))
            result['known_processes'] = [dict(pid=pid, create_time=created) for pid, created in owner.known.items()]
            try:
                owner.reap_orphans()
                owner.restore()
            except BaseException as exc:
                result['cleanup_errors'].append(type(exc).__name__ + ': ' + str(exc))
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)
        samples = result.pop('samples')
        result['sample_count'] = len(samples)
        result['sample_interval_seconds'] = spec.get('sample_seconds', .2)
        result['sampled_peak_tree_rss_bytes'] = max((s['rss_bytes'] for s in samples), default=None)
        result['minimum_sampled_host_available_bytes'] = min((s['host_available_bytes'] for s in samples), default=None)
        result['wall_seconds_including_cleanup'] = time.monotonic() - started
        result['finished_utc'] = stamp()
        result['execution_log_sha256'] = sha(log_path)
        result['status'] = 'passed' if (result['launched'] and result['returncode'] == 0
            and result['stop_reason'] is None and samples and not result['cleanup_errors']
            and result['survivors_after_cleanup'] == []
            and result.get('execution_wall_seconds', math.inf) < spec['wall_cap_seconds']) else 'failed'
        (output / 'resource_samples.json').write_text(json.dumps(samples, indent=2) + '\n', encoding='utf-8')
        (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result), flush=True)
    return 0 if result['status'] == 'passed' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('spec', type=Path)
    args = parser.parse_args()
    raw = args.spec.read_bytes()
    spec = json.loads(raw)
    if not isinstance(spec, dict) or not isinstance(spec.get('output'), str):
        parser.error('spec must be an object containing an output directory string')
    return run(spec, raw, spec['output'])


if __name__ == '__main__':
    raise SystemExit(main())
