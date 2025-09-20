import React from 'react'
import { Bot, Briefcase } from 'lucide-react'

const Header = () => {
  return (
    <header className="bg-white border-b border-gray-200 shadow-sm">
      <div className="container mx-auto px-4 py-4 max-w-7xl">
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2">
            <Bot className="h-8 w-8 text-primary-600" />
            <Briefcase className="h-6 w-6 text-gray-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              Job Automation Tool
            </h1>
            <p className="text-sm text-gray-600">
              Automated job applications with local LLM integration
            </p>
          </div>
        </div>
      </div>
    </header>
  )
}

export default Header