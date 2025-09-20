import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

export const fetchStatus = async () => {
  const response = await api.get('/status')
  return response.data
}

export const startAutomation = async () => {
  const response = await api.post('/start')
  if (window.addSystemLog) {
    window.addSystemLog('🚀 Automation started', 'success')
  }
  return response.data
}

export const stopAutomation = async () => {
  const response = await api.post('/stop')
  if (window.addSystemLog) {
    window.addSystemLog('⏹️ Automation stopped', 'info')
  }
  return response.data
}

export const addSampleJobs = async () => {
  const response = await api.post('/add-sample-jobs')
  if (window.addSystemLog) {
    window.addSystemLog('➕ Sample jobs added to queue', 'success')
  }
  return response.data
}

export const scrapeJobs = async () => {
  const response = await api.post('/scrape', {
    searchTerms: ['software engineer', 'data engineer'],
    locations: ['Remote', 'San Francisco']
  })
  if (window.addSystemLog) {
    window.addSystemLog('🔍 Job scraping initiated', 'info')
  }
  return response.data
}

export const getJobQueue = async () => {
  const response = await api.get('/queue')
  return response.data
}

export const deleteJob = async (jobId) => {
  const response = await api.delete(`/jobs/${jobId}`)
  if (window.addSystemLog) {
    window.addSystemLog(`🗑️ Job ${jobId} removed from queue`, 'info')
  }
  return response.data
}