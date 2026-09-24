import { RotateCcw } from 'lucide-react'
import { useEffect, useRef } from 'react'
import './VisualizadorMao3D.css'

const conexoes = [
  [0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [5, 6], [6, 7], [7, 8],
  [5, 9], [9, 10], [10, 11], [11, 12], [9, 13], [13, 14], [14, 15], [15, 16],
  [13, 17], [17, 18], [18, 19], [19, 20], [0, 17],
]

function projetar(ponto, rotacao) {
  const cosY = Math.cos(rotacao.y)
  const sinY = Math.sin(rotacao.y)
  const cosX = Math.cos(rotacao.x)
  const sinX = Math.sin(rotacao.x)
  const x = ponto.x * cosY - ponto.z * sinY
  const z = ponto.x * sinY + ponto.z * cosY
  return { x, y: ponto.y * cosX - z * sinX, z: ponto.y * sinX + z * cosX }
}

function desenhar(canvas, landmarks, rotacao) {
  const contexto = canvas.getContext('2d')
  const largura = canvas.width
  const altura = canvas.height
  contexto.clearRect(0, 0, largura, altura)
  contexto.fillStyle = '#0F172A'
  contexto.fillRect(0, 0, largura, altura)

  if (!landmarks?.length) return

  const centro = landmarks.reduce((total, ponto) => ({ x: total.x + ponto.x, y: total.y + ponto.y, z: total.z + ponto.z }), { x: 0, y: 0, z: 0 })
  centro.x /= landmarks.length
  centro.y /= landmarks.length
  centro.z /= landmarks.length
  const escala = Math.max(...landmarks.map((ponto) => Math.hypot(ponto.x - centro.x, ponto.y - centro.y, ponto.z - centro.z)), 0.01)
  const pontos = landmarks.map((ponto) => projetar({ x: (ponto.x - centro.x) / escala, y: (ponto.y - centro.y) / escala, z: (ponto.z - centro.z) / escala }, rotacao))
  const projetados = pontos.map((ponto) => ({ x: largura / 2 + ponto.x * largura * 0.28, y: altura / 2 + ponto.y * altura * 0.28, z: ponto.z }))

  contexto.lineCap = 'round'
  contexto.lineWidth = Math.max(2, largura * 0.012)
  conexoes.forEach(([inicio, fim]) => {
    const primeiro = projetados[inicio]
    const segundo = projetados[fim]
    contexto.strokeStyle = primeiro.z + segundo.z > 0 ? '#5EEAD4' : '#2DD4BF'
    contexto.beginPath()
    contexto.moveTo(primeiro.x, primeiro.y)
    contexto.lineTo(segundo.x, segundo.y)
    contexto.stroke()
  })

  projetados
    .map((ponto, indice) => ({ ...ponto, indice }))
    .sort((a, b) => a.z - b.z)
    .forEach((ponto) => {
      contexto.fillStyle = ponto.indice === 0 ? '#F8FAFC' : '#99F6E4'
      contexto.beginPath()
      contexto.arc(ponto.x, ponto.y, ponto.indice === 0 ? 5 : 3.5, 0, Math.PI * 2)
      contexto.fill()
    })
}

export default function VisualizadorMao3D({ resultadoMaoRef, cameraAtiva }) {
  const canvasRef = useRef(null)
  const rotacaoRef = useRef({ x: -0.2, y: 0.45 })
  const ponteiroRef = useRef(null)

  useEffect(() => {
    let quadro
    const canvas = canvasRef.current
    if (!cameraAtiva) {
      if (canvas) desenhar(canvas, null, rotacaoRef.current)
      return undefined
    }
    const atualizar = () => {
      const elemento = canvasRef.current
      if (elemento) {
        const proporcao = window.devicePixelRatio || 1
        const largura = Math.round(elemento.clientWidth * proporcao)
        const altura = Math.round(elemento.clientHeight * proporcao)
        if (elemento.width !== largura || elemento.height !== altura) {
          elemento.width = largura
          elemento.height = altura
        }
        desenhar(elemento, resultadoMaoRef.current?.landmarks?.[0], rotacaoRef.current)
      }
      quadro = requestAnimationFrame(atualizar)
    }
    atualizar()
    return () => cancelAnimationFrame(quadro)
  }, [cameraAtiva, resultadoMaoRef])

  const iniciarArraste = (evento) => {
    ponteiroRef.current = { id: evento.pointerId, x: evento.clientX, y: evento.clientY }
    evento.currentTarget.setPointerCapture(evento.pointerId)
  }

  const moverArraste = (evento) => {
    const ponteiro = ponteiroRef.current
    if (!ponteiro || ponteiro.id !== evento.pointerId) return
    rotacaoRef.current.y += (evento.clientX - ponteiro.x) * 0.012
    rotacaoRef.current.x += (evento.clientY - ponteiro.y) * 0.012
    ponteiroRef.current = { ...ponteiro, x: evento.clientX, y: evento.clientY }
  }

  const finalizarArraste = () => {
    ponteiroRef.current = null
  }

  return (
    <section className="visualizador-3d" aria-labelledby="titulo-3d">
      <div className="visualizador-3d__cabecalho">
        <div>
          <p className="visualizador-3d__etiqueta">VISUALIZAÇÃO</p>
          <h2 id="titulo-3d">Mão em 3D</h2>
        </div>
        <button type="button" className="visualizador-3d__reset" onClick={() => { rotacaoRef.current = { x: -0.2, y: 0.45 } }}>
          <RotateCcw size={17} aria-hidden="true" />
          <span>Redefinir</span>
        </button>
      </div>
      <canvas
        ref={canvasRef}
        className="visualizador-3d__canvas"
        onPointerDown={iniciarArraste}
        onPointerMove={moverArraste}
        onPointerUp={finalizarArraste}
        onPointerCancel={finalizarArraste}
        aria-label={cameraAtiva ? 'Visualização tridimensional da primeira mão detectada. Arraste para girar.' : 'Visualização tridimensional disponível após ativar a câmera.'}
      />
      <p className="visualizador-3d__ajuda">
        {cameraAtiva ? 'Arraste para girar. Os pontos mostram profundidade relativa, não medidas físicas.' : 'Ative a câmera para ver os pontos em movimento.'}
      </p>
    </section>
  )
}
