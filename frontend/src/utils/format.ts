/** Keep monetary formatting in decimal strings, including exact cents. */
export function formatMoney(value: string): string {
  const negative = value.startsWith('-')
  const [integer, fraction = ''] = (negative ? value.slice(1) : value).split('.')
  return `${negative ? '−' : ''}R$ ${integer.replace(/\B(?=(\d{3})+(?!\d))/g, '.')},${fraction.padEnd(2, '0')}`
}

const monthNames = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
export const monthLabel = (year: number, month: number) => `${monthNames[month - 1]}/${String(year).slice(-2)}`
