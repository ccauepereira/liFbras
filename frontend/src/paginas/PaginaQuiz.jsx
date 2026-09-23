import { BookOpen, Languages, Zap, ChevronRight, Sparkles } from 'lucide-react'
import Cabecalho from '../componentes/Cabecalho'
import './PaginaQuiz.css'

const modalidadesQuiz = [
  {
    id: 'reconhecer',
    titulo: 'Reconhecer sinais',
    descricao: 'Veja o sinal e escolha o significado correto.',
    icone: BookOpen,
    corBadge: '#10B981',
  },
  {
    id: 'traducao',
    titulo: 'Tradução',
    descricao: 'Veja a palavra e escolha o sinal correto.',
    icone: Languages,
    corBadge: '#8B5CF6',
  },
  {
    id: 'desafio',
    titulo: 'Desafio',
    descricao: 'Teste seus conhecimentos com sinais aleatórios.',
    icone: Zap,
    corBadge: '#F59E0B',
  },
]

export default function PaginaQuiz() {
  return (
    <main className="pagina pagina-quiz">
      <Cabecalho />

      <section className="pagina-quiz__apresentacao">
        <h1 className="pagina-quiz__titulo">Teste seus conhecimentos</h1>
        <p className="pagina-quiz__descricao">
          Responda aos quizzes e fixe o que você aprendeu de forma interativa.
        </p>
      </section>

      {/* Lista de modalidades de exercícios estruturais */}
      <section className="pagina-quiz__lista" aria-label="Tipos de exercícios disponíveis">
        {modalidadesQuiz.map(({ id, titulo, descricao, icone: Icone, corBadge }) => (
          <article key={id} className="cartao-quiz">
            <div
              className="cartao-quiz__badge"
              style={{ backgroundColor: corBadge }}
              aria-hidden="true"
            >
              <Icone size={22} color="#FFFFFF" strokeWidth={2.2} />
            </div>

            <div className="cartao-quiz__conteudo">
              <h2 className="cartao-quiz__titulo">{titulo}</h2>
              <p className="cartao-quiz__descricao">{descricao}</p>
            </div>

            <ChevronRight className="cartao-quiz__seta" size={20} aria-hidden="true" />
          </article>
        ))}
      </section>

      {/* Card informativo estrutural — sem falso rastreamento ou dados inventados */}
      <section className="pagina-quiz__informativo" aria-label="Status dos exercícios">
        <div className="cartao-informativo">
          <div className="cartao-informativo__badge" aria-hidden="true">
            <Sparkles size={22} color="#0D9488" strokeWidth={2} />
          </div>
          <div className="cartao-informativo__conteudo">
            <h2 className="cartao-informativo__titulo">Exercícios em preparação</h2>
            <p className="cartao-informativo__descricao">
              As atividades serão ativadas assim que o conteúdo educacional de Libras for adicionado nas próximas etapas.
            </p>
          </div>
        </div>
      </section>
    </main>
  )
}
