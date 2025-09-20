import React from 'react'
import { BarChart3, CheckCircle, XCircle, Clock, TrendingUp } from 'lucide-react'

const StatsCards = ({ stats = {} }) => {
  const { total = 0, successful = 0, failed = 0, pending = 0 } = stats
  
  const successRate = total > 0 ? Math.round((successful / total) * 100) : 0

  const statItems = [
    {
      label: 'Total Applications',
      value: total,
      icon: BarChart3,
      color: 'text-gray-600',
      bgColor: 'bg-gray-100'
    },
    {
      label: 'Successful',
      value: successful,
      icon: CheckCircle,
      color: 'text-green-600',
      bgColor: 'bg-green-50'
    },
    {
      label: 'Failed',
      value: failed,
      icon: XCircle,
      color: 'text-red-600',
      bgColor: 'bg-red-50'
    },
    {
      label: 'Pending',
      value: pending,
      icon: Clock,
      color: 'text-yellow-600',
      bgColor: 'bg-yellow-50'
    },
    {
      label: 'Success Rate',
      value: `${successRate}%`,
      icon: TrendingUp,
      color: successRate >= 70 ? 'text-green-600' : successRate >= 50 ? 'text-yellow-600' : 'text-red-600',
      bgColor: successRate >= 70 ? 'bg-green-50' : successRate >= 50 ? 'bg-yellow-50' : 'bg-red-50'
    }
  ]

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-6">
      {statItems.map((item, index) => {
        const Icon = item.icon
        return (
          <div key={index} className="stat-card">
            <div className={`inline-flex items-center justify-center w-12 h-12 rounded-lg ${item.bgColor} mb-4`}>
              <Icon className={`w-6 h-6 ${item.color}`} />
            </div>
            <div className="text-2xl font-bold text-gray-900 mb-1">
              {item.value}
            </div>
            <div className="text-sm text-gray-600">
              {item.label}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default StatsCards