import { useState } from 'react'
import CategoriesPanel from './components/CategoriesPanel'
import FinancialEntryPanel from './components/FinancialEntryPanel'
import ImportPanel from './components/ImportPanel'
import CopilotPanel from './components/CopilotPanel'
import AutomationPanel from './components/AutomationPanel'
import DashboardPanel from './components/DashboardPanel'
import './App.css'

const pages = [
  { id: 'dashboard', label: 'Visão geral', title: 'Visão financeira', description: 'Receitas, despesas e decisões com base nos seus registros.' },
  { id: 'entries', label: 'Registros', title: 'Registros financeiros', description: 'Organize categorias e registre o orçamento e as despesas.' },
  { id: 'imports', label: 'Importações', title: 'Importações', description: 'Revise os registros antes de incorporá-los às despesas.' },
  { id: 'automations', label: 'Automações', title: 'Alertas e automações', description: 'Acompanhe as regras financeiras e as tarefas de processamento.' },
  { id: 'copilot', label: 'Copiloto', title: 'Copiloto financeiro', description: 'Consulte os dados e as políticas disponíveis.' },
] as const
type PageId = typeof pages[number]['id']

function initialPeriod() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

function App() {
  const [active, setActive] = useState<PageId>('dashboard')
  const [visited, setVisited] = useState<PageId[]>(['dashboard'])
  const [period, setPeriod] = useState(initialPeriod)
  const page = pages.find((item) => item.id === active)!
  const [year, month] = period.split('-').map(Number)

  function navigate(id: PageId) {
    setActive(id)
    setVisited((current) => current.includes(id) ? current : [...current, id])
  }

  return <>
    <header className="topbar">
      <a className="brand" href="#dashboard" onClick={(event) => { event.preventDefault(); navigate('dashboard') }} aria-label="Aurora, visão geral">aurora<span>gestão financeira</span></a>
      <nav aria-label="Navegação principal">
        {pages.map((item) => <button key={item.id} type="button" aria-current={active === item.id ? 'page' : undefined} onClick={() => navigate(item.id)}>{item.label}</button>)}
      </nav>
    </header>
    <main className="dashboard" id="dashboard">
      <div className="page-heading">
        <div><p className="eyebrow">Aurora / {page.label}</p><h1>{page.title}</h1><p>{page.description}</p></div>
        {(active === 'dashboard' || active === 'automations') && <label className="period-control" htmlFor="period">Mês de referência
          <input id="period" type="month" required min="2000-01" max="2100-12" value={period}
            onChange={(event) => { if (/^(20\d{2}|2100)-(0[1-9]|1[0-2])$/.test(event.target.value)) setPeriod(event.target.value) }} />
        </label>}
      </div>
      {active === 'dashboard' && <DashboardPanel period={period} />}
      {visited.includes('entries') && <div hidden={active !== 'entries'}><FinancialEntryPanel /><CategoriesPanel /></div>}
      {visited.includes('imports') && <div hidden={active !== 'imports'}><ImportPanel /></div>}
      {visited.includes('automations') && <div hidden={active !== 'automations'}><AutomationPanel year={year} month={month} /></div>}
      {visited.includes('copilot') && <div hidden={active !== 'copilot'}><CopilotPanel /></div>}
      <footer className="page-footer"><span>Aurora</span><p>Controle financeiro · Cosméticos naturais</p></footer>
    </main>
  </>
}

export default App
