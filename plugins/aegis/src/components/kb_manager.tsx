import React, { useState, useEffect, useRef } from 'react';
import { listKBDocuments, uploadKBDocument, deleteKBDocument } from '../client/bridge_client';

const KBManager: React.FC = () => {
    const [scope, setScope] = useState<'public' | 'private'>('private');
    const [docs, setDocs] = useState<any[]>([]);
    const [loading, setLoading] = useState(false);
    const [err, setErr] = useState('');
    const [busy, setBusy] = useState('');
    const fileRef = useRef<HTMLInputElement>(null);

    const load = async () => {
        setLoading(true); setErr('');
        try { setDocs(await listKBDocuments(scope)); }
        catch (e: any) { setErr(e.message); }
        finally { setLoading(false); }
    };

    useEffect(() => { load(); }, [scope]);

    const upload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]; if (!file) return;
        setBusy('Uploading…');
        try { await uploadKBDocument(scope, file); await load(); }
        catch (e: any) { setErr(e.message); }
        finally { setBusy(''); if (fileRef.current) fileRef.current.value = ''; }
    };

    const remove = async (docId: string) => {
        setBusy(docId);
        try { await deleteKBDocument(scope, docId); await load(); }
        catch (e: any) { setErr(e.message); }
        finally { setBusy(''); }
    };

    return (
        <div>
            <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
                {(['private', 'public'] as const).map(s => (
                    <button key={s} onClick={() => setScope(s)} style={{
                        padding: '6px 14px', borderRadius: '4px', border: 'none',
                        cursor: 'pointer', fontWeight: 600, fontSize: '13px',
                        background: scope === s ? 'var(--button-bg)' : 'var(--center-channel-color-08)',
                        color: scope === s ? 'var(--button-color)' : 'var(--center-channel-color)',
                    }}>
                        {s === 'private' ? '🔒 Private' : '🌐 Public'}
                    </button>
                ))}
            </div>

            {err && <p style={{ color: 'var(--error-text)', fontSize: '12px' }}>{err}</p>}
            {loading && <p style={{ color: 'var(--center-channel-color-56)', fontSize: '13px' }}>Loading…</p>}
            {busy && busy !== '' && !loading && <p style={{ color: 'var(--center-channel-color-56)', fontSize: '12px' }}>{busy === 'Uploading…' ? busy : 'Removing…'}</p>}

            <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 16px' }}>
                {docs.map((d: any) => (
                    <li key={d.id} style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        padding: '8px 0', borderBottom: '1px solid var(--center-channel-color-08)',
                        fontSize: '13px',
                    }}>
                        <span style={{ color: 'var(--center-channel-color)' }}>
                            📄 {d.filename}
                            <span style={{ color: 'var(--center-channel-color-56)', marginLeft: '8px' }}>
                                {d.chunk_count} chunk{d.chunk_count !== 1 ? 's' : ''}
                            </span>
                        </span>
                        <button
                            disabled={!!busy}
                            onClick={() => remove(d.id)}
                            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--error-text)', fontSize: '16px' }}
                            title="Remove document"
                        >
                            ×
                        </button>
                    </li>
                ))}
            </ul>

            <label style={{
                display: 'inline-block', padding: '8px 16px',
                background: 'var(--center-channel-color-08)', borderRadius: '4px',
                cursor: 'pointer', fontSize: '13px', fontWeight: 600,
                color: 'var(--center-channel-color)',
            }}>
                + Add document
                <input ref={fileRef} type="file" style={{ display: 'none' }} onChange={upload} />
            </label>
        </div>
    );
};

export default KBManager;
