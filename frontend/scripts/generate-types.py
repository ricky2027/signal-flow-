"""Generate TS data shapes from the checked-in actual backend OpenAPI schema."""
import json
from pathlib import Path
root=Path(__file__).resolve().parents[2]
schemas=json.loads((root/'backend/openapi.json').read_text())['components']['schemas']
def shape(s):
    if '$ref' in s:return s['$ref'].split('/')[-1]
    if 'anyOf' in s:return ' | '.join(shape(x) for x in s['anyOf'])
    if 'enum' in s:return ' | '.join(json.dumps(x) for x in s['enum'])
    t=s.get('type')
    if t=='null':return 'null'
    if t=='array':return f"Array<{shape(s['items'])}>"
    if t in ('integer','number'):return 'number'
    if t=='string':return 'string'
    if t=='boolean':return 'boolean'
    if t=='object':
        if 'properties' not in s:return 'Record<string, '+(shape(s['additionalProperties']) if isinstance(s.get('additionalProperties'),dict) else 'unknown')+'>'
        return '{ '+ '; '.join(f'{k}{"" if k in s.get("required",[]) else "?"}: {shape(v)}' for k,v in s['properties'].items())+' }'
    return 'unknown'
text='// Generated from backend/openapi.json. Run npm run types:generate after backend schema changes.\n'
text+='\n'.join(f'export type {name} = {shape(s)};' for name,s in schemas.items())+'\n'
(root/'frontend/src/lib/contracts.ts').write_text(text)
