import React, { useState, useEffect } from 'react'
import { Terminal, Download } from 'lucide-react'

const SystemLogs = () => {
  const [logs, setLogs] = useState([
    { id: 1, timestamp: new Date().toISOString(), message: 'Job automation tool ready...', level: 'info' },
    { id: 2, timestamp: new Date().toISOString(), message: 'Waiting for jobs to be added to queue...', level: 'info' }
  ])

  useEffect(() => {
    // Simulate real-time logs
    const interval = setInterval(() => {
      if (Math.random() > 0.7) { // 30% chance of new log every 5 seconds
        const messages = [
          'System health check completed',
          'Queue processed successfully',
          'Cover letter cache updated',
          'Browser session initialized',
          'Database connection verified'
        ]
        
        const newLog = {
          id: Date.now(),
          timestamp: new Date().toISOString(),
          message: messages[Math.floor(Math.random() * messages.length)],
          level: 'info'
        }
        
        setLogs(prev => [...prev.slice(-19), newLog]) // Keep last 20 logs
      }
    }, 5000)

    return () => clearInterval(interval)
  }, [])

  const addLog = (message, level = 'info') => {
    const newLog = {
      id: Date.now(),
      timestamp: new Date().toISOString(),
      message,
      level
    }
    setLogs(prev => [...prev.slice(-19), newLog])
  }

  const getLevelColor = (level) => {
    switch (level) {
      case 'error': return 'text-red-400'
      case 'warn': return 'text-yellow-400'
      case 'success': return 'text-green-400'
      default: return 'text-gray-300'
    }
  }

  const downloadLogs = () => {
    const logText = logs.map(log => 
      `[${new Date(log.timestamp).toLocaleString()}] ${log.level.toUpperCase()}: ${log.message}`
    ).join('\n')
    
    const blob = new Blob([logText], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `job-automation-logs-${new Date().toISOString().split('T')[0]}.txt`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  // Expose addLog function globally for other components
  useEffect(() => {
    window.addSystemLog = addLog
    return () => {
      delete window.addSystemLog
    }
  }, [])

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <Terminal className="w-5 h-5 text-gray-600" />
          <h3 className="text-lg font-semibold text-gray-900">System Logs</h3>
        </div>
        <button
          onClick={downloadLogs}
          className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900"
        >
          <Download className="w-4 h-4 mr-1" />
          Export
        </button>
      </div>

      <div className="bg-gray-900 rounded-lg p-4 font-mono text-sm h-64 overflow-y-auto">
        {logs.map((log) => (
          <div key={log.id} className="flex space-x-2 mb-1">
            <span className="text-gray-500 text-xs">
              [{new Date(log.timestamp).toLocaleTimeString()}]
            </span>
            <span className={getLevelColor(log.level)}>
              {log.message}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default SystemLogs