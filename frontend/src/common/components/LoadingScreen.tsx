// Full-page placeholder shown while auth or a lazily loaded section is loading.
export default function LoadingScreen() {
  return (
    <div style={{ 
      display: 'flex', 
      justifyContent: 'center', 
      alignItems: 'center', 
      height: '100vh',
      fontSize: '1.5rem'
    }}>
      Loading...
    </div>
  );
}

