// A full-page error with a button to reload.
const ErrorScreen = ({ message }: { message: string }) => (
  <div style={{
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
    alignItems: 'center',
    height: '100vh',
    fontSize: '1.2rem',
    color: '#d32f2f'
  }}>
    <p>Error: {message}</p>
    <button onClick={() => window.location.reload()} style={{ marginTop: '1rem' }}>
      Retry
    </button>
  </div>
);

export default ErrorScreen;
