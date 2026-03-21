export function Navbar() {
  return (
    <header style={{ background: 'rgba(8,8,16,0.85)', backdropFilter: 'blur(16px)', borderBottom: '1px solid rgba(108,99,255,0.12)' }}
      className="fixed top-0 left-0 right-0 z-50 h-14 flex items-center px-6">
      <div className="flex items-center gap-2 flex-1">
        <span className="text-xl font-extrabold" style={{ fontFamily: 'Syne, sans-serif', color: '#6C63FF' }}>
          Fan<span style={{ color: '#00E5FF' }}>Frame</span>
        </span>
        <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#6C63FF', boxShadow: '0 0 8px #6C63FF', animation: 'pulse 2s infinite', display: 'inline-block' }} />
      </div>
      <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'linear-gradient(135deg,#6C63FF,#00E5FF)', display:'flex', alignItems:'center', justifyContent:'center', fontSize: 13, fontWeight: 600, color: '#fff' }}>
        FF
      </div>
    </header>
  )
}
