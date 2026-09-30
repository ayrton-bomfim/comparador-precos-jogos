import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import './App.css'
import Inicio from './paginas/Inicio'
import Jogos from './paginas/Jogos'
import DetalhesJogo from './paginas/DetalhesJogo'
import Ofertas from './paginas/Ofertas'
import Sobre from './paginas/Sobre'
import Arquitetura from './paginas/Arquitetura'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Inicio />} />
        <Route path="/jogos" element={<Jogos />} />
        <Route path="/jogos/:id" element={<DetalhesJogo />} />
        <Route path="/ofertas" element={<Ofertas />} />
        <Route path="/sobre" element={<Sobre />} />
        <Route path="/arquitetura" element={<Arquitetura />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
