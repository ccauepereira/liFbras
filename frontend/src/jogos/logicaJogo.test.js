import test from 'node:test'
import assert from 'node:assert/strict'
import { colisaoCircular, gerarAlvoSeguro, mapearPontaIndicador } from './logicaJogo.js'

test('indicator mapping mirrors horizontal position and preserves vertical position', () => {
  assert.deepEqual(mapearPontaIndicador({ x: 0.2, y: 0.7 }, 640, 480, 640, 480), { x: 0.8, y: 0.7 })
})

test('indicator mapping accounts for cover crop before mirroring', () => {
  const mapped = mapearPontaIndicador({ x: 0.5, y: 0 }, 640, 480, 360, 640)
  assert.ok(mapped.x >= 0 && mapped.x <= 1)
  assert.ok(mapped.y === 0)
})

test('target stays entirely inside the play area and moves away from the previous target', () => {
  const previous = { x: 0.5, y: 0.5 }
  const next = gerarAlvoSeguro(360, 500, 40, () => 0.5, previous)
  assert.ok(next.x >= 40 / 360 && next.x <= 1 - 40 / 360)
  assert.ok(next.y >= 40 / 500 && next.y <= 1 - 40 / 500)
  assert.ok(Math.hypot((next.x - previous.x) * 360, (next.y - previous.y) * 500) >= 40 * 2.2)
})

test('circular collision awards only spatial contact', () => {
  const target = { x: 0.5, y: 0.5 }
  assert.equal(colisaoCircular({ x: 0.5, y: 0.5 }, target, 360, 640, 40, 12), true)
  assert.equal(colisaoCircular({ x: 0, y: 0 }, target, 360, 640, 40, 12), false)
  assert.equal(colisaoCircular(null, target, 360, 640, 40), false)
})
