#!/usr/bin/env python3
"""Build the complete modified Wine dsound DLL from pinned source. Never runs Wine."""
# SPDX-License-Identifier: LGPL-2.1-or-later
from pathlib import Path
import argparse,hashlib,json,os,shutil,struct,subprocess,tarfile
HERE=Path(__file__).resolve().parent

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def run(args,cwd,env,log):
    result=subprocess.run(args,cwd=cwd,env=env,capture_output=True,text=True)
    log.write_text(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError('Build failed; see '+str(log))
def strip_metadata(data):
    """Discard unmapped COFF symbols and Wine's empty CodeView placeholder only."""
    data=bytearray(data);pe=struct.unpack_from('<I',data,60)[0];opt=pe+24
    n=struct.unpack_from('<H',data,pe+6)[0];optsize=struct.unpack_from('<H',data,pe+20)[0]
    sections=[struct.unpack_from('<8sIIII',data,opt+optsize+40*i)for i in range(n)]
    def offset(rva,size):
        for name,vs,va,rs,raw in sections:
            if va<=rva and rva-va+size<=rs:return raw+rva-va
        raise ValueError('Metadata is outside mapped file sections')
    debug_rva,debug_size=struct.unpack_from('<II',data,opt+96+6*8)
    if debug_size:
        assert debug_size==28,'Unexpected debug metadata'
        at=offset(debug_rva,debug_size);record=struct.unpack_from('<IIHHIIII',data,at)
        assert record[4]==2 and record[5]==25,'Unexpected debug type'
        payload=offset(record[6],record[5]);assert payload==record[7]
        assert data[payload:payload+25]==bytes(25),'Nonempty debug payload'
        data[at:at+28]=bytes(28);struct.pack_into('<II',data,opt+96+6*8,0,0)
    symbol_at,symbol_count=struct.unpack_from('<II',data,pe+12)
    end=max(raw+size for _,_,_,size,raw in sections)
    assert struct.unpack_from('<II',data,opt+96+4*8)==(0,0),'Do not strip signed files'
    if symbol_at:
        assert symbol_at==end and symbol_count>0,'Unexpected COFF layout'
        strings=symbol_at+symbol_count*18
        string_size=struct.unpack_from('<I',data,strings)[0]
        assert string_size>=4 and strings+string_size<=len(data)
        struct.pack_into('<II',data,pe+12,0,0);data=data[:end]
    assert len(data)==end,'Unexpected trailing payload'
    return bytes(data)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wine-archive',type=Path,default=HERE/'upstream/wine-11.0.tar.gz')
    parser.add_argument('--work-dir',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--bison',type=Path,required=True)
    parser.add_argument('--bison-data',type=Path)
    parser.add_argument('--lld-dir',type=Path,required=True)
    parser.add_argument('--jobs',type=int,default=8)
    args=parser.parse_args();manifest=json.loads((HERE/'source-manifest.json').read_text())
    archive=args.wine_archive.resolve();assert digest(archive)==manifest['upstream']['sha256'],'Wrong Wine source archive'
    work=args.work_dir.resolve();work.mkdir(parents=True,exist_ok=False)
    source=work/manifest['upstream']['root'];build=work/'build';build.mkdir();toolchain=work/'toolchain';toolchain.mkdir()
    with tarfile.open(archive)as stream:
        for item in stream.getmembers():
            p=Path(item.name)
            assert p.parts and p.parts[0]==source.name and not p.is_absolute() and '..' not in p.parts
            if item.issym()or item.islnk():assert not Path(item.linkname).is_absolute() and '..' not in Path(item.linkname).parts
        stream.extractall(work)
    for name,item in manifest['overlay'].items():
        p=HERE/'overlay'/name;assert digest(p)==item['sha256'],name
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    (toolchain/'bison').symlink_to(args.bison.resolve())
    for name in ('ld.lld','lld-link'):
        target=args.lld_dir.resolve()/name;assert target.is_file(),str(target);(toolchain/name).symlink_to(target)
    env=os.environ.copy();env['PATH']=str(toolchain)+os.pathsep+env['PATH'];env['SOURCE_DATE_EPOCH']='0';env['LC_ALL']='C'
    if args.bison_data:env['BISON_PKGDATADIR']=str(args.bison_data.resolve())
    configure=['../'+source.name+'/configure','--enable-archs=i386','--without-x','--without-freetype','--without-vulkan','--without-gnutls','CC=clang -arch x86_64','CXX=clang++ -arch x86_64','--host=x86_64-apple-darwin','BISON=../toolchain/bison','ac_cv_mabi_ms=yes']
    run(configure,build,env,work/'configure.log')
    makefile=build/'Makefile';text=makefile.read_text()
    assert '-Wl,--wine-builtin -shared' in text
    text=text.replace('-Wl,--wine-builtin -shared','-shared')
    text=text.replace('tools/winebuild/winebuild -w --implib','tools/winebuild/winebuild --without-dlltool --safeseh -w --implib')
    makefile.write_text(text)
    command=['make','-j'+str(args.jobs),'i386_CFLAGS=-O2 -g0','i386_LDFLAGS= --no-default-config -fms-hotpatch -Wl,/debug:none,/timestamp:0','dlls/dsound/i386-windows/dsound.dll']
    run(command,build,env,work/'build.log')
    dll=build/'dlls/dsound/i386-windows/dsound.dll';data=strip_metadata(dll.read_bytes());pe=struct.unpack_from('<I',data,60)[0]
    assert data[pe:pe+4]==b'PE\0\0' and struct.unpack_from('<H',data,pe+4)[0]==0x14c
    assert struct.unpack_from('<I',data,pe+8)[0]==0,'Non-deterministic PE timestamp'
    opt=pe+24;assert struct.unpack_from('<II',data,opt+96+6*8)==(0,0),'Debug directory retained'
    n=struct.unpack_from('<H',data,pe+6)[0];optsize=struct.unpack_from('<H',data,pe+20)[0]
    sections=[data[opt+optsize+40*i:opt+optsize+40*i+8].rstrip(b'\0')for i in range(n)]
    assert not any(x.startswith(b'.debug')for x in sections),'Debug sections retained'
    assert b'Wine builtin DLL'not in data[:128]
    for private in ('/Users/','/home/','stage14','stage15','DAO_Test_','ChatGPT/Dragon Age','dsound-trace'):
        assert private.encode()not in data and private.encode('utf-16le')not in data,private
    output=args.output.resolve();output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(data)
    provenance={'schema':1,'component':'origins-audio','version':'1.0.0-beta.1','dll':{'sha256':digest(output),'bytes':len(data)},'source_manifest_sha256':digest(HERE/'source-manifest.json'),'build_recipe_sha256':digest(Path(__file__).resolve()),'wine_archive_sha256':digest(archive),'configure_arguments':configure,'make_arguments':command,'debug_data':False,'pe_timestamp':0,'live_actions':False,'tools':{}}
    for name,cmd in [('clang',['clang','--version']),('lld',['lld-link','--version']),('bison',['../toolchain/bison','--version']),('flex',['flex','--version'])]:
        provenance['tools'][name]=subprocess.check_output(cmd,cwd=build,env=env,text=True).splitlines()[0]
    (work/'build-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n');print(json.dumps(provenance,indent=2))
if __name__=='__main__':main()
