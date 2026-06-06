import React from 'react';

interface Props {
    post: any;
    showRHSPlugin: () => void;
}

const DraftEphemeralPost: React.FC<Props> = ({ post, showRHSPlugin }) => {
    return (
        <div style={{
            padding: '12px 16px',
            background: 'var(--center-channel-bg)',
            border: '1px solid var(--center-channel-color-16)',
            borderRadius: '4px',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
        }}>
            <span style={{ fontSize: '20px' }}>✏️</span>
            <div style={{ flex: 1 }}>
                <strong style={{ color: 'var(--center-channel-color)' }}>AEGIS has a draft reply</strong>
                <div style={{ fontSize: '13px', color: 'var(--center-channel-color-72)', marginTop: '2px' }}>
                    Review it in the AI drafting panel before sending.
                </div>
            </div>
            <button
                onClick={showRHSPlugin}
                style={{
                    background: 'var(--button-bg)',
                    color: 'var(--button-color)',
                    border: 'none',
                    borderRadius: '4px',
                    padding: '8px 16px',
                    cursor: 'pointer',
                    fontWeight: 600,
                    fontSize: '14px',
                    whiteSpace: 'nowrap',
                }}
            >
                Open drafting surface
            </button>
        </div>
    );
};

export default DraftEphemeralPost;
