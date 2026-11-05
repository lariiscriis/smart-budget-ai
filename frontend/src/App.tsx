import { useState } from 'react'
import CategoriesPanel from './components/CategoriesPanel'
import FinancialEntryPanel from './components/FinancialEntryPanel'
import ImportPanel from './components/ImportPanel'
import CopilotPanel from './components/CopilotPanel'
import AutomationPanel from './components/AutomationPanel'
import DashboardPanel from './components/DashboardPanel'
import IncomeListPanel from './components/IncomeListPanel'
import CampaignsPanel from './components/CampaignsPanel'
import AuthGate from './components/AuthGate'
import AuditPanel from './components/AuditPanel'
import { useAuth } from './context/AuthContext'
import './App.css'

const pages = [
  { id: 'dashboard', label: 'Visão geral', title: 'Visão financeira', description: 'Receitas, despesas e decisões com base nos registros do departamento.' },
  { id: 'entries', label: 'Registros', title: 'Registros financeiros', description: 'Organize categorias e campanhas e registre orçamentos, receitas e despesas.' },
  { id: 'imports', label: 'Importações', title: 'Importações', description: 'Revise os registros antes de incorporá-los às despesas.' },
  { id: 'automations', label: 'Automações', title: 'Alertas e automações', description: 'Acompanhe as regras financeiras e as tarefas de processamento.' },
  { id: 'copilot', label: 'Copiloto', title: 'Copiloto financeiro', description: 'Consulte os dados e as políticas disponíveis.' },
  { id: 'audit', label: 'Auditoria', title: 'Auditoria', description: 'Acompanhe as alterações na base compartilhada do departamento.' },
] as const
type PageId = typeof pages[number]['id']

function initialPeriod() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

function FinancialApp() {
  const { user, workspace, logout, loggingOut } = useAuth()
  const [active, setActive] = useState<PageId>('dashboard')
  const [visited, setVisited] = useState<PageId[]>(['dashboard'])
  const [period, setPeriod] = useState(initialPeriod)
  const [incomePeriod, setIncomePeriod] = useState(initialPeriod)
  const [incomeRefresh, setIncomeRefresh] = useState(0)
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
      <div><span>{workspace.name} · {user.email}</span> <button className="secondary-button" type="button" disabled={loggingOut} onClick={() => void logout()}>Sair</button></div>
    </header>
    <main className="dashboard" id="dashboard">
      <div className="page-heading">
        <div><p className="eyebrow">Aurora / {page.label}</p><h1>{page.title}</h1><p>{page.description}</p></div>
        {(active === 'dashboard' || active === 'automations') && <label className="period-control" htmlFor="period">Mês de referência
          <input id="period" type="month" required min="2000-01" max="2100-12" value={period}
            onChange={(event) => { if (/^(20\d{2}|2100)-(0[1-9]|1[0-2])$/.test(event.target.value)) setPeriod(event.target.value) }} />
        </label>}
      </div>
      <p className="data-note">Base compartilhada: {workspace.name}{workspace.is_demo ? ' · Demonstração — use somente dados fictícios.' : ' · Acesso restrito aos membros do departamento.'}</p>
      {active === 'dashboard' && <DashboardPanel period={period} />}
      {visited.includes('entries') && <div hidden={active !== 'entries'}>
        <FinancialEntryPanel onIncomeCreated={(date) => { setIncomePeriod(date.slice(0, 7)); setIncomeRefresh((value) => value + 1) }} />
        <IncomeListPanel key={`${incomePeriod}-${incomeRefresh}`} period={incomePeriod} onPeriodChange={setIncomePeriod} refresh={incomeRefresh} />
        <CampaignsPanel />
        <CategoriesPanel />
      </div>}
      {visited.includes('imports') && <div hidden={active !== 'imports'}><ImportPanel /></div>}
      {visited.includes('automations') && <div hidden={active !== 'automations'}><AutomationPanel year={year} month={month} /></div>}
      {visited.includes('copilot') && <div hidden={active !== 'copilot'}><CopilotPanel /></div>}
      {visited.includes('audit') && <div hidden={active !== 'audit'}><AuditPanel /></div>}
      <footer className="page-footer"><span>Aurora</span><p>Controle financeiro · Cosméticos naturais</p></footer>
    </main>
  </>
}

export default function App() {
  return <AuthGate><FinancialApp /></AuthGate>
}
