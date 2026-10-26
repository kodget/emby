"""Small, disposable renderer. Deliberately does not initialize Django or Celery."""
import json
import os
from pathlib import Path
import signal
import sys
import threading


def write_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value), encoding='utf-8')
    temporary.replace(path)


def main():
    from .document_rendering import render_document, rendering_failure
    source, kind, directory, budget = sys.argv[1:]
    output = Path(directory)
    if os.name == 'posix':
        # EOF also arrives if Celery is killed. Kill this whole converter group,
        # including LibreOffice, rather than leaving an orphan consuming memory.
        def parent_watch():
            # Raw fd read avoids a daemon holding Python's buffered-stdin lock
            # while the successful renderer is shutting its interpreter down.
            os.read(sys.stdin.fileno(), 1)
            os.killpg(os.getpid(), signal.SIGKILL)
        threading.Thread(target=parent_watch, daemon=True).start()
    def progress(phase, completed, total):
        write_json(output / 'progress.json', {'phase': phase, 'completed': completed, 'total': total})
    try:
        progress('rendering' if kind == 'pdf' else 'converting', 0, 0)
        result = render_document(source, kind, output, ocr=False, progress=progress, memory_mb=int(budget))
        write_json(output / 'result.json', {'success': True, 'result': result})
    except BaseException as exc:
        code = 'render_memory' if isinstance(exc, MemoryError) or 'malloc' in str(exc).lower() else rendering_failure(exc)[0]
        write_json(output / 'result.json', {'success': False, 'error_code': code})
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
