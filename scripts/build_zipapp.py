"""Build a stdlib-only executable archive without installing build dependencies."""
from pathlib import Path
import tempfile,shutil,zipapp,hashlib,json
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as temp:
    stage=Path(temp);(stage/'crg').mkdir()
    for source in sorted((root/'crg').glob('*.py')):shutil.copyfile(source,stage/'crg'/source.name)
    (stage/'__main__.py').write_text('from crg.cli import main\nraise SystemExit(main())\n')
    (root/'dist').mkdir(exist_ok=True)
    zipapp.create_archive(stage,root/'dist/crg.pyz',interpreter='/usr/bin/env python3.13',compressed=True)
artifact=root/'dist/crg.pyz'
(root/'dist/MANIFEST.json').write_text(json.dumps({'artifact':'crg.pyz','sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),
    'python':'>=3.11; inspected machine uses python3.13','schemas':'external version-bound evidence; pass --schema to recovery'},indent=2)+'\n')
print(str(artifact))
