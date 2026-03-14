/**
 * PageTransition — wraps page content in a Framer Motion fade+slide.
 *
 * Usage: wrap your page's root element in <PageTransition>.
 */
import { motion } from 'framer-motion'
import { ReactNode } from 'react'

interface Props {
  children: ReactNode
  className?: string
}

const VARIANTS = {
  hidden:  { opacity: 0, y: 8 },
  visible: { opacity: 1, y: 0 },
  exit:    { opacity: 0, y: -4 },
}

export default function PageTransition({ children, className }: Props) {
  return (
    <motion.div
      variants={VARIANTS}
      initial="hidden"
      animate="visible"
      exit="exit"
      transition={{ duration: 0.18, ease: [0.4, 0, 0.2, 1] }}
      className={className}
    >
      {children}
    </motion.div>
  )
}
