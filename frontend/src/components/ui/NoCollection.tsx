import PageTransition from './PageTransition'

/** What a page that needs a collection shows while none is picked. */
export default function NoCollection() {
  return (
    <PageTransition>
      <p className="text-center text-ink-faint mt-16">Selecciona una colección para continuar.</p>
    </PageTransition>
  )
}
