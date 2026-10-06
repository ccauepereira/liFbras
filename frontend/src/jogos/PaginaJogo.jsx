import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import Cabecalho from '../componentes/Cabecalho'
import useDeteccaoMao from '../ganchos/useDeteccaoMao'
import { colisaoCircular, gerarAlvoSeguro, mapearPontaIndicador } from './logicaJogo'
import './PaginaJogo.css'

const DURACAO_PARTIDA_MS = 30_000
const RAIO_CURSOR = 12

function novaPosicao(area, evitar = null) {
  const largura = area?.clientWidth || 360
  const altura = area?.clientHeight || 420
  const raio = Math.min(40, Math.max(28, Math.min(largura, altura) * 0.12))
  return { ...gerarAlvoSeguro(largura, altura, raio, Math.random, evitar), raio }
}

export default function PaginaJogo() {
  const areaRef = useRef(null)
  const cursorRef = useRef(null)
  const alvoRef = useRef(null)
  const posicaoSuaveRef = useRef(null)
  const proximoAcertoRef = useRef(0)
  const prazoRef = useRef(0)
  const inicioSolicitadoRef = useRef(false)
  const [fase, setFase] = useState('inicio')
  const [pontuacao, setPontuacao] = useState(0)
  const [segundos, setSegundos] = useState(30)
  const [alvo, setAlvo] = useState(null)
  const [solicitandoInicio, setSolicitandoInicio] = useState(false)
  const [mensagemCamera, setMensagemCamera] = useState('A câmera será ativada ao iniciar o jogo.')
  const { estadoCamera, iniciarCamera, maoDetectada, resultadoMaoRef, videoRef } = useDeteccaoMao()

  const iniciarPartida = useCallback(() => {
    const proximo = novaPosicao(areaRef.current)
    alvoRef.current = proximo
    posicaoSuaveRef.current = null
    proximoAcertoRef.current = 0
    setAlvo(proximo)
    setPontuacao(0)
    setSegundos(30)
    prazoRef.current = performance.now() + DURACAO_PARTIDA_MS
    setFase('jogando')
  }, [])

  useEffect(() => {
    if (solicitandoInicio && estadoCamera === 'ativa') {
      inicioSolicitadoRef.current = false
      setSolicitandoInicio(false)
      setMensagemCamera('Câmera pronta')
      iniciarPartida()
    } else if (solicitandoInicio && ['erro', 'permissao_negada', 'indisponivel'].includes(estadoCamera)) {
      inicioSolicitadoRef.current = false
      setSolicitandoInicio(false)
      setMensagemCamera('Não foi possível acessar a câmera. Verifique a permissão do navegador e tente novamente.')
    } else if (estadoCamera === 'ativa') {
      setMensagemCamera('Câmera pronta')
    } else if (estadoCamera === 'solicitando') {
      setMensagemCamera('Preparando câmera…')
    }
  }, [estadoCamera, iniciarPartida, solicitandoInicio])

  useEffect(() => {
    if (fase !== 'jogando') return undefined
    const atualizarTempo = () => {
      const restante = Math.max(0, Math.ceil((prazoRef.current - performance.now()) / 1000))
      setSegundos((valor) => valor === restante ? valor : restante)
      if (restante === 0) setFase('fim')
    }
    atualizarTempo()
    const timer = window.setInterval(atualizarTempo, 100)
    return () => window.clearInterval(timer)
  }, [fase])

  useEffect(() => {
    if (fase !== 'jogando' || estadoCamera !== 'ativa') return undefined
    let quadro
    const atualizarCursorEColisao = () => {
      const area = areaRef.current
      const cursor = cursorRef.current
      const video = videoRef.current
      const largura = area?.clientWidth ?? 0
      const altura = area?.clientHeight ?? 0
      const maos = resultadoMaoRef.current?.landmarks ?? []
      const mao = maos.find((pontos) => pontos?.[8] && Number.isFinite(pontos[8].x) && Number.isFinite(pontos[8].y))
      const ponta = mao?.[8]

      if (ponta && largura && altura && video?.videoWidth && video?.videoHeight) {
        const mapeada = mapearPontaIndicador(ponta, video.videoWidth, video.videoHeight, largura, altura)
        const anterior = posicaoSuaveRef.current
        const suavizada = anterior ? { x: anterior.x * 0.65 + mapeada.x * 0.35, y: anterior.y * 0.65 + mapeada.y * 0.35 } : mapeada
        posicaoSuaveRef.current = suavizada
        if (cursor) {
          cursor.style.display = 'block'
          cursor.style.left = `${suavizada.x * 100}%`
          cursor.style.top = `${suavizada.y * 100}%`
        }

        const atual = alvoRef.current
        const agora = performance.now()
        if (atual && agora >= proximoAcertoRef.current && colisaoCircular(suavizada, atual, largura, altura, atual.raio, RAIO_CURSOR)) {
          const proximo = novaPosicao(area, atual)
          alvoRef.current = proximo
          proximoAcertoRef.current = agora + 200
          setAlvo(proximo)
          setPontuacao((valor) => valor + 1)
        }
      } else if (cursor) {
        cursor.style.display = 'none'
      }

      quadro = window.requestAnimationFrame(atualizarCursorEColisao)
    }
    quadro = window.requestAnimationFrame(atualizarCursorEColisao)
    return () => window.cancelAnimationFrame(quadro)
  }, [fase, estadoCamera, resultadoMaoRef, videoRef])

  const pedirInicio = () => {
    if (inicioSolicitadoRef.current || solicitandoInicio) return
    inicioSolicitadoRef.current = true
    setSolicitandoInicio(true)
    if (estadoCamera === 'ativa') return
    iniciarCamera()
  }

  const jogarNovamente = () => {
    setFase('inicio')
    setAlvo(null)
    alvoRef.current = null
    posicaoSuaveRef.current = null
    setSegundos(30)
    setMensagemCamera(estadoCamera === 'ativa' ? 'Câmera pronta' : 'A câmera será ativada ao iniciar o jogo.')
  }

  const alvoVisual = fase === 'jogando' ? alvo : null
  const cameraPreparando = solicitandoInicio || estadoCamera === 'solicitando'

  return <main className="pagina-jogo">
    <Cabecalho />
    <div className="jogo__topo">
      <Link className="jogo__voltar" to="/praticar">Voltar</Link>
      <p className="jogo__rotulo">LABORATÓRIO DE INTERAÇÃO GESTUAL</p>
    </div>
    {fase === 'jogando' && <section className="jogo__hud" aria-label="Placar"><h1>Mão Ninja</h1><p>Pontos: <strong>{pontuacao}</strong></p><p>Tempo: <strong>{segundos}</strong></p></section>}
    {fase === 'jogando' && !maoDetectada && <p className="jogo__sem-mao" role="status">Mostre sua mão para a câmera</p>}

    <section className={`jogo__area ${fase === 'jogando' ? 'jogo__area--jogando' : ''}`} ref={areaRef} aria-label="Área do jogo">
      <video ref={videoRef} className="jogo__video" autoPlay muted playsInline aria-hidden="true" />
      <div className="jogo__sombra" aria-hidden="true" />
      {alvoVisual && <div key={`${pontuacao}-${alvoVisual.x}-${alvoVisual.y}`} className="jogo__alvo" style={{ left: `${alvoVisual.x * 100}%`, top: `${alvoVisual.y * 100}%`, '--alvo-diametro': `${alvoVisual.raio * 2}px` }} aria-hidden="true" />}
      <div ref={cursorRef} className="jogo__cursor" aria-hidden="true" />
      {fase === 'inicio' && <div className="jogo__cartao"><p className="jogo__marca">GAME LAB 01 · EXPERIMENTAL</p><h1>Mão Ninja</h1><p>Use a ponta do dedo indicador para tocar os alvos.</p><p className="jogo__camera-status" role="status">{mensagemCamera}</p><p className="jogo__lembrete-mao">Mostre sua mão para a câmera.</p><button type="button" onClick={pedirInicio} disabled={cameraPreparando}>{cameraPreparando ? 'Preparando câmera…' : ['erro', 'permissao_negada', 'indisponivel'].includes(estadoCamera) ? 'Tentar novamente' : 'Iniciar'}</button><small>Interação gestual local. Nenhum vídeo ou landmark é armazenado.</small></div>}
      {fase === 'jogando' && pontuacao > 0 && <span key={pontuacao} className="jogo__acerto" aria-hidden="true">+1</span>}
      {fase === 'fim' && <div className="jogo__cartao"><p className="jogo__marca">PARTIDA ENCERRADA</p><h1>Fim de jogo</h1><p className="jogo__resultado">Sua pontuação: <strong>{pontuacao}</strong></p><p>Tente superar sua pontuação.</p><button type="button" onClick={jogarNovamente}>Jogar novamente</button></div>}
    </section>
    {fase !== 'jogando' && <p className="jogo__nota">Demonstração de interação gestual por visão computacional. Não reconhece sinais de Libras.</p>}
  </main>
}
