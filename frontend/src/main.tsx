import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'
import { AuthProvider } from './common/contexts/AuthContext.tsx'
import { isSignInPath, signInTarget } from './common/signIn'

// Apache has already signed the user in by the time /sign-in loads, so send
// them back to the page they came from without starting the app
if (isSignInPath(window.location.pathname)) {
  window.location.replace(signInTarget(window.location.search))
} else {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <AuthProvider>
        <App />
      </AuthProvider>
    </React.StrictMode>,
  )
}
