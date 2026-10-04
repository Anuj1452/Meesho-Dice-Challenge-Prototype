import React, { useState, useEffect } from 'react';
import './OpsDashboard.css';

const MOCK_HUB = "VMC-DEL-01";

export default function OpsDashboard() {
  const [metrics, setMetrics] = useState(null);
  const [queue, setQueue] = useState([]);
  const [pendingActions, setPendingActions] = useState([]);
  const [copilotInput, setCopilotInput] = useState('');
  const [chatLog, setChatLog] = useState([
    { role: 'assistant', text: 'Ops Copilot ready. I can explain risk scores, fetch bundles, or propose actions.' }
  ]);
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [caseBundle, setCaseBundle] = useState(null);

  const fetchDashboardData = async () => {
    try {
      const [metRes, qRes, actRes] = await Promise.all([
        fetch(`/api/ops/metrics/${MOCK_HUB}`),
        fetch(`/api/ops/queue/${MOCK_HUB}`),
        fetch(`/api/ops/pending-actions`)
      ]);
      setMetrics(await metRes.json());
      
      const qData = await qRes.json();
      setQueue(qData.queue || []);
      
      const actData = await actRes.json();
      setPendingActions(actData.actions || []);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchDashboardData();
    // Simulate SSE polling or simple refresh for prototype
    const interval = setInterval(fetchDashboardData, 10000);
    return () => clearInterval(interval);
  }, []);

  const loadCase = async (orderId) => {
    setSelectedOrder(orderId);
    try {
      const res = await fetch(`/api/ops/case/${orderId}`);
      setCaseBundle(await res.json());
    } catch (e) {
      console.error(e);
    }
  };

  const sendCopilotMsg = async () => {
    if (!copilotInput.trim()) return;
    const msg = copilotInput;
    setCopilotInput('');
    setChatLog(prev => [...prev, { role: 'user', text: msg }]);

    try {
      const res = await fetch(`/api/ops/copilot/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg, order_id: selectedOrder, hub_id: MOCK_HUB })
      });
      const data = await res.json();
      setChatLog(prev => [...prev, { role: 'assistant', text: data.reply }]);
      fetchDashboardData(); // Refresh actions if copilot proposed one
    } catch (e) {
      console.error(e);
    }
  };

  const resolveAction = async (proposalId, approved) => {
    try {
      await fetch(`/api/ops/pending-actions/${proposalId}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approved, reviewer: "Ops Dashboard User" })
      });
      fetchDashboardData();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="ops-dashboard">
      {/* Left Sidebar: Metrics & Queue */}
      <div className="ops-sidebar">
        <div className="ops-panel metrics-panel">
          <h3>{metrics?.hub_name || 'Hub Metrics'}</h3>
          <div className="metrics-grid">
            <div className="metric-box">
              <span className="val error-text">{metrics?.metrics?.rto_percentage || '-'}</span>
              <span className="lbl">RTO %</span>
            </div>
            <div className="metric-box">
              <span className="val">{metrics?.metrics?.attempts_per_delivery || '-'}</span>
              <span className="lbl">Att/Del</span>
            </div>
            <div className="metric-box">
              <span className="val">{metrics?.metrics?.dispute_rate || '-'}</span>
              <span className="lbl">Disputes</span>
            </div>
          </div>
          {metrics?.flags && metrics.flags.map((f, i) => (
            <div key={i} className="hub-flag">⚠️ {f}</div>
          ))}
        </div>

        <div className="ops-panel queue-panel">
          <h3>Review Queue <span className="badge">{queue.length}</span></h3>
          <div className="queue-list">
            {queue.map(q => (
              <div 
                key={q.case_id} 
                className={`queue-item ${selectedOrder === q.order_id ? 'active' : ''}`}
                onClick={() => loadCase(q.order_id)}
              >
                <div className="q-header">
                  <strong>{q.order_id}</strong>
                  <span className={`badge ${q.severity.toLowerCase()}`}>{q.severity}</span>
                </div>
                <p className="q-reason">{q.flag_reason}</p>
                <span className="q-rider">Rider: {q.rider_name}</span>
              </div>
            ))}
            {queue.length === 0 && <p className="empty-text">Queue is empty</p>}
          </div>
        </div>
      </div>

      {/* Main Center: Case Inspector */}
      <div className="ops-main">
        {caseBundle ? (
          <div className="ops-panel case-inspector">
            <div className="case-header">
              <h2>Order {caseBundle.order_id}</h2>
              <span className={`badge ${caseBundle.order_details.risk_tier}`}>
                Risk: {caseBundle.order_details.risk_tier.toUpperCase()}
              </span>
            </div>
            
            <div className="case-details-grid">
              <div className="detail-col">
                <h4>Customer</h4>
                <p><strong>Name:</strong> {caseBundle.customer.name}</p>
                <p><strong>Address:</strong> {caseBundle.order_details.address}</p>
                <p><strong>Pin:</strong> {caseBundle.order_details.pincode}</p>
              </div>
              <div className="detail-col">
                <h4>Order</h4>
                <p><strong>Product:</strong> {caseBundle.order_details.product}</p>
                <p><strong>Amount:</strong> {caseBundle.order_details.amount} ({caseBundle.order_details.payment_mode})</p>
                <p><strong>Status:</strong> {caseBundle.order_details.current_status}</p>
              </div>
            </div>

            <div className="case-timeline">
              <h4>Timeline & Audits</h4>
              <div className="timeline-list">
                {caseBundle.timeline.map((t, i) => (
                  <div key={i} className="timeline-item">
                    <div className="t-time">{new Date(t.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</div>
                    <div className="t-content">
                      <strong>{t.status}</strong>
                      <p>{t.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="ops-empty-state">
            Select a case from the queue to inspect.
          </div>
        )}
      </div>

      {/* Right Sidebar: Copilot & Actions */}
      <div className="ops-right-sidebar">
        <div className="ops-panel pending-actions">
          <h3>Pending Approvals <span className="badge">{pendingActions.length}</span></h3>
          <div className="action-list">
            {pendingActions.map(act => (
              <div key={act.proposal_id} className="action-card">
                <div className="ac-header">
                  <strong>{act.action_type.replace('_', ' ').toUpperCase()}</strong>
                  <span>{act.order_id}</span>
                </div>
                <p>{act.rationale}</p>
                <div className="ac-buttons">
                  <button className="btn-approve" onClick={() => resolveAction(act.proposal_id, true)}>✓ Approve</button>
                  <button className="btn-reject" onClick={() => resolveAction(act.proposal_id, false)}>✕ Reject</button>
                </div>
              </div>
            ))}
            {pendingActions.length === 0 && <p className="empty-text">No pending actions</p>}
          </div>
        </div>

        <div className="ops-panel copilot-panel">
          <div className="copilot-header">
            <h3>🤖 Ops Copilot</h3>
          </div>
          <div className="copilot-chat">
            {chatLog.map((m, i) => (
              <div key={i} className={`cp-msg ${m.role}`}>
                {m.text}
              </div>
            ))}
          </div>
          <div className="copilot-input">
            <input 
              type="text" 
              placeholder="Ask copilot..." 
              value={copilotInput}
              onChange={e => setCopilotInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && sendCopilotMsg()}
            />
            <button onClick={sendCopilotMsg}>➤</button>
          </div>
        </div>
      </div>
    </div>
  );
}
