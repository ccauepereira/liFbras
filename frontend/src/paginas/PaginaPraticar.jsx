import { Camera, Eye, Hand, Info, ShieldCheck, Square } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import Cabecalho from '../componentes/Cabecalho'
import VisualizadorMao3D from '../componentes/VisualizadorMao3D'
import useDeteccaoMao from '../ganchos/useDeteccaoMao'
import useGravacaoTemporal from '../ganchos/useGravacaoTemporal'
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

function formatarTempo(tempoMs) {
  return `${(tempoMs / 1000).toFixed(1)} s`
}

export default function PaginaPraticar() {
  const [painelAtivo, setPainelAtivo] = useState('camera')
  const [referenciaId, setReferenciaId] = useState(conteudo.categorias[0].id)
  const gravacao = useGravacaoTemporal()
  const {
    canvasRef,
    desativarCamera,
    estadoCamera,
    fps,
    iniciarCamera,
    maoDetectada,
    maosDetectadas,
    resultadoMaoRef,
    videoRef,
  } = useDeteccaoMao({ onFrame: gravacao.registrarFrame })
  const cameraAtiva = estadoCamera === 'ativa'
  const replayAtivo = gravacao.estado === 'replaying'
  const resultadoVisualizadorRef = replayAtivo ? gravacao.replayFrameRef : resultadoMaoRef
  const visualizadorAtivo = cameraAtiva || replayAtivo
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
          {cameraAtiva && <p className="pagina-praticar__fps">Captura: {fps} fps</p>}
          {cameraAtiva && quantidadeMaos > 0 && <p className="pagina-praticar__handedness">{maosDetectadas.join(' · ')}</p>}
        </div>

        <div className={`pagina-praticar__painel-3d ${painelAtivo !== '3d' ? 'pagina-praticar__painel--oculto' : ''}`}>
          <VisualizadorMao3D resultadoMaoRef={resultadoVisualizadorRef} cameraAtiva={visualizadorAtivo} />
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
        {cameraAtiva && gravacao.estado !== 'countdown' && gravacao.estado !== 'recording' && (
          <button type="button" className="pagina-praticar__botao-gravar" onClick={gravacao.iniciarCaptura}>
            Gravar sinal
          </button>
        )}
        {cameraAtiva && (gravacao.estado === 'countdown' || gravacao.estado === 'recording') && (
          <button type="button" className="pagina-praticar__botao-gravar pagina-praticar__botao-gravar--parar" onClick={gravacao.pararCaptura}>
            Parar gravação
          </button>
        )}
      </div>

      {(gravacao.estado === 'countdown' || gravacao.estado === 'recording') && (
        <section className="pagina-praticar__gravacao-status" role="status" aria-live="polite">
          {gravacao.estado === 'countdown' ? (
            <p className="pagina-praticar__contagem">Começando em {gravacao.contagem}…</p>
          ) : (
            <p><span className="pagina-praticar__ponto-gravacao" aria-hidden="true">●</span> Gravando — {formatarTempo(gravacao.duracaoMs)} — {gravacao.quantidadeFrames} frames</p>
          )}
        </section>
      )}

      {gravacao.sequencia && gravacao.estado !== 'countdown' && gravacao.estado !== 'recording' && (
        <section className="pagina-praticar__replay" aria-labelledby="titulo-replay">
          <div className="pagina-praticar__replay-cabecalho">
            <div>
              <p className="pagina-praticar__etiqueta">CAPTURA EM MEMÓRIA</p>
              <h2 id="titulo-replay">Replay do sinal</h2>
            </div>
            <button type="button" className="pagina-praticar__botao-novo" onClick={gravacao.novaTentativa}>Nova tentativa</button>
          </div>
          <dl className="pagina-praticar__resumo-gravacao">
            <div><dt>Duração</dt><dd>{formatarTempo(gravacao.duracaoMs)}</dd></div>
            <div><dt>Frames</dt><dd>{gravacao.quantidadeFrames}</dd></div>
            <div><dt>Máximo de mãos</dt><dd>{gravacao.maximoMaos}</dd></div>
          </dl>
          <div className="pagina-praticar__controles-replay" aria-label="Controles do replay">
            {replayAtivo ? (
              <button type="button" onClick={gravacao.pausar}>Pausar</button>
            ) : (
              <button type="button" onClick={gravacao.reproduzir}>Reproduzir</button>
            )}
            <button type="button" onClick={gravacao.reiniciarReplay}>Reiniciar</button>
          </div>
          <label className="pagina-praticar__timeline">
            <span>Posição do replay: {formatarTempo(gravacao.posicaoReplayMs)}</span>
            <input
              type="range"
              min="0"
              max={gravacao.duracaoMs || 0}
              step="1"
              value={Math.min(gravacao.posicaoReplayMs, gravacao.duracaoMs)}
              onChange={(evento) => gravacao.moverReplay(evento.target.value)}
              aria-label="Posição temporal do replay"
              disabled={!gravacao.duracaoMs}
            />
          </label>
        </section>
      )}

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
