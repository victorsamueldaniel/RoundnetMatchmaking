export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export const downloadJson = (value: unknown, filename: string) =>
  downloadBlob(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }), filename)

export function dateStamp(date = new Date()) {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(date.getDate())}_${pad(date.getMonth() + 1)}_${date.getFullYear()}`
}
