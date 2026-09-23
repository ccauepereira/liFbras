import { ArrowLeft, ChevronRight } from 'lucide-react'
import { Link, Navigate, useParams } from 'react-router-dom'
import Cabecalho from '../componentes/Cabecalho'
import conteudo from '../../../dados/conteudo_libras.json'
import './PaginaAprender.css'

const categorias = conteudo.categorias

function CartaoCategoria({ categoria }) {
  const imagem = categoria.imagens[0]

  return (
    <Link
      className="cartao-categoria"
      to={`/aprender/${categoria.id}`}
      aria-label={`Abrir categoria ${categoria.titulo}`}
    >
      <div className="cartao-categoria__visual">
        <img src={imagem.arquivo} alt={imagem.alt} loading="lazy" />
      </div>
      <div className="cartao-categoria__rodape">
        <div className="cartao-categoria__textos">
          <h2 className="cartao-categoria__titulo">{categoria.titulo}</h2>
          <span className="cartao-categoria__contagem">{categoria.resumo}</span>
        </div>
        <ChevronRight className="cartao-categoria__seta" size={18} aria-hidden="true" />
      </div>
    </Link>
  )
}

function ListaFontes({ fontes }) {
  return (
    <p className="pagina-aprender__fontes">
      Fonte: {fontes.map((fonte, indice) => (
        <span key={`${fonte.documento}-${fonte.pagina}`}>
          {indice > 0 ? '; ' : ''}{fonte.documento}, p. {fonte.pagina}
        </span>
      ))}
    </p>
  )
}

function PaginaCategoria({ categoria }) {
  return (
    <main className="pagina pagina-aprender pagina-categoria">
      <Cabecalho />

      <Link className="pagina-categoria__voltar" to="/aprender">
        <ArrowLeft size={18} aria-hidden="true" />
        <span>Voltar para Aprender</span>
      </Link>

      <header className="pagina-categoria__cabecalho">
        <span className="pagina-categoria__etiqueta">{categoria.categoria}</span>
        <h1 className="pagina-aprender__titulo">{categoria.titulo}</h1>
        <p className="pagina-aprender__descricao">{categoria.descricao}</p>
      </header>

      <section className="pagina-categoria__visuais" aria-label={`Referências visuais de ${categoria.titulo}`}>
        {categoria.imagens.map((imagem) => (
          <figure className="pagina-categoria__figura" key={imagem.arquivo}>
            <img src={imagem.arquivo} alt={imagem.alt} />
            <figcaption>Referência visual — p. {imagem.fonte.pagina}</figcaption>
          </figure>
        ))}
      </section>

      <section className="pagina-categoria__notas" aria-labelledby="titulo-notas">
        <h2 id="titulo-notas">Pontos para observar</h2>
        <ul>
          {categoria.notas.map((nota) => <li key={nota}>{nota}</li>)}
        </ul>
      </section>

      <section className="pagina-categoria__itens" aria-labelledby="titulo-itens">
        <h2 id="titulo-itens">Conteúdo da categoria</h2>
        <ul>
          {categoria.itens.map((item) => (
            <li key={item.id}>
              <strong>{item.titulo}</strong>
              {item.descricao && <span>{item.descricao}</span>}
            </li>
          ))}
        </ul>
      </section>

      <ListaFontes fontes={categoria.fontes} />
    </main>
  )
}

export default function PaginaAprender() {
  const { categoriaId } = useParams()

  if (categoriaId) {
    const categoria = categorias.find((item) => item.id === categoriaId)
    if (!categoria) return <Navigate to="/aprender" replace />
    return <PaginaCategoria categoria={categoria} />
  }

  return (
    <main className="pagina pagina-aprender">
      <Cabecalho />

      <section className="pagina-aprender__apresentacao">
        <h1 className="pagina-aprender__titulo">
          Aprenda Libras<br />
          no seu ritmo
        </h1>
        <p className="pagina-aprender__descricao">
          Explore referências visuais e notas curtas a partir das apostilas do curso.
        </p>
      </section>

      <section className="pagina-aprender__secao-categorias" aria-labelledby="titulo-categorias">
        <h2 id="titulo-categorias" className="sr-only">Categorias de estudo</h2>
        <div className="pagina-aprender__grade">
          {categorias.map((categoria) => <CartaoCategoria key={categoria.id} categoria={categoria} />)}
        </div>
      </section>
    </main>
  )
}
