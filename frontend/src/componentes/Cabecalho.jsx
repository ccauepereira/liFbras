import './Cabecalho.css'

export default function Cabecalho() {
  return (
    <header className="cabecalho">
      <div className="cabecalho__marca">
        <svg className="cabecalho__logo-icone" viewBox="0 0 40 40" fill="none" aria-hidden="true">
          <rect width="40" height="40" rx="10" fill="#0D9488" />
          <g transform="translate(6, 5)">
            <path d="M3 23 C1 18, 3 12, 8 9 C11 7, 15 8, 16 12 C18 16, 16 22, 13 25 C10 28, 5 26, 3 23 Z" fill="#FFFFFF" />
            <path d="M12 5 C15 3, 19 3, 21 6 C24 9, 23 14, 20 18" stroke="#A7F3D0" strokeWidth="2.5" strokeLinecap="round" />
            <path d="M18 3 C22 2, 26 3, 28 7 C29 11, 28 15, 25 18" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" opacity="0.9" />
          </g>
        </svg>
        <div className="cabecalho__textos">
          <span className="cabecalho__nome">
            <span className="cabecalho__nome-destaque">Li</span>Fbras
          </span>
          <span className="cabecalho__lema">LIBRAS AO SEU ALCANCE</span>
        </div>
      </div>
    </header>
  )
}

