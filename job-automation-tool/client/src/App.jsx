import React from 'react'
import { QueryClient, QueryClientProvider } from 'react-query'
import Dashboard from './components/Dashboard'
import Header from './components/Header'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchInterval: 3000, // Refresh every 3 seconds
      refetchOnWindowFocus: false,
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-gray-50">
        <Header />
        <main className="container mx-auto px-4 py-8 max-w-7xl">
          <Dashboard />
        </main>
      </div>
    </QueryClientProvider>
  )
}

export default App