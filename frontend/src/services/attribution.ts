export type AttributedRecord = {
  workspace_id?: number
  created_by_user?: { id: number; email: string }
  updated_by_user?: { id: number; email: string }
  created_at?: string
  updated_at?: string
  attribution_source?: string
}
