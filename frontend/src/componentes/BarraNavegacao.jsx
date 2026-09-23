import { NavLink } from 'react-router-dom'
import { BookOpen, Video, BarChart2 } from 'lucide-react'
import './BarraNavegacao.css'

const abas = [
  { caminho: '/aprender', rotulo: 'Aprender', icone: BookOpen },
  { caminho: '/praticar', rotulo: 'Praticar', icone: Video },
  { caminho: '/quiz', rotulo: 'Quiz', icone: BarChart2 },
]

export default function BarraNavegacao() {
  return (
    <nav className="barra-navegacao" aria-label="Navegação principal">
      <div className="barra-navegacao__container">
        {abas.map(({ caminho, rotulo, icone: Icone }) => (
          <NavLink
            key={caminho}
            to={caminho}
            className={({ isActive }) =>
              `barra-navegacao__aba ${isActive ? 'barra-navegacao__aba--ativa' : ''}`
            }
          >
            <Icone className="barra-navegacao__icone" size={24} aria-hidden="true" />
            <span className="barra-navegacao__rotulo">{rotulo}</span>
          </NavLink>
        ))}
      </div>
    </nav>
  )
}
