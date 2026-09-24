import { Camera, Eye, Hand, Info, ShieldCheck, Square } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import Cabecalho from '../componentes/Cabecalho'
import VisualizadorMao3D from '../componentes/VisualizadorMao3D'
import useDeteccaoMao from '../ganchos/useDeteccaoMao'
import conteudo from '../../../dados/conteudo_libras.json'
import './PaginaPraticar.css'

const passosPratica = [
  { numero: 1, texto: 'Escolha uma referência de estudo' },
  { numero: 2, texto: 'Ative a câmera e posicione as mãos' },
  { numero: 3, texto: 'Observe como os pontos acompanham o movimento' },
]

const mensagensCamera = {
  inativa: 'Pronto para ativar a câmera.',
  solicitando: 'Solicitando acesso à câmera.',
  permissao_negada: 'O acesso à câmera foi negado. Ajuste a permissão do navegador e tente novamente.',
  indisponivel: 'A câmera não está disponível. Use um navegador compatível em localhost ou HTTPS.',
  erro: 'Não foi possível iniciar a câmera. Tente novamente.',
}

export default function PaginaPraticar() {
  const [painelAtivo, setPainelAtivo] = useState('camera')
  const [referenciaId, setReferenciaId] = useState(conteudo.categorias[0].id)
  const {
    canvasRef,
    desativarCamera,
    estadoCamera,
    iniciarCamera,
    maoDetectada,
    maosDetectadas,
    resultadoMaoRef,
    videoRef,
  } = useDeteccaoMao()
  const cameraAtiva = estadoCamera === 'ativa'
  const referencia = conteudo.categorias.find((categoria) => categoria.id === referenciaId) ?? conteudo.categorias[0]
  const quantidadeMaos = maosDetectadas.length
  const mensagemStatus = cameraAtiva
    ? quantidadeMaos > 1
      ? `${quantidadeMaos} mãos detectadas. Veja como os pontos acompanham seu movimento.`
      : maoDetectada
        ? 'Mão detectada. Observe os pontos sobre a sua mão.'
        : 'Posicione sua mão dentro da câmera.'
    : mensagensCamera[estadoCamera]

  return (
    <main className="pagina pagina-praticar">
      <Cabecalho />

      <section className="pagina-praticar__apresentacao">
        <p className="pagina-praticar__etiqueta">PRACTICE LAB</p>
        <h1 className="pagina-praticar__titulo">Pratique com referências visuais</h1>
        <p className="pagina-praticar__descricao">
          Use a câmera para observar os pontos que acompanham suas mãos. Esta área não avalia nem traduz sinais.
        </p>
      </section>

      <section className="pagina-praticar__seletor" aria-label="Modo de visualização">
        <button type="button" className={`pagina-praticar__aba-visual ${painelAtivo === 'camera' ? 'pagina-praticar__aba-visual--ativa' : ''}`} onClick={() => setPainelAtivo('camera')} aria-pressed={painelAtivo === 'camera'}>
          <Camera size={18} aria-hidden="true" />
          Câmera
        </button>
        <button type="button" className={`pagina-praticar__aba-visual ${painelAtivo === '3d' ? 'pagina-praticar__aba-visual--ativa' : ''}`} onClick={() => setPainelAtivo('3d')} aria-pressed={painelAtivo === '3d'}>
          <Eye size={18} aria-hidden="true" />
          Pontos em 3D
        </button>
      </section>

      <section className="pagina-praticar__visualizadores" aria-label="Visualização da prática">
        <div className={`pagina-praticar__painel-camera ${painelAtivo !== 'camera' ? 'pagina-praticar__painel--oculto' : ''}`}>
          <div className={`pagina-praticar__palco ${cameraAtiva ? 'pagina-praticar__palco--ativo' : ''}`}>
            <video ref={videoRef} className="pagina-praticar__video" autoPlay muted playsInline aria-hidden="true" />
            <canvas ref={canvasRef} className="pagina-praticar__marcadores" aria-hidden="true" />

            {!cameraAtiva && (
              <svg className="pagina-praticar__silhueta" viewBox="0 0 200 200" fill="none" aria-hidden="true">
                <circle cx="100" cy="72" r="26" fill="#334155" opacity="0.8" />
                <path d="M56 160 C56 122, 75 110, 100 110 C125 110, 144 122, 144 160" fill="#334155" opacity="0.8" />
                <g transform="translate(132, 70)">
                  <circle cx="14" cy="18" r="10" fill="#0D9488" opacity="0.75" />
                  <path d="M8 14 L8 4 C8 2.5, 10 2.5, 10 4 L10 14 M12 14 L12 2 C12 0.5, 14 0.5, 14 2 L14 14 M16 14 L16 3 C16 1.5, 18 1.5, 18 3 L18 14 M20 14 L20 6 C20 4.5, 22 4.5, 22 6 L22 14" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" />
                </g>
              </svg>
            )}

            <div className="palco-guia palco-guia--superior-esquerdo" aria-hidden="true" />
            <div className="palco-guia palco-guia--superior-direito" aria-hidden="true" />
            <div className="palco-guia palco-guia--inferior-esquerdo" aria-hidden="true" />
            <div className="palco-guia palco-guia--inferior-direito" aria-hidden="true" />
            {!cameraAtiva && <div className="pagina-praticar__pilula-posicao">Posicione-se no centro</div>}
          </div>

          <div className="pagina-praticar__status" role="status" aria-live="polite">
            <Hand size={18} aria-hidden="true" />
            <span>{mensagemStatus}</span>
          </div>
          {cameraAtiva && quantidadeMaos > 0 && <p className="pagina-praticar__handedness">{maosDetectadas.join(' · ')}</p>}
        </div>

        <div className={`pagina-praticar__painel-3d ${painelAtivo !== '3d' ? 'pagina-praticar__painel--oculto' : ''}`}>
          <VisualizadorMao3D resultadoMaoRef={resultadoMaoRef} cameraAtiva={cameraAtiva} />
        </div>
      </section>

      <section className="pagina-praticar__privacidade" aria-label="Privacidade da câmera">
        <div className="pagina-praticar__privacidade-card">
          <ShieldCheck size={20} className="pagina-praticar__privacidade-icone" aria-hidden="true" />
          <p className="pagina-praticar__privacidade-texto">
            A câmera é processada no seu dispositivo. O LiFbras não envia imagens, vídeos ou pontos das mãos. Ao ativar a câmera, o MediaPipe envia métricas de uso e desempenho ao Google. <a href="https://github.com/google-ai-edge/mediapipe#privacy-notice" target="_blank" rel="noreferrer">Veja o aviso de privacidade do MediaPipe</a>.
          </p>
        </div>
      </section>

      <div className="pagina-praticar__acao-container">
        {cameraAtiva ? (
          <button type="button" className="pagina-praticar__botao-principal pagina-praticar__botao-principal--secundario" onClick={desativarCamera}>
            <Square size={17} fill="currentColor" aria-hidden="true" />
            <span>Desativar câmera</span>
          </button>
        ) : (
          <button type="button" className="pagina-praticar__botao-principal" onClick={iniciarCamera} disabled={estadoCamera === 'solicitando'}>
            <Camera size={19} aria-hidden="true" />
            <span>{estadoCamera === 'solicitando' ? 'Ativando câmera' : 'Ativar câmera'}</span>
          </button>
        )}
      </div>

      <section className="pagina-praticar__referencia" aria-labelledby="titulo-referencia">
        <div className="pagina-praticar__referencia-cabecalho">
          <div>
            <p className="pagina-praticar__etiqueta">REFERÊNCIA DE ESTUDO</p>
            <h2 id="titulo-referencia">Escolha o conteúdo para praticar</h2>
          </div>
          <select value={referenciaId} onChange={(evento) => setReferenciaId(evento.target.value)} aria-label="Conteúdo de referência">
            {conteudo.categorias.map((categoria) => <option key={categoria.id} value={categoria.id}>{categoria.titulo}</option>)}
          </select>
        </div>
        <details className="pagina-praticar__referencia-detalhe">
          <summary>Ver referência visual de {referencia.titulo}</summary>
          <img src={referencia.imagens[0].arquivo} alt={referencia.imagens[0].alt} />
          <p>{referencia.descricao}</p>
        </details>
        <Link className="pagina-praticar__aprender" to={`/aprender/${referencia.id}`}>Estudar {referencia.titulo} em Aprender</Link>
      </section>

      <section className="pagina-praticar__passos-card" aria-label="Como usar o laboratório de prática">
        <ol className="pagina-praticar__lista-passos">
          {passosPratica.map(({ numero, texto }) => (
            <li key={numero} className="pagina-praticar__passo-item">
              <span className="pagina-praticar__passo-numero" aria-hidden="true">{numero}</span>
              <span className="pagina-praticar__passo-texto">{texto}</span>
            </li>
          ))}
        </ol>
      </section>

      <details className="pagina-praticar__explicacao">
        <summary><Info size={18} aria-hidden="true" /> O que o computador vê?</summary>
        <p>O MediaPipe acompanha 21 pontos em cada mão. x e y localizam cada ponto na imagem; z representa profundidade relativa. A imagem da câmera permanece no seu dispositivo.</p>
      </details>

      <details className="pagina-praticar__pesquisa">
        <summary>Sobre o reconhecimento automático</summary>
        <p>O reconhecimento automático ainda está em pesquisa no LiFbras. Nos testes atuais, o modelo não apresentou estabilidade suficiente entre pessoas diferentes, por isso ele não é usado para avaliar seus sinais.</p>
      </details>
    </main>
  )
}
