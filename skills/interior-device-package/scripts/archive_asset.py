#!/usr/bin/env python3
"""Write a deterministic source ZIP after rechecking its sealed inventory."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile

def archive(root, output, entry_digest):
    root=Path(root).resolve();output=Path(output)
    raw=(root/'device-asset.json').read_bytes()
    digest=lambda b:'sha256:'+hashlib.sha256(b).hexdigest()
    if digest(raw)!=entry_digest:raise ValueError('Source entry changed during build')
    data={'device-asset.json':raw}
    for row in json.loads(raw)['files']:
        name=row['path'];parts=name.split('/')
        if '\\' in name or any(p in ('','.','..')for p in parts):raise ValueError('Unsafe path')
        file=root/name
        if any((root.joinpath(*parts[:n])).is_symlink()for n in range(1,len(parts)+1)):raise ValueError('Symlink')
        content=file.read_bytes()
        if len(content)!=row['byteSize']or digest(content)!=row['digest']:raise ValueError('Source file changed: '+name)
        data[name]=content
    with output.open('xb')as stream:
        with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED)as z:
            for name,content in sorted(data.items()):
                info=zipfile.ZipInfo(name,(1980,1,1,0,0,0));info.create_system=3
                info.external_attr=0o100644<<16
                z.writestr(info,content)

if __name__=='__main__':archive(*sys.argv[1:])
