export interface Draft {
    id: string;
    reply: string;
    reason: string;
    provenance: string[];
    contexts: Array<{text: string; source: string; score: number}>;
    trigger_text: string;
    channel_id: string;
}

export interface KBDocument {
    id: string;
    filename: string;
    chunk_count: number;
    created_at: string;
}
