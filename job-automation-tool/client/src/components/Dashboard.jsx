import React from 'react'
import { useQuery } from 'react-query'
import ControlPanel from './ControlPanel'
import StatsCards from './StatsCards'
import JobQueue from './JobQueue'
import SystemLogs from './SystemLogs'
import { fetchStatus } from '../api/jobApi'

const Dashboard = () => {
  const { data: status, isLoading, error } = useQuery('status', fetchStatus)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card">
        <div className="text-center text-error-600">
          <p className="text-lg font-semibold">Connection Error</p>
          <p className="text-sm mt-2">Unable to connect to the automation server</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Control Panel */}
      <ControlPanel isRunning={status?.running} />
      
      {/* Statistics */}
      <StatsCards stats={status?.stats} />
      
      {/* Job Queue and Logs */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <JobQueue jobs={status?.queue || []} />
        <SystemLogs />
      </div>
    </div>
  )
}

export default Dashboard