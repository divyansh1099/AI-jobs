import React, { useState } from 'react'
import { Play, Square, RefreshCw, Search, Plus } from 'lucide-react'
import { useMutation, useQueryClient } from 'react-query'
import { startAutomation, stopAutomation, addSampleJobs, scrapeJobs } from '../api/jobApi'

const ControlPanel = ({ isRunning }) => {
  const [isLoading, setIsLoading] = useState(false)
  const queryClient = useQueryClient()

  const startMutation = useMutation(startAutomation, {
    onSuccess: () => queryClient.invalidateQueries('status')
  })

  const stopMutation = useMutation(stopAutomation, {
    onSuccess: () => queryClient.invalidateQueries('status')
  })

  const sampleJobsMutation = useMutation(addSampleJobs, {
    onSuccess: () => queryClient.invalidateQueries('status')
  })

  const scrapeMutation = useMutation(scrapeJobs, {
    onSuccess: () => queryClient.invalidateQueries('status')
  })

  const handleStart = async () => {
    setIsLoading(true)
    await startMutation.mutateAsync()
    setIsLoading(false)
  }

  const handleStop = async () => {
    setIsLoading(true)
    await stopMutation.mutateAsync()
    setIsLoading(false)
  }

  const handleAddSample = async () => {
    setIsLoading(true)
    await sampleJobsMutation.mutateAsync()
    setIsLoading(false)
  }

  const handleScrape = async () => {
    setIsLoading(true)
    await scrapeMutation.mutateAsync()
    setIsLoading(false)
  }

  const handleRefresh = () => {
    queryClient.invalidateQueries('status')
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-3">
          <div className={`w-3 h-3 rounded-full ${isRunning ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`}></div>
          <h2 className="text-xl font-semibold text-gray-900">
            Status: {isRunning ? 'Running' : 'Stopped'}
          </h2>
        </div>
      </div>

      <div className="flex flex-wrap gap-3">
        <button
          onClick={handleStart}
          disabled={isRunning || isLoading}
          className="btn btn-primary focus:ring-blue-500"
        >
          <Play className="w-4 h-4 mr-2" />
          Start Automation
        </button>

        <button
          onClick={handleStop}
          disabled={!isRunning || isLoading}
          className="btn btn-danger"
        >
          <Square className="w-4 h-4 mr-2" />
          Stop Automation
        </button>

        <button
          onClick={handleAddSample}
          disabled={isLoading}
          className="btn btn-secondary"
        >
          <Plus className="w-4 h-4 mr-2" />
          Add Sample Jobs
        </button>

        <button
          onClick={handleScrape}
          disabled={isLoading}
          className="btn btn-secondary"
        >
          <Search className="w-4 h-4 mr-2" />
          Scrape Jobs
        </button>

        <button
          onClick={handleRefresh}
          disabled={isLoading}
          className="btn btn-secondary"
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </button>
      </div>

      {isLoading && (
        <div className="mt-4 flex items-center space-x-2 text-gray-600">
          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary-600"></div>
          <span className="text-sm">Processing...</span>
        </div>
      )}
    </div>
  )
}

export default ControlPanel