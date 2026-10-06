export function mapearPontaIndicador(ponto, videoLargura, videoAltura, areaLargura, areaAltura) {
  if (!ponto || ![ponto.x, ponto.y].every(Number.isFinite) || !videoLargura || !videoAltura || !areaLargura || !areaAltura) return null

  // O vídeo usa object-fit: cover e scaleX(-1); ajuste o corte antes de espelhar X.
  const escala = Math.max(areaLargura / videoLargura, areaAltura / videoAltura)
  const larguraRenderizada = videoLargura * escala
  const alturaRenderizada = videoAltura * escala
  const recorteX = (areaLargura - larguraRenderizada) / 2
  const recorteY = (areaAltura - alturaRenderizada) / 2
  const xRenderizado = ponto.x * larguraRenderizada + recorteX
  const yRenderizado = ponto.y * alturaRenderizada + recorteY

  return {
    x: Math.min(1, Math.max(0, (areaLargura - xRenderizado) / areaLargura)),
    y: Math.min(1, Math.max(0, yRenderizado / areaAltura)),
  }
}

export function gerarAlvoSeguro(largura, altura, raio, random = Math.random, evitar = null) {
  // Allow room for the target's visible outer ring and glow.
  const margemX = Math.min(raio + 14, largura / 2)
  const margemY = Math.min(raio + 14, altura / 2)
  const minimoX = margemX
  const minimoY = margemY
  const maximoX = Math.max(minimoX, largura - margemX)
  const maximoY = Math.max(minimoY, altura - margemY)
  const limiteDistancia = raio * 2.2
  let candidato = { x: largura / 2, y: altura / 2 }
  let distante = !evitar

  for (let tentativa = 0; tentativa < 40; tentativa += 1) {
    candidato = {
      x: minimoX + random() * (maximoX - minimoX),
      y: minimoY + random() * (maximoY - minimoY),
    }
    if (!evitar || Math.hypot(candidato.x - evitar.x * largura, candidato.y - evitar.y * altura) >= limiteDistancia) { distante = true; break }
  }

  if (!distante) {
    const cantos = [
      { x: minimoX, y: minimoY }, { x: maximoX, y: minimoY },
      { x: minimoX, y: maximoY }, { x: maximoX, y: maximoY },
    ]
    candidato = cantos.reduce((maisDistante, atual) => (
      Math.hypot(atual.x - evitar.x * largura, atual.y - evitar.y * altura) > Math.hypot(maisDistante.x - evitar.x * largura, maisDistante.y - evitar.y * altura) ? atual : maisDistante
    ))
  }

  return { x: candidato.x / largura, y: candidato.y / altura }
}

export function colisaoCircular(ponteiro, alvo, largura, altura, raioAlvo, raioPonteiro = 12) {
  if (!ponteiro || !alvo || largura <= 0 || altura <= 0) return false
  const dx = (ponteiro.x - alvo.x) * largura
  const dy = (ponteiro.y - alvo.y) * altura
  return Math.hypot(dx, dy) <= raioAlvo + raioPonteiro
}
