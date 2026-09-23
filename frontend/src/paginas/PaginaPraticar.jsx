import { Camera, ShieldCheck, Square } from 'lucide-react'
import Cabecalho from '../componentes/Cabecalho'
import useDeteccaoMao from '../ganchos/useDeteccaoMao'
import './PaginaPraticar.css'

const passosPratica = [
  { numero: 1, texto: 'Ative a câmera quando estiver pronto' },
  { numero: 2, texto: 'Posicione uma mão no centro da imagem' },
  { numero: 3, texto: 'Confira os pontos sobre a sua mão' },
]

const mensagensCamera = {
  inativa: 'Pronto para ativar a câmera.',
  solicitando: 'Solicitando acesso à câmera.',
  permissao_negada: 'O acesso à câmera foi negado. Ajuste a permissão do navegador e tente novamente.',
  indisponivel: 'A câmera não está disponível. Use um navegador compatível em localhost ou HTTPS.',
  erro: 'Não foi possível iniciar a câmera. Tente novamente.',
}

export default function PaginaPraticar() {
  const {
    canvasRef,
    desativarCamera,
    estadoCamera,
    iniciarCamera,
    maoDetectada,
    videoRef,
  } = useDeteccaoMao()
  const cameraAtiva = estadoCamera === 'ativa'
  const mensagemStatus = cameraAtiva
    ? maoDetectada
      ? 'Mão detectada.'
      : 'Câmera ativa. Posicione uma mão na área da câmera.'
    : mensagensCamera[estadoCamera]

  return (
    <main className="pagina pagina-praticar">
      <Cabecalho />

      <section className="pagina-praticar__apresentacao">
        <h1 className="pagina-praticar__titulo">Pratique os sinais</h1>
        <p className="pagina-praticar__descricao">
          Ative a câmera para conferir o enquadramento da sua mão.
        </p>
      </section>

      <section className="pagina-praticar__palco-container" aria-label="Visualizador da câmera">
        <div className={`pagina-praticar__palco ${cameraAtiva ? 'pagina-praticar__palco--ativo' : ''}`}>
          <video
            ref={videoRef}
            className="pagina-praticar__video"
            autoPlay
            muted
            playsInline
            aria-hidden="true"
          />
          <canvas ref={canvasRef} className="pagina-praticar__marcadores" aria-hidden="true" />

          {!cameraAtiva && (
            <svg className="pagina-praticar__silhueta" viewBox="0 0 200 200" fill="none" aria-hidden="true">
              <circle cx="100" cy="72" r="26" fill="#334155" opacity="0.8" />
              <path d="M56 160 C56 122, 75 110, 100 110 C125 110, 144 122, 144 160" fill="#334155" opacity="0.8" />
              <g transform="translate(132, 70)">
                <circle cx="14" cy="18" r="10" fill="#0D9488" opacity="0.75" />
                <path d="M8 14 L8 4 C8 2.5, 10 2.5, 10 4 L10 14" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" />
                <path d="M12 14 L12 2 C12 0.5, 14 0.5, 14 2 L14 14" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" />
                <path d="M16 14 L16 3 C16 1.5, 18 1.5, 18 3 L18 14" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" />
                <path d="M20 14 L20 6 C20 4.5, 22 4.5, 22 6 L22 14" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" />
              </g>
            </svg>
          )}

          <div className="palco-guia palco-guia--superior-esquerdo" aria-hidden="true" />
          <div className="palco-guia palco-guia--superior-direito" aria-hidden="true" />
          <div className="palco-guia palco-guia--inferior-esquerdo" aria-hidden="true" />
          <div className="palco-guia palco-guia--inferior-direito" aria-hidden="true" />

          {!cameraAtiva && (
            <div className="pagina-praticar__pilula-posicao">
              <span>Posicione-se no centro</span>
            </div>
          )}
        </div>

        <p className="pagina-praticar__aviso-status" aria-live="polite" role="status">
          {mensagemStatus}
        </p>
      </section>

      <section className="pagina-praticar__passos-card" aria-label="Instruções de prática">
        <ol className="pagina-praticar__lista-passos">
          {passosPratica.map(({ numero, texto }) => (
            <li key={numero} className="pagina-praticar__passo-item">
              <span className="pagina-praticar__passo-numero" aria-hidden="true">{numero}</span>
              <span className="pagina-praticar__passo-texto">{texto}</span>
            </li>
          ))}
        </ol>
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

      <section className="pagina-praticar__privacidade" aria-label="Privacidade da câmera">
        <div className="pagina-praticar__privacidade-card">
          <ShieldCheck size={20} className="pagina-praticar__privacidade-icone" aria-hidden="true" />
          <p className="pagina-praticar__privacidade-texto">
            A câmera é processada no seu dispositivo. Nenhuma imagem ou vídeo é enviado.
          </p>
        </div>
      </section>
    </main>
  )
}
