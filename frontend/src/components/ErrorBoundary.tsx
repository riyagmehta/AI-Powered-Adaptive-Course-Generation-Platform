import { Component, type ErrorInfo, type ReactNode } from 'react'

interface ErrorBoundaryProps {
  children: ReactNode
}

interface ErrorBoundaryState {
  error: Error | null
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Unhandled error in component tree:', error, info.componentStack)
  }

  handleReset = () => {
    this.setState({ error: null })
    window.location.assign('/dashboard')
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-slate-50 px-4 text-center">
          <h1 className="text-lg font-semibold text-slate-900">Something went wrong</h1>
          <p className="max-w-sm text-sm text-slate-500">
            An unexpected error occurred while rendering this page. You can try going back to the dashboard.
          </p>
          <pre className="max-w-md overflow-x-auto rounded-md bg-slate-100 px-3 py-2 text-left text-xs text-slate-500">
            {this.state.error.message}
          </pre>
          <button
            onClick={this.handleReset}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
          >
            Back to dashboard
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
