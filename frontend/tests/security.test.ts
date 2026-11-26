import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,mkdirSync,rmSync,readFileSync,symlinkSync} from 'node:fs';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import postcss from 'postcss';

test('CSS serialization cannot close an enclosing HTML style element',()=>{
    const css=postcss.parse('a { content: "</style><script>untrusted</script>" }').toString();
    assert.doesNotMatch(css,/<\/style/i);
});
test('untrusted source map paths cannot read outside the CSS directory or when from is omitted',async()=>{
    const directory=mkdtempSync(join(tmpdir(),'signalflow-postcss-regression-'));
    try {
        const inside=join(directory,'styles');mkdirSync(inside);
        const marker='TEST_ONLY_MAP_CONTENT_MUST_NOT_LEAK';
        const map=join(directory,'private.map');
        writeFileSync(map,JSON.stringify({version:3,sources:['private.txt'],sourcesContent:[marker],names:[],mappings:'AAAA'}));
        writeFileSync(join(inside,'input.css'),'a {}');
        symlinkSync(map,join(inside,'linked.map'));
        for(const sample of [
            {annotation:map,options:{}},
            {annotation:'../private.map',options:{from:join(inside,'input.css')}},
            {annotation:'linked.map',options:{from:join(inside,'input.css')}}
        ]){
            const result=await postcss([]).process(`a {} /*# sourceMappingURL=${sample.annotation} */`,sample.options);
            assert.equal(result.root.source?.input.map?.text,undefined);
            assert.ok(!JSON.stringify(result.map?.toJSON()||{}).includes(marker));
        }
    }finally{rmSync(directory,{recursive:true,force:true});}
});
test('no older PostCSS copy can remain hidden under Next or Tailwind in the lockfile',()=>{
    const lock=JSON.parse(readFileSync(new URL('../package-lock.json',import.meta.url),'utf8'));
    const versions=Object.entries(lock.packages).filter(([path])=>path.endsWith('/postcss')).map(([,pkg])=>(pkg as {version:string}).version);
    assert.ok(versions.length>0);
    assert.deepEqual([...new Set(versions)],['8.5.33']);
});
