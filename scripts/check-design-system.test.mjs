import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { contrast, validate } from './check-design-system.mjs'
test('WCAG calculation and invalid color handling', () => {
  assert.equal(contrast('#000000', '#ffffff'), 21)
  assert.equal(contrast('#ffffff', '#ffffff'), 1)
  assert.throws(() => contrast('var(--ink)', '#ffffff'))
})
test('gate rejects disconnected CSS, missing tokens and low contrast', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'dq-design-contract-'))
  const files = {
    'package.json': JSON.stringify({ dependencies: { tailwindcss: '4' } }),
    'build.js': 'tailwindcss',
    'style.css': '@import "tailwindcss"; --ink: #222222; --paper: #ffffff;',
    'entry.js': 'import "style.css"',
    'DESIGN.md': ['Token sources', 'Components', 'Accessibility', 'Review and learning']
      .map((x) => '## ' + x)
      .join('\n'),
    'AGENTS.md': 'Read DESIGN.md',
    'Button.tsx': 'button',
  }
  for (const [p, s] of Object.entries(files)) fs.writeFileSync(path.join(root, p), s)
  const app = {
    name: 'fixture',
    package: 'package.json',
    buildConfig: 'build.js',
    styles: 'style.css',
    entry: 'entry.js',
    importMarker: 'style.css',
    design: 'DESIGN.md',
    instructions: 'AGENTS.md',
    designLink: 'DESIGN.md',
    tokenSource: 'style.css',
    requiredTokens: ['--ink', '--paper'],
    contrastPairs: [{ foreground: '--ink', background: '--paper', minimum: 4.5 }],
    componentSources: ['Button.tsx'],
  }
  try {
    assert.deepEqual(validate(root, { apps: [app] }).errors, [])
    assert.match(
      validate(root, { apps: [{ ...app, contrastPairs: [] }] }).errors.join(),
      /contrast coverage/
    )
    assert.match(validate(root, { apps: [] }).errors.join(), /At least one frontend/)
    fs.mkdirSync(path.join(root, 'extra'))
    fs.writeFileSync(
      path.join(root, 'extra/package.json'),
      JSON.stringify({ dependencies: { next: '16' } })
    )
    assert.match(
      validate(root, { apps: [app] }).errors.join(),
      /Frontend package inventoried: extra/
    )
    fs.rmSync(path.join(root, 'extra'), { recursive: true })
    fs.writeFileSync(path.join(root, 'entry.js'), '')
    assert.match(validate(root, { apps: [app] }).errors.join(), /stylesheet imported/)
    fs.writeFileSync(path.join(root, 'entry.js'), files['entry.js'])
    fs.writeFileSync(path.join(root, 'style.css'), '@import "tailwindcss"; --paper: #ffffff;')
    assert.match(validate(root, { apps: [app] }).errors.join(), /token --ink/)
    fs.writeFileSync(
      path.join(root, 'style.css'),
      '@import "tailwindcss"; --paper: #ffffff; --ink: #eeeeee;'
    )
    assert.match(validate(root, { apps: [app] }).errors.join(), /1.16:1/)
    fs.writeFileSync(path.join(root, 'style.css'), '@import "tailwindcss"; --paper: light-dark(#ffffff, #000000); --ink: light-dark(#222222, #eeeeee);')
    const modes = {...app, requiredSchemes:['light','dark'], contrastPairs:['light','dark'].map(scheme => ({foreground:'--ink',background:'--paper',minimum:4.5,scheme}))}
    assert.deepEqual(validate(root,{apps:[modes]}).errors,[])
    assert.match(validate(root,{apps:[{...modes,contrastPairs:modes.contrastPairs.slice(0,1)}]}).errors.join(),/coverage for dark/)
  } finally {
    fs.rmSync(root, { recursive: true, force: true })
  }
})
