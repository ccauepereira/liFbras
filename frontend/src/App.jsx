import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import BarraNavegacao from './componentes/BarraNavegacao'
import PaginaAprender from './paginas/PaginaAprender'
import PaginaPraticar from './paginas/PaginaPraticar'
import PaginaQuiz from './paginas/PaginaQuiz'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/aprender" element={<PaginaAprender />} />
        <Route path="/aprender/:categoriaId" element={<PaginaAprender />} />
        <Route path="/praticar" element={<PaginaPraticar />} />
        <Route path="/quiz" element={<PaginaQuiz />} />
        <Route path="*" element={<Navigate to="/aprender" replace />} />
      </Routes>
      <BarraNavegacao />
    </BrowserRouter>
  )
}
