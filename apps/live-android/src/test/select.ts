/** Test helpers for the `Select` dropdown of the app (issue #571): the tests choose by the value of an option, as they did with the system `<select>`. */
import { fireEvent, screen } from '@testing-library/react'

const box = (label: string) => screen.getByRole('combobox', { name: label })

/** Opens the dropdown called `label` and chooses the option with that value. */
export function pickOption(label: string, value: string): void {
  fireEvent.click(box(label))
  const option = Array.from(screen.getByRole('listbox').querySelectorAll('[role="option"]')).find(o => o.getAttribute('data-value') === value)
  if (!option) throw new Error(`No option with value "${value}" in "${label}"`)
  fireEvent.click(option)
}

/** The value of the chosen option. */
export const valueOf = (label: string): string | null => box(label).getAttribute('data-value')

/** The texts of the options, in order (the list is opened and closed again). */
export function optionLabels(label: string): string[] {
  fireEvent.click(box(label))
  const labels = Array.from(screen.getByRole('listbox').querySelectorAll('[role="option"]')).map(o => o.textContent ?? '')
  fireEvent.keyDown(box(label), { key: 'Escape' })
  return labels
}
