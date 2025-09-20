import React from 'react'
import { Building2, MapPin, ExternalLink, Briefcase } from 'lucide-react'

const JobQueue = ({ jobs = [] }) => {
  const getStatusColor = (status) => {
    switch (status) {
      case 'pending': return 'status-pending'
      case 'processing': return 'status-processing'  
      case 'completed': return 'status-completed'
      case 'failed': return 'status-failed'
      default: return 'status-pending'
    }
  }

  const getPlatformColor = (platform) => {
    switch (platform.toLowerCase()) {
      case 'linkedin': return 'text-blue-600 bg-blue-50'
      case 'indeed': return 'text-green-600 bg-green-50'
      default: return 'text-gray-600 bg-gray-50'
    }
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold text-gray-900">Job Queue</h3>
        <span className="text-sm text-gray-500">
          {jobs.length} job{jobs.length !== 1 ? 's' : ''}
        </span>
      </div>

      <div className="space-y-4 max-h-96 overflow-y-auto">
        {jobs.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Briefcase className="w-12 h-12 mx-auto mb-3 text-gray-300" />
            <p className="text-sm">No jobs in queue</p>
            <p className="text-xs">Add sample jobs or scrape new ones to get started</p>
          </div>
        ) : (
          jobs.map((job) => (
            <div
              key={job.id}
              className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center space-x-2 mb-2">
                    <h4 className="text-sm font-semibold text-gray-900 truncate">
                      {job.title}
                    </h4>
                    <span className={`status-badge ${getStatusColor(job.status)}`}>
                      {job.status}
                    </span>
                  </div>
                  
                  <div className="flex items-center space-x-4 text-xs text-gray-600 mb-2">
                    <div className="flex items-center space-x-1">
                      <Building2 className="w-3 h-3" />
                      <span>{job.company}</span>
                    </div>
                    
                    {job.location && (
                      <div className="flex items-center space-x-1">
                        <MapPin className="w-3 h-3" />
                        <span>{job.location}</span>
                      </div>
                    )}
                  </div>

                  <div className="flex items-center justify-between">
                    <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getPlatformColor(job.platform)}`}>
                      {job.platform}
                    </span>
                    
                    {job.url && (
                      <a
                        href={job.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary-600 hover:text-primary-700"
                      >
                        <ExternalLink className="w-4 h-4" />
                      </a>
                    )}
                  </div>

                  {job.processedAt && (
                    <div className="text-xs text-gray-500 mt-2">
                      Processed: {new Date(job.processedAt).toLocaleString()}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default JobQueue