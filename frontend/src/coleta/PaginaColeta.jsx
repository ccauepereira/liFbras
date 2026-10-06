import { Download, Hand, Play, ShieldCheck, Square, Trash2, Upload } from 'lucide-react'
import { useMemo, useRef, useState } from 'react'
import Cabecalho from '../componentes/Cabecalho'
import VisualizadorMao3D from '../componentes/VisualizadorMao3D'
import useDeteccaoMao from '../ganchos/useDeteccaoMao'
import useGravacaoTemporal from '../ganchos/useGravacaoTemporal'
import { agruparPorSigner, carregarReferencias, CATALOGO_COLETA, contarTentativas, criarReferencia, criarTesteTecnico, detectarDuplicata, normalizarImportacao, salvarReferencias } from './referencias'
import './PaginaColeta.css'

function qualidadeCaptura(sequencia) {
  const frames = sequencia?.frames ?? []
  const contagem = frames.reduce((acc, frame) => { acc[Number(Boolean(frame.maoEsquerda)) + Number(Boolean(frame.maoDireita))] += 1; return acc }, [0, 0, 0])
  const gaps = frames.slice(1).map((frame, index) => frame.timestampMs - frames[index].timestampMs).filter((gap) => gap > 500)
  const fps = sequencia?.duracaoMs > 0 ? frames.length * 1000 / sequencia.duracaoMs : 0
  const maiorAusencia = (lado) => { let atual = 0; let maior = 0; frames.forEach((frame) => { atual = frame[lado] ? 0 : atual + 1; maior = Math.max(maior, atual) }); return frames.length ? maior / frames.length : 0 }
  return { frames: frames.length, duracaoMs: Math.round(sequencia?.duracaoMs ?? 0), fpsAproximado: Number(fps.toFixed(2)), proporcaoSemMaos: Number((contagem[0] / Math.max(1, frames.length)).toFixed(3)), proporcaoUmaMao: Number((contagem[1] / Math.max(1, frames.length)).toFixed(3)), proporcaoDuasMaos: Number((contagem[2] / Math.max(1, frames.length)).toFixed(3)), maiorGapMs: gaps.length ? Math.max(...gaps) : 0, maiorAusenciaEsquerda: Number(maiorAusencia('maoEsquerda').toFixed(3)), maiorAusenciaDireita: Number(maiorAusencia('maoDireita').toFixed(3)) }
}

function baixarArquivo(nome, conteudo) {
  const blob = new Blob([conteudo], { type: 'application/json' }); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = nome; link.click(); URL.revokeObjectURL(url)
}

function ReferenciaDidatica({ sinal }) {
  const ref = sinal.referencia
  if (!ref.disponivel || ref.tipo === 'nenhuma' || !ref.arquivo) return <p className="coleta__bloqueio" role="status">Referência didática ainda não disponível.</p>
  if (ref.tipo === 'imagem') return <img className="coleta__referencia-media" src={ref.arquivo} alt={`Referência didática: ${sinal.label}`} />
  if (ref.tipo === 'gif') return <img className="coleta__referencia-media" src={ref.arquivo} alt={`Referência didática animada: ${sinal.label}`} />
  if (ref.tipo === 'video') return <video className="coleta__referencia-media" src={ref.arquivo} controls playsInline />
  if (ref.tipo === 'sequencia' && Array.isArray(ref.arquivo)) return <div className="coleta__sequencia">{ref.arquivo.map((arquivo, index) => <img key={arquivo} src={arquivo} alt={`Quadro ${index + 1} da referência didática`} />)}</div>
  return <p className="coleta__bloqueio" role="status">Referência didática ainda não disponível.</p>
}

export default function PaginaColeta() {
  const [modo, setModo] = useState('escolha')
  const [etapa, setEtapa] = useState('referencia')
  const [signerId, setSignerId] = useState('S001')
  const [sinalId, setSinalId] = useState(CATALOGO_COLETA[0].id)
  const [tentativa, setTentativa] = useState(1)
  const [referencias, setReferencias] = useState(carregarReferencias)
  const [motivo, setMotivo] = useState('')
  const [mensagem, setMensagem] = useState('')
  const inputImportRef = useRef(null)
  const gravacao = useGravacaoTemporal()
  const { canvasRef, desativarCamera, estadoCamera, iniciarCamera, videoRef } = useDeteccaoMao({ onFrame: gravacao.registrarFrame })
  const cameraAtiva = estadoCamera === 'ativa'; const sequencia = gravacao.sequencia
  const qualidade = useMemo(() => qualidadeCaptura(sequencia), [sequencia])
  const sinal = CATALOGO_COLETA.find((item) => item.id === sinalId) ?? CATALOGO_COLETA[0]
  const tentativasSinal = contarTentativas(referencias, signerId, sinalId)
  const emCaptura = ['countdown', 'recording'].includes(gravacao.estado)

  const iniciarModo = (novoModo) => { gravacao.novaTentativa(); setModo(novoModo); setEtapa(novoModo === 'coleta_guiada' ? 'referencia' : 'captura'); setMensagem('') }
  const exportar = () => baixarArquivo(`lifbras-referencias-${new Date().toISOString().slice(0, 10)}.json`, JSON.stringify(referencias, null, 2))
  const importar = async (event) => {
    const file = event.target.files?.[0]; if (!file) return
    try {
      const parsed = normalizarImportacao(JSON.parse(await file.text()))
      const merged = [...referencias, ...parsed.filter((item) => !referencias.some((current) => current.referenciaId === item.referenciaId))]
      setReferencias(merged); salvarReferencias(merged); setMensagem(`${parsed.length} registros importados. Arquivos v1 foram migrados para v2.`)
    } catch { setMensagem('Arquivo recusado: schema, versão, tipos ou IDs inválidos.') } finally { event.target.value = '' }
  }
  const aceitar = () => {
    if (!sequencia) return
    if (!signerId.trim()) return setMensagem('Informe um signerId pseudônimo antes de guardar.')
    const item = modo === 'teste_tecnico'
      ? criarTesteTecnico({ signerId: signerId.trim(), sequencia, qualidade: { ...qualidade, motivoTecnico: motivo || null } })
      : criarReferencia({ signerId: signerId.trim(), sinal, tentativa, sequencia, qualidade: { ...qualidade, motivoTecnico: motivo || null } })
    if (detectarDuplicata(item, referencias)) return setMensagem('Captura duplicada: revise ou descarte antes de guardar.')
    const next = [...referencias, item]; setReferencias(next); salvarReferencias(next)
    setMensagem(modo === 'teste_tecnico' ? 'Teste técnico exportável localmente; não entra no dataset nem conta como tentativa.' : 'Captura concluída e guardada como referência não validada.')
    setMotivo('')
    if (modo === 'teste_tecnico') gravacao.novaTentativa()
    if (modo === 'coleta_guiada') setTentativa((value) => Math.min(5, value + 1))
  }
  const descartar = () => { gravacao.novaTentativa(); setMotivo(''); setEtapa(modo === 'coleta_guiada' ? 'referencia' : 'captura'); setMensagem('Captura descartada; nenhum landmark foi guardado.') }
  const limpar = () => { setReferencias([]); salvarReferencias([]); setMensagem('Sessão local limpa.') }
  const escolherSinal = (value) => { setSinalId(value); setTentativa(1); setEtapa('referencia'); gravacao.novaTentativa() }
  const pronto = () => { if (!sinal.referencia.disponivel || !cameraAtiva) return; setEtapa('captura'); gravacao.iniciarCaptura() }
  const repetir = () => { gravacao.novaTentativa(); setEtapa(modo === 'coleta_guiada' ? 'referencia' : 'captura'); setMensagem(modo === 'coleta_guiada' ? 'Consulte a referência antes da próxima tentativa.' : 'Captura técnica descartada. Você pode iniciar outra.') }
  const referenciaNovamente = () => { gravacao.novaTentativa(); setEtapa('referencia'); setMensagem('Referência exibida novamente.') }

  return <main className="pagina pagina-coleta">
    <Cabecalho />
    <section className="coleta__intro"><p className="coleta__eyebrow">LABORATÓRIO EXPERIMENTAL</p><h1>Laboratório de coleta</h1><p>Teste recursos da câmera ou faça uma coleta guiada por referência didática.</p></section>
    {modo === 'escolha' && <section className="coleta__modos" aria-label="Escolha do modo de coleta">
      <article><h2>Teste técnico</h2><p>Teste câmera, landmarks e replay sem gerar dados rotulados de Libras.</p><button type="button" onClick={() => iniciarModo('teste_tecnico')}>Teste técnico</button></article>
      <article><h2>Coleta guiada</h2><p>Veja uma referência didática antes de gravar uma tentativa rotulada.</p><button type="button" onClick={() => iniciarModo('coleta_guiada')}>Coleta guiada</button></article>
    </section>}
    {modo !== 'escolha' && <>
      <button type="button" className="coleta__voltar" onClick={() => { gravacao.novaTentativa(); desativarCamera(); setModo('escolha'); setEtapa('referencia') }}>← Escolher outro modo</button>
      <section className="coleta__consent" aria-label="Aviso de privacidade"><ShieldCheck size={20} aria-hidden="true" /><p>Esta ferramenta registra landmarks derivados da câmera e metadados. Nenhum vídeo, áudio ou imagem RGB é salvo pelo LiFbras.</p></section>
      {modo === 'teste_tecnico' && <section className="coleta__aviso-tecnico"><h2>Teste técnico</h2><p>Use este modo para testar câmera, landmarks, gravação e replay.</p><p>Os movimentos feitos aqui não representam sinais de Libras e não entram no dataset de pesquisa.</p><button type="button" onClick={iniciarCamera} disabled={cameraAtiva}>Testar câmera</button></section>}
      {modo === 'coleta_guiada' && <section className="coleta__form" aria-label="Coleta guiada">
        <label>SignerId pseudônimo<input value={signerId} onChange={(event) => setSignerId(event.target.value.replace(/[^A-Za-z0-9_-]/g, '').slice(0, 24))} aria-describedby="signer-help" /></label>
        <small id="signer-help">Use um código como S003; não informe nome, e-mail ou matrícula.</small>
        <label>Sinal<select value={sinalId} onChange={(event) => escolherSinal(event.target.value)}>{CATALOGO_COLETA.map((item) => <option key={item.id} value={item.id}>{item.label} ({item.id})</option>)}</select></label>
        <p className="coleta__tentativa"><strong>{sinal.label.toUpperCase()}</strong><span>Signer: {signerId || '—'}</span><span>Tentativa: {tentativa} / 5</span></p>
        <div className="coleta__tentativas" aria-label="Tentativas rotuladas">{[1, 2, 3, 4, 5].map((numero) => <span key={numero} className={tentativasSinal.some((item) => item.tentativa === numero) ? 'feito' : ''}>{tentativasSinal.some((item) => item.tentativa === numero) ? '✓' : '○'} {numero}</span>)}</div>
      </section>}
      {modo === 'coleta_guiada' && etapa === 'referencia' && <section className="coleta__referencia" aria-labelledby="referencia-title"><p className="coleta__eyebrow">REFERÊNCIA DIDÁTICA</p><h2 id="referencia-title">Sinal: {sinal.label}</h2><ReferenciaDidatica sinal={sinal} />{sinal.referencia.origem && <p className="coleta__origem">Fonte: {sinal.referencia.origem}</p>}{sinal.referencia.descricao && <p>{sinal.referencia.descricao}</p>}<div className="coleta__acoes"><button type="button" onClick={pronto} disabled={!sinal.referencia.disponivel || !cameraAtiva}>Estou pronto</button><button type="button" className="coleta__botao-secundario" onClick={iniciarCamera} disabled={cameraAtiva}>Testar câmera</button></div></section>}
      <section className="coleta__camera" aria-label="Captura local"><div className="coleta__palco"><video ref={videoRef} autoPlay muted playsInline aria-label="Pré-visualização temporária da câmera" /><canvas ref={canvasRef} aria-hidden="true" />{!cameraAtiva && <p>Ative a câmera para preparar a captura.</p>}{gravacao.estado === 'countdown' && <strong className="coleta__countdown" aria-live="assertive">{gravacao.contagem}</strong>}</div><div className="coleta__acoes">{cameraAtiva ? <button type="button" onClick={desativarCamera}><Square size={17} /> Desativar câmera</button> : !(modo === 'teste_tecnico' || (modo === 'coleta_guiada' && etapa === 'referencia')) && <button type="button" onClick={iniciarCamera}>Ativar câmera</button>}{modo === 'teste_tecnico' && cameraAtiva && !emCaptura && <button type="button" onClick={gravacao.iniciarCaptura}>Iniciar gravação técnica</button>}{emCaptura && <button type="button" onClick={gravacao.pararCaptura}><Square size={17} /> Parar</button>}</div><p className="coleta__status" role="status" aria-live="polite">{gravacao.estado === 'countdown' ? `Começando em ${gravacao.contagem}…` : gravacao.estado === 'recording' ? `Gravando: ${gravacao.quantidadeFrames} frames` : estadoCamera === 'ativa' ? 'Câmera pronta.' : 'Câmera inativa.'}</p></section>
      {sequencia && <section className="coleta__revisao" aria-labelledby="revisao-title"><div><p className="coleta__eyebrow">REVISÃO LOCAL</p><h2 id="revisao-title">Captura concluída</h2></div><VisualizadorMao3D resultadoMaoRef={gravacao.replayFrameRef} cameraAtiva={false} /><div className="coleta__replay"><button type="button" onClick={gravacao.reproduzir}><Play size={16} /> Reproduzir replay</button><button type="button" onClick={repetir}>Repetir</button>{modo === 'coleta_guiada' && <button type="button" onClick={referenciaNovamente}>Ver referência novamente</button>}</div><dl className="coleta__qualidade"><div><dt>Frames</dt><dd>{qualidade.frames}</dd></div><div><dt>Duração</dt><dd>{(qualidade.duracaoMs / 1000).toFixed(1)} s</dd></div><div><dt>FPS estimado</dt><dd>{qualidade.fpsAproximado}</dd></div><div><dt>0 / 1 / 2 mãos</dt><dd>{Math.round(qualidade.proporcaoSemMaos * 100)}% / {Math.round(qualidade.proporcaoUmaMao * 100)}% / {Math.round(qualidade.proporcaoDuasMaos * 100)}%</dd></div><div><dt>Maior gap</dt><dd>{qualidade.maiorGapMs} ms</dd></div><div><dt>Ausência mão E/D</dt><dd>{Math.round(qualidade.maiorAusenciaEsquerda * 100)}% / {Math.round(qualidade.maiorAusenciaDireita * 100)}%</dd></div></dl><p className="coleta__nota">Qualidade técnica não confirma validade linguística.</p><label>Motivo técnico opcional<select value={motivo} onChange={(event) => setMotivo(event.target.value)}><option value="">Nenhum</option><option>Câmera ruim</option><option>Tracking perdido</option><option>Início cedo</option><option>Final cortado</option><option>Mão fora da tela</option><option>Captura incompleta</option><option>Outro</option></select></label><div className="coleta__revisao-acoes"><button type="button" onClick={aceitar}>{modo === 'teste_tecnico' ? 'Guardar teste técnico' : 'Aceitar captura experimental'}</button><button type="button" className="coleta__botao-secundario" onClick={descartar}><Trash2 size={16} /> Descartar</button></div></section>}
    </>}
    <section className="coleta__dados"><h2>Sessão local</h2><p>{referencias.length} registros guardados no navegador; coleta rotulada: {referencias.filter((item) => item.tipo === 'referencia_rotulada').length} · testes técnicos: {referencias.filter((item) => item.tipo === 'teste_tecnico').length}.</p><div className="coleta__dados-acoes"><button type="button" onClick={exportar} disabled={!referencias.length}><Download size={16} /> Exportar registros</button><button type="button" onClick={() => inputImportRef.current?.click()}><Upload size={16} /> Importar arquivo</button><input ref={inputImportRef} type="file" accept="application/json,.json" onChange={importar} hidden /><button type="button" onClick={limpar} disabled={!referencias.length}><Trash2 size={16} /> Limpar sessão</button></div><p className="coleta__mensagem" role="status" aria-live="polite">{mensagem}</p><p className="coleta__privacidade"><Hand size={16} /> Nenhuma chamada de backend, upload, analytics, vídeo ou áudio é feita por esta ferramenta.</p><p className="coleta__resumo">Signers locais: {Object.keys(agruparPorSigner(referencias)).length} · Schema: v2</p></section>
  </main>
}
