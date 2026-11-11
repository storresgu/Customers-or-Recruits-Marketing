from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import json,sys
raw=Path(sys.argv[1]);out=Path(sys.argv[2])
for sid in ['retail03_repeat30','retail03_repeat80','retail12_repeat30','retail12_repeat80']:
 pairs=sorted((raw/'pairs').glob('*__'+sid+'__r*'))
 target=out/f'Article_25_M4_Trazas_{sid}_v0.1.zip'
 if target.exists(): continue
 if len(pairs)!=10 or any(not (p/'manifest.json').exists() or json.loads((p/'manifest.json').read_text()).get('status')!='completed' for p in pairs): continue
 with ZipFile(target,'x',ZIP_DEFLATED,compresslevel=6) as z:
  for pair in pairs:
   for file in sorted(pair.rglob('*')):
    if file.is_file(): z.write(file,Path('Article_25_M4/pilot_v01')/file.relative_to(raw))
 with ZipFile(target) as z: assert z.testzip() is None
 print(target.name,target.stat().st_size,flush=True)
