import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import Cabecalho from '../componentes/Cabecalho'
import conteudo from '../../../dados/conteudo_libras.json'
import './PaginaQuiz.css'

const categorias = conteudo.categorias
const numerais = categorias.find((categoria) => categoria.id === 'numerais')
const perguntas = [
  ...categorias.map((categoria) => ({
    id: categoria.id,
    categoriaId: categoria.id,
    enunciado: 'Qual conteúdo corresponde a esta descrição?',
    referencia: categoria.descricao,
    opcoes: categorias.map((item) => item.titulo),
    resposta: categoria.titulo,
  })),
  ...numerais.itens.filter((item) => item.id !== 'cardinais').map((item) => ({
    id: `numerais-${item.id}`,
    categoriaId: numerais.id,
    enunciado: 'Qual tipo de numeral corresponde a esta descrição?',
    referencia: item.descricao,
    opcoes: numerais.itens.map((opcao) => opcao.titulo),
    resposta: item.titulo,
  })),
]

export default function PaginaQuiz() {
  const [fase, setFase] = useState('inicio')
  const [indice, setIndice] = useState(0)
  const [resposta, setResposta] = useState(null)
  const [acertos, setAcertos] = useState(0)
  const [revisar, setRevisar] = useState([])
  const tituloAtivoRef = useRef(null)
  const pergunta = perguntas[indice]

  useEffect(() => {
    if (fase !== 'inicio') tituloAtivoRef.current?.focus()
  }, [fase, indice])

  function iniciar() {
    setIndice(0)
    setResposta(null)
    setAcertos(0)
    setRevisar([])
    setFase('pergunta')
  }

  function responder(opcao) {
    if (resposta !== null) return
    setResposta(opcao)
    if (opcao === pergunta.resposta) {
      setAcertos((valor) => valor + 1)
    } else {
      setRevisar((itens) => [...new Set([...itens, pergunta.categoriaId])])
    }
  }

  function avancar() {
    if (resposta === null) return
    if (indice === perguntas.length - 1) {
      setFase('resultado')
    } else {
      setIndice((valor) => valor + 1)
      setResposta(null)
    }
  }

  return (
    <main className="pagina pagina-quiz">
      <Cabecalho />
      <header className="pagina-quiz__apresentacao">
        <h1 className="pagina-quiz__titulo">Quiz de Libras</h1>
        <p className="pagina-quiz__descricao">Revise os conceitos das categorias de Aprender. As perguntas não avaliam sua sinalização.</p>
      </header>

      {fase === 'inicio' && (
        <section className="pagina-quiz__cartao" aria-labelledby="titulo-inicio">
          <h2 id="titulo-inicio">Pronto para revisar?</h2>
          <p>São {perguntas.length} perguntas sobre Alfabeto Manual, Saudações e Numerais. Escolha uma resposta por vez.</p>
          <button className="pagina-quiz__acao" type="button" onClick={iniciar}>Iniciar quiz</button>
        </section>
      )}

      {fase === 'pergunta' && (
        <section className="pagina-quiz__cartao" aria-labelledby="titulo-pergunta" key={pergunta.id}>
          <p className="pagina-quiz__progresso">Pergunta {indice + 1} de {perguntas.length}</p>
          <h2 id="titulo-pergunta" ref={tituloAtivoRef} tabIndex={-1}>{pergunta.enunciado}</h2>
          <blockquote className="pagina-quiz__referencia">{pergunta.referencia}</blockquote>
          <div className="pagina-quiz__opcoes" role="group" aria-label="Escolha uma resposta">
            {pergunta.opcoes.map((opcao) => (
              <button
                key={opcao}
                className={`pagina-quiz__opcao ${resposta === opcao ? 'pagina-quiz__opcao--selecionada' : ''}`}
                type="button"
                onClick={() => responder(opcao)}
                disabled={resposta !== null}
                aria-pressed={resposta === opcao}
              >
                {opcao}
              </button>
            ))}
          </div>
          {resposta !== null && (
            <div className="pagina-quiz__feedback" role="status" aria-live="polite">
              <p><strong>{resposta === pergunta.resposta ? 'Correto!' : `Resposta correta: ${pergunta.resposta}.`}</strong></p>
              <Link to={`/aprender/${pergunta.categoriaId}`}>Revisar {categorias.find((categoria) => categoria.id === pergunta.categoriaId).titulo}</Link>
              <button className="pagina-quiz__acao" type="button" onClick={avancar}>
                {indice === perguntas.length - 1 ? 'Ver resultado' : 'Próxima pergunta'}
              </button>
            </div>
          )}
        </section>
      )}

      {fase === 'resultado' && (
        <section className="pagina-quiz__cartao" aria-labelledby="titulo-resultado">
          <h2 id="titulo-resultado" ref={tituloAtivoRef} tabIndex={-1}>Resultado</h2>
          <p className="pagina-quiz__pontuacao">Você acertou {acertos} de {perguntas.length} perguntas.</p>
          {revisar.length > 0 ? (
            <div className="pagina-quiz__revisao">
              <h3>Conteúdos para revisar</h3>
              <ul>
                {revisar.map((id) => {
                  const categoria = categorias.find((item) => item.id === id)
                  return <li key={id}><Link to={`/aprender/${id}`}>{categoria.titulo}</Link></li>
                })}
              </ul>
            </div>
          ) : <p><Link to="/aprender">Revisar conteúdo em Aprender</Link></p>}
          <button className="pagina-quiz__acao" type="button" onClick={iniciar}>Refazer quiz</button>
        </section>
      )}
    </main>
  )
}
