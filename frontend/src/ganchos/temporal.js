export function copiarMao(landmarks) {
  if (!landmarks?.length) return null
  return landmarks.map(({ x, y, z }) => ({ x, y, z }))
}

export function copiarFrame(resultado, timestampMs) {
  const esquerda = []
  const direita = []

  resultado.landmarks.forEach((landmarks, indice) => {
    const categoria = resultado.handedness?.[indice]?.[0]?.categoryName
    if (categoria === 'Left') esquerda.push(landmarks)
    if (categoria === 'Right') direita.push(landmarks)
  })

  return {
    timestampMs,
    maoEsquerda: copiarMao(esquerda[0]),
    maoDireita: copiarMao(direita[0]),
  }
}

export function contarMaos(frame) {
  return Number(Boolean(frame.maoEsquerda)) + Number(Boolean(frame.maoDireita))
}
