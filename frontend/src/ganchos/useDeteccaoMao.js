import { useCallback, useEffect, useRef, useState } from 'react'
import { DrawingUtils, FilesetResolver, HandLandmarker } from '@mediapipe/tasks-vision'

const URL_WASM = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1/wasm'
const URL_MODELO = 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task'

function limparCanvas(canvas) {
  const contexto = canvas?.getContext('2d')
  contexto?.clearRect(0, 0, canvas.width, canvas.height)
}

export default function useDeteccaoMao() {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const fluxoRef = useRef(null)
  const detectorRef = useRef(null)
  const animacaoRef = useRef(null)
  const desenhoRef = useRef(null)
  const ultimoTempoVideoRef = useRef(-1)
  const operacaoRef = useRef(0)
  const maoDetectadaRef = useRef(false)
  const resultadoMaoRef = useRef(null)
  const [estadoCamera, setEstadoCamera] = useState('inativa')
  const [maoDetectada, setMaoDetectada] = useState(false)
  const [maosDetectadas, setMaosDetectadas] = useState([])

  const atualizarMaoDetectada = useCallback((detectada) => {
    if (maoDetectadaRef.current !== detectada) {
      maoDetectadaRef.current = detectada
      setMaoDetectada(detectada)
    }
  }, [])

  const atualizarMaosDetectadas = useCallback((resultado) => {
    const maos = resultado.landmarks.map((_, indice) => {
      const nome = resultado.handedness?.[indice]?.[0]?.categoryName
      return nome === 'Left' ? 'Mão esquerda' : nome === 'Right' ? 'Mão direita' : 'Mão detectada'
    })
    setMaosDetectadas((anteriores) => (
      anteriores.length === maos.length && anteriores.every((mao, indice) => mao === maos[indice])
        ? anteriores
        : maos
    ))
  }, [])

  const liberarRecursos = useCallback(() => {
    if (animacaoRef.current) {
      cancelAnimationFrame(animacaoRef.current)
      animacaoRef.current = null
    }

    detectorRef.current?.close()
    detectorRef.current = null
    desenhoRef.current = null
    resultadoMaoRef.current = null
    setMaosDetectadas([])
    ultimoTempoVideoRef.current = -1

    fluxoRef.current?.getTracks().forEach((trilha) => trilha.stop())
    fluxoRef.current = null

    if (videoRef.current) {
      videoRef.current.pause()
      videoRef.current.srcObject = null
    }

    limparCanvas(canvasRef.current)
  }, [])

  const desenharResultado = useCallback((resultado, video) => {
    const canvas = canvasRef.current
    if (!canvas || !video.videoWidth || !video.videoHeight) return

    if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
      canvas.width = video.videoWidth
      canvas.height = video.videoHeight
      desenhoRef.current = null
    }

    const contexto = canvas.getContext('2d')
    if (!contexto) return

    contexto.clearRect(0, 0, canvas.width, canvas.height)
    desenhoRef.current ??= new DrawingUtils(contexto)

    resultado.landmarks.forEach((landmarks) => {
      desenhoRef.current.drawConnectors(landmarks, HandLandmarker.HAND_CONNECTIONS, {
        color: '#99F6E4',
        lineWidth: 1.5,
      })
      desenhoRef.current.drawLandmarks(landmarks, {
        color: '#0D9488',
        fillColor: '#F0FDFA',
        lineWidth: 1,
        radius: 2.5,
      })
    })
  }, [])

  const iniciarCamera = useCallback(async () => {
    const operacaoAtual = operacaoRef.current + 1
    operacaoRef.current = operacaoAtual
    atualizarMaoDetectada(false)
    setEstadoCamera('solicitando')

    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      setEstadoCamera('indisponivel')
      return
    }

    try {
      const fluxo = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: { ideal: 'user' } },
      })

      if (operacaoRef.current !== operacaoAtual) {
        fluxo.getTracks().forEach((trilha) => trilha.stop())
        return
      }

      const video = videoRef.current
      if (!video) {
        fluxo.getTracks().forEach((trilha) => trilha.stop())
        return
      }

      fluxoRef.current = fluxo
      video.srcObject = fluxo
      await video.play()
      setEstadoCamera('ativa')

      const visao = await FilesetResolver.forVisionTasks(URL_WASM)
      const detector = await HandLandmarker.createFromOptions(visao, {
        baseOptions: { modelAssetPath: URL_MODELO },
        numHands: 2,
        runningMode: 'VIDEO',
      })

      if (operacaoRef.current !== operacaoAtual) {
        detector.close()
        return
      }

      detectorRef.current = detector

      const processarQuadro = () => {
        if (operacaoRef.current !== operacaoAtual || !detectorRef.current) return

        if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && video.currentTime !== ultimoTempoVideoRef.current) {
          const resultado = detectorRef.current.detectForVideo(video, performance.now())
          ultimoTempoVideoRef.current = video.currentTime
          resultadoMaoRef.current = resultado
          atualizarMaoDetectada(resultado.landmarks.length > 0)
          atualizarMaosDetectadas(resultado)
          desenharResultado(resultado, video)
        }

        animacaoRef.current = requestAnimationFrame(processarQuadro)
      }

      processarQuadro()
    } catch (erro) {
      if (operacaoRef.current !== operacaoAtual) return

      liberarRecursos()

      if (erro?.name === 'NotAllowedError' || erro?.name === 'SecurityError') {
        setEstadoCamera('permissao_negada')
      } else if (erro?.name === 'NotFoundError' || erro?.name === 'OverconstrainedError') {
        setEstadoCamera('indisponivel')
      } else {
        setEstadoCamera('erro')
      }
    }
  }, [atualizarMaoDetectada, atualizarMaosDetectadas, desenharResultado, liberarRecursos])

  const desativarCamera = useCallback(() => {
    operacaoRef.current += 1
    liberarRecursos()
    atualizarMaoDetectada(false)
    setMaosDetectadas([])
    setEstadoCamera('inativa')
  }, [atualizarMaoDetectada, liberarRecursos])

  useEffect(() => () => {
    operacaoRef.current += 1
    liberarRecursos()
  }, [liberarRecursos])

  return {
    canvasRef,
    desativarCamera,
    estadoCamera,
    iniciarCamera,
    maoDetectada,
    maosDetectadas,
    resultadoMaoRef,
    videoRef,
  }
}
