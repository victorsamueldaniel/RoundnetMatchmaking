import { create } from 'zustand'

type Toast = { id: number; tone: 'info' | 'error' | 'success'; text: string }

export const useToasts = create<{ toasts: Toast[]; push: (tone: Toast['tone'], text: string) => void }>((set) => ({
  toasts: [],
  push: (tone, text) => {
    const id = Date.now() + Math.random()
    set((s) => ({ toasts: [...s.toasts, { id, tone, text }] }))
    setTimeout(() => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })), tone === 'error' ? 7000 : 3500)
  },
}))

export const toast = (tone: Toast['tone'], text: string) => useToasts.getState().push(tone, text)

export function Toasts() {
  const toasts = useToasts((s) => s.toasts)
  const tones = {
    info: 'border-line bg-raised',
    error: 'border-red-500/50 bg-red-950',
    success: 'border-emerald-500/50 bg-emerald-950',
  }
  return (
    <div aria-live="polite" className="pointer-events-none fixed inset-x-0 top-3 z-50 flex flex-col items-center gap-2 px-3">
      {toasts.map((t) => (
        <div key={t.id} className={`pointer-events-auto max-w-md rounded-lg border px-4 py-2.5 text-sm whitespace-pre-line shadow-lg ${tones[t.tone]}`}>
          {t.text}
        </div>
      ))}
    </div>
  )
}
