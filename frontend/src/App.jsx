import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import BarraNavegacao from './componentes/BarraNavegacao'
import PaginaAprender from './paginas/PaginaAprender'
import PaginaPraticar from './paginas/PaginaPraticar'
import PaginaQuiz from './paginas/PaginaQuiz'
import PaginaColeta from './coleta/PaginaColeta'

function RotasAplicacao() {
  const location = useLocation()
  const experimental = location.pathname.startsWith('/laboratorio/')
  return <>
    <Routes>
      <Route path="/aprender" element={<PaginaAprender />} />
      <Route path="/aprender/:categoriaId" element={<PaginaAprender />} />
      <Route path="/praticar" element={<PaginaPraticar />} />
      <Route path="/quiz" element={<PaginaQuiz />} />
      <Route path="/laboratorio/coleta" element={<PaginaColeta />} />
      <Route path="*" element={<Navigate to="/aprender" replace />} />
    </Routes>
    {!experimental && <BarraNavegacao />}
  </>
}

export default function App() {
  return (
    <BrowserRouter>
      <RotasAplicacao />
    </BrowserRouter>
  )
}
