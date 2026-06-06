const BRIDGE = 'http://localhost:8080';

function getToken(): string {
    return (window as any).MattermostClient4?.getToken?.() ?? '';
}

function headers(): HeadersInit {
    return { 'Authorization': `Bearer ${getToken()}`, 'Content-Type': 'application/json' };
}

export async function listDrafts(): Promise<any[]> {
    const resp = await fetch(`${BRIDGE}/aegis/drafts`, { headers: headers() });
    if (!resp.ok) throw new Error(`listDrafts: ${resp.status}`);
    return resp.json();
}

export async function approveDraft(draftId: string): Promise<any> {
    const resp = await fetch(`${BRIDGE}/aegis/approve`, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({ context: { draft_id: draftId }, user_id: '' }),
    });
    if (!resp.ok) throw new Error(`approveDraft: ${resp.status}`);
    return resp.json();
}

export async function discardDraft(draftId: string): Promise<any> {
    const resp = await fetch(`${BRIDGE}/aegis/discard`, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({ context: { draft_id: draftId }, user_id: '' }),
    });
    if (!resp.ok) throw new Error(`discardDraft: ${resp.status}`);
    return resp.json();
}

export async function sendDraft(draftId: string, text: string): Promise<any> {
    const resp = await fetch(`${BRIDGE}/aegis/send`, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({ draft_id: draftId, text }),
    });
    if (!resp.ok) throw new Error(`sendDraft: ${resp.status}`);
    return resp.json();
}

export async function listKBDocuments(scope: 'public' | 'private'): Promise<any[]> {
    const resp = await fetch(`${BRIDGE}/aegis/kb/${scope}/documents`, { headers: headers() });
    if (!resp.ok) throw new Error(`listKBDocuments: ${resp.status}`);
    return resp.json();
}

export async function uploadKBDocument(scope: 'public' | 'private', file: File): Promise<any> {
    const form = new FormData();
    form.append('file', file);
    const tok = getToken();
    const resp = await fetch(`${BRIDGE}/aegis/kb/${scope}/documents`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${tok}` },  // no Content-Type, let browser set multipart boundary
        body: form,
    });
    if (!resp.ok) throw new Error(`uploadKBDocument: ${resp.status}`);
    return resp.json();
}

export async function deleteKBDocument(scope: 'public' | 'private', docId: string): Promise<void> {
    const resp = await fetch(`${BRIDGE}/aegis/kb/${scope}/documents/${docId}`, {
        method: 'DELETE',
        headers: headers(),
    });
    if (!resp.ok) throw new Error(`deleteKBDocument: ${resp.status}`);
}
