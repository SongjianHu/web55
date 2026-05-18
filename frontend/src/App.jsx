import { useState } from 'react';
import { useSession } from './state/SessionContext.jsx';
import AppHeader from './components/layout/AppHeader.jsx';
import MainLayout from './components/layout/MainLayout.jsx';
import ModeSwitch from './components/modes/ModeSwitch.jsx';
import UploadZone from './components/upload/UploadZone.jsx';
import Toolbar from './components/toolbar/Toolbar.jsx';
import FormatPane from './components/modes/FormatPane/FormatPane.jsx';
import CheckPane from './components/modes/CheckPane/CheckPane.jsx';
import QaPane from './components/modes/QaPane/QaPane.jsx';
import PreviewPane from './components/preview/PreviewPane.jsx';
import BatchModal from './components/batch/BatchModal.jsx';

export default function App() {
  const { mode } = useSession();
  const [batchOpen, setBatchOpen] = useState(false);

  const left = (
    <div className="flex min-h-0 flex-1 flex-col gap-2.5 overflow-hidden pt-3.5">
      <div className="px-3.5">
        <ModeSwitch />
      </div>
      <UploadZone />
      <Toolbar onOpenBatch={() => setBatchOpen(true)} />
      <div className="flex min-h-0 flex-1 flex-col px-0 pb-0">
        {mode === 'format' && <FormatPane />}
        {mode === 'check' && (
          <div className="flex min-h-0 flex-1 flex-col px-3.5 pb-3.5">
            <CheckPane />
          </div>
        )}
        {mode === 'qa' && (
          <div className="flex min-h-0 flex-1 flex-col px-3.5 pb-3.5">
            <QaPane />
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div className="flex h-full flex-col">
      <AppHeader />
      <MainLayout left={left} right={<PreviewPane />} />
      <BatchModal open={batchOpen} onClose={() => setBatchOpen(false)} />
    </div>
  );
}
