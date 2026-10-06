import test from 'node:test'
import assert from 'node:assert/strict'
import {
  CATALOGO_COLETA,
  contarTentativas,
  criarTesteTecnico,
  migrarReferencia,
  normalizarImportacao,
  validarReferencia,
} from './referencias.js'

const sequencia = { duracaoMs: 3000, frames: [] }
const qualidade = { frames: 0 }

function referenciaV1() {
  return { versao: 1, referenciaId: 'old-1', sinalId: '7_Quero', gloss: 'Quero', categoria: 'experimental', signerId: 'S001', tentativa: 1, criadoEm: '2026-10-05T00:00:00Z', origem: 'lifbras-camera', validacao: { status: 'nao_validado' }, captura: { duracaoMs: 3000, frames: [] } }
}

test('catalog marks unavailable didactic references explicitly and blocks all five target classes', () => {
  assert.deepEqual(CATALOGO_COLETA.map(({ id, referencia }) => [id, referencia.disponivel, referencia.tipo]), [
    ['2_Sim', false, 'nenhuma'], ['7_Quero', false, 'nenhuma'], ['92_Energia', false, 'nenhuma'], ['110_Menos', false, 'nenhuma'], ['111_Mais', false, 'nenhuma'],
  ])
})

test('technical test carries no label and is excluded from labeled attempts', () => {
  const item = criarTesteTecnico({ signerId: 'T001', sequencia, qualidade })
  assert.equal(item.tipo, 'teste_tecnico')
  assert.equal(item.sinalId, null)
  assert.equal(item.tentativa, null)
  assert.equal(item.usarEmDataset, false)
  assert.equal(validarReferencia(item), true)
  assert.equal(contarTentativas([item], 'T001', '7_Quero').length, 0)
})

test('V2.07 records migrate explicitly and remain valid legacy labeled records', () => {
  const migrated = migrarReferencia(referenciaV1())
  assert.equal(migrated.versao, 2)
  assert.equal(migrated.migradoDe, 1)
  assert.equal(migrated.tipo, 'referencia_rotulada')
  assert.equal(migrated.usarEmDataset, true)
  assert.equal(validarReferencia(migrated), true)
  assert.equal(normalizarImportacao([referenciaV1()])[0].referenciaId, 'old-1')
})

test('new labeled records require an identified didactic source', () => {
  const invalid = { ...referenciaV1(), versao: 2, tipo: 'referencia_rotulada', usarEmDataset: true }
  assert.equal(validarReferencia(invalid), false)
  assert.throws(() => normalizarImportacao([invalid]), /schema/)
})

test('schema rejects contradictory technical labels and duplicate IDs', () => {
  const technical = criarTesteTecnico({ signerId: 'T001', sequencia, qualidade })
  assert.equal(validarReferencia({ ...technical, sinalId: '7_Quero' }), false)
  assert.throws(() => normalizarImportacao([technical, technical]), /id/)
})
