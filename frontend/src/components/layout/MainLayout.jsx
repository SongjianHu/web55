// 两栏布局：>=900px 左右分栏；<900px 上下堆叠。
export default function MainLayout({ left, right }) {
  return (
    <div className="flex flex-1 flex-col overflow-hidden pane:flex-row">
      <div className="glass-soft flex h-[54vh] min-h-0 min-w-0 flex-col overflow-hidden border-b border-white/40 pane:h-auto pane:flex-1 pane:border-b-0 pane:border-r pane:border-white/40">
        {left}
      </div>
      <div className="h-[46vh] w-full flex-shrink-0 pane:h-auto pane:w-[760px] lg:w-[820px] xl:w-[860px]">
        {right}
      </div>
    </div>
  );
}
