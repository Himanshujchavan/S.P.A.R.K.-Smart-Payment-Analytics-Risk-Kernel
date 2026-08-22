// Root layout for the S.P.A.R.K. dashboard. Wraps every page in the
// design-token theme provider and persistent top navigation.

import './globals.css'
import ThemeProvider from '../components/ThemeProvider'
import Navbar from '../components/Navbar'

export const metadata = {
  title: 'S.P.A.R.K. · Smart Payment Analytics & Risk Kernel',
  description:
    'Real-time fraud detection and risk decisioning for Razorpay. Three-tier scoring, abuse-ring detection, counterfactual explainability, and model drift monitoring.',
}

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link
          rel="preconnect"
          href="https://fonts.googleapis.com"
        />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin=""
        />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;600&family=IBM+Plex+Mono:wght@400;500&display=swap"
        />
      </head>
      <body>
        <ThemeProvider>
          <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
            <Navbar />
            <main
              style={{
                flex: 1,
                width: '100%',
                maxWidth: 1400,
                margin: '0 auto',
                padding: '24px 20px 40px',
              }}
            >
              {children}
            </main>
            <footer
              style={{
                borderTop: '1px solid var(--border-hairline)',
                padding: '12px 20px',
                color: 'var(--text-secondary)',
                fontSize: 11,
                textAlign: 'center',
              }}
            >
              S.P.A.R.K. — Track 02 · AI Risk Manager · Razorpay Buildathon · Defense-only · Every decision is logged.
            </footer>
          </div>
        </ThemeProvider>
      </body>
    </html>
  )
}
