// 图标统一走 lucide-react（开源 MIT，线性描边，符合设计规范：1.5px 描边、随文字色）。
// 保留原 <Icon name=.. size=.. /> API，调用处无需改动。
import {
  FileText,
  Upload,
  Download,
  WandSparkles,
  Undo2,
  RotateCcw,
  LayoutGrid,
  ListChecks,
  Paperclip,
  Mic,
  Send,
  Monitor,
  RefreshCw,
  Search,
  X,
  MessageCircle,
} from 'lucide-react';

const MAP = {
  file: FileText,
  upload: Upload,
  download: Download,
  wand: WandSparkles,
  undo: Undo2,
  reset: RotateCcw,
  grid: LayoutGrid,
  checklist: ListChecks,
  paperclip: Paperclip,
  mic: Mic,
  send: Send,
  screen: Monitor,
  refresh: RefreshCw,
  search: Search,
  close: X,
  chat: MessageCircle,
};

export default function Icon({ name, size = 18, className = '', ...rest }) {
  const Cmp = MAP[name];
  if (!Cmp) return null;
  return (
    <Cmp
      size={size}
      strokeWidth={1.5}
      absoluteStrokeWidth
      className={className}
      aria-hidden="true"
      {...rest}
    />
  );
}
