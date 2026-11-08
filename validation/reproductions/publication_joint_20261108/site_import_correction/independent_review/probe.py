import importlib.util,json,sys
from pathlib import Path
root=Path(sys.argv[1]); source=Path(sys.argv[2]);sys.path[0]=str(root/'website')
assert str(root) not in sys.path, sys.path
exec(compile(source.read_bytes(),str(root/'website/build_site.py'),'exec'),{'__name__':'source_import_probe','__file__':str(root/'website/build_site.py')})
spec=importlib.util.spec_from_file_location('disposition_import_probe',root/'scripts/render_joint_disposition_results.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
print(json.dumps({'formatter':str(spec.origin),'builder':str(module.builder.__file__),'repo_on_sys_path':str(root) in sys.path,'build_or_validation_invoked':False}))
