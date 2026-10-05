export const SCHEMA_REFERENCIA = 1
export const CATALOGO_COLETA = [
  { id: '2_Sim', label: 'Sim' },
  { id: '7_Quero', label: 'Quero' },
  { id: '92_Energia', label: 'Energia' },
  { id: '110_Menos', label: 'Menos' },
  { id: '111_Mais', label: 'Mais' },
]

export const STATUS_VALIDACAO = ['nao_validado', 'aprovado_experimental', 'validado_pedagogicamente', 'rejeitado']
const STORAGE_KEY = 'lifbras:referencias:v1'

export function referenciaId() {
  return globalThis.crypto?.randomUUID?.() ?? `ref-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

export function validarReferencia(value) {
  if (!value || typeof value !== 'object' || value.versao !== SCHEMA_REFERENCIA) return false
  if (typeof value.referenciaId !== 'string' || typeof value.sinalId !== 'string' || typeof value.signerId !== 'string') return false
  if (!CATALOGO_COLETA.some((item) => item.id === value.sinalId)) return false
  if (!Number.isInteger(value.tentativa) || value.tentativa < 1) return false
  if (!value.captura || !Number.isFinite(value.captura.duracaoMs) || !Array.isArray(value.captura.frames)) return false
  return value.validacao && STATUS_VALIDACAO.includes(value.validacao.status)
}

export function carregarReferencias() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]')
    return Array.isArray(parsed) ? parsed.filter(validarReferencia) : []
  } catch {
    return []
  }
}

export function salvarReferencias(referencias) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(referencias.filter(validarReferencia)))
}

export function criarReferencia({ signerId, sinal, tentativa, sequencia, qualidade }) {
  return {
    versao: SCHEMA_REFERENCIA,
    referenciaId: referenciaId(),
    sinalId: sinal.id,
    gloss: sinal.label,
    categoria: 'experimental',
    signerId,
    tentativa,
    criadoEm: new Date().toISOString(),
    origem: 'lifbras-camera',
    validacao: { status: 'nao_validado' },
    qualidade,
    captura: { duracaoMs: Math.round(sequencia.duracaoMs), frames: sequencia.frames },
  }
}

export function agruparPorSigner(referencias) {
  return referencias.reduce((groups, item) => ({ ...groups, [item.signerId]: [...(groups[item.signerId] ?? []), item] }), {})
}

export function agruparPorSinal(referencias) {
  return referencias.reduce((groups, item) => ({ ...groups, [item.sinalId]: [...(groups[item.sinalId] ?? []), item] }), {})
}

export function detectarDuplicata(referencia, referencias) {
  const serializado = JSON.stringify(referencia.captura)
  return referencias.some((item) => item.referenciaId !== referencia.referenciaId && JSON.stringify(item.captura) === serializado)
}

export { STORAGE_KEY }
