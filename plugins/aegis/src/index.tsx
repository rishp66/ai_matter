import React from 'react';
import DraftingRHS from './components/drafting_rhs';
import DraftEphemeralPost from './components/draft_ephemeral_post';
import KBManager from './components/kb_manager';

// RHS tab state
let _showRHSPlugin: (() => void) | null = null;

const RHSRoot: React.FC = () => {
    const [tab, setTab] = React.useState<'drafts' | 'kb'>('drafts');
    return (
        <div style={{ height: '100%', display: 'flex', flexDirection: 'column', fontFamily: 'var(--font-family)' }}>
            <div style={{ display: 'flex', borderBottom: '1px solid var(--center-channel-color-16)', padding: '0 20px' }}>
                {(['drafts', 'kb'] as const).map(t => (
                    <button key={t} onClick={() => setTab(t)} style={{
                        background: 'none', border: 'none', borderBottom: tab === t ? '2px solid var(--button-bg)' : '2px solid transparent',
                        padding: '12px 16px', cursor: 'pointer', fontWeight: tab === t ? 700 : 400,
                        color: tab === t ? 'var(--button-bg)' : 'var(--center-channel-color-72)',
                        fontSize: '14px',
                    }}>
                        {t === 'drafts' ? '✏️ Drafts' : '📚 Knowledge'}
                    </button>
                ))}
            </div>
            <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
                {tab === 'drafts' ? <DraftingRHS /> : <KBManager />}
            </div>
        </div>
    );
};

class AegisDraftingPlugin {
    initialize(registry: any, _store: any) {
        // Register RHS panel
        const { showRHSPlugin, toggleRHSPlugin } = registry.registerRightHandSidebarComponent({
            component: RHSRoot,
            title: 'AEGIS',
        });
        _showRHSPlugin = showRHSPlugin;

        // Register custom post type renderer for ephemeral draft nudges
        registry.registerPostTypeComponent({
            type: 'custom_aegis_draft',
            component: (props: any) => React.createElement(DraftEphemeralPost, {
                ...props,
                showRHSPlugin,
            }),
        });

        // Register channel header button
        registry.registerChannelHeaderButtonAction({
            icon: React.createElement('span', { style: { fontSize: '18px' } }, '✏️'),
            action: toggleRHSPlugin,
            dropdownText: 'AEGIS Draft',
            tooltipText: 'Open AEGIS drafting surface',
        });
    }
}

(window as any).registerPlugin('com.aegis.drafting', new AegisDraftingPlugin());
