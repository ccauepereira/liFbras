import { Download, Hand, Play, ShieldCheck, Square, Trash2, Upload } from 'lucide-react'
import { useMemo, useRef, useState } from 'react'
import Cabecalho from '../componentes/Cabecalho'
import VisualizadorMao3D from '../componentes/VisualizadorMao3D'
import useDeteccaoMao from '../ganchos/useDeteccaoMao'
import useGravacaoTemporal from '../ganchos/useGravacaoTemporal'
import { agruparPorSigner, carregarReferencias, CATALOGO_COLETA, criarReferencia, detectarDuplicata, salvarReferencias, validarReferencia } from './referencias'
import './PaginaColeta.css'

function qualidadeCaptura(sequencia) {
  const frames = sequencia?.frames ?? []
  const contagem = frames.reduce((acc, frame) => {
    const n = Number(Boolean(frame.maoEsquerda)) + Number(Boolean(frame.maoDireita))
    acc[n] += 1
    return acc
  }, [0, 0, 0])
  const gaps = frames.slice(1).map((frame, index) => frame.timestampMs - frames[index].timestampMs).filter((gap) => gap > 500)
  const fps = sequencia?.duracaoMs > 0 ? (frames.length * 1000) / sequencia.duracaoMs : 0
  const maiorAusencia = (lado) => {
    let atual = 0; let maior = 0
    frames.forEach((frame) => { atual = frame[lado] ? 0 : atual + 1; maior = Math.max(maior, atual) })
    return frames.length ? maior / frames.length : 0
  }
  return {
    frames: frames.length,
    duracaoMs: Math.round(sequencia?.duracaoMs ?? 0),
    fpsAproximado: Number(fps.toFixed(2)),
    proporcaoSemMaos: Number((contagem[0] / Math.max(1, frames.length)).toFixed(3)),
    proporcaoUmaMao: Number((contagem[1] / Math.max(1, frames.length)).toFixed(3)),
    proporcaoDuasMaos: Number((contagem[2] / Math.max(1, frames.length)).toFixed(3)),
    maiorGapMs: gaps.length ? Math.max(...gaps) : 0,
    maiorAusenciaEsquerda: Number(maiorAusencia('maoEsquerda').toFixed(3)),
    maiorAusenciaDireita: Number(maiorAusencia('maoDireita').toFixed(3)),
  }
}

function baixarArquivo(nome, conteudo) {
  const blob = new Blob([conteudo], { type: 'application/json' }); const url = URL.createObjectURL(blob); const link = document.createElement('a')
  link.href = url; link.download = nome; link.click(); URL.revokeObjectURL(url)
}

export default function PaginaColeta() {
  const [signerId, setSignerId] = useState('S001'); const [sinalId, setSinalId] = useState(CATALOGO_COLETA[0].id); const [tentativa, setTentativa] = useState(1)
  const [referencias, setReferencias] = useState(carregarReferencias); const [motivo, setMotivo] = useState(''); const [mensagem, setMensagem] = useState('')
  const inputImportRef = useRef(null); const gravacao = useGravacaoTemporal();
  const { canvasRef, desativarCamera, estadoCamera, iniciarCamera, videoRef } = useDeteccaoMao({ onFrame: gravacao.registrarFrame })
  const cameraAtiva = estadoCamera === 'ativa'; const sequencia = gravacao.sequencia; const qualidade = useMemo(() => qualidadeCaptura(sequencia), [sequencia]);
  const sinal = CATALOGO_COLETA.find((item) => item.id === sinalId) ?? CATALOGO_COLETA[0]; const tentativasSinal = referencias.filter((item) => item.signerId === signerId && item.sinalId === sinalId)

  const exportar = () => baixarArquivo(`lifbras-referencias-${new Date().toISOString().slice(0, 10)}.json`, JSON.stringify(referencias, null, 2))
  const importar = async (event) => {
    const file = event.target.files?.[0]; if (!file) return
    try {
      const parsed = JSON.parse(await file.text()); if (!Array.isArray(parsed) || !parsed.every(validarReferencia)) throw new Error('schema')
      const ids = new Set(); if (parsed.some((item) => ids.has(item.referenciaId) || ids.add(item.referenciaId) === false)) throw new Error('id')
      const merged = [...referencias, ...parsed.filter((item) => !referencias.some((current) => current.referenciaId === item.referenciaId))]; setReferencias(merged); salvarReferencias(merged); setMensagem(`${parsed.length} referências importadas localmente.`)
    } catch { setMensagem('Arquivo recusado: schema, versão ou tipos inválidos.') } finally { event.target.value = '' }
  }
  const aceitar = () => {
    if (!sequencia || !signerId.trim()) return setMensagem('Informe um signerId pseudônimo antes de aceitar.')
    const item = criarReferencia({ signerId: signerId.trim(), sinal, tentativa, sequencia, qualidade: { ...qualidade, motivoTecnico: motivo || null } }); if (detectarDuplicata(item, referencias)) return setMensagem('Captura duplicada: revise ou descarte antes de aceitar.')
    const next = [...referencias, item]; setReferencias(next); salvarReferencias(next); setMensagem('Referência guardada localmente como dado experimental.'); gravacao.novaTentativa(); setTentativa((value) => Math.min(5, value + 1))
  }
  const descartar = () => { gravacao.novaTentativa(); setMotivo(''); setMensagem('Captura descartada; nenhum landmark foi guardado.') }
  const limpar = () => { setReferencias([]); salvarReferencias([]); setMensagem('Sessão local limpa.') }

  return <main className="pagina pagina-coleta">
    <Cabecalho />
    <section className="coleta__intro"><p className="coleta__eyebrow">LABORATÓRIO EXPERIMENTAL</p><h1>Coleta experimental de referências</h1><p>Capture apenas landmarks para uma pesquisa local. A aplicação não decide se o sinal está correto.</p></section>
    <section className="coleta__consent" aria-label="Aviso de privacidade"><ShieldCheck size={20} aria-hidden="true" /><p>Esta ferramenta registra apenas landmarks derivados da câmera e metadados experimentais. Nenhum vídeo, áudio ou imagem RGB é salvo pelo LiFbras. Você pode descartar a captura.</p></section>
    <section className="coleta__form" aria-label="Identificação experimental"><label>SignerId pseudônimo<input value={signerId} onChange={(event) => setSignerId(event.target.value.replace(/[^A-Za-z0-9_-]/g, '').slice(0, 24))} aria-describedby="signer-help" /></label><small id="signer-help">Use um código como S003; não informe nome, e-mail ou matrícula.</small><label>Sinal<select value={sinalId} onChange={(event) => { setSinalId(event.target.value); setTentativa(1) }}>{CATALOGO_COLETA.map((item) => <option key={item.id} value={item.id}>{item.label} ({item.id})</option>)}</select></label><p className="coleta__tentativa"><strong>{sinal.label.toUpperCase()}</strong><span>Signer: {signerId || '—'}</span><span>Tentativa: {tentativa} / 5</span></p><div className="coleta__tentativas" aria-label="Tentativas aceitas">{[1, 2, 3, 4, 5].map((numero) => <span key={numero} className={tentativasSinal.some((item) => item.tentativa === numero) ? 'feito' : ''}>{tentativasSinal.some((item) => item.tentativa === numero) ? '✓' : '○'} {numero}</span>)}</div></section>
    <section className="coleta__camera" aria-label="Captura local"><div className="coleta__palco"><video ref={videoRef} autoPlay muted playsInline aria-label="Pré-visualização temporária da câmera" /><canvas ref={canvasRef} aria-hidden="true" />{!cameraAtiva && <p>Ative a câmera para preparar a captura.</p>}</div><div className="coleta__acoes">{cameraAtiva ? <button type="button" onClick={desativarCamera}><Square size={17} /> Desativar câmera</button> : <button type="button" onClick={iniciarCamera}>Ativar câmera</button>}{cameraAtiva && !['recording', 'countdown'].includes(gravacao.estado) && <button type="button" onClick={gravacao.iniciarCaptura}>Iniciar countdown</button>}{cameraAtiva && ['recording', 'countdown'].includes(gravacao.estado) && <button type="button" onClick={gravacao.pararCaptura}><Square size={17} /> Parar</button>}</div><p className="coleta__status" role="status" aria-live="polite">{gravacao.estado === 'countdown' ? `Começando em ${gravacao.contagem}…` : gravacao.estado === 'recording' ? `Gravando: ${gravacao.quantidadeFrames} frames` : estadoCamera === 'ativa' ? 'Câmera pronta.' : 'Câmera inativa.'}</p></section>
    {sequencia && <section className="coleta__revisao" aria-labelledby="revisao-title"><div><p className="coleta__eyebrow">REVISÃO LOCAL</p><h2 id="revisao-title">Revise antes de guardar</h2></div><VisualizadorMao3D resultadoMaoRef={gravacao.replayFrameRef} cameraAtiva={false} /><div className="coleta__replay"><button type="button" onClick={gravacao.reproduzir}><Play size={16} /> Reproduzir replay</button><button type="button" onClick={gravacao.novaTentativa}>Nova tentativa</button></div><dl className="coleta__qualidade"><div><dt>Frames</dt><dd>{qualidade.frames}</dd></div><div><dt>Duração</dt><dd>{(qualidade.duracaoMs / 1000).toFixed(1)} s</dd></div><div><dt>FPS estimado</dt><dd>{qualidade.fpsAproximado}</dd></div><div><dt>0 / 1 / 2 mãos</dt><dd>{Math.round(qualidade.proporcaoSemMaos * 100)}% / {Math.round(qualidade.proporcaoUmaMao * 100)}% / {Math.round(qualidade.proporcaoDuasMaos * 100)}%</dd></div><div><dt>Maior gap</dt><dd>{qualidade.maiorGapMs} ms</dd></div><div><dt>Ausência mão E/D</dt><dd>{Math.round(qualidade.maiorAusenciaEsquerda * 100)}% / {Math.round(qualidade.maiorAusenciaDireita * 100)}%</dd></div></dl><p className="coleta__nota">Estas verificações medem qualidade técnica, não correção em Libras.</p><label>Motivo técnico opcional<select value={motivo} onChange={(event) => setMotivo(event.target.value)}><option value="">Nenhum</option><option>Câmera ruim</option><option>Tracking perdido</option><option>Início cedo</option><option>Final cortado</option><option>Mão fora da tela</option><option>Captura incompleta</option><option>Outro</option></select></label><div className="coleta__revisao-acoes"><button type="button" onClick={aceitar}>Aceitar referência experimental</button><button type="button" onClick={descartar}><Trash2 size={16} /> Descartar</button></div></section>}
    <section className="coleta__dados"><h2>Sessão local</h2><p>{referencias.length} referências guardadas no navegador; status inicial: <code>nao_validado</code>.</p><div className="coleta__dados-acoes"><button type="button" onClick={exportar} disabled={!referencias.length}><Download size={16} /> Exportar referências</button><button type="button" onClick={() => inputImportRef.current?.click()}><Upload size={16} /> Importar arquivo</button><input ref={inputImportRef} type="file" accept="application/json,.json" onChange={importar} hidden /><button type="button" onClick={limpar} disabled={!referencias.length}><Trash2 size={16} /> Limpar sessão</button></div><p className="coleta__mensagem" role="status" aria-live="polite">{mensagem}</p><p className="coleta__privacidade"><Hand size={16} /> Nenhuma chamada de backend, upload, analytics, vídeo ou áudio é feita por esta ferramenta.</p><p className="coleta__resumo">Signers locais: {Object.keys(agruparPorSigner(referencias)).length} · Schema: v1</p></section>
  </main>
}
