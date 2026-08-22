"use client"

import { createContext, useState, useEffect } from 'react'

export const ThemeContext = createContext()

export default function ThemeProvider({ children }) {
  const [theme, setTheme] = useState('light')
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
    try {
      const stored = localStorage.getItem('theme')
      if (stored) {
        setTheme(stored)
      }
    } catch (e) {}
  }, [])

  useEffect(() => {
    if (!mounted) return
    const el = document.documentElement
    const apply = (t) => {
      if (t === 'system') {
        const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
        el.setAttribute('data-theme', prefersDark ? 'dark' : 'light')
        if (prefersDark) el.classList.add('dark')
        else el.classList.remove('dark')
      } else {
        el.setAttribute('data-theme', t === 'dark' ? 'dark' : 'light')
        if (t === 'dark') el.classList.add('dark')
        else el.classList.remove('dark')
      }
    }

    apply(theme)
    try { localStorage.setItem('theme', theme) } catch (e) {}
  }, [theme, mounted])

  return (
    <ThemeContext.Provider value={{ theme, setTheme, mounted }}>
      {children}
    </ThemeContext.Provider>
  )
}
