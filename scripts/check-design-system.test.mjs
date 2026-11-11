import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
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
test('gate reports each remaining refusal', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'dq-design-refusals-'))
  const headings = ['Token sources', 'Components', 'Accessibility', 'Review and learning']
  const base = {
    'package.json': JSON.stringify({
      dependencies: { tailwindcss: '4' },
      scripts: { 'design:check': 'node check.mjs' },
    }),
    'build.js': 'tailwindcss',
    'style.css': '@import "tailwindcss"; --ink: #222222; --paper: #ffffff;',
    'entry.js': 'import "style.css"',
    'DESIGN.md': headings.map((x) => '## ' + x).join('\n'),
    'AGENTS.md': 'Read DESIGN.md',
    'Button.tsx': 'button',
    'check.mjs': 'x',
  }
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
  const reset = () => {
    for (const [p, s] of Object.entries(base)) fs.writeFileSync(path.join(root, p), s)
  }
  const errors = (a = app) => validate(root, { apps: [a] }).errors.join()
  try {
    reset()
    assert.deepEqual(validate(root, { apps: [app] }).errors, [])
    fs.writeFileSync(path.join(root, 'package.json'), JSON.stringify({ scripts: {} }))
    assert.match(errors(), /Tailwind dependency/)
    reset()
    fs.writeFileSync(path.join(root, 'build.js'), 'nothing')
    assert.match(errors(), /Tailwind build plugin/)
    reset()
    fs.writeFileSync(path.join(root, 'style.css'), '--ink: #222222; --paper: #ffffff;')
    assert.match(errors(), /Tailwind stylesheet import/)
    for (const heading of headings) {
      reset()
      fs.writeFileSync(
        path.join(root, 'DESIGN.md'),
        headings.filter((x) => x !== heading).map((x) => '## ' + x).join('\n')
      )
      assert.match(errors(), new RegExp('DESIGN.md ' + heading))
    }
    reset()
    fs.writeFileSync(path.join(root, 'AGENTS.md'), 'nothing here')
    assert.match(errors(), /discoverable design instructions/)
    reset()
    assert.deepEqual(
      validate(root, {
        apps: [
          {
            ...app,
            contrastPairs: [],
            externalContrast: { script: 'check.mjs', command: 'node check.mjs' },
          },
        ],
      }).errors,
      []
    )
    assert.match(
      errors({
        ...app,
        contrastPairs: [],
        externalContrast: { script: 'check.mjs', command: 'node other.mjs' },
      }),
      /existing contrast gate is mandatory/
    )
    fs.writeFileSync(
      path.join(root, 'style.css'),
      '@import "tailwindcss"; --paper: light-dark(#ffffff, #000000); --ink: light-dark(#222222, #eeeeee);'
    )
    assert.match(errors(), /Scheme required for --ink/)
    reset()
    assert.match(errors({ ...app, componentSources: [] }), /existing reusable components/)
  } finally {
    fs.rmSync(root, { recursive: true, force: true })
  }
})
test('build check refuses a stale compiled design.css', () => {
  const repo = process.cwd()
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'dq-design-stale-'))
  try {
    fs.mkdirSync(path.join(root, 'scripts'))
    fs.copyFileSync(
      path.join(repo, 'scripts/design.source.css'),
      path.join(root, 'scripts/design.source.css')
    )
    fs.writeFileSync(path.join(root, 'scripts/design.css'), '/* stale */')
    fs.symlinkSync(path.join(repo, 'node_modules'), path.join(root, 'node_modules'))
    const result = spawnSync(process.execPath, [path.join(repo, 'scripts/check-design-build.mjs')], {
      cwd: root,
      encoding: 'utf8',
    })
    assert.notEqual(result.status, 0)
    assert.match(result.stderr, /Compiled design\.css is stale/)
  } finally {
    fs.rmSync(root, { recursive: true, force: true })
  }
})
