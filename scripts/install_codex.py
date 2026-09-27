#!/usr/bin/env python3
"""Install only the Codex collector and refresh the existing Übersicht widget.

Usage: python3 scripts/install_codex.py --python /FDA/python --codex-bin /path/to/codex
No git/deployment actions; existing Claude launch agents are untouched.
"""
import argparse
import os
import plistlib
import shutil
import subprocess
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--python', required=True)
    ap.add_argument('--codex-bin', required=True)
    ap.add_argument('--prepare-only', action='store_true')
    args = ap.parse_args()
    repo = Path(__file__).resolve().parent.parent
    python = Path(args.python).absolute()
    codex = Path(args.codex_bin).absolute()
    for binary in (python, codex):
        if not os.access(binary, os.X_OK):
            raise SystemExit('Not executable: ' + str(binary))
    label = 'com.cc-usage.codex'
    data = repo / 'data'
    data.mkdir(exist_ok=True)
    spec = {
        'Label': label,
        'ProgramArguments': [str(python), str(repo / 'codex_usage.py'), '--collect', '--codex-bin', str(codex)],
        'EnvironmentVariables': {'PATH': str(codex.parent) + ':/usr/bin:/bin:/usr/sbin:/sbin'},
        'WorkingDirectory': str(repo), 'StartInterval': 60, 'RunAtLoad': True,
        'ProcessType': 'Background', 'StandardOutPath': str(data / 'codex_usage.log'),
        'StandardErrorPath': str(data / 'codex_usage.log'),
    }
    prepared = data / 'com.cc-usage.codex.plist'
    prepared.write_bytes(plistlib.dumps(spec))
    if args.prepare_only:
        print('Prepared ' + str(prepared))
        return
    target = Path.home() / 'Library/LaunchAgents' / (label + '.plist')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(prepared.read_bytes())
    service = 'gui/' + str(os.getuid())
    subprocess.run(['launchctl', 'bootout', service + '/' + label], capture_output=True)
    subprocess.run(['launchctl', 'bootstrap', service, str(target)], check=True)
    # Current installation is a symlink to the repo. For copy installations,
    # install just the changed main file and new module, preserving config.
    widgets = Path.home() / 'Library/Application Support/Übersicht/widgets'
    main_widget = widgets / 'cc-usage.jsx'
    if main_widget.is_symlink():
        if main_widget.resolve() != repo / 'ubersicht/cc-usage.jsx':
            raise SystemExit('Unexpected widget symlink; collector installed, widget refresh skipped')
        os.utime(main_widget, follow_symlinks=False)
    elif main_widget.exists():
        for name in ('cc-usage.jsx', 'cc-usage.codex.jsx', 'cc-usage.standby.jsx', 'cc-usage.styles.jsx'):
            shutil.copy2(repo / 'ubersicht' / name, widgets / name)
    print('Installed Codex collector: local refresh every minute, live quota every 15 minutes.')
    print('Widget source updated; refresh Übersicht if the new row has not appeared.')


if __name__ == '__main__':
    main()
