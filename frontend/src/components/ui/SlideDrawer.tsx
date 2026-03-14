/**
 * SlideDrawer — animated side panel sliding from the right.
 *
 * Usage:
 *   <SlideDrawer open={open} onClose={() => setOpen(false)} title="Jugador">
 *     <PlayerDetail player={player} />
 *   </SlideDrawer>
 */
import { ReactNode, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'

interface Props {
  open: boolean
  onClose: () => void
  title?: string
  /** Width of the drawer. Defaults to 'md' (480px) */
  size?: 'sm' | 'md' | 'lg'
  children: ReactNode
}

const SIZES = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-xl',
}

export default function SlideDrawer({
  open,
  onClose,
  title,
  size = 'md',
  children,
}: Props) {
  // Close on Escape
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, onClose])

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 bg-black/50 z-40 backdrop-blur-sm"
            onClick={onClose}
          />

          {/* Panel */}
          <motion.div
            key="panel"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 30, stiffness: 300 }}
            className={cn(
              'fixed right-0 top-0 bottom-0 w-full bg-surface-raised border-l border-surface-border',
              'flex flex-col z-50 shadow-panel',
              SIZES[size],
            )}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-surface-border shrink-0">
              {title && (
                <h2 className="text-sm font-semibold text-ink-primary">{title}</h2>
              )}
              <button
                onClick={onClose}
                className="ml-auto p-1 rounded hover:bg-surface-hover text-ink-secondary hover:text-ink-primary transition-colors"
                aria-label="Cerrar"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto px-5 py-4">
              {children}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
