import React, { useState, useEffect, useRef } from 'react';
import './CustomerChat.css';

// === DEMO USERS — all 14 served by RDR-001 (Amit) at VMC-DEL-01, Rohini Delhi ===
const DEMO_USERS = [
  {
    name: "Priya Sharma",
    phone: "9198765001",
    phone_hash: "f855b2ec33339e4b",
    category: "active",
    scenario: "IN_TRANSIT · COD ₹449",
    tip: "Try: 'kahan hai mera order?' or 'track karo'",
    color: "#10b981",
    quickMessages: ["kahan hai mera order?", "Track karo", "Status batao"],
  },
  {
    name: "Rahul Verma",
    phone: "9198765002",
    phone_hash: "44a7469deed95dfa",
    category: "active",
    scenario: "OUT_FOR_DELIVERY · HIGH Risk",
    tip: "Try: 'rider kab aayega?' or 'gate par note likhdo'",
    color: "#3b82f6",
    quickMessages: ["rider kab aayega?", "Rider ko call karwao", "gate locked hai, call karo aane se pehle"],
  },
  {
    name: "Anita Patel",
    phone: "9198765003",
    phone_hash: "d3aba319ff24da92",
    category: "failed",
    scenario: "FAILED_ATTEMPT · Reschedule",
    tip: "Try: 'aaj delivery kyun nahi hui?' or 'kal rescheduled karo'",
    color: "#f59e0b",
    quickMessages: ["aaj delivery kyun nahi hui?", "Kal shaam 4 baje ke baad deliver karo", "Callback chahiye"],
  },
  {
    name: "Suresh Kumar",
    phone: "9198765004",
    phone_hash: "2da161fd74c17eb8",
    category: "active",
    scenario: "AT_HUB · COD ₹1299 (Online pay)",
    tip: "Try: 'online pay karna hai' or 'payment link bhejo'",
    color: "#8b5cf6",
    quickMessages: ["online pay karna hai", "Payment link bhejo", "COD ke badle UPI se pay kar sakta hoon?"],
  },
  {
    name: "Meena Devi",
    phone: "9198765005",
    phone_hash: "9c7e3945db6acfb8",
    category: "escalated",
    scenario: "RESCHEDULED x2 · HIGH Risk (Angry)",
    tip: "Try: 'yeh kab aayega?' multiple times — triggers escalation flow",
    color: "#ef4444",
    quickMessages: ["yeh kab aayega?", "2 baar ho gaya, kab deliver hoga?", "Cancel karna hai mujhe"],
  },
  {
    name: "Vikram Singh",
    phone: "9198765006",
    phone_hash: "01bc0cf8c7ded7f2",
    category: "active",
    scenario: "OUT_FOR_DELIVERY · Same-Pin Address",
    tip: "Try: 'mera address change kar do Sector 9 mein House 12'",
    color: "#06b6d4",
    quickMessages: ["Mera address update kar do", "House 12, Block C, Sector 9 Rohini deliver karna", "Address galat hai"],
  },
  {
    name: "Deepa Joshi",
    phone: "9198765007",
    phone_hash: "14f7c36e478b5803",
    category: "active",
    scenario: "OUT_FOR_DELIVERY · Neighbour",
    tip: "Try: 'main ghar pe nahi hoon, padosi ko de do'",
    color: "#ec4899",
    quickMessages: ["Padosi Sharma ji (Flat 204) ko de do", "Ghar par koi nahi hai", "Security guard ko package de dena"],
  },
  {
    name: "Arjun Malhotra",
    phone: "9198765008",
    phone_hash: "3b901121fcc7c09d",
    category: "failed",
    scenario: "FAILED_ATTEMPT · 2 Missed Calls",
    tip: "Try: 'mujhe call nahi aaya' or 'reschedule kar do'",
    color: "#f97316",
    quickMessages: ["Rider ne call nahi kiya", "Kal deliver karo", "Rider ka number do"],
  },
  {
    name: "Sunita Rao",
    phone: "9198765009",
    phone_hash: "e6105ff0cb2b608d",
    category: "active",
    scenario: "OUT_FOR_DELIVERY · PREPAID",
    tip: "Try: 'kahan tak pahuncha?' or 'live tracking'",
    color: "#14b8a6",
    quickMessages: ["Kahan tak pahuncha?", "Kitna time lagega?", "OTP kya hai?"],
  },
  {
    name: "Ramesh Gupta",
    phone: "9198765010",
    phone_hash: "7e730bd451bb72a2",
    category: "active",
    scenario: "AT_HUB · COD ₹1899",
    tip: "Try: 'UPI QR code se pay karna hai'",
    color: "#6366f1",
    quickMessages: ["Payment link bhejo", "Ghar par cash nahi hai", "Online pay kaise karein?"],
  },
  {
    name: "Kavita Sharma",
    phone: "9198765011",
    phone_hash: "06e9cad701be8104",
    category: "failed",
    scenario: "RESCHEDULED x1 · Worried",
    tip: "Try: 'aaj pakka aayega kya?'",
    color: "#a855f7",
    quickMessages: ["Aaj pakka deliver hoga?", "Time slot batao", "Call rider"],
  },
  {
    name: "Mohan Lal",
    phone: "9198765012",
    phone_hash: "9e6fea52c7840b9f",
    category: "active",
    scenario: "OUT_FOR_DELIVERY · Far Zone (₹30 Bonus)",
    tip: "Try: 'Outer ring road ke pass hai'",
    color: "#e11d48",
    quickMessages: ["Outer ring road ke pass aake call karo", "Gate 2 se entry hai", "Available Today"],
  },
  {
    name: "Geeta Pandey",
    phone: "9198765013",
    phone_hash: "e8e40d76d9f45c09",
    category: "failed",
    scenario: "FAILED_ATTEMPT · Self Pickup",
    tip: "Try: 'kya main hub se khud le sakti hoon?'",
    color: "#d97706",
    quickMessages: ["Hub se khud collect karna hai", "Serving center ka timing kya hai?", "Rohini center kahan hai?"],
  },
  {
    name: "Sanjay Tiwari",
    phone: "9198765014",
    phone_hash: "7f307f5a24bdff81",
    category: "active",
    scenario: "OUT_FOR_DELIVERY · Gate Note",
    tip: "Try: 'delivery note add karo: ring bell twice'",
    color: "#475569",
    quickMessages: ["Gate locked hai, bell 2 baar bajana", "Delivery instructions add karo", "Available Today"],
  },
];

export default function CustomerChat() {
  const [activeUserIdx, setActiveUserIdx] = useState(0);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [orders, setOrders] = useState([]);
  const [sessionId, setSessionId] = useState('');
  const [filterCategory, setFilterCategory] = useState('all');
  const [resetting, setResetting] = useState(false);

  const messagesEndRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const isAtBottomRef = useRef(true);

  const activeUser = DEMO_USERS[activeUserIdx];

  const handleScroll = () => {
    if (!messagesContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = messagesContainerRef.current;
    // Considered at bottom if within 80px of bottom
    isAtBottomRef.current = scrollHeight - scrollTop - clientHeight < 80;
  };

  const scrollToBottom = (behavior = "smooth") => {
    messagesEndRef.current?.scrollIntoView({ behavior });
  };

  const handleCallRider = () => {
    window.location.href = 'tel:+919876500000';
    setMessages(prev => [...prev, {
      role: 'system',
      content: `[SIMULATED DIALER] Opening native dialer for Rider Amit (+91 98765 00000)...`
    }]);
    isAtBottomRef.current = true;
    scrollToBottom();
  };

  const handleResetDemo = async () => {
    if (resetting) return;
    setResetting(true);
    try {
      await fetch('/api/chat/demo/reset', { method: 'POST' });
      startSession(activeUser);
    } catch (e) {
      console.error(e);
    } finally {
      setResetting(false);
    }
  };

  const startSession = (user) => {
    const newSessionId = `sess_${user.phone}_${Date.now()}`;
    setSessionId(newSessionId);
    setMessages([{ role: 'system', content: `[SIMULATED] Chat started as ${user.name} (${user.phone})` }]);
    setOrders([]);
    isAtBottomRef.current = true;

    fetch(`/api/chat/session/start/${user.phone_hash}`)
      .then(res => res.json())
      .then(data => {
        if (data.orders) setOrders(data.orders);
        if (data.session_id) setSessionId(data.session_id);
        
        if (data.session_id) {
          fetch(`/api/chat/history/${data.session_id}`)
            .then(r => r.json())
            .then(h => {
              if (h.messages && h.messages.length > 0) {
                setMessages(prev => [
                  prev[0],
                  ...h.messages.map(m => ({
                    role: m.role,
                    content: m.content,
                    buttons: m.buttons
                  }))
                ]);
              } else {
                setMessages(prev => [...prev, {
                  role: 'assistant',
                  content: `Namaste ${user.name.split(' ')[0]}! Main Valmo Mitra hoon. Aapki delivery ke baare mein kya madad kar sakta hoon? 😊`,
                  buttons: [
                    { id: 'btn_status', title: '📦 Track Order' },
                    { id: 'btn_available_today', title: '✅ Available Today' },
                    { id: 'btn_call_rider', title: '📞 Call Rider' }
                  ]
                }]);
              }
              setTimeout(() => scrollToBottom("auto"), 50);
            });
        }
      })
      .catch(() => {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: 'Namaste! Main Valmo Mitra hoon. Backend se connect ho raha hoon...'
        }]);
      });
  };

  // Periodic history sync that respects user scroll position and doesn't flicker
  const syncHistory = () => {
    if (!sessionId) return;
    fetch(`/api/chat/history/${sessionId}`)
      .then(r => r.json())
      .then(h => {
        if (h.messages && h.messages.length > 0) {
          setMessages(prev => {
            const systemMsg = prev[0]?.role === 'system' ? [prev[0]] : [];
            const newHistory = [
              ...systemMsg,
              ...h.messages.map(m => ({
                role: m.role,
                content: m.content,
                buttons: m.buttons
              }))
            ];
            // Only update state if message count or last message changed
            if (prev.length === newHistory.length && 
                prev[prev.length - 1]?.content === newHistory[newHistory.length - 1]?.content) {
              return prev;
            }
            return newHistory;
          });
        }
      })
      .catch(() => {});
  };

  useEffect(() => {
    startSession(activeUser);
  }, [activeUserIdx]);

  useEffect(() => {
    const interval = setInterval(syncHistory, 3000);
    return () => clearInterval(interval);
  }, [sessionId]);

  // Auto-scroll ONLY when user was already near the bottom
  useEffect(() => {
    if (isAtBottomRef.current) {
      scrollToBottom("smooth");
    }
  }, [messages, loading]);

  const switchUser = (idx) => {
    if (idx === activeUserIdx) return;
    isAtBottomRef.current = true;
    setActiveUserIdx(idx);
  };

  const sendMessage = async (text, isButton = false, buttonId = '', messageType = 'text') => {
    if (!text.trim() || loading) return;
    
    if (text.includes("Open Dialer") || text.includes("Call Rider") || text.includes("Call Rider Back")) {
      handleCallRider();
    }

    const userMsg = { role: 'user', content: text, isButton };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);
    isAtBottomRef.current = true;
    setTimeout(() => scrollToBottom("smooth"), 20);

    try {
      const response = await fetch('/api/chat/message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          phone_hash: activeUser.phone_hash,
          message: text,
          message_type: isButton ? 'button_reply' : messageType,
          button_payload: buttonId || (isButton ? text : '')
        })
      });
      const data = await response.json();
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.reply || 'Sorry, kuch problem aa rahi hai.',
        buttons: data.buttons
      }]);
    } catch (error) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: "Network error. Backend se connect nahi ho pa raha."
      }]);
    } finally {
      setLoading(false);
      isAtBottomRef.current = true;
      setTimeout(() => scrollToBottom("smooth"), 50);
    }
  };

  const sendAudio = () => {
    // Browser audio capture is intentionally mocked; the visible text is the
    // speech-to-text transcript sent with message_type=audio.
    const transcript = input.trim() || 'Bhaiya main 5 baje aaunga parcel padosi ko de dena';
    sendMessage(`🎤 ${transcript}`, false, '', 'audio');
  };

  const filteredUsers = DEMO_USERS.filter(u => {
    if (filterCategory === 'all') return true;
    return u.category === filterCategory;
  });

  return (
    <div className="wa-layout">
      {/* Left Drawer: User Switcher + Order Context */}
      <div className="wa-drawer">
        <div className="wa-drawer-header">
          <div>
            <h3>Demo Customers ({DEMO_USERS.length})</h3>
            <p className="wa-drawer-subtitle">All assigned to Rider Amit (RDR-001) · Rohini</p>
          </div>
          <button 
            className="btn-demo-reset" 
            onClick={handleResetDemo} 
            disabled={resetting}
            title="Reset demo data to fresh state"
          >
            {resetting ? '⏳' : '🔄 Reset'}
          </button>
        </div>

        {/* Category Filters */}
        <div className="user-filter-tabs">
          <button className={filterCategory === 'all' ? 'active' : ''} onClick={() => setFilterCategory('all')}>All (14)</button>
          <button className={filterCategory === 'active' ? 'active' : ''} onClick={() => setFilterCategory('active')}>Active (8)</button>
          <button className={filterCategory === 'failed' ? 'active' : ''} onClick={() => setFilterCategory('failed')}>Failed/Rescheduled (5)</button>
          <button className={filterCategory === 'escalated' ? 'active' : ''} onClick={() => setFilterCategory('escalated')}>Escalated (1)</button>
        </div>

        <div className="user-switcher">
          {filteredUsers.map((user) => {
            const originalIdx = DEMO_USERS.findIndex(u => u.phone_hash === user.phone_hash);
            return (
              <button
                key={user.phone_hash}
                className={`user-card ${originalIdx === activeUserIdx ? 'active' : ''}`}
                onClick={() => switchUser(originalIdx)}
                style={{ '--user-color': user.color }}
              >
                <div className="user-avatar" style={{ background: user.color }}>
                  {user.name.charAt(0)}
                </div>
                <div className="user-info">
                  <strong>{user.name}</strong>
                  <span>{user.scenario}</span>
                </div>
                {originalIdx === activeUserIdx && <span className="active-dot">●</span>}
              </button>
            );
          })}
        </div>

        <div className="scenario-tip">
          <div className="tip-label">💡 Scenario Quick-Try</div>
          <p>{activeUser.tip}</p>
          <div className="quick-chip-list">
            {activeUser.quickMessages?.map((qm, i) => (
              <button key={i} className="quick-chip" onClick={() => sendMessage(qm)}>
                {qm}
              </button>
            ))}
          </div>
        </div>

        <div className="wa-doorbell-sim">
          <h4>Smart Actions</h4>
          <div className="action-button-grid">
            <button onClick={() => sendMessage("Available Today", true, "btn_available_today")}>
              ✅ Available Today
            </button>
            <button onClick={() => sendMessage("Kal deliver karo", true, "btn_not_today")}>
              🔄 Kal Deliver Karein
            </button>
            <button onClick={() => sendMessage("Mera address Sector 9 mein House 12 change kar do", true, "btn_change_address")}>
              📍 Change Address
            </button>
            <button onClick={() => sendMessage("Padosi Sharma ji (Flat 204) ko de do", true, "btn_leave_neighbor")}>
              🏠 Leave with Neighbor
            </button>
            <button onClick={() => handleCallRider()}>
              📞 Call Rider Amit
            </button>
          </div>
        </div>

        {orders.length > 0 && (
          <div className="order-context">
            <h4>Active Orders ({orders.length})</h4>
            {orders.map(o => (
              <div key={o.order_id} className="wa-order-card">
                <div className="wa-order-header">
                  <strong>{o.order_id}</strong>
                  <span className={`badge ${
                    o.status?.includes('DELIVERED') ? 'success' :
                    o.status?.includes('OUT') ? 'info' :
                    o.status?.includes('FAILED') ? 'error' : 'medium'
                  }`}>{o.status?.replace(/_/g, ' ')}</span>
                </div>
                <p className="wa-order-title">{o.product_name?.replace('[SIMULATED] ', '')}</p>
                <p className="wa-order-amount">₹{o.amount}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* WhatsApp Device Simulator */}
      <div className="device-frame">
        <div className="wa-header" style={{ background: `linear-gradient(135deg, ${activeUser.color}cc, #075e54)` }}>
          <div className="wa-avatar-header">
            {activeUser.name.charAt(0)}
          </div>
          <div className="wa-header-info">
            <h2>Meesho Valmo <span className="wa-verified">✓</span></h2>
            <p>Simulated as: {activeUser.name} · {activeUser.phone}</p>
          </div>
          <div className="wa-header-actions" style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button className="wa-call-rider-btn" onClick={handleCallRider} title="Call Rider Amit directly">
              📞 Call Rider
            </button>
            <span className="badge simulated" style={{ flexShrink: 0 }}>SIMULATED</span>
          </div>
        </div>

        <div className="wa-messages" ref={messagesContainerRef} onScroll={handleScroll}>
          {messages.map((m, idx) => (
            <div key={idx} className={`wa-msg-wrapper ${m.role}`}>
              {m.role === 'system' ? (
                <div className="wa-msg-system">{m.content}</div>
              ) : (
                <div className={`wa-bubble ${m.role}`}>
                  <div className="wa-bubble-content">{m.content}</div>
                  {m.buttons && m.buttons.length > 0 && (
                    <div className="wa-buttons">
                      {m.buttons.map(btn => (
                        <button key={btn.id} onClick={() => sendMessage(btn.title, true, btn.id)}>
                          {btn.title}
                        </button>
                      ))}
                    </div>
                  )}
                  <div className="wa-time">
                    {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    {m.role === 'user' && <span className="wa-tick">✓✓</span>}
                  </div>
                </div>
              )}
            </div>
          ))}
          {loading && (
            <div className="wa-msg-wrapper assistant">
              <div className="wa-bubble assistant typing">
                <span className="dot"></span><span className="dot"></span><span className="dot"></span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="wa-input-area">
          <button className="wa-icon-btn" title="Simulated Attachment">📎</button>
          <input
            type="text"
            placeholder={`Message as ${activeUser.name.split(' ')[0]}...`}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && sendMessage(input)}
            disabled={loading}
          />
          <button className="wa-icon-btn" onClick={() => input.trim() ? sendMessage(input) : sendAudio()} disabled={loading}>
            {loading ? '⏳' : input.trim() ? '➤' : '🎤'}
          </button>
        </div>
      </div>
    </div>
  );
}
