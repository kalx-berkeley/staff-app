import { Component, type ErrorInfo, type ReactNode } from 'react';
import ErrorScreen from './ErrorScreen';

interface Props {
  children: ReactNode;
}

interface State {
  failed: boolean;
}

// Without a boundary, an error while rendering (or a page's code failing to
// load) leaves a blank page, with nothing telling the user to reload.
class ErrorBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Page failed to render:', error, info.componentStack);
  }

  render() {
    if (this.state.failed) {
      return <ErrorScreen message="Something went wrong showing this page." />;
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
