import subprocess
import sys
import unittest
from pathlib import Path

class ReadOnlyPackImportTest(unittest.TestCase):
    def test_fresh_process_import_and_failure_restore_state(self):
        root = Path(__file__).resolve().parents[1]
        code = r'''
import sys, tempfile, shutil, types
from pathlib import Path
from gearmath.tools.fea_ingest import repost_check, strict_repost_check
source=Path(sys.argv[1])
with tempfile.TemporaryDirectory() as td:
    pack=Path(td); shutil.copytree(source/'scripts',pack/'scripts',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    sentinel=types.ModuleType('cases'); sys.modules['cases']=sentinel
    oldpath=sys.path[:]; flag=sys.dont_write_bytecode
    result=repost_check([],{},pack)
    assert result['pass'] and sys.modules['cases'] is sentinel and sys.path==oldpath and sys.dont_write_bytecode==flag
    assert strict_repost_check([],{},pack)['pass'] and sys.path==oldpath and sys.modules['cases'] is sentinel and sys.dont_write_bytecode==flag
    assert not list(pack.rglob('*.pyc')) and not list(pack.rglob('__pycache__'))
    try:
        repost_check([{'id':'L2_test','case':'L2','status':'solved'}],{'runs/L2/L2_test.dat':b'x','runs/L2/L2_test.meta.json':b'bad'},pack)
        raise AssertionError('bad metadata accepted')
    except ValueError:
        pass
    assert sys.modules['cases'] is sentinel and sys.path==oldpath and sys.dont_write_bytecode==flag
    (pack/'scripts'/'cases.py').write_text('raise RuntimeError("import failure")',encoding='utf8')
    result=repost_check([],{},pack)
    assert result['pass'] is None and 'import failure' in result['error']
    assert sys.modules['cases'] is sentinel and sys.path==oldpath and sys.dont_write_bytecode==flag
    assert not list(pack.rglob('*.pyc')) and not list(pack.rglob('__pycache__'))
'''
        result = subprocess.run([sys.executable, '-c', code, str(root / 'data' / 'm37_fea_pack')], cwd=root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

if __name__ == '__main__': unittest.main()
