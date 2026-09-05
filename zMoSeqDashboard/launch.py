"""lbs MoSeq Syllable Explorer v0.1. Python 3.8+, standard library only.

Launch: python launch.py
Refresh the offline catalog without starting the server: python launch.py --catalog-only
"""
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import argparse
import json
import webbrowser
import os
import tempfile
import shutil
import threading
import subprocess

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'data_MoSeq_raw'
MAX_BYTES = 20 * 1024 * 1024
EXTENSIONS = {'.txt', '.tsv', '.csv'}


def data_files():
    if not RAW.is_dir():
        return []
    return sorted((p for p in RAW.iterdir()
                   if p.is_file() and not p.is_symlink() and p.suffix.lower() in EXTENSIONS),
                  key=lambda p: p.name.lower())


def make_catalog(report=False):
    entries = []
    for path in data_files():
        if path.stat().st_size > MAX_BYTES:
            print('Offline catalog skipped oversized file:', path.name)
            continue
        try:
            entries.append({'name': path.name, 'text': path.read_text(encoding='utf-8-sig')})
        except UnicodeError:
            print('Offline catalog skipped non-UTF-8 file:', path.name)
    (ROOT / 'catalog.js').write_text(
        '// Generated offline snapshot. Source TXT/TSV/CSV files are unchanged.\n'
        'window.MOSEQ_CATALOG = ' + json.dumps(entries, ensure_ascii=True) + ';\n',
        encoding='utf-8')
    if report:
        print('Updated offline catalog:', len(entries), 'datasets')
        for entry in entries:
            print('  - ' + entry['name'])
        if not entries:
            print('  Add TXT, TSV or CSV files to data_MoSeq_raw, then refresh the dashboard.')
        print(flush=True)
    return len(entries)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        super().end_headers()

    def reply(self, data, content_type='application/json; charset=utf-8'):
        body = data.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/session':
            name = parse_qs(parsed.query).get('name', [''])[0]
            if name not in {p.name for p in data_files()}:
                self.send_error(404)
                return
            path = RAW / (Path(name).stem + '_session.json')
            if not path.is_file() or path.is_symlink():
                self.send_error(404)
                return
            self.reply(path.read_text(encoding='utf-8'))
            return
        if parsed.path == '/api/files':
            self.reply(json.dumps({'files': [p.name for p in data_files()]}))
            return
        if parsed.path == '/api/data':
            name = parse_qs(parsed.query).get('name', [''])[0]
            available = {p.name: p for p in data_files()}
            path = available.get(name)
            if path is None:
                self.send_error(404, 'File is not in the raw-data folder')
                return
            if path.stat().st_size > MAX_BYTES:
                self.send_error(413, 'File exceeds 20 MB')
                return
            try:
                self.reply(path.read_text(encoding='utf-8-sig'), 'text/plain; charset=utf-8')
            except UnicodeError:
                self.send_error(400, 'Please use UTF-8 text files')
            return
        # Restrict static serving to the app's own folder, including symlink resolution.
        target = Path(self.translate_path(parsed.path)).resolve()
        try:
            target.relative_to(ROOT)
        except ValueError:
            self.send_error(403)
            return
        super().do_GET()

    def list_directory(self, path):
        self.send_error(403, 'Directory listings disabled')
        return None

    def do_POST(self):
        # Only this local app may write its narrowly named session sidecar.
        if self.path not in ('/api/session', '/api/shutdown'):
            self.send_error(404)
            return
        expected = '127.0.0.1:' + str(self.server.server_address[1])
        if self.headers.get('Host') != expected or self.headers.get('Origin') not in (None, 'http://' + expected):
            self.send_error(403, 'This action must come from this local dashboard')
            return
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            self.send_error(415)
            return
        if self.path == '/api/shutdown':
            self.reply(json.dumps({'stopped': True}))
            self.wfile.flush()
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        temporary = None
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 25 * 1024 * 1024:
                self.send_error(413)
                return
            payload = json.loads(self.rfile.read(length).decode('utf-8'))
            dataset = payload.get('dataset', {})
            name = dataset.get('name')
            source = {p.name: p for p in data_files()}.get(name)
            if source is None or payload.get('app') != 'MoSeq Dashboard' or payload.get('version') != '0.1' or not isinstance(payload.get('settings'), dict):
                raise ValueError('Unsupported session or source is not in data_MoSeq_raw')
            normalize = lambda text: text.lstrip('\ufeff').replace('\r\n', '\n').replace('\r', '\n')
            if normalize(dataset.get('text', '')) != normalize(source.read_text(encoding='utf-8-sig')):
                self.send_error(409, 'Raw file changed: reload it before saving this session')
                return
            destination = RAW / (source.stem + '_session.json')
            backup = RAW / (source.stem + '_session.previous.json')
            if destination.is_symlink() or backup.is_symlink():
                raise ValueError('Session destination must not be a symbolic link')
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=RAW, suffix='.tmp', delete=False) as output:
                temporary = output.name
                json.dump(payload, output, ensure_ascii=True, indent=2)
            if destination.exists():
                shutil.copyfile(destination, backup)
            os.replace(temporary, destination)
            temporary = None
            self.reply(json.dumps({'saved': destination.name}))
        except (ValueError, TypeError, AttributeError, OSError) as error:
            self.send_error(400, str(error))
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)


def find_chrome():
    for command in ('chrome', 'chrome.exe', 'google-chrome', 'chromium'):
        executable = shutil.which(command)
        if executable:
            return executable
    for variable in ('LOCALAPPDATA', 'PROGRAMFILES', 'PROGRAMFILES(X86)'):
        base = os.environ.get(variable)
        if base:
            executable = Path(base) / 'Google' / 'Chrome' / 'Application' / 'chrome.exe'
            if executable.is_file():
                return str(executable)
    return None


def open_dashboard(url, browser):
    if browser == 'chrome':
        executable = find_chrome()
        if executable:
            try:
                subprocess.Popen([executable, url], stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except OSError:
                print('Chrome could not start; using your default browser.', flush=True)
        else:
            print('Chrome was not found; using your default browser.', flush=True)
    webbrowser.open(url)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog-only', action='store_true')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--browser', choices=('default', 'chrome'), default='default')
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args()
    print('\nlbs MoSeq Syllable Explorer | v0.1')
    print('Explore mouse behavioral syllable usage: treatment comparisons, combined syllables and heatmaps.\n', flush=True)
    make_catalog(report=True)
    if args.catalog_only:
        return
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    url = 'http://127.0.0.1:' + str(server.server_address[1]) + '/index.html'
    print('Data and saved sessions: ' + str(RAW))
    print('Open dashboard: ' + url)
    print('Keep this window open while working. Save session keeps your current work.')
    print('When finished, use Close dashboard in the app (or Ctrl+C here).\n', flush=True)
    if not args.no_browser:
        open_dashboard(url, args.browser)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print('\nDashboard server stopped.')
        print('Your raw files and saved sessions remain in: ' + str(RAW))
        print('Closing does not automatically save unsaved changes.')
        print('You can close the browser tab. Run Start Dashboard.bat to reopen.', flush=True)


if __name__ == '__main__':
    main()
