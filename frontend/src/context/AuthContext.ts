import { createContext, useContext } from 'react'
import type { User, Workspace } from '../services/auth'

export const AuthContext = createContext<{ user: User; workspace: Workspace; logout: () => Promise<void>; loggingOut: boolean } | null>(null)
export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('Sessão não inicializada.')
  return value
}
