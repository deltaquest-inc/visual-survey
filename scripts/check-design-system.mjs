#!/usr/bin/env node
/** Dependency-free source contract. Rendered review remains required by DESIGN.md. */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
export function contrast(a, b) {
  const lum = (hex) => {
    if (!/^#[0-9a-f]{6}$/i.test(hex)) throw new Error(`Expected opaque six-digit hex, got ${hex}`)
    const c = [1, 3, 5]
      .map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
      .map((v) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4))
    return c[0] * 0.2126 + c[1] * 0.7152 + c[2] * 0.0722
  }
  const x = lum(a),
    y = lum(b)
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05)
}
export function validate(root, config) {
  const errors = [],
    checks = []
  function read(p) {
    const absolute = path.resolve(root, p)
    if (!absolute.startsWith(path.resolve(root) + path.sep))
      throw new Error(`Path outside repository: ${p}`)
    return fs.readFileSync(absolute, 'utf8')
  }
  function expect(ok, message) {
    ;(ok ? checks : errors).push(message)
  }
  expect(
    Array.isArray(config.apps) && config.apps.length > 0,
    'At least one frontend app is configured'
  )
  const configured = new Set((config.apps || []).map((app) => app.package))
  const libraries = new Map((config.nonApps || []).map((item) => [item.package, item.reason]))
  function inventory(directory) {
    for (const item of fs.readdirSync(path.join(root, directory), { withFileTypes: true })) {
      if (['node_modules', '.git', '.next', '.yarn', 'dist', 'coverage'].includes(item.name))
        continue
      const relative = path.posix.join(directory, item.name)
      if (item.isDirectory() && !item.isSymbolicLink()) inventory(relative)
      if (item.isFile() && item.name === 'package.json') {
        const pkg = JSON.parse(read(relative))
        const deps = { ...pkg.dependencies, ...pkg.devDependencies }
        if (deps.next || deps['react-dom'] || deps.vue || deps.svelte) {
          expect(
            configured.has(relative) || Boolean(libraries.get(relative)?.trim()),
            `Frontend package inventoried: ${relative}`
          )
        }
      }
    }
  }
  inventory('')
  for (const app of config.apps || []) {
    try {
      const pkg = JSON.parse(read(app.package))
      const dependencies = { ...pkg.dependencies, ...pkg.devDependencies }
      expect(Boolean(dependencies.tailwindcss), `${app.name}: Tailwind dependency`)
      expect(/tailwindcss/.test(read(app.buildConfig)), `${app.name}: Tailwind build plugin`)
      const css = read(app.styles)
      expect(
        /@import\s+['"]tailwindcss['"]|@tailwind\s+utilities/.test(css),
        `${app.name}: Tailwind stylesheet import`
      )
      expect(
        read(app.entry).includes(app.importMarker),
        `${app.name}: stylesheet imported by application entry`
      )
      const design = read(app.design)
      for (const heading of [
        'Token sources',
        'Components',
        'Accessibility',
        'Review and learning',
      ]) {
        expect(design.includes(`## ${heading}`), `${app.name}: DESIGN.md ${heading}`)
      }
      expect(
        read(app.instructions).includes(app.designLink),
        `${app.name}: discoverable design instructions`
      )
      const tokens = Object.fromEntries(
        [...read(app.tokenSource).matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)].map((m) => [
          m[1],
          m[2].trim(),
        ])
      )
      for (const token of app.requiredTokens)
        expect(Boolean(tokens[token]), `${app.name}: token ${token}`)
      // Explicit reviewed pairs only. CSS cascade, opacity, images and arbitrary colors need browser checks.
      expect(
        (app.contrastPairs || []).length > 0 || Boolean(app.externalContrast),
        `${app.name}: contrast coverage is explicit`
      )
      for (const scheme of app.requiredSchemes || []) {
        expect((app.contrastPairs || []).some(pair => pair.scheme === scheme), `${app.name}: contrast coverage for ${scheme}`)
      }
      if (app.externalContrast) {
        expect(
          read(app.externalContrast.script).length > 0 &&
            JSON.parse(read('package.json')).scripts['design:check'].includes(
              app.externalContrast.command
            ),
          `${app.name}: existing contrast gate is mandatory in design:check`
        )
      }
      const color = (token, scheme) => {
        const value = tokens[token]
        const dual = /^light-dark\(\s*(#[0-9a-f]{6})\s*,\s*(#[0-9a-f]{6})\s*\)$/i.exec(value || '')
        if (dual) {
          if (!['light', 'dark'].includes(scheme)) throw new Error(`Scheme required for ${token}`)
          return dual[scheme === 'dark' ? 2 : 1]
        }
        return value
      }
      for (const pair of app.contrastPairs || []) {
        const ratio = contrast(
          color(pair.foreground, pair.scheme),
          color(pair.background, pair.scheme)
        )
        expect(
          ratio >= pair.minimum,
          `${app.name}: ${pair.scheme || "fixed"} ${pair.foreground}/${pair.background} ${ratio.toFixed(2)}:1 >= ${pair.minimum}:1`
        )
      }
      expect(
        app.componentSources.length > 0 &&
          app.componentSources.every((p) => read(p).trim().length > 0),
        `${app.name}: existing reusable components`
      )
    } catch (error) {
      errors.push(`${app.name}: ${error.message}`)
    }
  }
  return {
    checks,
    errors,
    limitations:
      'Source contract only; run builds, existing tests, and rendered keyboard/mobile/contrast review. Not a whole-site accessibility certification.',
  }
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const root = process.cwd()
  const result = validate(
    root,
    JSON.parse(fs.readFileSync(path.join(root, 'design-system.config.json'), 'utf8'))
  )
  console.log(JSON.stringify(result, null, 2))
  process.exitCode = result.errors.length ? 1 : 0
}
