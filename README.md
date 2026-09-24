# LiFbras

LiFbras é um aplicativo educacional para estudar conceitos introdutórios de Língua Brasileira de Sinais (Libras). O MVP reúne **Aprender** (referências visuais), **Praticar** (pontos das mãos pela câmera) e **Quiz** (revisão de conceitos).

## Tecnologia

O frontend é uma PWA em React e Vite. O laboratório usa MediaPipe no navegador para mostrar pontos das mãos, sem classificar ou corrigir sinais. O projeto também contém uma base FastAPI e pesquisa experimental em PyTorch, que não são necessárias para executar o MVP.

## Executar localmente

Requer Node.js 20.

```bash
cd frontend
npm ci
npm run dev
```

Para conferir a versão de produção: `npm run lint`, `npm run build` e `npm run preview`. A câmera precisa de `localhost` ou HTTPS. O deploy estático no Vercel usa as configurações de `vercel.json` na raiz do repositório.

## Privacidade e limites

Os quadros da câmera são processados no dispositivo; o LiFbras não envia imagens, vídeos ou pontos das mãos a seus servidores. Ao ativar a câmera, o navegador baixa o runtime WASM e o modelo do MediaPipe de serviços externos. O MediaPipe também [envia métricas de uso e desempenho ao Google](https://github.com/google-ai-edge/mediapipe#privacy-notice). Por isso, a prática com câmera requer conexão na primeira carga e não é garantida offline. Aprender e Quiz usam conteúdo local e ficam disponíveis após o cache da PWA.

O reconhecimento automático de sinais é pesquisa experimental e não faz parte do MVP. Consulte [CREDITS.md](CREDITS.md) para fontes educacionais e bibliotecas.
