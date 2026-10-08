import { createContext } from 'react'

// Student worksheets eagerly load mounted figures; see docs/worksheet-print.md.
export const FigureLoadingContext = createContext<'eager' | 'lazy'>('lazy')
