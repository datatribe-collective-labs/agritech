// A template (unlike a layout) starts again on every navigation, so each screen eases in.
export default function Template({ children }: { children: React.ReactNode }) {
  return <div className="page">{children}</div>;
}
