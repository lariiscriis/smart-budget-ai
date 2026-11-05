import stillLife from '../assets/aurora-still-life.svg'
import './LandingPage.css'

export default function LandingPage({ authenticated = false }: { authenticated?: boolean }) {
  const destination = authenticated ? '#app' : '#login'
  const action = authenticated ? 'Ir para a aplicação' : 'Entrar no sistema'

  return <div className="aurora-landing">
    <header className="landing-header">
      <a className="landing-wordmark" href="#inicio" aria-label="Aurora, início">aurora<span>cosméticos naturais</span></a>
      <nav aria-label="Acesso ao sistema"><a className="landing-access" href={destination}>{action} <span aria-hidden="true">↗</span></a></nav>
    </header>
    <main className="landing-main" id="inicio">
      <div className="landing-copy">
        <p className="landing-kicker">O cuidado também está nos bastidores</p>
        <h1>Cuidado natural.<br /><em>Clareza para crescer.</em></h1>
        <p className="landing-description">Da essência dos cosméticos à organização das finanças. Um espaço para a equipe Aurora acompanhar receitas, despesas e campanhas com uma visão compartilhada.</p>
        <a className="landing-cta" href={destination}>{action}<span aria-hidden="true">↗</span></a>
        <p className="landing-caption">Gestão financeira da Aurora</p>
      </div>
      <figure className="landing-artwork">
        <img src={stillLife} width="560" height="580" alt="Composição ilustrada de frascos Aurora e um ramo de folhas, em tons creme e bordô." />
        <figcaption>Natureza na essência. Cuidado em cada detalhe.</figcaption>
      </figure>
    </main>
    <footer className="landing-footer">
      <p>Receitas e despesas <span aria-hidden="true">/</span> Campanhas <span aria-hidden="true">/</span> Visão financeira</p>
      <p>Marca fictícia · Projeto de demonstração</p>
    </footer>
  </div>
}
