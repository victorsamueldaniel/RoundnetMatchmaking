import { useEffect, useRef, type ButtonHTMLAttributes, type ReactNode } from 'react'

type Variant = 'primary' | 'danger' | 'ghost' | 'subtle'

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-brand-yellow text-black hover:bg-brand-yellow-hover font-semibold',
  danger: 'bg-brand-red text-white hover:bg-brand-red-hover',
  ghost: 'bg-transparent text-soft hover:bg-raised border border-line',
  subtle: 'bg-raised text-white hover:bg-line',
}

export function Button({
  variant = 'subtle',
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      {...props}
      className={`inline-flex min-h-10 items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm transition-colors disabled:opacity-40 ${VARIANTS[variant]} ${className}`}
    />
  )
}

export function Card({ title, actions, children, className = '' }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl border border-line bg-panel ${className}`}>
      {(title || actions) && (
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2.5">
          <h2 className="text-sm font-semibold tracking-wide text-brand-yellow uppercase">{title}</h2>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  )
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
  size = 'md',
}: {
  value: T
  options: { value: T; label: string }[]
  onChange: (value: T) => void
  label?: string
  size?: 'sm' | 'md'
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-lg border border-line bg-ink p-0.5">
      {options.map((option) => (
        <button
          key={option.value}
          role="radio"
          aria-checked={value === option.value}
          onClick={() => onChange(option.value)}
          className={`rounded-md ${size === 'sm' ? 'min-h-8 px-2.5 text-xs' : 'min-h-9 px-3 text-sm'} transition-colors ${
            value === option.value ? 'bg-brand-yellow font-semibold text-black' : 'text-soft hover:bg-raised'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

export function Slider({
  label,
  help,
  value,
  min,
  max,
  step,
  onChange,
  format = (v) => v.toFixed(step < 1 ? 1 : 0),
}: {
  label: string
  help?: string
  value: number
  min: number
  max: number
  step: number
  onChange: (value: number) => void
  format?: (value: number) => string
}) {
  return (
    <label className="block rounded-lg border border-line bg-ink/60 px-3 py-2.5" title={help}>
      <span className="flex items-baseline justify-between gap-2 text-sm">
        <span className="text-soft">{label}</span>
        <span className="font-mono font-semibold text-brand-yellow tabular-nums">{format(value)}</span>
      </span>
      <input
        type="range"
        className="mt-2 w-full"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      {help && <span className="mt-1 block text-xs text-muted">{help}</span>}
    </label>
  )
}

export function Modal({
  open,
  title,
  onClose,
  children,
  footer,
  wide = false,
}: {
  open: boolean
  title: ReactNode
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  wide?: boolean
}) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])
  return (
    <dialog
      ref={ref}
      onCancel={(e) => {
        e.preventDefault()
        onClose()
      }}
      className={`m-auto max-h-[92dvh] w-[calc(100%-1rem)] ${wide ? 'max-w-4xl' : 'max-w-lg'} overflow-hidden rounded-2xl border border-line bg-panel p-0 text-white backdrop:bg-black/70`}
    >
      {open && (
        <div className="flex max-h-[92dvh] flex-col">
          <header className="flex items-center justify-between gap-3 bg-brand-red px-4 py-3">
            <h2 className="text-base font-semibold text-brand-yellow">{title}</h2>
            <button onClick={onClose} aria-label="Close" className="rounded-md px-2 text-xl leading-none text-white/80 hover:text-white">
              ×
            </button>
          </header>
          <div className="scroll-thin flex-1 overflow-y-auto p-4">{children}</div>
          {footer && <footer className="flex flex-wrap justify-end gap-2 border-t border-line px-4 py-3">{footer}</footer>}
        </div>
      )}
    </dialog>
  )
}

export function Notice({ tone = 'info', children }: { tone?: 'info' | 'error' | 'success'; children: ReactNode }) {
  const tones = {
    info: 'border-line bg-raised text-soft',
    error: 'border-red-500/40 bg-red-950/60 text-red-200',
    success: 'border-emerald-500/40 bg-emerald-950/50 text-emerald-200',
  }
  return <div className={`rounded-lg border px-3 py-2 text-sm ${tones[tone]}`}>{children}</div>
}
