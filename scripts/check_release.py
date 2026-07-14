from pathlib import Path
import subprocess,sys
root=Path(__file__).resolve().parents[1]
required=['README.md','AGENTS.md','LICENSE','SECURITY.md','CONTRIBUTING.md','CODE_OF_CONDUCT.md','docs/ROADMAP_72_HOURS.md','docs/ACCEPTANCE_CRITERIA.md','docs/EVIDENCE_POLICY.md','docs/THREAT_MODEL.md','Dockerfile','docker-compose.yml','app/server.py','tests/test_api.py','db/schema.sql']
missing=[x for x in required if not (root/x).exists()]
if missing:print('Missing:',*missing);sys.exit(1)
tracked=subprocess.run(['git','ls-files','-z'],cwd=root,capture_output=True,check=True).stdout.split(b'\0')
markers=[b's' + b'k-',b'BEGIN' + b' PRIVATE KEY']
for raw in tracked:
 if not raw:continue
 p=root/raw.decode()
 if p.name in {'.env.example','check_release.py'}:continue
 data=p.read_bytes()
 if any(marker in data for marker in markers):print('Potential secret:',p);sys.exit(1)
compile_result=subprocess.run([sys.executable,'-m','compileall','-q','app','scripts','tests'],cwd=root)
if compile_result.returncode:sys.exit(compile_result.returncode)
tests=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(root/'tests'),'-v'],cwd=root)
if tests.returncode:sys.exit(tests.returncode)
ui=subprocess.run(['node','scripts/ui_acceptance.mjs'],cwd=root)
sys.exit(ui.returncode)
