import React, { useState, useEffect, useCallback } from 'react';
import { listDrafts, approveDraft, discardDraft, sendDraft } from '../client/bridge_client';

const cardStyle: React.CSSProperties = {
    border: '1px solid var(--center-channel-color-16)',
    borderRadius: '6px',
    padding: '16px',
    marginBottom: '16px',
    background: 'var(--center-channel-bg)',
};

const labelStyle: React.CSSProperties = {
    fontSize: '11px',
    fontWeight: 700,
    textTransform: 'uppercase',
    color: 'var(--center-channel-color-56)',
    letterSpacing: '0.06em',
    marginBottom: '4px',
};

const DraftCard: React.FC<{ draft: any; onRefresh: () => void }> = ({ draft, onRefresh }) => {
    const [editText, setEditText] = useState('');
    const [editing, setEditing] = useState(false);
    const [busy, setBusy] = useState(false);
    const [msg, setMsg] = useState('');

    const act = async (fn: () => Promise<any>) => {
        setBusy(true);
        setMsg('');
        try { await fn(); onRefresh(); }
        catch (e: any) { setMsg(e.message || 'Error'); }
        finally { setBusy(false); }
    };

    return (
        <div style={cardStyle}>
            <div style={labelStyle}>Trigger</div>
            <p style={{ fontStyle: 'italic', color: 'var(--center-channel-color-72)', fontSize: '13px', margin: '0 0 12px' }}>
                "{draft.trigger_text}"
            </p>

            <div style={labelStyle}>Draft reply</div>
            <p style={{ margin: '0 0 8px', color: 'var(--center-channel-color)', fontSize: '14px', lineHeight: '1.5' }}>
                {draft.reply}
            </p>

            {draft.provenance?.length > 0 && (
                <>
                    <div style={labelStyle}>Sources</div>
                    <ul style={{ margin: '0 0 12px', paddingLeft: '18px', fontSize: '12px', color: 'var(--center-channel-color-72)' }}>
                        {draft.provenance.map((s: string, i: number) => <li key={i}>{s}</li>)}
                    </ul>
                </>
            )}

            {draft.reason && (
                <div style={{ fontSize: '12px', color: 'var(--center-channel-color-56)', marginBottom: '12px' }}>
                    {draft.reason}
                </div>
            )}

            {editing ? (
                <>
                    <div style={labelStyle}>Your reply</div>
                    <textarea
                        value={editText}
                        onChange={e => setEditText(e.target.value)}
                        rows={4}
                        style={{
                            width: '100%', boxSizing: 'border-box', resize: 'vertical',
                            border: '1px solid var(--center-channel-color-24)',
                            borderRadius: '4px', padding: '8px', fontSize: '14px',
                            background: 'var(--center-channel-bg)',
                            color: 'var(--center-channel-color)',
                            marginBottom: '8px',
                        }}
                    />
                    <div style={{ display: 'flex', gap: '8px' }}>
                        <button disabled={busy || !editText.trim()} onClick={() => act(() => sendDraft(draft.id, editText))} style={btnStyle('primary')}>Send</button>
                        <button disabled={busy} onClick={() => setEditing(false)} style={btnStyle('ghost')}>Cancel</button>
                    </div>
                </>
            ) : (
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    <button disabled={busy} onClick={() => act(() => approveDraft(draft.id))} style={btnStyle('primary')}>Approve</button>
                    <button disabled={busy} onClick={() => { setEditText(draft.reply); setEditing(true); }} style={btnStyle('secondary')}>Write your own</button>
                    <button disabled={busy} onClick={() => act(() => discardDraft(draft.id))} style={btnStyle('danger')}>Discard</button>
                </div>
            )}
            {msg && <div style={{ marginTop: '8px', color: 'var(--error-text)', fontSize: '12px' }}>{msg}</div>}
        </div>
    );
};

function btnStyle(variant: 'primary' | 'secondary' | 'danger' | 'ghost'): React.CSSProperties {
    const base: React.CSSProperties = {
        border: 'none', borderRadius: '4px', padding: '6px 14px',
        cursor: 'pointer', fontWeight: 600, fontSize: '13px',
    };
    if (variant === 'primary') return { ...base, background: 'var(--button-bg)', color: 'var(--button-color)' };
    if (variant === 'secondary') return { ...base, background: 'var(--center-channel-color-08)', color: 'var(--center-channel-color)' };
    if (variant === 'danger') return { ...base, background: 'var(--error-text)', color: '#fff' };
    return { ...base, background: 'transparent', color: 'var(--center-channel-color-72)' };
}

const DraftingRHS: React.FC = () => {
    const [drafts, setDrafts] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [err, setErr] = useState('');

    const load = useCallback(async () => {
        setLoading(true);
        setErr('');
        try { setDrafts(await listDrafts()); }
        catch (e: any) { setErr(e.message || 'Failed to load drafts'); }
        finally { setLoading(false); }
    }, []);

    useEffect(() => { load(); }, [load]);

    return (
        <div style={{ padding: '20px', fontFamily: 'var(--font-family)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
                <h3 style={{ margin: 0, fontSize: '16px', color: 'var(--center-channel-color)' }}>✏️ AEGIS Drafts</h3>
                <button onClick={load} disabled={loading} style={btnStyle('ghost')}>↻</button>
            </div>
            {loading && <p style={{ color: 'var(--center-channel-color-56)' }}>Loading…</p>}
            {err && <p style={{ color: 'var(--error-text)' }}>{err}</p>}
            {!loading && !err && drafts.length === 0 && (
                <p style={{ color: 'var(--center-channel-color-56)', fontSize: '14px' }}>No pending drafts.</p>
            )}
            {drafts.map((d: any) => <DraftCard key={d.id} draft={d} onRefresh={load} />)}
        </div>
    );
};

export default DraftingRHS;
