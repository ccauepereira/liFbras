export const SCHEMA_REFERENCIA = 2
export const CATALOGO_COLETA = [
  { id: '2_Sim', label: 'Sim', referencia: { disponivel: false, tipo: 'nenhuma', arquivo: null, origem: null, descricao: null } },
  { id: '7_Quero', label: 'Quero', referencia: { disponivel: false, tipo: 'nenhuma', arquivo: null, origem: null, descricao: null } },
  { id: '92_Energia', label: 'Energia', referencia: { disponivel: false, tipo: 'nenhuma', arquivo: null, origem: null, descricao: null } },
  { id: '110_Menos', label: 'Menos', referencia: { disponivel: false, tipo: 'nenhuma', arquivo: null, origem: null, descricao: null } },
  { id: '111_Mais', label: 'Mais', referencia: { disponivel: false, tipo: 'nenhuma', arquivo: null, origem: null, descricao: null } },
]

export const STATUS_VALIDACAO = ['nao_validado', 'aprovado_experimental', 'validado_pedagogicamente', 'rejeitado']
export const TIPOS_REFERENCIA_DIDATICA = ['imagem', 'video', 'sequencia', 'gif', 'nenhuma']
export const STORAGE_KEY = 'lifbras:referencias:v2'
const LEGACY_STORAGE_KEY = 'lifbras:referencias:v1'

export function referenciaId() {
  return globalThis.crypto?.randomUUID?.() ?? `ref-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

export function migrarReferencia(value) {
  if (!value || typeof value !== 'object') return null
  if (value.versao === 1) {
    if (typeof value.sinalId !== 'string' || !CATALOGO_COLETA.some((item) => item.id === value.sinalId)) return null
    return { ...value, versao: SCHEMA_REFERENCIA, tipo: 'referencia_rotulada', usarEmDataset: true, migradoDe: 1 }
  }
  return value.versao === SCHEMA_REFERENCIA ? value : null
}

export function validarReferencia(value) {
  if (!value || typeof value !== 'object' || value.versao !== SCHEMA_REFERENCIA) return false
  if (typeof value.referenciaId !== 'string' || typeof value.signerId !== 'string' || !value.captura || !Number.isFinite(value.captura.duracaoMs) || !Array.isArray(value.captura.frames)) return false
  if (!value.validacao || !STATUS_VALIDACAO.includes(value.validacao.status)) return false
  if (value.tipo === 'teste_tecnico') return value.usarEmDataset === false && value.sinalId === null && value.tentativa === null
  if (value.tipo !== 'referencia_rotulada' || value.usarEmDataset !== true || !CATALOGO_COLETA.some((item) => item.id === value.sinalId) || !Number.isInteger(value.tentativa) || value.tentativa < 1) return false
  if (value.migradoDe === 1) return true
  return value.referenciaDidatica?.disponivel === true && TIPOS_REFERENCIA_DIDATICA.includes(value.referenciaDidatica.tipo) && value.referenciaDidatica.tipo !== 'nenhuma' && typeof value.referenciaDidatica.origem === 'string' && value.referenciaDidatica.origem.length > 0
}

export function normalizarImportacao(parsed) {
  if (!Array.isArray(parsed)) throw new Error('formato')
  const migrated = parsed.map(migrarReferencia)
  if (migrated.some((item) => !validarReferencia(item))) throw new Error('schema')
  const ids = migrated.map((item) => item.referenciaId)
  if (new Set(ids).size !== ids.length) throw new Error('id')
  return migrated
}

export function carregarReferencias() {
  try {
    const current = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? 'null')
    if (Array.isArray(current)) return normalizarImportacao(current)
    const legacy = JSON.parse(localStorage.getItem(LEGACY_STORAGE_KEY) ?? '[]')
    const migrated = normalizarImportacao(legacy)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(migrated))
    return migrated
  } catch {
    return []
  }
}

export function salvarReferencias(referencias) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(normalizarImportacao(referencias)))
}

export function criarReferencia({ signerId, sinal, tentativa, sequencia, qualidade }) {
  return {
    versao: SCHEMA_REFERENCIA,
    referenciaId: referenciaId(),
    tipo: 'referencia_rotulada',
    usarEmDataset: true,
    sinalId: sinal.id,
    gloss: sinal.label,
    referenciaDidatica: { ...sinal.referencia },
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

export function criarTesteTecnico({ signerId, sequencia, qualidade }) {
  return {
    versao: SCHEMA_REFERENCIA,
    referenciaId: referenciaId(),
    tipo: 'teste_tecnico',
    usarEmDataset: false,
    sinalId: null,
    gloss: null,
    categoria: 'debug_tecnico',
    signerId,
    tentativa: null,
    criadoEm: new Date().toISOString(),
    origem: 'lifbras-camera',
    validacao: { status: 'nao_validado' },
    qualidade,
    captura: { duracaoMs: Math.round(sequencia.duracaoMs), frames: sequencia.frames },
  }
}

export function contarTentativas(referencias, signerId, sinalId) {
  return referencias.filter((item) => item.tipo === 'referencia_rotulada' && item.usarEmDataset === true && item.signerId === signerId && item.sinalId === sinalId)
}

export function agruparPorSigner(referencias) {
  return referencias.reduce((groups, item) => ({ ...groups, [item.signerId]: [...(groups[item.signerId] ?? []), item] }), {})
}

export function agruparPorSinal(referencias) {
  return referencias.filter((item) => item.tipo === 'referencia_rotulada').reduce((groups, item) => ({ ...groups, [item.sinalId]: [...(groups[item.sinalId] ?? []), item] }), {})
}

export function detectarDuplicata(referencia, referencias) {
  const serializado = JSON.stringify(referencia.captura)
  return referencias.some((item) => item.referenciaId !== referencia.referenciaId && JSON.stringify(item.captura) === serializado)
}
