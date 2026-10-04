import React, { useState, useEffect } from 'react';
import './RiderApp.css';

const MOCK_RIDER_ID = "RDR-001";

export default function RiderApp() {
  const [manifest, setManifest] = useState(null);
  const [myDay, setMyDay] = useState(null);
  const [activeTab, setActiveTab] = useState('manifest'); // manifest or myday
  const [loading, setLoading] = useState(true);

  const [toastMsg, setToastMsg] = useState(null);

  const showToast = (msg) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 4000);
  };

  const fetchRiderData = async (showLoader = false) => {
    if (showLoader) setLoading(true);
    try {
      const [manifestRes, myDayRes] = await Promise.all([
        fetch(`/api/rider/manifest/${MOCK_RIDER_ID}`),
        fetch(`/api/rider/myday/${MOCK_RIDER_ID}`)
      ]);
      const manifestData = await manifestRes.json();
      const myDayData = await myDayRes.json();
      setManifest(manifestData);
      setMyDay(myDayData);
    } catch (e) {
      console.error(e);
    } finally {
      if (showLoader) setLoading(false);
    }
  };

  useEffect(() => {
    fetchRiderData(true);
    const interval = setInterval(() => {
      fetchRiderData(false);
    }, 3500);
    return () => clearInterval(interval);
  }, []);

  const handleOutcome = async (orderId, outcome, reason = null) => {
    try {
      await fetch(`/api/rider/outcome/${MOCK_RIDER_ID}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ order_id: orderId, outcome, reason })
      });
      showToast(`Outcome saved: ${outcome}`);
      fetchRiderData(false);
    } catch (e) {
      console.error(e);
    }
  };

  const handleNudge = async (orderId) => {
    try {
      const res = await fetch(`/api/rider/nudge/${MOCK_RIDER_ID}/${orderId}`, {
        method: 'POST'
      });
      const data = await res.json();
      showToast(`🔔 Nudge sent to customer! Message delivered on WhatsApp.`);
      fetchRiderData(false);
    } catch (e) {
      console.error(e);
    }
  };

  const handleNudgeAll = async () => {
    try {
      const res = await fetch(`/api/rider/nudge-all/${MOCK_RIDER_ID}`, {
        method: 'POST'
      });
      const data = await res.json();
      showToast(`🔔 Morning Nudge sent to all ${data.nudged_count || 'active'} customers on WhatsApp!`);
      fetchRiderData(false);
    } catch (e) {
      console.error(e);
    }
  };

  const handleMissedCall = async (orderId) => {
    try {
      const res = await fetch(`/api/rider/missed-call/${MOCK_RIDER_ID}/${orderId}`, {
        method: 'POST'
      });
      const data = await res.json();
      showToast(`📵 Missed call logged (Attempt ${data.missed_call_count}/3). WhatsApp alert sent to customer!`);
      fetchRiderData(false);
    } catch (e) {
      console.error(e);
    }
  };

  const handleCallCustomer = (phone, name) => {
    window.location.href = `tel:${phone}`;
    showToast(`📞 Dialing ${name} (${phone})...`);
  };

  if (loading && !manifest) return <div className="rider-loading"><div className="loader"></div></div>;

  return (
    <div className="device-frame rider-pwa">
      {toastMsg && <div className="rider-toast">{toastMsg}</div>}
      
      <div className="rider-header">
        <div className="rider-profile">
          <div className="avatar">🛵</div>
          <div>
            <h2>Hi, {manifest?.rider_name || "Rider Amit"}</h2>
            <p>{manifest?.total_stops} Stops Today · Hub: VMC-DEL-01</p>
          </div>
          <button className="btn-refresh" onClick={() => fetchRiderData(false)} title="Refresh Sync">🔄</button>
        </div>

        {/* Morning Nudge All Action Banner */}
        <div className="morning-nudge-bar">
          <button className="btn-nudge-all" onClick={handleNudgeAll}>
            🔔 <strong>Morning Nudge All Customers</strong>
            <span>Send arrival notification & collect availability</span>
          </button>
        </div>
      </div>

      <div className="rider-tabs">
        <button 
          className={activeTab === 'manifest' ? 'active' : ''} 
          onClick={() => setActiveTab('manifest')}
        >
          My Stops ({manifest?.pending_stops ?? 0} Pending)
        </button>
        <button 
          className={activeTab === 'myday' ? 'active' : ''} 
          onClick={() => setActiveTab('myday')}
        >
          My Day Stats
        </button>
      </div>

      <div className="rider-content">
        {activeTab === 'manifest' && (
          <div className="manifest-list">
            {manifest?.stops.length === 0 ? (
              <div className="empty-state">No stops assigned today.</div>
            ) : (
              manifest?.stops.map((stop, i) => (
                <div key={stop.order_id} className={`rider-card ${stop.is_delivered ? 'delivered' : ''} ${stop.is_skipped ? 'skipped' : ''}`}>
                  <div className="rider-card-header">
                    <div className="stop-number">{i + 1}</div>
                    <div className="order-ids">
                      <strong>{stop.customer_full_name || stop.customer_first_name}</strong>
                      <span>{stop.awb} · {stop.product_name?.replace('[SIMULATED] ', '')}</span>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px' }}>
                      {stop.is_prepaid ? (
                        <span className="badge prepaid">PREPAID</span>
                      ) : (
                        <span className="badge cod">COD {stop.cash_to_collect}</span>
                      )}
                      <span className={`badge ${stop.payout === 30 ? 'bonus-payout' : 'standard-payout'}`} style={{
                        fontSize: '0.68rem',
                        fontWeight: 700,
                        background: stop.payout === 30 ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                        color: stop.payout === 30 ? '#ef4444' : '#10b981',
                        border: stop.payout === 30 ? '1px solid #ef4444' : '1px solid #10b981',
                        borderRadius: '4px',
                        padding: '2px 6px'
                      }}>
                        {stop.payout_label || `₹${stop.payout || 18}`}
                      </span>
                    </div>
                  </div>

                  <div className="rider-card-body">
                    {stop.original_address && stop.original_address !== stop.address ? (
                      <div className="address-comparison-box">
                        <div className="addr-row old">
                          <span className="addr-badge old">OLD ADDRESS</span>
                          <span className="addr-text old-text"><s>{stop.original_address}</s></span>
                        </div>
                        <div className="addr-row new">
                          <span className="addr-badge new">📍 NEW ADDRESS</span>
                          <strong className="addr-text new-text">{stop.address}</strong>
                        </div>
                      </div>
                    ) : (
                      <p className="address">📍 {stop.address}</p>
                    )}
                    <p className="landmark">Landmark: {stop.landmark}</p>
                    
                    {/* Live Customer Status Responses */}
                    <div className="customer-status-row">
                      {stop.customer_response_status === 'available_today' && (
                        <div className="response-tag available">
                          ✅ Customer Confirmed: Available Today
                        </div>
                      )}
                      {(stop.customer_response_status === 'rescheduled_tomorrow' || stop.is_skipped) && (
                        <div className="response-tag skipped">
                          🗓️ Customer Rescheduled: Deliver Tomorrow (Saved Dead Miles)
                        </div>
                      )}
                      {stop.customer_response_status === 'address_updated' && (
                        <div className="response-tag address-updated">
                          📍 Address Updated by Customer
                        </div>
                      )}
                      {stop.missed_call_count > 0 && (
                        <div className="response-tag missed-call">
                          ⚠️ Missed Call Logged: Attempt {stop.missed_call_count}/3
                        </div>
                      )}
                    </div>

                    {stop.customer_note && (
                      <div className="customer-note">
                        <strong>📝 Customer Note:</strong> {stop.customer_note}
                      </div>
                    )}
                    {stop.alternate_receiver && (
                      <div className="alternate-receiver-note">
                        <strong>👤 Alternate Receiver:</strong> {stop.alternate_receiver}
                      </div>
                    )}
                  </div>

                  {!stop.is_delivered && !stop.is_skipped && (
                    <div className="rider-card-actions">
                      <button className="btn-call-cust" onClick={() => handleCallCustomer(stop.customer_phone, stop.customer_first_name)}>
                        📞 Call
                      </button>
                      <button className="btn-nudge" onClick={() => handleNudge(stop.order_id)}>
                        🔔 Nudge
                      </button>
                      <button 
                        className={`btn-missed-call ${stop.missed_call_count >= 3 ? 'exhausted' : ''}`}
                        onClick={() => handleMissedCall(stop.order_id)}
                        title="Click if user did not answer call"
                      >
                        📵 No Answer ({stop.missed_call_count || 0}/3)
                      </button>
                      <button className="btn-success" onClick={() => handleOutcome(stop.order_id, 'Delivered')}>
                        ✓ Delivered
                      </button>
                      <div className="fail-dropdown">
                        <button className="btn-fail">✕ ▾</button>
                        <div className="dropdown-content">
                          <button onClick={() => handleOutcome(stop.order_id, 'Failed: not available')}>Not Available</button>
                          <button onClick={() => handleOutcome(stop.order_id, 'Failed: refused')}>Refused</button>
                          <button onClick={() => handleOutcome(stop.order_id, 'Failed: address issue')}>Address Issue</button>
                        </div>
                      </div>
                    </div>
                  )}

                  {stop.is_delivered && <div className="status-banner success">✓ Delivered Successfully</div>}
                  {stop.is_skipped && <div className="status-banner skipped">🗓️ Deferred to Tomorrow (No Dead Miles)</div>}
                </div>
              ))
            )}
          </div>
        )}


        {activeTab === 'myday' && myDay && (
          <div className="myday-stats">
            <div className="stats-hero glass-panel">
              <span className="sparkle">✨</span>
              <h3>You saved dead miles today!</h3>
              <p>{myDay.message}</p>
            </div>
            
            <div className="stats-grid">
              <div className="stat-box">
                <div className="stat-val">{myDay.delivered_stops}</div>
                <div className="stat-label">Delivered</div>
              </div>
              <div className="stat-box">
                <div className="stat-val">{myDay.pending_stops}</div>
                <div className="stat-label">Pending</div>
              </div>
              <div className="stat-box highlight">
                <div className="stat-val">{myDay.stops_skipped_by_customer}</div>
                <div className="stat-label">Pre-Cancelled</div>
              </div>
              <div className="stat-box highlight-cash">
                <div className="stat-val">{myDay.cash_collected_today}</div>
                <div className="stat-label">Cash Collected</div>
              </div>
            </div>

            <div className="dead-mile-counter">
              <h4>Dead Mile Savings</h4>
              <div className="savings-row">
                <span>Distance Saved:</span>
                <strong>{myDay.dead_km_saved}</strong>
              </div>
              <div className="savings-row">
                <span>Petrol & Effort Value:</span>
                <strong className="money">{myDay.rupees_saved}</strong>
              </div>
              <p className="caption">Thanks to Valmo Mitra checking with customers before you ride!</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
