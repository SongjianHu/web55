import StructurePanel from './StructurePanel.jsx';
import DefaultsPanel from './DefaultsPanel.jsx';
import Chat from './Chat.jsx';
import Composer from './Composer.jsx';

export default function FormatPane() {
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2.5">
      <StructurePanel />
      <DefaultsPanel />
      <Chat />
      <Composer />
    </div>
  );
}
