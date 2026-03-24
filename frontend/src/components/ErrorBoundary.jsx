import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error, info) {
    console.error('Uncaught error:', error, info)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '2rem' }}>
          <p className="error-message">
            Something went wrong.{' '}
            <button
              onClick={() => window.location.reload()}
              style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', textDecoration: 'underline', padding: 0, font: 'inherit' }}
            >
              Refresh the page
            </button>
          </p>
        </div>
      )
    }
    return this.props.children
  }
}
