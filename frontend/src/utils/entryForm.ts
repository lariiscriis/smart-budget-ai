export function todayLocal(): string {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}

export function normalizeAmount(value: string, positive: boolean): string {
  const normalized = value.trim().replace(',', '.')
  if (!/^\d{1,12}(\.\d{1,2})?$/.test(normalized)) {
    throw new Error('Use até 12 dígitos inteiros e duas casas decimais, sem separador de milhares. Ex.: 1500,50.')
  }
  const [integer, fraction = ''] = normalized.split('.')
  const result = `${integer}.${fraction.padEnd(2, '0')}`
  if (positive && /^0+\.00$/.test(result)) throw new Error('O valor precisa ser maior que zero.')
  return result
}

export function parsePeriod(value: string): { year: number; month: number } {
  if (!/^(20\d{2}|2100)-(0[1-9]|1[0-2])$/.test(value)) throw new Error('Selecione um mês válido entre 2000 e 2100.')
  const [year, month] = value.split('-').map(Number)
  return { year, month }
}

export function validateDate(value: string): void {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) throw new Error('Informe uma data válida.')
  parsePeriod(value.slice(0, 7))
  const date = new Date(`${value}T00:00:00Z`)
  if (Number.isNaN(date.getTime()) || date.toISOString().slice(0, 10) !== value) throw new Error('Informe uma data válida.')
}
