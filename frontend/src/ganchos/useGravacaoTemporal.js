import { useCallback, useEffect, useRef, useState } from 'react'
import { copiarFrame, contarMaos } from './temporal'

const DURACAO_MAXIMA_MS = 5000

function frameMaisProximo(frames, tempoMs) {
  if (!frames.length) return null
  return frames.reduce((anterior, atual) => (
    Math.abs(atual.timestampMs - tempoMs) < Math.abs(anterior.timestampMs - tempoMs) ? atual : anterior
  ))
}

export default function useGravacaoTemporal() {
  const framesRef = useRef([])
  const inicioRef = useRef(0)
  const estadoRef = useRef('idle')
  const countdownTimerRef = useRef(null)
  const relogioRef = useRef(null)
  const limiteTimerRef = useRef(null)
  const replayFrameRef = useRef({ landmarks: [] })
  const replayAnimacaoRef = useRef(null)
  const sequenciaRef = useRef(null)
  const [estado, setEstado] = useState('idle')
  const [contagem, setContagem] = useState(0)
  const [duracaoMs, setDuracaoMs] = useState(0)
  const [quantidadeFrames, setQuantidadeFrames] = useState(0)
  const [maximoMaos, setMaximoMaos] = useState(0)
  const [posicaoReplayMs, setPosicaoReplayMs] = useState(0)
  const [sequencia, setSequencia] = useState(null)

  const atualizarEstado = useCallback((novoEstado) => {
    estadoRef.current = novoEstado
    setEstado(novoEstado)
  }, [])

  const limparTimers = useCallback(() => {
    window.clearInterval(countdownTimerRef.current)
    window.clearInterval(relogioRef.current)
    window.clearTimeout(limiteTimerRef.current)
    countdownTimerRef.current = null
    relogioRef.current = null
    limiteTimerRef.current = null
  }, [])

  const mostrarFrameReplay = useCallback((tempoMs) => {
    const frames = sequenciaRef.current?.frames ?? []
    const frame = frameMaisProximo(frames, tempoMs)
    replayFrameRef.current = { landmarks: [frame?.maoEsquerda, frame?.maoDireita].filter(Boolean) }
    setPosicaoReplayMs(Math.max(0, Math.min(tempoMs, sequenciaRef.current?.duracaoMs ?? 0)))
  }, [])

  const finalizarGravacao = useCallback(() => {
    if (estadoRef.current !== 'recording') return
    limparTimers()
    const ultimoFrame = framesRef.current.at(-1)
    const duracaoFinal = Math.min(DURACAO_MAXIMA_MS, Math.max(0, ultimoFrame?.timestampMs ?? performance.now() - inicioRef.current))
    const resultado = {
      versao: 1,
      duracaoMs: Math.round(duracaoFinal),
      frames: framesRef.current,
    }
    sequenciaRef.current = resultado
    setSequencia(resultado)
    setDuracaoMs(resultado.duracaoMs)
    setQuantidadeFrames(resultado.frames.length)
    setPosicaoReplayMs(0)
    mostrarFrameReplay(0)
    atualizarEstado('recorded')
  }, [atualizarEstado, limparTimers, mostrarFrameReplay])

  const iniciarCaptura = useCallback(() => {
    if (estadoRef.current !== 'idle' && estadoRef.current !== 'recorded') return
    limparTimers()
    framesRef.current = []
    sequenciaRef.current = null
    setSequencia(null)
    setDuracaoMs(0)
    setQuantidadeFrames(0)
    setMaximoMaos(0)
    setPosicaoReplayMs(0)
    setContagem(3)
    atualizarEstado('countdown')

    let restante = 3
    countdownTimerRef.current = window.setInterval(() => {
      restante -= 1
      setContagem(restante)
      if (restante <= 0) {
        window.clearInterval(countdownTimerRef.current)
        countdownTimerRef.current = null
        inicioRef.current = performance.now()
        atualizarEstado('recording')
        relogioRef.current = window.setInterval(() => {
          setDuracaoMs(Math.min(DURACAO_MAXIMA_MS, performance.now() - inicioRef.current))
        }, 100)
        limiteTimerRef.current = window.setTimeout(finalizarGravacao, DURACAO_MAXIMA_MS)
      }
    }, 1000)
  }, [atualizarEstado, finalizarGravacao, limparTimers])

  const registrarFrame = useCallback((resultado, timestampMediaPipe) => {
    if (estadoRef.current !== 'recording') return
    const timestampMs = Math.max(0, Math.round(timestampMediaPipe - inicioRef.current))
    if (timestampMs > DURACAO_MAXIMA_MS) {
      finalizarGravacao()
      return
    }
    const frame = copiarFrame(resultado, timestampMs)
    framesRef.current.push(frame)
    setQuantidadeFrames(framesRef.current.length)
    setMaximoMaos((valor) => Math.max(valor, contarMaos(frame)))
  }, [finalizarGravacao])

  const pararCaptura = useCallback(() => {
    if (estadoRef.current === 'countdown') {
      limparTimers()
      setContagem(0)
      atualizarEstado('idle')
      return
    }
    finalizarGravacao()
  }, [atualizarEstado, finalizarGravacao, limparTimers])

  const reproduzir = useCallback(() => {
    if (!sequenciaRef.current?.frames.length) return
    if (posicaoReplayMs >= sequenciaRef.current.duracaoMs) mostrarFrameReplay(0)
    atualizarEstado('replaying')
    const inicioPlayback = performance.now() - (posicaoReplayMs >= sequenciaRef.current.duracaoMs ? 0 : posicaoReplayMs)
    const avançar = () => {
      if (estadoRef.current !== 'replaying' || !sequenciaRef.current) return
      const posicao = performance.now() - inicioPlayback
      if (posicao >= sequenciaRef.current.duracaoMs) {
        mostrarFrameReplay(sequenciaRef.current.duracaoMs)
        atualizarEstado('recorded')
        replayAnimacaoRef.current = null
        return
      }
      mostrarFrameReplay(posicao)
      replayAnimacaoRef.current = window.requestAnimationFrame(avançar)
    }
    replayAnimacaoRef.current = window.requestAnimationFrame(avançar)
  }, [atualizarEstado, mostrarFrameReplay, posicaoReplayMs])

  const pausar = useCallback(() => {
    if (replayAnimacaoRef.current) window.cancelAnimationFrame(replayAnimacaoRef.current)
    replayAnimacaoRef.current = null
    if (estadoRef.current === 'replaying') atualizarEstado('recorded')
  }, [atualizarEstado])

  const reiniciarReplay = useCallback(() => {
    pausar()
    mostrarFrameReplay(0)
  }, [mostrarFrameReplay, pausar])

  const novaTentativa = useCallback(() => {
    pausar()
    limparTimers()
    framesRef.current = []
    sequenciaRef.current = null
    replayFrameRef.current = { landmarks: [] }
    setSequencia(null)
    setDuracaoMs(0)
    setQuantidadeFrames(0)
    setMaximoMaos(0)
    setPosicaoReplayMs(0)
    setContagem(0)
    atualizarEstado('idle')
  }, [atualizarEstado, limparTimers, pausar])

  const moverReplay = useCallback((tempoMs) => {
    pausar()
    mostrarFrameReplay(Number(tempoMs))
  }, [mostrarFrameReplay, pausar])

  useEffect(() => () => {
    limparTimers()
    if (replayAnimacaoRef.current) window.cancelAnimationFrame(replayAnimacaoRef.current)
  }, [limparTimers])

  return {
    contagem,
    duracaoMs,
    estado,
    iniciarCaptura,
    maximoMaos,
    moverReplay,
    novaTentativa,
    pararCaptura,
    pausar,
    posicaoReplayMs,
    quantidadeFrames,
    registrarFrame,
    reiniciarReplay,
    reproduzir,
    replayFrameRef,
    sequencia,
  }
}
